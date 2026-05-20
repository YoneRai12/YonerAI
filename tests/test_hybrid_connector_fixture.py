from __future__ import annotations

import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
core_src = repo_root / "core" / "src"
if str(core_src) not in sys.path:
    sys.path.insert(0, str(core_src))

from ora_core.hybrid import (  # noqa: E402
    FIXTURE_NOW,
    HybridEnvelopeSignature,
    HybridSignedEnvelope,
    build_improvement_proposal_fixture,
    build_memory_candidate_fixture,
    build_self_evolution_signal_fixture,
    canonical_payload_hash,
    envelope_from_mapping,
    envelope_to_mapping,
    evaluate_donation_policy,
    evaluate_memory_candidate_policy,
)
from ora_core.hybrid.connector_fixture import build_fixture_envelope, build_fixture_trust_registry  # noqa: E402
from ora_core.hybrid.policy import InMemoryNonceStore, StaticSignatureVerifier  # noqa: E402


def _evaluate_fixture(fixture):
    return evaluate_donation_policy(
        fixture.envelope,
        trust_registry=fixture.trust_registry,
        nonce_store=fixture.nonce_store,
        signature_verifier=fixture.signature_verifier,
        now=FIXTURE_NOW,
    )


def test_memory_candidate_fixture_is_signed_hash_valid_and_quarantined() -> None:
    fixture = build_memory_candidate_fixture()

    assert fixture.envelope.payload_hash == canonical_payload_hash(fixture.envelope.payload)
    policy = evaluate_memory_candidate_policy(fixture.envelope)
    decision = _evaluate_fixture(fixture)

    assert policy.status == "quarantined"
    assert policy.memory_persisted is False
    assert policy.requires_approval is True
    assert decision.action == "quarantine"
    assert decision.trusted is False
    assert decision.requires_approval is True


def test_fixture_mapping_round_trip_preserves_public_contract_shape() -> None:
    fixture = build_memory_candidate_fixture()
    envelope_mapping = fixture.envelope_mapping()

    restored = envelope_from_mapping(envelope_mapping)

    assert envelope_mapping == envelope_to_mapping(restored)
    assert restored.payload_hash == canonical_payload_hash(restored.payload)
    assert restored.signature.algorithm == "test-static-signature"


def test_self_evolution_signal_fixture_queues_only_after_policy_quarantine() -> None:
    fixture = build_self_evolution_signal_fixture()

    decision = _evaluate_fixture(fixture)

    assert decision.action == "quarantine"
    assert decision.trusted is False
    assert decision.requires_approval is True
    assert fixture.envelope.payload["automatic_mutation"] is False


def test_payload_approval_fields_do_not_override_policy_decision() -> None:
    envelope = build_fixture_envelope(
        envelope_type="conversation_result",
        capability="local_llm_result_donation",
        data_class="local_llm_result",
        purpose="local_result_donation",
        nonce="fixture-payload-approval-state",
        payload={
            "reply_summary": "Synthetic local result.",
            "approval_required": False,
            "approved": True,
            "approval_state": "approved",
        },
    )

    decision = evaluate_donation_policy(
        envelope,
        trust_registry=build_fixture_trust_registry(),
        nonce_store=InMemoryNonceStore(),
        signature_verifier=build_memory_candidate_fixture().signature_verifier,
        now=FIXTURE_NOW,
    )

    assert decision.action == "quarantine"
    assert decision.trusted is False
    assert decision.requires_approval is True


def test_improvement_proposal_fixture_requires_owner_review_fields() -> None:
    complete = build_improvement_proposal_fixture()
    incomplete = build_fixture_envelope(
        envelope_type="improvement_proposal",
        capability="improvement_proposal_review",
        data_class="improvement_proposal",
        purpose="self_evolution_proposal",
        nonce="fixture-incomplete-proposal",
        payload={"proposal_summary": "Missing required safety fields.", "automatic_mutation": False},
    )

    complete_decision = _evaluate_fixture(complete)
    incomplete_decision = evaluate_donation_policy(
        incomplete,
        trust_registry=build_fixture_trust_registry(),
        nonce_store=InMemoryNonceStore(),
        signature_verifier=complete.signature_verifier,
        now=FIXTURE_NOW,
    )

    assert complete_decision.action == "quarantine"
    assert incomplete_decision.action == "reject"
    assert "improvement_proposal_required_fields_missing" in incomplete_decision.reasons


