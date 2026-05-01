import os
import json
import re
from pathlib import Path
from typing import Any, Iterable, Optional

import requests
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

DEFAULT_MODEL = "mistralai/Mistral-7B-Instruct-v0.2"
DEFAULT_CHAT_MODEL = "openai/gpt-oss-120b"
DEFAULT_ROUTER_URL = "https://router.huggingface.co/v1/chat/completions"


def model_status() -> dict[str, str | bool]:
    token = os.getenv("HF_API_TOKEN", "").strip()
    mode = os.getenv("HF_API_MODE", "router").strip().lower()
    default_model = DEFAULT_CHAT_MODEL if mode == "router" else DEFAULT_MODEL
    model = os.getenv("HF_TEXT_MODEL", default_model).strip() or default_model
    return {
        "provider": "Hugging Face",
        "model": model,
        "configured": bool(token),
        "mode": "huggingface-router" if token and mode == "router" else "huggingface-legacy" if token else "local-fallback",
        "api_mode": mode,
    }


def _extract_text(data: Any) -> Optional[str]:
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict):
            return first.get("generated_text") or first.get("summary_text")

    if isinstance(data, dict):
        return data.get("generated_text") or data.get("summary_text")

    return None


def _format_prompt(prompt: str, system_prompt: str = "") -> str:
    model = os.getenv("HF_TEXT_MODEL", DEFAULT_MODEL).lower()
    system = system_prompt.strip()
    user = prompt.strip()

    if "mistral" in model or "mixtral" in model:
        if system:
            return f"<s>[INST] {system}\n\n{user} [/INST]"
        return f"<s>[INST] {user} [/INST]"

    if system:
        return f"System:\n{system}\n\nUser:\n{user}\n\nAssistant:"

    return user


def _clean_generation(text: str) -> str:
    cleaned = text.strip()
    for marker in ("[/INST]", "Assistant:", "ASSISTANT:", "<|assistant|>"):
        if marker in cleaned:
            cleaned = cleaned.split(marker, 1)[-1].strip()
    return clean_model_output(cleaned)


def clean_model_output(text: str) -> str:
    cleaned = _normalize_text(text).strip()
    cleaned = re.sub(
        r"\{\s*\"tool\"\s*:\s*\"[^\"]+\"\s*,\s*\"arguments\"\s*:\s*\{.*?\}\s*\}",
        "",
        cleaned,
        flags=re.DOTALL,
    )
    cleaned = re.sub(
        r"^\s*(Drafting|Using|Calling|Running)\b[^\n]*(?:\n|$)",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = cleaned.replace("```json", "").replace("```", "")
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip().strip('"')


def _normalize_text(text: str) -> str:
    replacements = {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u202f": " ",
        "\u00a0": " ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def _generate_with_router(
    prompt: str,
    *,
    system_prompt: str = "",
    max_new_tokens: int = 500,
    temperature: float = 0.4,
    timeout: int = 60,
) -> Optional[str]:
    token = os.getenv("HF_API_TOKEN", "").strip()
    if not token:
        return None

    status = model_status()
    url = os.getenv("HF_ROUTER_URL", DEFAULT_ROUTER_URL).strip() or DEFAULT_ROUTER_URL
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    messages = []
    if system_prompt.strip():
        messages.append({"role": "system", "content": system_prompt.strip()})
    messages.append({"role": "user", "content": prompt.strip()})

    payload = {
        "model": status["model"],
        "messages": messages,
        "max_tokens": max_new_tokens,
        "temperature": temperature,
        "top_p": 0.92,
    }

    for _ in range(2):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            choices = data.get("choices", [])
            if choices:
                message = choices[0].get("message", {})
                content = message.get("content")
                if content and content.strip():
                    return _clean_generation(content)
        except (requests.RequestException, ValueError, AttributeError):
            continue

    return None


def _generate_with_legacy_text_generation(
    prompt: str,
    *,
    system_prompt: str = "",
    max_new_tokens: int = 500,
    temperature: float = 0.4,
    timeout: int = 60,
) -> Optional[str]:
    status = model_status()
    token = os.getenv("HF_API_TOKEN", "").strip()
    if not token:
        return None

    url = f"https://api-inference.huggingface.co/models/{status['model']}"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "inputs": _format_prompt(prompt, system_prompt),
        "parameters": {
            "max_new_tokens": max_new_tokens,
            "temperature": temperature,
            "top_p": 0.92,
            "repetition_penalty": 1.08,
            "return_full_text": False,
        },
        "options": {
            "wait_for_model": True,
            "use_cache": True,
        },
    }

    generated = None
    for _ in range(2):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=timeout)
            response.raise_for_status()
            generated = _extract_text(response.json())
            break
        except (requests.RequestException, ValueError):
            generated = None

    if not generated:
        return None

    return _clean_generation(generated)


