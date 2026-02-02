import json

def debug_classification():
    # Simulate available tools (subset)
    available_tools = [
        {"name": "web_screenshot", "tags": ["view", "url", "screenshot"], "description": "Screenshot tool"},
        {"name": "web_download", "tags": ["save", "url", "download"], "description": "Download tool"},
        {"name": "join_voice", "tags": ["voice", "vc"], "description": "Join VC"},
    ]

    categories = {
        "WEB_SURFING": {"desc": "Web browsing...", "tools": []},
        "VOICE_AUDIO": {"desc": "Voice...", "tools": []},
        "OTHER": {"desc": "Other...", "tools": []}
    }

    # Same logic as tool_selector.py
    for tool in available_tools:
        name = tool["name"].lower()
        tags = tool.get("tags", [])
        tag_set = set(tags) if tags else set()
        
        if name.startswith("web_") or "browser" in tag_set or "url" in tag_set:
            categories["WEB_SURFING"]["tools"].append(tool)
        elif "voice" in name or "speak" in name or "tts" in tag_set or "vc" in tag_set:
            categories["VOICE_AUDIO"]["tools"].append(tool)
        else:
            categories["OTHER"]["tools"].append(tool)

    print("--- Classification Results ---")
    for cat, data in categories.items():
        tool_names = [t["name"] for t in data["tools"]]
        print(f"{cat}: {tool_names}")

    if "web_screenshot" in [t["name"] for t in categories["WEB_SURFING"]["tools"]]:
        print("✅ Classification Logic OK")
    else:
        print("❌ Classification Logic FAILED")

if __name__ == "__main__":
    debug_classification()
