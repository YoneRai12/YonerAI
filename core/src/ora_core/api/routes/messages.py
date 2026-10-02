from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from ora_core.api.dependencies.auth import get_current_user
from ora_core.api.schemas.messages import MessageRequest, MessageResponse
from ora_core.brain.process import MainProcess
from ora_core.database.models import User
from ora_core.database.repo import Repository
from ora_core.database.session import AsyncSessionLocal, get_db
from ora_core.distribution.runtime import get_current_runtime
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()

@router.post("/messages", response_model=MessageResponse)
async def post_message(
    req: MessageRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
    authenticated_user: Optional[User] = Depends(get_current_user)
):
    get_current_runtime().require_capability("run.submit_messages")
    repo = Repository(db)

    # 1. User Resolution
    if authenticated_user:
        # Trust the Middleware/Header
        user = authenticated_user
    else:
        # Fallback to Payload Identity (Bot/Local)
        # Note: In Cloudflare Strict Mode, get_current_user might raise 401, so we won't get here if unauthed.
        if not req.user_identity:
             raise HTTPException(status_code=400, detail="Missing user_identity in body (and no auth header found).")
             
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
    conv_id = await repo.resolve_conversation(
        user_id=user.id,
        conversation_id=req.conversation_id,
        context_binding=req.context_binding.model_dump() if req.context_binding else None
    )

    # 4. Create Message & Run
    att_dicts = [a.model_dump() for a in req.attachments]
    
    msg, run = await repo.create_user_message_and_run(
        conversation_id=conv_id,
        user_id=user.id,
        content=req.content,
        attachments=att_dicts,
        idempotency_key=req.idempotency_key
    )

    # 5. Dispatch Brain Process
    # We must use a separate session for background tasks
    background_tasks.add_task(run_brain_task, run.id, conv_id, req)

    return MessageResponse(
        conversation_id=conv_id,
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

