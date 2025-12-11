import asyncio
import aiohttp
import json

async def test_voicevox():
    base_url = "http://127.0.0.1:50021"
    speaker_id = 1
    text = "テスト"

    async with aiohttp.ClientSession() as session:
        # 1. Audio Query
        query_url = f"{base_url}/audio_query"
        params = {"text": text, "speaker": speaker_id}
        print(f"Sending audio_query to {query_url} with params={params}")
        
        async with session.post(query_url, params=params) as resp:
            if resp.status != 200:
                print(f"Audio query failed: {resp.status} {await resp.text()}")
                return
            query = await resp.json()
            print("Audio query success.")
            
            # Save query to file for inspection
            with open("debug_query.json", "w", encoding="utf-8") as f:
                json.dump(query, f, indent=2, ensure_ascii=False)

        # 2. Synthesis
        synthesis_url = f"{base_url}/synthesis"
        synth_params = {"speaker": speaker_id, "enable_interrogative_upspeak": "true"}
        print(f"Sending synthesis to {synthesis_url} with params={synth_params}")
        
        # Manually serialize JSON
        headers = {"Content-Type": "application/json"}
        async with session.post(synthesis_url, params=synth_params, data=json.dumps(query), headers=headers) as resp:
            if resp.status != 200:
                print(f"Synthesis failed: {resp.status} {await resp.text()}")
                return
            audio = await resp.read()
            print(f"Synthesis success! Received {len(audio)} bytes.")
            
            with open("test_output.wav", "wb") as f:
                f.write(audio)
            print("Saved to test_output.wav")

if __name__ == "__main__":
    asyncio.run(test_voicevox())
