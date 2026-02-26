@echo off
setlocal
cd /d "%~dp0\.."

if not exist logs mkdir logs

start "ORA API" cmd /c scripts\dev_api.cmd
start "ORA WEB" cmd /c scripts\dev_web.cmd
start "ORA DISCORD" cmd /c scripts\dev_discord.cmd

echo Started local dev windows: API, WEB, DISCORD.
exit /b 0
