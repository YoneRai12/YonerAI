import logging
import mss
import mss.tools
import io
from typing import Optional, Dict, Any
from . import image_tools

logger = logging.getLogger(__name__)

class DesktopWatcher:
    def __init__(self):
        pass

    def capture_screen(self) -> Optional[bytes]:
        """Capture the primary monitor and return PNG bytes."""
        try:
            with mss.mss() as sct:
                # Capture primary monitor (monitor 1)
                if not sct.monitors:
                    return None
                monitor = sct.monitors[1]
                sct_img = sct.grab(monitor)
                
                # Convert to PNG bytes
                return mss.tools.to_png(sct_img.rgb, sct_img.size)
        except Exception as e:
            logger.error(f"Screen capture failed: {e}")
            return None

    def analyze_screen(self) -> Optional[Dict[str, Any]]:
        """Capture and analyze the screen."""
        png_bytes = self.capture_screen()
        if not png_bytes:
            return None
        
        try:
            # Use existing vision tool
            # Note: analyze_image_structured might be slow, so run in thread if needed
            result = image_tools.analyze_image_structured(png_bytes)
            return result
        except Exception as e:
            logger.error(f"Screen analysis failed: {e}")
            return None
