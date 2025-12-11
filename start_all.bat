@echo off
setlocal

:: Activate venv if it exists
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else (
    echo Warning: venv not found. Running with system python.
)

echo Starting ORA Bot and Web API...

:: Start Web API in a new window
start "ORA Web API" cmd /k "uvicorn src.web.app:app --reload --port 8000"

:: Wait a bit for API to start
timeout /t 3 /nobreak >nul

:: Start Next.js Frontend in a new window
start "ORA Vision UI" cmd /k "cd ora-ui && npm run dev"

:: Start Discord Bot in a new window
start "ORA Bot" cmd /k "python main.py"

:: Start Stable Diffusion WebUI in a new window (with API enabled)
echo Starting Stable Diffusion...
start "Stable Diffusion WebUI" cmd /k "cd /d C:\Users\YoneRai12\stable-diffusion-webui && set COMMANDLINE_ARGS=--api && call webui-user.bat"

echo Services started!
echo Web API: http://localhost:8000/docs
echo Frontend: http://localhost:3000
echo Bot: Check Discord
pause
endlocal
