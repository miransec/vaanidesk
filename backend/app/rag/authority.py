"""Document authority helpers for customer-policy vs agent-playbook ranking."""

from __future__ import annotations

import re

# Titles/slugs that are primary customer policy sources.
_CUSTOMER_POLICY = (
    "damaged products",
    "damaged-products",
    "return procedure",
    "return-procedure",
    "refund timeline",
    "refund-timeline",
    "cancellation policy",
    "cancellation-policy",
    "exchange policy",
    "delivery policy",
    "warranty terms",
    "payment disputes",
    "account security",
    "privacy of support",
)

# Agent / operational guidance — valid for agent-coaching queries, demoted for customer policy Qs.
_AGENT_OPS = (
    "escalation",
    "de-escalation",
    "agent playbook",
    "playbook",
    "safety hub",
    "product instructions",
)

# Security-test / injection corpora — never primary customer or coaching evidence.
_SECURITY_BAIT = (
    "internal override",
    "injection bait",
    "override notes",
)

_AGENT_QUERY = (
    "agent",
    "de-escalat",
    "deescalat",
    "what should an agent",
    "script",
    "angry customer",
    "how should support",
    "playbook",
)


def is_agent_coaching_query(query: str) -> bool:
    lower = query.lower()
    return any(n in lower for n in _AGENT_QUERY)


def document_authority_multiplier(*, title: str, query: str) -> float:
    """Return a multiplicative boost/penalty for fused retrieval scores."""
    hay = title.lower()
    agent_q = is_agent_coaching_query(query)

    is_customer_policy = any(t in hay for t in _CUSTOMER_POLICY)
    is_agent_ops = any(t in hay for t in _AGENT_OPS)
    is_security_bait = any(t in hay for t in _SECURITY_BAIT)

    # Injection / override test docs must never outrank real policy or playbooks.
    if is_security_bait:
        return 0.15

    if agent_q:
        if is_agent_ops:
            return 1.45
        if is_customer_policy:
            return 0.9
        return 1.0

    # Customer-facing policy questions prefer authoritative customer policies.
    if is_customer_policy:
        concepts = _query_concepts(query)
        title_hits = sum(1 for c in concepts if c in hay)
        boost = 1.25 + min(0.35, 0.08 * title_hits)
        # Direct damaged-product policy questions should strongly prefer the
        # dedicated Damaged Products document over adjacent warranty/refund docs.
        if "damaged" in concepts and "damaged" in hay:
            boost += 0.55
        if "refund" in concepts and ("refund" in hay or "return" in hay):
            boost += 0.15
        return boost
    if is_agent_ops:
        return 0.55
    return 1.0


def _query_concepts(query: str) -> list[str]:
    lower = query.lower()
    concepts: list[str] = []
    mapping = [
        (("damaged", "defective", "doa", "क्षतिग्रस्त", "टूटा", "खराब"), "damaged"),
        (("refund", "रिफंड"), "refund"),
        (("return", "वापसी", "परतावा", "wapas"), "return"),
        (("replacement", "replace"), "replacement"),
        (("cancel", "रद्द"), "cancel"),
        (("warranty", "वारंटी"), "warranty"),
        (("delivery", "shipping", "डिलीवरी"), "delivery"),
    ]
    for needles, label in mapping:
        if any(n in lower for n in needles):
            concepts.append(label)
    return concepts


def query_concepts(query: str) -> list[str]:
    return _query_concepts(query)


def evidence_concept_coverage(*, query: str, texts: list[str]) -> float:
    """Fraction of important query concepts present in selected evidence text."""
    concepts = _query_concepts(query)
    blob = " ".join(texts).lower()
    if not concepts:
        # No recognized policy concepts (often nonsense / out-of-domain bait).
        # Require distinctive content tokens from the query to appear in evidence.
        raw = re.findall(r"[A-Za-z\u0900-\u097F]{4,}", query.lower())
        stop = {
            "what",
            "when",
            "where",
            "which",
            "that",
            "this",
            "with",
            "from",
            "your",
            "have",
            "please",
            "about",
            "should",
            "could",
            "would",
        }
        # Treat common policy nouns as too weak alone to ground an answer.
        weak = {"policy", "policies", "terms", "guide", "support"}
        distinctive = [t for t in raw if t not in stop and t not in weak]
        if not distinctive:
            return 0.1
        hits = sum(1 for t in distinctive if t in blob)
        return hits / max(1, len(distinctive))
    # Expand synonyms for matching inside evidence
    syn = {
        "damaged": ("damaged", "defective", "doa", "physical damage", "क्षतिग्रस्त"),
        "refund": ("refund", "full refund", "partial refund", "रिफंड"),
        "return": ("return", "pickup", "reverse logistics", "वापसी"),
        "replacement": ("replacement", "replace", "full unit"),
        "cancel": ("cancel", "cancellation"),
        "warranty": ("warranty",),
        "delivery": ("delivery", "shipping"),
    }
    hits = 0
    for c in concepts:
        if any(s in blob for s in syn.get(c, (c,))):
            hits += 1
    return hits / len(concepts)


def confidence_band(score: float) -> str:
    if score >= 0.72:
        return "high"
    if score >= 0.45:
        return "medium"
    return "low"


_WORD = re.compile(r"[a-zA-Z\u0900-\u097F]{3,}")
