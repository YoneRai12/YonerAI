from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Protocol

from .envelope import DEFAULT_CONTROL_PLANE_AUDIENCE, HybridSignedEnvelope, validate_hybrid_envelope


DONATION_ACTION_REJECT = "reject"
DONATION_ACTION_QUARANTINE = "quarantine"
MEMORY_STATUS_OBSERVED = "observed"
MEMORY_STATUS_QUARANTINED = "quarantined"
MEMORY_STATUS_REJECTED = "rejected"
MEMORY_STATUS_APPROVED_FOR_MEMORY = "approved_for_memory"
MEMORY_STATUS_EXPIRED = "expired"
MEMORY_CANDIDATE_ALLOWED_KEYS = frozenset(
    {
        "approval_required",
        "candidate_summary",
        "evidence_summary",
        "memory_persisted",
        "retention_hint",
        "source_conversation_id",
        "source_session_id",
    }
)
SELF_EVOLUTION_PROPOSAL_REQUIRED_KEYS = frozenset(
    {
        "proposal_summary",
        "test_plan",
        "rollback_plan",
        "privacy_risk",
        "hype_debt",
        "provider_independence_score",
        "same_experience_score",
    }
)
FORBIDDEN_PAYLOAD_KEYS = frozenset(
    {
        "api_key",
        "access_token",
        "refresh_token",
        "chain_of_thought",
        "client_secret",
        "credential",
        "discord_token",
        "google_client_secret",
        "live_route_map",
        "local_file_path",
        "local_path",
        "password",
        "private_runtime_inventory",
        "private_key",
        "raw_completion",
        "raw_prompt",
        "route_map",
        "secret",
        "token",
    }
)
PAYLOAD_SCAN_MAX_DEPTH = 32
PAYLOAD_SCAN_MAX_ITEMS = 4096
NONCE_STORE_MAX_ENTRIES = 4096
SECRET_VALUE_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{10,}"),
    re.compile("-----BEGIN " + r"[A-Z ]*PRIVATE KEY-----"),
    re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+", re.IGNORECASE),
    re.compile(r"(?:^|[\s\"'=])" + "/" + r"(root|etc|home|users|var|tmp)/", re.IGNORECASE),
)


class SignatureVerifier(Protocol):
    def verify(self, envelope: HybridSignedEnvelope, *, key_id: str) -> bool:
        """Return whether the signature is valid for the trusted key id."""


@dataclass(frozen=True)
class TrustRegistryEntry:
    issuer_node_id: str
    key_id: str
    allowed_capabilities: frozenset[str]
    revoked: bool = False


@dataclass(frozen=True)
class DonationPolicyDecision:
    action: str
    trusted: bool
    requires_approval: bool
    reasons: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class MemoryCandidatePolicyDecision:
    status: str
    memory_persisted: bool
    requires_approval: bool
    reasons: tuple[str, ...] = field(default_factory=tuple)


class InMemoryTrustRegistry:
    def __init__(self, entries: Mapping[str, TrustRegistryEntry] | None = None) -> None:
        self._entries = dict(entries or {})

    def get(self, issuer_node_id: str) -> TrustRegistryEntry | None:
        return self._entries.get(issuer_node_id)


class InMemoryNonceStore:
    def __init__(self, *, max_entries: int = NONCE_STORE_MAX_ENTRIES) -> None:
        if max_entries < 1:
            raise ValueError("max_entries must be at least 1")
        self._max_entries = max_entries
        self._seen: OrderedDict[tuple[str, str, str], None] = OrderedDict()

    def claim(self, *, issuer_node_id: str, audience: str, nonce: str) -> bool:
        key = (issuer_node_id, audience, nonce)
        if key in self._seen:
            return False
        self._seen[key] = None
        if len(self._seen) > self._max_entries:
            self._seen.popitem(last=False)
        return True


class StaticSignatureVerifier:
    """Test-oriented verifier used to exercise policy flow without production keys."""

    def __init__(self, valid_signatures: Mapping[tuple[str, str], str]) -> None:
        self._valid_signatures = dict(valid_signatures)

    def verify(self, envelope: HybridSignedEnvelope, *, key_id: str) -> bool:
        expected = self._valid_signatures.get((envelope.issuer_node_id, key_id))
        return expected is not None and envelope.signature.signature == expected


def _is_forbidden_payload_key(raw_key: Any) -> bool:
    key = re.sub(r"[-.\s]+", "_", str(raw_key).strip().lower())
    return key in FORBIDDEN_PAYLOAD_KEYS


def _normalized_payload_keys(payload: Mapping[str, Any]) -> set[str]:
    return {re.sub(r"[-.\s]+", "_", str(raw_key).strip().lower()) for raw_key in payload}


def _payload_contains_forbidden_marker(root: Any) -> bool:
    stack: list[tuple[Any, int]] = [(root, 0)]
    scanned = 0
    while stack:
        value, depth = stack.pop()
        scanned += 1
        if scanned > PAYLOAD_SCAN_MAX_ITEMS or depth > PAYLOAD_SCAN_MAX_DEPTH:
            return True
        if isinstance(value, Mapping):
            for raw_key, raw_value in value.items():
                if _is_forbidden_payload_key(raw_key):
                    return True
                stack.append((raw_value, depth + 1))
            continue
        if isinstance(value, (list, tuple, set)):
            for item in value:
                stack.append((item, depth + 1))
            continue
        if isinstance(value, str) and any(pattern.search(value) for pattern in SECRET_VALUE_PATTERNS):
            return True
    return False


