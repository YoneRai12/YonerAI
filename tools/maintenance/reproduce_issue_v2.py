import json
import re


def extract_json_objects(text):
    """
    Simulate the existing _extract_json_objects method (simplified).
    Current bot implementation likely uses a regex or stack-based approach.
    I'll assume it returns empty list for the problematic string based on behavior.
    """
    # Assuming the current implementation fails to find json{...}
    # Let's verify what the fallback regex does.
    return []


def test_parsing(content):
    print(f"Testing content: '{content}'")

    json_objects = extract_json_objects(content)
    tool_call = None

    cmd_r_match = re.search(r"to=(\w+)", content)
    if cmd_r_match:
        print(f"Cmd R+ Match: {cmd_r_match.group(1)}")

        # This is the logic I added last time
        if not json_objects:
            # Look for json{...} or json {...}
            # Regex: json\s*(\{.*?\})
            json_match = re.search(r"json\s*(\{.*?\})", content, re.DOTALL)
            if json_match:
                print(f"Fallback Regex Matched: {json_match.group(1)}")
                json_objects.append(json_match.group(1))
            else:
                print("Fallback Regex FAILED")

    for _i, json_str in enumerate(json_objects):
        try:
            print(f"Attempting to parse: {json_str}")
            data = json.loads(json_str)
            if "tool" in data and "args" in data:
                tool_call = data
                print("Found Standard Tool Call")
                break
            elif cmd_r_match and isinstance(data, dict):
                tool_name = cmd_r_match.group(1)
                tool_call = {"tool": tool_name, "args": data}
                print(f"Found Cmd R+ Tool Call: {tool_call}")
                break
        except json.JSONDecodeError as e:
            print(f"JSON Decode Error: {e}")
            continue

    if tool_call:
        print(f"SUCCESS: Tool call parsed: {tool_call}")
    else:
        print("FAILURE: No tool call parsed.")


# The problematic string from user
test_content = 'commentary to=google_search json{"query":"PC プログラミング 上手になる 方法"}'
test_parsing(test_content)
