from __future__ import annotations

import json
import logging
import os
import threading
from typing import Any, Callable, ContextManager, Optional
from urllib import parse, request

from .. import schemas
from ..observability import get_logger, increment_metric, log_event, set_metric_gauge
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
        increment_metric(
            "alerts_created_total",
            tags={"alert_type": alert_type, "severity": severity},
        )
        log_event(
            self.logger,
            "alert_created",
            level=logging.WARNING,
            project_id=project_id,
            alert_type=alert_type,
            severity=severity,
            message=message,
            metadata=metadata or {},
        )
        return alert


class IntegrationHealthService:
    def __init__(
        self,
        store: DatabaseStore,
        timeout: int = 5,
        sora_base_url: Optional[str] = None,
    ) -> None:
        self.store = store
        self.timeout = timeout
        self.sora_base_url = (
            (sora_base_url or os.getenv("SORA_BASE_URL", "http://localhost:9001"))
            .rstrip("/")
        )
        self.logger = get_logger()
        self.alerts = AlertService(store)

    def check_project(self, project_id: int) -> None:
        self._check_telegram(project_id)
        self._check_vk(project_id)
        self._check_sora(project_id)

    def _check_telegram(self, project_id: int) -> None:
        token = self._find_token(project_id, ("telegram_bot", "telegram"))
        if not token:
            self._handle_unavailable(project_id, "telegram", "token_missing")
            return
        url = f"https://api.telegram.org/bot{token.token}/getMe"
        payload = self._fetch_json(url)
        ok = bool(payload and payload.get("ok"))
        self._record_result(project_id, "telegram", ok, payload)

    def _check_vk(self, project_id: int) -> None:
        token = self._find_token(project_id, ("vk_api", "vk"))
        if not token:
            self._handle_unavailable(project_id, "vk", "token_missing")
            return
        params = {
            "access_token": token.token,
            "v": "5.131",
        }
        url = "https://api.vk.com/method/users.get?" + parse.urlencode(params)
        payload = self._fetch_json(url)
        ok = bool(payload and payload.get("response"))
        self._record_result(project_id, "vk", ok, payload)

    def _check_sora(self, project_id: int) -> None:
        url = f"{self.sora_base_url}/health"
        ok, detail = self._fetch_status(url)
        self._record_result(project_id, "sora", ok, detail)

    def _find_token(
        self, project_id: int, providers: tuple[str, ...]
    ) -> Optional[schemas.IntegrationToken]:
        tokens = self.store.list_integration_tokens(project_id)
        for provider in providers:
            for token in tokens:
                if token.provider == provider:
                    return token
        return None

    def _fetch_json(self, url: str) -> Optional[dict[str, Any]]:
        try:
            with request.urlopen(url, timeout=self.timeout) as response:
                data = response.read().decode("utf-8")
            return json.loads(data)
        except Exception as exc:
            return {"error": str(exc)}

    def _fetch_status(self, url: str) -> tuple[bool, dict[str, Any]]:
        try:
            with request.urlopen(url, timeout=self.timeout) as response:
                status = response.status
            return status == 200, {"status": status}
        except Exception as exc:
            return False, {"error": str(exc)}

    def _record_result(
        self,
        project_id: int,
        provider: str,
        ok: bool,
        payload: Optional[dict[str, Any]],
    ) -> None:
        set_metric_gauge(
            "integration_health_status",
            1.0 if ok else 0.0,
            tags={"project_id": str(project_id), "provider": provider},
        )
        log_event(
            self.logger,
            "integration_health_check",
            level=logging.INFO if ok else logging.WARNING,
            project_id=project_id,
            provider=provider,
            status="ok" if ok else "failed",
            payload=payload or {},
        )
        if not ok:
            self._handle_unavailable(project_id, provider, "check_failed", payload)

    def _handle_unavailable(
        self,
        project_id: int,
        provider: str,
        reason: str,
        payload: Optional[dict[str, Any]] = None,
    ) -> None:
        self.alerts.create_alert(
            project_id,
            alert_type="integration_unavailable",
            severity="warning",
            message=f"{provider}:{reason}",
            metadata={
                "provider": provider,
                "reason": reason,
                "payload": payload or {},
            },
        )


StoreFactory = Callable[[], ContextManager[DatabaseStore]]


class IntegrationMonitor:
    def __init__(
        self,
        store_factory: StoreFactory,
        interval_seconds: int = 300,
        timeout: int = 5,
        sora_base_url: Optional[str] = None,
    ) -> None:
        self.store_factory = store_factory
        self.interval_seconds = interval_seconds
        self.timeout = timeout
        self.sora_base_url = sora_base_url
        self.logger = get_logger()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()
        log_event(
            self.logger,
            "integration_monitor_started",
            level=logging.INFO,
            interval_seconds=self.interval_seconds,
        )

    def stop(self) -> None:
        self._stop_event.set()
        log_event(self.logger, "integration_monitor_stopped", level=logging.INFO)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                with self.store_factory() as store:
                    checker = IntegrationHealthService(
                        store,
                        timeout=self.timeout,
                        sora_base_url=self.sora_base_url,
                    )
                    for project in store.list_projects():
                        checker.check_project(project.id)
            except Exception as exc:
                log_event(
                    self.logger,
                    "integration_monitor_failed",
                    level=logging.ERROR,
                    error=str(exc),
                )
            self._stop_event.wait(self.interval_seconds)
