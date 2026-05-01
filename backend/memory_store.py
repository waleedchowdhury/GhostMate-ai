import re
import time
import uuid
from dataclasses import dataclass, field

from .pdf_agent import PageText, TextChunk, _chunk_pages, extract_pdf_pages


@dataclass
class DocumentMemory:
    id: str
    filename: str
    pages: list[PageText]
    chunks: list[TextChunk]
    quick_summary: str
    created_at: float = field(default_factory=time.time)


DOCUMENTS: dict[str, DocumentMemory] = {}
CONVERSATIONS: dict[str, list[dict[str, str]]] = {}


def _keywords(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Z0-9]{4,}", text.lower())
    stop_words = {
        "that",
        "this",
        "with",
        "from",
        "have",
        "what",
        "when",
        "where",
        "which",
        "there",
        "their",
        "about",
        "would",
        "should",
        "could",
    }
    return {word for word in words if word not in stop_words}


def _quick_summary(pages: list[PageText]) -> str:
    text = " ".join(page.text for page in pages[:8])
    sentences = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text).strip())
    picked = []
    seen = set()
    for sentence in sentences:
        normalized = sentence.lower().strip()
        if len(sentence) > 45 and normalized not in seen:
            picked.append(sentence.strip())
            seen.add(normalized)
        if len(picked) >= 5:
            break
    if not picked:
        return "I have the PDF in memory now. Ask me for a summary, study notes, questions, or a simple explanation."
    return "I have the PDF in memory now. Here is a quick first look:\n" + "\n".join(f"- {sentence}" for sentence in picked)


def create_document_memory(pdf_bytes: bytes, filename: str) -> DocumentMemory:
    pages = extract_pdf_pages(pdf_bytes)
    if not pages:
        raise ValueError("I could not find readable text in this PDF. It may be scanned images instead of selectable text.")

    chunks = _chunk_pages(pages, max_chars=7000, max_pages=8)
    document = DocumentMemory(
        id=str(uuid.uuid4()),
        filename=filename or "uploaded.pdf",
        pages=pages,
        chunks=chunks,
        quick_summary=_quick_summary(pages),
    )
    DOCUMENTS[document.id] = document
    return document


def get_document(document_id: str) -> DocumentMemory | None:
    return DOCUMENTS.get(document_id)


def retrieve_context(document_id: str, query: str, max_chunks: int = 5) -> str:
    document = get_document(document_id)
    if not document:
        return ""

    query_terms = _keywords(query)
    scored: list[tuple[int, TextChunk]] = []
    for chunk in document.chunks:
        chunk_terms = _keywords(chunk.text)
        score = len(query_terms & chunk_terms)
        if any(word in query.lower() for word in ("summary", "summarize", "notes", "overview", "chapter")):
            score += max(0, 3 - len(scored))
        scored.append((score, chunk))

    scored.sort(key=lambda item: item[0], reverse=True)
    selected = [chunk for score, chunk in scored[:max_chunks] if score > 0]
    if not selected:
        selected = document.chunks[: min(max_chunks, len(document.chunks))]

    return "\n\n".join(
        f"[Pages {chunk.start_page}-{chunk.end_page}]\n{chunk.text[:4500]}" for chunk in selected
    )


def get_conversation(conversation_id: str) -> list[dict[str, str]]:
    return CONVERSATIONS.setdefault(conversation_id, [])


def add_message(conversation_id: str, role: str, content: str) -> None:
    history = get_conversation(conversation_id)
    history.append({"role": role, "content": content})
    if len(history) > 16:
        del history[:-16]
