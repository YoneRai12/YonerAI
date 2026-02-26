@echo off
setlocal
cd /d "%~dp0\.."

if not exist logs mkdir logs

set "PY_EXE=.venv\Scripts\python.exe"
if exist "%PY_EXE%" goto run_api
set "PY_EXE=python"

:run_api
echo [dev_api] using %PY_EXE% >> "logs\api_dev.log" 2>&1
call "%PY_EXE%" -m uvicorn src.web.app:app --reload --host 127.0.0.1 --port 8000 --no-access-log >> "logs\api_dev.log" 2>&1
exit /b %errorlevel%
