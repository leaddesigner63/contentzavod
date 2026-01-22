from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import select

from .. import models, schemas
from ..storage_db import DatabaseStore


@dataclass(frozen=True)
class LearningResult:
    state: schemas.AutoLearningState
    applied_changes: list[schemas.LearningEvent]
    rollback_applied: bool


class AutoLearningService:
    def __init__(self, store: DatabaseStore) -> None:
        self.store = store

    def run(self, project_id: int, now: Optional[datetime] = None) -> LearningResult:
        now = now or datetime.utcnow()
        config = self.store.get_or_create_auto_learning_config(project_id)
        state = self.store.get_or_create_auto_learning_state(project_id)
        updated_state = state
        applied_changes: list[schemas.LearningEvent] = []

        updated_state = self._ensure_window(updated_state, now)
        updated_state = self._ensure_baseline(updated_state)

        rollback_applied = False
        recent_snapshots = self.store.list_recent_metric_snapshots(
            project_id, config.rollback_window
        )
        avg_ctr = self._average_ctr(recent_snapshots)
        if (
            avg_ctr is not None
            and avg_ctr < config.rollback_threshold
            and updated_state.stable_parameters
            and updated_state.parameters != updated_state.stable_parameters
        ):
            rollback_event = self._apply_rollback(
                project_id, updated_state, avg_ctr, now
            )
            updated_state = rollback_event[0]
            applied_changes.append(rollback_event[1])
            rollback_applied = True

        if not rollback_applied:
            updated_state, new_events = self._apply_optimizations(
                project_id, updated_state, config, now
            )
            applied_changes.extend(new_events)

        updated_state = self.store.update_auto_learning_state(project_id, updated_state)
        return LearningResult(
            state=updated_state,
            applied_changes=applied_changes,
            rollback_applied=rollback_applied,
        )

    def select_parameters(self, project_id: int) -> dict[str, Any]:
        state = self.store.get_or_create_auto_learning_state(project_id)
        return state.parameters or {
            "slot": "default",
            "cta": "standard",
        }

    def _ensure_window(
        self, state: schemas.AutoLearningState, now: datetime
    ) -> schemas.AutoLearningState:
        if not state.window_started_at or now - state.window_started_at >= timedelta(days=7):
            state.window_started_at = now
            state.changes_in_window = 0
        return state

    @staticmethod
    def _ensure_baseline(
        state: schemas.AutoLearningState,
    ) -> schemas.AutoLearningState:
        if not state.parameters:
            state.parameters = {"slot": "default", "cta": "standard"}
        if not state.stable_parameters:
            state.stable_parameters = dict(state.parameters)
        return state

    def _apply_optimizations(
        self,
        project_id: int,
        state: schemas.AutoLearningState,
        config: schemas.AutoLearningConfig,
        now: datetime,
    ) -> tuple[schemas.AutoLearningState, list[schemas.LearningEvent]]:
        if state.changes_in_window >= config.max_changes_per_week:
            return state, []
        protected = {param.lower() for param in config.protected_parameters}
        candidates = self._best_variants(project_id, config.rollback_window)
        events: list[schemas.LearningEvent] = []
        for key in ("slot", "cta", "angle"):
            if key in protected:
                continue
            if key not in candidates:
                continue
            best_value = candidates[key]
            if best_value == state.parameters.get(key):
                continue
            previous_value = state.parameters.get(key, "")
            state.stable_parameters = dict(state.parameters)
            state.parameters[key] = best_value
            state.last_change_at = now
            state.changes_in_window += 1
            event = self.store.create_learning_event(
                project_id,
                schemas.LearningEventCreate(
                    parameter=key,
                    previous_value=str(previous_value),
                    new_value=str(best_value),
                    reason="auto-optimization",
                ),
            )
            events.append(event)
            if state.changes_in_window >= config.max_changes_per_week:
                break
        return state, events

    def _apply_rollback(
        self,
        project_id: int,
        state: schemas.AutoLearningState,
        avg_ctr: float,
        now: datetime,
    ) -> tuple[schemas.AutoLearningState, schemas.LearningEvent]:
        previous = dict(state.parameters)
        state.parameters = dict(state.stable_parameters)
        state.last_rollback_at = now
        state.changes_in_window += 1
        event = self.store.create_learning_event(
            project_id,
            schemas.LearningEventCreate(
                parameter="auto_rollback",
                previous_value=str(previous),
                new_value=str(state.parameters),
                reason=f"avg_ctr_below_threshold:{avg_ctr:.4f}",
            ),
        )
        return state, event

    def _best_variants(self, project_id: int, limit: int) -> dict[str, str]:
        snapshots = self.store.list_recent_metric_snapshots(project_id, limit)
        if not snapshots:
            return {}
        item_map = {
            item.id: item
            for item in self.store.session.scalars(
                select(models.ContentItem).where(
                    models.ContentItem.project_id == project_id
                )
            )
        }
        perf: dict[str, dict[str, list[float]]] = {}
        for snapshot in snapshots:
            item = item_map.get(snapshot.content_item_id)
            if not item:
                continue
            ctr = self._ctr(snapshot)
            if ctr is None:
                continue
            for key in ("slot", "cta", "angle"):
                value = item.metadata.get(key)
                if not value:
                    continue
                perf.setdefault(key, {}).setdefault(str(value), []).append(ctr)
        best: dict[str, str] = {}
        for key, variants in perf.items():
            best_value = max(
                variants.items(), key=lambda item: sum(item[1]) / len(item[1])
            )[0]
            best[key] = best_value
        return best

    def _average_ctr(self, snapshots: list[models.MetricSnapshot]) -> Optional[float]:
        values = [ctr for snapshot in snapshots if (ctr := self._ctr(snapshot)) is not None]
        if not values:
            return None
        return sum(values) / len(values)

    @staticmethod
    def _ctr(snapshot: models.MetricSnapshot) -> Optional[float]:
        if snapshot.impressions <= 0:
            return None
        return snapshot.clicks / snapshot.impressions
