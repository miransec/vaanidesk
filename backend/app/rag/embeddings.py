"""Embedding provider interface and deterministic lexical mock embeddings.

Deterministic lexical embedding baseline for local development and testing —
not production semantic embeddings.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

from app.models.knowledge import EMBEDDING_DIM

_TOKEN_RE = re.compile(r"[\w\u0900-\u097F]+", re.UNICODE)


class EmbeddingProvider(Protocol):
    def embed(self, text: str) -> list[float]: ...

    @property
    def name(self) -> str: ...

    @property
    def disclaimer(self) -> str: ...


class LexicalHashEmbeddingProvider:
    """Stable feature-hashed word/char n-gram vectors (L2-normalized)."""

    name = "mock-lexical-hash"
    disclaimer = (
        "Deterministic lexical embedding baseline for local development and testing "
        "— not production semantic embeddings."
    )
    dim = EMBEDDING_DIM

    def embed(self, text: str) -> list[float]:
        normalized = _normalize(text)
        vec = [0.0] * self.dim
        tokens = _TOKEN_RE.findall(normalized)
        # Word unigrams + bigrams
        for tok in tokens:
            _accumulate(vec, f"w1:{tok}", 1.0)
        for a, b in zip(tokens, tokens[1:], strict=False):
            _accumulate(vec, f"w2:{a}_{b}", 0.7)
        # Character 3-grams on compact form
        compact = re.sub(r"\s+", "", normalized)
        for i in range(max(0, len(compact) - 2)):
            _accumulate(vec, f"c3:{compact[i : i + 3]}", 0.35)
        return _l2_normalize(vec)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _accumulate(vec: list[float], feature: str, weight: float) -> None:
    digest = hashlib.sha256(feature.encode("utf-8")).digest()
    idx = int.from_bytes(digest[:4], "big") % len(vec)
    sign = 1.0 if digest[4] % 2 == 0 else -1.0
    vec[idx] += sign * weight


def _l2_normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec))
    if norm <= 1e-12:
        return vec
    return [v / norm for v in vec]


_default: EmbeddingProvider | None = None


def get_embedding_provider() -> EmbeddingProvider:
    global _default
    if _default is None:
        _default = LexicalHashEmbeddingProvider()
    return _default
