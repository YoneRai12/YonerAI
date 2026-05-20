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


def envelope_to_mapping(envelope: HybridSignedEnvelope) -> dict[str, Any]:
    return {
        "contract_version": envelope.contract_version,
        "envelope_type": envelope.envelope_type,
        "issuer_node_id": envelope.issuer_node_id,
        "subject_user_id": envelope.subject_user_id,
        "account_ref": envelope.account_ref,
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
        "payload": dict(envelope.payload),
        "signature": {
            "algorithm": envelope.signature.algorithm,
            "key_id": envelope.signature.key_id,
            "signature": envelope.signature.signature,
        },
    }


def envelope_from_mapping(data: Mapping[str, Any]) -> HybridSignedEnvelope:
    signature_data = data.get("signature")
    if not isinstance(signature_data, Mapping):
        signature_data = {}
    payload = data.get("payload")
    if not isinstance(payload, Mapping):
        payload = {}
    return HybridSignedEnvelope(
        contract_version=str(data.get("contract_version") or HYBRID_ENVELOPE_CONTRACT_VERSION),
        envelope_type=str(data.get("envelope_type") or ""),
        issuer_node_id=str(data.get("issuer_node_id") or ""),
        subject_user_id=data.get("subject_user_id") if data.get("subject_user_id") is not None else None,
        account_ref=data.get("account_ref") if data.get("account_ref") is not None else None,
        audience=str(data.get("audience") or ""),
        session_id=str(data.get("session_id") or ""),
        conversation_id=str(data.get("conversation_id") or ""),
        capability=str(data.get("capability") or ""),
        data_class=str(data.get("data_class") or ""),
        purpose=str(data.get("purpose") or ""),
        issued_at=str(data.get("issued_at") or ""),
        expires_at=str(data.get("expires_at") or ""),
        nonce=str(data.get("nonce") or ""),
        payload_hash=str(data.get("payload_hash") or ""),
        payload=payload,
        signature=HybridEnvelopeSignature(
            algorithm=str(signature_data.get("algorithm") or ""),
            key_id=str(signature_data.get("key_id") or ""),
            signature=str(signature_data.get("signature") or ""),
        ),
    )


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
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        current = current.astimezone(timezone.utc)
        if expires_at <= issued_at:
            errors.append("invalid_expiry_window")
        if current < issued_at:
            errors.append("not_yet_valid")
        if current >= expires_at:
            errors.append("expired_envelope")

    return errors
