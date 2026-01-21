from typing import Literal, Optional
from pydantic import BaseModel, Field

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

class ContextBinding(BaseModel):
    provider: Literal["discord", "web", "google", "apple", "mc"]
    kind: Literal["dm", "thread", "channel", "room", "server"]
    external_id: str  # e.g. "dm:123", "guild:chan:thread", "guild:chan"

class MessageRequest(BaseModel):
    conversation_id: Optional[str] = None
    user_identity: UserIdentity
    content: str
    attachments: list[Attachment] = []
    idempotency_key: str = Field(min_length=8)
    stream: bool = True
    source: Literal["discord", "web", "api"] = "web"
    context_binding: Optional[ContextBinding] = None

class MessageResponse(BaseModel):
    conversation_id: str
    message_id: str
    run_id: str
    status: str
