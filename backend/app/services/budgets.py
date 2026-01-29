from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from .. import schemas
from ..observability import get_logger, increment_metric, log_event
from ..storage_db import DatabaseStore
from .alerts import AlertService


class BudgetLimitExceeded(RuntimeError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class BudgetService:
    def __init__(self, store: DatabaseStore) -> None:
        self.store = store
        self.logger = get_logger()
        self.alerts = AlertService(store)

    def get_active_budget(self, project_id: int) -> schemas.Budget:
        budget = self.store.get_latest_budget(project_id)
        if not budget:
            raise KeyError("budget_not_found")
        return budget

    def record_usage(
        self,
        project_id: int,
        token_used: int = 0,
        video_seconds_used: int = 0,
        publications_used: int = 0,
        usage_date: Optional[datetime] = None,
    ) -> schemas.BudgetUsage:
        budget = self.get_active_budget(project_id)
        usage_date = usage_date or datetime.utcnow()
        self.ensure_budget(
            project_id,
            token_used=token_used,
            video_seconds_used=video_seconds_used,
            publications_used=publications_used,
            usage_date=usage_date,
        )
        usage = self.store.create_budget_usage(
            project_id,
            schemas.BudgetUsageCreate(
                budget_id=budget.id,
                usage_date=usage_date,
                token_used=token_used,
                video_seconds_used=video_seconds_used,
                publications_used=publications_used,
            ),
        )
        increment_metric(
            "budget_usage_recorded_total",
            tags={"project_id": str(project_id)},
        )
        log_event(
            self.logger,
            "budget_usage_recorded",
            project_id=project_id,
            budget_id=budget.id,
            token_used=token_used,
            video_seconds_used=video_seconds_used,
            publications_used=publications_used,
        )
        return usage

    def ensure_budget(
        self,
        project_id: int,
        token_used: int = 0,
        video_seconds_used: int = 0,
        publications_used: int = 0,
        usage_date: Optional[datetime] = None,
    ) -> None:
        usage_date = usage_date or datetime.utcnow()
        budget = self.get_active_budget(project_id)
        window_start = self._get_window_start("daily", usage_date)
        totals = self.store.sum_budget_usage(project_id, window_start, usage_date)
        total_tokens = totals.token_used + token_used
        total_video = totals.video_seconds_used + video_seconds_used
        total_publications = totals.publications_used + publications_used
        reasons = []
        if budget.token_limit and total_tokens > budget.token_limit:
            reasons.append("token_limit_exceeded")
        if budget.video_seconds_limit and total_video > budget.video_seconds_limit:
            reasons.append("video_seconds_limit_exceeded")
        if budget.publication_limit and total_publications > budget.publication_limit:
            reasons.append("publication_limit_exceeded")
        if reasons:
            message = ",".join(reasons)
            self.alerts.create_alert(
                project_id,
                alert_type="budget_exceeded",
                severity="critical",
                message=message,
                metadata={
                    "token_limit": budget.token_limit,
                    "video_seconds_limit": budget.video_seconds_limit,
                    "publication_limit": budget.publication_limit,
                    "token_used": total_tokens,
                    "video_seconds_used": total_video,
                    "publications_used": total_publications,
                    "window": "daily",
                },
            )
            self.logger.warning(
                "budget_limit_exceeded",
                extra={
                    "event": "budget_limit_exceeded",
                    "project_id": project_id,
                    "reasons": reasons,
                    "token_used": total_tokens,
                    "video_seconds_used": total_video,
                    "publications_used": total_publications,
                },
            )
            raise BudgetLimitExceeded(message)

    def build_report(self, project_id: int) -> schemas.BudgetReport:
        budget = self.get_active_budget(project_id)
        now = datetime.utcnow()
        daily = self._build_window_usage(project_id, budget, "daily", now)
        weekly = self._build_window_usage(project_id, budget, "weekly", now)
        monthly = self._build_window_usage(project_id, budget, "monthly", now)
        blocked = self._is_blocked(budget, daily)
        return schemas.BudgetReport(
            project_id=project_id,
            budget=budget,
            windows=[daily, weekly, monthly],
            is_blocked=blocked,
            generated_at=now,
        )

    def _build_window_usage(
        self, project_id: int, budget: schemas.Budget, window: str, now: datetime
    ) -> schemas.BudgetWindowUsage:
        start = self._get_window_start(window, now)
        totals = self.store.sum_budget_usage(project_id, start, now)
        budget_limit = self._get_budget_limit(budget, window)
        return schemas.BudgetWindowUsage(
            window=window,
            token_used=totals.token_used,
            video_seconds_used=totals.video_seconds_used,
            publications_used=totals.publications_used,
            budget_limit=budget_limit,
            token_limit=budget.token_limit,
            video_seconds_limit=budget.video_seconds_limit,
            publications_limit=budget.publication_limit,
            token_used_pct=self._calc_pct(totals.token_used, budget.token_limit),
            video_seconds_used_pct=self._calc_pct(
                totals.video_seconds_used, budget.video_seconds_limit
            ),
            publications_used_pct=self._calc_pct(
                totals.publications_used, budget.publication_limit
            ),
            token_remaining=self._calc_remaining(totals.token_used, budget.token_limit),
            video_seconds_remaining=self._calc_remaining(
                totals.video_seconds_used, budget.video_seconds_limit
            ),
            publications_remaining=self._calc_remaining(
                totals.publications_used, budget.publication_limit
            ),
        )

    @staticmethod
    def _get_window_start(window: str, now: datetime) -> datetime:
        if window == "daily":
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        if window == "weekly":
            start = now - timedelta(days=now.weekday())
            return start.replace(hour=0, minute=0, second=0, microsecond=0)
        if window == "monthly":
            return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        raise ValueError("unsupported_window")

    @staticmethod
    def _get_budget_limit(budget: schemas.Budget, window: str) -> float:
        if window == "daily":
            return budget.daily
        if window == "weekly":
            return budget.weekly
        if window == "monthly":
            return budget.monthly
        raise ValueError("unsupported_window")

    @staticmethod
    def _calc_pct(used: int, limit: int) -> Optional[float]:
        if not limit:
            return None
        return round((used / limit) * 100, 2)

    @staticmethod
    def _calc_remaining(used: int, limit: int) -> Optional[int]:
        if not limit:
            return None
        return max(limit - used, 0)

    @staticmethod
    def _is_blocked(
        budget: schemas.Budget, daily_usage: schemas.BudgetWindowUsage
    ) -> bool:
        if budget.token_limit and daily_usage.token_used > budget.token_limit:
            return True
        if budget.video_seconds_limit and daily_usage.video_seconds_used > budget.video_seconds_limit:
            return True
        if budget.publication_limit and daily_usage.publications_used > budget.publication_limit:
            return True
        return False
