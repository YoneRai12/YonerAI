from datetime import datetime
from enum import Enum as PyEnum
from typing import List, Optional
from sqlalchemy import String, ForeignKey, DateTime, Enum, JSON, UniqueConstraint
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

class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String, ForeignKey("conversations.id"), index=True)
    author: Mapped[AuthorRole] = mapped_column(Enum(AuthorRole))
    content: Mapped[Optional[str]] = mapped_column(String, nullable=True) # Text content
    attachments: Mapped[Optional[List[dict]]] = mapped_column(JSON, default=list) # List of file/image data
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
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus), default=RunStatus.queued)
    user_message_id: Mapped[str] = mapped_column(String, ForeignKey("messages.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Idempotency Key
    idempotency_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Relationships
    conversation = relationship("Conversation", back_populates="runs")
    user_message = relationship("Message", foreign_keys=[user_message_id])

    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_runs_user_idempotency"),
    )
