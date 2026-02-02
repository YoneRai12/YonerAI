import logging
from typing import Optional

logger = logging.getLogger(__name__)

class RAGHandler:
    def __init__(self, bot):
        self.bot = bot

    async def get_context(self, prompt: str, user_id: str, guild_id: Optional[str] = None) -> str:
        """
        Retrieves relevant context from Vector Memory based on the prompt.
        Returns a formatted string suitable for injection into the system prompt.
        """
        rag_context = ""
        
        # Check if vector memory is available on the bot
        if hasattr(self.bot, "vector_memory") and self.bot.vector_memory:
            try:
                memories = await self.bot.vector_memory.search_memory(
                    query=prompt,
                    user_id=user_id,
                    guild_id=guild_id,
                    limit=3
                )
                
                if memories:
                    # Format as a distinct block
                    rag_context = "\n[Relevant Past Memories]:\n" + "\n".join([f"- {m}" for m in memories]) + "\n"
                    logger.info(f"RAG: Injected {len(memories)} memories.")
            
            except Exception as e:
                logger.warning(f"RAG Retrieval Failed: {e}")
                
        return rag_context
