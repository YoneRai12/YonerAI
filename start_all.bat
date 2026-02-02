@echo off
setlocal enabledelayedexpansion
title ORA Launcher (Unified)
echo ===================================================
echo   ORA System Launcher - Unified Experience
echo ===================================================

set "ROOT_DIR=%~dp0"
set "PYTHON_EXE=L:\ORADiscordBOT_Env\Scripts\python.exe"
set "UVICORN_EXE=L:\ORADiscordBOT_Env\Scripts\uvicorn.exe"

echo [1/4] Starting Main Web UI (Port 3000)...
start "ORA-Web-Main" /D "%ROOT_DIR%clients\web" cmd /k "npm run dev"

echo [2/4] Starting Dashboard UI (Port 3333)...
start "ORA-Dashboard" /D "%ROOT_DIR%ora-ui" cmd /k "npm run dev"

echo [3/4] Starting ORA-Core (Port 8001)...
start "ORA-Core" /D "%ROOT_DIR%" cmd /k "set "PYTHONPATH=%ROOT_DIR%core\src" && "%PYTHON_EXE%" -m ora_core.main"

echo [4/4] Starting ORA-Admin-Server (Port 8000)...
start "ORA-Admin" /D "%ROOT_DIR%" cmd /k "set "PYTHONPATH=%ROOT_DIR%" && "%UVICORN_EXE%" src.web.app:app --host 0.0.0.0 --port 8000"

echo [5/5] Starting ORA Discord Bot...
echo Waiting 8s for servers to initialize...
timeout /t 8 >nul
set "PYTHONPATH=%ROOT_DIR%"
"%PYTHON_EXE%" "%ROOT_DIR%main.py"

pause
