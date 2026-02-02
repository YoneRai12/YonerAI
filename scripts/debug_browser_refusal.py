import json

def debug_browser_classification():
    prompt = "ブラウザで開いてhttps://vt.tiktok.com/ZSaq2c86b/"
    selected_categories = [] # Simulate Router Failure (Empty)

    print(f"User Prompt: {prompt}")
    
    # [CURRENT FALLBACK LOGIC REPLICATION]
    lower_p = prompt.lower()
    
    # Check for URLs -> WEB_SURFING
    # The user prompt has "https"
    if "http" in lower_p or "www." in lower_p or ".com" in lower_p:
        if "WEB_SURFING" not in selected_categories:
            selected_categories.append("WEB_SURFING")
            print("Fallback triggered by URL (http)")

    # Check for Voice
    if "vc" in lower_p or "voice" in lower_p or "call" in lower_p or "join" in lower_p or "通話" in lower_p or "きて" in lower_p:
        if "VOICE_AUDIO" not in selected_categories:
            selected_categories.append("VOICE_AUDIO")
            
    print(f"Result: {selected_categories}")

    if "WEB_SURFING" in selected_categories:
        print("✅ Fallback worked (in theory)")
    else:
        print("❌ Fallback FAILED")

if __name__ == "__main__":
    debug_browser_classification()
