import asyncio
import logging
from typing import Optional
from src.utils.browser_agent import BrowserAgent

logger = logging.getLogger(__name__)

class BrowserManager:
    """
    Manages a persistent BrowserAgent session (Adapter Pattern).
    Provides backward compatibility for the API router while using the robust Agent.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(BrowserManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, headless: bool = True):
        if hasattr(self, "agent"):
            return
            
        self.headless = headless
        self.headless = headless
        self.agent = BrowserAgent()
        self._lock = asyncio.Lock()
        self.is_recording = False
        self.recording_dir = None
        self.last_url = None

    def is_ready(self) -> bool:
        """Returns True if the browser agent is started and ready."""
        return self.agent.is_started()

    async def start_recording(self) -> bool:
        """Restarts the browser in recording mode."""
        import os
        import tempfile
        from src.config import TEMP_DIR
        
        if self.is_recording: return False
        
        # Save current state
        if self.page:
             try: self.last_url = self.page.url
             except: pass
        
        await self.close()
        
        os.makedirs(TEMP_DIR, exist_ok=True)
        self.recording_dir = tempfile.mkdtemp(dir=TEMP_DIR)
        async with self._lock:
            # Restart with recording options
            await self.agent.start(
                headless=self.headless, 
                record_video_dir=self.recording_dir,
                record_video_size={"width": 1280, "height": 720}
            )
            self.is_recording = True
            logger.info(f"Started recording to {self.recording_dir}")
            
            # Restore state
            if self.last_url and self.last_url != "about:blank":
                try: await self.agent.act({"type": "goto", "url": self.last_url})
                except: pass
        return True

    async def stop_recording(self) -> Optional[str]:
        """Stops recording and returns path to the video file."""
        import glob
        import shutil
        
        if not self.is_recording or not self.recording_dir:
            return None
            
        # Save current state again for restoration
        if self.page:
             try: self.last_url = self.page.url
             except: pass
             
        # Closing the context triggers the video save
        await self.close()
        
        # Find the video file
        video_path = None
        try:
            files = glob.glob(os.path.join(self.recording_dir, "*.webm"))
            if files:
                video_path = files[0] # Usually only one file per context page
        except Exception as e:
            logger.error(f"Failed to find recorded video: {e}")
            
        self.is_recording = False
        
        # Restart normal session
        await self.start()
        
        # Restore URL if possible
        if self.last_url:
             try: await self.navigate(self.last_url)
             except: pass
             
        return video_path

    @property
    def page(self):
        try:
            return self.agent.page
        except RuntimeError:
            return None

    async def start(self):
        """Starts the BrowserAgent."""
        async with self._lock:
            if not self.agent.is_started():
                await self.agent.start(headless=self.headless)
                logger.info(f"BrowserAgent started (Headless: {self.headless})")
                
                # Default homepage
                try:
                    await self.agent.act({"type": "goto", "url": "https://google.com"})
                except Exception as e:
                    logger.warning(f"Failed to load default homepage: {e}")

    async def ensure_active(self):
        """Ensures the browser is active."""
        if not self.agent.is_started() or self.agent.needs_restart():
            await self.start()

    async def close(self):
        """Closes the BrowserAgent."""
        async with self._lock:
            await self.agent.close()
            logger.info("BrowserAgent closed.")

    async def navigate(self, url: str) -> str:
        """Navigates to a URL and returns the page title."""
        # SECURITY BLOCKLIST
        BLOCKED_DOMAINS = [
            "whatismyip", "ipinfo.io", "cman.jp", "whoer.net", "checkip", "ifconfig.me", "ip-api.com",
            "on-ze.com", "systemexpress.co.jp", "geolocation", "device-info"
        ]
        
        # [PARANOID SECURITY] Local Access Prevention
        # 1. Block Local File System Access
        if url.lower().startswith("file://") or url.lower().startswith("file:"):
            logger.warning(f"Blocked local file access attempt: {url}")
            raise Exception("Security Block: Accessing local files is strictly prohibited.")
            
        # 2. Block Local/Private IP Ranges (Prevent internal network scanning)
        # 127.0.0.1, 192.168.*, 10.*, 172.16.*, localhost
        PRIVATE_IPS = ["127.0.0.1", "localhost", "192.168.", "10.", "172.16."]
        if any(ip in url for ip in PRIVATE_IPS):
             # Exception: Allow localhost ONLY if specifically configured for internal API testing?
             # For now, block everything for safety.
             logger.warning(f"Blocked local network access attempt: {url}")
             raise Exception("Security Block: Accessing local network addresses is restricted.")

        if any(bad in url.lower() for bad in BLOCKED_DOMAINS):
            logger.warning(f"Blocked navigation to sensitive site: {url}")
            raise Exception("Security Block: Accessing IP checking sites is restricted to protect server identity.")

        await self.ensure_active()
        try:
            result = await self.agent.act({"type": "goto", "url": url})
            if not result["ok"]:
                raise Exception(result["error"])
            return result["observation"]["title"]
        except Exception as e:
            logger.error(f"Navigation failed: {e}")
            raise

    async def get_screenshot(self) -> bytes:
        """Returns the current page screenshot as bytes."""
        await self.ensure_active()
        try:
            p = self.agent.page
            if not p:
                raise Exception("Browser page is not available.")
            
            # Simple retry for screenshot
            for attempt in range(2):
                try:
                    return await p.screenshot(type='jpeg', quality=80, timeout=10000)
                except Exception as e:
                    if attempt == 0:
                        await asyncio.sleep(1)
                        continue
                    raise e
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            raise

    async def click_at(self, x: int, y: int):
        """Clicks at specific coordinates."""
        await self.ensure_active()
        try:
            await self.agent.page.mouse.click(x, y)
        except Exception as e:
            logger.error(f"Click failed at {x}, {y}: {e}")
            raise

    async def type_text(self, text: str):
        """Types text into the focused element."""
        # This assumes focus is already set. 
        # BrowserAgent.act('type') expects a selector/ref.
        # We can use page.keyboard directly.
        await self.ensure_active()
        try:
            await self.agent.page.keyboard.type(text)
        except Exception as e:
            logger.error(f"Type failed: {e}")
            raise

    async def press_key(self, key: str):
        """Presses a specific key (e.g. 'Enter', 'Backspace')."""
        await self.ensure_active()
        try:
            await self.agent.act({"type": "press", "key": key})
        except Exception as e:
            logger.error(f"Key press failed: {e}")
            raise

    async def scroll(self, delta_x: int, delta_y: int):
        """Scrolls the page."""
        await self.ensure_active()
        try:
            await self.agent.act({"type": "scroll", "delta_x": delta_x, "delta_y": delta_y, "after_ms": 0})
        except Exception as e:
            logger.error(f"Scroll failed: {e}")
            raise

    async def set_view(self, width: Optional[int] = None, height: Optional[int] = None, 
                      dark_mode: Optional[bool] = None, scale: Optional[float] = None):
        """Configures the viewport and visual settings."""
        await self.ensure_active()
        page = self.agent.page
        
        try:
            # 1. Viewport (Mobile/Vertical)
            if width and height:
                await page.set_viewport_size({"width": width, "height": height})
            
            # 2. Dark Mode
            if dark_mode is not None:
                scheme = 'dark' if dark_mode else 'light'
                await page.emulate_media(color_scheme=scheme)
                
                # FORCE Dark Mode via CSS Injection (for sites like Google that ignore preference)
                if dark_mode:
                    js_force_dark = """
                    () => {
                        const style = document.createElement('style');
                        style.innerHTML = `
                            html { filter: invert(0.9) hue-rotate(180deg) !important; }
                            img, video, iframe, canvas { filter: invert(1) hue-rotate(180deg) !important; }
                        `;
                        document.head.appendChild(style);
                    }
                    """
                    try:
                        await page.evaluate(js_force_dark)
                    except Exception:
                        pass
            
            # 3. Scale (Zoom) - CSS Transform on Body
            if scale is not None:
                # Reset first then apply
                await page.evaluate("document.body.style.transformOrigin = '0 0';")
                await page.evaluate(f"document.body.style.transform = 'scale({scale})';")
                
        except Exception as e:
            logger.error(f"Failed to set view: {e}")
            raise


# Singleton instance
browser_manager = BrowserManager(headless=True)
