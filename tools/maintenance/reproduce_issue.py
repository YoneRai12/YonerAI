
import json
import re


def _extract_json_objects(text: str) -> list[str]:
    """Extracts top-level JSON objects from text by matching balanced braces."""
    objects = []
    stack = 0
    start_index = -1
    
    for i, char in enumerate(text):
        if char == '{':
            if stack == 0:
                start_index = i
            stack += 1
        elif char == '}':
            if stack > 0:
                stack -= 1
                if stack == 0:
                    objects.append(text[start_index:i+1])
    return objects

def test_parsing(content):
    print(f"Testing content: {content}")
    json_objects = _extract_json_objects(content)
    print(f"Extracted JSON objects: {json_objects}")
    
    tool_call = None
    cmd_r_match = re.search(r"to=(\w+)", content)
    if cmd_r_match:
        print(f"Command R+ match: {cmd_r_match.group(1)}")
    
    for json_str in json_objects:
        try:
            data = json.loads(json_str)
            print(f"Parsed JSON: {data}")
            # Case 1: Standard JSON format {"tool": "name", "args": {...}}
            if "tool" in data and "args" in data:
                tool_call = data
                print("Matched Case 1")
                break
            # Case 2: Command R+ style (args only in JSON, tool name in text)
            elif cmd_r_match and isinstance(data, dict):
                tool_name = cmd_r_match.group(1)
                tool_call = {"tool": tool_name, "args": data}
                print("Matched Case 2")
                break
        except json.JSONDecodeError:
            print("JSON Decode Error")
            continue
            
    if tool_call:
        print(f"SUCCESS: Tool call found: {tool_call}")
    else:
        print("FAILURE: No tool call found.")

# User's error string
user_content = '<|channel|>commentary to=google_search <|constrain|>json<|message|>{"query":"Python ゲーム シミュレータ 無謀 か"}'
test_parsing(user_content)
