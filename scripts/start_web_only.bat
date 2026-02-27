@echo off
setlocal EnableExtensions
chcp 65001 >nul 2>&1

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "REPO_ROOT=%%~fI"
cd /d "%REPO_ROOT%"

title YonerAI WEB launcher
set "DRY_RUN=0"
if /I "%~1"=="--dry-run" set "DRY_RUN=1"

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
echo YonerAI WEB start
echo ROOT: %REPO_ROOT%
echo Python: %PYEXE%
echo ==========================================
echo [INFO] API: http://127.0.0.1:8000
echo [INFO] WEB: http://127.0.0.1:3000
echo.

if "%DRY_RUN%"=="1" (
  echo [INFO] Dry-run mode. Commands were not executed.
  exit /b 0
)

call :start_api
call :start_web

echo.
echo [OK] WEB startup sequence completed.
exit /b 0

:start_api
powershell -NoProfile -Command "$c=New-Object Net.Sockets.TcpClient; try { $c.Connect('127.0.0.1',8000); exit 0 } catch { exit 1 } finally { $c.Dispose() }"
if %ERRORLEVEL% equ 0 (
  echo [INFO] API already running on 127.0.0.1:8000
) else (
  echo [INFO] Starting API on 127.0.0.1:8000
  start "YonerAI-WebAPI" cmd /c "cd /d ""%REPO_ROOT%"" && set PYTHONPATH=%REPO_ROOT% && ""%PYEXE%"" -m uvicorn src.web.app:app --reload --host 127.0.0.1 --port 8000 --no-access-log >> ""logs\web_api.log"" 2>&1"
)
goto :eof

:start_web
powershell -NoProfile -Command "$c=New-Object Net.Sockets.TcpClient; try { $c.Connect('127.0.0.1',3000); exit 0 } catch { exit 1 } finally { $c.Dispose() }"
if %ERRORLEVEL% equ 0 (
  echo [INFO] WEB already running on 127.0.0.1:3000
) else (
  echo [INFO] Starting WEB on 127.0.0.1:3000
  start "YonerAI-WebUI" cmd /c "cd /d ""%REPO_ROOT%\clients\web"" && npm.cmd run dev -- -H 127.0.0.1 -p 3000 >> ""..\..\logs\web_dev.log"" 2>&1"
)
goto :eof

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
