
import json
import random

# Output File
OUTPUT_FILE = "src/training/ora_tool_dataset.jsonl"

# ORA Tool Definitions (Templates)
TOOLS = {
    "generate_image": {
        "description": "Generates an image based on a prompt.",
        "patterns": [
            ("Draw a {prompt}", "generate_image", {"prompt": "{prompt}"}),
            ("Create an image of {prompt}", "generate_image", {"prompt": "{prompt}"}),
            ("Generate {prompt}", "generate_image", {"prompt": "{prompt}"}),
            ("I want to see {prompt}", "generate_image", {"prompt": "{prompt}"})
        ],
        "args": ["prompt"]
    },
    "web_search": {
        "description": "Searches the web for information.",
        "patterns": [
            ("Search for {query}", "web_search", {"query": "{query}"}),
            ("Google {query}", "web_search", {"query": "{query}"}),
            ("Find info about {query}", "web_search", {"query": "{query}"}),
            ("What is {query}?", "web_search", {"query": "{query}"})
        ],
        "args": ["query"]
    },
    "speak_text": {
        "description": "Speaks the provided text in voice chat.",
        "patterns": [
            ("Say {text}", "speak", {"text": "{text}"}),
            ("Speak {text}", "speak", {"text": "{text}"}),
            ("Read this aloud: {text}", "speak", {"text": "{text}"})
        ],
        "args": ["text"]
    },
     "doppelganger": {
        "description": "Clones a user's voice from audio attachment.",
        "patterns": [
            ("Clone this voice", "doppelganger", {}),
            ("Learn my voice from this audio", "doppelganger", {}),
            ("Register this as my doppelganger", "doppelganger", {})
        ],
        "args": []
    }
}

# Domain Data (to fill templates)
PROMPTS = ["cyberpunk city", "cute cat", "space station", "fantasy dragon", "Tesla Cybertruck", "anime girl", "forest landscape"]
QUERIES = ["latest RTX 5090 price", "weather in Tokyo", "how to cook pasta", "Python async tutorial", "history of Rome"]
TEXTS = ["Hello world", "System online", "Initiating shutdown", "Welcome to the server", "I am ORA"]

SYSTEM_PROMPT = """You are ORA, an advanced AI Assistant.
Your goal is to assist the user by calling the appropriate tool.
Output your thought process, followed by a JSON object containing the tool call.
JSON Schema: {"tool": "tool_name", "args": { ... }}"""

def generate_example():
    tool_key = random.choice(list(TOOLS.keys()))
    tool_def = TOOLS[tool_key]
    
    # Pick a pattern
    pattern_template, tool_name, args_template = random.choice(tool_def["patterns"])
    
    # Fill Slots
    if "{prompt}" in pattern_template:
        val = random.choice(PROMPTS)
        user_input = pattern_template.format(prompt=val)
        args = {k: v.format(prompt=val) for k, v in args_template.items()}
    elif "{query}" in pattern_template:
        val = random.choice(QUERIES)
        user_input = pattern_template.format(query=val)
        args = {k: v.format(query=val) for k, v in args_template.items()}
    elif "{text}" in pattern_template:
        val = random.choice(TEXTS)
        user_input = pattern_template.format(text=val)
        args = {k: v.format(text=val) for k, v in args_template.items()}
    else:
        user_input = pattern_template
        args = args_template

    # Construct Output
    thought = f"The user wants to {tool_key.replace('_', ' ')}. I should call the {tool_name} tool."
    tool_json = json.dumps({"tool": tool_name, "args": args})
    
    # ChatML Format
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": f"{thought}\n```json\n{tool_json}\n```"}
        ]
    }

def main():
    print(f"Generating 1000 examples to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for _ in range(1000):
            ex = generate_example()
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    print("Done!")

if __name__ == "__main__":
    main()
