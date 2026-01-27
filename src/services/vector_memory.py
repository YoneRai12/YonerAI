
import logging
import os
import asyncio
from datetime import datetime
from typing import List, Dict, Optional, Any
import chromadb
from chromadb.config import Settings

from src.config import Config
import sys

# Load config to get the correct path
try:
    _cfg = Config.load()
    DB_DIR = os.path.join(_cfg.db_path.replace("ora_bot.db", ""), "vector_store")
    # Better: Use MEMORY_DIR from config module if available, or load it
    from src.config import MEMORY_DIR
    DB_DIR = os.path.join(MEMORY_DIR, "vector_store")
except ImportError:
    # Fallback to local if config import fails (circular dependency risk)
    DB_DIR = os.path.join(os.getcwd(), "data", "vector_store")

logger = logging.getLogger(__name__)

class VectorMemory:
    """
    Long-term Semantic Memory using ChromaDB.
    Stores conversation snippets as vectors for RAG (Retrieval Augmented Generation).
    """
    def __init__(self, collection_name: str = "ora_memory"):
        self.client = chromadb.PersistentClient(path=DB_DIR)
        
        # Use default embedding function (all-MiniLM-L6-v2) for now to keep it local/free.
        # Ideally switch to OpenAI for better quality if budget allows.
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        logger.info(f"VectorMemory initialized at {DB_DIR} (Collection: {collection_name})")

    async def add_memory(self, 
                         text: str, 
                         user_id: str, 
                         metadata: Optional[Dict[str, Any]] = None):
        """Add a text snippet to the vector database."""
        if not text or len(text.strip()) < 5:
            return # Ignore noise

        if metadata is None:
            metadata = {}
        
        # Ensure metadata values are primitives
        clean_meta = {
            "user_id": str(user_id),
            "timestamp": datetime.now().isoformat(),
            **{k: str(v) for k, v in metadata.items() if v is not None}
        }

        # Generate ID based on timestamp and hash
        import hashlib
        doc_id = hashlib.md5(f"{text}{datetime.now().timestamp()}".encode()).hexdigest()

        try:
            self.collection.add(
                documents=[text],
                metadatas=[clean_meta],
                ids=[doc_id]
            )
        except Exception as e:
            logger.error(f"Failed to add memory: {e}")

    async def search_memory(self, 
                            query: str, 
                            user_id: Optional[str] = None, 
                            guild_id: Optional[str] = None,
                            limit: int = 5,
                            threshold: float = 0.6) -> List[str]:
        """
        Retrieve relevant memories. Supports User + Guild (Shared) scope.
        Args:
            query: The search text.
            user_id: Filter by this user (Private Memory).
            guild_id: Filter by this guild (Shared Memory).
        """
        try:
            # Complex filtering logic for Chroma is limited in basic API.
            # We want: (user_id == UID) OR (guild_id == GID)
            # Chroma's $or requires exact matches.
            
            where_clause = None
            if user_id and guild_id:
                where_clause = {
                    "$or": [
                        {"user_id": str(user_id)},
                        {"guild_id": str(guild_id)}
                    ]
                }
            elif user_id:
                where_clause = {"user_id": str(user_id)}
            elif guild_id:
                where_clause = {"guild_id": str(guild_id)}

            results = self.collection.query(
                query_texts=[query],
                n_results=limit,
                where=where_clause
            )

            # Results structure: {'documents': [[...]], 'distances': [[...]], ...}
            memories = []
            if results["documents"] and results["distances"]:
                docs = results["documents"][0]
                dists = results["distances"][0]

                for doc, dist in zip(docs, dists):
                    # Filter by relevance (heuristic)
                    if dist < threshold: 
                        memories.append(doc)
            
            return memories

        except Exception as e:
            logger.error(f"Memory search failed: {e}")
            return []

    async def wipe_user_memory(self, user_id: str):
        """Delete all memories for a user."""
        try:
            self.collection.delete(where={"user_id": str(user_id)})
            logger.info(f"Wiped vector memory for {user_id}")
        except Exception as e:
            logger.error(f"Failed to wipe memory: {e}")
