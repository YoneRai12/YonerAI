from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator


class UserIdentity(BaseModel):
    provider: Literal["discord", "web", "google", "apple"] = "web"
    id: str
    display_name: Optional[str] = None  # hint only

class Attachment(BaseModel):
    type: Literal["image_url", "image_base64", "audio_url", "file_url"]
    url: Optional[str] = None
    base64: Optional[str] = None
    mime: Optional[str] = None
    name: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_image_shape(cls, data):
        # Accept legacy payload:
        # {"type":"image_url","image_url":{"url":"..."}}
        if isinstance(data, dict) and data.get("type") == "image_url" and not data.get("url"):
            nested = data.get("image_url")
            if isinstance(nested, dict) and nested.get("url"):
                data = {**data, "url": nested.get("url")}
        return data

class ContextBinding(BaseModel):
    provider: Literal["discord", "web", "google", "apple", "mc"]
    kind: Literal["dm", "thread", "channel", "room", "server"]
    external_id: str  # e.g. "dm:123", "guild:chan:thread", "guild:chan"

class HistoryMessage(BaseModel):
    """Pre-built history message from client (e.g., Discord reply chain)."""
    role: Literal["user", "assistant", "system"]
    content: str
    author_name: Optional[str] = None  # Display name for user messages

class ClientContext(BaseModel):
    """Rich context provided by the client (Discord bot, Web UI, etc.)."""
    is_admin: bool = False
    is_sub_admin: bool = False
    is_vc_admin: bool = False
    server_name: Optional[str] = None
    guild_id: Optional[str] = None
    channel_id: Optional[str] = None
    channel_name: Optional[str] = None
    channel_memory: Optional[dict] = None  # Summary, topics, atmosphere
    timestamp: Optional[str] = None  # ISO format

class MessageRequest(BaseModel):
    conversation_id: Optional[str] = None
    user_identity: UserIdentity
    content: str
    attachments: list[Attachment] = []
    available_tools: list[dict[str, Any]] = []
    idempotency_key: str = Field(min_length=8)
    stream: bool = True
    source: Literal["discord", "web", "api"] = "web"
    context_binding: Optional[ContextBinding] = None
    # NEW: Client-provided rich context
    client_history: list[HistoryMessage] = []  # Pre-built history from client
    client_context: Optional[ClientContext] = None  # Admin status, server info, etc.
    llm_preference: Optional[str] = None # Override engine priority or specify model name

class MessageResponse(BaseModel):
    conversation_id: str
    message_id: str
    run_id: str
    status: str
