@echo off
cd /d "%~dp0\.."
chcp 65001 >nul

set "PY_EXE=.venv\Scripts\python.exe"
if exist "%PY_EXE%" goto loop
set "PY_EXE=python"

:loop
title ORA Bot (auto-restart loop)
echo Starting ORA Bot process...
set PYTHONPATH=.
call "%PY_EXE%" main.py
if %errorlevel% equ 99 (
    echo Exit code 99 detected. Stop loop.
    exit /b 99
)
echo Bot process exited. Restarting in 5 seconds...
timeout /t 5
goto loop
