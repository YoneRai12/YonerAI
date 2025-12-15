$ErrorActionPreference = "Stop"

Write-Host "==========================================="
Write-Host "🐞 COMFYUI NATIVE CRASH TRACER"
Write-Host "==========================================="
Write-Host "Enabling Fault Handler & C++ Stack Traces..."

$env:PYTHONFAULTHANDLER = "1"
$env:TORCH_SHOW_CPP_STACKTRACES = "1"

Set-Location "L:\ComfyUI"

Write-Host "Launching ComfyUI (Normal VRAM) with Tracing..."
Write-Host "Log will be saved to: L:\comfy_crash.log"
Write-Host "-------------------------------------------"

# Launch with -X faulthandler and redirect output
& "L:\ORADiscordBOT_Env\Scripts\python.exe" -X faulthandler -u main.py --listen 127.0.0.1 --port 8188 2>&1 | Tee-Object -FilePath "L:\comfy_crash.log"

Write-Host "`n==========================================="
Write-Host "❌ PROCESS EXITED."
Write-Host "Please check L:\comfy_crash.log for stack traces."
Write-Host "==========================================="
Read-Host "Press Enter to exit"
