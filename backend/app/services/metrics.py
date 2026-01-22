from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional
from urllib import parse, request

from .. import schemas
from ..storage_db import DatabaseStore


@dataclass(frozen=True)
class MetricsResult:
    snapshots: list[schemas.MetricSnapshot]


class MetricsCollector:
    def __init__(self, store: DatabaseStore, timeout: int = 5) -> None:
        self.store = store
        self.timeout = timeout

    def collect(self, project_id: int) -> MetricsResult:
        snapshots: list[schemas.MetricSnapshot] = []
        publications = self.store.list_publications(project_id)
        for publication in publications:
            if publication.status != "published" or not publication.platform_post_id:
                continue
            metrics = None
            if publication.platform == "telegram":
                metrics = self._collect_telegram_metrics(project_id, publication)
            elif publication.platform == "vk":
                metrics = self._collect_vk_metrics(project_id, publication)
            if metrics is None:
                continue
            clicks = self.store.count_clicks(project_id, publication.content_item_id)
            metrics["clicks"] = max(metrics.get("clicks", 0), clicks)
            snapshot = self.store.create_metric_snapshot(
                project_id,
                schemas.MetricSnapshotCreate(
                    content_item_id=publication.content_item_id,
                    impressions=metrics.get("impressions", 0),
                    clicks=metrics.get("clicks", 0),
                    likes=metrics.get("likes", 0),
                    comments=metrics.get("comments", 0),
                    shares=metrics.get("shares", 0),
                ),
            )
            snapshots.append(snapshot)
        return MetricsResult(snapshots=snapshots)

    def _collect_telegram_metrics(
        self, project_id: int, publication: schemas.Publication
    ) -> Optional[dict[str, int]]:
        token = self.store.get_integration_token_by_provider(project_id, "telegram")
        if not token:
            return None
        identifiers = self._split_telegram_post_id(publication.platform_post_id)
        if not identifiers:
            return None
        chat_id, message_id = identifiers
        url = (
            f"https://api.telegram.org/bot{token.token}/getMessage?"
            f"chat_id={parse.quote(chat_id)}&message_id={message_id}"
        )
        payload = self._fetch_json(url)
        if not payload or not payload.get("ok"):
            return None
        result = payload.get("result", {})
        views = int(result.get("views") or 0)
        return {
            "impressions": views,
            "clicks": 0,
            "likes": 0,
            "comments": 0,
            "shares": 0,
        }

    def _collect_vk_metrics(
        self, project_id: int, publication: schemas.Publication
    ) -> Optional[dict[str, int]]:
        token = self.store.get_integration_token_by_provider(project_id, "vk")
        if not token:
            return None
        if "_" not in publication.platform_post_id:
            return None
        owner_id, post_id = publication.platform_post_id.split("_", 1)
        params = {
            "access_token": token.token,
            "v": "5.131",
            "posts": f"{owner_id}_{post_id}",
        }
        url = "https://api.vk.com/method/wall.getById?" + parse.urlencode(params)
        payload = self._fetch_json(url)
        if not payload or "response" not in payload:
            return None
        response = payload.get("response")
        if not response:
            return None
        post = response[0]
        return {
            "impressions": int(post.get("views", {}).get("count") or 0),
            "clicks": 0,
            "likes": int(post.get("likes", {}).get("count") or 0),
            "comments": int(post.get("comments", {}).get("count") or 0),
            "shares": int(post.get("reposts", {}).get("count") or 0),
        }

    def _fetch_json(self, url: str) -> Optional[dict[str, Any]]:
        try:
            with request.urlopen(url, timeout=self.timeout) as response:
                data = response.read().decode("utf-8")
            return json.loads(data)
        except Exception:
            return None

    @staticmethod
    def _split_telegram_post_id(value: str) -> Optional[tuple[str, str]]:
        if ":" not in value:
            return None
        chat_id, message_id = value.split(":", 1)
        if not chat_id or not message_id:
            return None
        return chat_id, message_id
