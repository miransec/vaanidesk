"""Deterministic policy document chunking."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    index: int
    section_label: str
    text: str


def chunk_document(text: str, *, max_chars: int = 500, overlap: int = 60) -> list[TextChunk]:
    """Split on markdown headings / blank lines, then window long sections.

    Same input always yields the same chunks.
    """
    cleaned = text.replace("\r\n", "\n").strip()
    if not cleaned:
        return []

    sections = _split_sections(cleaned)
    chunks: list[TextChunk] = []
    idx = 0
    for label, body in sections:
        body = body.strip()
        if not body:
            continue
        if len(body) <= max_chars:
            chunks.append(TextChunk(index=idx, section_label=label, text=body))
            idx += 1
            continue
        start = 0
        while start < len(body):
            end = min(len(body), start + max_chars)
            if end < len(body):
                # Prefer break on whitespace
                cut = body.rfind(" ", start + max_chars // 2, end)
                if cut > start:
                    end = cut
            piece = body[start:end].strip()
            if piece:
                chunks.append(TextChunk(index=idx, section_label=label, text=piece))
                idx += 1
            if end >= len(body):
                break
            start = max(end - overlap, start + 1)
    return chunks


def _split_sections(text: str) -> list[tuple[str, str]]:
    parts = re.split(r"(?m)^(#{1,3}\s+.+)$", text)
    if len(parts) == 1:
        return [("body", text)]
    sections: list[tuple[str, str]] = []
    preamble = parts[0].strip()
    if preamble:
        sections.append(("body", preamble))
    i = 1
    while i + 1 < len(parts):
        heading = parts[i].lstrip("#").strip() or "section"
        body = parts[i + 1]
        sections.append((heading[:180], body))
        i += 2
    return sections
