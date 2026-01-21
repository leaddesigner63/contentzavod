from __future__ import annotations

"""Deprecated in-memory store kept for reference."""


class InMemoryStore:  # pragma: no cover - deprecated
    def __init__(self) -> None:
        raise RuntimeError("InMemoryStore is deprecated; use DatabaseStore")
