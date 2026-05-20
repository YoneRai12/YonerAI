from __future__ import annotations

import hashlib
import os
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
from ora_core.sessions import (
    ConversationSessionError,
    ConversationSessionState,
    get_public_conversation_session_store,
)


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
    def __init__(self, status_code: int, code: str, message: str, metadata: dict[str, str] | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.metadata = metadata or {}


def _raise_public_message_error(
    status_code: int, code: str, message: str, metadata: dict[str, str] | None = None
) -> NoReturn:
    raise PublicMessageError(status_code, code, message, metadata=metadata)


def _public_message_error_response(exc: PublicMessageError) -> JSONResponse:
    body = {"error": exc.code, "message": exc.message}
    body.update(exc.metadata)
    return JSONResponse(status_code=exc.status_code, content=body)


def _contains_private_marker(value: str) -> bool:
    return any(pattern.search(value) for pattern in (*SECRET_KEYWORD_PATTERNS, *PRIVATE_PATH_PATTERNS))


def _safe_metadata_value(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = str(value).strip()
    if not cleaned or _contains_private_marker(cleaned):
        return None
    return cleaned[:120]


def _local_error_metadata(
    *,
    provider: str | None = None,
    model: str | None = None,
    status: str,
    config: local_llm.LocalLLMConfig | None = None,
) -> dict[str, str]:
    selected_provider = provider
    selected_model = model
    if config is not None:
        selected_provider = local_llm.LOCAL_LLM_PROVIDER_LABELS.get(config.provider, config.provider)
        selected_model = config.model

    metadata: dict[str, str] = {"mode": "local", "status": status}
    safe_provider = _safe_metadata_value(selected_provider)
    safe_model = _safe_metadata_value(selected_model)
    if safe_provider:
        metadata["provider"] = safe_provider
    if safe_model:
        metadata["model"] = safe_model
    return metadata


def _normalize_mode(mode: str) -> str:
    normalized = str(mode or "mock").strip().lower()
    if normalized not in PUBLIC_MESSAGE_SUPPORTED_MODES:
        _raise_public_message_error(
            400,
            "unsupported_mode",
            "Public message MVP supports mock/offline mode and optional loopback-only local mode.",
        )
    return normalized


def _record_session_turn(*, session_id: str | None, conversation_id: str) -> ConversationSessionState:
    try:
        return get_public_conversation_session_store().record_turn(
            session_id=session_id,
            conversation_id=conversation_id,
        )
    except ConversationSessionError as exc:
        _raise_public_message_error(400, "invalid_public_session", str(exc))


def _build_local_message_response(
    *,
    message: str,
    session_id: str | None,
    conversation_id: str,
    local_provider: str | None,
    local_base_url: str | None,
    model: str | None,
    temperature: float | None,
    max_tokens: int | None,
    request: Request | None,
) -> PublicMessageResponse:
    expected_token = (os.getenv("ORA_LOCAL_LLM_PUBLIC_TOKEN") or "").strip()
    if not expected_token:
        _raise_public_message_error(
            503,
            "local_llm_auth_not_configured",
            "Local LLM mode requires explicit token configuration.",
        )
    presented_token = (request.headers.get("x-ora-local-token") if request is not None else None) or ""
    if presented_token != expected_token:
        _raise_public_message_error(
            403,
            "local_llm_auth_required",
            "Local LLM mode requires a valid local access token.",
        )

    client_host = request.client.host if request and request.client else None
    if not local_llm.is_loopback_host(client_host):
        _raise_public_message_error(
            403,
            "local_llm_loopback_required",
            "Local LLM mode can only be called from a loopback client.",
        )

    config: local_llm.LocalLLMConfig | None = None
    try:
        config = local_llm.build_local_llm_config(
            provider=local_provider,
            base_url=local_base_url,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        generated = local_llm.generate_local_llm_reply(
            message=message,
            conversation_id=conversation_id,
            config=config,
        )
    except local_llm.LocalLLMDisabledError:
        _raise_public_message_error(
            503,
            "local_llm_disabled",
            "Local LLM mode is disabled.",
            _local_error_metadata(status="disabled", config=config),
        )
    except local_llm.LocalLLMProviderError:
        _raise_public_message_error(
            400,
            "unsupported_local_llm_provider",
            (
                "Local mode supports ollama and openai_compatible_local. "
                "OpenAI-compatible local aliases include lmstudio, llama.cpp, text-generation-webui, and localai."
            ),
            _local_error_metadata(status="unsupported_provider"),
        )
    except local_llm.LocalLLMSecurityError:
        _raise_public_message_error(
            400,
            "unsafe_local_llm_endpoint",
            "Local LLM mode only accepts loopback provider endpoints without credentials, query strings, or fragments.",
            _local_error_metadata(provider=local_provider, model=model, status="blocked_by_loopback_policy"),
        )
    except local_llm.LocalLLMConnectionError:
        _raise_public_message_error(
            503,
            "local_llm_unavailable",
            "Local LLM runtime is unavailable on the configured loopback endpoint.",
            _local_error_metadata(status="unavailable", config=config),
        )
    except local_llm.LocalLLMResponseError:
        _raise_public_message_error(
            502,
            "local_llm_bad_response",
            "Local LLM runtime returned an unsupported response.",
            _local_error_metadata(status="bad_response", config=config),
        )

    session_state = _record_session_turn(session_id=session_id, conversation_id=conversation_id)
    digest = hashlib.sha256(
        f"local:{session_state.session_id}:{conversation_id}:{session_state.turn_index}:{message}".encode("utf-8")
    ).hexdigest()
    message_id = f"local-msg-{digest[:16]}"

    return PublicMessageResponse(
        ok=True,
        mode="local",
        session_id=session_state.session_id,
        conversation_id=conversation_id,
        message_id=message_id,
        turn_index=session_state.turn_index,
        history_count=session_state.history_count,
        memory_persisted=session_state.memory_persisted,
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
    session_id = req.session_id.strip() if req.session_id else None
    if session_id and _contains_private_marker(session_id):
        _raise_public_message_error(
            400,
            "unsafe_public_session_id",
            "Public smoke session_id must not contain secret-like values or private machine paths.",
        )
    if req.model and _contains_private_marker(req.model):
        _raise_public_message_error(
            400,
            "unsafe_public_model",
            "Public smoke model must not contain secret-like values or private machine paths.",
        )

    if mode == "local":
        return _build_local_message_response(
            message=message,
            session_id=session_id,
            conversation_id=conversation_id,
            local_provider=req.local_provider,
            local_base_url=req.local_base_url,
            model=req.model,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
            request=request,
        )

    session_state = _record_session_turn(session_id=session_id, conversation_id=conversation_id)
    digest = hashlib.sha256(
        f"{mode}:{session_state.session_id}:{conversation_id}:{session_state.turn_index}:{message}".encode("utf-8")
    ).hexdigest()
    message_id = f"public-msg-{digest[:16]}"
    reply = (
        f"{PUBLIC_MESSAGE_PROVIDER}: received {len(message)} characters. "
        "This deterministic public message contract used no provider call, memory store, or Discord gateway. "
        "Conversation session metadata is in-memory only and is not persistent memory."
    )

    return PublicMessageResponse(
        ok=True,
        mode=mode,
        session_id=session_state.session_id,
        conversation_id=conversation_id,
        message_id=message_id,
        turn_index=session_state.turn_index,
        history_count=session_state.history_count,
        memory_persisted=session_state.memory_persisted,
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
