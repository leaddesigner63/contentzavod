from __future__ import annotations

from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models


class VectorStore:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_atom_embedding(
        self, project_id: int, atom_id: int, embedding: List[float]
    ) -> None:
        self._require_project_index(project_id)
        atom = self.session.get(models.Atom, atom_id)
        if not atom or atom.project_id != project_id:
            raise KeyError("atom_not_found")
        atom.embedding = embedding
        self.session.add(atom)

    def search_atoms(
        self, project_id: int, embedding: List[float], limit: int = 5
    ) -> List[models.Atom]:
        self._require_project_index(project_id)
        stmt = (
            select(models.Atom)
            .where(models.Atom.project_id == project_id)
            .order_by(models.Atom.embedding.cosine_distance(embedding))
            .limit(limit)
        )
        return self.session.scalars(stmt).all()

    def _require_project_index(self, project_id: int) -> models.ProjectVectorIndex:
        index = self.session.scalar(
            select(models.ProjectVectorIndex).where(
                models.ProjectVectorIndex.project_id == project_id
            )
        )
        if not index:
            raise KeyError("vector_index_not_found")
        return index
