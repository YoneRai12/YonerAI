from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional
from sqlalchemy import String, ForeignKey, DateTime, Enum, JSON, UniqueConstraint, Integer, Boolean
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class AuthorRole(str, PyEnum):
    system = "system"
    user = "user"
    assistant = "assistant"
    tool = "tool"

class RunStatus(str, PyEnum):
    queued = "queued"
    in_progress = "in_progress"
    requires_action = "requires_action"
    cancelling = "cancelling"
    cancelled = "cancelled"
    failed = "failed"
    completed = "completed"
    expired = "expired"
    done = "done" # generic finished

class ConversationScope(str, PyEnum):
    personal = "personal"
    workspace = "workspace"

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True) # UUID
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Security for Identity Link
    failed_link_attempts: Mapped[int] = mapped_column(Integer, default=0)
    link_locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    identities = relationship("UserIdentity", back_populates="user", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="user")

class UserIdentity(Base):
    __tablename__ = "user_identities"

    id: Mapped[str] = mapped_column(String, primary_key=True) # UUID
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"))
    provider: Mapped[str] = mapped_column(String) # e.g. "discord", "google", "api_key"
    provider_id: Mapped[str] = mapped_column(String) # e.g. discord_user_id
    auth_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Composite unique constraint on (provider, provider_id)
    __table_args__ = (
        UniqueConstraint("provider", "provider_id", name="uq_provider_id"),
    )

    user = relationship("User", back_populates="identities")

class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    scope: Mapped[ConversationScope] = mapped_column(Enum(ConversationScope), default=ConversationScope.personal)

    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", order_by="Message.created_at")
    runs = relationship("Run", back_populates="conversation")
    bindings = relationship("ConversationBinding", back_populates="conversation")

class ConversationBinding(Base):
    __tablename__ = "conversation_bindings"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String, ForeignKey("conversations.id"), index=True)
    
    provider: Mapped[str] = mapped_column(String) # discord, web, etc.
    kind: Mapped[str] = mapped_column(String) # dm, thread, channel, room
    external_id: Mapped[str] = mapped_column(String) # "dm:123", etc.

    __table_args__ = (
        UniqueConstraint("provider", "kind", "external_id", name="uq_binding_key"),
    )

    conversation = relationship("Conversation", back_populates="bindings")

class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String, ForeignKey("conversations.id"), index=True)
    author: Mapped[str] = mapped_column(String(32)) # system, user, assistant, tool
    content: Mapped[Optional[str]] = mapped_column(String, nullable=True) # Text content
    attachments: Mapped[Optional[list[dict]]] = mapped_column(JSON, default=list) # List of file/image data
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Context Logic
    # e.g. replying_to_id, metadata, tools calls etc.

    conversation = relationship("Conversation", back_populates="messages")

class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String, ForeignKey("conversations.id"), index=True)
    # Added user_id for strict idempotency constraint per user
    user_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="queued") # queued, in_progress, etc.
    user_message_id: Mapped[str] = mapped_column(String, ForeignKey("messages.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Idempotency Key
    idempotency_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Relationships
    conversation = relationship("Conversation", back_populates="runs")
    user_message = relationship("Message", foreign_keys=[user_message_id])
    tool_calls = relationship("ToolCall", back_populates="run")

    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_runs_user_idempotency"),
    )

class ToolCall(Base):
    __tablename__ = "tool_calls"

    id: Mapped[str] = mapped_column(String, primary_key=True) # tool_call_id from LLM
    run_id: Mapped[str] = mapped_column(String, ForeignKey("runs.id"), index=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), index=True)
    tool_name: Mapped[str] = mapped_column(String)
    args_json: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String, default="queued") # queued, running, completed, failed
    result_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    # New metrics & tracing
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    artifact_ref: Mapped[Optional[str]] = mapped_column(String, nullable=True) # e.g. "file:///..."
    
    # Lease management for recovery
    lease_token: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    run = relationship("Run", back_populates="tool_calls")

    __table_args__ = (
        UniqueConstraint("user_id", "id", name="uq_tool_call_user_id"),
    )


class ResourceLock(Base):
    __tablename__ = "resource_locks"

    resource_key: Mapped[str] = mapped_column(String, primary_key=True) # e.g., "gpu:0"
    status: Mapped[str] = mapped_column(String, default="free") # "free" or "held"
    lease_token: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    holder_tool_call_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    def __repr__(self) -> str:
        return f"<ResourceLock(key={self.resource_key}, status={self.status}, holder={self.holder_tool_call_id})>"

class IdentityLinkRequest(Base):
    __tablename__ = "identity_link_requests"

    code: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), index=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class IdentityLinkAudit(Base):
    __tablename__ = "identity_link_audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target_user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), index=True)
    from_user_id: Mapped[str] = mapped_column(String)
    ip_address: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    details: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
