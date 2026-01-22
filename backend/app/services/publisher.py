from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Protocol
from urllib import parse, request

from sqlalchemy import select

from .. import models, schemas
from ..observability import get_logger
from ..storage_db import DatabaseStore
from .alerts import AlertService
from .budgets import BudgetLimitExceeded, BudgetService


class TaskQueue(Protocol):
    def enqueue(
        self,
        task_name: str,
        payload: dict,
        run_at: Optional[datetime] = None,
        idempotency_key: Optional[str] = None,
    ) -> str:
        ...


@dataclass(frozen=True)
class PublicationResult:
    publication: schemas.Publication
    task_id: Optional[str] = None


@dataclass
class TaskEntry:
    task_id: str
    task_name: str
    payload: dict
    run_at: datetime
    idempotency_key: Optional[str] = None
    attempts: int = 0


class InMemoryTaskQueue:
    def __init__(self) -> None:
        self._tasks: list[TaskEntry] = []
        self._idempotency_index: set[str] = set()
        self._counter = 0

    def enqueue(
        self,
        task_name: str,
        payload: dict,
        run_at: Optional[datetime] = None,
        idempotency_key: Optional[str] = None,
    ) -> str:
        if idempotency_key and idempotency_key in self._idempotency_index:
            return idempotency_key
        self._counter += 1
        task_id = idempotency_key or f"task-{self._counter}"
        run_at = run_at or datetime.utcnow()
        entry = TaskEntry(
            task_id=task_id,
            task_name=task_name,
            payload=payload,
            run_at=run_at,
            idempotency_key=idempotency_key,
        )
        self._tasks.append(entry)
        if idempotency_key:
            self._idempotency_index.add(idempotency_key)
        return task_id

    def pop_due(self, now: Optional[datetime] = None) -> list[TaskEntry]:
        now = now or datetime.utcnow()
        due = [task for task in self._tasks if task.run_at <= now]
        self._tasks = [task for task in self._tasks if task.run_at > now]
        return due

    def mark_done(self, task_id: str) -> None:
        self._idempotency_index.discard(task_id)


class PublicationScheduler:
    """Простейший cron/beat для постановки публикаций в очередь."""

    def __init__(self, store: DatabaseStore, task_queue: TaskQueue) -> None:
        self.store = store
        self.task_queue = task_queue

    def tick(self, project_id: int, now: Optional[datetime] = None) -> int:
        now = now or datetime.utcnow()
        due = self.store.list_due_publications(project_id, now)
        for publication in due:
            self.task_queue.enqueue(
                "publish_content",
                {"publication_id": publication.id, "project_id": project_id},
                run_at=now,
                idempotency_key=f"publication-{publication.id}",
            )
        return len(due)


