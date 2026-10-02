from __future__ import annotations

import hashlib
import ipaddress
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Mapping


LOCAL_DEV_RELAY_TRANSPORT_SCHEMA_VERSION = "yonerai-local-dev-relay-transport/v0.1"
LOCAL_DEV_RELAY_AUDIT_SCHEMA_VERSION = "yonerai-local-dev-relay-audit/v0.1"
DEFAULT_TRANSPORT_BIND_HOST = "127.0.0.1"
DEFAULT_TRANSPORT_HEARTBEAT_TIMEOUT_SEC = 90
DEFAULT_TRANSPORT_MAX_BODY_BYTES = 262_144


TransportHandler = Callable[[bytes], bytes]


@dataclass(frozen=True)
class TransportNodeRecord:
    node_id: str
    key_id: str
    capabilities: tuple[str, ...]
    last_heartbeat_at: str
    revoked: bool = False

    def to_public_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["capabilities"] = list(self.capabilities)
        return payload


@dataclass(frozen=True)
class TransportSessionRecord:
    session_id: str
    node_id: str
    key_id: str
    token_hash: str
    capabilities: tuple[str, ...]
    expires_at: str
    revoked: bool = False

    def to_public_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["capabilities"] = list(self.capabilities)
        payload["token_hash_present"] = bool(self.token_hash)
        payload["token_hash_algorithm"] = "sha256"
        payload.pop("token_hash", None)
        return payload


@dataclass(frozen=True)
class TransportAuditEvent:
    schema_version: str
    event_id: str
    request_id: str
    created_at: str
    node_id: str | None
    capability: str
    status: str
    ok: bool
    request_body_hash: str | None
    response_body_hash: str | None
    request_body_bytes: int
    response_body_bytes: int
    request_body_persisted: bool
    response_body_persisted: bool
    raw_body_included: bool
    session_token_hash_only: bool
    reason_codes: tuple[str, ...]

    def to_public_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["reason_codes"] = list(self.reason_codes)
        return payload


@dataclass(frozen=True)
class TransportProxyResult:
    schema_version: str
    ok: bool
    status: str
    request_id: str
    node_id: str | None
    capability: str
    request_body_hash: str | None
    response_body_hash: str | None
    request_body_bytes: int
    response_body_bytes: int
    request_body_persisted: bool
    response_body_persisted: bool
    raw_body_included: bool
    session_token_hash_only: bool
    controlled_error: bool
    reasons: tuple[str, ...]
    audit_event: TransportAuditEvent

    def to_public_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["reasons"] = list(self.reasons)
        payload["audit_event"] = self.audit_event.to_public_dict()
        return payload


