import asyncio

import aiohttp


async def check_voicevox():
    base_url = "http://127.0.0.1:50021"
    
    async with aiohttp.ClientSession() as session:
        # 1. Check Version
        try:
            async with session.get(f"{base_url}/version") as resp:
                if resp.status == 200:
                    version = await resp.json()
                    print(f"VOICEVOX Version: {version}")
                else:
                    print(f"Failed to get version: {resp.status}")
        except Exception as e:
            print(f"Connection failed: {e}")
            return

        # 2. Check Speakers
        try:
            async with session.get(f"{base_url}/speakers") as resp:
                if resp.status == 200:
                    speakers = await resp.json()
                    print(f"Fetched {len(speakers)} speakers.")
                    
                    # Check for Speaker ID 1 (Zundamon)
                    found = False
                    for speaker in speakers:
                        for style in speaker.get("styles", []):
                            if style.get("id") == 1:
                                print(f"Found Speaker ID 1: {speaker.get('name')} - {style.get('name')}")
                                found = True
                                break
                        if found: break
                    
                    if not found:
                        print("WARNING: Speaker ID 1 NOT found in available speakers!")
                        # Print first available speaker
                        if speakers and speakers[0].get("styles"):
                            first_id = speakers[0]["styles"][0]["id"]
                            print(f"Suggestion: Try using Speaker ID {first_id} ({speakers[0]['name']})")
                else:
                    print(f"Failed to get speakers: {resp.status}")
        except Exception as e:
            print(f"Failed to fetch speakers: {e}")

if __name__ == "__main__":
    asyncio.run(check_voicevox())
