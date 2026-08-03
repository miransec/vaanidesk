"""Language detection interface and heuristic detector (Phase 2).

Not a production-grade language model — rule/heuristic only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class LanguageResult:
    language_code: str  # en | hi | hinglish | mr | unknown
    script: str  # latin | devanagari | mixed | unknown
    confidence: float
    signals: list[str] = field(default_factory=list)
    code_switching: bool = False


class LanguageDetector(Protocol):
    def detect(self, text: str) -> LanguageResult: ...


_DEVANAGARI = re.compile(r"[\u0900-\u097F]")
_LATIN = re.compile(r"[A-Za-z]")

# Marathi-leaning Devanagari cues (heuristic, not authoritative).
_MR_CUES = ("माझी", "माझा", "कुठे", "आहे", "रद्द करा", "कृपया", "आहेत", "तुम्ही", "समजलो")
_HI_CUES = ("मेरा", "मेरी", "कहाँ", "है", "रद्द", "कृपया", "आप", "स्थिति", "ऑर्डर")
_HINGLISH_CUES = (
    "mera",
    "meri",
    "kahan",
    "kidhar",
    "kaha",
    "hai",
    "bhai",
    "kar",
    "karo",
    "karna",
    "do",
    "address",
    "cancel",
    "order",
    "madad",
    "please",
)


class HeuristicLanguageDetector:
    """Deterministic script + cue detector for English / Hindi / Hinglish / Marathi."""

    def detect(self, text: str) -> LanguageResult:
        raw = text.strip()
        if not raw:
            return LanguageResult("unknown", "unknown", 0.0, ["empty"], False)

        has_deva = bool(_DEVANAGARI.search(raw))
        has_latin = bool(_LATIN.search(raw))
        lower = raw.lower()
        signals: list[str] = []

        if has_deva and has_latin:
            signals.append("mixed_script_identifiers")
            mr_hits = sum(1 for c in _MR_CUES if c in raw)
            hi_hits = sum(1 for c in _HI_CUES if c in raw)
            # Latin public refs (VD-…) alongside Devanagari prose → still hi/mr.
            if mr_hits > hi_hits:
                signals.append(f"mr_cues={mr_hits}")
                return LanguageResult("mr", "mixed", min(0.95, 0.55 + 0.1 * mr_hits), signals, True)
            if hi_hits > 0 or any(c in raw for c in ("ऑर्डर", "कहाँ", "रद्द")):
                signals.append(f"hi_cues={hi_hits}")
                return LanguageResult(
                    "hi", "mixed", min(0.95, 0.55 + 0.1 * max(hi_hits, 1)), signals, True
                )
            signals.append("mixed_default_hinglish")
            return LanguageResult("hinglish", "mixed", 0.7, signals, True)

        if has_deva:
            signals.append("devanagari_script")
            mr_hits = sum(1 for c in _MR_CUES if c in raw)
            hi_hits = sum(1 for c in _HI_CUES if c in raw)
            if mr_hits > hi_hits:
                signals.append(f"mr_cues={mr_hits}")
                return LanguageResult("mr", "devanagari", min(0.95, 0.55 + 0.1 * mr_hits), signals)
            if hi_hits > 0:
                signals.append(f"hi_cues={hi_hits}")
                return LanguageResult("hi", "devanagari", min(0.95, 0.55 + 0.1 * hi_hits), signals)
            # Default Devanagari without strong cues → Hindi with lower confidence.
            signals.append("deva_default_hi")
            return LanguageResult("hi", "devanagari", 0.5, signals)

        # Latin script
        signals.append("latin_script")
        hinglish_hits = sum(1 for c in _HINGLISH_CUES if re.search(rf"\b{re.escape(c)}\b", lower))
        english_order = bool(
            re.search(
                r"\b(where|please|cancel|status|delivery|address|"
                r"order|help|hello|hi)\b",
                lower,
            )
        )

        # Strong Hinglish patterns
        if re.search(r"\b(mera|meri|kahan|kidhar|karna|kar do|bhai)\b", lower):
            signals.append("hinglish_markers")
            conf = min(0.95, 0.6 + 0.05 * hinglish_hits)
            return LanguageResult("hinglish", "latin", conf, signals, code_switching=True)

        if hinglish_hits >= 2 and not re.search(r"\b(where is|please cancel|my order)\b", lower):
            signals.append(f"hinglish_cues={hinglish_hits}")
            return LanguageResult("hinglish", "latin", 0.65, signals, True)

        if english_order or re.search(r"^[a-z0-9\s.,'!?-]+$", lower):
            signals.append("english_lexicon")
            return LanguageResult("en", "latin", 0.8 if english_order else 0.55, signals)

        signals.append("uncertain_latin")
        return LanguageResult("unknown", "latin", 0.3, signals)


_default_detector: LanguageDetector | None = None


def get_language_detector() -> LanguageDetector:
    global _default_detector
    if _default_detector is None:
        _default_detector = HeuristicLanguageDetector()
    return _default_detector