def generate_text(
    prompt: str,
    *,
    system_prompt: str = "",
    max_new_tokens: int = 500,
    temperature: float = 0.4,
    timeout: int = 60,
) -> Optional[str]:
    mode = os.getenv("HF_API_MODE", "router").strip().lower()
    if mode == "router":
        generated = _generate_with_router(
            prompt,
            system_prompt=system_prompt,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            timeout=timeout,
        )
        if generated:
            return generated

    return _generate_with_legacy_text_generation(
        prompt,
        system_prompt=system_prompt,
        max_new_tokens=max_new_tokens,
        temperature=temperature,
        timeout=timeout,
    )


def stream_text(
    prompt: str,
    *,
    system_prompt: str = "",
    max_new_tokens: int = 700,
    temperature: float = 0.35,
    timeout: int = 90,
) -> Iterable[str]:
    mode = os.getenv("HF_API_MODE", "router").strip().lower()
    token = os.getenv("HF_API_TOKEN", "").strip()
    if mode == "router" and token:
        yield from _stream_with_router(
            prompt,
            system_prompt=system_prompt,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            timeout=timeout,
        )
        return

    generated = generate_text(
        prompt,
        system_prompt=system_prompt,
        max_new_tokens=max_new_tokens,
        temperature=temperature,
        timeout=timeout,
    )
    if generated:
        for word in generated.split(" "):
            yield f"{word} "
    else:
        yield "I could not reach the model right now. Please try again in a moment."


def _stream_with_router(
    prompt: str,
    *,
    system_prompt: str = "",
    max_new_tokens: int = 700,
    temperature: float = 0.35,
    timeout: int = 90,
) -> Iterable[str]:
    token = os.getenv("HF_API_TOKEN", "").strip()
    status = model_status()
    url = os.getenv("HF_ROUTER_URL", DEFAULT_ROUTER_URL).strip() or DEFAULT_ROUTER_URL
    messages = []
    if system_prompt.strip():
        messages.append({"role": "system", "content": system_prompt.strip()})
    messages.append({"role": "user", "content": prompt.strip()})

    payload = {
        "model": status["model"],
        "messages": messages,
        "max_tokens": max_new_tokens,
        "temperature": temperature,
        "top_p": 0.9,
        "stream": True,
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    try:
        with requests.post(url, headers=headers, json=payload, timeout=timeout, stream=True) as response:
            response.raise_for_status()
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                if line.startswith("data: "):
                    line = line[6:]
                if line.strip() == "[DONE]":
                    break
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                choices = data.get("choices", [])
                if not choices:
                    continue
                delta = choices[0].get("delta", {})
                content = delta.get("content")
                if content:
                    yield _normalize_text(content)
    except requests.RequestException:
        generated = generate_text(
            prompt,
            system_prompt=system_prompt,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            timeout=timeout,
        )
        if generated:
            for word in generated.split(" "):
                yield f"{word} "
        else:
            yield "I could not reach the model right now. Please try again in a moment."
