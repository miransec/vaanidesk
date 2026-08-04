"""Channel-aware message renderers for different output formats."""

from __future__ import annotations

import html
from typing import Any


def render_web(text: str, **kwargs: Any) -> str:
    return text


def render_email_plain(text: str, **kwargs: Any) -> str:
    citations = kwargs.get("citations", [])
    parts = [text]
    if citations:
        parts.append("\n---\nSources:")
        for c in citations[:3]:
            parts.append(f"  - {c.get('document_title', '')} §{c.get('section_label', '')}")
    parts.append("\n-- VaaniDesk Support")
    return "\n".join(parts)


def render_email_html(text: str, **kwargs: Any) -> str:
    safe_text = html.escape(text).replace("\n", "<br>")
    citations = kwargs.get("citations", [])
    cite_html = ""
    if citations:
        items = "".join(
            f"<li>{html.escape(c.get('document_title', ''))}"
            f" §{html.escape(c.get('section_label', ''))}</li>"
            for c in citations[:3]
        )
        cite_html = f"<hr><p><strong>Sources:</strong></p><ul>{items}</ul>"
    footer = "<p style='color:#666;font-size:12px'>— VaaniDesk Support</p>"
    return (
        f"<div style='font-family:sans-serif;max-width:600px'>"
        f"<p>{safe_text}</p>{cite_html}{footer}</div>"
    )


def render_whatsapp(text: str, **kwargs: Any) -> str:
    citations = kwargs.get("citations", [])
    result = text[:4000]
    if citations:
        cite_refs = ", ".join(c.get("section_label", "") for c in citations[:2])
        result += f"\n\n📎 {cite_refs}"
    return result


def render_citation(citations: list[dict[str, Any]], channel: str = "web") -> str:
    if not citations:
        return ""
    if channel == "whatsapp":
        return " | ".join(f"{c.get('section_label', '')}" for c in citations[:2])
    parts = ["Sources:"]
    for c in citations:
        parts.append(f"  [{c.get('document_title', '')} §{c.get('section_label', '')}]")
    return "\n".join(parts)


def render_no_answer(channel: str = "web") -> str:
    base = "I wasn't able to find a confident answer for that question."
    if channel == "whatsapp":
        return f"{base} Reply AGENT for human support."
    return f"{base} Would you like me to connect you with a support agent?"


def render_ticket(ticket_ref: str, channel: str = "web") -> str:
    return f"A support ticket has been created: {ticket_ref}. Our team will follow up shortly."


def render_confirmation_link(url: str, summary: str, channel: str = "web") -> str:
    if channel == "whatsapp":
        return f"⚠️ Action required: {summary}\nPlease confirm via: {url}"
    if channel == "email":
        return f"Action required: {summary}\n\nConfirm here: {url}"
    return f"Please confirm this action: {summary}\n{url}"


def render_escalation(channel: str = "web") -> str:
    return "I'm connecting you with a human support agent. They'll be with you shortly."


RENDERERS = {
    "web": render_web,
    "email_plain": render_email_plain,
    "email_html": render_email_html,
    "whatsapp": render_whatsapp,
}


def render_for_channel(channel_type: str, text: str, **kwargs: Any) -> str:
    renderer = RENDERERS.get(channel_type, render_web)
    return renderer(text, **kwargs)
