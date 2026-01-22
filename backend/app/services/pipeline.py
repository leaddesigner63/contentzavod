from __future__ import annotations

from datetime import datetime
from typing import List

from .. import schemas
from ..observability import get_logger
from ..storage_db import DatabaseStore
from .budgets import BudgetLimitExceeded, BudgetService
from .learning import AutoLearningService
from .video_workshop import StyleAnchors, VideoWorkshopService


class PipelineService:
    def __init__(
        self, store: DatabaseStore, video_workshop: VideoWorkshopService | None = None
    ) -> None:
        self.store = store
        self.logger = get_logger()
        self.budgets = BudgetService(store)
        self.video_workshop = video_workshop

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        return max(1, len(text.split()))

    def run(self, project_id: int, topic_id: int) -> dict:
        """Запускает упрощённый пайплайн и возвращает созданные сущности."""
        topic = self.store.get_topic(project_id, topic_id)
        learning_service = AutoLearningService(self.store)
        learning_params = learning_service.select_parameters(project_id)
        pack = self.store.create_content_pack(
            project_id,
            schemas.ContentPackCreate(topic_id=topic_id, description="auto"),
        )
        items: List[schemas.ContentItem] = []
        for channel, fmt in (
            ("telegram", "post"),
            ("vk", "post"),
            ("blog", "longread"),
        ):
            item = self.store.create_content_item(
                project_id,
                schemas.ContentItemCreate(
                    pack_id=pack.id,
                    channel=channel,
                    format=fmt,
                    body=f"Черновик {fmt} для {channel} из темы {topic_id}",
                    metadata={
                        "generated_at": datetime.utcnow().isoformat(),
                        "slot": learning_params.get("slot", "default"),
                        "cta": learning_params.get("cta", "standard"),
                        "angle": topic.angle,
                    },
                ),
            )
            tokens_estimate = self._estimate_tokens(item.body)
            try:
                self.budgets.record_usage(
                    project_id,
                    token_used=tokens_estimate,
                )
            except BudgetLimitExceeded:
                self.logger.warning(
                    "pipeline_budget_blocked",
                    extra={
                        "event": "pipeline_budget_blocked",
                        "project_id": project_id,
                        "content_item_id": item.id,
                        "channel": channel,
                        "format": fmt,
                    },
                )
                raise
            items.append(item)
            self.store.create_qc_report(
                project_id,
                schemas.QcReportCreate(
                    content_item_id=item.id,
                    score=0.8,
                    passed=True,
                    reasons=["auto-qc-pass"],
                ),
            )
        video_item = self.store.create_content_item(
            project_id,
            schemas.ContentItemCreate(
                pack_id=pack.id,
                channel="video",
                format="video",
                body=f"Черновик видео для темы {topic_id}",
                metadata={
                    "generated_at": datetime.utcnow().isoformat(),
                    "slot": learning_params.get("slot", "default"),
                    "cta": learning_params.get("cta", "standard"),
                    "angle": topic.angle,
                    "topic_title": topic.title,
                    "topic_angle": topic.angle,
                    "video_status": "queued",
                },
            ),
        )
        self.store.update_content_item_status(project_id, video_item.id, "queued")
        items.append(video_item)
        if self.video_workshop:
            style_anchors = StyleAnchors(
                camera="cinematic",
                movement="smooth",
                angle="wide",
                lighting="soft",
                palette="warm",
                location="studio",
                characters=(),
            )
            self.video_workshop.run_workshop(
                project_id,
                video_item.id,
                topic.title,
                topic.angle,
                style_anchors,
            )
        return {"pack": pack, "items": items}
