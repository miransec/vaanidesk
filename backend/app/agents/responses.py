"""Deterministic multilingual response templates for Phase 2 workflow."""

from __future__ import annotations

from typing import Any


def respond(
    *,
    language_code: str,
    kind: str,
    **kwargs: Any,
) -> str:
    table = _TEMPLATES.get(kind, {})
    template = table.get(language_code) or table.get("en") or "{kind}"
    try:
        return template.format(**kwargs)
    except (KeyError, ValueError):
        return str(template)


_TEMPLATES: dict[str, dict[str, str]] = {
    "greeting": {
        "en": (
            "Hello! I'm VaaniDesk's support assistant (mock workflow — not a production model). "
            "I can check order status, details, cancellation eligibility, update addresses "
            "(with confirmation), open tickets, or queue a human handoff."
        ),
        "hi": (
            "नमस्ते! मैं VaaniDesk सहायक हूँ (mock workflow — production model नहीं)। "
            "ऑर्डर स्थिति, विवरण, रद्दीकरण योग्यता, पता बदलना (पुष्टि के साथ), टिकट या मानव सहायता।"
        ),
        "hinglish": (
            "Namaste! Main VaaniDesk support assistant hoon "
            "(mock workflow — production model nahi). "
            "Order status, details, cancel eligibility, address change (confirmation ke saath), "
            "ticket, ya human handoff kar sakta hoon."
        ),
        "mr": (
            "नमस्कार! मी VaaniDesk सहाय्यक आहे (mock workflow — production model नाही). "
            "ऑर्डर स्थिती, तपशील, रद्द योग्यता, पत्ता बदल (पुष्टीसह), तिकीट किंवा मनुष्य मदत."
        ),
    },
    "clarification": {
        "en": "{question}",
        "hi": "{question}",
        "hinglish": "{question}",
        "mr": "{question}",
    },
    "order_status": {
        "en": ("Order {order_ref} is currently **{status}**. Delivery address on file: {address}."),
        "hi": "ऑर्डर {order_ref} की वर्तमान स्थिति: **{status}**. पता: {address}.",
        "hinglish": "Order {order_ref} abhi **{status}** hai. Address: {address}.",
        "mr": "ऑर्डर {order_ref} सध्या **{status}** आहे. पत्ता: {address}.",
    },
    "order_details": {
        "en": (
            "Order {order_ref}: status **{status}**, total {currency} {total}. "
            "Items: {items}. Address: {address}."
        ),
        "hi": (
            "ऑर्डर {order_ref}: स्थिति **{status}**, कुल {currency} {total}. "
            "आइटम: {items}. पता: {address}."
        ),
        "hinglish": (
            "Order {order_ref}: status **{status}**, total {currency} {total}. "
            "Items: {items}. Address: {address}."
        ),
        "mr": (
            "ऑर्डर {order_ref}: स्थिती **{status}**, एकूण {currency} {total}. "
            "वस्तू: {items}. पत्ता: {address}."
        ),
    },
    "confirm_cancel": {
        "en": "Please confirm: cancel order {order_ref}? This cannot be undone in the demo.",
        "hi": "कृपया पुष्टि करें: ऑर्डर {order_ref} रद्द करें?",
        "hinglish": "Confirm karo: order {order_ref} cancel karna hai?",
        "mr": "कृपया पुष्टी करा: ऑर्डर {order_ref} रद्द करायची?",
    },
    "confirm_address": {
        "en": "Please confirm: change delivery address for {order_ref} to: {address}",
        "hi": "कृपया पुष्टि करें: {order_ref} का नया पता — {address}",
        "hinglish": "Confirm karo: {order_ref} ka naya address — {address}",
        "mr": "कृपया पुष्टी करा: {order_ref} साठी नवीन पत्ता — {address}",
    },
    "cancelled": {
        "en": "Order {order_ref} has been cancelled.",
        "hi": "ऑर्डर {order_ref} रद्द कर दिया गया है।",
        "hinglish": "Order {order_ref} cancel ho gaya.",
        "mr": "ऑर्डर {order_ref} रद्द झाली आहे.",
    },
    "address_updated": {
        "en": "Delivery address for {order_ref} updated to: {address}",
        "hi": "{order_ref} का डिलीवरी पता अपडेट: {address}",
        "hinglish": "{order_ref} ka delivery address update: {address}",
        "mr": "{order_ref} चा डिलिव्हरी पत्ता अद्ययावत: {address}",
    },
    "cancel_eligibility_yes": {
        "en": "Order {order_ref} is eligible to cancel. Reason: {reason}",
        "hi": "ऑर्डर {order_ref} रद्द किया जा सकता है। कारण: {reason}",
        "hinglish": "Order {order_ref} cancel ho sakta hai. Reason: {reason}",
        "mr": "ऑर्डर {order_ref} रद्द करता येईल. कारण: {reason}",
    },
    "cancel_eligibility_no": {
        "en": "Order {order_ref} cannot be cancelled. Reason: {reason}",
        "hi": "ऑर्डर {order_ref} रद्द नहीं हो सकता। कारण: {reason}",
        "hinglish": "Order {order_ref} cancel nahi ho sakta. Reason: {reason}",
        "mr": "ऑर्डर {order_ref} रद्द करता येणार नाही. कारण: {reason}",
    },
    "ticket_created": {
        "en": "Support ticket {ticket_ref} created (status: {status}).",
        "hi": "सपोर्ट टिकट {ticket_ref} बनाया गया (स्थिति: {status}).",
        "hinglish": "Support ticket {ticket_ref} ban gaya (status: {status}).",
        "mr": "सपोर्ट तिकीट {ticket_ref} तयार झाले (स्थिती: {status}).",
    },
    "ticket_status": {
        "en": "Ticket {ticket_ref}: status **{status}**, priority {priority}.",
        "hi": "टिकट {ticket_ref}: स्थिति **{status}**, प्राथमिकता {priority}.",
        "hinglish": "Ticket {ticket_ref}: status **{status}**, priority {priority}.",
        "mr": "तिकीट {ticket_ref}: स्थिती **{status}**, प्राधान्य {priority}.",
    },
    "escalated": {
        "en": (
            "I've queued a human handoff request ({ticket_ref}). "
            "No live agent has joined this portfolio demo chat."
        ),
        "hi": (
            "मानव सहायता अनुरोध कतार में है ({ticket_ref}). "
            "इस पोर्टफोलियो डेमो में कोई लाइव एजेंट शामिल नहीं हुआ।"
        ),
        "hinglish": (
            "Human handoff queue mein aa gaya ({ticket_ref}). "
            "Is portfolio demo mein koi live agent join nahi hua."
        ),
        "mr": (
            "मनुष्य मदत विनंती रांगेत आहे ({ticket_ref}). "
            "या पोर्टफोलिओ डेमोमध्ये कोणताही लाइव्ह एजंट सामील झालेला नाही."
        ),
    },
    "denied": {
        "en": "Okay — that action was not executed.",
        "hi": "ठीक है — वह कार्रवाई निष्पादित नहीं हुई।",
        "hinglish": "Theek hai — action execute nahi hua.",
        "mr": "ठीक आहे — ती क्रिया झाली नाही.",
    },
    "not_found": {
        "en": "I could not find {ref} for your account.",
        "hi": "आपके खाते में {ref} नहीं मिला।",
        "hinglish": "Aapke account mein {ref} nahi mila.",
        "mr": "तुमच्या खात्यात {ref} सापडले नाही.",
    },
    "error": {
        "en": "Something went wrong ({code}). Please try again or ask for a human.",
        "hi": "कुछ गलत हुआ ({code}). फिर कोशिश करें या मानव सहायता माँगें।",
        "hinglish": "Kuch galat ho gaya ({code}). Dobara try karo ya human maango.",
        "mr": "काहीतरी चुकले ({code}). पुन्हा प्रयत्न करा किंवा मनुष्य मदत मागा.",
    },
    "unknown_escalation": {
        "en": (
            "I'm not confident I understood. I've queued escalation ({ticket_ref}). "
            "No live agent has joined this portfolio demo."
        ),
        "hi": (
            "मैं पूरा समझ नहीं पाया। एस्केलेशन कतार में है ({ticket_ref}). लाइव एजेंट इस डेमो में शामिल नहीं है।"
        ),
        "hinglish": (
            "Confidence kam hai. Escalation queue mein hai ({ticket_ref}). "
            "Live agent is demo mein nahi aaya."
        ),
        "mr": ("मला खात्री नाही. एस्केलेशन रांगेत आहे ({ticket_ref}). लाइव्ह एजंट या डेमोमध्ये नाही."),
    },
}
