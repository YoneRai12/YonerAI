$ErrorActionPreference = "Stop"

Write-Host "==========================================="
Write-Host "⬇️ DOWNLOADING QWEN3-VL-30B-A3B (AWQ) MODEL"
Write-Host "==========================================="
Write-Host "Repo: QuantTrio/Qwen3-VL-30B-A3B-Instruct-AWQ"
Write-Host "Type: Mixture-of-Experts (30B Total, 3B Active)"
Write-Host "Optimization: AWQ (4-bit)"
Write-Host "Destination: L:\ai_models\huggingface"

set "HF_HOME=L:\ai_models\huggingface"
set "HUGGINGFACE_HUB_CACHE=L:\ai_models\huggingface\hub"

# Download Model
huggingface-cli download QuantTrio/Qwen3-VL-30B-A3B-Instruct-AWQ --local-dir "L:\ai_models\huggingface\QuantTrio_Qwen3-VL-30B-A3B-Instruct-AWQ"

Write-Host "`n✅ Download Complete."
Write-Host "Model Location: L:\ai_models\huggingface\QuantTrio_Qwen3-VL-30B-A3B-Instruct-AWQ"
Write-Host "==========================================="
pause
