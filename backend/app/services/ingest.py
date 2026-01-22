from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Protocol, Sequence

from .. import schemas
from ..storage_db import DatabaseStore
from ..vector_store import VectorStore


class TaskQueue(Protocol):
    def enqueue(self, task_name: str, payload: dict) -> str:
        ...


@dataclass(frozen=True)
class IngestResult:
    source_id: int
    atoms: List[schemas.Atom]


class IngestService:
    """Сервис загрузки знаний: STT, парсинг, атомы смысла и эмбеддинги."""

    def __init__(
        self,
        store: DatabaseStore,
        vector_store: Optional[VectorStore] = None,
        task_queue: Optional[TaskQueue] = None,
    ) -> None:
        self.store = store
        self.vector_store = vector_store
        self.task_queue = task_queue

    def enqueue_ingest(self, project_id: int, source_id: int) -> Optional[str]:
        if not self.task_queue:
            return None
        return self.task_queue.enqueue(
            "ingest_source",
            {"project_id": project_id, "source_id": source_id},
        )

    def transcribe_audio(self, audio_uri: str) -> str:
        """STT для аудио. Возвращает текстовую расшифровку (заглушка)."""
        return f"[stt] transcript for {audio_uri}"

    def parse_documents(self, content: str) -> Sequence[str]:
        """Парсинг документов/ссылок и разбиение на смысловые куски (заглушка)."""
        return [chunk.strip() for chunk in content.split("\n") if chunk.strip()]

    def extract_atoms(
        self, source_id: int, chunks: Iterable[str]
    ) -> List[schemas.AtomCreate]:
        """Экстракция атомов смысла из текста (заглушка)."""
        atoms: List[schemas.AtomCreate] = []
        for chunk in chunks:
            atoms.append(
                schemas.AtomCreate(
                    source_id=source_id,
                    kind="fact",
                    text=chunk,
                    source_backed=True,
                    embedding=[0.0, 0.0, 0.0],
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
        self, project_id: int, source_id: int, content: str
    ) -> IngestResult:
        chunks = self.parse_documents(content)
        atoms_payload = self.extract_atoms(source_id, chunks)
        atoms = self.persist_atoms(project_id, atoms_payload)
        return IngestResult(source_id=source_id, atoms=atoms)
