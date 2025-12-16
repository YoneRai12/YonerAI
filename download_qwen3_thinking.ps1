$ErrorActionPreference = "Stop"

Write-Host "==========================================="
Write-Host "⬇️ DOWNLOADING QWEN3-VL-30B-A3B (Thinking) (AWQ)"
Write-Host "==========================================="
Write-Host "Repo: QuantTrio/Qwen3-VL-30B-A3B-Thinking-AWQ"
Write-Host "Type: Reasoning/Thinking Variant (Math/Graph specialized)"
Write-Host "Optimization: AWQ (4-bit)"
Write-Host "Destination: L:\ai_models\huggingface"

set "HF_HOME=L:\ai_models\huggingface"
set "HUGGINGFACE_HUB_CACHE=L:\ai_models\huggingface\hub"

# Download Model
huggingface-cli download QuantTrio/Qwen3-VL-30B-A3B-Thinking-AWQ --local-dir "L:\ai_models\huggingface\QuantTrio_Qwen3-VL-30B-A3B-Thinking-AWQ"

Write-Host "`n✅ Download Complete."
Write-Host "Model Location: L:\ai_models\huggingface\QuantTrio_Qwen3-VL-30B-A3B-Thinking-AWQ"
Write-Host "==========================================="
pause
