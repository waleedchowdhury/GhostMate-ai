from .brain import ASSISTANT_FRAMEWORK, PROFESSIONAL_SYSTEM
from .hf_client import generate_text


def _intent_hint(task: str) -> str:
    lowered = task.lower()
    if any(word in lowered for word in ("email", "message", "reply")):
        return "The user likely needs communication help. Offer a draft or structure."
    if any(word in lowered for word in ("plan", "schedule", "roadmap", "steps")):
        return "The user likely needs planning help. Break the work into ordered actions."
    if any(word in lowered for word in ("decide", "choose", "compare")):
        return "The user likely needs decision support. Compare options and recommend one."
    if any(word in lowered for word in ("study", "learn", "explain")):
        return "The user likely needs learning support. Explain clearly and include practice steps."
    return "The user needs general task assistance. Be practical and concise."


def run_assistant(task: str, context: str = "", mode: str = "business") -> str:
    task = task.strip()
    context = context.strip()
    mode = mode.strip() or "business"
    prompt = f"""
{ASSISTANT_FRAMEWORK}

Intent hint: {_intent_hint(task)}
Mode: {mode}

User task:
{task}

Extra context:
{context or "Not specified"}

Answer like a smart human collaborator in a chat.
Keep it concise unless the task explicitly asks for depth.
Do not use robotic labels or corporate report language.

Use this natural shape:
Quick take
...

What I would do
1. ...

Watch out for
- ...

Next move
...
""".strip()

    generated = generate_text(
        prompt,
        system_prompt=PROFESSIONAL_SYSTEM,
        max_new_tokens=850,
        temperature=0.35,
        timeout=75,
    )
    if generated:
        return generated

    return (
        "Quick take\n"
        f"I would focus on one commercially useful outcome first: {task or 'the task'}.\n\n"
        "What I would do\n"
        "1. Define the exact outcome you want.\n"
        "2. Identify who would pay for that outcome and what pain it solves.\n"
        "3. Build one proof sample that looks professional enough to show.\n"
        "4. Turn the proof into a simple offer, price, and delivery process.\n"
        "5. Test it with a small group of real prospects and improve from replies.\n\n"
        "Watch out for\n"
        "- If the offer is too broad, pick one audience and one painful task.\n"
        "- If output quality varies, use structured inputs and review before delivery.\n\n"
        "Next move\n"
        "Choose one target customer type and one service outcome, then create a sample result."
    )
