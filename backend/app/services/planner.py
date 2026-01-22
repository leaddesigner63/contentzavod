from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Dict, Iterable, List, Optional, Protocol, Sequence, Tuple

from sqlalchemy import select

from .. import models, schemas
from ..storage_db import DatabaseStore


class TaskQueue(Protocol):
    def enqueue(self, task_name: str, payload: dict) -> str:
        ...


@dataclass(frozen=True)
class PlanResult:
    topics: List[schemas.Topic]
    content_packs: List[schemas.ContentPack]
    content_items: List[schemas.ContentItem]
    publications: List[schemas.Publication]


class PlannerService:
    """Сервис планирования тем, рубрик и расписания."""

    default_rubrics = ("tips", "case", "promo")
    default_channels = ("telegram", "vk")
    default_slots = {
        "telegram": ("09:00", "13:00", "18:00"),
        "vk": ("10:00", "14:00", "19:00"),
    }

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
        rubric_weights: Optional[Dict[str, float]] = None,
        channels: Optional[Sequence[str]] = None,
        channel_slots: Optional[Dict[str, Sequence[str]]] = None,
        channel_frequency: Optional[Dict[str, int]] = None,
    ) -> PlanResult:
        """Генерирует темы, контент-пакеты и расписание публикаций на период."""
        start_date = start_date or datetime.utcnow().date()
        rubrics = list(rubrics or [])
        channels = list(channels or self.default_channels)
        rubric_weights = rubric_weights or {}
        channel_slots = channel_slots or {}
        channel_frequency = channel_frequency or {}
        brand_config = self._get_active_brand_config(project_id)
        if not rubrics:
            rubrics = list(brand_config.rubrics if brand_config else self.default_rubrics)
        if not rubrics:
            rubrics = list(self.default_rubrics)
        metric_context = self._collect_metric_context(project_id)
        metric_rubric_weights = self._weights_from_scores(metric_context["rubrics"])
        weights = self._merge_weights(rubrics, rubric_weights, metric_rubric_weights)
        rubric_sequence = self._build_weighted_sequence(
            rubrics, weights, self._total_publications(days, channels, channel_slots, channel_frequency)
        )
        best_angle = self._best_variant(metric_context["angles"]) or "основной"
        offers = list(brand_config.offers) if brand_config else []
        audience = brand_config.audience if brand_config else "аудитория"
        topics: List[schemas.Topic] = []
        packs: List[schemas.ContentPack] = []
        items: List[schemas.ContentItem] = []
        publications: List[schemas.Publication] = []
        schedule = self._build_schedule(
            start_date,
            days,
            channels,
            channel_slots,
            channel_frequency,
            metric_context["slots"],
        )
        for index, entry in enumerate(schedule):
            rubric = rubric_sequence[index % len(rubric_sequence)]
            offer = offers[index % len(offers)] if offers else None
            title = self._build_topic_title(index, rubric, audience, offer)
            topic = self.store.create_topic(
                project_id,
                schemas.TopicCreate(
                    title=title,
                    angle=best_angle,
                    rubric=rubric,
                    planned_for=entry.scheduled_at,
                ),
            )
            pack = self.store.create_content_pack(
                project_id,
                schemas.ContentPackCreate(
                    topic_id=topic.id,
                    description=f"Контент-пакет для {topic.title}",
                ),
            )
            item = self.store.create_content_item(
                project_id,
                schemas.ContentItemCreate(
                    pack_id=pack.id,
                    channel=entry.channel,
                    format="post",
                    body=f"Запланированный пост для {entry.channel} по теме {topic.title}",
                    metadata={
                        "slot": entry.slot,
                        "rubric": rubric,
                        "angle": best_angle,
                        "planned_for": entry.scheduled_at.isoformat(),
                    },
                ),
            )
            publication = self.store.create_publication(
                project_id,
                schemas.PublicationCreate(
                    content_item_id=item.id,
                    platform=entry.channel,
                    scheduled_at=entry.scheduled_at,
                    status="scheduled",
                ),
            )
            topics.append(topic)
            packs.append(pack)
            items.append(item)
            publications.append(publication)
        return PlanResult(
            topics=topics,
            content_packs=packs,
            content_items=items,
            publications=publications,
        )

    def _get_active_brand_config(self, project_id: int) -> Optional[schemas.BrandConfig]:
        configs = self.store.list_brand_configs(project_id)
        for config in configs:
            if config.is_active:
                return config
        return configs[-1] if configs else None

    @staticmethod
    def _ctr(impressions: int, clicks: int) -> Optional[float]:
        if impressions <= 0:
            return None
        return clicks / impressions

    def _collect_metric_context(self, project_id: int) -> dict[str, Dict[str, float]]:
        rubric_scores: dict[str, list[float]] = {}
        slot_scores: dict[Tuple[str, str], list[float]] = {}
        angle_scores: dict[str, list[float]] = {}
        rows = self.store.session.execute(
            select(models.MetricSnapshot, models.ContentItem, models.Topic)
            .join(
                models.ContentItem,
                models.ContentItem.id == models.MetricSnapshot.content_item_id,
            )
            .join(
                models.ContentPack,
                models.ContentPack.id == models.ContentItem.pack_id,
            )
            .join(models.Topic, models.Topic.id == models.ContentPack.topic_id)
            .where(models.MetricSnapshot.project_id == project_id)
        ).all()
        for snapshot, item, topic in rows:
            ctr = self._ctr(snapshot.impressions, snapshot.clicks)
            if ctr is None:
                continue
            rubric = topic.rubric or "general"
            rubric_scores.setdefault(rubric, []).append(ctr)
            angle = item.metadata.get("angle") or topic.angle
            if angle:
                angle_scores.setdefault(str(angle), []).append(ctr)
            slot = item.metadata.get("slot")
            if slot:
                slot_scores.setdefault((item.channel, str(slot)), []).append(ctr)
        return {
            "rubrics": self._average_scores(rubric_scores),
            "slots": self._average_scores(slot_scores),
            "angles": self._average_scores(angle_scores),
        }

    @staticmethod
    def _average_scores(scores: Dict[object, List[float]]) -> Dict[object, float]:
        averages: dict[object, float] = {}
        for key, values in scores.items():
            if values:
                averages[key] = sum(values) / len(values)
        return averages

    @staticmethod
    def _weights_from_scores(scores: Dict[object, float]) -> Dict[str, int]:
        if not scores:
            return {}
        max_score = max(scores.values())
        weights: dict[str, int] = {}
        for key, value in scores.items():
            if max_score <= 0:
                weights[str(key)] = 1
            else:
                scaled = 1 + round((value / max_score) * 2)
                weights[str(key)] = max(1, int(scaled))
        return weights

    @staticmethod
    def _merge_weights(
        rubrics: Iterable[str],
        explicit_weights: Dict[str, float],
        metric_weights: Dict[str, int],
    ) -> Dict[str, int]:
        merged: dict[str, int] = {}
        for rubric in rubrics:
            if rubric in explicit_weights:
                weight = explicit_weights[rubric]
            else:
                weight = metric_weights.get(rubric, 1)
            merged[rubric] = max(1, int(round(weight)))
        return merged

    @staticmethod
    def _build_weighted_sequence(
        rubrics: List[str],
        weights: Dict[str, int],
        total: int,
    ) -> List[str]:
        if total <= 0:
            return []
        pool: list[str] = []
        for rubric in rubrics:
            pool.extend([rubric] * max(1, weights.get(rubric, 1)))
        if not pool:
            pool = list(rubrics)
        return [pool[index % len(pool)] for index in range(total)]

    @staticmethod
    def _best_variant(scores: Dict[object, float]) -> Optional[str]:
        if not scores:
            return None
        best_key = max(scores.items(), key=lambda item: item[1])[0]
        return str(best_key)

    def _total_publications(
        self,
        days: int,
        channels: Sequence[str],
        channel_slots: Dict[str, Sequence[str]],
        channel_frequency: Dict[str, int],
    ) -> int:
        total = 0
        for channel in channels:
            slots = list(channel_slots.get(channel, self.default_slots.get(channel, ())))
            if not slots:
                slots = list(self.default_slots.get(channel, ()))
            frequency = channel_frequency.get(channel, len(slots))
            total += max(0, frequency) * days
        return total

    def _build_schedule(
        self,
        start_date: date,
        days: int,
        channels: Sequence[str],
        channel_slots: Dict[str, Sequence[str]],
        channel_frequency: Dict[str, int],
        slot_scores: Dict[Tuple[str, str], float],
    ) -> List["_ScheduleEntry"]:
        schedule: list[_ScheduleEntry] = []
        for offset in range(days):
            current_date = start_date + timedelta(days=offset)
            for channel in channels:
                slots = list(channel_slots.get(channel, self.default_slots.get(channel, ())))
                if not slots:
                    slots = list(self.default_slots.get(channel, ()))
                slots = self._order_slots(channel, slots, slot_scores)
                frequency = channel_frequency.get(channel, len(slots))
                for slot in slots[: max(0, frequency)]:
                    slot_time = self._parse_slot(slot)
                    scheduled_at = datetime.combine(current_date, slot_time)
                    schedule.append(
                        _ScheduleEntry(
                            channel=channel,
                            slot=slot,
                            scheduled_at=scheduled_at,
                        )
                    )
        return schedule

    @staticmethod
    def _order_slots(
        channel: str,
        slots: Sequence[str],
        slot_scores: Dict[Tuple[str, str], float],
    ) -> List[str]:
        if not slot_scores:
            return list(slots)
        return sorted(
            slots,
            key=lambda slot: slot_scores.get((channel, slot), 0.0),
            reverse=True,
        )

    @staticmethod
    def _parse_slot(slot: str) -> time:
        try:
            return datetime.strptime(slot, "%H:%M").time()
        except ValueError as exc:
            raise ValueError(f"invalid_slot_format:{slot}") from exc

    @staticmethod
    def _build_topic_title(
        index: int, rubric: str, audience: str, offer: Optional[str]
    ) -> str:
        parts = []
        if rubric:
            parts.append(rubric.capitalize())
        if offer:
            parts.append(offer)
        if audience:
            parts.append(f"для {audience}")
        return " — ".join(parts) or f"Тема {index + 1}"


@dataclass(frozen=True)
class _ScheduleEntry:
    channel: str
    slot: str
    scheduled_at: datetime
