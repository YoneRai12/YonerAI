from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


PUBLIC_MESSAGE_MAX_LENGTH = 2000


class PublicMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=PUBLIC_MESSAGE_MAX_LENGTH)
    conversation_id: Optional[str] = Field(default=None, max_length=120)
    mode: str = Field(default="mock", max_length=24)
    model: Optional[str] = Field(default=None, max_length=120)
    local_provider: Optional[str] = Field(default=None, max_length=64)
    local_base_url: Optional[str] = Field(default=None, max_length=200)
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, ge=1, le=4096)


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
