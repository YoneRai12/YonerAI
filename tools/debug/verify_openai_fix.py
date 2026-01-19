
import asyncio
import os
import sys

# Add root dir to sys.path to allow imports
sys.path.append(os.getcwd())

from dotenv import load_dotenv

from src.utils.llm_client import LLMClient

# Load Env explicitly
env_path = r"C:\Users\YoneRai12\Desktop\ORADiscordBOT-main3\.env"
load_dotenv(env_path, override=True)
key = os.getenv("OPENAI_API_KEY")

async def main():
    if not key:
        print("ERROR: No API Key found.")
        return

    print(f"Testing with Key: {key[:10]}... (Length: {len(key)})")
    
    # Use the same model as configured
    model = "gpt-5-mini" # Or whatever matches the user's expectation
    
    client = LLMClient("https://api.openai.com/v1", key, model)
    
    print(f"Sending request to {model} with temperature=None...")
    try:
        # User message
        msgs = [{"role": "user", "content": "Hello. If you can read this, just say 'SUCCESS'."}]
        
        # This calls the patched logic
        resp = await client.chat(msgs, temperature=None)
        
        print("-" * 20)
        print(f"RESPONSE: {resp}")
        print("-" * 20)
        print("✅ VERIFICATION PASSED: No 400 Error. Parameters are correct.")
        
    except Exception as e:
        print(f"❌ FAILED: {e}")
        print("Detailed traceback may be needed if 400 error persists.")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
