"""Reranking provider interface + deterministic mock reranker."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class RerankCandidate:
    chunk_id: UUID
    text: str
    base_score: float


@dataclass(frozen=True)
class RerankResult:
    chunk_id: UUID
    score: float


class RerankingProvider(Protocol):
    def rerank(self, query: str, candidates: list[RerankCandidate]) -> list[RerankResult]: ...

    @property
    def name(self) -> str: ...


class MockLexicalReranker:
    name = "mock-lexical-overlap"

    def rerank(self, query: str, candidates: list[RerankCandidate]) -> list[RerankResult]:
        q_tokens = set(_tokens(query))
        scored: list[RerankResult] = []
        for c in candidates:
            c_tokens = set(_tokens(c.text))
            if not q_tokens or not c_tokens:
                overlap = 0.0
            else:
                overlap = len(q_tokens & c_tokens) / math.sqrt(len(q_tokens) * len(c_tokens))
            score = 0.6 * overlap + 0.4 * c.base_score
            scored.append(RerankResult(chunk_id=c.chunk_id, score=score))
        scored.sort(key=lambda r: r.score, reverse=True)
        return scored


def _tokens(text: str) -> list[str]:
    return re.findall(r"[\w\u0900-\u097F]+", text.lower())


def get_reranker() -> RerankingProvider:
    return MockLexicalReranker()
