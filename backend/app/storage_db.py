from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from . import models, schemas
from .security import decrypt_secret, encrypt_secret


@dataclass(frozen=True)
class BudgetUsageTotals:
    token_used: int
    video_seconds_used: int
    publications_used: int


class DatabaseStore:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.jwt_secret_key = os.getenv("JWT_SECRET_KEY", "change_me")
        self.jwt_algorithm = os.getenv("JWT_ALGORITHM", "HS256")
        self.jwt_expire_minutes = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

    def has_users(self) -> bool:
        return bool(self.session.scalar(select(models.User.id)))

    def get_user_by_email(self, email: str) -> Optional[models.User]:
        return self.session.scalar(select(models.User).where(models.User.email == email))

    def list_users(self) -> List[schemas.User]:
        users = self.session.scalars(select(models.User)).all()
        return [self.to_user_schema(user) for user in users]

    def create_role(self, name: str) -> models.Role:
        role = self.session.scalar(select(models.Role).where(models.Role.name == name))
        if role:
            return role
        role = models.Role(name=name)
        self.session.add(role)
        self.session.flush()
        return role

    def list_roles(self) -> List[schemas.Role]:
        roles = self.session.scalars(select(models.Role)).all()
        return [self._to_role(role) for role in roles]

    def create_user(self, payload: schemas.UserCreate, password_hash: str) -> schemas.User:
        user = models.User(
            email=payload.email,
            hashed_password=password_hash,
            is_active=payload.is_active,
        )
        self.session.add(user)
        for role_name in sorted(set(payload.roles)):
            role = self.create_role(role_name)
            self.session.add(models.UserRole(user=user, role=role))
        self.session.flush()
        return self.to_user_schema(user)

    def list_projects(self) -> List[schemas.Project]:
        projects = self.session.scalars(select(models.Project)).all()
        return [self._to_project(project) for project in projects]

    def get_project(self, project_id: int) -> schemas.Project:
        project = self.session.get(models.Project, project_id)
        if not project:
            raise KeyError("project_not_found")
        return self._to_project(project)

    def create_project(self, payload: schemas.ProjectCreate) -> schemas.Project:
        project = models.Project(
            name=payload.name,
            description=payload.description,
            status="active",
        )
        self.session.add(project)
        self.session.flush()
        dataset = models.ProjectDataset(
            project=project,
            name=f"project_{project.id}_dataset",
            kind="atoms",
            storage_uri=f"s3://datasets/project_{project.id}",
            is_active=True,
        )
        vector_index = models.ProjectVectorIndex(
            project=project,
            name=f"project_{project.id}_atoms",
            provider="pgvector",
            embedding_dimension=1536,
            metadata={"table": "atoms"},
        )
        self.session.add_all([dataset, vector_index])
        return self._to_project(project)

    def create_brand_config(
        self, project_id: int, payload: schemas.BrandConfigCreate
    ) -> schemas.BrandConfig:
        project = self._require_project(project_id)
        latest = (
            self.session.scalar(
                select(models.BrandConfig)
                .where(models.BrandConfig.project_id == project_id)
                .order_by(models.BrandConfig.version.desc())
            )
            or None
        )
        next_version = latest.version + 1 if latest else 1
        for active_config in self.session.scalars(
            select(models.BrandConfig).where(
                models.BrandConfig.project_id == project_id,
                models.BrandConfig.is_active.is_(True),
            )
        ):
            active_config.is_active = False
        config = models.BrandConfig(
            project=project,
            version=next_version,
            is_active=True,
            is_stable=payload.is_stable,
            tone=payload.tone,
            audience=payload.audience,
            offers=payload.offers,
            rubrics=payload.rubrics,
            forbidden=payload.forbidden,
            cta_policy=payload.cta_policy,
        )
        self.session.add(config)
        self.session.flush()
        self._record_brand_config_history(
            project_id=project_id,
            config=config,
            previous=latest,
            change_summary=payload.change_summary,
        )
        return self._to_brand_config(config)

    def list_brand_configs(self, project_id: int) -> List[schemas.BrandConfig]:
        self._require_project(project_id)
        configs = self.session.scalars(
            select(models.BrandConfig).where(models.BrandConfig.project_id == project_id)
        ).all()
        return [self._to_brand_config(config) for config in configs]

    def list_brand_config_history(self, project_id: int) -> List[schemas.BrandConfigHistory]:
        self._require_project(project_id)
        history = self.session.scalars(
            select(models.BrandConfigHistory)
            .where(models.BrandConfigHistory.project_id == project_id)
            .order_by(models.BrandConfigHistory.created_at.desc())
        ).all()
        return [self._to_brand_config_history(entry) for entry in history]

    def set_brand_config_stable(
        self, project_id: int, config_id: int, payload: schemas.StableVersionUpdate
    ) -> schemas.BrandConfig:
        config = self.session.get(models.BrandConfig, config_id)
        if not config or config.project_id != project_id:
            raise KeyError("brand_config_not_found")
        previous = self._brand_config_snapshot(config)
        config.is_stable = payload.is_stable
        self.session.add(config)
        self.session.flush()
        self.session.add(
            models.BrandConfigHistory(
                project_id=project_id,
                brand_config_id=config.id,
                version=config.version,
                change_summary="stable_status_changed",
                change_payload={
                    "previous": previous,
                    "current": self._brand_config_snapshot(config),
                },
            )
        )
        return self._to_brand_config(config)

    def rollback_brand_config(
        self, project_id: int, payload: schemas.BrandConfigRollback
    ) -> schemas.BrandConfig:
        self._require_project(project_id)
        target = self.session.scalar(
            select(models.BrandConfig).where(
                models.BrandConfig.project_id == project_id,
                models.BrandConfig.version == payload.version,
            )
        )
        if not target:
            raise KeyError("brand_config_not_found")
        if not target.is_stable:
            raise ValueError("brand_config_not_stable")
        latest = self.session.scalar(
            select(models.BrandConfig)
            .where(models.BrandConfig.project_id == project_id)
            .order_by(models.BrandConfig.version.desc())
        )
        next_version = latest.version + 1 if latest else 1
        for active_config in self.session.scalars(
            select(models.BrandConfig).where(
                models.BrandConfig.project_id == project_id,
                models.BrandConfig.is_active.is_(True),
            )
        ):
            active_config.is_active = False
        config = models.BrandConfig(
            project_id=project_id,
            version=next_version,
            is_active=True,
            is_stable=False,
            tone=target.tone,
            audience=target.audience,
            offers=target.offers,
            rubrics=target.rubrics,
            forbidden=target.forbidden,
            cta_policy=target.cta_policy,
        )
        self.session.add(config)
        self.session.flush()
        self._record_brand_config_history(
            project_id=project_id,
            config=config,
            previous=latest,
            change_summary=payload.change_summary
            or f"rollback_to_version_{target.version}",
        )
        return self._to_brand_config(config)

    def create_budget(self, project_id: int, payload: schemas.BudgetCreate) -> schemas.Budget:
        project = self._require_project(project_id)
        budget = models.Budget(
            project=project,
            daily=payload.daily,
            weekly=payload.weekly,
            monthly=payload.monthly,
            token_limit=payload.token_limit,
            video_seconds_limit=payload.video_seconds_limit,
            publication_limit=payload.publication_limit,
        )
        self.session.add(budget)
        self.session.flush()
        return self._to_budget(budget)

    def list_budgets(self, project_id: int) -> List[schemas.Budget]:
        self._require_project(project_id)
        budgets = self.session.scalars(
            select(models.Budget).where(models.Budget.project_id == project_id)
        ).all()
        return [self._to_budget(budget) for budget in budgets]

    def get_latest_budget(self, project_id: int) -> Optional[schemas.Budget]:
        self._require_project(project_id)
        budget = self.session.scalar(
            select(models.Budget)
            .where(models.Budget.project_id == project_id)
            .order_by(models.Budget.created_at.desc())
        )
        if not budget:
            return None
        return self._to_budget(budget)

    def create_budget_usage(
        self, project_id: int, payload: schemas.BudgetUsageCreate
    ) -> schemas.BudgetUsage:
        project = self._require_project(project_id)
        budget = self.session.get(models.Budget, payload.budget_id)
        if not budget or budget.project_id != project_id:
            raise KeyError("budget_not_found")
        usage = models.BudgetUsage(
            budget=budget,
            project=project,
            usage_date=payload.usage_date,
            token_used=payload.token_used,
            video_seconds_used=payload.video_seconds_used,
            publications_used=payload.publications_used,
        )
        self.session.add(usage)
        self.session.flush()
        return self._to_budget_usage(usage)

    def list_budget_usages(self, project_id: int) -> List[schemas.BudgetUsage]:
        self._require_project(project_id)
        usages = self.session.scalars(
            select(models.BudgetUsage).where(models.BudgetUsage.project_id == project_id)
        ).all()
        return [self._to_budget_usage(usage) for usage in usages]

    def sum_budget_usage(
        self, project_id: int, start: datetime, end: datetime
    ) -> BudgetUsageTotals:
        self._require_project(project_id)
        totals = self.session.execute(
            select(
                func.coalesce(func.sum(models.BudgetUsage.token_used), 0),
                func.coalesce(func.sum(models.BudgetUsage.video_seconds_used), 0),
                func.coalesce(func.sum(models.BudgetUsage.publications_used), 0),
            ).where(
                models.BudgetUsage.project_id == project_id,
                models.BudgetUsage.usage_date >= start,
                models.BudgetUsage.usage_date <= end,
            )
        ).one()
        return BudgetUsageTotals(
            token_used=int(totals[0] or 0),
            video_seconds_used=int(totals[1] or 0),
            publications_used=int(totals[2] or 0),
        )

    def create_source(self, project_id: int, payload: schemas.SourceCreate) -> schemas.Source:
        project = self._require_project(project_id)
        source = models.Source(
            project=project,
            title=payload.title,
            source_type=payload.source_type,
            uri=payload.uri,
            content=payload.content,
            artifact_uri=payload.artifact_uri,
            artifact_version=payload.artifact_version,
            artifact_metadata=payload.artifact_metadata,
            status=payload.status,
            is_current=payload.is_current,
        )
        self.session.add(source)
        self.session.flush()
        return self._to_source(source)

    def list_sources(self, project_id: int) -> List[schemas.Source]:
        self._require_project(project_id)
        sources = self.session.scalars(
            select(models.Source).where(models.Source.project_id == project_id)
        ).all()
        return [self._to_source(source) for source in sources]

    def update_source(
        self, project_id: int, source_id: int, payload: schemas.SourceUpdate
    ) -> schemas.Source:
        source = self.session.get(models.Source, source_id)
        if not source or source.project_id != project_id:
            raise KeyError("source_not_found")
        updates = payload.model_dump(exclude_unset=True)
        for field_name, value in updates.items():
            setattr(source, field_name, value)
        self.session.add(source)
        self.session.flush()
        return self._to_source(source)

    def create_atom(self, project_id: int, payload: schemas.AtomCreate) -> schemas.Atom:
        project = self._require_project(project_id)
        source = self.session.get(models.Source, payload.source_id)
        if not source or source.project_id != project_id:
            raise KeyError("source_not_found")
        atom = models.Atom(
            project=project,
            source=source,
            kind=payload.kind,
            text=payload.text,
            source_backed=payload.source_backed,
            embedding=payload.embedding,
            source_uri=payload.source_uri,
            source_version=payload.source_version,
            artifact_uri=payload.artifact_uri,
            artifact_version=payload.artifact_version,
            artifact_metadata=payload.artifact_metadata,
            status=payload.status,
            is_current=payload.is_current,
        )
        self.session.add(atom)
        self.session.flush()
        return self._to_atom(atom)

    def list_atoms(self, project_id: int) -> List[schemas.Atom]:
        self._require_project(project_id)
        atoms = self.session.scalars(
            select(models.Atom).where(models.Atom.project_id == project_id)
        ).all()
        return [self._to_atom(atom) for atom in atoms]

    def get_topic(self, project_id: int, topic_id: int) -> schemas.Topic:
        topic = self.session.get(models.Topic, topic_id)
        if not topic or topic.project_id != project_id:
            raise KeyError("topic_not_found")
        return self._to_topic(topic)

    def create_topic(self, project_id: int, payload: schemas.TopicCreate) -> schemas.Topic:
        project = self._require_project(project_id)
        topic = models.Topic(
            project=project,
            title=payload.title,
            angle=payload.angle,
            rubric=payload.rubric,
            planned_for=payload.planned_for,
            status="planned",
        )
        self.session.add(topic)
        self.session.flush()
        return self._to_topic(topic)

    def list_topics(self, project_id: int) -> List[schemas.Topic]:
        self._require_project(project_id)
        topics = self.session.scalars(
            select(models.Topic).where(models.Topic.project_id == project_id)
        ).all()
        return [self._to_topic(topic) for topic in topics]

    def create_content_pack(
        self, project_id: int, payload: schemas.ContentPackCreate
    ) -> schemas.ContentPack:
        project = self._require_project(project_id)
        topic = self.session.get(models.Topic, payload.topic_id)
        if not topic or topic.project_id != project_id:
            raise KeyError("topic_not_found")
        pack = models.ContentPack(
            project=project,
            topic=topic,
            description=payload.description,
            status="queued",
        )
        self.session.add(pack)
        self.session.flush()
        return self._to_content_pack(pack)

    def list_content_packs(self, project_id: int) -> List[schemas.ContentPack]:
        self._require_project(project_id)
        packs = self.session.scalars(
            select(models.ContentPack).where(models.ContentPack.project_id == project_id)
        ).all()
        return [self._to_content_pack(pack) for pack in packs]

    def create_content_item(
        self, project_id: int, payload: schemas.ContentItemCreate
    ) -> schemas.ContentItem:
        project = self._require_project(project_id)
        pack = self.session.get(models.ContentPack, payload.pack_id)
        if not pack or pack.project_id != project_id:
            raise KeyError("content_pack_not_found")
        item = models.ContentItem(
            project=project,
            content_pack=pack,
            channel=payload.channel,
            format=payload.format,
            body=payload.body,
            metadata=payload.metadata,
            status="draft",
        )
        self.session.add(item)
        self.session.flush()
        return self._to_content_item(item)

    def list_content_items(self, project_id: int) -> List[schemas.ContentItem]:
        self._require_project(project_id)
        items = self.session.scalars(
            select(models.ContentItem).where(models.ContentItem.project_id == project_id)
        ).all()
        return [self._to_content_item(item) for item in items]

    def get_content_item(
        self, project_id: int, content_item_id: int
    ) -> schemas.ContentItem:
        item = self.session.get(models.ContentItem, content_item_id)
        if not item or item.project_id != project_id:
            raise KeyError("content_item_not_found")
        return self._to_content_item(item)

    def get_content_item_with_topic(
        self, project_id: int, content_item_id: int
    ) -> tuple[schemas.ContentItem, schemas.Topic]:
        item = self.session.get(models.ContentItem, content_item_id)
        if not item or item.project_id != project_id:
            raise KeyError("content_item_not_found")
        topic = item.content_pack.topic if item.content_pack else None
        if not topic:
            raise KeyError("topic_not_found")
        return self._to_content_item(item), self._to_topic(topic)

    def update_content_item_metadata(
        self, project_id: int, content_item_id: int, metadata_update: dict
    ) -> schemas.ContentItem:
        item = self.session.get(models.ContentItem, content_item_id)
        if not item or item.project_id != project_id:
            raise KeyError("content_item_not_found")
        metadata = dict(item.metadata or {})
        metadata.update(metadata_update)
        item.metadata = metadata
        self.session.add(item)
        self.session.flush()
        return self._to_content_item(item)

    def update_content_item_status(
        self, project_id: int, content_item_id: int, status: str
    ) -> schemas.ContentItem:
        item = self.session.get(models.ContentItem, content_item_id)
        if not item or item.project_id != project_id:
            raise KeyError("content_item_not_found")
        item.status = status
        self.session.add(item)
        self.session.flush()
        return self._to_content_item(item)

    def create_qc_report(
        self, project_id: int, payload: schemas.QcReportCreate
    ) -> schemas.QcReport:
        project = self._require_project(project_id)
        item = self.session.get(models.ContentItem, payload.content_item_id)
        if not item or item.project_id != project_id:
            raise KeyError("content_item_not_found")
        report = models.QcReport(
            project=project,
            content_item=item,
            score=payload.score,
            passed=payload.passed,
            reasons=payload.reasons,
        )
        self.session.add(report)
        self.session.flush()
        return self._to_qc_report(report)

    def list_qc_reports(self, project_id: int) -> List[schemas.QcReport]:
        self._require_project(project_id)
        reports = self.session.scalars(
            select(models.QcReport).where(models.QcReport.project_id == project_id)
        ).all()
        return [self._to_qc_report(report) for report in reports]

    def create_publication(
        self, project_id: int, payload: schemas.PublicationCreate
    ) -> schemas.Publication:
        project = self._require_project(project_id)
        item = self.session.get(models.ContentItem, payload.content_item_id)
        if not item or item.project_id != project_id:
            raise KeyError("content_item_not_found")
        publication = models.Publication(
            project=project,
            content_item=item,
            platform=payload.platform,
            scheduled_at=payload.scheduled_at,
            status=payload.status,
            idempotency_key=payload.idempotency_key,
        )
        self.session.add(publication)
        self.session.flush()
        return self._to_publication(publication)

    def list_publications(self, project_id: int) -> List[schemas.Publication]:
        self._require_project(project_id)
        publications = self.session.scalars(
            select(models.Publication).where(models.Publication.project_id == project_id)
        ).all()
        return [self._to_publication(publication) for publication in publications]

    def get_publication_by_idempotency_key(
        self, project_id: int, idempotency_key: str
    ) -> Optional[schemas.Publication]:
        self._require_project(project_id)
        publication = self.session.scalar(
            select(models.Publication).where(
                models.Publication.project_id == project_id,
                models.Publication.idempotency_key == idempotency_key,
            )
        )
        if not publication:
            return None
        return self._to_publication(publication)

    def list_due_publications(
        self, project_id: int, scheduled_before: datetime
    ) -> List[schemas.Publication]:
        self._require_project(project_id)
        publications = self.session.scalars(
            select(models.Publication).where(
                models.Publication.project_id == project_id,
                models.Publication.status == "scheduled",
                models.Publication.scheduled_at <= scheduled_before,
            )
        ).all()
        return [self._to_publication(publication) for publication in publications]

    def create_metric_snapshot(
        self, project_id: int, payload: schemas.MetricSnapshotCreate
    ) -> schemas.MetricSnapshot:
        project = self._require_project(project_id)
        item = self.session.get(models.ContentItem, payload.content_item_id)
        if not item or item.project_id != project_id:
            raise KeyError("content_item_not_found")
        snapshot = models.MetricSnapshot(
            project=project,
            content_item=item,
            impressions=payload.impressions,
            clicks=payload.clicks,
            likes=payload.likes,
            comments=payload.comments,
            shares=payload.shares,
        )
        self.session.add(snapshot)
        self.session.flush()
        return self._to_metric_snapshot(snapshot)

    def list_metric_snapshots(self, project_id: int) -> List[schemas.MetricSnapshot]:
        self._require_project(project_id)
        snapshots = self.session.scalars(
            select(models.MetricSnapshot).where(
                models.MetricSnapshot.project_id == project_id
            )
        ).all()
        return [self._to_metric_snapshot(snapshot) for snapshot in snapshots]

    def list_recent_metric_snapshots(
        self, project_id: int, limit: int
    ) -> List[models.MetricSnapshot]:
        self._require_project(project_id)
        return (
            self.session.scalars(
                select(models.MetricSnapshot)
                .where(models.MetricSnapshot.project_id == project_id)
                .order_by(desc(models.MetricSnapshot.collected_at))
                .limit(limit)
            )
            .unique()
            .all()
        )

    def create_learning_event(
        self, project_id: int, payload: schemas.LearningEventCreate
    ) -> schemas.LearningEvent:
        project = self._require_project(project_id)
        event = models.LearningEvent(
            project=project,
            parameter=payload.parameter,
            previous_value=payload.previous_value,
            new_value=payload.new_value,
            reason=payload.reason,
        )
        self.session.add(event)
        self.session.flush()
        return self._to_learning_event(event)

    def list_learning_events(self, project_id: int) -> List[schemas.LearningEvent]:
        self._require_project(project_id)
        events = self.session.scalars(
            select(models.LearningEvent).where(models.LearningEvent.project_id == project_id)
        ).all()
        return [self._to_learning_event(event) for event in events]

    def get_or_create_auto_learning_config(
        self, project_id: int
    ) -> schemas.AutoLearningConfig:
        self._require_project(project_id)
        config = self.session.scalar(
            select(models.AutoLearningConfig).where(
                models.AutoLearningConfig.project_id == project_id
            )
        )
        if config:
            return self._to_auto_learning_config(config)
        config = models.AutoLearningConfig(
            project_id=project_id,
            max_changes_per_week=2,
            rollback_threshold=0.02,
            rollback_window=20,
            protected_parameters=[],
        )
        self.session.add(config)
        self.session.flush()
        return self._to_auto_learning_config(config)

    def upsert_auto_learning_config(
        self, project_id: int, payload: schemas.AutoLearningConfigCreate
    ) -> schemas.AutoLearningConfig:
        self._require_project(project_id)
        config = self.session.scalar(
            select(models.AutoLearningConfig).where(
                models.AutoLearningConfig.project_id == project_id
            )
        )
        if not config:
            config = models.AutoLearningConfig(project_id=project_id)
        config.max_changes_per_week = payload.max_changes_per_week
        config.rollback_threshold = payload.rollback_threshold
        config.rollback_window = payload.rollback_window
        config.protected_parameters = payload.protected_parameters
        self.session.add(config)
        self.session.flush()
        return self._to_auto_learning_config(config)

    def get_or_create_auto_learning_state(
        self, project_id: int
    ) -> schemas.AutoLearningState:
        self._require_project(project_id)
        state = self.session.scalar(
            select(models.AutoLearningState).where(
                models.AutoLearningState.project_id == project_id
            )
        )
        if state:
            return self._to_auto_learning_state(state)
        state = models.AutoLearningState(
            project_id=project_id,
            parameters={},
            stable_parameters={},
            window_started_at=None,
            changes_in_window=0,
        )
        self.session.add(state)
        self.session.flush()
        return self._to_auto_learning_state(state)

    def update_auto_learning_state(
        self, project_id: int, payload: schemas.AutoLearningState
    ) -> schemas.AutoLearningState:
        self._require_project(project_id)
        state = self.session.scalar(
            select(models.AutoLearningState).where(
                models.AutoLearningState.project_id == project_id
            )
        )
        if not state:
            state = models.AutoLearningState(project_id=project_id)
        state.parameters = payload.parameters
        state.stable_parameters = payload.stable_parameters
        state.window_started_at = payload.window_started_at
        state.changes_in_window = payload.changes_in_window
        state.last_change_at = payload.last_change_at
        state.last_rollback_at = payload.last_rollback_at
        self.session.add(state)
        self.session.flush()
        return self._to_auto_learning_state(state)

    def create_prompt_version(
        self, project_id: int, payload: schemas.PromptVersionCreate
    ) -> schemas.PromptVersion:
        project = self._require_project(project_id)
        latest = (
            self.session.scalar(
                select(models.PromptVersion)
                .where(
                    models.PromptVersion.project_id == project_id,
                    models.PromptVersion.prompt_key == payload.prompt_key,
                )
                .order_by(models.PromptVersion.version.desc())
            )
            or None
        )
        next_version = latest.version + 1 if latest else 1
        if payload.is_active:
            for active_prompt in self.session.scalars(
                select(models.PromptVersion).where(
                    models.PromptVersion.project_id == project_id,
                    models.PromptVersion.prompt_key == payload.prompt_key,
                    models.PromptVersion.is_active.is_(True),
                )
            ):
                active_prompt.is_active = False
        prompt = models.PromptVersion(
            project=project,
            prompt_key=payload.prompt_key,
            content=payload.content,
            version=next_version,
            is_active=payload.is_active,
            is_stable=payload.is_stable,
        )
        self.session.add(prompt)
        self.session.flush()
        self._record_prompt_history(
            project_id=project_id,
            prompt=prompt,
            previous=latest,
            change_summary=payload.change_summary,
        )
        return self._to_prompt_version(prompt)

    def list_prompt_versions(self, project_id: int) -> List[schemas.PromptVersion]:
        self._require_project(project_id)
        prompts = self.session.scalars(
            select(models.PromptVersion).where(
                models.PromptVersion.project_id == project_id
            )
        ).all()
        return [self._to_prompt_version(prompt) for prompt in prompts]

    def list_prompt_version_history(
        self, project_id: int
    ) -> List[schemas.PromptVersionHistory]:
        self._require_project(project_id)
        history = self.session.scalars(
            select(models.PromptVersionHistory)
            .where(models.PromptVersionHistory.project_id == project_id)
            .order_by(models.PromptVersionHistory.created_at.desc())
        ).all()
        return [self._to_prompt_version_history(entry) for entry in history]

    def set_prompt_version_stable(
        self, project_id: int, prompt_id: int, payload: schemas.StableVersionUpdate
    ) -> schemas.PromptVersion:
        prompt = self.session.get(models.PromptVersion, prompt_id)
        if not prompt or prompt.project_id != project_id:
            raise KeyError("prompt_version_not_found")
        previous = self._prompt_snapshot(prompt)
        prompt.is_stable = payload.is_stable
        self.session.add(prompt)
        self.session.flush()
        self.session.add(
            models.PromptVersionHistory(
                project_id=project_id,
                prompt_version_id=prompt.id,
                prompt_key=prompt.prompt_key,
                version=prompt.version,
                change_summary="stable_status_changed",
                change_payload={
                    "previous": previous,
                    "current": self._prompt_snapshot(prompt),
                },
            )
        )
        return self._to_prompt_version(prompt)

    def rollback_prompt_version(
        self, project_id: int, payload: schemas.PromptVersionRollback
    ) -> schemas.PromptVersion:
        self._require_project(project_id)
        target = self.session.scalar(
            select(models.PromptVersion).where(
                models.PromptVersion.project_id == project_id,
                models.PromptVersion.prompt_key == payload.prompt_key,
                models.PromptVersion.version == payload.version,
            )
        )
        if not target:
            raise KeyError("prompt_version_not_found")
        if not target.is_stable:
            raise ValueError("prompt_version_not_stable")
        latest = self.session.scalar(
            select(models.PromptVersion)
            .where(
                models.PromptVersion.project_id == project_id,
                models.PromptVersion.prompt_key == payload.prompt_key,
            )
            .order_by(models.PromptVersion.version.desc())
        )
        next_version = latest.version + 1 if latest else 1
        for active_prompt in self.session.scalars(
            select(models.PromptVersion).where(
                models.PromptVersion.project_id == project_id,
                models.PromptVersion.prompt_key == payload.prompt_key,
                models.PromptVersion.is_active.is_(True),
            )
        ):
            active_prompt.is_active = False
        prompt = models.PromptVersion(
            project_id=project_id,
            prompt_key=target.prompt_key,
            content=target.content,
            version=next_version,
            is_active=True,
            is_stable=False,
        )
        self.session.add(prompt)
        self.session.flush()
        self._record_prompt_history(
            project_id=project_id,
            prompt=prompt,
            previous=latest,
            change_summary=payload.change_summary
            or f"rollback_to_version_{target.version}",
        )
        return self._to_prompt_version(prompt)

    def list_project_datasets(self, project_id: int) -> List[schemas.ProjectDataset]:
        self._require_project(project_id)
        datasets = self.session.scalars(
            select(models.ProjectDataset).where(
                models.ProjectDataset.project_id == project_id
            )
        ).all()
        return [self._to_project_dataset(dataset) for dataset in datasets]

    def list_project_vector_indexes(
        self, project_id: int
    ) -> List[schemas.ProjectVectorIndex]:
        self._require_project(project_id)
        indexes = self.session.scalars(
            select(models.ProjectVectorIndex).where(
                models.ProjectVectorIndex.project_id == project_id
            )
        ).all()
        return [self._to_project_vector_index(index_) for index_ in indexes]

    def create_redirect_link(
        self, project_id: int, payload: schemas.RedirectLinkCreate
    ) -> schemas.RedirectLink:
        project = self._require_project(project_id)
        content_item = None
        if payload.content_item_id is not None:
            content_item = self.session.get(models.ContentItem, payload.content_item_id)
            if not content_item or content_item.project_id != project_id:
                raise KeyError("content_item_not_found")
        if not payload.slug:
            raise ValueError("redirect_slug_required")
        link = models.RedirectLink(
            project=project,
            content_item=content_item,
            slug=payload.slug,
            target_url=payload.target_url,
            utm_params=payload.utm_params,
            is_active=payload.is_active,
        )
        self.session.add(link)
        self.session.flush()
        return self._to_redirect_link(link)

    def list_redirect_links(self, project_id: int) -> List[schemas.RedirectLink]:
        self._require_project(project_id)
        links = self.session.scalars(
            select(models.RedirectLink).where(models.RedirectLink.project_id == project_id)
        ).all()
        return [self._to_redirect_link(link) for link in links]

    def get_redirect_link_by_slug(self, slug: str) -> Optional[models.RedirectLink]:
        return self.session.scalar(
            select(models.RedirectLink).where(models.RedirectLink.slug == slug)
        )

    def create_click_event(
        self,
        project_id: int,
        redirect_link_id: int,
        content_item_id: Optional[int],
        ip_address: Optional[str],
        user_agent: Optional[str],
        referrer: Optional[str],
        utm_params: dict,
        query_params: dict,
    ) -> schemas.ClickEvent:
        project = self._require_project(project_id)
        link = self.session.get(models.RedirectLink, redirect_link_id)
        if not link or link.project_id != project_id:
            raise KeyError("redirect_link_not_found")
        content_item = None
        if content_item_id is not None:
            content_item = self.session.get(models.ContentItem, content_item_id)
            if not content_item or content_item.project_id != project_id:
                raise KeyError("content_item_not_found")
        event = models.ClickEvent(
            project=project,
            redirect_link=link,
            content_item=content_item,
            ip_address=ip_address,
            user_agent=user_agent,
            referrer=referrer,
            utm_params=utm_params,
            query_params=query_params,
        )
        self.session.add(event)
        self.session.flush()
        return self._to_click_event(event)

    def list_click_events(
        self,
        project_id: int,
        redirect_link_id: Optional[int] = None,
        content_item_id: Optional[int] = None,
    ) -> List[schemas.ClickEvent]:
        self._require_project(project_id)
        query = select(models.ClickEvent).where(
            models.ClickEvent.project_id == project_id
        )
        if redirect_link_id is not None:
            query = query.where(models.ClickEvent.redirect_link_id == redirect_link_id)
        if content_item_id is not None:
            query = query.where(models.ClickEvent.content_item_id == content_item_id)
        events = self.session.scalars(query).all()
        return [self._to_click_event(event) for event in events]

    def count_clicks(self, project_id: int, content_item_id: int) -> int:
        self._require_project(project_id)
        return int(
            self.session.scalar(
                select(func.count(models.ClickEvent.id)).where(
                    models.ClickEvent.project_id == project_id,
                    models.ClickEvent.content_item_id == content_item_id,
                )
            )
            or 0
        )

    def get_integration_token_by_provider(
        self, project_id: int, provider: str
    ) -> Optional[schemas.IntegrationToken]:
        self._require_project(project_id)
        token = self.session.scalar(
            select(models.IntegrationToken).where(
                models.IntegrationToken.project_id == project_id,
                models.IntegrationToken.provider == provider,
            )
        )
        if not token:
            return None
        return self._to_integration_token(token)

    def create_integration_token(
        self, project_id: int, payload: schemas.IntegrationTokenCreate
    ) -> schemas.IntegrationToken:
        project = self._require_project(project_id)
        token = models.IntegrationToken(
            project=project,
            provider=payload.provider,
            token_encrypted=encrypt_secret(payload.token),
        )
        self.session.add(token)
        self.session.flush()
        return self._to_integration_token(token)

    def list_integration_tokens(self, project_id: int) -> List[schemas.IntegrationToken]:
        self._require_project(project_id)
        tokens = self.session.scalars(
            select(models.IntegrationToken).where(
                models.IntegrationToken.project_id == project_id
            )
        ).all()
        return [self._to_integration_token(token) for token in tokens]

    def get_integration_token(
        self, project_id: int, token_id: int
    ) -> schemas.IntegrationToken:
        token = self.session.get(models.IntegrationToken, token_id)
        if not token or token.project_id != project_id:
            raise KeyError("integration_token_not_found")
        return self._to_integration_token(token)

    def update_integration_token(
        self, project_id: int, token_id: int, payload: schemas.IntegrationTokenUpdate
    ) -> schemas.IntegrationToken:
        token = self.session.get(models.IntegrationToken, token_id)
        if not token or token.project_id != project_id:
            raise KeyError("integration_token_not_found")
        token.token_encrypted = encrypt_secret(payload.token)
        self.session.add(token)
        self.session.flush()
        return self._to_integration_token(token)

    def delete_integration_token(self, project_id: int, token_id: int) -> None:
        token = self.session.get(models.IntegrationToken, token_id)
        if not token or token.project_id != project_id:
            raise KeyError("integration_token_not_found")
        self.session.delete(token)

    def create_alert(self, project_id: int, payload: schemas.AlertCreate) -> schemas.Alert:
        project = self._require_project(project_id)
        alert = models.Alert(
            project=project,
            alert_type=payload.alert_type,
            severity=payload.severity,
            message=payload.message,
            metadata=payload.metadata,
        )
        self.session.add(alert)
        self.session.flush()
        return self._to_alert(alert)

    def list_alerts(self, project_id: int) -> List[schemas.Alert]:
        self._require_project(project_id)
        alerts = self.session.scalars(
            select(models.Alert).where(models.Alert.project_id == project_id)
        ).all()
        return [self._to_alert(alert) for alert in alerts]

    def _require_project(self, project_id: int) -> models.Project:
        project = self.session.get(models.Project, project_id)
        if not project:
            raise KeyError("project_not_found")
        return project

    @staticmethod
    def _to_project(project: models.Project) -> schemas.Project:
        return schemas.Project(
            id=project.id,
            name=project.name,
            description=project.description,
            status=project.status,
            created_at=project.created_at,
        )

    @staticmethod
    def _to_brand_config(config: models.BrandConfig) -> schemas.BrandConfig:
        return schemas.BrandConfig(
            id=config.id,
            project_id=config.project_id,
            version=config.version,
            is_active=config.is_active,
            tone=config.tone,
            audience=config.audience,
            offers=config.offers,
            rubrics=config.rubrics,
            forbidden=config.forbidden,
            cta_policy=config.cta_policy,
            is_stable=config.is_stable,
            created_at=config.created_at,
        )

    @staticmethod
    def _to_budget(budget: models.Budget) -> schemas.Budget:
        return schemas.Budget(
            id=budget.id,
            project_id=budget.project_id,
            daily=budget.daily,
            weekly=budget.weekly,
            monthly=budget.monthly,
            token_limit=budget.token_limit,
            video_seconds_limit=budget.video_seconds_limit,
            publication_limit=budget.publication_limit,
            created_at=budget.created_at,
        )

    @staticmethod
    def _to_budget_usage(usage: models.BudgetUsage) -> schemas.BudgetUsage:
        return schemas.BudgetUsage(
            id=usage.id,
            budget_id=usage.budget_id,
            project_id=usage.project_id,
            usage_date=usage.usage_date,
            token_used=usage.token_used,
            video_seconds_used=usage.video_seconds_used,
            publications_used=usage.publications_used,
            created_at=usage.created_at,
        )

    @staticmethod
    def _to_source(source: models.Source) -> schemas.Source:
        return schemas.Source(
            id=source.id,
            project_id=source.project_id,
            title=source.title,
            source_type=source.source_type,
            uri=source.uri,
            content=source.content,
            artifact_uri=source.artifact_uri,
            artifact_version=source.artifact_version,
            artifact_metadata=source.artifact_metadata,
            status=source.status,
            is_current=source.is_current,
            created_at=source.created_at,
        )

    @staticmethod
    def _to_atom(atom: models.Atom) -> schemas.Atom:
        return schemas.Atom(
            id=atom.id,
            project_id=atom.project_id,
            source_id=atom.source_id,
            kind=atom.kind,
            text=atom.text,
            source_backed=atom.source_backed,
            embedding=atom.embedding,
            source_uri=atom.source_uri,
            source_version=atom.source_version,
            artifact_uri=atom.artifact_uri,
            artifact_version=atom.artifact_version,
            artifact_metadata=atom.artifact_metadata,
            status=atom.status,
            is_current=atom.is_current,
            created_at=atom.created_at,
        )

    @staticmethod
    def _to_topic(topic: models.Topic) -> schemas.Topic:
        return schemas.Topic(
            id=topic.id,
            project_id=topic.project_id,
            title=topic.title,
            angle=topic.angle,
            rubric=topic.rubric,
            planned_for=topic.planned_for,
            status=topic.status,
            created_at=topic.created_at,
        )

    @staticmethod
    def _to_content_pack(pack: models.ContentPack) -> schemas.ContentPack:
        return schemas.ContentPack(
            id=pack.id,
            project_id=pack.project_id,
            topic_id=pack.topic_id,
            description=pack.description,
            status=pack.status,
            created_at=pack.created_at,
        )

    @staticmethod
    def _to_content_item(item: models.ContentItem) -> schemas.ContentItem:
        return schemas.ContentItem(
            id=item.id,
            project_id=item.project_id,
            pack_id=item.pack_id,
            channel=item.channel,
            format=item.format,
            body=item.body,
            metadata=item.metadata,
            status=item.status,
            created_at=item.created_at,
        )

    @staticmethod
    def _to_qc_report(report: models.QcReport) -> schemas.QcReport:
        return schemas.QcReport(
            id=report.id,
            project_id=report.project_id,
            content_item_id=report.content_item_id,
            score=report.score,
            passed=report.passed,
            reasons=report.reasons,
            created_at=report.created_at,
        )

    @staticmethod
    def _to_publication(publication: models.Publication) -> schemas.Publication:
        return schemas.Publication(
            id=publication.id,
            project_id=publication.project_id,
            content_item_id=publication.content_item_id,
            platform=publication.platform,
            scheduled_at=publication.scheduled_at,
            status=publication.status,
            platform_post_id=publication.platform_post_id,
            platform_post_url=publication.platform_post_url,
            published_at=publication.published_at,
            idempotency_key=publication.idempotency_key,
            attempt_count=publication.attempt_count,
            last_error=publication.last_error,
        )

    @staticmethod
    def _to_metric_snapshot(snapshot: models.MetricSnapshot) -> schemas.MetricSnapshot:
        return schemas.MetricSnapshot(
            id=snapshot.id,
            project_id=snapshot.project_id,
            content_item_id=snapshot.content_item_id,
            impressions=snapshot.impressions,
            clicks=snapshot.clicks,
            likes=snapshot.likes,
            comments=snapshot.comments,
            shares=snapshot.shares,
            collected_at=snapshot.collected_at,
        )

    @staticmethod
    def _to_redirect_link(link: models.RedirectLink) -> schemas.RedirectLink:
        return schemas.RedirectLink(
            id=link.id,
            project_id=link.project_id,
            content_item_id=link.content_item_id,
            target_url=link.target_url,
            slug=link.slug,
            utm_params=link.utm_params,
            is_active=link.is_active,
            created_at=link.created_at,
        )

    @staticmethod
    def _to_click_event(event: models.ClickEvent) -> schemas.ClickEvent:
        return schemas.ClickEvent(
            id=event.id,
            project_id=event.project_id,
            redirect_link_id=event.redirect_link_id,
            content_item_id=event.content_item_id,
            ip_address=event.ip_address,
            user_agent=event.user_agent,
            referrer=event.referrer,
            utm_params=event.utm_params,
            query_params=event.query_params,
            clicked_at=event.clicked_at,
        )

    @staticmethod
    def _to_learning_event(event: models.LearningEvent) -> schemas.LearningEvent:
        return schemas.LearningEvent(
            id=event.id,
            project_id=event.project_id,
            parameter=event.parameter,
            previous_value=event.previous_value,
            new_value=event.new_value,
            reason=event.reason,
            created_at=event.created_at,
        )

    @staticmethod
    def _to_auto_learning_config(
        config: models.AutoLearningConfig,
    ) -> schemas.AutoLearningConfig:
        return schemas.AutoLearningConfig(
            id=config.id,
            project_id=config.project_id,
            max_changes_per_week=config.max_changes_per_week,
            rollback_threshold=config.rollback_threshold,
            rollback_window=config.rollback_window,
            protected_parameters=config.protected_parameters,
            created_at=config.created_at,
        )

    @staticmethod
    def _to_auto_learning_state(
        state: models.AutoLearningState,
    ) -> schemas.AutoLearningState:
        return schemas.AutoLearningState(
            id=state.id,
            project_id=state.project_id,
            parameters=state.parameters,
            stable_parameters=state.stable_parameters,
            window_started_at=state.window_started_at,
            changes_in_window=state.changes_in_window,
            last_change_at=state.last_change_at,
            last_rollback_at=state.last_rollback_at,
            created_at=state.created_at,
        )

    @staticmethod
    def _to_prompt_version(prompt: models.PromptVersion) -> schemas.PromptVersion:
        return schemas.PromptVersion(
            id=prompt.id,
            project_id=prompt.project_id,
            prompt_key=prompt.prompt_key,
            content=prompt.content,
            version=prompt.version,
            is_active=prompt.is_active,
            is_stable=prompt.is_stable,
            created_at=prompt.created_at,
        )

    @staticmethod
    def _to_brand_config_history(
        entry: models.BrandConfigHistory,
    ) -> schemas.BrandConfigHistory:
        return schemas.BrandConfigHistory(
            id=entry.id,
            project_id=entry.project_id,
            brand_config_id=entry.brand_config_id,
            version=entry.version,
            change_summary=entry.change_summary,
            change_payload=entry.change_payload,
            created_at=entry.created_at,
        )

    @staticmethod
    def _to_prompt_version_history(
        entry: models.PromptVersionHistory,
    ) -> schemas.PromptVersionHistory:
        return schemas.PromptVersionHistory(
            id=entry.id,
            project_id=entry.project_id,
            prompt_version_id=entry.prompt_version_id,
            prompt_key=entry.prompt_key,
            version=entry.version,
            change_summary=entry.change_summary,
            change_payload=entry.change_payload,
            created_at=entry.created_at,
        )

    @staticmethod
    def _to_project_dataset(dataset: models.ProjectDataset) -> schemas.ProjectDataset:
        return schemas.ProjectDataset(
            id=dataset.id,
            project_id=dataset.project_id,
            name=dataset.name,
            kind=dataset.kind,
            storage_uri=dataset.storage_uri,
            is_active=dataset.is_active,
            created_at=dataset.created_at,
        )

    @staticmethod
    def _to_project_vector_index(
        index_: models.ProjectVectorIndex,
    ) -> schemas.ProjectVectorIndex:
        return schemas.ProjectVectorIndex(
            id=index_.id,
            project_id=index_.project_id,
            name=index_.name,
            provider=index_.provider,
            embedding_dimension=index_.embedding_dimension,
            metadata=index_.metadata,
            created_at=index_.created_at,
        )

    @staticmethod
    def _brand_config_snapshot(config: models.BrandConfig) -> dict:
        return {
            "id": config.id,
            "version": config.version,
            "is_active": config.is_active,
            "is_stable": config.is_stable,
            "tone": config.tone,
            "audience": config.audience,
            "offers": config.offers,
            "rubrics": config.rubrics,
            "forbidden": config.forbidden,
            "cta_policy": config.cta_policy,
        }

    @staticmethod
    def _prompt_snapshot(prompt: models.PromptVersion) -> dict:
        return {
            "id": prompt.id,
            "prompt_key": prompt.prompt_key,
            "version": prompt.version,
            "is_active": prompt.is_active,
            "is_stable": prompt.is_stable,
            "content": prompt.content,
        }

    def _record_brand_config_history(
        self,
        project_id: int,
        config: models.BrandConfig,
        previous: Optional[models.BrandConfig],
        change_summary: Optional[str],
    ) -> None:
        default_summary = "brand_config_created" if previous is None else "brand_config_updated"
        history = models.BrandConfigHistory(
            project_id=project_id,
            brand_config_id=config.id,
            version=config.version,
            change_summary=change_summary or default_summary,
            change_payload={
                "previous": self._brand_config_snapshot(previous)
                if previous
                else None,
                "current": self._brand_config_snapshot(config),
            },
        )
        self.session.add(history)

    def _record_prompt_history(
        self,
        project_id: int,
        prompt: models.PromptVersion,
        previous: Optional[models.PromptVersion],
        change_summary: Optional[str],
    ) -> None:
        default_summary = "prompt_version_created" if previous is None else "prompt_version_updated"
        history = models.PromptVersionHistory(
            project_id=project_id,
            prompt_version_id=prompt.id,
            prompt_key=prompt.prompt_key,
            version=prompt.version,
            change_summary=change_summary or default_summary,
            change_payload={
                "previous": self._prompt_snapshot(previous) if previous else None,
                "current": self._prompt_snapshot(prompt),
            },
        )
        self.session.add(history)

    @staticmethod
    def _to_role(role: models.Role) -> schemas.Role:
        return schemas.Role(
            id=role.id,
            name=role.name,
            created_at=role.created_at,
        )

    @staticmethod
    def to_user_schema(user: models.User) -> schemas.User:
        roles = sorted({user_role.role.name for user_role in user.user_roles})
        return schemas.User(
            id=user.id,
            email=user.email,
            roles=roles,
            is_active=user.is_active,
            created_at=user.created_at,
        )

    @staticmethod
    def _to_integration_token(token: models.IntegrationToken) -> schemas.IntegrationToken:
        return schemas.IntegrationToken(
            id=token.id,
            project_id=token.project_id,
            provider=token.provider,
            token=decrypt_secret(token.token_encrypted),
            created_at=token.created_at,
            updated_at=token.updated_at,
        )

    @staticmethod
    def _to_alert(alert: models.Alert) -> schemas.Alert:
        return schemas.Alert(
            id=alert.id,
            project_id=alert.project_id,
            alert_type=alert.alert_type,
            severity=alert.severity,
            message=alert.message,
            metadata=alert.metadata,
            created_at=alert.created_at,
        )
