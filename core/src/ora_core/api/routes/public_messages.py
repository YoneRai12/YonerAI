from __future__ import annotations

import hashlib
import re
from typing import NoReturn

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ora_core.api.schemas.public_messages import (
    PublicMessageErrorResponse,
    PublicMessageRequest,
    PublicMessageResponse,
)
from ora_core.providers import local_llm


router = APIRouter()

PUBLIC_MESSAGE_CONTRACT_VERSION = "public-core-message-mvp-0.1"
LOCAL_LLM_MESSAGE_CONTRACT_VERSION = "local-llm-conversation-mvp-0.1"
PUBLIC_MESSAGE_PROVIDER = "offline-mock"
PUBLIC_MESSAGE_DEFAULT_CONVERSATION_ID = "public-smoke"
PUBLIC_MESSAGE_SUPPORTED_MODES = frozenset({"mock", "offline", "local"})
SECRET_KEYWORD_PATTERNS = (
    re.compile(
        r"(api[_-]?key|access[_-]?token|refresh[_-]?token|discord[_-]?token|private[_-]?key|client[_-]?secret|google[_-]?client[_-]?secret)",
        re.IGNORECASE,
    ),
    re.compile(r"sk-[A-Za-z0-9_-]{10,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)
PRIVATE_PATH_PATTERNS = (
    re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+", re.IGNORECASE),
    re.compile(r"(?:^|[\s\"'=])/(root|etc|home|users|var|tmp)/", re.IGNORECASE),
)


class PublicMessageError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def _raise_public_message_error(status_code: int, code: str, message: str) -> NoReturn:
    raise PublicMessageError(status_code, code, message)


def _public_message_error_response(exc: PublicMessageError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"error": exc.code, "message": exc.message})


def _contains_private_marker(value: str) -> bool:
    return any(pattern.search(value) for pattern in (*SECRET_KEYWORD_PATTERNS, *PRIVATE_PATH_PATTERNS))


def _normalize_mode(mode: str) -> str:
    normalized = str(mode or "mock").strip().lower()
    if normalized not in PUBLIC_MESSAGE_SUPPORTED_MODES:
        _raise_public_message_error(
            400,
            "unsupported_mode",
            "Public message MVP supports mock/offline mode and optional loopback-only local mode.",
        )
    return normalized


def _build_local_message_response(
    *,
    message: str,
    conversation_id: str,
    model: str | None,
    request: Request | None,
) -> PublicMessageResponse:
    client_host = request.client.host if request and request.client else None
    if not local_llm.is_loopback_host(client_host):
        _raise_public_message_error(
            403,
            "local_llm_loopback_required",
            "Local LLM mode can only be called from a loopback client.",
        )

    digest = hashlib.sha256(f"local:{conversation_id}:{message}".encode("utf-8")).hexdigest()
    message_id = f"local-msg-{digest[:16]}"
    try:
        generated = local_llm.generate_local_llm_reply(
            message=message,
            conversation_id=conversation_id,
            model=model,
        )
    except local_llm.LocalLLMDisabledError:
        _raise_public_message_error(503, "local_llm_disabled", "Local LLM mode is disabled.")
    except local_llm.LocalLLMSecurityError as exc:
        _raise_public_message_error(400, "unsafe_local_llm_endpoint", str(exc))
    except local_llm.LocalLLMConnectionError:
        _raise_public_message_error(
            503,
            "local_llm_unavailable",
            "Local LLM runtime is unavailable on the configured loopback endpoint.",
        )
    except local_llm.LocalLLMResponseError:
        _raise_public_message_error(
            502,
            "local_llm_bad_response",
            "Local LLM runtime returned an unsupported response.",
        )

    return PublicMessageResponse(
        ok=True,
        mode="local",
        conversation_id=conversation_id,
        message_id=message_id,
        reply=generated.reply,
        provider=generated.provider,
        model=generated.model,
        requires_approval=False,
        contract_version=LOCAL_LLM_MESSAGE_CONTRACT_VERSION,
    )


def build_public_message_response(req: PublicMessageRequest, request: Request | None = None) -> PublicMessageResponse:
    message = req.message.strip()
    if not message:
        _raise_public_message_error(400, "empty_message", "message must contain non-whitespace text.")
    if _contains_private_marker(message):
        _raise_public_message_error(
            400,
            "unsafe_public_message",
            "Public smoke messages must not contain secret-like values or private machine paths.",
        )

    mode = _normalize_mode(req.mode)
    conversation_id = (req.conversation_id or PUBLIC_MESSAGE_DEFAULT_CONVERSATION_ID).strip()
    if not conversation_id:
        conversation_id = PUBLIC_MESSAGE_DEFAULT_CONVERSATION_ID
    if _contains_private_marker(conversation_id):
        _raise_public_message_error(
            400,
            "unsafe_public_conversation_id",
            "Public smoke conversation_id must not contain secret-like values or private machine paths.",
        )

    if mode == "local":
        return _build_local_message_response(
            message=message,
            conversation_id=conversation_id,
            model=req.model,
            request=request,
        )

    digest = hashlib.sha256(f"{mode}:{conversation_id}:{message}".encode("utf-8")).hexdigest()
    message_id = f"public-msg-{digest[:16]}"
    reply = (
        f"{PUBLIC_MESSAGE_PROVIDER}: received {len(message)} characters. "
        "This deterministic public message contract used no provider call, memory store, or Discord gateway."
    )

    return PublicMessageResponse(
        ok=True,
        mode=mode,
        conversation_id=conversation_id,
        message_id=message_id,
        reply=reply,
        provider=PUBLIC_MESSAGE_PROVIDER,
        model=None,
        requires_approval=False,
        contract_version=PUBLIC_MESSAGE_CONTRACT_VERSION,
    )


@router.post(
    "/public/messages",
    response_model=PublicMessageResponse,
    responses={
        400: {"model": PublicMessageErrorResponse},
        403: {"model": PublicMessageErrorResponse},
        502: {"model": PublicMessageErrorResponse},
        503: {"model": PublicMessageErrorResponse},
    },
)
def post_public_message(req: PublicMessageRequest, request: Request) -> PublicMessageResponse | JSONResponse:
    try:
        return build_public_message_response(req, request)
    except PublicMessageError as exc:
        return _public_message_error_response(exc)
