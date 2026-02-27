@echo off
setlocal EnableExtensions
chcp 65001 >nul 2>&1

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "REPO_ROOT=%%~fI"
cd /d "%REPO_ROOT%"
title YonerAI Full Launcher

if not exist logs mkdir logs

set "PYEXE="
call :pick_python "%REPO_ROOT%\.venv\Scripts\python.exe"
if not defined PYEXE if defined VIRTUAL_ENV call :pick_python "%VIRTUAL_ENV%\Scripts\python.exe"
if not defined PYEXE call :pick_python "%ORA_PYEXE%"
if not defined PYEXE call :pick_python "python"
if not defined PYEXE set "PYEXE=python"

where npm.cmd >nul 2>&1
if errorlevel 1 (
  echo [ERROR] npm.cmd was not found. Install Node.js/npm first.
  pause
  exit /b 1
)

echo ==========================================
echo YonerAI full start
echo ROOT: %REPO_ROOT%
echo Python: %PYEXE%
echo ==========================================
echo.

echo [1/5] DB init scripts...
set "PYTHONPATH=%REPO_ROOT%\core\src"
"%PYEXE%" "%REPO_ROOT%\scripts\fix_user_id_column.py" >> "logs\start_ora_system.log" 2>&1
"%PYEXE%" "%REPO_ROOT%\scripts\init_core_db.py" >> "logs\start_ora_system.log" 2>&1

echo [2/5] Core API (8001)...
call :start_if_free 8001 "YonerAI-CoreAPI" "cd /d ""%REPO_ROOT%"" && set PYTHONPATH=%REPO_ROOT%\core\src && ""%PYEXE%"" -m ora_core.main >> ""logs\core_api.log"" 2>&1"

echo [3/5] Legacy API (8000)...
call :start_if_free 8000 "YonerAI-WebAPI" "cd /d ""%REPO_ROOT%"" && set PYTHONPATH=%REPO_ROOT% && ""%PYEXE%"" -m uvicorn src.web.app:app --reload --host 127.0.0.1 --port 8000 --no-access-log >> ""logs\web_api.log"" 2>&1"

echo [4/5] Next Web (3000)...
call :start_if_free 3000 "YonerAI-WebUI" "cd /d ""%REPO_ROOT%\clients\web"" && npm.cmd run dev -- -H 127.0.0.1 -p 3000 >> ""..\..\logs\web_dev.log"" 2>&1"

if exist "%REPO_ROOT%\main.py" (
  echo [5/5] Discord Bot...
  start "YonerAI-Discord" cmd /c "cd /d ""%REPO_ROOT%"" && ""%PYEXE%"" main.py >> ""logs\discord_main.log"" 2>&1"
) else (
  echo [5/5] Discord Bot skipped (main.py not found).
)

echo.
echo [OK] Started portable services. Check logs\*.log
echo      Web UI: http://127.0.0.1:3000
echo      API:    http://127.0.0.1:8000
echo      Core:   http://127.0.0.1:8001
echo.
exit /b 0

:pick_python
set "CAND=%~1"
if "%CAND%"=="" goto :eof
if /I "%CAND%"=="python" (
  python -c "import encodings" >nul 2>&1
  if not errorlevel 1 set "PYEXE=python"
  goto :eof
)
if not exist "%CAND%" goto :eof
"%CAND%" -c "import encodings" >nul 2>&1
if not errorlevel 1 set "PYEXE=%CAND%"
goto :eof

:start_if_free
set "PORT=%~1"
set "TITLE=%~2"
set "CMD=%~3"
powershell -NoProfile -Command "$c=New-Object Net.Sockets.TcpClient; try { $c.Connect('127.0.0.1',%PORT%); exit 0 } catch { exit 1 } finally { $c.Dispose() }"
if %ERRORLEVEL% equ 0 (
  echo [INFO] Port %PORT% is already in use. Skip %TITLE%.
) else (
  start "%TITLE%" cmd /c "%CMD%"
)
goto :eof