class InMemoryRelayTransport:
    """Local-dev client->relay->node transport model.

    This transport intentionally avoids sockets, public exposure, process start,
    and plaintext body persistence. Plaintext bodies and tokens are accepted only
    as in-flight method arguments and are represented in state by hashes.
    """

    def __init__(
        self,
        *,
        bind_host: str = DEFAULT_TRANSPORT_BIND_HOST,
        max_body_bytes: int = DEFAULT_TRANSPORT_MAX_BODY_BYTES,
        heartbeat_timeout_sec: int = DEFAULT_TRANSPORT_HEARTBEAT_TIMEOUT_SEC,
    ) -> None:
        self.bind_host = bind_host
        self.max_body_bytes = max_body_bytes
        self.heartbeat_timeout_sec = heartbeat_timeout_sec
        self._nodes: dict[str, TransportNodeRecord] = {}
        self._sessions: dict[str, TransportSessionRecord] = {}
        self._handlers: dict[str, TransportHandler] = {}

    def status_report(self) -> dict[str, object]:
        return {
            "schema_version": LOCAL_DEV_RELAY_TRANSPORT_SCHEMA_VERSION,
            "mode": "local_dev_in_memory",
            "ok": self.loopback_only,
            "bind_host": self.bind_host if self.loopback_only else "non_loopback_redacted",
            "loopback_only": self.loopback_only,
            "network_required": False,
            "process_started": False,
            "public_exposure_allowed": False,
            "message_body_persisted": False,
            "session_token_storage": "hash_only",
            "node_count": len(self._nodes),
            "session_count": len(self._sessions),
            "actions_not_performed": [
                "no socket bind",
                "no public tunnel",
                "no network call",
                "no relay process start",
                "no plaintext body persistence",
                "no plaintext session token persistence",
            ],
        }

    @property
    def loopback_only(self) -> bool:
        return _is_loopback_host(self.bind_host)

    def register_node(
        self,
        *,
        node_id: str,
        key_id: str,
        capabilities: tuple[str, ...],
        handler: TransportHandler,
        heartbeat_at: datetime,
    ) -> TransportNodeRecord:
        node = TransportNodeRecord(
            node_id=_safe_id(node_id),
            key_id=_safe_id(key_id),
            capabilities=_normalize_capabilities(capabilities),
            last_heartbeat_at=_format_datetime(heartbeat_at),
        )
        self._nodes[node.node_id] = node
        self._handlers[node.node_id] = handler
        return node

    def heartbeat(self, *, node_id: str, at: datetime) -> TransportNodeRecord | None:
        node = self._nodes.get(_safe_id(node_id))
        if node is None:
            return None
        updated = TransportNodeRecord(
            node_id=node.node_id,
            key_id=node.key_id,
            capabilities=node.capabilities,
            last_heartbeat_at=_format_datetime(at),
            revoked=node.revoked,
        )
        self._nodes[node.node_id] = updated
        return updated

    def start_session(
        self,
        *,
        session_id: str,
        node_id: str,
        key_id: str,
        session_token: str,
        capabilities: tuple[str, ...],
        expires_at: datetime,
    ) -> TransportSessionRecord:
        session = TransportSessionRecord(
            session_id=_safe_id(session_id),
            node_id=_safe_id(node_id),
            key_id=_safe_id(key_id),
            token_hash=_session_token_hash(session_id=_safe_id(session_id), session_token=session_token),
            capabilities=_normalize_capabilities(capabilities),
            expires_at=_format_datetime(expires_at),
        )
        self._sessions[session.token_hash] = session
        return session

    def revoke_session(self, *, session_token: str, session_id: str) -> TransportSessionRecord | None:
        token_hash = _session_token_hash(session_id=_safe_id(session_id), session_token=session_token)
        session = self._sessions.get(token_hash)
        if session is None:
            return None
        revoked = TransportSessionRecord(
            session_id=session.session_id,
            node_id=session.node_id,
            key_id=session.key_id,
            token_hash=session.token_hash,
            capabilities=session.capabilities,
            expires_at=session.expires_at,
            revoked=True,
        )
        self._sessions[token_hash] = revoked
        return revoked

    def proxy_request(
        self,
        *,
        session_token: str,
        session_id: str,
        request_id: str,
        capability: str,
        body: bytes,
        now: datetime,
    ) -> TransportProxyResult:
        normalized_capability = _normalize_requested_capability(capability)
        safe_request_id = _safe_id(request_id) or "request"
        audit_created_at = _format_datetime(now)
        request_body_hash = _sha256_prefixed(body)
        if not self.loopback_only:
            return _proxy_error(
                request_id=safe_request_id,
                capability=normalized_capability,
                status="non_loopback_bind_denied",
                reasons=("transport_bind_host_not_loopback",),
                request_body_hash=request_body_hash,
                request_body_bytes=len(body),
                audit_created_at=audit_created_at,
            )
        if len(body) > self.max_body_bytes:
            return _proxy_error(
                request_id=safe_request_id,
                capability=normalized_capability,
                status="body_too_large",
                reasons=("request_body_exceeds_local_dev_limit",),
                request_body_hash=request_body_hash,
                request_body_bytes=len(body),
                audit_created_at=audit_created_at,
            )
        token_hash = _session_token_hash(session_id=_safe_id(session_id), session_token=session_token)
        session = self._sessions.get(token_hash)
        if session is None:
            return _proxy_error(
                request_id=safe_request_id,
                capability=normalized_capability,
                status="invalid_session",
                reasons=("session_token_hash_not_found",),
                request_body_hash=request_body_hash,
                request_body_bytes=len(body),
                audit_created_at=audit_created_at,
            )
        if session.revoked:
            return _proxy_error(
                request_id=safe_request_id,
                capability=normalized_capability,
                status="revoked_session",
                node_id=session.node_id,
                reasons=("session_revoked",),
                request_body_hash=request_body_hash,
                request_body_bytes=len(body),
                audit_created_at=audit_created_at,
            )
        if now >= _parse_datetime(session.expires_at):
            return _proxy_error(
                request_id=safe_request_id,
                capability=normalized_capability,
                status="expired_session",
                node_id=session.node_id,
                reasons=("session_expired",),
                request_body_hash=request_body_hash,
                request_body_bytes=len(body),
                audit_created_at=audit_created_at,
            )
        if normalized_capability not in session.capabilities:
            return _proxy_error(
                request_id=safe_request_id,
                capability=normalized_capability,
                status="capability_not_declared",
                node_id=session.node_id,
                reasons=("session_capability_not_declared",),
                request_body_hash=request_body_hash,
                request_body_bytes=len(body),
                audit_created_at=audit_created_at,
            )
        node = self._nodes.get(session.node_id)
        if node is None:
            return _proxy_error(
                request_id=safe_request_id,
                capability=normalized_capability,
                status="node_not_connected",
                node_id=session.node_id,
                reasons=("node_not_connected",),
                request_body_hash=request_body_hash,
                request_body_bytes=len(body),
                audit_created_at=audit_created_at,
            )
        if node.revoked:
            return _proxy_error(
                request_id=safe_request_id,
                capability=normalized_capability,
                status="revoked_node",
                node_id=node.node_id,
                reasons=("node_revoked",),
                request_body_hash=request_body_hash,
                request_body_bytes=len(body),
                audit_created_at=audit_created_at,
            )
        if node.key_id != session.key_id:
            return _proxy_error(
                request_id=safe_request_id,
                capability=normalized_capability,
                status="node_key_mismatch",
                node_id=node.node_id,
                reasons=("session_key_id_does_not_match_node",),
                request_body_hash=request_body_hash,
                request_body_bytes=len(body),
                audit_created_at=audit_created_at,
            )
        if normalized_capability not in node.capabilities:
            return _proxy_error(
                request_id=safe_request_id,
                capability=normalized_capability,
                status="node_capability_not_declared",
                node_id=node.node_id,
                reasons=("node_capability_not_declared",),
                request_body_hash=request_body_hash,
                request_body_bytes=len(body),
                audit_created_at=audit_created_at,
            )
        last_heartbeat = _parse_datetime(node.last_heartbeat_at)
        if now - last_heartbeat > timedelta(seconds=self.heartbeat_timeout_sec):
            return _proxy_error(
                request_id=safe_request_id,
                capability=normalized_capability,
                status="stale_heartbeat",
                node_id=node.node_id,
                reasons=("node_heartbeat_stale",),
                request_body_hash=request_body_hash,
                request_body_bytes=len(body),
                audit_created_at=audit_created_at,
            )
        handler = self._handlers.get(node.node_id)
        if handler is None:
            return _proxy_error(
                request_id=safe_request_id,
                capability=normalized_capability,
                status="node_handler_missing",
                node_id=node.node_id,
                reasons=("node_handler_missing",),
                request_body_hash=request_body_hash,
                request_body_bytes=len(body),
                audit_created_at=audit_created_at,
            )
        try:
            response = handler(bytes(body))
        except Exception:
            return _proxy_error(
                request_id=safe_request_id,
                capability=normalized_capability,
                status="node_handler_error",
                node_id=node.node_id,
                reasons=("node_handler_error",),
                request_body_hash=request_body_hash,
                request_body_bytes=len(body),
                audit_created_at=audit_created_at,
            )
        if not isinstance(response, bytes):
            response = str(response).encode("utf-8", errors="replace")
        response_body_hash = _sha256_prefixed(response)
        return TransportProxyResult(
            schema_version=LOCAL_DEV_RELAY_TRANSPORT_SCHEMA_VERSION,
            ok=True,
            status="completed",
            request_id=safe_request_id,
            node_id=node.node_id,
            capability=normalized_capability,
            request_body_hash=request_body_hash,
            response_body_hash=response_body_hash,
            request_body_bytes=len(body),
            response_body_bytes=len(response),
            request_body_persisted=False,
            response_body_persisted=False,
            raw_body_included=False,
            session_token_hash_only=True,
            controlled_error=False,
            reasons=("transport_proxy_completed_hash_only",),
            audit_event=_audit_event(
                request_id=safe_request_id,
                created_at=audit_created_at,
                node_id=node.node_id,
                capability=normalized_capability,
                status="completed",
                ok=True,
                request_body_hash=request_body_hash,
                response_body_hash=response_body_hash,
                request_body_bytes=len(body),
                response_body_bytes=len(response),
                reason_codes=("transport_proxy_completed_hash_only",),
            ),
        )


