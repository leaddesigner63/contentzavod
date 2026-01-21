from __future__ import annotations

from datetime import datetime
from typing import List

from .. import schemas
from ..storage import InMemoryStore


class PipelineService:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def run(self, project_id: int, topic_id: int) -> dict:
        """Запускает упрощённый пайплайн и возвращает созданные сущности."""
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
                    metadata={"generated_at": datetime.utcnow().isoformat()},
                ),
            )
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
        return {"pack": pack, "items": items}
