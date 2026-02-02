from typing import Dict, Any, List

# Central Registry for Tool Metada (Schema + Implementation Path)
# This file MUST NOT import heavy libraries (torch, numpy, etc.)

TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {
    # --- WEB TOOLS ---
    "web_navigate": {
        "impl": "src.cogs.tools.web_tools:navigate",
        "tags": ["browser", "web"],
        "schema": {
            "name": "web_navigate",
            "description": "Navigate the browser to a specific URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to navigate to."}
                },
                "required": ["url"]
            }
        }
    },
    "web_screenshot": {
        "impl": "src.cogs.tools.web_tools:screenshot",
        "tags": ["browser", "screenshot", "image"],
        "schema": {
            "name": "web_screenshot",
            "description": "Take a screenshot of the current page.",
            "parameters": {
                "type": "object",
                "properties": {
                    "full_page": {"type": "boolean", "description": "Whether to capture the full scrolling page."}
                }
            }
        }
    },
    "web_download": {
        "impl": "src.cogs.tools.web_tools:download",
        "tags": ["browser", "download", "save", "video", "image"],
        "schema": {
            "name": "web_download",
            "description": "Download media (video/image) from the current page/URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to download from (optional, defaults to current page)."},
                    "file_type": {"type": "string", "description": "Type of file to expect (video, image, audio)."}
                }
            }
        }
    },
    "web_record_screen": {
        "impl": "src.cogs.tools.web_tools:record_screen",
        "tags": ["browser", "record", "video"],
        "schema": {
            "name": "web_record_screen",
            "description": "Record a video of the browser viewport.",
            "parameters": {
                "type": "object",
                "properties": {
                    "duration": {"type": "integer", "description": "Duration in seconds."}
                },
                "required": ["duration"]
            }
        }
    },

    # --- VOICE / MUSIC TOOLS ---
    # Note: These might point to music_skill methods
    "music_play": {
        "impl": "src.cogs.tools.music_tools:play",
        "tags": ["voice", "music", "vc"],
        "schema": {
            "name": "music_play",
            "description": "Play music from a query or URL in VC.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query or URL."}
                },
                "required": ["query"]
            }
        }
    },
    "join_voice_channel": {
        "impl": "src.cogs.tools.music_tools:join",
        "tags": ["voice", "vc", "join"],
        "schema": {
            "name": "join_voice_channel",
            "description": "Join the user's voice channel.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    "leave_voice_channel": {
        "impl": "src.cogs.tools.music_tools:leave",
        "tags": ["voice", "vc", "leave"],
        "schema": {
            "name": "leave_voice_channel",
            "description": "Leave the voice channel.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    "tts_speak": {
        "impl": "src.cogs.tools.music_tools:speak", 
        "tags": ["voice", "tts", "speak"],
        "schema": {
            "name": "tts_speak",
            "description": "Speak text using TTS in VC.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to speak."}
                },
                "required": ["text"]
            }
        }
    },

    # --- MEDIA GEN TOOLS ---
    "dall-e_gen": {
        "impl": "src.cogs.tools.media_tools:generate_image",
        "tags": ["image", "generate", "create"],
        "schema": {
            "name": "dall-e_gen",
            "description": "Generate an image using DALL-E.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "Image description."}
                },
                "required": ["prompt"]
            }
        }
    },

    # --- SYSTEM TOOLS ---
    "system_info": {
        "impl": "src.cogs.tools.system_tools:info",
        "tags": ["system", "info", "memory"],
        "schema": {
            "name": "system_info",
            "description": "Get bot system status and memory info.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    "check_privilege": {
        "impl": "src.cogs.tools.system_tools:check_privilege",
        "tags": ["system", "auth"],
        "schema": {
             "name": "check_privilege",
             "description": "Check user privilege level.",
             "parameters": {"type": "object", "properties": {}}
        }
    },
    "router_health": {
        "impl": "src.cogs.tools.system_tools:router_health",
        "tags": ["system", "health", "monitor", "router"],
        "schema": {
            "name": "router_health",
            "description": "View real-time Router Health Metrics (S7). Fallback rates, Latency, Cache Stability.",
            "parameters": {"type": "object", "properties": {}}
        }
    }
}

def get_tool_schemas() -> List[Dict[str, Any]]:
    """Returns a list of tool definitions (JSON schemas) for the LLM."""
    schemas = []
    for key, data in TOOL_REGISTRY.items():
        # Inject tags into the schema for the Router to see?
        # Actually Router looks at tool['tags'] in our custom logic.
        # We should return a dict that includes 'tags' alongside the schema wrapper.
        
        # Structure matching available_tools in ToolSelector:
        # { "name": "...", "tags": [], ... (schema fields) }
        
        s = data["schema"].copy()
        s["tags"] = data["tags"]
        schemas.append(s)
    return schemas

def get_tool_impl(tool_name: str) -> str:
    """Returns the implementation path for a tool."""
    return TOOL_REGISTRY.get(tool_name, {}).get("impl")