LocalDevRelayTransport = InMemoryRelayTransport


def _proxy_error(
    *,
    request_id: str,
    capability: str,
    status: str,
    reasons: tuple[str, ...],
    node_id: str | None = None,
    request_body_hash: str | None = None,
    request_body_bytes: int = 0,
    audit_created_at: str = "",
) -> TransportProxyResult:
    return TransportProxyResult(
        schema_version=LOCAL_DEV_RELAY_TRANSPORT_SCHEMA_VERSION,
        ok=False,
        status=status,
        request_id=request_id,
        node_id=node_id,
        capability=capability,
        request_body_hash=request_body_hash,
        response_body_hash=None,
        request_body_bytes=request_body_bytes,
        response_body_bytes=0,
        request_body_persisted=False,
        response_body_persisted=False,
        raw_body_included=False,
        session_token_hash_only=True,
        controlled_error=True,
        reasons=reasons,
        audit_event=_audit_event(
            request_id=request_id,
            created_at=audit_created_at or _format_datetime(datetime.now(timezone.utc)),
            node_id=node_id,
            capability=capability,
            status=status,
            ok=False,
            request_body_hash=request_body_hash,
            response_body_hash=None,
            request_body_bytes=request_body_bytes,
            response_body_bytes=0,
            reason_codes=reasons,
        ),
    )


