import os

target_file = r"L:\ComfyUI\comfy\supported_models.py"

if not os.path.exists(target_file):
    print(f"Error: {target_file} not found.")
    exit(1)

with open(target_file, "r", encoding="utf-8") as f:
    content = f.read()

# Target: class FluxSchnell(Flux): ... "guidance_embed": False
# We want to change False to True.

# Use regex or precise string matching to find the specific block
# Because "guidance_embed": False might appear elsewhere.

# Look for:
# class FluxSchnell(Flux):
#     vae_key_prefix = ["vae."]
#     text_encoder_key_prefix = ["text_encoders."]
#     unet_config = {
#         "guidance_embed": False,
#     }

# We will replace `"guidance_embed": False` inside `FluxSchnell` context.
# Since python files are structured, we can just replace the first occurrence AFTER `class FluxSchnell`.

parts = content.split("class FluxSchnell(Flux):")
if len(parts) < 2:
    print("Error: Could not find 'class FluxSchnell(Flux):'")
    exit(1)

pre_flux = parts[0]
flux_schnell_part = parts[1]

# Now we perform replacement ONLY in flux_schnell_part
# Note: we need to be careful not to affect subsequent classes if they are in the same chunk.
# But likely it's fine as long as we only target the *first* occurrence of guidance_embed: False.

if '"guidance_embed": False' in flux_schnell_part:
    new_flux_schnell_part = flux_schnell_part.replace('"guidance_embed": False', '"guidance_embed": True', 1)
    new_content = pre_flux + "class FluxSchnell(Flux):" + new_flux_schnell_part
    
    with open(target_file, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("Success: Forced FluxSchnell to use 'guidance_embed': True (Dev Mode).")
else:
    print("Warning: 'guidance_embed': False not found in FluxSchnell block. Already patched?")
