import os

# Target File: L:\ComfyUI\comfy\ldm\flux\model.py
target_file = r"L:\ComfyUI\comfy\ldm\flux\model.py"

if not os.path.exists(target_file):
    print(f"Error: {target_file} not found.")
    exit(1)

with open(target_file, "r", encoding="utf-8") as f:
    content = f.read()

# Fix: Make vec_in_dim optional in FluxParams.__init__
# Original: def __init__(self, image_model_type, vector_in_dim, ...
# Or similar. We will simply replace the error causing line.

# Based on error: TypeError: FluxParams.__init__() missing 1 required positional argument: 'vec_in_dim'
# We need to find __init__ and add a default value to vec_in_dim or patch the caller?
# Patching the definition is safer.

# Locating FluxParams class
# It likely looks like: class FluxParams: def __init__(self, ..., vec_in_dim, ...)

# Strategy: Replace "vec_in_dim," with "vec_in_dim=768," (Default for Flux Dev)
# Note: vec_in_dim is typically 768 for Flux.

new_content = content.replace("vec_in_dim,", "vec_in_dim=768,")

if content == new_content:
    print("Patch not applied (String not found or already patched). Attempting regex/alternate match...")
    # Try end of arguments? 
    # Let's try patching the __init__ call in standard location?
    # No, the error is in definition.
    # Let's just print the signature to debug via output if it fails.
    
    # Debug mode: Read the file and print the relevant lines
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if "def __init__" in line and "FluxParams" in lines[i-1] or "class FluxParams" in lines[i-2]:
            print(f"Found signature close to line {i}: {line}")
else:
    with open(target_file, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("Success: Patched FluxParams in model.py to have default vec_in_dim=768.")
