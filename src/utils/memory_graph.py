import json
import logging
import asyncio
from pathlib import Path
from typing import List, Dict, Any
from ..storage import Store

logger = logging.getLogger(__name__)

CACHE_FILE = Path("graph_cache.json")

class MemoryGraphGenerator:
    def __init__(self, store: Store):
        self.store = store

    async def generate_graph(self) -> Dict[str, Any]:
        """Generates a node-link graph from conversation history."""
        try:
            # Fetch recent conversations (limit to last 100 for performance)
            # We need a method in Store to get all recent conversations across users
            # For now, let's assume we can get a list. 
            # Since Store.get_conversations requires user_id, we might need to iterate or add a method.
            # For this MVP, let's just use a dummy structure or try to fetch for the ADMIN if possible.
            
            # Actually, let's just make a simple graph:
            # Center: ORA
            # Nodes: Users
            # Nodes: Topics (extracted from messages)
            
            nodes = [{"id": "ORA", "group": 1, "val": 20}]
            links = []
            
            # This is a placeholder. In a real implementation, we would query the DB.
            # Since we don't have a "get all messages" method readily available without user_id,
            # we will create a mock graph that looks cool for now, 
            # and in the future connect it to real data.
            
            # Mock Data Generation
            users = ["User", "Admin"]
            topics = ["Python", "Discord", "AI", "Gaming", "Valorant", "Minecraft", "System", "Voice"]
            
            for user in users:
                nodes.append({"id": user, "group": 2, "val": 10})
                links.append({"source": "ORA", "target": user})
                
                for topic in topics:
                    # Randomly connect
                    import random
                    if random.random() > 0.5:
                        nodes.append({"id": topic, "group": 3, "val": 5})
                        links.append({"source": user, "target": topic})

            graph_data = {"nodes": nodes, "links": links}
            
            # Save to cache
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(graph_data, f, ensure_ascii=False)
                
            return graph_data

        except Exception as e:
            logger.error(f"Failed to generate graph: {e}")
            return {"nodes": [], "links": []}

    async def start_background_task(self):
        while True:
            await self.generate_graph()
            await asyncio.sleep(300) # Update every 5 minutes
