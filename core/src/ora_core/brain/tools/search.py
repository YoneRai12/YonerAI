import logging
from typing import Any, Dict, List
from duckduckgo_search import DDGS
from .base import BaseTool, ToolContext

logger = logging.getLogger(__name__)

class SearchTool(BaseTool):
    @property
    def name(self) -> str:
        return "google_search" # Keep name for backward compatibility/LLM training

    @property
    def description(self) -> str:
        return "Search the web for current information, news, or specific facts."

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query."}
            },
            "required": ["query"]
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        query = args.get("query")
        if not query:
            return "Error: No query provided."

        try:
            # Note: DDGS is synchronous, but often used in threads or small bursts.
            # In a truly high-concurrency core, we'd wrap this in run_in_executor.
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=5))
            
            if not results:
                return "No results found for that query."

            formatted = []
            for r in results:
                title = r.get("title", "No Title")
                body = r.get("body", "")
                href = r.get("href", "")
                formatted.append(f"### {title}\nURL: {href}\n{body}")

            return "\n\n".join(formatted)

        except Exception as e:
            logger.exception(f"SearchTool failed for query: {query}")
            return f"Search error occured: {str(e)}"
