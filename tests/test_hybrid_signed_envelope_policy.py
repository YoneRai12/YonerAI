from __future__ import annotations

import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
core_src = repo_root / "core" / "src"
if str(core_src) not in sys.path:
    sys.path.insert(0, str(core_src))

from ora_core.hybrid import (  # noqa: E402
    HybridEnvelopeSignature,
    HybridSignedEnvelope,
    InMemoryNonceStore,
    InMemoryTrustRegistry,
    StaticSignatureVerifier,
    TrustRegistryEntry,
    canonical_payload_hash,
    evaluate_donation_policy,
)


NOW = datetime(2026, 5, 20, 6, 0, tzinfo=timezone.utc)


def _valid_envelope(**overrides) -> HybridSignedEnvelope:
    payload = overrides.pop(
        "payload",
        {
            "reply_summary": "Local model returned a short answer.",
            "provider": "local-openai-compatible",
            "model": "local-model",
        },
    )
    data = {
        "envelope_type": "conversation_result",
        "issuer_node_id": "node_public_smoke",
        "subject_user_id": "acct_public_smoke",
        "account_ref": None,
        "audience": "yonerai-official-control-plane",
        "session_id": "session-alpha",
        "conversation_id": "conversation-alpha",
        "capability": "local_llm_result_donation",
        "data_class": "local_llm_result",
        "purpose": "local_result_donation",
        "issued_at": "2026-05-20T05:59:00Z",
        "expires_at": "2026-05-20T06:05:00Z",
        "nonce": "nonce-alpha",
        "payload_hash": canonical_payload_hash(payload),
        "payload": payload,
        "signature": HybridEnvelopeSignature(
            algorithm="test-static-signature",
            key_id="test-key-1",
            signature="valid-test-signature",
        ),
    }
    data.update(overrides)
    if "payload" in overrides and "payload_hash" not in overrides:
        data["payload_hash"] = canonical_payload_hash(overrides["payload"])
    return HybridSignedEnvelope(**data)


def _trusted_registry() -> InMemoryTrustRegistry:
    return InMemoryTrustRegistry(
        {
            "node_public_smoke": TrustRegistryEntry(
                issuer_node_id="node_public_smoke",
                key_id="test-key-1",
                allowed_capabilities=frozenset({"local_llm_result_donation", "memory_candidate_review"}),
            )
        }
    )


def _verifier() -> StaticSignatureVerifier:
    return StaticSignatureVerifier({("node_public_smoke", "test-key-1"): "valid-test-signature"})


def _evaluate(envelope: HybridSignedEnvelope, nonce_store: InMemoryNonceStore | None = None):
    return evaluate_donation_policy(
        envelope,
        trust_registry=_trusted_registry(),
        nonce_store=nonce_store or InMemoryNonceStore(),
        signature_verifier=_verifier(),
        now=NOW,
    )


def test_valid_signed_donation_is_quarantined_not_trusted() -> None:
    decision = _evaluate(_valid_envelope())

    assert decision.action == "quarantine"
    assert decision.trusted is False
    assert decision.requires_approval is True
    assert decision.reasons == ("signed_origin_verified_policy_quarantine_required",)


def test_signature_validity_does_not_bypass_memory_candidate_policy() -> None:
    envelope = _valid_envelope(
        envelope_type="memory_candidate",
        capability="memory_candidate_review",
        data_class="memory_candidate",
        purpose="memory_candidate_review",
        payload={"candidate_summary": "User may prefer short replies.", "memory_persisted": False},
    )

    decision = _evaluate(envelope)

    assert decision.action == "quarantine"
    assert decision.trusted is False
    assert decision.requires_approval is True


def test_wrong_audience_expired_hash_mismatch_and_replay_are_rejected() -> None:
    wrong_audience = _evaluate(_valid_envelope(audience="public-core"))
    expired = _evaluate(_valid_envelope(expires_at="2026-05-20T05:59:30Z"))
    hash_mismatch = _evaluate(_valid_envelope(payload_hash="sha256:not-the-payload"))

    nonce_store = InMemoryNonceStore()
    first = _evaluate(_valid_envelope(nonce="nonce-replay"), nonce_store=nonce_store)
    replay = _evaluate(_valid_envelope(nonce="nonce-replay"), nonce_store=nonce_store)

    assert wrong_audience.action == "reject"
    assert "wrong_audience" in wrong_audience.reasons
    assert expired.action == "reject"
    assert "expired_envelope" in expired.reasons
    assert hash_mismatch.action == "reject"
    assert "payload_hash_mismatch" in hash_mismatch.reasons
    assert first.action == "quarantine"
    assert replay.action == "reject"
    assert "replayed_nonce" in replay.reasons


