@echo off
echo Installing AnimateDiff Extension for Video Generation...
cd /d "C:\Users\YoneRai12\stable-diffusion-webui\extensions"

if not exist sd-webui-animatediff (
    echo Cloning sd-webui-animatediff...
    git clone https://github.com/continue-revolution/sd-webui-animatediff.git
) else (
    echo sd-webui-animatediff already exists. skipping clone.
)

echo Downloading Motion Module (v3_sd15_mm.ckpt)...
cd sd-webui-animatediff\model
curl -L -O "https://huggingface.co/guoyww/animatediff/resolve/main/v3_sd15_mm.ckpt"

if %errorlevel% neq 0 (
    echo Download Failed!
    pause
    exit /b %errorlevel%
)

echo Installation Complete!
echo Please RESTART Stable Diffusion WebUI (run_l.bat).
pause