class PublisherService:
    """Сервис автопубликации: ретраи, дедупликация и идемпотентность."""

    def __init__(
        self,
        store: DatabaseStore,
        task_queue: Optional[TaskQueue] = None,
        max_attempts: int = 3,
        retry_delay_seconds: int = 60,
    ) -> None:
        self.store = store
        self.task_queue = task_queue
        self.max_attempts = max_attempts
        self.retry_delay_seconds = retry_delay_seconds
        self.logger = get_logger()
        self.alerts = AlertService(store)
        self.budgets = BudgetService(store)

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
        idempotency_key: Optional[str] = None,
    ) -> PublicationResult:
        scheduled_at = scheduled_at or datetime.utcnow()
        idempotency_key = idempotency_key or self._make_idempotency_key(
            project_id, content_item_id, platform, scheduled_at
        )
        existing = self.store.get_publication_by_idempotency_key(
            project_id, idempotency_key
        )
        if existing:
            return PublicationResult(publication=existing)
        try:
            self.budgets.record_usage(project_id, publications_used=1)
        except BudgetLimitExceeded:
            self.logger.warning(
                "publication_budget_blocked",
                extra={
                    "event": "publication_budget_blocked",
                    "project_id": project_id,
                    "content_item_id": content_item_id,
                    "platform": platform,
                },
            )
            raise
        publication = self.store.create_publication(
            project_id,
            schemas.PublicationCreate(
                content_item_id=content_item_id,
                platform=platform,
                scheduled_at=scheduled_at,
                status="scheduled",
                idempotency_key=idempotency_key,
            ),
        )
        task_id: Optional[str] = None
        if self.task_queue:
            task_id = self.task_queue.enqueue(
                "publish_content",
                {"publication_id": publication.id, "project_id": project_id},
                run_at=scheduled_at,
                idempotency_key=f"publication-{publication.id}",
            )
        return PublicationResult(publication=publication, task_id=task_id)

    def mark_published(
        self,
        project_id: int,
        publication_id: int,
        platform_post_id: str,
        platform_post_url: Optional[str] = None,
        published_at: Optional[datetime] = None,
    ) -> schemas.Publication:
        published_at = published_at or datetime.utcnow()
        publication = self.store.session.get(models.Publication, publication_id)
        if not publication or publication.project_id != project_id:
            raise KeyError("publication_not_found")
        publication.platform_post_id = platform_post_id
        publication.platform_post_url = platform_post_url
        publication.published_at = published_at
        publication.status = "published"
        publication.last_error = None
        self.store.session.add(publication)
        self.store.session.flush()
        return self.store._to_publication(publication)

    def process_due_publications(
        self, project_id: int, now: Optional[datetime] = None
    ) -> list[schemas.Publication]:
        now = now or datetime.utcnow()
        due_publications = self.store.list_due_publications(project_id, now)
        results: list[schemas.Publication] = []
        for publication in due_publications:
            results.append(self.publish_publication(project_id, publication.id))
        return results

    def publish_publication(
        self, project_id: int, publication_id: int
    ) -> schemas.Publication:
        publication = self.store.session.get(models.Publication, publication_id)
        if not publication or publication.project_id != project_id:
            raise KeyError("publication_not_found")
        if not self._qc_passed(project_id, publication.content_item_id):
            publication.status = "failed"
            publication.last_error = "qc_failed"
            self.store.session.add(publication)
            self.store.session.flush()
            return self.store._to_publication(publication)
        if publication.status == "published" and publication.platform_post_id:
            return self.store._to_publication(publication)
        if publication.status == "publishing":
            return self.store._to_publication(publication)
        publication.status = "publishing"
        publication.attempt_count += 1
        self.store.session.add(publication)
        self.store.session.flush()
        try:
            result = self._publish_to_platform(project_id, publication)
        except Exception as exc:  # noqa: BLE001 - фиксируем ошибку для ретраев
            return self._handle_publish_error(publication, str(exc))
        return self.mark_published(
            project_id,
            publication_id,
            result["platform_post_id"],
            platform_post_url=result.get("platform_post_url"),
        )

    def process_queue(self, now: Optional[datetime] = None) -> list[schemas.Publication]:
        if not isinstance(self.task_queue, InMemoryTaskQueue):
            return []
        results: list[schemas.Publication] = []
        for task in self.task_queue.pop_due(now):
            if task.task_name == "publish_content":
                publication_id = task.payload.get("publication_id")
                project_id = task.payload.get("project_id")
                if publication_id and project_id:
                    results.append(self.publish_publication(project_id, publication_id))
        return results

    def _handle_publish_error(
        self, publication: models.Publication, error_message: str
    ) -> schemas.Publication:
        publication.last_error = error_message
        if publication.attempt_count >= self.max_attempts:
            publication.status = "failed"
            self.alerts.create_alert(
                publication.project_id,
                alert_type="publication_failed",
                severity="high",
                message=error_message,
                metadata={
                    "publication_id": publication.id,
                    "platform": publication.platform,
                    "attempts": publication.attempt_count,
                },
            )
        else:
            publication.status = "scheduled"
            if self.task_queue:
                run_at = datetime.utcnow() + timedelta(
                    seconds=self.retry_delay_seconds
                )
                self.task_queue.enqueue(
                    "publish_content",
                    {"publication_id": publication.id, "project_id": publication.project_id},
                    run_at=run_at,
                    idempotency_key=f"publication-retry-{publication.id}-{publication.attempt_count}",
                )
        self.store.session.add(publication)
        self.store.session.flush()
        return self.store._to_publication(publication)

    def _publish_to_platform(
        self, project_id: int, publication: models.Publication
    ) -> Dict[str, Any]:
        content_item = self.store.session.get(
            models.ContentItem, publication.content_item_id
        )
        if not content_item:
            raise KeyError("content_item_not_found")
        body = content_item.body or ""
        metadata = content_item.metadata or {}
        if publication.platform == "telegram":
            token = self._get_integration_token(project_id, "telegram_bot")
            chat_id = metadata.get("telegram_chat_id")
            if not chat_id:
                raise ValueError("telegram_chat_id_missing")
            return self._publish_telegram(token, chat_id, body, metadata)
        if publication.platform == "vk":
            token = self._get_integration_token(project_id, "vk_api")
            owner_id = metadata.get("vk_owner_id")
            if owner_id is None:
                raise ValueError("vk_owner_id_missing")
            return self._publish_vk(token, owner_id, body, metadata)
        raise ValueError("unsupported_platform")

    def _get_integration_token(self, project_id: int, provider: str) -> str:
        tokens = self.store.list_integration_tokens(project_id)
        for token in tokens:
            if token.provider == provider:
                return token.token
        raise ValueError("integration_token_not_found")

    def _publish_telegram(
        self, token: str, chat_id: str, text: str, metadata: dict
    ) -> Dict[str, Any]:
        endpoint = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": metadata.get("disable_web_preview", True),
        }
        response = self._post_json(endpoint, payload)
        if not response.get("ok"):
            raise RuntimeError(f"telegram_error:{response}")
        result = response.get("result", {})
        message_id = result.get("message_id")
        url = None
        chat_username = metadata.get("telegram_chat_username")
        if chat_username and message_id:
            url = f"https://t.me/{chat_username}/{message_id}"
        return {"platform_post_id": str(message_id), "platform_post_url": url}

    def _publish_vk(
        self, token: str, owner_id: int, text: str, metadata: dict
    ) -> Dict[str, Any]:
        endpoint = "https://api.vk.com/method/wall.post"
        payload = {
            "owner_id": owner_id,
            "message": text,
            "from_group": int(metadata.get("vk_from_group", 1)),
            "v": metadata.get("vk_api_version", "5.199"),
            "access_token": token,
        }
        response = self._post_form(endpoint, payload)
        if "response" not in response:
            raise RuntimeError(f"vk_error:{response}")
        post_id = response["response"].get("post_id")
        url = f"https://vk.com/wall{owner_id}_{post_id}" if post_id else None
        return {"platform_post_id": str(post_id), "platform_post_url": url}

    def _post_json(self, url: str, payload: dict) -> dict:
        data = parse.urlencode(payload).encode("utf-8")
        req = request.Request(url, data=data, method="POST")
        with request.urlopen(req, timeout=10) as response:
            content = response.read().decode("utf-8")
        return json_loads(content)

    def _post_form(self, url: str, payload: dict) -> dict:
        data = parse.urlencode(payload).encode("utf-8")
        req = request.Request(url, data=data, method="POST")
        with request.urlopen(req, timeout=10) as response:
            content = response.read().decode("utf-8")
        return json_loads(content)

    @staticmethod
    def _make_idempotency_key(
        project_id: int, content_item_id: int, platform: str, scheduled_at: datetime
    ) -> str:
        return f"{project_id}:{content_item_id}:{platform}:{scheduled_at.isoformat()}"

    def _qc_passed(self, project_id: int, content_item_id: int) -> bool:
        report = self.store.session.scalar(
            select(models.QcReport)
            .where(
                models.QcReport.project_id == project_id,
                models.QcReport.content_item_id == content_item_id,
            )
            .order_by(models.QcReport.created_at.desc())
        )
        return bool(report and report.passed)


def json_loads(content: str) -> dict:
    try:
        return json.loads(content)
    except ValueError:
        return {"raw": content}
