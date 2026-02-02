import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from src.utils.browser import browser_manager

async def test_run():
    print("🚀 Starting Isolated Browser Test...")
    try:
        print("1. Initializing Browser...")
        # Accessing the lazy property will trigger init
        # But we might need to explicit start if it's not auto
        # BrowserManager.__init__ is async? No, usually synch but calls async methods.
        # Let's try navigating.
        
        target_url = "https://www.google.com"
        print(f"2. Navigating to {target_url}...")
        await browser_manager.navigate(target_url)
        print("✅ Navigation Complete.")
        
        print("3. Taking Screenshot...")
        img = await browser_manager.get_screenshot()
        
        if img:
            print(f"✅ Screenshot taken. Size: {len(img)} bytes")
            with open("test_ss.jpg", "wb") as f:
                f.write(img)
            print("✅ Saved to test_ss.jpg")
        else:
            print("❌ No image data returned.")
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(test_run())
