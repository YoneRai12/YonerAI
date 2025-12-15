@echo off
echo Installing ComfyUI for FLUX.2...
cd /d L:\

if not exist ComfyUI (
    echo Cloning ComfyUI...
    git clone https://github.com/comfyanonymous/ComfyUI.git
) else (
    echo ComfyUI already exists. Skipping clone.
)

cd ComfyUI

echo Installing Requirements...
L:\ORADiscordBOT_Env\Scripts\python.exe -m pip install -r requirements.txt
if %errorlevel% neq 0 pause && exit /b 1

echo Installing Huggingface CLI...
L:\ORADiscordBOT_Env\Scripts\python.exe -m pip install -U huggingface_hub[cli]
if %errorlevel% neq 0 pause && exit /b 1

echo Setup Complete. Next: Run download_flux.ps1
pause
