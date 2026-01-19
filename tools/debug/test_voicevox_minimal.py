import asyncio

import aiohttp


async def test_synthesis_minimal():
    base_url = "http://127.0.0.1:50021"
    speaker_id = 3 # Zundamon Normal
    text = "テスト"

    async with aiohttp.ClientSession() as session:
        print(f"Testing Speaker ID {speaker_id} (Zundamon Normal)...")
        
        # 1. Audio Query
        query_url = f"{base_url}/audio_query"
        params = {"text": text, "speaker": speaker_id}
        
        try:
            async with session.post(query_url, params=params) as resp:
                if resp.status != 200:
                    print(f"Audio Query failed: {resp.status}")
                    return
                query_data = await resp.json()
                print("Audio Query successful.")
        except Exception as e:
            print(f"Audio Query connection failed: {e}")
            return

        # 2. Synthesis
        synth_url = f"{base_url}/synthesis"
        synth_params = {"speaker": speaker_id}
        headers = {"Content-Type": "application/json"}
        
        try:
            async with session.post(synth_url, params=synth_params, json=query_data, headers=headers) as resp:
                if resp.status == 200:
                    audio = await resp.read()
                    print(f"Synthesis SUCCESS! Audio size: {len(audio)} bytes")
                    with open("test_success.wav", "wb") as f:
                        f.write(audio)
                else:
                    body = await resp.text()
                    print(f"Synthesis failed: {resp.status} {body}")
        except Exception as e:
            print(f"Synthesis connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_synthesis_minimal())
