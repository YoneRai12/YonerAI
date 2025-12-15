$env:HF_HOME="L:\hf"
$env:HUGGINGFACE_HUB_CACHE="L:\hf\hub"

write-host "Downloading FLUX.2 Models..."
write-host "Warning: Ensure you have run 'huggingface-cli login' if these are gated models."

# Text Encoder
write-host "Downloading Text Encoder..."
huggingface-cli download Comfy-Org/flux2-dev split_files/text_encoders/mistral_3_small_flux2_fp8.safetensors --local-dir "L:\ComfyUI\models\text_encoders" --resume-download

# Diffusion Model
write-host "Downloading Diffusion Model..."
huggingface-cli download Comfy-Org/flux2-dev split_files/diffusion_models/flux2_dev_fp8mixed.safetensors --local-dir "L:\ComfyUI\models\diffusion_models" --resume-download

# VAE
write-host "Downloading VAE..."
huggingface-cli download Comfy-Org/flux2-dev split_files/vae/flux2-vae.safetensors --local-dir "L:\ComfyUI\models\vae" --resume-download

write-host "Download Complete."
pause
