import asyncio
import logging

import aiohttp
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)

class WebSkill:
    """Skill for Web Browsing and Searching."""
    
    def __init__(self, bot=None):
        self.bot = bot
        self.ddgs = DDGS()

    async def search(self, query: str, max_results: int = 3) -> str:
        """
        Search the web using DuckDuckGo.
        """
        try:
            logger.info(f"WebSkill: Searching for '{query}'...")
            # Use run_in_executor if needed, but DDGS is synch mostly. 
            # library might have async now? assuming sync for safety wrapped in executor or just direct if fast.
            # DDGS().text is sync.
            loop = asyncio.get_running_loop()
            results = await loop.run_in_executor(None, lambda: self.ddgs.text(query, max_results=max_results))
            
            if not results:
                return "No results found."
                
            formatted = []
            for r in results:
                formatted.append(f"### {r['title']}\n{r['body']}\nSource: {r['href']}")
            
            return "\n\n".join(formatted)
        except Exception as e:
            logger.error(f"WebSearch Error: {e}")
            return f"Search Error: {str(e)}"

    async def read_page(self, url: str) -> str:
        """
        Fetch and read the content of a specific URL.
        Useful for analyzing GitHub repos, articles, etc.
        """
        try:
            logger.info(f"WebSkill: Reading {url}...")
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
            
            # Truncate if too long (Discord limits / Token limits)
            if len(text) > 4000:
                text = text[:4000] + "\n...(Content Truncated)..."
                
            return f"### Content of {url}\n\n{text}"

        except Exception as e:
            logger.error(f"ReadPage Error: {e}")
            return f"Detailed Access Error: {str(e)}"
