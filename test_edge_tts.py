import asyncio
import edge_tts

async def test_voice(voice, text):
    print(f"Testing voice: {voice}")
    communicate = edge_tts.Communicate(text, voice)
    audio_data = bytearray()
    try:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data.extend(chunk["data"])
        
        if audio_data:
            print(f"Success! Received {len(audio_data)} bytes.")
            with open(f"test_{voice}.mp3", "wb") as f:
                f.write(audio_data)
        else:
            print("Failed: No audio data received.")
    except Exception as e:
        print(f"Error: {e}")

async def main():
    try:
        voices = await edge_tts.list_voices()
        print(f"Found {len(voices)} voices.")
        ja_voices = [v['ShortName'] for v in voices if "ja-JP" in v['ShortName']]
        print(f"Japanese voices: {ja_voices}")
        
        if ja_voices:
            for voice in ja_voices:
                print(f"--- Testing {voice} ---")
                await test_voice(voice, "こんにちは。")
                await asyncio.sleep(1) # Be nice to the API
    except Exception as e:
        print(f"Failed to list voices: {e}")

if __name__ == "__main__":
    asyncio.run(main())
