@echo off
cd /d "%~dp0"
echo Starting GhostMate AI at http://127.0.0.1:8000
"C:\Users\KHAN GADGET\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
pause
