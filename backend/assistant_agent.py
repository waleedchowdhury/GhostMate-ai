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

Return this structure:
EXECUTIVE ANSWER
...

PROFIT / VALUE ANGLE
...

ACTION PLAN
1. ...

ASSETS TO CREATE
- ...

RISKS AND FIXES
- Risk: ...
  Fix: ...

NEXT BEST MOVE
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
        "EXECUTIVE ANSWER\n"
        f"Focus on one commercially useful outcome first: {task or 'the task'}.\n\n"
        "PROFIT / VALUE ANGLE\n"
        "Package the result as a repeatable service, template, or workflow that saves time, increases sales, or improves quality for a clear audience.\n\n"
        "ACTION PLAN\n"
        "1. Define the exact outcome you want.\n"
        "2. Identify who would pay for that outcome and what pain it solves.\n"
        "3. Build one proof sample that looks professional enough to show.\n"
        "4. Turn the proof into a simple offer, price, and delivery process.\n"
        "5. Test it with 10 real prospects and improve from replies.\n\n"
        "ASSETS TO CREATE\n"
        "- One clear offer description.\n"
        "- One before/after sample.\n"
        "- One outreach email.\n"
        "- One delivery checklist.\n\n"
        "RISKS AND FIXES\n"
        "- Risk: The offer is too broad. Fix: Pick one audience and one painful task.\n"
        "- Risk: Output quality varies. Fix: Use structured inputs and review before delivery.\n\n"
        "NEXT BEST MOVE\n"
        "Choose one target customer type and one service outcome, then create a sample result."
    )
