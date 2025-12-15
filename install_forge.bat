@echo off
echo Installing WebUI Forge (Optimized for FLUX.2 and GTX 5090)...
echo Destination: L:\WebUI_Forge

cd /d L:\

if not exist WebUI_Forge (
    echo Cloning WebUI Forge...
    git clone https://github.com/lllyasviel/stable-diffusion-webui-forge.git WebUI_Forge
) else (
    echo WebUI_Forge directory already exists. Skipping clone.
)

cd WebUI_Forge

echo Creating VENV and Installing Dependencies...
echo This may take a while.
call webui-user.bat --nowebui

echo.
echo Forge Installed!
echo Please copy your FLUX.2 model to: L:\WebUI_Forge\models\Stable-diffusion
pause
