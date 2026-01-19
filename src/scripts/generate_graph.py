
import asyncio
import json
import os
import sqlite3

DB_PATH = os.getenv("ORA_BOT_DB", "ora_bot.db")
CACHE_FILE = "graph_cache.json"

async def generate_graph():
    print(f"Reading from {DB_PATH}...")
    
    if not os.path.exists(DB_PATH):
        print("Database not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Nodes: Users and ORA
    nodes = []
    links = []

    # Add ORA Central Node
    nodes.append({"id": "ORA", "group": 1, "val": 20})

    # Get Users from Conversations
    # Group by user_id and count interactions
    cursor.execute("SELECT user_id, COUNT(*) as count FROM conversations GROUP BY user_id")
    rows = cursor.fetchall()

    for user_id, count in rows:
        # User Node
        # Try to resolve name? For now use ID
        short_id = str(user_id)[:8]
        nodes.append({"id": str(user_id), "name": short_id, "group": 2, "val": 5})
        
        # Link to ORA interaction
        links.append({
            "source": str(user_id),
            "target": "ORA",
            "value": count
        })
    
    # Advanced: Keyword nodes?
    # Simple keyword extraction (very basic)
    cursor.execute("SELECT message FROM conversations ORDER BY id DESC LIMIT 100")
    messages = cursor.fetchall()
    
    keywords = {}
    ignore_words = {"the", "is", "a", "to", "of", "in", "and", "or", "for", "with", "ora", "bot", "users", "discord"}
    
    for (msg,) in messages:
        words = msg.lower().split()
        for w in words:
            if len(w) > 4 and w not in ignore_words:
                keywords[w] = keywords.get(w, 0) + 1
    
    # Filter top keywords
    top_keywords = sorted(keywords.items(), key=lambda x: x[1], reverse=True)[:10]
    
    for word, count in top_keywords:
        nodes.append({"id": word, "group": 3, "val": count})
        # Link word to ORA
        links.append({"source": "ORA", "target": word, "value": count})

    graph_data = {"nodes": nodes, "links": links}
    
    print(f"Nodes: {len(nodes)}, Links: {len(links)}")
    
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(graph_data, f, ensure_ascii=False, indent=2)
    
    print(f"Saved to {CACHE_FILE}")
    conn.close()

if __name__ == "__main__":
    asyncio.run(generate_graph())
