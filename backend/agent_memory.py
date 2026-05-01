import json
import re
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
MEMORY_FILE = DATA_DIR / "agent_memory.json"


def _load_memory() -> dict:
    if not MEMORY_FILE.exists():
        return {"facts": [], "interactions": []}
    try:
        return json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"facts": [], "interactions": []}


def _save_memory(memory: dict) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    MEMORY_FILE.write_text(json.dumps(memory, indent=2), encoding="utf-8")


def remember_fact(text: str) -> None:
    cleaned = text.strip()
    if not cleaned:
        return
    memory = _load_memory()
    facts = memory.setdefault("facts", [])
    if cleaned not in facts:
        facts.append(cleaned)
    memory["facts"] = facts[-80:]
    _save_memory(memory)


def record_interaction(user_message: str, assistant_message: str) -> None:
    memory = _load_memory()
    interactions = memory.setdefault("interactions", [])
    interactions.append(
        {
            "at": time.time(),
            "user": user_message[:1200],
            "assistant": assistant_message[:1600],
        }
    )
    memory["interactions"] = interactions[-80:]

    # Lightweight explicit memory command. Example: "remember: I prefer short formal emails".
    match = re.search(r"remember\s*:\s*(.+)", user_message, re.IGNORECASE | re.DOTALL)
    if match:
        remember_fact(match.group(1).strip())
    else:
        _save_memory(memory)


def memory_context(limit: int = 8) -> str:
    memory = _load_memory()
    facts = memory.get("facts", [])[-limit:]
    interactions = memory.get("interactions", [])[-4:]
    lines = []
    if facts:
        lines.append("Long-term user memory:")
        lines.extend(f"- {fact}" for fact in facts)
    if interactions:
        lines.append("Recent long-term interaction summary:")
        for item in interactions:
            lines.append(f"- User: {item.get('user', '')[:220]}")
            lines.append(f"  Assistant: {item.get('assistant', '')[:220]}")
    return "\n".join(lines)
