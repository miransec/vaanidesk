"""Intent classification interface and heuristic classifier (Phase 2)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol

from app.agents.language import LanguageResult


class Intent(StrEnum):
    GREETING = "greeting"
    ORDER_STATUS = "order_status"
    ORDER_DETAILS = "order_details"
    UPDATE_DELIVERY_ADDRESS = "update_delivery_address"
    CANCELLATION_ELIGIBILITY = "cancellation_eligibility"
    CANCEL_ORDER = "cancel_order"
    CREATE_SUPPORT_TICKET = "create_support_ticket"
    SUPPORT_TICKET_STATUS = "support_ticket_status"
    HUMAN_ESCALATION = "human_escalation"
    POLICY_QUESTION = "policy_question"
    UNKNOWN = "unknown"


ORDER_REF_RE = re.compile(r"\b(VD-\d{4,})\b", re.IGNORECASE)
TICKET_REF_RE = re.compile(r"\b(TKT-\d{4,})\b", re.IGNORECASE)
# Also accept bare numbers in demos like "order 1001" → map later to VD- if needed
BARE_ORDER_RE = re.compile(r"\b(?:order|ऑर्डर)\s*(?:#|no\.?|number)?\s*(\d{4,5})\b", re.IGNORECASE)


@dataclass
class IntentResult:
    intent: Intent
    confidence: float
    entities: dict[str, Any] = field(default_factory=dict)
    missing_fields: list[str] = field(default_factory=list)
    clarification_question: str | None = None


class IntentClassifier(Protocol):
    def classify(self, text: str, language: LanguageResult) -> IntentResult: ...


def _extract_entities(text: str) -> dict[str, Any]:
    entities: dict[str, Any] = {}
    order_match = ORDER_REF_RE.search(text)
    if order_match:
        entities["order_ref"] = order_match.group(1).upper()
    else:
        bare = BARE_ORDER_RE.search(text)
        if bare:
            # Map demo bare numbers into public refs when they look like VD suffix
            num = int(bare.group(1))
            if num < 10000:
                entities["order_ref"] = f"VD-{10000 + num}" if num < 1000 else f"VD-{num}"
            else:
                entities["order_ref"] = f"VD-{num}"
            # Prefer VD-10001 style for 1001 → VD-10001
            if 1000 <= num <= 9999:
                entities["order_ref"] = f"VD-{num}"

    ticket_match = TICKET_REF_RE.search(text)
    if ticket_match:
        entities["ticket_ref"] = ticket_match.group(1).upper()

    # Address extraction heuristics
    addr = None
    for pattern in (
        r"(?:new\s+)?(?:address|delivery\s+address)\s*(?:to|as|:)\s*[\"']?(.+?)[\"']?\s*$",
        r"(?:change|update).*?(?:to)\s+(.{10,200})$",
        r"(?:address|पता|पत्ता)\s*(?:change|बदल|:)?\s*(?:to|kar do|कर दो)?\s*[\"']?(.+)",
        r"\bto\s+(.{10,200})$",
    ):
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if m:
            candidate = m.group(1).strip(" .,\"'")
            # Drop trailing order-ref-only junk
            if ORDER_REF_RE.fullmatch(candidate):
                continue
            if len(candidate) >= 10:
                addr = candidate
                break
    if addr:
        entities["new_address"] = addr

    # Issue description for tickets — leftover after stripping refs
    if len(text.strip()) >= 12:
        entities.setdefault("issue_description", text.strip()[:500])

    return entities


class HeuristicIntentClassifier:
    def classify(self, text: str, language: LanguageResult) -> IntentResult:
        raw = text.strip()
        lower = raw.lower()
        entities = _extract_entities(raw)

        # Agent-coaching / playbook questions are knowledge lookups, not customer escalation.
        if re.search(
            r"(what\s+should\s+an?\s+agent|how\s+should\s+(an?\s+)?agent|de-?escalat|"
            r"agent\s+playbook|script\s+for\s+(an?\s+)?agent|when\s+a\s+customer\s+is\s+angry)",
            lower,
        ):
            return IntentResult(Intent.POLICY_QUESTION, 0.88, entities)

        # Human escalation (customer asking to reach a person)
        if re.search(
            r"\b(human|agent|representative|support\s+agent|talk\s+to\s+(a\s+)?person)\b",
            lower,
        ) or any(x in raw for x in ("इंसान", "एजेंट", "मनुष्य", "मनुष्यसेवा")):
            return IntentResult(Intent.HUMAN_ESCALATION, 0.9, entities)

        # Greetings
        if re.fullmatch(
            r"(hello|hi|hey|namaste|namaskar|नमस्ते|नमस्कार|good\s+(morning|evening|afternoon))[!?.]*",
            lower,
        ) or raw in {"नमस्ते", "नमस्कार"}:
            return IntentResult(Intent.GREETING, 0.95, entities)

        # Cancel
        if (
            re.search(
                r"(cancel\s+(my\s+)?order|order\s+cancel|cancel\s+kar|रद्द|रद्द कर)",
                lower,
            )
            or "रद्द" in raw
        ):
            missing = []
            q = None
            if "order_ref" not in entities:
                missing.append("order_ref")
                q = _clarify_order(language.language_code)
            return IntentResult(Intent.CANCEL_ORDER, 0.88, entities, missing, q)

        # Cancellation eligibility
        if re.search(r"(can\s+i\s+cancel|eligible\s+to\s+cancel|cancellation\s+eligib)", lower):
            missing = []
            q = None
            if "order_ref" not in entities:
                missing.append("order_ref")
                q = _clarify_order(language.language_code)
            return IntentResult(Intent.CANCELLATION_ELIGIBILITY, 0.85, entities, missing, q)

        # Address update
        if (
            re.search(
                r"(change|update).*(address|delivery)|address.*(change|update)|delivery address|"
                r"address change|पता बदल|पत्ता बदल",
                lower,
            )
            or any(x in raw for x in ("पता", "पत्ता"))
            and ("बदल" in raw or "change" in lower)
        ):
            missing = []
            q_parts = []
            if "order_ref" not in entities:
                missing.append("order_ref")
                q_parts.append(_clarify_order(language.language_code))
            if "new_address" not in entities:
                missing.append("new_address")
                q_parts.append(_clarify_address(language.language_code))
            q = " ".join(q_parts) if missing else None
            return IntentResult(Intent.UPDATE_DELIVERY_ADDRESS, 0.86, entities, missing, q)

        # Ticket status
        if (
            re.search(r"(ticket\s+status|status\s+of\s+(my\s+)?ticket|TKT-)", lower)
            or "टिकट" in raw
        ):
            missing = []
            q = None
            if "ticket_ref" not in entities:
                missing.append("ticket_ref")
                q = _clarify_ticket(language.language_code)
            return IntentResult(Intent.SUPPORT_TICKET_STATUS, 0.84, entities, missing, q)

        # Create ticket
        if re.search(
            r"(create\s+(a\s+)?(support\s+)?ticket|open\s+(a\s+)?ticket|file\s+(a\s+)?complaint|"
            r"support\s+ticket| शिकायत|टिकट बना)",
            lower,
        ):
            missing = []
            q = None
            if (
                "issue_description" not in entities
                or len(entities.get("issue_description", "")) < 8
            ):
                missing.append("issue_description")
                q = _clarify_issue(language.language_code)
            return IntentResult(Intent.CREATE_SUPPORT_TICKET, 0.82, entities, missing, q)

        # Policy / knowledge questions (RAG) — before generic order status
        policy_hit = re.search(
            r"(policy|warranty|refund|return|exchange|delivery\s+time|shipping|"
            r"damaged|broken|payment\s+dispute|account\s+security|privacy|"
            r"what\s+is\s+your|how\s+(do|long|can)|can\s+i\s+return|"
            r"नीति|वापसी|वारंटी|रिफंड|डिलीवरी\s+नीति|परतावा)",
            lower,
        ) or any(x in raw for x in ("नीति", "वापसी", "वारंटी", "परतावा", "रिफंड"))
        # Do not treat concrete cancel/status with order refs as policy
        order_action = "order_ref" in entities and re.search(
            r"\b(cancel|status|where\s+is|track)\b", lower
        )
        if policy_hit and not order_action:
            return IntentResult(Intent.POLICY_QUESTION, 0.86, entities)

        # Order details
        if re.search(
            r"(order\s+details|details\s+of\s+(my\s+)?order|what\s+did\s+i\s+order)",
            lower,
        ):
            missing = []
            q = None
            if "order_ref" not in entities:
                missing.append("order_ref")
                q = _clarify_order(language.language_code)
            return IntentResult(Intent.ORDER_DETAILS, 0.84, entities, missing, q)

        # Order status
        if (
            re.search(
                r"(where\s+is\s+(my\s+)?order|order\s+status|track\s+(my\s+)?order|"
                r"mera\s+order|order\s+kahan|order\s+kidhar|ऑर्डर.*(कहाँ|कुठे)|कहाँ\s+है|कुठे\s+आहे)",
                lower,
            )
            or any(x in raw for x in ("कहाँ", "कुठे"))
            and ("ऑर्डर" in raw or "order" in lower)
        ):
            missing = []
            q = None
            if "order_ref" not in entities:
                missing.append("order_ref")
                q = _clarify_order(language.language_code)
            return IntentResult(Intent.ORDER_STATUS, 0.9, entities, missing, q)

        return IntentResult(
            Intent.UNKNOWN,
            0.25,
            entities,
            clarification_question=_unknown_prompt(language.language_code),
        )


def _clarify_order(lang: str) -> str:
    if lang == "hinglish":
        return "Kaunsa order? Public order reference batao jaise VD-10001."
    if lang == "hi":
        return "कृपया सार्वजनिक ऑर्डर संदर्भ बताएँ, जैसे VD-10001।"
    if lang == "mr":
        return "कृपया सार्वजनिक ऑर्डर संदर्भ सांगा, उदा. VD-10001."
    return "Which order? Please share the public order reference (for example VD-10001)."


def _clarify_address(lang: str) -> str:
    if lang == "hinglish":
        return "Naya delivery address poora likho (kam se kam 10 characters)."
    if lang == "hi":
        return "कृपया नया डिलीवरी पता पूरा लिखें (कम से कम 10 अक्षर)।"
    if lang == "mr":
        return "कृपया नवीन डिलिव्हरी पत्ता पूर्ण लिहा (किमान 10 अक्षरे)."
    return "What should the new delivery address be? Please provide at least 10 characters."


def _clarify_ticket(lang: str) -> str:
    if lang == "hinglish":
        return "Ticket reference chahiye, jaise TKT-10001."
    if lang == "hi":
        return "कृपया टिकट संदर्भ बताएँ, जैसे TKT-10001।"
    if lang == "mr":
        return "कृपया तिकीट संदर्भ सांगा, उदा. TKT-10001."
    return "Which ticket? Please share the public ticket reference (for example TKT-10001)."


def _clarify_issue(lang: str) -> str:
    if lang == "hinglish":
        return "Ticket ke liye short issue description likho."
    if lang == "hi":
        return "कृपया समस्या का संक्षिप्त विवरण लिखें।"
    if lang == "mr":
        return "कृपया समस्येचे थोडक्यात वर्णन लिहा."
    return "Please describe the issue so I can open a support ticket."


def _unknown_prompt(lang: str) -> str:
    if lang == "hinglish":
        return (
            "Samajh nahi aaya. Order status, cancel, address change, ticket, "
            "ya human escalation try karo."
        )
    if lang == "hi":
        return "मैं समझ नहीं पाया। ऑर्डर स्थिति, रद्दीकरण, पता बदलना, टिकट या मानव सहायता आज़माएँ।"
    if lang == "mr":
        return "समजले नाही. ऑर्डर स्थिती, रद्द, पत्ता बदल, तिकीट किंवा मनुष्य मदत वापरून पहा."
    return (
        "I did not understand that request. Try order status, cancellation, "
        "address change, support tickets, or ask for a human."
    )


_default_classifier: IntentClassifier | None = None


def get_intent_classifier() -> IntentClassifier:
    global _default_classifier
    if _default_classifier is None:
        _default_classifier = HeuristicIntentClassifier()
    return _default_classifier
