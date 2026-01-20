from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from .models import User, UserIdentity, Conversation, Message, Run, RunStatus, AuthorRole, ConversationScope
import uuid

class Repository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create_user(self, provider: str, provider_id: str, display_name: str | None = None) -> User:
        # Check existing identity
        stmt = select(UserIdentity).options(selectinload(UserIdentity.user)).where(
            UserIdentity.provider == provider,
            UserIdentity.provider_id == provider_id
        )
        result = await self.db.execute(stmt)
        identity = result.scalar_one_or_none()
        
        if identity:
            return identity.user
            
        # Create new
        new_user = User(id=str(uuid.uuid4()))
        new_identity = UserIdentity(
            id=str(uuid.uuid4()),
            user_id=new_user.id,
            provider=provider,
            provider_id=provider_id,
            auth_metadata={"display_name": display_name} if display_name else {}
        )
        self.db.add(new_user)
        self.db.add(new_identity)
        await self.db.flush()
        return new_user

    async def get_run_by_idempotency(self, user_id: str, idempotency_key: str) -> Run | None:
        stmt = select(Run).where(
            Run.user_id == user_id,
            Run.idempotency_key == idempotency_key
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create_conversation(self, conversation_id: str | None, user_id: str) -> Conversation:
        if conversation_id:
            stmt = select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id
            )
            result = await self.db.execute(stmt)
            conv = result.scalar_one_or_none()
            if conv:
                return conv
        
        # Create new
        new_id = str(uuid.uuid4())
        new_conv = Conversation(
            id=new_id,
            user_id=user_id,
            title="New Conversation",
            scope=ConversationScope.personal
        )
        self.db.add(new_conv)
        await self.db.flush()
        return new_conv

    async def create_user_message_and_run(
        self, conversation_id: str, user_id: str, content: str, attachments: list[dict], idempotency_key: str
    ) -> tuple[Message, Run]:
        msg_id = str(uuid.uuid4())
        msg = Message(
            id=msg_id,
            conversation_id=conversation_id,
            author=AuthorRole.user,
            content=content,
            attachments=attachments
        )
        self.db.add(msg)
        
        run_id = str(uuid.uuid4())
        run = Run(
            id=run_id,
            conversation_id=conversation_id,
            user_id=user_id,
            user_message_id=msg_id,
            status=RunStatus.queued,
            idempotency_key=idempotency_key
        )
        self.db.add(run)
        
        await self.db.commit()
        await self.db.refresh(msg)
        await self.db.refresh(run)
        return msg, run

    async def update_run_status(self, run_id: str, status: RunStatus):
        stmt = update(Run).where(Run.id == run_id).values(status=status)
        await self.db.execute(stmt)
        await self.db.commit()

    async def create_assistant_message(self, conversation_id: str, content: str) -> Message:
        msg = Message(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            author=AuthorRole.assistant,
            content=content,
            attachments=[]
        )
        self.db.add(msg)
        await self.db.commit()
        await self.db.refresh(msg)
        return msg



