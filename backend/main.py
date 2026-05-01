from pathlib import Path
import uuid

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .assistant_agent import run_assistant
from .agent_core import build_agent_prompt
from .agent_memory import memory_context, record_interaction
from .brain import PROFESSIONAL_SYSTEM
from .email_agent import write_email
from .hf_client import model_status, stream_text
from .memory_store import add_message, create_document_memory, get_conversation, get_document, retrieve_context
from .pdf_agent import summarize_pdf


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = PROJECT_ROOT / "frontend"

app = FastAPI(
    title="GhostMate AI",
    description="AI agent project for emails, PDF summaries, and general tasks.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


class EmailRequest(BaseModel):
    purpose: str = Field(..., min_length=2)
    recipient: str = "there"
    tone: str = "professional"
    details: str = ""
    email_type: str = "business"
    audience: str = ""
    offer: str = ""
    call_to_action: str = ""


class AssistantRequest(BaseModel):
    task: str = Field(..., min_length=2)
    context: str = ""
    mode: str = "business"


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    conversation_id: str = ""
    document_id: str = ""
    mode: str = "study"


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/style.css")
def style_css() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "style.css")


@app.get("/script.js")
def script_js() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "script.js")


@app.get("/bootstrap.local.css")
def bootstrap_local_css() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "bootstrap.local.css")


@app.get("/index.html")
def index_html() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/health")
def health_check() -> dict[str, str | bool | dict[str, str | bool]]:
    return {"status": "ok", "app": "GhostMate AI", "ai": model_status()}


@app.post("/api/email")
def create_email(request: EmailRequest) -> dict[str, str]:
    result = write_email(
        purpose=request.purpose,
        recipient=request.recipient,
        tone=request.tone,
        details=request.details,
        email_type=request.email_type,
        audience=request.audience,
        offer=request.offer,
        call_to_action=request.call_to_action,
    )
    return {"result": result}


@app.post("/api/pdf-memory")
async def memorize_pdf(file: UploadFile = File(...)) -> dict[str, str | int]:
    filename = file.filename or ""
    allowed_content_types = {"application/pdf", "application/octet-stream", ""}
    if file.content_type not in allowed_content_types and not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file.")

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    try:
        document = create_document_memory(pdf_bytes, filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "document_id": document.id,
        "filename": document.filename,
        "readable_pages": len(document.pages),
        "chunks": len(document.chunks),
        "quick_summary": document.quick_summary,
    }


@app.post("/api/pdf-summary")
async def create_pdf_summary(
    file: UploadFile = File(...),
    summary_mode: str = Form("university study notes"),
    target_length: str = Form("standard"),
    detail_level: str = Form("advanced"),
    focus: str = Form(""),
) -> dict[str, str]:
    filename = file.filename or ""
    allowed_content_types = {"application/pdf", "application/octet-stream", ""}
    if file.content_type not in allowed_content_types and not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file.")

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    try:
        result = summarize_pdf(
            pdf_bytes,
            summary_mode=summary_mode,
            target_length=target_length,
            detail_level=detail_level,
            focus=focus,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"result": result}


@app.post("/api/assistant")
def assistant(request: AssistantRequest) -> dict[str, str]:
    result = run_assistant(request.task, request.context, request.mode)
    return {"result": result}


@app.post("/api/chat/stream")
def stream_chat(request: ChatRequest) -> StreamingResponse:
    conversation_id = request.conversation_id.strip() or str(uuid.uuid4())
    message = request.message.strip()
    document = get_document(request.document_id.strip()) if request.document_id.strip() else None
    document_context = retrieve_context(request.document_id, message) if document else ""
    history = get_conversation(conversation_id)[-8:]
    history_text = "\n".join(f"{item['role']}: {item['content']}" for item in history)

    document_instruction = (
        f"Current PDF: {document.filename}\nUse the retrieved PDF context below. Cite page ranges when possible.\n"
        if document
        else "No PDF is attached to this message.\n"
    )
    prompt = build_agent_prompt(
        message=message,
        mode=request.mode,
        has_document=bool(document),
        document_instruction=document_instruction,
        document_context=document_context,
        history_text=history_text,
        long_term_memory=memory_context(),
    )

    def generator():
        add_message(conversation_id, "user", message)
        full_response = []
        yield f"[conversation_id:{conversation_id}]\n"
        for chunk in stream_text(
            prompt,
            system_prompt=PROFESSIONAL_SYSTEM,
            max_new_tokens=950,
            temperature=0.22,
            timeout=120,
        ):
            full_response.append(chunk)
            yield chunk
        assistant_message = "".join(full_response).strip()
        add_message(conversation_id, "assistant", assistant_message)
        record_interaction(message, assistant_message)

    return StreamingResponse(generator(), media_type="text/plain")
