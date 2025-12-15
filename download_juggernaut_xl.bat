@echo off
echo Downloading Juggernaut XL v9 (High Quality SDXL Model)...
echo This is optimized for RTX 5090 (Native 1024x1024).
echo Destination: L:\AI_Models\Stable-diffusion\Juggernaut-XL_v9.safetensors

cd /d "L:\AI_Models\Stable-diffusion"
curl -L -O "https://huggingface.co/RunDiffusion/Juggernaut-XL-v9/resolve/main/Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors"

if %errorlevel% neq 0 (
    echo Download Failed!
    pause
    exit /b %errorlevel%
)

echo Download Complete!
pause
