import asyncio
import logging
import sys
import os
import re

# Logic to test (must match src/cogs/handlers/tool_selector.py)
def simulate_router_fallback(prompt: str):
    lower_p = prompt.strip().lower()
    selected = ["SYSTEM_UTIL"]

    # Robust URL detection
    has_url = re.search(r'https?://[^\s]+', lower_p) is not None

    # Simple Browsing & Searching (Safe)
    search_keywords = ["検索", "調べて", "調査", "教えて", "見せて", "探し", "wiki", "google", "search", "browse", "whois", "誰", "何者", "クローム", "chrome", "記事", "サイト"]
    if has_url or any(k in lower_p for k in search_keywords) or any(k in lower_p for k in ["http", "google", "開いて", "スクショ", "撮って", "screenshot"]):
         selected.append("WEB_READ")

    # WEB_FETCH
    download_keywords = ["save", "download", "fetch", "record", "保存", "ダウンロード", "落として", "録画", "持ってきて"]
    if (has_url or any(k in lower_p for k in ["動画", "ビデオ", "mp4"])) and any(k in lower_p for k in download_keywords):
         selected.append("WEB_FETCH")

    # Voice
    if any(k in lower_p for k in ["vc", "join", "leave", "music", "play", "speak", "voice", "歌って", "流して"]):
         selected.append("VOICE_AUDIO")

    # Discord
    # Expanded: ロール, 権限, 誰, 何
    if any(k in lower_p for k in ["server", "user", "info", "role", "whois", "鯖", "ユーザー", "誰", "ロール", "権限", "何"]):
         selected.append("DISCORD_SERVER")

    return selected

async def test_router_japanese():
    test_cases = [
        ("YoneRai12について検索して", ["WEB_READ"]),
        ("YoutubeでYoneRai12のチャンネルを開きスクショ", ["WEB_READ"]),
        ("動画をダウンロードして https://example.com/v", ["WEB_FETCH", "WEB_READ"]),
        ("VCに来て", ["VOICE_AUDIO"]),
        ("この人のロールは何？", ["DISCORD_SERVER"]),
        ("CDPについて．クローム", ["WEB_READ"]),
        ("何者か教えて", ["WEB_READ", "DISCORD_SERVER"]),
    ]

    print("\n--- Router Japanese Heuristic Test (Fallback Scenario) ---")
    all_passed = True
    for prompt, expected_cats in test_cases:
        selected = simulate_router_fallback(prompt)
        success = all(cat in selected for cat in expected_cats)
        print(f"Prompt: {prompt}")
        print(f"Selected: {selected}")
        print(f"Result: {'✅' if success else '❌'}")
        if not success:
            print(f"Missing: {set(expected_cats) - set(selected)}")
            all_passed = False

    if all_passed:
        print("\n✨ All Japanese heuristics passed!")
    else:
        print("\n⚠️ Some cases failed.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_router_japanese())
