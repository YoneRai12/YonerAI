$env:HF_HOME = "L:\hf"
$env:HUGGINGFACE_HUB_CACHE = "L:\hf\hub"

Write-Host "=============================================="
Write-Host "🌩️ Downloading HunyuanVideo 1.5 Models"
Write-Host "=============================================="
Write-Host ""
Write-Host "Destination: L:\ComfyUI\models\..."
Write-Host ""

# Ensure directories exist
New-Item -ItemType Directory -Force -Path "L:\ComfyUI\models\diffusion_models" | Out-Null
New-Item -ItemType Directory -Force -Path "L:\ComfyUI\models\vae" | Out-Null
New-Item -ItemType Directory -Force -Path "L:\ComfyUI\models\text_encoders" | Out-Null

# diffusion model
Write-Host "Downloading Diffusion Model (T2V FP16)..."
L:\ORADiscordBOT_Env\Scripts\huggingface-cli.exe download Comfy-Org/HunyuanVideo_1.5_repackaged split_files/diffusion_models/hunyuanvideo1.5_720p_t2v_fp16.safetensors --local-dir "L:\ComfyUI\models\diffusion_models" --local-dir-use-symlinks False

# VAE
Write-Host "Downloading VAE..."
L:\ORADiscordBOT_Env\Scripts\huggingface-cli.exe download Comfy-Org/HunyuanVideo_1.5_repackaged split_files/vae/hunyuanvideo15_vae_fp16.safetensors --local-dir "L:\ComfyUI\models\vae" --local-dir-use-symlinks False

# text encoders
Write-Host "Downloading Text Encoders (Qwen & ByT5)..."
L:\ORADiscordBOT_Env\Scripts\huggingface-cli.exe download Comfy-Org/HunyuanVideo_1.5_repackaged split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors --local-dir "L:\ComfyUI\models\text_encoders" --local-dir-use-symlinks False
L:\ORADiscordBOT_Env\Scripts\huggingface-cli.exe download Comfy-Org/HunyuanVideo_1.5_repackaged split_files/text_encoders/byt5_small_glyphxl_fp16.safetensors --local-dir "L:\ComfyUI\models\text_encoders" --local-dir-use-symlinks False

Write-Host ""
Write-Host "=============================================="
Write-Host "✅ HunyuanVideo 1.5 Download Complete!"
Write-Host "=============================================="
Read-Host "Press Enter to exit"
