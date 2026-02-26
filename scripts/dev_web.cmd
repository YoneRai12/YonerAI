@echo off
setlocal
cd /d "%~dp0\.."

if not exist logs mkdir logs
cd /d clients\web

echo [dev_web] npm install >> "..\..\logs\web_dev.log" 2>&1
call npm.cmd install >> "..\..\logs\web_dev.log" 2>&1
if errorlevel 1 exit /b %errorlevel%

echo [dev_web] npm run dev -- -H 127.0.0.1 -p 3000 >> "..\..\logs\web_dev.log" 2>&1
call npm.cmd run dev -- -H 127.0.0.1 -p 3000 >> "..\..\logs\web_dev.log" 2>&1
exit /b %errorlevel%
