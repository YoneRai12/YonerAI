@echo off
echo Starting ORA Services...
echo ============================
echo [1] Voice Engine (Aratako TTS) -> Port 8002
echo ============================

start "Voice Engine (Port 8002)" cmd /k "python src/services/voice_server.py"

echo Voice Engine launched! Main Bot can now be started.
pause

