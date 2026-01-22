from __future__ import annotations

from typing import Any, Optional

from .. import schemas
from ..observability import get_logger
from ..storage_db import DatabaseStore


class AlertService:
    def __init__(self, store: DatabaseStore) -> None:
        self.store = store
        self.logger = get_logger()

    def create_alert(
        self,
        project_id: int,
        alert_type: str,
        severity: str,
        message: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> schemas.Alert:
        alert = self.store.create_alert(
            project_id,
            schemas.AlertCreate(
                alert_type=alert_type,
                severity=severity,
                message=message,
                metadata=metadata or {},
            ),
        )
        self.logger.warning(
            "alert_created",
            extra={
                "event": "alert_created",
                "project_id": project_id,
                "alert_type": alert_type,
                "severity": severity,
            },
        )
        return alert
