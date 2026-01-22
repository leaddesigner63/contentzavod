from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import List, Optional, Protocol, Sequence

from .. import schemas
from ..storage_db import DatabaseStore


class TaskQueue(Protocol):
    def enqueue(self, task_name: str, payload: dict) -> str:
        ...


@dataclass(frozen=True)
class PlanResult:
    topics: List[schemas.Topic]
    content_packs: List[schemas.ContentPack]


class PlannerService:
    """Сервис планирования тем, рубрик и расписания."""

    def __init__(
        self, store: DatabaseStore, task_queue: Optional[TaskQueue] = None
    ) -> None:
        self.store = store
        self.task_queue = task_queue

    def enqueue_planning(self, project_id: int, days: int) -> Optional[str]:
        if not self.task_queue:
            return None
        return self.task_queue.enqueue(
            "plan_period", {"project_id": project_id, "days": days}
        )

    def plan_period(
        self,
        project_id: int,
        start_date: Optional[date] = None,
        days: int = 14,
        rubrics: Optional[Sequence[str]] = None,
    ) -> PlanResult:
        """Генерирует темы и контент-пакеты на период."""
        start_date = start_date or datetime.utcnow().date()
        rubrics = list(rubrics or ["tips", "case", "promo"])
        topics: List[schemas.Topic] = []
        packs: List[schemas.ContentPack] = []
        for offset in range(days):
            planned_for = datetime.combine(start_date + timedelta(days=offset), datetime.min.time())
            rubric = rubrics[offset % len(rubrics)]
            topic = self.store.create_topic(
                project_id,
                schemas.TopicCreate(
                    title=f"Тема {offset + 1}",
                    angle="основной",
                    rubric=rubric,
                    planned_for=planned_for,
                ),
            )
            pack = self.store.create_content_pack(
                project_id,
                schemas.ContentPackCreate(
                    topic_id=topic.id,
                    description=f"Контент-пакет для {topic.title}",
                ),
            )
            topics.append(topic)
            packs.append(pack)
        return PlanResult(topics=topics, content_packs=packs)
