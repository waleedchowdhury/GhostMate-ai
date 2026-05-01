from dataclasses import dataclass


@dataclass
class AgentDecision:
    intent: str
    risk: str
    tools: list[str]
    approval_required: bool
    plan: list[str]


AVAILABLE_TOOLS = {
    "email_writer": "Drafts professional emails and follow-ups. Does not send email.",
    "pdf_memory": "Retrieves relevant chunks from memorized PDFs.",
    "pdf_summarizer": "Creates long-form study summaries from uploaded PDFs.",
    "general_assistant": "Plans, explains, compares, and creates task outputs.",
    "memory": "Uses saved user preferences and past interaction facts.",
    "hitl_guardrail": "Requires user approval for sending, deleting, buying, or external actions.",
}


def classify_intent(message: str, has_document: bool) -> str:
    lowered = message.lower()
    if any(word in lowered for word in ("email", "reply", "inbox", "outreach", "follow-up")):
        return "email"
    if has_document or any(word in lowered for word in ("pdf", "summary", "summarize", "notes", "chapter", "questions")):
        return "pdf_study"
    if any(word in lowered for word in ("plan", "strategy", "profit", "business", "launch")):
        return "planning"
    return "general"


def classify_risk(message: str) -> tuple[str, bool]:
    lowered = message.lower()
    high_risk = (
        "send email",
        "send this",
        "delete",
        "purchase",
        "pay",
        "submit",
        "cancel",
        "password",
        "refund",
        "processed",
        "transfer",
        "charge",
    )
    medium_risk = ("draft", "reply", "client", "customer", "legal", "medical", "financial", "complaint")
    if any(term in lowered for term in high_risk):
        return "high", True
    if any(term in lowered for term in medium_risk):
        return "medium", False
    return "low", False


def decide_agent_path(message: str, has_document: bool) -> AgentDecision:
    intent = classify_intent(message, has_document)
    risk, approval_required = classify_risk(message)
    tools = ["memory", "general_assistant", "hitl_guardrail"]
    if intent == "email":
        tools.insert(0, "email_writer")
    if intent == "pdf_study":
        tools.insert(0, "pdf_memory")
    if "summarize" in message.lower() and has_document:
        tools.append("pdf_summarizer")

    plan = [
        "Perceive the user command and available context.",
        "Select the safest useful tool path.",
        "Use document memory or user memory if relevant.",
        "Produce a direct answer or draft.",
        "Flag anything requiring human approval before external action.",
    ]
    return AgentDecision(intent=intent, risk=risk, tools=tools, approval_required=approval_required, plan=plan)


def build_agent_prompt(
    *,
    message: str,
    mode: str,
    has_document: bool,
    document_instruction: str,
    document_context: str,
    history_text: str,
    long_term_memory: str,
) -> str:
    decision = decide_agent_path(message, has_document)
    approval_line = (
        "This request may require user approval before any external action. Do not claim you completed external actions."
        if decision.approval_required
        else "No external action is allowed unless the user explicitly approves it."
    )

    return f"""
You are GhostMate AI, an interactive professional agent.
Behave like a capable assistant inside a messenger conversation.

Private context, do not mention:
- User intent: {decision.intent}
- Risk level: {decision.risk}
- Approval required before external action: {decision.approval_required}
- Safety rule: {approval_line}

Human-in-the-loop rule for your behavior:
{approval_line}

Mode: {mode}

Long-term memory:
{long_term_memory or "No saved long-term memory yet."}

Recent conversation:
{history_text or "No previous messages."}

{document_instruction}
Retrieved PDF context:
{document_context or "None"}

User command:
{message}

Response rules:
- Start with the useful answer immediately.
- Use a natural, human messenger style. Be warm when the request is personal, romantic, supportive, or emotional.
- Stay professional and compact for business, study, PDF, or task requests.
- For PDF questions, answer like a tutor: explain the idea, why it matters, and what the student should remember.
- For assistant questions, answer like a practical collaborator: direct, thoughtful, and action-focused.
- Use clean readable sections with short headings, bullets, and numbered steps.
- Avoid long walls of text. Keep normal answers under about 350 words unless the user asks for deep detail.
- If the answer is complex, give a brief summary first, then a short action list.
- If the user asks for a sheet/table/spreadsheet, return a clean Markdown table.
- If the user asks for email, write the email directly. Do not wrap it in JSON. Do not say you selected an email tool.
- For romantic/personal emails, provide a sincere copy-ready message with a subject and body only, plus one optional personalization note.
- For refunds, payments, cancellations, legal, medical, or account actions, never state that the action has happened unless the user explicitly says it has happened.
- Use safe draft language such as "we can review", "we can process if eligible", or "I can help you with the next step" when facts are missing.
- If the user asks about a PDF, cite page ranges when available.
- Do not sound like a system report. Avoid labels such as "Agent decision", "Execution plan", "Document processing report", or "Tool used".
- If a task needs an external integration that is not connected, say what integration is needed and provide the next safe step.
- Do not pretend to send emails, monitor inboxes, update CRMs, or access calendars unless a real integration exists.
- Never output tool calls, JSON objects, "arguments", or hidden implementation details.
- Never begin with "Drafting..." or "Using...". Just answer naturally.
- For business/task answers, end with one short useful next command the user can send.
- For personal or romantic writing, end naturally. Do not add a robotic next-step instruction unless the user asks for edits.
""".strip()