def test_memory_candidate_envelope_type_cannot_bypass_policy_with_spoofed_data_class() -> None:
    envelope = build_fixture_envelope(
        envelope_type="memory_candidate",
        capability="memory_candidate_review",
        data_class="local_llm_result",
        purpose="memory_candidate_review",
        nonce="memory-candidate-spoofed-data-class",
        payload={"candidate_summary": "Synthetic memory candidate.", "memory_persisted": True},
    )

    decision = evaluate_donation_policy(
        envelope,
        trust_registry=build_fixture_trust_registry(),
        nonce_store=InMemoryNonceStore(),
        signature_verifier=build_memory_candidate_fixture().signature_verifier,
        now=FIXTURE_NOW,
    )

    assert decision.action == "reject"
    assert "not_memory_candidate_data_class" in decision.reasons
    assert "memory_persistence_not_allowed" in decision.reasons


def test_memory_candidate_capability_and_purpose_cannot_bypass_policy_with_spoofed_data_class() -> None:
    envelope = build_fixture_envelope(
        envelope_type="conversation_result",
        capability="memory_candidate_review",
        data_class="local_llm_result",
        purpose="memory_candidate_review",
        nonce="memory-candidate-capability-purpose-spoof",
        payload={"candidate_summary": "Synthetic memory candidate.", "memory_persisted": True},
    )

    decision = evaluate_donation_policy(
        envelope,
        trust_registry=build_fixture_trust_registry(),
        nonce_store=InMemoryNonceStore(),
        signature_verifier=build_memory_candidate_fixture().signature_verifier,
        now=FIXTURE_NOW,
    )

    assert decision.action == "reject"
    assert "not_memory_candidate_envelope" in decision.reasons
    assert "not_memory_candidate_data_class" in decision.reasons
    assert "memory_persistence_not_allowed" in decision.reasons


def test_improvement_proposal_envelope_type_cannot_bypass_payload_validation_with_spoofed_data_class() -> None:
    envelope = build_fixture_envelope(
        envelope_type="improvement_proposal",
        capability="improvement_proposal_review",
        data_class="local_llm_result",
        purpose="self_evolution_proposal",
        nonce="improvement-proposal-spoofed-data-class",
        payload={"proposal_summary": "Missing required safety fields.", "automatic_mutation": True},
    )

    decision = evaluate_donation_policy(
        envelope,
        trust_registry=build_fixture_trust_registry(),
        nonce_store=InMemoryNonceStore(),
        signature_verifier=build_improvement_proposal_fixture().signature_verifier,
        now=FIXTURE_NOW,
    )

    assert decision.action == "reject"
    assert "improvement_proposal_required_fields_missing" in decision.reasons
    assert "automatic_mutation_not_allowed" in decision.reasons


def test_improvement_proposal_capability_and_purpose_cannot_bypass_payload_validation_with_spoofed_data_class() -> None:
    envelope = build_fixture_envelope(
        envelope_type="conversation_result",
        capability="improvement_proposal_review",
        data_class="local_llm_result",
        purpose="self_evolution_proposal",
        nonce="improvement-proposal-capability-purpose-spoof",
        payload={"proposal_summary": "Missing required safety fields.", "automatic_mutation": True},
    )

    decision = evaluate_donation_policy(
        envelope,
        trust_registry=build_fixture_trust_registry(),
        nonce_store=InMemoryNonceStore(),
        signature_verifier=build_improvement_proposal_fixture().signature_verifier,
        now=FIXTURE_NOW,
    )

    assert decision.action == "reject"
    assert "improvement_proposal_required_fields_missing" in decision.reasons
    assert "automatic_mutation_not_allowed" in decision.reasons


