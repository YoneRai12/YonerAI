from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Protocol

from .envelope import DEFAULT_CONTROL_PLANE_AUDIENCE, HybridSignedEnvelope, validate_hybrid_envelope


DONATION_ACTION_REJECT = "reject"
DONATION_ACTION_QUARANTINE = "quarantine"
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
        "local_file_path",
        "local_path",
        "password",
        "private_key",
        "raw_completion",
        "raw_prompt",
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

    if reasons:
        return DonationPolicyDecision(
            action=DONATION_ACTION_REJECT,
            trusted=False,
            requires_approval=True,
            reasons=tuple(reasons),
        )

    return DonationPolicyDecision(
        action=DONATION_ACTION_QUARANTINE,
        trusted=False,
        requires_approval=True,
        reasons=("signed_origin_verified_policy_quarantine_required",),
    )
