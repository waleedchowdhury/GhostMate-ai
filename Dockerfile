FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY frontend ./frontend

ENV HF_API_MODE=router
ENV HF_TEXT_MODEL=openai/gpt-oss-120b
ENV HF_ROUTER_URL=https://router.huggingface.co/v1/chat/completions

CMD python -m uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-7860}
