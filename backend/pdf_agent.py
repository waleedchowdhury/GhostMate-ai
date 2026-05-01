import io
import re
from dataclasses import dataclass

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from .brain import PDF_FRAMEWORK, PROFESSIONAL_SYSTEM
from .hf_client import generate_text


@dataclass
class PageText:
    page: int
    text: str


@dataclass
class TextChunk:
    start_page: int
    end_page: int
    text: str


TARGET_LENGTHS = {
    "short": {"label": "about half a page", "tokens": 900},
    "standard": {"label": "about one to two pages", "tokens": 1700},
    "deep": {"label": "detailed university notes, about three to five pages", "tokens": 2800},
    "exam": {"label": "exam-prep study guide with questions", "tokens": 2600},
}


def extract_pdf_pages(pdf_bytes: bytes) -> list[PageText]:
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
    except PdfReadError as exc:
        raise ValueError("This PDF could not be read. It may be encrypted or damaged.") from exc

    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as exc:
            raise ValueError("This PDF is encrypted and could not be opened.") from exc

    pages: list[PageText] = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""

        clean_text = re.sub(r"\s+", " ", text).strip()
        if clean_text:
            pages.append(PageText(page=index, text=clean_text))

    return pages


def extract_pdf_text(pdf_bytes: bytes) -> str:
    return "\n".join(page.text for page in extract_pdf_pages(pdf_bytes)).strip()


def _chunk_pages(
    pages: list[PageText],
    *,
    max_chars: int = 8500,
    max_pages: int = 10,
) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    current: list[PageText] = []
    current_chars = 0

    for page in pages:
        would_exceed_chars = current_chars + len(page.text) > max_chars
        would_exceed_pages = len(current) >= max_pages
        if current and (would_exceed_chars or would_exceed_pages):
            chunks.append(
                TextChunk(
                    start_page=current[0].page,
                    end_page=current[-1].page,
                    text="\n".join(f"[Page {item.page}] {item.text}" for item in current),
                )
            )
            current = []
            current_chars = 0

        current.append(page)
        current_chars += len(page.text)

    if current:
        chunks.append(
            TextChunk(
                start_page=current[0].page,
                end_page=current[-1].page,
                text="\n".join(f"[Page {item.page}] {item.text}" for item in current),
            )
        )

    return chunks


def _fallback_summary_from_pages(pages: list[PageText], target_length: str) -> str:
    compact_text = " ".join(page.text for page in pages)
    compact_text = re.sub(r"\s+", " ", compact_text).strip()
    if not compact_text:
        return "I could not find readable text in this PDF."

    sentence_limit = 14 if target_length in {"deep", "exam"} else 8
    sentences = re.split(r"(?<=[.!?])\s+", compact_text)
    key_sentences = []
    seen = set()
    for sentence in sentences:
        normalized = sentence.strip().lower()
        if len(sentence) > 45 and normalized not in seen:
            seen.add(normalized)
            key_sentences.append(sentence)
        if len(key_sentences) >= sentence_limit:
            break
    if not key_sentences:
        key_sentences = sentences[:sentence_limit]

    bullets = "\n".join(f"- {sentence.strip()}" for sentence in key_sentences if sentence.strip())
    return (
        "STUDY SUMMARY\n"
        f"{bullets}\n\n"
        "KEY WARNING\n"
        "- This local fallback is extractive. For stronger human-style notes, use the Hugging Face model connection.\n\n"
        "HOW TO STUDY THIS\n"
        "- Turn each bullet into a question.\n"
        "- Re-read the original pages for definitions, formulas, dates, and examples.\n"
        "- Make a one-page revision sheet from the most repeated ideas."
    )


