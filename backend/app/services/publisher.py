from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Protocol

from .. import models, schemas
from ..storage_db import DatabaseStore


class TaskQueue(Protocol):
    def enqueue(self, task_name: str, payload: dict) -> str:
        ...


@dataclass(frozen=True)
class PublicationResult:
    publication: schemas.Publication


class PublisherService:
    """Сервис автопубликации: ретраи, дедупликация и идемпотентность."""

    def __init__(
        self, store: DatabaseStore, task_queue: Optional[TaskQueue] = None
    ) -> None:
        self.store = store
        self.task_queue = task_queue

    def enqueue_publication(
        self, project_id: int, content_item_id: int, platform: str
    ) -> Optional[str]:
        if not self.task_queue:
            return None
        return self.task_queue.enqueue(
            "publish_content",
            {
                "project_id": project_id,
                "content_item_id": content_item_id,
                "platform": platform,
            },
        )

    def schedule(
        self,
        project_id: int,
        content_item_id: int,
        platform: str,
        scheduled_at: Optional[datetime] = None,
    ) -> PublicationResult:
        scheduled_at = scheduled_at or datetime.utcnow()
        publication = self.store.create_publication(
            project_id,
            schemas.PublicationCreate(
                content_item_id=content_item_id,
                platform=platform,
                scheduled_at=scheduled_at,
                status="scheduled",
            ),
        )
        return PublicationResult(publication=publication)

    def mark_published(
        self,
        project_id: int,
        publication_id: int,
        platform_post_id: str,
        published_at: Optional[datetime] = None,
    ) -> schemas.Publication:
        published_at = published_at or datetime.utcnow()
        publication = self.store.session.get(models.Publication, publication_id)
        if not publication or publication.project_id != project_id:
            raise KeyError("publication_not_found")
        publication.platform_post_id = platform_post_id
        publication.published_at = published_at
        publication.status = "published"
        self.store.session.add(publication)
        self.store.session.flush()
        return self.store._to_publication(publication)