def test_unknown_revoked_or_overbroad_issuer_is_rejected() -> None:
    unknown = evaluate_donation_policy(
        _valid_envelope(issuer_node_id="unknown-node"),
        trust_registry=_trusted_registry(),
        nonce_store=InMemoryNonceStore(),
        signature_verifier=_verifier(),
        now=NOW,
    )
    revoked_registry = InMemoryTrustRegistry(
        {
            "node_public_smoke": TrustRegistryEntry(
                issuer_node_id="node_public_smoke",
                key_id="test-key-1",
                allowed_capabilities=frozenset({"local_llm_result_donation"}),
                revoked=True,
            )
        }
    )
    revoked = evaluate_donation_policy(
        _valid_envelope(),
        trust_registry=revoked_registry,
        nonce_store=InMemoryNonceStore(),
        signature_verifier=_verifier(),
        now=NOW,
    )
    disallowed_capability = _evaluate(_valid_envelope(capability="official_memory_write"))

    assert unknown.action == "reject"
    assert "unknown_issuer" in unknown.reasons
    assert revoked.action == "reject"
    assert "revoked_issuer" in revoked.reasons
    assert disallowed_capability.action == "reject"
    assert "capability_not_allowed" in disallowed_capability.reasons


def test_invalid_signature_and_secret_like_payload_are_rejected_without_trusting_payload() -> None:
    invalid_signature_data = deepcopy(_valid_envelope().__dict__)
    invalid_signature_data["signature"] = HybridEnvelopeSignature(
        algorithm="test-static-signature",
        key_id="test-key-1",
        signature="tampered",
    )
    invalid_signature = _evaluate(HybridSignedEnvelope(**invalid_signature_data))
    secret_payload = _evaluate(
        _valid_envelope(payload={"raw_prompt": "do not ingest", "result": "contains api key placeholder"})
    )
    token_payload = _evaluate(_valid_envelope(payload={"access_token": "placeholder"}))

    assert invalid_signature.action == "reject"
    assert "invalid_signature" in invalid_signature.reasons
    assert secret_payload.action == "reject"
    assert "forbidden_payload_marker" in secret_payload.reasons
    assert token_payload.action == "reject"
    assert "forbidden_payload_marker" in token_payload.reasons


def test_common_llm_token_count_metadata_is_not_rejected_by_substring_match() -> None:
    decision = _evaluate(
        _valid_envelope(
            payload={
                "reply_summary": "Local result summarized.",
                "usage": {"prompt_tokens": 4, "completion_tokens": 6, "total_tokens": 10},
            }
        )
    )

    assert decision.action == "quarantine"
    assert "forbidden_payload_marker" not in decision.reasons


def test_deep_payload_is_rejected_without_recursive_scan_error() -> None:
    nested = {}
    current = nested
    for index in range(40):
        current["child"] = {}
        current = current["child"]
        current["index"] = index

    decision = _evaluate(_valid_envelope(payload=nested))

    assert decision.action == "reject"
    assert "forbidden_payload_marker" in decision.reasons


def test_nonce_store_is_bounded_and_evicts_oldest_nonce() -> None:
    nonce_store = InMemoryNonceStore(max_entries=2)

    assert nonce_store.claim(issuer_node_id="node", audience="aud", nonce="one") is True
    assert nonce_store.claim(issuer_node_id="node", audience="aud", nonce="two") is True
    assert nonce_store.claim(issuer_node_id="node", audience="aud", nonce="three") is True
    assert nonce_store.claim(issuer_node_id="node", audience="aud", nonce="one") is True
    assert nonce_store.claim(issuer_node_id="node", audience="aud", nonce="three") is False


def test_unsupported_signature_algorithm_is_rejected_before_trust() -> None:
    envelope = _valid_envelope(
        signature=HybridEnvelopeSignature(
            algorithm="none",
            key_id="test-key-1",
            signature="valid-test-signature",
        )
    )

    decision = _evaluate(envelope)

    assert decision.action == "reject"
    assert "unsupported_signature_algorithm" in decision.reasons


def test_self_evolution_donation_is_quarantined_and_never_auto_mutates() -> None:
    envelope = _valid_envelope(
        envelope_type="self_evolution_signal",
        data_class="self_evolution_signal",
        purpose="self_evolution_proposal",
        payload={
            "signal_summary": "Synthetic fixture observed a wording mismatch.",
            "suggested_tests": ["contract_snapshot"],
            "automatic_mutation": False,
        },
    )

    decision = _evaluate(envelope)

    assert decision.action == "quarantine"
    assert decision.trusted is False
    assert decision.requires_approval is True
