"""Deterministic multilingual response templates for customer-facing support."""

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
            "Hi! I'm VaaniDesk Support. I can help with order status, returns and refunds, "
            "delivery address changes, cancellation checks, and connecting you with support."
        ),
        "hi": (
            "नमस्ते! मैं VaaniDesk Support हूँ। ऑर्डर स्थिति, रिटर्न/रिफंड, डिलीवरी पता बदलना, "
            "रद्दीकरण जाँच, और सपोर्ट कनेक्ट करने में मदद कर सकता हूँ।"
        ),
        "hinglish": (
            "Namaste! Main VaaniDesk Support hoon. Order status, returns/refunds, "
            "delivery address change, cancellation check, aur support connect kar sakta hoon."
        ),
        "mr": (
            "नमस्कार! मी VaaniDesk Support आहे. ऑर्डर स्थिती, रिटर्न/रिफंड, डिलिव्हरी पत्ता बदल, "
            "रद्द तपासणी आणि सपोर्ट कनेक्ट करण्यात मदत करू शकतो."
        ),
    },
    "clarification": {
        "en": "{question}",
        "hi": "{question}",
        "hinglish": "{question}",
        "mr": "{question}",
    },
    "unknown_intent": {
        "en": (
            "I'm not sure I understood that. I can help with orders, returns, delivery "
            "changes, support requests, or connecting you with support."
        ),
        "hi": (
            "मुझे पूरा समझ नहीं आया। मैं ऑर्डर, रिटर्न, डिलीवरी बदलाव, सपोर्ट अनुरोध, "
            "या सपोर्ट से जोड़ने में मदद कर सकता हूँ।"
        ),
        "hinglish": (
            "Main samajh nahi paya. Orders, returns, delivery changes, support requests, "
            "ya support se connect kar sakta hoon."
        ),
        "mr": (
            "मला पूर्ण समजले नाही. ऑर्डर, रिटर्न, डिलिव्हरी बदल, सपोर्ट विनंती "
            "किंवा सपोर्टशी जोडण्यात मदत करू शकतो."
        ),
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
        "en": (
            "You're about to cancel order {order_ref}. "
            "This action may not be reversible once processed."
        ),
        "hi": ("आप ऑर्डर {order_ref} रद्द करने वाले हैं। प्रक्रिया के बाद यह वापस नहीं लिया जा सकता।"),
        "hinglish": (
            "Aap order {order_ref} cancel karne wale ho. Process ke baad yeh reverse nahi hoga."
        ),
        "mr": (
            "तुम्ही ऑर्डर {order_ref} रद्द करणार आहात. प्रक्रिया झाल्यानंतर ही क्रिया परत घेता येणार नाही."
        ),
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
        "en": (
            "I've created support request {ticket_ref} (status: {status}). "
            "A support specialist can review this request. "
            "This demo creates the support ticket, but does not connect to a live support agent."
        ),
        "hi": (
            "सपोर्ट अनुरोध {ticket_ref} बनाया गया (स्थिति: {status}). "
            "एक सपोर्ट विशेषज्ञ इसकी समीक्षा कर सकता है। "
            "यह डेमो टिकट बनाता है, लेकिन लाइव एजेंट से कनेक्ट नहीं करता।"
        ),
        "hinglish": (
            "Support request {ticket_ref} ban gaya (status: {status}). "
            "Support specialist iski review kar sakta hai. "
            "Yeh demo ticket banata hai, lekin live agent se connect nahi karta."
        ),
        "mr": (
            "सपोर्ट विनंती {ticket_ref} तयार झाली (स्थिती: {status}). "
            "सपोर्ट तज्ज्ञ याची समीक्षा करू शकतो. "
            "हा डेमो तिकीट तयार करतो, पण लाइव्ह एजंटशी जोडत नाही."
        ),
    },
    "ticket_status": {
        "en": "Ticket {ticket_ref}: status **{status}**, priority {priority}.",
        "hi": "टिकट {ticket_ref}: स्थिति **{status}**, प्राथमिकता {priority}.",
        "hinglish": "Ticket {ticket_ref}: status **{status}**, priority {priority}.",
        "mr": "तिकीट {ticket_ref}: स्थिती **{status}**, प्राधान्य {priority}.",
    },
    "escalated": {
        "en": (
            "I've created support request {ticket_ref}. "
            "A support specialist can review this request. "
            "This demo creates the support ticket, but does not connect to a live support agent."
        ),
        "hi": (
            "सपोर्ट अनुरोध {ticket_ref} बनाया गया। "
            "एक सपोर्ट विशेषज्ञ इसकी समीक्षा कर सकता है। "
            "यह डेमो टिकट बनाता है, लेकिन लाइव एजेंट से कनेक्ट नहीं करता।"
        ),
        "hinglish": (
            "Support request {ticket_ref} ban gaya. "
            "Support specialist iski review kar sakta hai. "
            "Yeh demo ticket banata hai, lekin live agent se connect nahi karta."
        ),
        "mr": (
            "सपोर्ट विनंती {ticket_ref} तयार झाली. "
            "सपोर्ट तज्ज्ञ याची समीक्षा करू शकतो. "
            "हा डेमो तिकीट तयार करतो, पण लाइव्ह एजंटशी जोडत नाही."
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
        "en": "Something went wrong. Please try again or ask to connect with support.",
        "hi": "कुछ गलत हुआ। फिर कोशिश करें या सपोर्ट से जुड़ने को कहें।",
        "hinglish": "Kuch galat ho gaya. Dobara try karo ya support se connect maango.",
        "mr": "काहीतरी चुकले. पुन्हा प्रयत्न करा किंवा सपोर्टशी जोडण्याची विनंती करा.",
    },
    "unknown_escalation": {
        "en": (
            "I'm not sure I understood that. I've created support request {ticket_ref}. "
            "A support specialist can review this request. "
            "This demo creates the support ticket, but does not connect to a live support agent."
        ),
        "hi": (
            "मुझे पूरा समझ नहीं आया। सपोर्ट अनुरोध {ticket_ref} बनाया गया। "
            "यह डेमो टिकट बनाता है, लेकिन लाइव एजेंट से कनेक्ट नहीं करता।"
        ),
        "hinglish": (
            "Main samajh nahi paya. Support request {ticket_ref} ban gaya. "
            "Yeh demo ticket banata hai, lekin live agent se connect nahi karta."
        ),
        "mr": (
            "मला पूर्ण समजले नाही. सपोर्ट विनंती {ticket_ref} तयार झाली. "
            "हा डेमो तिकीट तयार करतो, पण लाइव्ह एजंटशी जोडत नाही."
        ),
    },
    "policy_answer": {
        "en": "{snippet}",
        "hi": "{snippet}",
        "hinglish": "{snippet}",
        "mr": "{snippet}",
    },
    "policy_answer_cautious": {
        "en": (
            "Based on available policy information (please verify for your specific case): "
            "{snippet}"
        ),
        "hi": "उपलब्ध नीति जानकारी के आधार पर (अपने मामले की पुष्टि करें): {snippet}",
        "hinglish": ("Available policy info ke hisaab se (apne case verify karo): {snippet}"),
        "mr": "उपलब्ध धोरण माहितीनुसार (तुमच्या प्रकरणाची पुष्टी करा): {snippet}",
    },
    "no_answer": {
        "en": (
            "I couldn't find enough reliable policy information to answer that confidently. "
            "I can create a support request so an agent can confirm it for you."
        ),
        "hi": (
            "इस प्रश्न के लिए पर्याप्त विश्वसनीय नीति जानकारी नहीं मिली। "
            "मैं सपोर्ट अनुरोध बना सकता हूँ ताकि एजेंट पुष्टि कर सके।"
        ),
        "hinglish": (
            "Reliable policy info nahi mila. Main support request bana sakta hoon "
            "taaki agent confirm kar sake."
        ),
        "mr": (
            "या प्रश्नासाठी पुरेशी विश्वासार्ह धोरण माहिती सापडली नाही. "
            "मी सपोर्ट विनंती तयार करू शकतो जेणेकरून एजंट पुष्टी करू शकेल."
        ),
    },
    "escalation_offer": {
        "en": "You can ask to connect with support if you still need help.",
        "hi": "आवश्यक हो तो सपोर्ट से जुड़ने का अनुरोध कर सकते हैं।",
        "hinglish": "Zarurat ho to support se connect maang sakte ho.",
        "mr": "गरज असल्यास सपोर्टशी जोडण्याची विनंती करू शकता.",
    },
    "evidence_review_flag": {
        "en": (
            "Note: retrieved evidence included unusual phrasing and was treated as "
            "untrusted reference text only."
        ),
        "hi": "नोट: प्राप्त साक्ष्य में असामान्य वाक्यांश थे; केवल संदर्भ के रूप में उपयोग किया गया।",
        "hinglish": (
            "Note: retrieved evidence mein unusual phrasing thi; sirf reference ke tor pe use hui."
        ),
        "mr": "नोंद: मिळालेल्या पुराव्यात असामान्य शब्द होते; फक्त संदर्भासाठी वापरले.",
    },
}
