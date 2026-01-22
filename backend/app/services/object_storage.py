from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Optional

from .video_workshop import ObjectStorage, StorageObject


class LocalObjectStorage(ObjectStorage):
    def __init__(self, root: Path, public_base_url: str) -> None:
        self.root = root
        self.public_base_url = public_base_url.rstrip("/")
        self.root.mkdir(parents=True, exist_ok=True)

    def upload_file(
        self,
        file_path: Path,
        content_type: str,
        metadata: Optional[dict] = None,
    ) -> StorageObject:
        key = f"{uuid.uuid4().hex}/{file_path.name}"
        destination = self.root / key
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_path, destination)
        return StorageObject(key=key, url=f"{self.public_base_url}/{key}")
