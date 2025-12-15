import os

target_file = r"L:\ComfyUI\comfy\supported_models.py"

if not os.path.exists(target_file):
    print(f"Error: {target_file} not found.")
    exit(1)

with open(target_file, "r", encoding="utf-8") as f:
    content = f.read()

# Strategy: Find "FluxSchnell," in the "models = [...]" list and comment it out or remove it.
# Warning: It might be "FluxSchnell]" if it's the last one.

if "FluxSchnell" in content:
    # We are looking for the registration list logic usually at the end of file
    # models = [..., Flux, FluxSchnell, ...]
    
    # Simple replace: "FluxSchnell," -> "# FluxSchnell," 
    # But wait, python list doesn't like random comments inside if not careful with newlines.
    # Safe replacement: "FluxSchnell" -> "Flux" (Duplicate Flux check? redundant but safe)
    # OR better: remove it.
    
    new_content = content.replace("FluxSchnell,", "Flux, # Replaced FluxSchnell")
    
    # Also handle if it's at the end without comma
    new_content = new_content.replace("FluxSchnell]", "Flux]")
    
    if new_content != content:
        with open(target_file, "w", encoding="utf-8") as f:
            f.write(new_content)
        print("Success: Replaced FluxSchnell detection with Flux (forced Dev match).")
    else:
        print("Warning: FluxSchnell found but replacements failed (maybe string mismatch).")

else:
    print("Error: FluxSchnell not found in supported_models.py.")