def _has_memory_candidate_semantics(envelope: HybridSignedEnvelope) -> bool:
    return (
        envelope.envelope_type == "memory_candidate"
        or envelope.data_class == "memory_candidate"
        or envelope.capability == "memory_candidate_review"
        or envelope.purpose == "memory_candidate_review"
    )


def _has_improvement_proposal_semantics(envelope: HybridSignedEnvelope) -> bool:
    # `self_evolution_proposal` is also used by signal donations, so purpose alone
    # is not enough to apply proposal-payload requirements.
    return (
        envelope.envelope_type == "improvement_proposal"
        or envelope.data_class == "improvement_proposal"
        or envelope.capability == "improvement_proposal_review"
    )


def evaluate_memory_candidate_policy(envelope: HybridSignedEnvelope) -> MemoryCandidatePolicyDecision:
    reasons: list[str] = []
    payload = envelope.payload

    if envelope.envelope_type != "memory_candidate":
        reasons.append("not_memory_candidate_envelope")
    if envelope.data_class != "memory_candidate":
        reasons.append("not_memory_candidate_data_class")
    if envelope.capability != "memory_candidate_review":
        reasons.append("invalid_memory_candidate_capability")
    if envelope.purpose != "memory_candidate_review":
        reasons.append("invalid_memory_candidate_purpose")
    if not isinstance(payload, Mapping):
        reasons.append("memory_candidate_payload_not_object")
    else:
        normalized_keys = _normalized_payload_keys(payload)
        disallowed_keys = normalized_keys - MEMORY_CANDIDATE_ALLOWED_KEYS
        if disallowed_keys:
            reasons.append("memory_candidate_payload_field_not_allowed")
        if not str(payload.get("candidate_summary") or "").strip():
            reasons.append("candidate_summary_required")
        if payload.get("memory_persisted") is not False:
            reasons.append("memory_persistence_not_allowed")
        if _payload_contains_forbidden_marker(payload):
            reasons.append("forbidden_payload_marker")

    if reasons:
        return MemoryCandidatePolicyDecision(
            status=MEMORY_STATUS_REJECTED,
            memory_persisted=False,
            requires_approval=False,
            reasons=tuple(dict.fromkeys(reasons)),
        )
    return MemoryCandidatePolicyDecision(
        status=MEMORY_STATUS_QUARANTINED,
        memory_persisted=False,
        requires_approval=True,
        reasons=("memory_candidate_quarantine_required",),
    )


def validate_self_evolution_proposal_payload(envelope: HybridSignedEnvelope) -> tuple[str, ...]:
    if not _has_improvement_proposal_semantics(envelope):
        return ()
    reasons: list[str] = []
    if envelope.envelope_type != "improvement_proposal":
        reasons.append("not_improvement_proposal_envelope")
    if envelope.data_class != "improvement_proposal":
        reasons.append("not_improvement_proposal_data_class")
    if envelope.capability != "improvement_proposal_review":
        reasons.append("invalid_improvement_proposal_capability")
    if envelope.purpose != "self_evolution_proposal":
        reasons.append("invalid_improvement_proposal_purpose")
    payload = envelope.payload
    if not isinstance(payload, Mapping):
        reasons.append("improvement_proposal_payload_not_object")
        return tuple(dict.fromkeys(reasons))
    normalized_keys = _normalized_payload_keys(payload)
    missing = SELF_EVOLUTION_PROPOSAL_REQUIRED_KEYS - normalized_keys
    if missing:
        reasons.append("improvement_proposal_required_fields_missing")
    if payload.get("automatic_mutation") is not False:
        reasons.append("automatic_mutation_not_allowed")
    return tuple(dict.fromkeys(reasons))


def evaluate_donation_policy(
    envelope: HybridSignedEnvelope,
    *,
    trust_registry: InMemoryTrustRegistry,
    nonce_store: InMemoryNonceStore,
    signature_verifier: SignatureVerifier,
    expected_audience: str = DEFAULT_CONTROL_PLANE_AUDIENCE,
    now: datetime | None = None,
) -> DonationPolicyDecision:
    reasons: list[str] = []
    reasons.extend(validate_hybrid_envelope(envelope, expected_audience=expected_audience, now=now))

    trust_entry = trust_registry.get(envelope.issuer_node_id)
    if trust_entry is None:
        reasons.append("unknown_issuer")
    elif trust_entry.revoked:
        reasons.append("revoked_issuer")
    else:
        if trust_entry.key_id != envelope.signature.key_id:
            reasons.append("key_id_mismatch")
        if envelope.capability not in trust_entry.allowed_capabilities:
            reasons.append("capability_not_allowed")
        if not signature_verifier.verify(envelope, key_id=trust_entry.key_id):
            reasons.append("invalid_signature")

    if not nonce_store.claim(
        issuer_node_id=envelope.issuer_node_id,
        audience=envelope.audience,
        nonce=envelope.nonce,
    ):
        reasons.append("replayed_nonce")
    if _payload_contains_forbidden_marker(envelope.payload):
        reasons.append("forbidden_payload_marker")
    if _has_memory_candidate_semantics(envelope):
        memory_policy = evaluate_memory_candidate_policy(envelope)
        if memory_policy.status == MEMORY_STATUS_REJECTED:
            reasons.extend(memory_policy.reasons)
    reasons.extend(validate_self_evolution_proposal_payload(envelope))

    if reasons:
        return DonationPolicyDecision(
            action=DONATION_ACTION_REJECT,
            trusted=False,
            requires_approval=False,
            reasons=tuple(dict.fromkeys(reasons)),
        )

    return DonationPolicyDecision(
        action=DONATION_ACTION_QUARANTINE,
        trusted=False,
        requires_approval=True,
        reasons=("signed_origin_verified_policy_quarantine_required",),
    )
