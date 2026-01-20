from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from ora_core.database.session import get_db, AsyncSessionLocal
from ora_core.database.repo import Repository
from ora_core.api.schemas.messages import MessageRequest, MessageResponse
from ora_core.brain.process import MainProcess

router = APIRouter()

@router.post("/messages", response_model=MessageResponse)
async def post_message(

    req: MessageRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    repo = Repository(db)

    # 1. User Resolution
    user = await repo.get_or_create_user(
        provider=req.user_identity.provider,
        provider_id=req.user_identity.id,
        display_name=req.user_identity.display_name
    )

    # 2. Idempotency Check
    existing_run = await repo.get_run_by_idempotency(user.id, req.idempotency_key)
    if existing_run:
        return MessageResponse(
            conversation_id=existing_run.conversation_id,
            message_id=existing_run.user_message_id,
            run_id=existing_run.id,
            status=existing_run.status
        )

    # 3. Conversation Resolution
    conversation = await repo.get_or_create_conversation(req.conversation_id, user.id)

    # 4. Create Message & Run
    att_dicts = [a.model_dump() for a in req.attachments]
    
    msg, run = await repo.create_user_message_and_run(
        conversation_id=conversation.id,
        user_id=user.id,
        content=req.content,
        attachments=att_dicts,
        idempotency_key=req.idempotency_key
    )

    # 5. Dispatch Brain Process
    # We must use a separate session for background tasks
    background_tasks.add_task(run_brain_task, run.id, conversation.id, req)

    return MessageResponse(
        conversation_id=conversation.id,
        message_id=msg.id,
        run_id=run.id,
        status=run.status
    )

async def run_brain_task(run_id: str, conversation_id: str, req: MessageRequest):
    """
    Bootstrap the Brain MainProcess with a fresh DB session.
    """
    async with AsyncSessionLocal() as session:
        brain = MainProcess(run_id, conversation_id, req, session)
        await brain.run()

