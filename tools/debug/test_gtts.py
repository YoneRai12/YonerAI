import asyncio

from src.utils.gtts_client import GTTSClient


async def main():
    client = GTTSClient()
    print("Synthesizing text with gTTS...")
    try:
        audio = await client.synthesize("こんにちは、これはgTTSのテストです。")
        if audio:
            print(f"Success! Received {len(audio)} bytes.")
            with open("test_gtts.mp3", "wb") as f:
                f.write(audio)
        else:
            print("Failed: No audio data received.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
