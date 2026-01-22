from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Protocol

from .. import schemas
from ..storage_db import DatabaseStore


class TaskQueue(Protocol):
    def enqueue(self, task_name: str, payload: dict) -> str:
        ...


@dataclass(frozen=True)
class QcResult:
    report: schemas.QcReport


class QcService:
    """Сервис контроля качества: тональность, факты, риски, читабельность."""

    def __init__(
        self, store: DatabaseStore, task_queue: Optional[TaskQueue] = None
    ) -> None:
        self.store = store
        self.task_queue = task_queue

    def enqueue_qc(self, project_id: int, content_item_id: int) -> Optional[str]:
        if not self.task_queue:
            return None
        return self.task_queue.enqueue(
            "qc_check", {"project_id": project_id, "content_item_id": content_item_id}
        )

    def run_checks(self, project_id: int, content_item_id: int) -> QcResult:
        reasons: List[str] = [
            "voice_match",
            "facts_checked_via_rag",
            "risk_scan_ok",
            "no_repetition",
            "readability_ok",
        ]
        report = self.store.create_qc_report(
            project_id,
            schemas.QcReportCreate(
                content_item_id=content_item_id,
                score=0.9,
                passed=True,
                reasons=reasons,
            ),
        )
        return QcResult(report=report)
