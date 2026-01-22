from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from arq.connections import RedisSettings, create_pool


@dataclass(frozen=True)
class ArqTaskQueue:
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    queue_name: str = os.getenv("ARQ_QUEUE_NAME", "contentzavod")

    def enqueue(
        self,
        task_name: str,
        payload: dict,
        run_at: Optional[datetime] = None,
        idempotency_key: Optional[str] = None,
    ) -> str:
        return asyncio.run(
            self._enqueue_async(task_name, payload, run_at, idempotency_key)
        )

    async def _enqueue_async(
        self,
        task_name: str,
        payload: dict,
        run_at: Optional[datetime],
        idempotency_key: Optional[str],
    ) -> str:
        redis = await create_pool(RedisSettings.from_dsn(self.redis_url))
        try:
            job_id = idempotency_key
            defer_until = None
            now = datetime.utcnow()
            if run_at and run_at > now:
                defer_until = run_at
            job = await redis.enqueue_job(
                task_name,
                **payload,
                _job_id=job_id,
                _queue_name=self.queue_name,
                _defer_until=defer_until,
            )
            if job:
                return job.job_id
            return job_id or ""
        finally:
            redis.close()
            await redis.wait_closed()
