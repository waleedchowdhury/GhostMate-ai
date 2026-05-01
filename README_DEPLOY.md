# GhostMate AI Deployment

## Best free option: Render

1. Push this project to a private GitHub repository.
2. Go to Render and create a new Web Service from that repo.
3. Use:
   - Build command: `pip install -r requirements.txt`
   - Start command: `python -m uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
4. Add environment variables in Render:
   - `HF_API_TOKEN`
   - `HF_API_MODE=router`
   - `HF_TEXT_MODEL=openai/gpt-oss-120b`
   - `HF_ROUTER_URL=https://router.huggingface.co/v1/chat/completions`
5. Deploy.

## Alternative free option: Hugging Face Spaces

1. Create a new Space.
2. Choose Docker as the SDK.
3. Upload this project with the included `Dockerfile`.
4. Add `HF_API_TOKEN` as a Space secret.
5. The Dockerfile uses port `7860` by default.

## Important security

Do not upload `.env`. It contains your private token and is ignored by `.gitignore`.

Because this project currently stores chat/PDF memory locally, memory may reset when a free server sleeps or restarts. For a public product, add a database later.
