from .brain import EMAIL_FRAMEWORK, PROFESSIONAL_SYSTEM
from .hf_client import generate_text


PERSONAL_EMAIL_TERMS = (
    "romantic",
    "love",
    "girlfriend",
    "boyfriend",
    "wife",
    "husband",
    "crush",
    "apology",
    "sorry",
    "birthday",
    "friend",
    "family",
    "personal",
)


def _title_preserving_case(text: str) -> str:
    text = text.strip().rstrip(".")
    if not text:
        return "Follow up"
    return f"{text[0].upper()}{text[1:]}"


def _purpose_sentence(purpose: str, offer: str = "") -> str:
    cleaned = purpose.strip().rstrip(".")
    offer = offer.strip().rstrip(".")

    if offer:
        return f"I wanted to share a practical way to {offer}."

    if not cleaned:
        return "I am writing about this matter."

    lowered = f"{cleaned[0].lower()}{cleaned[1:]}"
    action_starters = (
        "ask",
        "confirm",
        "follow",
        "invite",
        "request",
        "schedule",
        "send",
        "share",
        "thank",
    )

    if lowered.startswith(action_starters):
        return f"I would like to {lowered}."

    if lowered.startswith(("sell ", "pitch ", "promote ", "introduce ")):
        return "I wanted to introduce an idea that may be useful for your organization."

    return f"I am writing about {lowered}."


def write_email(
    purpose: str,
    recipient: str = "there",
    tone: str = "professional",
    details: str = "",
    email_type: str = "business",
    audience: str = "",
    offer: str = "",
    call_to_action: str = "",
) -> str:
    purpose = purpose.strip()
    recipient = recipient.strip() or "there"
    tone = tone.strip() or "professional"
    details = details.strip()
    email_type = email_type.strip() or "business"
    audience = audience.strip()
    offer = offer.strip()
    call_to_action = call_to_action.strip()
    combined_request = " ".join((purpose, tone, details, email_type, audience, offer, call_to_action)).lower()
    is_personal = any(term in combined_request for term in PERSONAL_EMAIL_TERMS)

    if is_personal:
        prompt = f"""
Write a sincere, human, copy-ready personal email.

Purpose: {purpose}
Recipient: {recipient}
Tone: {tone}
Important details: {details or "Not specified"}

Rules:
- Sound like a real person, not a corporate assistant.
- No JSON, no tool calls, no strategy notes.
- Do not overdo it or sound fake.
- If names or memories are missing, use tasteful placeholders.
- Return only:
Subject: ...

Hi/Hey ...

...

Personal touch to add: ...
""".strip()

        generated = generate_text(
            prompt,
            system_prompt=PROFESSIONAL_SYSTEM,
            max_new_tokens=650,
            temperature=0.45,
            timeout=75,
        )
        if generated:
            return generated

    prompt = f"""
{EMAIL_FRAMEWORK}

Create a premium, copy-ready {email_type} email.

Purpose: {purpose}
Recipient: {recipient}
Tone: {tone}
Audience profile: {audience or "Not specified"}
Offer/value angle: {offer or "Not specified"}
Call to action: {call_to_action or "Choose the strongest appropriate CTA"}
Important details: {details or "Not specified"}

Return exactly:
COPY-READY EMAIL
Subject: ...

Hi/Hello ...

...

SUBJECT OPTIONS
1. ...
2. ...
3. ...

FOLLOW-UP EMAIL
Subject: ...

...

STRATEGY NOTES
- Why this works: ...
- Best send timing: ...
- Personalization to add: ...

Keep the email concise, polished, and easy to paste. Avoid unnecessary explanation.
""".strip()

    generated = generate_text(
        prompt,
        system_prompt=PROFESSIONAL_SYSTEM,
        max_new_tokens=850,
        temperature=0.38,
        timeout=75,
    )
    if generated:
        return generated

    subject_base = offer if offer and email_type in {"cold outreach", "sales follow-up", "proposal"} else purpose
    detail_line = f"\n\nDetails to include:\n{details}" if details else ""
    value_line = (
        "\n\nFor your team, that can mean faster delivery, fewer repetitive tasks, "
        "and cleaner communication."
        if offer
        else ""
    )
    next_step = call_to_action or "Would you be available for a quick conversation this week?"
    if "thank" in purpose.lower():
        next_step = call_to_action or "Thank you again for your time and support."
    elif "follow" in purpose.lower():
        next_step = call_to_action or "I would appreciate any update when you have a chance."

    return (
        "COPY-READY EMAIL\n"
        f"Subject: {_title_preserving_case(subject_base)}\n\n"
        f"Hi {recipient},\n\n"
        f"I hope you are doing well. {_purpose_sentence(purpose, offer)}"
        f"{value_line}"
        f"{detail_line}\n\n"
        f"{next_step}\n\n"
        "Best regards,\n"
        "GhostMate\n\n"
        "SUBJECT OPTIONS\n"
        f"1. {_title_preserving_case(subject_base)}\n"
        f"2. Quick question about {purpose.lower()}\n"
        f"3. Next step: {purpose.lower()}\n\n"
        "FOLLOW-UP EMAIL\n"
        f"Subject: Following up on {_title_preserving_case(purpose)}\n\n"
        f"Hi {recipient},\n\n"
        f"I wanted to follow up on my earlier note about {purpose.lower()}. "
        "If this is still relevant, I would be glad to move it forward.\n\n"
        f"{next_step}\n\n"
        "Best regards,\n"
        "GhostMate\n\n"
        "STRATEGY NOTES\n"
        "- Why this works: It keeps the ask clear, respectful, and easy to respond to.\n"
        "- Best send timing: Tuesday through Thursday morning is usually strongest for business email.\n"
        "- Personalization to add: Mention a recent project, shared goal, or specific pain point."
    )
