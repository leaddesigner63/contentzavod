from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models, schemas


class DatabaseStore:
    def __init__(self, session: Session) -> None:
        self.session = session

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
        return self._to_project(project)

    def create_brand_config(
        self, project_id: int, payload: schemas.BrandConfigCreate
    ) -> schemas.BrandConfig:
        project = self._require_project(project_id)
        version = (
            self.session.scalar(
                select(models.BrandConfig)
                .where(models.BrandConfig.project_id == project_id)
                .order_by(models.BrandConfig.version.desc())
            )
            or None
        )
        next_version = version.version + 1 if version else 1
        config = models.BrandConfig(
            project=project,
            version=next_version,
            tone=payload.tone,
            audience=payload.audience,
            offers=payload.offers,
            rubrics=payload.rubrics,
            forbidden=payload.forbidden,
            cta_policy=payload.cta_policy,
        )
        self.session.add(config)
        self.session.flush()
        return self._to_brand_config(config)

    def list_brand_configs(self, project_id: int) -> List[schemas.BrandConfig]:
        self._require_project(project_id)
        configs = self.session.scalars(
            select(models.BrandConfig).where(models.BrandConfig.project_id == project_id)
        ).all()
        return [self._to_brand_config(config) for config in configs]

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

    def create_source(self, project_id: int, payload: schemas.SourceCreate) -> schemas.Source:
        project = self._require_project(project_id)
        source = models.Source(
            project=project,
            title=payload.title,
            source_type=payload.source_type,
            uri=payload.uri,
            content=payload.content,
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
        prompt = models.PromptVersion(
            project=project,
            prompt_key=payload.prompt_key,
            content=payload.content,
            version=next_version,
            is_active=payload.is_active,
        )
        self.session.add(prompt)
        self.session.flush()
        return self._to_prompt_version(prompt)

    def list_prompt_versions(self, project_id: int) -> List[schemas.PromptVersion]:
        self._require_project(project_id)
        prompts = self.session.scalars(
            select(models.PromptVersion).where(
                models.PromptVersion.project_id == project_id
            )
        ).all()
        return [self._to_prompt_version(prompt) for prompt in prompts]

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
            tone=config.tone,
            audience=config.audience,
            offers=config.offers,
            rubrics=config.rubrics,
            forbidden=config.forbidden,
            cta_policy=config.cta_policy,
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
            published_at=publication.published_at,
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
    def _to_prompt_version(prompt: models.PromptVersion) -> schemas.PromptVersion:
        return schemas.PromptVersion(
            id=prompt.id,
            project_id=prompt.project_id,
            prompt_key=prompt.prompt_key,
            content=prompt.content,
            version=prompt.version,
            is_active=prompt.is_active,
            created_at=prompt.created_at,
        )
