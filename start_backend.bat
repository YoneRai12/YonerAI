@echo off
echo Starting ORA Web Backend API...
echo Host: 127.0.0.1
echo Port: 8000

call .venv\Scripts\activate.bat
uvicorn src.web.app:app --host 127.0.0.1 --port 8000 --reload

pause
