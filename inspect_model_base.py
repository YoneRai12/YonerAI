import os

target_file = r"L:\ComfyUI\comfy\model_base.py"

if not os.path.exists(target_file):
    print(f"Error: {target_file} not found.")
    exit(1)

with open(target_file, "r", encoding="utf-8") as f:
    content = f.read()

print("--- Searching for Flux Model Definition ---")
lines = content.split('\n')
for i, line in enumerate(lines):
    if "class Flux" in line and "(BaseModel)" in line: # Or similar inheritance
         print(f"Line {i+1}: {line}")
         for j in range(1, 100):
             if i+j < len(lines):
                 print(f"Line {i+1+j}: {lines[i+j]}")
                 if "def __init__" in lines[i+j] and "hidden_size" in lines[i+j]:
                     print("... (Init found) ...")
