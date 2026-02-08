from typing import List, Optional

from fastapi import APIRouter, Depends
from ora_core.database.repo import Repository
from ora_core.database.session import get_db
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()

class HistoryEntry(BaseModel):
    user_id: str # OR user_id (local int) or UUID
    # We should support both, but for now lets assume ORA user_id (int or string)
    # The Bot sends Discord User ID (int/str)
    
    role: str # "user" or "assistant"
    content: str
    timestamp: Optional[str] = None
    conversation_id: Optional[str] = None
    provider: str = "discord" # Source
    provider_id: str # Discord User ID

@router.post("/memory/history")
async def sync_history(
    entries: List[HistoryEntry],
    db: AsyncSession = Depends(get_db)
):
    repo = Repository(db)
    
    saved_count = 0
    for entry in entries:
        # 1. Resolve User
        user = await repo.get_or_create_user(
            provider=entry.provider,
            provider_id=entry.provider_id
        )
        
        # 2. Resolve Conversation (Default to a "Discord Sync" conversation or similar if not provided)
        # For now, let's look for the most recent active conversation or create one.
        # Ideally, Bot tracks conversation_id. But currently Bot is "Stateless" mostly.
        # We can use a "Daily Discord" conversation concept or just one big one.
        # repo.resolve_conversation handles "getting latest" if None is passed? 
        # Actually repo.resolve_conversation requires SOME logic.
        
        # We'll use a specific logic: Get latest active conversation for this user.
        # If None, create one.
        conv_id = entry.conversation_id
        if not conv_id:
            # Resolve a stable "history sync" conversation per (provider, provider_id)
            # using the bindings table (so it doesn't create a new conversation every time).
            conv_id = await repo.resolve_conversation(
                user_id=user.id,
                conversation_id=None,
                context_binding={
                    "provider": entry.provider,
                    "kind": "history_sync",
                    "external_id": str(entry.provider_id),
                },
            )

        # 3. Save Message (History Sync)
        if conv_id:
            await repo.create_history_message(
                conversation_id=conv_id,
                role=entry.role,
                content=entry.content,
                attachments=[] # Currently not supporting attachments in sync for simplicity, or add later
            )
            saved_count += 1
        
    return {"status": "ok", "synced": saved_count}
