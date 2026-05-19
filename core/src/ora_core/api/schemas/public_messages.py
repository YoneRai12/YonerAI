from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


PUBLIC_MESSAGE_MAX_LENGTH = 2000


class PublicMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=PUBLIC_MESSAGE_MAX_LENGTH)
    conversation_id: Optional[str] = Field(default=None, max_length=120)
    mode: str = Field(default="mock", max_length=24)
    model: Optional[str] = Field(default=None, max_length=120)


class PublicMessageResponse(BaseModel):
    ok: bool
    mode: str
    conversation_id: str
    message_id: str
    reply: str
    provider: str
    model: Optional[str] = None
    requires_approval: bool
    contract_version: str


class PublicMessageErrorResponse(BaseModel):
    error: str
    message: str
