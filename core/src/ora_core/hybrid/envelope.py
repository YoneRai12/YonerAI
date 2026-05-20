from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping


HYBRID_ENVELOPE_CONTRACT_VERSION = "hybrid-signed-envelope-0.1"
DEFAULT_CONTROL_PLANE_AUDIENCE = "yonerai-official-control-plane"
ALLOWED_ENVELOPE_TYPES = frozenset(
    {
        "conversation_result",
        "memory_candidate",
        "self_evolution_signal",
        "improvement_proposal",
        "tool_result",
    }
)
ALLOWED_DATA_CLASSES = frozenset(
    {
        "conversation_metadata",
        "local_llm_result",
        "memory_candidate",
        "self_evolution_signal",
        "improvement_proposal",
        "tool_result",
    }
)
ALLOWED_PURPOSES = frozenset(
    {
        "conversation_continuation",
        "memory_candidate_review",
        "self_evolution_proposal",
        "local_result_donation",
        "tool_result_review",
    }
)
ALLOWED_SIGNATURE_ALGORITHMS = frozenset({"test-static-signature"})


@dataclass(frozen=True)
class HybridEnvelopeSignature:
    algorithm: str
    key_id: str
    signature: str


@dataclass(frozen=True)
class HybridSignedEnvelope:
    envelope_type: str
    issuer_node_id: str
    audience: str
    session_id: str
    conversation_id: str
    capability: str
    data_class: str
    purpose: str
    issued_at: str
    expires_at: str
    nonce: str
    payload_hash: str
    payload: Mapping[str, Any]
    signature: HybridEnvelopeSignature
    subject_user_id: str | None = None
    account_ref: str | None = None
    contract_version: str = HYBRID_ENVELOPE_CONTRACT_VERSION


def canonical_payload_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_payload_hash(payload: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(canonical_payload_json(payload).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def parse_envelope_datetime(value: str) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def validate_hybrid_envelope(
    envelope: HybridSignedEnvelope,
    *,
    expected_audience: str = DEFAULT_CONTROL_PLANE_AUDIENCE,
    now: datetime | None = None,
) -> list[str]:
    errors: list[str] = []

    required_fields = {
        "envelope_type": envelope.envelope_type,
        "issuer_node_id": envelope.issuer_node_id,
        "audience": envelope.audience,
        "session_id": envelope.session_id,
        "conversation_id": envelope.conversation_id,
        "capability": envelope.capability,
        "data_class": envelope.data_class,
        "purpose": envelope.purpose,
        "issued_at": envelope.issued_at,
        "expires_at": envelope.expires_at,
        "nonce": envelope.nonce,
        "payload_hash": envelope.payload_hash,
        "signature.algorithm": envelope.signature.algorithm,
        "signature.key_id": envelope.signature.key_id,
        "signature.signature": envelope.signature.signature,
    }
    for field_name, value in required_fields.items():
        if not str(value or "").strip():
            errors.append(f"{field_name}_required")

    if not (envelope.subject_user_id or envelope.account_ref):
        errors.append("subject_or_account_ref_required")
    if envelope.contract_version != HYBRID_ENVELOPE_CONTRACT_VERSION:
        errors.append("unsupported_contract_version")
    if envelope.envelope_type not in ALLOWED_ENVELOPE_TYPES:
        errors.append("unsupported_envelope_type")
    if envelope.data_class not in ALLOWED_DATA_CLASSES:
        errors.append("unsupported_data_class")
    if envelope.purpose not in ALLOWED_PURPOSES:
        errors.append("unsupported_purpose")
    if envelope.signature.algorithm not in ALLOWED_SIGNATURE_ALGORITHMS:
        errors.append("unsupported_signature_algorithm")
    if envelope.audience != expected_audience:
        errors.append("wrong_audience")
    if envelope.payload_hash != canonical_payload_hash(envelope.payload):
        errors.append("payload_hash_mismatch")

    try:
        issued_at = parse_envelope_datetime(envelope.issued_at)
        expires_at = parse_envelope_datetime(envelope.expires_at)
    except ValueError:
        errors.append("invalid_timestamp")
    else:
        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        if expires_at <= issued_at:
            errors.append("invalid_expiry_window")
        if current < issued_at:
            errors.append("not_yet_valid")
        if current >= expires_at:
            errors.append("expired_envelope")

    return errors
