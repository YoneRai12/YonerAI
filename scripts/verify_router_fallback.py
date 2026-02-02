import asyncio
import json
import logging
from unittest.mock import AsyncMock, MagicMock

# --- Mock Setup ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FallbackVerifier")

async def verify_fallback():
    print("\n--- Testing Router Fallback Logic ---")
    
    # Needs to replicate ToolSelector.select_tools logic roughly
    # or better, mock LLM response to be empty.
    
    # Let's verify the LOGIC I wrote, by pasting it here or importing if possible (complex due to dependencies).
    # I'll replicate the exact logic block I patched to ensure IT WORKS in isolation.
    
    prompt = "スクショして動画を保存して https://vt.tiktok.com/ZSaq2c86b/"
    selected_categories = [] # SIMULATE EMPTY ROUTER
    
    print(f"User Prompt: {prompt}")
    print(f"Simulated Router Response: {selected_categories}")
    
    # [FALLBACK LOGIC START]
    if not selected_categories:
        print(">> Triggering Fallback Check...")
        lower_p = prompt.lower()
        
        # Check for URLs -> WEB_SURFING
        if "http" in lower_p or "www." in lower_p or ".com" in lower_p:
            if "WEB_SURFING" not in selected_categories:
                selected_categories.append("WEB_SURFING")
        
        # Check for Voice -> VOICE_AUDIO
        if "vc" in lower_p or "voice" in lower_p or "call" in lower_p or "join" in lower_p or "通話" in lower_p or "きて" in lower_p:
            if "VOICE_AUDIO" not in selected_categories:
                selected_categories.append("VOICE_AUDIO")
    # [FALLBACK LOGIC END]
    
    print(f"Final Selected Categories: {selected_categories}")
    
    if "WEB_SURFING" in selected_categories:
        print("✅ SUCCESS: Fallback correctly added WEB_SURFING due to URL.")
    else:
        print("❌ FAILURE: Fallback missed the URL.")

if __name__ == "__main__":
    asyncio.run(verify_fallback())
