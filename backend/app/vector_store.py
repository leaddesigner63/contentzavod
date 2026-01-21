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
        atom = self.session.get(models.Atom, atom_id)
        if not atom or atom.project_id != project_id:
            raise KeyError("atom_not_found")
        atom.embedding = embedding
        self.session.add(atom)

    def search_atoms(
        self, project_id: int, embedding: List[float], limit: int = 5
    ) -> List[models.Atom]:
        stmt = (
            select(models.Atom)
            .where(models.Atom.project_id == project_id)
            .order_by(models.Atom.embedding.cosine_distance(embedding))
            .limit(limit)
        )
        return self.session.scalars(stmt).all()
