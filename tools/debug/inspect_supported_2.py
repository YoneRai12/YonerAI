
target_file = r"L:\ComfyUI\comfy\supported_models.py"
with open(target_file, "r", encoding="utf-8") as f:
    content = f.read()

print("--- Searching for Model Registration ---")
lines = content.split('\n')
# Search for 'models = [' which usually registers them
found = False
for i, line in enumerate(lines):
    if "models = [" in line:
        found = True
        print(f"Start Line {i+1}: {line}")
        for j in range(1, 150): # Print enough lines to see Flux entries
             if i+j < len(lines):
                 print(f"Line {i+1+j}: {lines[i+j]}")
        break 

if not found:
    print("Could not find 'models = ['")
