@echo off
setlocal
cd /d "%~dp0\.."

if not exist logs mkdir logs

set "PY_EXE=.venv\Scripts\python.exe"
if exist "%PY_EXE%" goto run_bot
set "PY_EXE=python"

:run_bot
echo [dev_discord] using %PY_EXE% >> "logs\discord_dev.log" 2>&1
call "%PY_EXE%" main.py >> "logs\discord_dev.log" 2>&1
exit /b %errorlevel%