def _audit_event(
    *,
    request_id: str,
    created_at: str,
    node_id: str | None,
    capability: str,
    status: str,
    ok: bool,
    request_body_hash: str | None,
    response_body_hash: str | None,
    request_body_bytes: int,
    response_body_bytes: int,
    reason_codes: tuple[str, ...],
) -> TransportAuditEvent:
    return TransportAuditEvent(
        schema_version=LOCAL_DEV_RELAY_AUDIT_SCHEMA_VERSION,
        event_id=f"audit-{request_id}",
        request_id=request_id,
        created_at=created_at,
        node_id=node_id,
        capability=capability,
        status=status,
        ok=ok,
        request_body_hash=request_body_hash,
        response_body_hash=response_body_hash,
        request_body_bytes=request_body_bytes,
        response_body_bytes=response_body_bytes,
        request_body_persisted=False,
        response_body_persisted=False,
        raw_body_included=False,
        session_token_hash_only=True,
        reason_codes=reason_codes,
    )


def _session_token_hash(*, session_id: str, session_token: str) -> str:
    payload = f"{session_id}:{session_token}".encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _sha256_prefixed(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def _normalize_capabilities(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            value.strip().lower().replace("-", "_").replace(".", "_")
            for value in values
            if value and value.strip()
        )
    )


def _normalize_requested_capability(value: str) -> str:
    normalized = _normalize_capabilities((value,))
    return normalized[0] if normalized else "unknown"


def _safe_id(value: str) -> str:
    text = str(value or "").strip()
    if "\\" in text or "/" in text or ":" in text:
        return "id-redacted"
    return text[:96]


def _is_loopback_host(host: str) -> bool:
    value = (host or "").strip().strip("[]").lower()
    if value == "localhost":
        return True
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return False


def _format_datetime(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_datetime(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text).astimezone(timezone.utc)
