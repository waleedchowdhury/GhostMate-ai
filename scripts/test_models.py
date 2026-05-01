import os
import time

import requests
from dotenv import load_dotenv


load_dotenv(".env")

TOKEN = os.getenv("HF_API_TOKEN", "")
ROUTER_URL = os.getenv("HF_ROUTER_URL", "https://router.huggingface.co/v1/chat/completions")

MODELS = [
    "openai/gpt-oss-120b",
    "zai-org/GLM-4.5",
    "deepseek-ai/DeepSeek-R1",
    "Qwen/Qwen2.5-7B-Instruct-1M",
]

SYSTEM = (
    "You are a senior business communication strategist. "
    "Write polished, concise, commercially useful emails."
)

PROMPT = (
    "Write a premium cold outreach email to a clinic owner offering an AI assistant "
    "that reduces manual patient follow-up email writing. Include a subject line, "
    "clear value, and a 15-minute demo CTA. Keep it under 170 words."
)


def test_model(model: str) -> dict[str, str | float | int]:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": PROMPT},
        ],
        "max_tokens": 260,
        "temperature": 0.25,
        "top_p": 0.9,
    }
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
    }
    start = time.perf_counter()
    response = requests.post(ROUTER_URL, headers=headers, json=payload, timeout=90)
    latency = round(time.perf_counter() - start, 2)

    if not response.ok:
        return {
            "model": model,
            "status": response.status_code,
            "latency": latency,
            "preview": response.text[:350],
        }

    data = response.json()
    message = data.get("choices", [{}])[0].get("message", {})
    content = message.get("content") or message.get("reasoning_content") or str(message)
    content = content.strip()
    return {
        "model": model,
        "status": response.status_code,
        "latency": latency,
        "preview": content[:500].replace("\n", "\\n").encode("ascii", "replace").decode("ascii"),
    }


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("HF_API_TOKEN is missing.")

    for model_name in MODELS:
        result = test_model(model_name)
        print(f"MODEL: {result['model']}")
        print(f"STATUS: {result['status']} | LATENCY: {result['latency']}s")
        print(f"PREVIEW: {result['preview']}")
        print("-" * 72)