def _summarize_chunk(
    chunk: TextChunk,
    *,
    summary_mode: str,
    detail_level: str,
    focus: str,
) -> str:
    prompt = f"""
{PDF_FRAMEWORK}

You are summarizing pages {chunk.start_page}-{chunk.end_page} for university students.
The goal is not a tiny abstract. Create dense, useful study notes that preserve meaning.

Summary mode: {summary_mode}
Detail level: {detail_level}
Student focus: {focus or "general understanding, assignment writing, and exam revision"}

For this page range, return:
PAGE RANGE
Pages {chunk.start_page}-{chunk.end_page}

CORE IDEAS
- ...

IMPORTANT DETAILS
- ...

TERMS / DEFINITIONS
- ...

EXAMPLES OR EVIDENCE
- ...

POSSIBLE EXAM OR ASSIGNMENT POINTS
- ...

TEXT:
{chunk.text}
""".strip()

    generated = generate_text(
        prompt,
        system_prompt=PROFESSIONAL_SYSTEM,
        max_new_tokens=850,
        temperature=0.18,
        timeout=100,
    )

    if generated:
        return generated

    return _fallback_summary_from_pages([PageText(chunk.start_page, chunk.text)], "short")


def _merge_summaries(
    summaries: list[str],
    *,
    pass_name: str,
    summary_mode: str,
    target_length: str,
    detail_level: str,
    focus: str,
) -> str:
    target = TARGET_LENGTHS.get(target_length, TARGET_LENGTHS["standard"])
    prompt = f"""
You are GhostMate AI, a human-style academic study assistant.
Merge the notes below into a coherent, high-quality student summary.

Pass: {pass_name}
Mode: {summary_mode}
Target length: {target["label"]}
Detail level: {detail_level}
Focus: {focus or "university notes, assignments, exam preparation"}

Write naturally, like a strong student tutor explaining the material.
Do not be vague. Preserve the important arguments, concepts, examples, and relationships.
If the source does not contain a fact, do not invent it.

Return:
TITLE

HUMAN-STYLE OVERVIEW

MAIN IDEAS

DETAILED STUDY NOTES

KEY TERMS AND DEFINITIONS

ASSIGNMENT / ESSAY ANGLES

EXAM QUESTIONS WITH SHORT ANSWERS

MEMORY CHECKLIST

SOURCE LIMITATIONS

NOTES TO MERGE:
{chr(10).join(summaries)}
""".strip()

    generated = generate_text(
        prompt,
        system_prompt=PROFESSIONAL_SYSTEM,
        max_new_tokens=target["tokens"],
        temperature=0.2,
        timeout=120,
    )

    return generated or "\n\n".join(summaries)


def summarize_pdf(
    pdf_bytes: bytes,
    *,
    summary_mode: str = "university study notes",
    target_length: str = "standard",
    detail_level: str = "advanced",
    focus: str = "",
) -> str:
    pages = extract_pdf_pages(pdf_bytes)
    if not pages:
        return "I could not find readable text in this PDF. It may be scanned images instead of selectable text."

    chunks = _chunk_pages(pages)
    partial_summaries: list[str] = []

    # This is designed for long books. It processes all chunks, but keeps each model call bounded.
    for chunk in chunks:
        partial_summaries.append(
            _summarize_chunk(
                chunk,
                summary_mode=summary_mode,
                detail_level=detail_level,
                focus=focus,
            )
        )

    if not partial_summaries:
        return _fallback_summary_from_pages(pages, target_length)

    batch_summaries: list[str] = []
    batch_size = 8
    for index in range(0, len(partial_summaries), batch_size):
        batch = partial_summaries[index : index + batch_size]
        batch_summaries.append(
            _merge_summaries(
                batch,
                pass_name=f"section synthesis {index // batch_size + 1}",
                summary_mode=summary_mode,
                target_length="short",
                detail_level=detail_level,
                focus=focus,
            )
        )

    final_summary = _merge_summaries(
        batch_summaries,
        pass_name="final synthesis",
        summary_mode=summary_mode,
        target_length=target_length,
        detail_level=detail_level,
        focus=focus,
    )

    stats = (
        "DOCUMENT PROCESSING REPORT\n"
        f"- Readable pages: {len(pages)}\n"
        f"- Analysis chunks: {len(chunks)}\n"
        f"- Summary mode: {summary_mode}\n"
        f"- Target length: {TARGET_LENGTHS.get(target_length, TARGET_LENGTHS['standard'])['label']}\n\n"
    )
    return f"{stats}{final_summary}"
