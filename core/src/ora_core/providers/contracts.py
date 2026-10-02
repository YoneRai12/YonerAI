from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Mapping, Protocol, runtime_checkable


_SECRET_MARKERS = (
    re.compile(r"sk-[A-Za-z0-9_-]{10,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(
        r"(api[_-]?key|access[_-]?token|refresh[_-]?token|discord[_-]?token|private[_-]?key|client[_-]?secret|authorization)",
        re.IGNORECASE,
    ),
)


@dataclass(frozen=True)
class ProviderCapabilities:
    chat: bool = True
    structured_output: bool = False
    streaming: bool = False
    vision: bool = False
    tool_use: bool = False
    local_only: bool = False
    cloud: bool = False
    external_provider: bool = False

    def to_public_dict(self) -> dict[str, bool]:
        return asdict(self)


@dataclass(frozen=True)
class ProviderRequest:
    prompt: str
    model: str | None = None
    system: str | None = None
    structured: bool = False
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderResponse:
    provider: str
    model: str
    output_text: str
    deterministic: bool
    finish_reason: str = "stop"

    def to_public_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ProviderStatus:
    provider_id: str
    configured: bool
    available: bool
    reason: str | None
    capabilities: ProviderCapabilities
    env_status: Mapping[str, str] = field(default_factory=dict)

    def to_public_dict(self) -> dict[str, object]:
        return {
            "provider_id": self.provider_id,
            "configured": self.configured,
            "available": self.available,
            "reason": self.reason,
            "capabilities": self.capabilities.to_public_dict(),
            "env_status": dict(self.env_status),
        }


class ProviderError(RuntimeError):
    def __init__(
        self,
        provider: str,
        code: str,
        message: str,
        *,
        safe_context: Mapping[str, object] | None = None,
    ) -> None:
        self.provider = _safe_text(provider, fallback="provider")
        self.code = _safe_text(code, fallback="provider_error")
        self.message = _safe_text(message, fallback="provider error")
        self.safe_context = {
            _safe_text(str(key), fallback="context"): _safe_public_value(value)
            for key, value in (safe_context or {}).items()
        }
        super().__init__(f"{self.provider}: {self.code}: {self.message}")

    def to_public_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "code": self.code,
            "message": self.message,
            "context": dict(self.safe_context),
        }


@runtime_checkable
class ProviderAdapter(Protocol):
    provider_id: str
    capabilities: ProviderCapabilities

    def status(self) -> ProviderStatus:
        ...

    def generate(self, request: ProviderRequest, *, allow_live_call: bool = False) -> ProviderResponse:
        ...


class UnavailableProviderAdapter:
    def __init__(
        self,
        provider_id: str,
        *,
        capabilities: ProviderCapabilities,
        reason: str,
        configured: bool = False,
        env_status: Mapping[str, str] | None = None,
    ) -> None:
        self.provider_id = provider_id
        self.capabilities = capabilities
        self._reason = reason
        self._configured = configured
        self._env_status = dict(env_status or {})

    def status(self) -> ProviderStatus:
        return ProviderStatus(
            provider_id=self.provider_id,
            configured=self._configured,
            available=False,
            reason=self._reason,
            capabilities=self.capabilities,
            env_status=self._env_status,
        )

    def generate(self, request: ProviderRequest, *, allow_live_call: bool = False) -> ProviderResponse:
        del request, allow_live_call
        raise ProviderError(self.provider_id, "provider_unavailable", self._reason)


def redact_env_presence(env: Mapping[str, str | None], keys: tuple[str, ...]) -> dict[str, str]:
    return {
        key: "present_redacted" if str(env.get(key) or "").strip() else "absent"
        for key in keys
    }


def _safe_public_value(value: object) -> object:
    if isinstance(value, str):
        return _safe_text(value, fallback="redacted")
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int | float):
        return value
    return _safe_text(str(value), fallback="redacted")


def _safe_text(value: str, *, fallback: str) -> str:
    cleaned = " ".join(str(value or "").split())
    if not cleaned:
        return fallback
    if any(pattern.search(cleaned) for pattern in _SECRET_MARKERS):
        return fallback
    return cleaned[:220]
