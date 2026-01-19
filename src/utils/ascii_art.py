import io
import logging

import aiohttp
from PIL import Image, ImageOps

logger = logging.getLogger(__name__)


class AsciiGenerator:
    """Generates ASCII Art from images."""

    ASCII_CHARS = ["@", "#", "S", "%", "?", "*", "+", ";", ":", ",", "."]

    @staticmethod
    def resize_image(image: Image.Image, new_width: int = 100) -> Image.Image:
        width, height = image.size
        ratio = height / width
        # Adjust for typical font aspect ratio (approx 0.55)
        new_height = int(new_width * ratio * 0.55)
        return image.resize((new_width, new_height))

    @staticmethod
    def grayify(image: Image.Image) -> Image.Image:
        return ImageOps.grayscale(image)

    @classmethod
    def pixels_to_ascii(cls, image: Image.Image) -> str:
        pixels = image.getdata()
        characters = "".join([cls.ASCII_CHARS[pixel // 25] for pixel in pixels])
        return characters

    @classmethod
    async def generate_from_url(cls, url: str, width: int = 100) -> str:
        """Downloads an image and converts it to ASCII art."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        return "Error: Failed to download image."
                    data = await resp.read()

            image = Image.open(io.BytesIO(data))

            # Process
            image = cls.resize_image(image, width)
            image = cls.grayify(image)

            ascii_str = cls.pixels_to_ascii(image)

            # Format into lines
            ascii_img = ""
            for i in range(0, len(ascii_str), width):
                ascii_img += ascii_str[i : i + width] + "\n"

            return ascii_img

        except Exception as e:
            logger.error(f"ASCII Generation failed: {e}")
            return f"Error generating ASCII: {e}"
