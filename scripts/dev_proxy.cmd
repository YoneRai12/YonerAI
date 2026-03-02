@echo off
setlocal
cd /d "%~dp0\.."

if not exist logs mkdir logs

where caddy >nul 2>&1
if errorlevel 1 (
  echo [ERROR] caddy not found in PATH.
  echo         Install Caddy and ensure "caddy" command is available.
  exit /b 1
)

echo [INFO] Starting local reverse proxy on http://127.0.0.1:8787
caddy run --config scripts\Caddyfile.local --adapter caddyfile

