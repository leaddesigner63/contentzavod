from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Protocol, Sequence

from .. import schemas
from ..storage_db import DatabaseStore


class TaskQueue(Protocol):
    def enqueue(self, task_name: str, payload: dict) -> str:
        ...


@dataclass(frozen=True)
class ProductionResult:
    content_items: List[schemas.ContentItem]


class ProducerService:
    """Сервис генерации контента: тексты, промпты изображений и видео."""

    def __init__(
        self, store: DatabaseStore, task_queue: Optional[TaskQueue] = None
    ) -> None:
        self.store = store
        self.task_queue = task_queue

    def enqueue_production(self, project_id: int, pack_id: int) -> Optional[str]:
        if not self.task_queue:
            return None
        return self.task_queue.enqueue(
            "produce_pack", {"project_id": project_id, "pack_id": pack_id}
        )

    def produce_pack(
        self,
        project_id: int,
        pack_id: int,
        topic_id: int,
        channels: Optional[Sequence[str]] = None,
    ) -> ProductionResult:
        channels = list(channels or ["telegram", "vk", "blog"])
        items: List[schemas.ContentItem] = []
        for channel in channels:
            fmt = "longread" if channel == "blog" else "post"
            metadata: Dict[str, str] = {
                "cta": "Подпишитесь и задайте вопрос",
                "hashtags": "#контент #маркетинг",
                "alt": "Описание изображения",
                "video_prompt": f"Видео по теме {topic_id}",
                "image_prompt": f"Обложка для темы {topic_id}",
            }
            item = self.store.create_content_item(
                project_id,
                schemas.ContentItemCreate(
                    pack_id=pack_id,
                    channel=channel,
                    format=fmt,
                    body=f"Черновик {fmt} для {channel} (тема {topic_id})",
                    metadata=metadata,
                ),
            )
            items.append(item)
        return ProductionResult(content_items=items)
