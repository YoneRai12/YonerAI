import os

# Target 1: model_base.py (Checks how it initializes Flux)
target_file = r"L:\ComfyUI\comfy\model_base.py"
with open(target_file, "r", encoding="utf-8") as f:
    content = f.read()

print("--- model_base.py (Flux Init) ---")
lines = content.split('\n')
for i, line in enumerate(lines):
    if "class Flux" in line:
        # Print next 50 lines to see __init__ logic
        for j in range(0, 50):
             if i+j < len(lines):
                 print(f"{i+j+1}: {lines[i+j]}")

# Target 2: ldm/flux/model.py (Checks config defaults)
target_file_2 = r"L:\ComfyUI\comfy\ldm\flux\model.py"
with open(target_file_2, "r", encoding="utf-8") as f:
    content_2 = f.read()
    
print("\n--- ldm/flux/model.py (Config) ---")
lines_2 = content_2.split('\n')
# We are looking for where 'hidden_size' is assigned or defaults
for i, line in enumerate(lines_2):
    if "hidden_size" in line and "=" in line:
        print(f"{i+1}: {line}")
