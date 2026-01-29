from __future__ import annotations

import json
import logging
import os
import sys
from collections import defaultdict
from datetime import datetime
from threading import Lock
from typing import Any, Dict, Optional, Tuple

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        extra = {
            key: value
            for key, value in record.__dict__.items()
            if key
            not in {
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
            }
        }
        event = extra.pop("event", None)
        if event:
            payload["event"] = event
        for key in ("request_id", "project_id", "alert_type", "severity", "metric"):
            if key in extra:
                payload[key] = extra.pop(key)
        span = trace.get_current_span()
        if span:
            context = span.get_span_context()
            if context.is_valid:
                payload["trace_id"] = format(context.trace_id, "032x")
                payload["span_id"] = format(context.span_id, "016x")
        if extra:
            payload["extra"] = extra
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str | None = None) -> None:
    log_level = level or os.getenv("LOG_LEVEL", "INFO")
    logger = logging.getLogger("contentzavod")
    if logger.handlers:
        return
    logger.setLevel(log_level)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.propagate = False


def configure_tracing(app: Any) -> None:
    service_name = os.getenv("OTEL_SERVICE_NAME", "contentzavod")
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if endpoint:
        exporter = OTLPSpanExporter(endpoint=endpoint)
    else:
        exporter = ConsoleSpanExporter()
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)


def get_logger() -> logging.Logger:
    return logging.getLogger("contentzavod")


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = Lock()
        self._counters: dict[Tuple[str, Tuple[Tuple[str, str], ...]], float] = defaultdict(float)
        self._gauges: dict[Tuple[str, Tuple[Tuple[str, str], ...]], float] = {}

    def increment(self, name: str, value: float = 1.0, tags: Optional[dict[str, str]] = None) -> None:
        key = self._build_key(name, tags)
        with self._lock:
            self._counters[key] += value

    def set_gauge(self, name: str, value: float, tags: Optional[dict[str, str]] = None) -> None:
        key = self._build_key(name, tags)
        with self._lock:
            self._gauges[key] = value

    def snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            counters = list(self._counters.items())
            gauges = list(self._gauges.items())
        now = datetime.utcnow().isoformat() + "Z"
        samples: list[dict[str, Any]] = []
        for (name, tags), value in counters:
            samples.append(
                {
                    "name": name,
                    "metric_type": "counter",
                    "value": value,
                    "tags": dict(tags),
                    "timestamp": now,
                }
            )
        for (name, tags), value in gauges:
            samples.append(
                {
                    "name": name,
                    "metric_type": "gauge",
                    "value": value,
                    "tags": dict(tags),
                    "timestamp": now,
                }
            )
        return samples

    @staticmethod
    def _build_key(name: str, tags: Optional[dict[str, str]]) -> Tuple[str, Tuple[Tuple[str, str], ...]]:
        if not tags:
            return (name, tuple())
        return (name, tuple(sorted(tags.items())))


_METRICS = MetricsRegistry()


def increment_metric(name: str, value: float = 1.0, tags: Optional[dict[str, str]] = None) -> None:
    _METRICS.increment(name, value=value, tags=tags)


def set_metric_gauge(name: str, value: float, tags: Optional[dict[str, str]] = None) -> None:
    _METRICS.set_gauge(name, value=value, tags=tags)


def get_metrics_snapshot() -> list[dict[str, Any]]:
    return _METRICS.snapshot()


def log_event(
    logger: logging.Logger,
    event: str,
    *,
    level: int = logging.INFO,
    **fields: Any,
) -> None:
    extra = {"event": event, **fields}
    logger.log(level, event, extra=extra)
