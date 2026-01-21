from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List

from . import schemas


@dataclass
class ProjectStore:
    project: schemas.Project
    brand_configs: List[schemas.BrandConfig] = field(default_factory=list)
    budgets: List[schemas.Budget] = field(default_factory=list)
    sources: List[schemas.Source] = field(default_factory=list)
    atoms: List[schemas.Atom] = field(default_factory=list)
    topics: List[schemas.Topic] = field(default_factory=list)
    content_packs: List[schemas.ContentPack] = field(default_factory=list)
    content_items: List[schemas.ContentItem] = field(default_factory=list)
    qc_reports: List[schemas.QcReport] = field(default_factory=list)
    publications: List[schemas.Publication] = field(default_factory=list)
    metrics: List[schemas.MetricSnapshot] = field(default_factory=list)
    learning_events: List[schemas.LearningEvent] = field(default_factory=list)


class InMemoryStore:
    def __init__(self) -> None:
        self._projects: Dict[int, ProjectStore] = {}
        self._counters: Dict[str, int] = {}

    def _next_id(self, key: str) -> int:
        current = self._counters.get(key, 0) + 1
        self._counters[key] = current
        return current

    def list_projects(self) -> List[schemas.Project]:
        return [store.project for store in self._projects.values()]

    def create_project(self, payload: schemas.ProjectCreate) -> schemas.Project:
        project_id = self._next_id("project")
        project = schemas.Project(
            id=project_id,
            name=payload.name,
            description=payload.description,
            status="active",
            created_at=datetime.utcnow(),
        )
        self._projects[project_id] = ProjectStore(project=project)
        return project

    def get_project_store(self, project_id: int) -> ProjectStore:
        if project_id not in self._projects:
            raise KeyError("project_not_found")
        return self._projects[project_id]

    def create_brand_config(
        self, project_id: int, payload: schemas.BrandConfigCreate
    ) -> schemas.BrandConfig:
        store = self.get_project_store(project_id)
        config = schemas.BrandConfig(
            id=self._next_id("brand_config"),
            project_id=project_id,
            version=len(store.brand_configs) + 1,
            created_at=datetime.utcnow(),
            **payload.model_dump(),
        )
        store.brand_configs.append(config)
        return config

    def create_budget(self, project_id: int, payload: schemas.BudgetCreate) -> schemas.Budget:
        store = self.get_project_store(project_id)
        budget = schemas.Budget(
            id=self._next_id("budget"),
            project_id=project_id,
            created_at=datetime.utcnow(),
            **payload.model_dump(),
        )
        store.budgets.append(budget)
        return budget

    def create_source(self, project_id: int, payload: schemas.SourceCreate) -> schemas.Source:
        store = self.get_project_store(project_id)
        source = schemas.Source(
            id=self._next_id("source"),
            project_id=project_id,
            created_at=datetime.utcnow(),
            **payload.model_dump(),
        )
        store.sources.append(source)
        return source

    def create_atom(
        self,
        project_id: int,
        source_id: int,
        kind: str,
        text: str,
        source_backed: bool,
    ) -> schemas.Atom:
        store = self.get_project_store(project_id)
        atom = schemas.Atom(
            id=self._next_id("atom"),
            project_id=project_id,
            source_id=source_id,
            kind=kind,
            text=text,
            source_backed=source_backed,
            created_at=datetime.utcnow(),
        )
        store.atoms.append(atom)
        return atom

    def create_topic(self, project_id: int, payload: schemas.TopicCreate) -> schemas.Topic:
        store = self.get_project_store(project_id)
        topic = schemas.Topic(
            id=self._next_id("topic"),
            project_id=project_id,
            created_at=datetime.utcnow(),
            **payload.model_dump(),
        )
        store.topics.append(topic)
        return topic

    def create_content_pack(
        self, project_id: int, payload: schemas.ContentPackCreate
    ) -> schemas.ContentPack:
        store = self.get_project_store(project_id)
        pack = schemas.ContentPack(
            id=self._next_id("content_pack"),
            project_id=project_id,
            created_at=datetime.utcnow(),
            **payload.model_dump(),
        )
        store.content_packs.append(pack)
        return pack

    def create_content_item(
        self, project_id: int, payload: schemas.ContentItemCreate
    ) -> schemas.ContentItem:
        store = self.get_project_store(project_id)
        item = schemas.ContentItem(
            id=self._next_id("content_item"),
            project_id=project_id,
            created_at=datetime.utcnow(),
            **payload.model_dump(),
        )
        store.content_items.append(item)
        return item

    def create_qc_report(
        self, project_id: int, payload: schemas.QcReportCreate
    ) -> schemas.QcReport:
        store = self.get_project_store(project_id)
        report = schemas.QcReport(
            id=self._next_id("qc_report"),
            project_id=project_id,
            created_at=datetime.utcnow(),
            **payload.model_dump(),
        )
        store.qc_reports.append(report)
        return report

    def create_publication(
        self, project_id: int, payload: schemas.PublicationCreate
    ) -> schemas.Publication:
        store = self.get_project_store(project_id)
        publication = schemas.Publication(
            id=self._next_id("publication"),
            project_id=project_id,
            **payload.model_dump(),
        )
        store.publications.append(publication)
        return publication

    def create_metric_snapshot(
        self, project_id: int, payload: schemas.MetricSnapshotCreate
    ) -> schemas.MetricSnapshot:
        store = self.get_project_store(project_id)
        snapshot = schemas.MetricSnapshot(
            id=self._next_id("metric_snapshot"),
            project_id=project_id,
            collected_at=datetime.utcnow(),
            **payload.model_dump(),
        )
        store.metrics.append(snapshot)
        return snapshot

    def create_learning_event(
        self, project_id: int, payload: schemas.LearningEventCreate
    ) -> schemas.LearningEvent:
        store = self.get_project_store(project_id)
        event = schemas.LearningEvent(
            id=self._next_id("learning_event"),
            project_id=project_id,
            created_at=datetime.utcnow(),
            **payload.model_dump(),
        )
        store.learning_events.append(event)
        return event
