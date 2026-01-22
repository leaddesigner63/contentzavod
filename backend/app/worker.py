from __future__ import annotations

import asyncio
import os
from typing import Any

from arq import cron
from arq.connections import RedisSettings

from .db import get_session
from .services.publisher import PublicationScheduler, PublisherService
from .services.task_queue import ArqTaskQueue
from .storage_db import DatabaseStore


def _publish_sync(publication_id: int, project_id: int) -> str:
    with get_session() as session:
        store = DatabaseStore(session)
        service = PublisherService(store, task_queue=ArqTaskQueue())
        publication = service.publish_publication(project_id, publication_id)
        return publication.status


async def publish_content(ctx: dict[str, Any], publication_id: int, project_id: int) -> str:
    return await asyncio.to_thread(_publish_sync, publication_id, project_id)


def _tick_sync() -> int:
    with get_session() as session:
        store = DatabaseStore(session)
        scheduler = PublicationScheduler(store, ArqTaskQueue())
        total = 0
        for project in store.list_projects():
            total += scheduler.tick(project.id)
        return total


async def tick_publication_scheduler(ctx: dict[str, Any]) -> int:
    return await asyncio.to_thread(_tick_sync)


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(
        os.getenv("REDIS_URL", "redis://localhost:6379/0")
    )
    queue_name = os.getenv("ARQ_QUEUE_NAME", "contentzavod")
    functions = [publish_content]
    cron_jobs = [cron(tick_publication_scheduler, minute="*/1")]