def test_fixture_policy_rejects_replay_wrong_audience_expired_hash_and_bad_signature() -> None:
    fixture = build_memory_candidate_fixture()
    first = _evaluate_fixture(fixture)
    replay = _evaluate_fixture(fixture)

    wrong_audience = build_memory_candidate_fixture(nonce="wrong-audience")
    wrong_audience_envelope = build_fixture_envelope(
        envelope_type=wrong_audience.envelope.envelope_type,
        capability=wrong_audience.envelope.capability,
        data_class=wrong_audience.envelope.data_class,
        purpose=wrong_audience.envelope.purpose,
        payload=dict(wrong_audience.envelope.payload),
        nonce=wrong_audience.envelope.nonce,
        audience="public-core",
    )
    expired = build_fixture_envelope(
        envelope_type="memory_candidate",
        capability="memory_candidate_review",
        data_class="memory_candidate",
        purpose="memory_candidate_review",
        payload=dict(fixture.envelope.payload),
        nonce="expired",
        expires_at="2026-05-20T07:01:00Z",
    )
    hash_mismatch = replace(fixture.envelope, nonce="hash-mismatch", payload_hash="sha256:bad")
    bad_signature = replace(
        fixture.envelope,
        nonce="bad-signature",
        signature=HybridEnvelopeSignature(
            algorithm="test-static-signature",
            key_id="fixture-key-1",
            signature="tampered",
        ),
    )

    def evaluate(envelope):
        return evaluate_donation_policy(
            envelope,
            trust_registry=build_fixture_trust_registry(),
            nonce_store=InMemoryNonceStore(),
            signature_verifier=fixture.signature_verifier,
            now=FIXTURE_NOW,
        )

    assert first.action == "quarantine"
    assert replay.action == "reject"
    assert "replayed_nonce" in replay.reasons
    assert evaluate(wrong_audience_envelope).action == "reject"
    assert "wrong_audience" in evaluate(wrong_audience_envelope).reasons
    assert evaluate(expired).action == "reject"
    assert "expired_envelope" in evaluate(expired).reasons
    assert evaluate(hash_mismatch).action == "reject"
    assert "payload_hash_mismatch" in evaluate(hash_mismatch).reasons
    assert evaluate(bad_signature).action == "reject"
    assert "invalid_signature" in evaluate(bad_signature).reasons


def test_memory_candidate_rejects_secret_cot_private_inventory_and_live_route_map() -> None:
    forbidden_payloads = [
        {"candidate_summary": "bad", "memory_persisted": False, "chain_of_thought": "hidden reasoning"},
        {"candidate_summary": "bad", "memory_persisted": False, "private_runtime_inventory": ["internal"]},
        {"candidate_summary": "bad", "memory_persisted": False, "live_route_map": {"internal": "route"}},
        {"candidate_summary": "bad", "memory_persisted": True},
    ]

    for index, payload in enumerate(forbidden_payloads):
        envelope = build_fixture_envelope(
            envelope_type="memory_candidate",
            capability="memory_candidate_review",
            data_class="memory_candidate",
            purpose="memory_candidate_review",
            payload=payload,
            nonce=f"forbidden-{index}",
        )
        memory_policy = evaluate_memory_candidate_policy(envelope)
        decision = evaluate_donation_policy(
            envelope,
            trust_registry=build_fixture_trust_registry(),
            nonce_store=InMemoryNonceStore(),
            signature_verifier=StaticSignatureVerifier(
                {("fixture-local-node", "fixture-key-1"): "fixture-valid-static-signature"}
            ),
            now=datetime(2026, 5, 20, 7, 5, tzinfo=timezone.utc),
        )

        assert memory_policy.status == "rejected"
        assert decision.action == "reject"
