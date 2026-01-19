
import asyncio
import logging

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestCycle")

# Mock ResourceManager for safety (we don't want to actually kill the user's running processes if possible, but user asked to verify)
# User asked "Make it and Verify it".
# Verification means actually testing the real manager.
# I will import the real manager but override the 'subprocess.run' to just print what it WOULD do for the 'start' commands, 
# but allow the 'kill' commands to run (since user's system is messed up anyway).
# actually, real verification is best.

from src.managers.resource_manager import ResourceManager


async def test_cycle():
    rm = ResourceManager()
    
    print("\n--- [1] Testing Image Context Switch (Kill vLLM, Start Comfy) ---")
    # This should trigger the "Scanning WSL distros" log
    await rm.switch_context("image")
    
    print("\n--- [2] Simulating Generation Delay (3s) ---")
    await asyncio.sleep(3)
    
    print("\n--- [3] Testing Return to LLM (Kill Comfy, Start vLLM) ---")
    # This should kill Comfy and start vLLM script
    # Note: This will actually launch the batch file window!
    await rm.switch_context("llm")
    
    print("\n✅ Cycle Test Complete. Please check if 'ORA vLLM Server' window opened.")

if __name__ == "__main__":
    try:
        asyncio.run(test_cycle())
    except KeyboardInterrupt:
        pass
