import os
import asyncio
from openai import AsyncOpenAI

# Load key from .env manually to be sure
from dotenv import load_dotenv
load_dotenv()

async def test_key():
    api_key = os.getenv("OPENAI_API_KEY")
    print(f"Loaded Key: {api_key[:10]}...{api_key[-5:] if api_key else 'None'}")
    
    client = AsyncOpenAI(api_key=api_key)
    
    try:
        print("Sending request to gpt-4o-mini...")
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=10
        )
        print(f"Success! Response: {resp.choices[0].message.content}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_key())
