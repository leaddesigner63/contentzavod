from __future__ import annotations

import os
from functools import lru_cache

from cryptography.fernet import Fernet


@lru_cache(maxsize=1)
def get_fernet() -> Fernet:
    key = os.getenv("CONTENTZAVOD_ENCRYPTION_KEY")
    if not key:
        raise RuntimeError("CONTENTZAVOD_ENCRYPTION_KEY is not set")
    return Fernet(key)


def encrypt_secret(value: str) -> str:
    return get_fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str) -> str:
    return get_fernet().decrypt(value.encode("utf-8")).decode("utf-8")
