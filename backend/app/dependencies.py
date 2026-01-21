from __future__ import annotations

from collections.abc import Generator

from .db import get_session
from .storage_db import DatabaseStore


def get_store() -> Generator[DatabaseStore, None, None]:
    with get_session() as session:
        yield DatabaseStore(session)
