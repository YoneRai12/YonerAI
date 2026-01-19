
target_file = r"L:\ComfyUI\comfy\ldm\flux\model.py"
print(f"Patching {target_file}...")

with open(target_file, "r", encoding="utf-8") as f:
    content = f.read()

# The correct block (8 spaces indentation)
correct_block = """        if "vec_in_dim" not in kwargs: kwargs["vec_in_dim"] = 768
        params = FluxParams(**kwargs)
        # ORA SMART PATCH: Fix known axes_dim mismatch for Flux.1 Dev
        pe_dim = params.hidden_size // params.num_heads
        if sum(params.axes_dim) != pe_dim:
            if pe_dim == 256 and sum(params.axes_dim) == 128:
                params.axes_dim = [32, 112, 112]"""

# The broken block (Double indentation - 16 spaces or mixed)
# My previous script likely added 8 spaces to the existing 8 spaces -> 16 spaces.
broken_line_part = '                if "vec_in_dim" not in kwargs: kwargs["vec_in_dim"] = 768'

# Also check for the single line original version with 8 spaces
original_line_indented = '        if "vec_in_dim" not in kwargs: kwargs["vec_in_dim"] = 768'

if broken_line_part in content:
    print("Found broken double-indentation. Fixing...")
    # Regex replacement for the whole broken block might be hard, so let's try to identify the start
    # We will search for the specific broken line and replace it + the following patched lines if present
    # But simpler: Just replace the broken line and the appended lines with the CORRECT block.
    # The broken block probably looks like:
    #                 if "vec_in_dim" ...
    #         # ORA FORCE PATCH...
    #         if kwargs.get...
    
    # Let's try to normalize.
    # We will look for the 16-space line and replace it and the next few lines if they match our patch signature.
    # Actually, simpler approach: Read lines, identify the line index, and rewrite the file.
    lines = content.splitlines()
    new_lines = []
    skip_next = 0
    
    for i, line in enumerate(lines):
        if skip_next > 0:
            skip_next -= 1
            continue
            
        if 'if "vec_in_dim" not in kwargs: kwargs["vec_in_dim"] = 768' in line:
            # Check indentation
            stripped = line.lstrip()
            indent = len(line) - len(stripped)
            
            if indent > 8: # Likely the broken 16 spaces
                print(f"Fixing line {i+1}: Indentation {indent} -> 8")
                new_lines.append(correct_block)
                # We might need to skip subsequent lines if they were part of the bad patch
                # The bad patch consisted of 5 lines (including comments)
                # Let's peek ahead
                if i+1 < len(lines) and "ORA FORCE PATCH" in lines[i+1]:
                    skip_next += 4 # Skip the bad patch lines
            elif indent == 8:
                # Could be minimal original or already correct patch
                if i+1 < len(lines) and "ORA FORCE PATCH" in lines[i+1]:
                    print("Patch appears correct (8 spaces). Updating just in case.")
                    new_lines.append(correct_block)
                    skip_next += 4
                else:
                    # Original line, replace with patch
                    print("Found original line (8 spaces). Patching.")
                    new_lines.append(correct_block)
            else:
                # Unexpected indentation, keep as is
                new_lines.append(line)
        else:
            new_lines.append(line)
            
    with open(target_file, "w", encoding="utf-8") as f:
        f.write("\n".join(new_lines))
    print("Success: Fixed indentation.")

elif "ORA FORCE PATCH" in content:
     print("Found existing ORA Patch (potentially bad). Replacing with clean version...")
     # We need to find the block and replace it.
     # The block usually starts with the 'vec_in_dim' line and ends after the 'axes_dim' line.
     lines = content.splitlines()
     new_lines = []
     skip_next = 0
     
     for i, line in enumerate(lines):
          if skip_next > 0:
               skip_next -= 1
               continue
               
          if 'if "vec_in_dim" not in kwargs' in line:
               # Found the start of a patch (or original line)
               new_lines.append(correct_block)
               # Check if it's the multi-line bad patch
               if i+1 < len(lines) and "ORA FORCE PATCH" in lines[i+1]:
                   print("Removing hidden_size override lines...")
                   skip_next = 4 # Skip the next 4 lines
          else:
               new_lines.append(line)

     with open(target_file, "w", encoding="utf-8") as f:
         f.write("\n".join(new_lines))
     print("Success: Reverted to clean patch.")

else:
     print("Patch not found. Applying clean version...")
     if original_line_indented in content:
          new_content = content.replace(original_line_indented, correct_block)
          with open(target_file, "w", encoding="utf-8") as f:
              f.write(new_content)
          print("Success: Clean patch applied.")
     else:
          print("Error: Could not locate injection point.")
