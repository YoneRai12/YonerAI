from sqlalchemy import select, update, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from .models import User, UserIdentity, Conversation, Message, Run, RunStatus, AuthorRole, ConversationScope, ToolCall, ConversationBinding, IdentityLinkRequest, IdentityLinkAudit
import uuid
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

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

    async def get_run(self, run_id: str) -> Run | None:
        stmt = select(Run).where(Run.id == run_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

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

    async def get_binding(self, provider: str, kind: str, external_id: str) -> ConversationBinding | None:
        stmt = select(ConversationBinding).where(
            ConversationBinding.provider == provider,
            ConversationBinding.kind == kind,
            ConversationBinding.external_id == external_id
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_binding(self, conversation_id: str, provider: str, kind: str, external_id: str) -> ConversationBinding:
        binding = ConversationBinding(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            provider=provider,
            kind=kind,
            external_id=external_id
        )
        self.db.add(binding)
        await self.db.flush()
        return binding

    async def resolve_conversation(self, user_id: str, conversation_id: str | None, context_binding: dict | None) -> str:
        """
        Hub & Spoke resolution logic:
        1. If explicit conversation_id is provided, use it.
        2. If context_binding is provided (provider/kind/external_id), resolve via Bindings table.
        3. Otherwise, create a new conversation.
        """
        # 1. Explicit ID
        if conversation_id:
            return conversation_id

        # 2. Binding
        if context_binding:
            provider = context_binding.get("provider")
            kind = context_binding.get("kind")
            external_id = context_binding.get("external_id")
            if provider and kind and external_id:
                binding = await self.get_binding(provider, kind, external_id)
                if binding:
                    return binding.conversation_id
                
                # Create new conversation for this binding
                new_conv = await self.get_or_create_conversation(None, user_id)
                await self.create_binding(new_conv.id, provider, kind, external_id)
                return new_conv.id

        # 3. Default
        conv = await self.get_or_create_conversation(None, user_id)
        return conv.id

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

    async def get_messages(self, conversation_id: str, limit: int = 20) -> list[Message]:
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        msgs = list(result.scalars().all())
        msgs.reverse() # Cronological order
        return msgs

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

    async def get_or_create_tool_call(
        self, tool_call_id: str, run_id: str, user_id: str, tool_name: str, args: dict
    ) -> tuple[ToolCall, bool]:
        """
        Idempotent tool call registration using DB constraints.
        Scoped by user_id to prevent cross-user ID guessing/collision.
        """
        # 1. Check existing
        stmt = select(ToolCall).where(
            ToolCall.id == tool_call_id,
            ToolCall.user_id == user_id
        )
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()
        
        # Zombie Check: If running but expired, we treat it as "stale" and allow retry
        if existing and existing.status == "running" and existing.expires_at:
            if datetime.utcnow() > existing.expires_at:
                # MARK AS FAILED (or let the runner overwrite it)
                # For safety, we just return it and let the runner decide to retry
                return existing, False

        if existing:
            return existing, False

        # 2. Try to insert
        new_call = ToolCall(
            id=tool_call_id,
            run_id=run_id,
            user_id=user_id,
            tool_name=tool_name,
            args_json=args,
            status="queued"
        )
        self.db.add(new_call)
        try:
            await self.db.commit()
            await self.db.refresh(new_call)
            return new_call, True
        except Exception: # Likely IntegrityError on race condition
            await self.db.rollback()
            stmt = select(ToolCall).where(
                ToolCall.id == tool_call_id,
                ToolCall.user_id == user_id
            )
            result = await self.db.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                return existing, False
            raise

    async def claim_tool_call(
        self, tool_call_id: str, user_id: str, lease_token: str, expires_at: datetime
    ) -> bool:
        """
        Atomically claim a tool call for execution.
        Winning criteria: status is queued/failed OR it's a timed-out zombie.
        """
        now = datetime.utcnow()
        stmt = (
            update(ToolCall)
            .where(
                ToolCall.id == tool_call_id,
                ToolCall.user_id == user_id
            )
            .where(
                or_(
                    ToolCall.status.in_(["queued", "failed"]),
                    and_(ToolCall.status == "running", ToolCall.expires_at < now)
                )
            )
            .values(
                status="running",
                lease_token=lease_token,
                expires_at=expires_at,
                error=None # Clear previous error if retrying
            )
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount == 1

    async def update_tool_call(
        self, tool_call_id: str, user_id: str, status: str, 
        lease_token: str | None = None,
        result: dict | None = None, error: str | None = None,
        expires_at: datetime | None = None,
        latency_ms: int | None = None,
        artifact_ref: str | None = None
    ):
        """
        Update tool call status, optionally verifying the lease_token to prevent ghost overwrites.
        """
        values = {"status": status}
        if result is not None:
            values["result_json"] = result
        if error is not None:
            values["error"] = error
        if expires_at is not None:
            values["expires_at"] = expires_at
        if latency_ms is not None:
            values["latency_ms"] = latency_ms
        if artifact_ref is not None:
            values["artifact_ref"] = artifact_ref
        
        stmt = update(ToolCall).where(
            ToolCall.id == tool_call_id,
            ToolCall.user_id == user_id
        )
        
        if lease_token is not None:
            stmt = stmt.where(ToolCall.lease_token == lease_token)
            
        stmt = stmt.values(**values)
        res = await self.db.execute(stmt)
        await self.db.commit()
        
        if lease_token is not None and res.rowcount == 0:
            # This means someone else reclaimed the tool or we are a "ghost"
            logger.warning(f"Update failed for tool {tool_call_id}: lease_token mismatch (Ghost overwrite prevented).")

    async def acquire_resource_lock(
        self, resource_key: str, tool_call_id: str, lease_token: str, expires_at: datetime
    ) -> bool:
        """
        Atomically acquire a resource lock.
        Wins if: status is free OR it's a timed-out zombie.
        """
        from .models import ResourceLock
        now = datetime.utcnow()
        
        # 1. Ensure the resource row exists (Initial seed if not present)
        stmt_check = select(ResourceLock).where(ResourceLock.resource_key == resource_key)
        res_check = await self.db.execute(stmt_check)
        if not res_check.scalar_one_or_none():
            lock_obj = ResourceLock(resource_key=resource_key, status="free")
            self.db.add(lock_obj)
            await self.db.commit()

        # 2. Atomic Update
        stmt = (
            update(ResourceLock)
            .where(ResourceLock.resource_key == resource_key)
            .where(
                or_(
                    ResourceLock.status == "free",
                    and_(ResourceLock.status == "held", ResourceLock.expires_at < now)
                )
            )
            .values(
                status="held",
                lease_token=lease_token,
                expires_at=expires_at,
                holder_tool_call_id=tool_call_id
            )
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount == 1

    async def release_resource_lock(
        self, resource_key: str, lease_token: str
    ) -> bool:
        """
        Release a resource lock if the lease_token matches.
        """
        from .models import ResourceLock
        stmt = (
            update(ResourceLock)
            .where(
                ResourceLock.resource_key == resource_key,
                ResourceLock.lease_token == lease_token
            )
            .values(
                status="free",
                lease_token=None,
                expires_at=None,
                holder_tool_call_id=None
            )
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount == 1

    async def create_link_request(self, user_id: str, code: str, ip: str | None = None, expires_in_sec: int = 300) -> IdentityLinkRequest:
        from datetime import timedelta
        request = IdentityLinkRequest(
            code=code,
            user_id=user_id,
            ip_address=ip,
            expires_at=datetime.utcnow() + timedelta(seconds=expires_in_sec)
        )
        self.db.add(request)
        await self.db.flush()
        return request

    async def get_link_request(self, code: str) -> IdentityLinkRequest | None:
        stmt = select(IdentityLinkRequest).where(
            IdentityLinkRequest.code == code,
            IdentityLinkRequest.expires_at > datetime.utcnow()
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_link_request(self, code: str):
        from sqlalchemy import delete
        stmt = delete(IdentityLinkRequest).where(IdentityLinkRequest.code == code)
        await self.db.execute(stmt)
        await self.db.flush()

    async def link_identities(self, from_user_id: str, target_user_id: str, ip: str | None = None):
        """
        Merges 'from_user_id' into 'target_user_id'.
        All identities and data pointing to from_user_id will now point to target_user_id.
        """
        if from_user_id == target_user_id:
            return

        # 1. Update UserIdentity
        stmt1 = update(UserIdentity).where(UserIdentity.user_id == from_user_id).values(user_id=target_user_id)
        # 2. Update Conversation
        stmt2 = update(Conversation).where(Conversation.user_id == from_user_id).values(user_id=target_user_id)
        # 3. Update Run
        stmt3 = update(Run).where(Run.user_id == from_user_id).values(user_id=target_user_id)
        
        await self.db.execute(stmt1)
        await self.db.execute(stmt2)
        await self.db.execute(stmt3)

        # 4. Audit
        audit = IdentityLinkAudit(
            target_user_id=target_user_id,
            from_user_id=from_user_id,
            ip_address=ip,
            success=True,
            details=f"Merged {from_user_id} into {target_user_id}"
        )
        self.db.add(audit)
        
        await self.db.commit()
        logger.info(f"Merged user {from_user_id} into {target_user_id}")

    async def get_user(self, user_id: str) -> User | None:
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_user_link_failure(self, user_id: str, ip: str | None = None):
        from datetime import timedelta
        user = await self.get_user(user_id)
        if user:
            user.failed_link_attempts += 1
            if user.failed_link_attempts >= 5:
                user.link_locked_until = datetime.utcnow() + timedelta(minutes=15)
            
            audit = IdentityLinkAudit(
                target_user_id=user_id, # This is the web user who is failing
                from_user_id=user_id, # not yet linked
                ip_address=ip,
                success=False,
                details=f"Failed attempt {user.failed_link_attempts}"
            )
            self.db.add(audit)
            await self.db.commit()

    async def reset_user_link_failure(self, user_id: str):
        user = await self.get_user(user_id)
        if user:
            user.failed_link_attempts = 0
            user.link_locked_until = None
            await self.db.flush()

    async def get_dashboard_stats(self):
        """Fetch summary stats for the dashboard."""
        from sqlalchemy import func
        from ora_core.database.models import ToolCall, Run
        
        # 1. Recent Runs
        run_count = await self.db.execute(select(func.count(Run.id)))
        
        # 2. Tool Usage & Latency
        tool_stats_stmt = select(
            ToolCall.tool_name,
            func.count(ToolCall.id).label("count"),
            func.avg(ToolCall.latency_ms).label("avg_latency")
        ).group_by(ToolCall.tool_name)
        tool_stats_res = await self.db.execute(tool_stats_stmt)
        
        # 3. Recent tool calls (last 10)
        recent_calls_stmt = select(ToolCall).order_by(ToolCall.created_at.desc()).limit(10)
        recent_calls_res = await self.db.execute(recent_calls_stmt)
        
        return {
            "total_runs": run_count.scalar(),
            "tools": [
                {"name": row.tool_name, "count": row.count, "avg_latency": float(row.avg_latency or 0)}
                for row in tool_stats_res
            ],
            "recent_tool_calls": [
                {
                    "id": c.id,
                    "tool": c.tool_name,
                    "status": c.status,
                    "latency": c.latency_ms,
                    "created_at": c.created_at.isoformat()
                }
                for c in recent_calls_res.scalars().all()
            ]
        }



