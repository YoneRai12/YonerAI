@echo off
echo Starting ORA Discord Bot and Web API...

:: Install dependencies to ensure everything works
echo Installing/Updating dependencies...
call .venv\Scripts\activate && pip install -r requirements.txt

:: Start Bot in a new window (with venv activation)
start "ORA Discord Bot (Launcher)" cmd /k "call .venv\Scripts\activate && python launcher.py"

:: Start Web API in a new window (with venv activation)
start "ORA Web API" cmd /k "call .venv\Scripts\activate && uvicorn src.web.app:app --reload --port 8000"

:: Start Ngrok in a new window
start "Ngrok Tunnel" cmd /k "ngrok http 8000"

echo Done! Check the new windows for logs.
