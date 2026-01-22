from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re
from typing import List, Optional, Protocol

from .. import models, schemas
from ..storage_db import DatabaseStore
from ..vector_store import VectorStore


class TaskQueue(Protocol):
    def enqueue(self, task_name: str, payload: dict) -> str:
        ...


@dataclass(frozen=True)
class QcResult:
    report: schemas.QcReport


class QcService:
    """Сервис контроля качества: тональность, факты, риски, читабельность."""

    def __init__(
        self,
        store: DatabaseStore,
        task_queue: Optional[TaskQueue] = None,
        vector_store: Optional[VectorStore] = None,
    ) -> None:
        self.store = store
        self.task_queue = task_queue
        self.vector_store = vector_store

    def enqueue_qc(self, project_id: int, content_item_id: int) -> Optional[str]:
        if not self.task_queue:
            return None
        return self.task_queue.enqueue(
            "qc_check", {"project_id": project_id, "content_item_id": content_item_id}
        )

    def run_checks(self, project_id: int, content_item_id: int) -> QcResult:
        content_item = self.store.session.get(models.ContentItem, content_item_id)
        if not content_item or content_item.project_id != project_id:
            raise KeyError("content_item_not_found")
        body = content_item.body or ""
        brand_config = self._get_active_brand_config(project_id)

        tone_ok, tone_reason = self._check_tone(body, brand_config)
        forbidden_ok, forbidden_reason = self._check_forbidden(body, brand_config)
        risk_ok, risk_reason = self._check_risks(body)
        readability_ok, readability_reason = self._check_readability(body)
        repetition_ok, repetition_reason = self._check_repetition(body)
        facts_ok, facts_reason = self._check_facts(project_id, body)

        checks = [
            tone_ok,
            forbidden_ok,
            risk_ok,
            readability_ok,
            repetition_ok,
            facts_ok,
        ]
        score = sum(1 for check in checks if check) / len(checks)
        passed = all(checks)
        reasons: List[str] = [
            tone_reason,
            forbidden_reason,
            risk_reason,
            readability_reason,
            repetition_reason,
            facts_reason,
        ]
        report = self.store.create_qc_report(
            project_id,
            schemas.QcReportCreate(
                content_item_id=content_item_id,
                score=score,
                passed=passed,
                reasons=reasons,
            ),
        )
        return QcResult(report=report)

    def _get_active_brand_config(self, project_id: int) -> Optional[schemas.BrandConfig]:
        configs = self.store.list_brand_configs(project_id)
        for config in configs:
            if config.is_active:
                return config
        return configs[-1] if configs else None

    def _check_tone(
        self, body: str, brand_config: Optional[schemas.BrandConfig]
    ) -> tuple[bool, str]:
        if not brand_config:
            return True, "tone_no_config"
        tone_tokens = self._tokenize(brand_config.tone)
        if not tone_tokens:
            return True, "tone_no_tokens"
        body_tokens = set(self._tokenize(body))
        matched = [token for token in tone_tokens if token in body_tokens]
        if matched:
            return True, f"tone_match:{','.join(matched)}"
        return False, "tone_mismatch"

    def _check_forbidden(
        self, body: str, brand_config: Optional[schemas.BrandConfig]
    ) -> tuple[bool, str]:
        if not brand_config or not brand_config.forbidden:
            return True, "forbidden_none"
        lowered = body.lower()
        hits = [term for term in brand_config.forbidden if term.lower() in lowered]
        if hits:
            return False, f"forbidden_hits:{','.join(hits)}"
        return True, "forbidden_ok"

    def _check_risks(self, body: str) -> tuple[bool, str]:
        lowered = body.lower()
        risky_patterns = [
            r"100%",
            r"гарантирован",
            r"без\s*рисков",
            r"точно",
            r"самый\s+лучший",
        ]
        hits = [pattern for pattern in risky_patterns if re.search(pattern, lowered)]
        if hits:
            return False, "risk_hits"
        return True, "risk_ok"

    def _check_readability(self, body: str) -> tuple[bool, str]:
        sentences = self._split_sentences(body)
        if not sentences:
            return False, "readability_empty"
        avg_length = sum(len(sentence.split()) for sentence in sentences) / len(sentences)
        if avg_length > 30:
            return False, "readability_long_sentences"
        if len(body) < 120:
            return False, "readability_too_short"
        return True, "readability_ok"

    def _check_repetition(self, body: str) -> tuple[bool, str]:
        sentences = self._split_sentences(body)
        if not sentences:
            return False, "repetition_empty"
        counts = Counter(sentence.strip().lower() for sentence in sentences)
        repeats = [sentence for sentence, count in counts.items() if count > 1]
        if repeats:
            return False, "repetition_found"
        tokens = self._tokenize(body)
        token_counts = Counter(tokens)
        if tokens and max(token_counts.values()) / len(tokens) > 0.2:
            return False, "repetition_token_overuse"
        return True, "repetition_ok"

    def _check_facts(self, project_id: int, body: str) -> tuple[bool, str]:
        facts = [sentence for sentence in self._split_sentences(body) if len(sentence) > 20]
        if not facts:
            return True, "facts_none"
        if not self.vector_store:
            return False, "rag_unavailable"
        embedding_dim = self.vector_store.get_embedding_dimension(project_id)
        backed = 0
        for fact in facts:
            embedding = self._generate_embedding(fact, embedding_dim)
            atoms = self.vector_store.search_atoms(project_id, embedding, limit=5)
            if self._is_fact_backed(fact, atoms):
                backed += 1
        total = len(facts)
        ratio = backed / total if total else 0.0
        if ratio >= 0.6:
            return True, f"facts_backed:{backed}/{total}"
        return False, f"facts_unverified:{backed}/{total}"

    @staticmethod
    def _split_sentences(body: str) -> List[str]:
        chunks = re.split(r"[.!?]+", body)
        return [chunk.strip() for chunk in chunks if chunk.strip()]

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return re.findall(r"[\w']+", text.lower())

    @staticmethod
    def _generate_embedding(text: str, dimension: int) -> List[float]:
        base = abs(hash(text)) % 10000
        return [((base + idx) % 1000) / 1000 for idx in range(dimension)]

    @staticmethod
    def _is_fact_backed(fact: str, atoms: List[models.Atom]) -> bool:
        fact_tokens = set(re.findall(r"[\w']+", fact.lower()))
        for atom in atoms:
            atom_tokens = set(re.findall(r"[\w']+", atom.text.lower()))
            if not atom_tokens:
                continue
            overlap = len(fact_tokens & atom_tokens) / len(fact_tokens | atom_tokens)
            if overlap >= 0.3:
                return True
        return False
