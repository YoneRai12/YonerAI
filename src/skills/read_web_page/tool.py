
import logging

import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

async def execute(args: dict, message=None) -> str:
    url = args.get("url")
    if not url:
        return "Error: No URL provided."

    try:
        logger.info(f"ReadPage: Reading {url}...")
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                if resp.status != 200:
                    return f"Error: Failed to fetch page (Status {resp.status})"
                
                html = await resp.text()
                
        # Simple Text Extraction
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove scripts and styles
        for script in soup(["script", "style"]):
            script.decompose()
            
        text = soup.get_text(separator="\n")
        
        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        # Truncate if too long
        if len(text) > 4000:
            text = text[:4000] + "\n...(Content Truncated)..."
            
        return f"### Content of {url}\n\n{text}"

    except Exception as e:
        logger.error(f"ReadPage Error: {e}")
        return f"Access Error: {e}"
