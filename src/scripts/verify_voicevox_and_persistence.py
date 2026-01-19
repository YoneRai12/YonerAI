import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Add src to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load env variables explicitly
load_dotenv()

from config import STATE_DIR, Config
from utils.tts_client import VoiceVoxClient


async def main():
    print("=== TTS Verification ===")

    # 1. Load Config
    try:
        config = Config.load()
        print(f"✅ Config loaded. VoiceVox URL: {config.voicevox_api_url}")
    except Exception as e:
        print(f"❌ Failed to load config: {e}")
        return

    # 2. Test VoiceVox Connectivity
    client = VoiceVoxClient(config.voicevox_api_url, config.voicevox_speaker_id)
    try:
        speakers = await client.get_speakers()
        if speakers:
            print(f"✅ VoiceVox Connected. Found {len(speakers)} speakers.")
            print(f"   First speaker: {speakers[0]['name']}")
        else:
            print("⚠️ VoiceVox returned empty speaker list.")
    except Exception as e:
        print(f"❌ VoiceVox connection failed: {e}")

    # 3. Test Persistence Logic
    state_path = Path(STATE_DIR) / "user_voices.json"
    print(f"Testing persistence at: {state_path}")

    # Write Test
    test_data = {999999: 1}  # Test ID
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        # Load existing if any to preserve it
        existing = {}
        if state_path.exists():
            with open(state_path, "r", encoding="utf-8") as f:
                existing = json.load(f)

        # Update with test
        existing.update(test_data)

        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        print("✅ Write permission check passed.")

    except Exception as e:
        print(f"❌ Persistence write failed: {e}")

    print("=== Verification Complete ===")


if __name__ == "__main__":
    asyncio.run(main())
