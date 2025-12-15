import os

target_file = r"L:\ComfyUI\comfy\ldm\flux\model.py"
print(f"Target: {target_file}")

with open(target_file, "r", encoding="utf-8") as f:
    content = f.read()

# The target line to hook into
target_line = '        params = FluxParams(**kwargs)'

# The patch block to insert
patch_block = """        print(f"DEBUG: Flux init kwargs: hidden_size={kwargs.get('hidden_size')}, vec_in_dim={kwargs.get('vec_in_dim')}")
        params = FluxParams(**kwargs)
        pe_dim = params.hidden_size // params.num_heads
        print(f"DEBUG: Flux params calculated: hidden_size={params.hidden_size}, num_heads={params.num_heads}, pe_dim={pe_dim}, axes_dim={params.axes_dim}")
        
        # ORA SMART PATCH
        if sum(params.axes_dim) != pe_dim:
            print(f"DEBUG: Mismatch detected! sum(axes)={sum(params.axes_dim)} != pe_dim={pe_dim}")
            if pe_dim == 256 and sum(params.axes_dim) == 128:
                print("DEBUG: ORA FIX TRIGGERED -> Updating axes_dim to [32, 112, 112]")
                params.axes_dim = [32, 112, 112]
            else:
                 print(f"DEBUG: Mismatch is NOT the 128/256 case. Leaving as is.")
        else:
            print("DEBUG: No mismatch detected.")
            
        print("DEBUG: Proceeding with self.params assignment...")"""

if "params = FluxParams(**kwargs)" not in content:
    print("Error: Could not find anchor 'params = FluxParams(**kwargs)'")
    exit(1)
    
if "self.params = params" not in content:
    print("Error: Could not find anchor 'self.params = params'")
    exit(1)

# Robust Wipe-and-Replace Logic
anchor_top = '        if "vec_in_dim" not in kwargs: kwargs["vec_in_dim"] = 768'
anchor_bottom = '        self.params = params'

patch_block = """        print(f"DEBUG: Flux init kwargs: hidden_size={kwargs.get('hidden_size')}, vec_in_dim={kwargs.get('vec_in_dim')}")
        
        # ORA SMART PATCH: Compatible with Standard Flux (3072) and Custom (6144)
        # We REMOVED the Force 6144 logic to allow standard models to load correctly.
            
        params = FluxParams(**kwargs)
        pe_dim = params.hidden_size // params.num_heads
        print(f"DEBUG: Flux params calculated: hidden_size={params.hidden_size}, num_heads={params.num_heads}, pe_dim={pe_dim}, axes_dim={params.axes_dim}")
        
        # ORA SMART PATCH
        if sum(params.axes_dim) != pe_dim:
            print(f"DEBUG: Mismatch detected! sum(axes)={sum(params.axes_dim)} != pe_dim={pe_dim}")
            if pe_dim == 256 and sum(params.axes_dim) == 128:
                print("DEBUG: ORA FIX TRIGGERED -> Updating axes_dim to [32, 112, 112]")
                params.axes_dim = [32, 112, 112]
            else:
                 print(f"DEBUG: Mismatch is NOT the 128/256 case. Leaving as is.")
        else:
            print("DEBUG: No mismatch detected.")
            
        print("DEBUG: Proceeding with self.params assignment...")"""

if anchor_top not in content:
    print("Error: Anchor TOP not found.")
    exit(1)
if anchor_bottom not in content:
    print("Error: Anchor BOTTOM not found.")
    exit(1)
    
parts_top = content.split(anchor_top)
pre_chunk = parts_top[0]
remainder = parts_top[1]
parts_bottom = remainder.split(anchor_bottom)

if len(parts_bottom) < 2:
    print("Error: Anchor BOTTOM split failed.")
    exit(1)

corrupted_middle = parts_bottom[0]
post_chunk = parts_bottom[1]

new_content = pre_chunk + anchor_top + "\n" + patch_block + "\n" + anchor_bottom + post_chunk

with open(target_file, "w", encoding="utf-8") as f:
    f.write(new_content)

print("Smart Patch Applied (Force 6144 + Fix Axes).")
