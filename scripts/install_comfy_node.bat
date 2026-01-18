@echo off
echo Installing ComfyUI-SaveAsScript to L:\ComfyUI\custom_nodes...
cd /d L:\ComfyUI\custom_nodes
if exist "ComfyUI-SaveAsScript" (
    echo Already installed. pulling latest...
    cd ComfyUI-SaveAsScript
    git pull
) else (
    git clone https://github.com/atmaranto/ComfyUI-SaveAsScript.git ComfyUI-SaveAsScript
)
echo Installation Complete.
