import os

target_file = r"L:\ComfyUI\comfy\ldm\flux\model.py"

if not os.path.exists(target_file):
    print(f"Error: {target_file} not found.")
    exit(1)

with open(target_file, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Ensure Revert (Safety Check)
content = content.replace("params.vec_in_dim=768", "params.vec_in_dim")

# 2. Apply Correct Patch
# It is a dataclass field: "vec_in_dim: int"
# We want: "vec_in_dim: int = 768"
# NOTE: Be careful not to replace it if it's already patched.
if "vec_in_dim: int = 768" in content:
    print("Already patched.")
else:
    # Use strict replacement to avoid collateral damage
    # Searching for the specific line indentation usually found in these files (4 spaces)
    # But just strict string match is safer.
    
    # Check if "vec_in_dim: int" exists
    if "vec_in_dim: int" in content:
        new_content = content.replace("vec_in_dim: int", "vec_in_dim: int = 768")
        
        # Verify it didn't break Python syntax (dataclasses with defaults must come after non-defaults)
        # Wait. "vec_in_dim" is at line 24. 
        # Line 25 is "context_in_dim: int". 
        # If I give 24 a default, ALL subsequent fields MUST have defaults too, or it's a SyntaxError.
        # "non-default argument follows default argument"
        
        # Checking lines:
        # 24: vec_in_dim: int
        # 25: context_in_dim: int
        # ...
        # 35: guidance_embed: bool
        
        # CRITICAL: I cannot just add a default to one field in the middle.
        # I must add defaults to ALL subsequent fields if I touch this one.
        # OR, I find where `FluxParams` is instantiated and pass the argument there.
        
        print("DETECTED DATACLASS: Cannot patch field directly without breaking inheritance/order.")
        print("Switching strategy: Patching instantiation in `Flux` class.")
        
        # Search for where FluxParams is instantiated.
        # Likely `params = FluxParams(**kwargs)` or similar.
        # The user error trace said:
        # File "L:\ComfyUI\comfy\ldm\flux\model.py", line 46, in __init__
        # params = FluxParams(**kwargs)
        
        # Strategy: Inject "vec_in_dim" into kwargs before FluxParams call.
        # Look for: `params = FluxParams(**kwargs)`
        # Replace with:
        # if "vec_in_dim" not in kwargs: kwargs["vec_in_dim"] = 768
        # params = FluxParams(**kwargs)
        
        target_str = "params = FluxParams(**kwargs)"
        if target_str in content:
            patch_code = 'if "vec_in_dim" not in kwargs: kwargs["vec_in_dim"] = 768\n        params = FluxParams(**kwargs)'
            new_content = content.replace(target_str, patch_code)
            
            with open(target_file, "w", encoding="utf-8") as f:
                f.write(new_content)
            print("Success: Patched FluxParams instantiation via kwargs injection.")
        else:
            print("Error: Could not find 'params = FluxParams(**kwargs)' to patch.")
            # Fallback print for debugging
            print(content[:2000])

    else:
        print("Error: 'vec_in_dim: int' not found in file.")
