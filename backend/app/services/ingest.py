from __future__ import annotations

from dataclasses import dataclass
import html
import os
from pathlib import Path
import re
from typing import Iterable, List, Optional, Protocol, Sequence
from urllib import request
from uuid import uuid4

from .. import schemas
from ..storage_db import DatabaseStore
from ..vector_store import VectorStore


class TaskQueue(Protocol):
    def enqueue(self, task_name: str, payload: dict) -> str:
        ...


class SttProvider(Protocol):
    def transcribe(self, uri: str, content: bytes, content_type: str) -> str:
        ...


@dataclass(frozen=True)
class IngestResult:
    source: schemas.Source
    atoms: List[schemas.Atom]


@dataclass(frozen=True)
class StoredArtifact:
    uri: str
    version: int
    metadata: dict


class IngestService:
    """Сервис загрузки знаний: STT, парсинг, атомы смысла и эмбеддинги."""

    def __init__(
        self,
        store: DatabaseStore,
        vector_store: Optional[VectorStore] = None,
        task_queue: Optional[TaskQueue] = None,
        stt_provider: Optional[SttProvider] = None,
        storage_root: Optional[Path] = None,
    ) -> None:
        self.store = store
        self.vector_store = vector_store
        self.task_queue = task_queue
        self.stt_provider = stt_provider or MockSttProvider()
        base_path = storage_root or Path(
            os.getenv("INGEST_STORAGE_PATH", "storage/ingest")
        )
        self.storage_root = base_path
        self.storage_root.mkdir(parents=True, exist_ok=True)

    def enqueue_ingest(self, project_id: int, source_id: int) -> Optional[str]:
        if not self.task_queue:
            return None
        return self.task_queue.enqueue(
            "ingest_source",
            {"project_id": project_id, "source_id": source_id},
        )

    def transcribe_audio(self, audio_uri: str, content: bytes, content_type: str) -> str:
        """STT для аудио/видео. Возвращает текстовую расшифровку."""
        return self.stt_provider.transcribe(audio_uri, content, content_type)

    def parse_documents(self, content: str) -> Sequence[str]:
        """Парсинг документов/ссылок и разбиение на смысловые куски (заглушка)."""
        return [chunk.strip() for chunk in content.split("\n") if chunk.strip()]

    def extract_atoms(
        self,
        project_id: int,
        source_id: int,
        source_uri: Optional[str],
        source_version: Optional[int],
        chunks: Iterable[str],
    ) -> List[schemas.AtomCreate]:
        """Экстракция атомов смысла из текста (заглушка)."""
        embedding_dim = self._get_embedding_dimension(project_id)
        atoms: List[schemas.AtomCreate] = []
        for chunk in chunks:
            embedding = self.generate_embedding(chunk, embedding_dim)
            atoms.append(
                schemas.AtomCreate(
                    source_id=source_id,
                    kind="fact",
                    text=chunk,
                    source_backed=True,
                    embedding=embedding,
                    source_uri=source_uri,
                    source_version=source_version,
                    artifact_metadata={
                        "source_uri": source_uri,
                        "source_version": source_version,
                    },
                    status="ready",
                    is_current=True,
                )
            )
        return atoms

    def persist_atoms(
        self, project_id: int, atoms: Iterable[schemas.AtomCreate]
    ) -> List[schemas.Atom]:
        created: List[schemas.Atom] = []
        for atom_payload in atoms:
            atom = self.store.create_atom(project_id, atom_payload)
            if self.vector_store and atom_payload.embedding is not None:
                self.vector_store.upsert_atom_embedding(
                    project_id, atom.id, atom_payload.embedding
                )
            created.append(atom)
        return created

    def ingest_source(
        self, project_id: int, source: schemas.Source, content: str
    ) -> IngestResult:
        chunks = self.parse_documents(content)
        atoms_payload = self.extract_atoms(
            project_id,
            source.id,
            source.uri,
            source.artifact_version,
            chunks,
        )
        atoms = self.persist_atoms(project_id, atoms_payload)
        return IngestResult(source=source, atoms=atoms)

    def ingest_file(
        self,
        project_id: int,
        filename: str,
        content: bytes,
        content_type: str,
        title: Optional[str] = None,
        source_type: Optional[str] = None,
    ) -> IngestResult:
        resolved_source_type = self._detect_source_type(
            content_type, filename, source_type
        )
        file_artifact = self._save_bytes(
            content,
            suffix=Path(filename).suffix or ".bin",
            metadata={"content_type": content_type, "filename": filename},
        )
        source = self.store.create_source(
            project_id,
            schemas.SourceCreate(
                title=title or filename,
                source_type=resolved_source_type,
                uri=file_artifact.uri,
                content=None,
                artifact_uri=None,
                artifact_version=1,
                artifact_metadata={"file": file_artifact.metadata},
                status="processing",
                is_current=True,
            ),
        )
        try:
            if resolved_source_type in {"audio", "video"}:
                transcript = self.transcribe_audio(
                    file_artifact.uri, content, content_type
                )
                transcript_artifact = self._save_text(
                    transcript,
                    suffix=".txt",
                    metadata={"source_uri": file_artifact.uri},
                )
                source = self.store.update_source(
                    project_id,
                    source.id,
                    schemas.SourceUpdate(
                        content=transcript,
                        artifact_uri=transcript_artifact.uri,
                        artifact_version=transcript_artifact.version,
                        artifact_metadata=transcript_artifact.metadata,
                        status="ready",
                        is_current=True,
                    ),
                )
                return self.ingest_source(project_id, source, transcript)
            extracted_text = self._extract_text(content, content_type, filename)
            extraction_artifact = self._save_text(
                extracted_text,
                suffix=".txt",
                metadata={"source_uri": file_artifact.uri},
            )
            source = self.store.update_source(
                project_id,
                source.id,
                schemas.SourceUpdate(
                    content=extracted_text,
                    artifact_uri=extraction_artifact.uri,
                    artifact_version=extraction_artifact.version,
                    artifact_metadata=extraction_artifact.metadata,
                    status="ready",
                    is_current=True,
                ),
            )
            return self.ingest_source(project_id, source, extracted_text)
        except Exception as exc:
            self.store.update_source(
                project_id,
                source.id,
                schemas.SourceUpdate(status="failed", is_current=False),
            )
            raise exc

    def ingest_link(
        self,
        project_id: int,
        url: str,
        title: Optional[str] = None,
        source_type: str = "link",
    ) -> IngestResult:
        content, content_type = self._download_url(url)
        download_artifact = self._save_bytes(
            content,
            suffix=self._guess_suffix(content_type),
            metadata={"content_type": content_type, "url": url},
        )
        source = self.store.create_source(
            project_id,
            schemas.SourceCreate(
                title=title or url,
                source_type=source_type,
                uri=url,
                content=None,
                artifact_uri=None,
                artifact_version=1,
                artifact_metadata={"download": download_artifact.metadata},
                status="processing",
                is_current=True,
            ),
        )
        try:
            extracted_text = self._extract_text(content, content_type, url)
            extraction_artifact = self._save_text(
                extracted_text,
                suffix=".txt",
                metadata={"source_uri": url},
            )
            source = self.store.update_source(
                project_id,
                source.id,
                schemas.SourceUpdate(
                    content=extracted_text,
                    artifact_uri=extraction_artifact.uri,
                    artifact_version=extraction_artifact.version,
                    artifact_metadata=extraction_artifact.metadata,
                    status="ready",
                    is_current=True,
                ),
            )
            return self.ingest_source(project_id, source, extracted_text)
        except Exception as exc:
            self.store.update_source(
                project_id,
                source.id,
                schemas.SourceUpdate(status="failed", is_current=False),
            )
            raise exc

    def generate_embedding(self, text: str, dimension: int) -> List[float]:
        base = abs(hash(text)) % 10000
        return [((base + idx) % 1000) / 1000 for idx in range(dimension)]

    def _get_embedding_dimension(self, project_id: int) -> int:
        if self.vector_store:
            return self.vector_store.get_embedding_dimension(project_id)
        return 1536

    def _detect_source_type(
        self, content_type: str, filename: str, source_type: Optional[str]
    ) -> str:
        if source_type:
            return source_type
        if content_type.startswith("audio/"):
            return "audio"
        if content_type.startswith("video/"):
            return "video"
        extension = Path(filename).suffix.lower()
        if extension in {".mp3", ".wav", ".m4a"}:
            return "audio"
        if extension in {".mp4", ".mov", ".avi"}:
            return "video"
        return "document"

    def _download_url(self, url: str) -> tuple[bytes, str]:
        with request.urlopen(url) as response:
            content = response.read()
            content_type = response.headers.get("Content-Type", "application/octet-stream")
            return content, content_type

    def _extract_text(self, content: bytes, content_type: str, source_hint: str) -> str:
        if "html" in content_type:
            text = content.decode("utf-8", errors="ignore")
            text = re.sub(r"<[^>]+>", " ", text)
            return html.unescape(text)
        if content_type.startswith("text/") or source_hint.endswith(".txt"):
            return content.decode("utf-8", errors="ignore")
        return content.decode("utf-8", errors="ignore")

    def _guess_suffix(self, content_type: str) -> str:
        if "html" in content_type:
            return ".html"
        if content_type.startswith("text/"):
            return ".txt"
        return ".bin"

    def _save_bytes(self, content: bytes, suffix: str, metadata: dict) -> StoredArtifact:
        artifact_id = uuid4().hex
        path = self.storage_root / f"{artifact_id}{suffix}"
        path.write_bytes(content)
        return StoredArtifact(uri=str(path), version=1, metadata=metadata)

    def _save_text(self, content: str, suffix: str, metadata: dict) -> StoredArtifact:
        artifact_id = uuid4().hex
        path = self.storage_root / f"{artifact_id}{suffix}"
        path.write_text(content, encoding="utf-8")
        return StoredArtifact(uri=str(path), version=1, metadata=metadata)


class MockSttProvider:
    def transcribe(self, uri: str, content: bytes, content_type: str) -> str:
        return f"[stt:{content_type}] transcript for {uri}"
