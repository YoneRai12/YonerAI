import os

target_file = r"L:\ComfyUI\comfy\supported_models.py"

if not os.path.exists(target_file):
    print(f"Error: {target_file} not found.")
    exit(1)

with open(target_file, "r", encoding="utf-8") as f:
    content = f.read()

# The Broken String from User Log:
# ", Flux, # Replaced FluxSchnell"
# Context: "Flux, Flux, # Replaced FluxSchnell GenmoMochi"
#
# We want to turn:
# "... FluxInpaint, Flux, Flux, # Replaced FluxSchnell GenmoMochi ..."
# into:
# "... FluxInpaint, Flux, GenmoMochi ..."
#
# So we need to remove: " Flux, # Replaced FluxSchnell"
# And ensure a comma remains for GenmoMochi.

# Let's search for the exact broken pattern.
broken_pattern = "Flux, # Replaced FluxSchnell"

if broken_pattern in content:
    # Replace with empty string? 
    # Current: "Flux, Flux, # Replaced FluxSchnell GenmoMochi"
    # If I sub broken_pattern with EMPTY:
    # Result: "Flux,  GenmoMochi" (Space is likely there)
    # 
    # Wait, need to check if GenmoMochi has a preceding comma.
    # In original: "Flux, FluxSchnell, GenmoMochi"
    # My patch replaced "FluxSchnell," with "Flux, # Replaced FluxSchnell"
    # So " GenmoMochi" is likely just after the inserted string.
    # If I remove the inserted string, I might lose the comma for GenmoMochi?
    # No, I replaced "FluxSchnell," (INCLUDING COMMA).
    # So " GenmoMochi" (no comma before it) follows.
    
    # So I need to put back a comma!
    # Replacement: "" -> ", "
    # But wait, "Flux" (the real one) is before it. "Flux, "
    # If I just remove the broken pattern:
    # "Flux, [removed] GenmoMochi" -> "Flux, GenmoMochi"
    # This implies GenmoMochi didn't have a comma before it because I consumed it.
    # So yes, "Flux, GenmoMochi" is exactly what I want.
    
    # So, searching for "Flux, # Replaced FluxSchnell" and replacing with "" (empty).
    # Let's check spaces. 
    # "Flux, Flux, # Replaced FluxSchnell GenmoMochi"
    # Removal -> "Flux,  GenmoMochi"
    # Looks syntactically valid.
    
    new_content = content.replace(broken_pattern, "")
    
    # Double check for "Flux,  GenmoMochi" (ensure comma exists from previous item)
    # Previous item is "Flux,". So yes.
    
    with open(target_file, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("Success: Fixed syntax error by cleanly removing the bad comment block.")

else:
    print("Error: Broken pattern not found. Trying flexible search...")
    # Maybe newlines involved?
    import re
    # Escape special chars just in case
    pattern = re.compile(r"Flux,\s*# Replaced FluxSchnell")
    if pattern.search(content):
        new_content = pattern.sub("", content)
        with open(target_file, "w", encoding="utf-8") as f:
            f.write(new_content)
        print("Success: Fixed syntax error via Regex.")
    else:
        print("Fatal: Could not find the syntax error pattern.")
