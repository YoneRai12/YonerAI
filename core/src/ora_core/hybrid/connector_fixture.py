from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .envelope import (
    DEFAULT_CONTROL_PLANE_AUDIENCE,
    HybridEnvelopeSignature,
    HybridSignedEnvelope,
    canonical_payload_hash,
    envelope_to_mapping,
)
from .policy import InMemoryNonceStore, InMemoryTrustRegistry, StaticSignatureVerifier, TrustRegistryEntry


FIXTURE_ISSUER_NODE_ID = "fixture-local-node"
FIXTURE_SUBJECT_USER_ID = "fixture-account"
FIXTURE_KEY_ID = "fixture-key-1"
FIXTURE_SIGNATURE = "fixture-valid-static-signature"
FIXTURE_ISSUED_AT = "2026-05-20T07:00:00Z"
FIXTURE_EXPIRES_AT = "2026-05-20T07:10:00Z"
FIXTURE_NOW = datetime(2026, 5, 20, 7, 5, tzinfo=timezone.utc)


@dataclass(frozen=True)
class HybridConnectorFixture:
    envelope: HybridSignedEnvelope
    trust_registry: InMemoryTrustRegistry
    nonce_store: InMemoryNonceStore
    signature_verifier: StaticSignatureVerifier

    def envelope_mapping(self) -> dict[str, object]:
        return envelope_to_mapping(self.envelope)


def build_fixture_trust_registry() -> InMemoryTrustRegistry:
    return InMemoryTrustRegistry(
        {
            FIXTURE_ISSUER_NODE_ID: TrustRegistryEntry(
                issuer_node_id=FIXTURE_ISSUER_NODE_ID,
                key_id=FIXTURE_KEY_ID,
                allowed_capabilities=frozenset(
                    {
                        "local_llm_result_donation",
                        "memory_candidate_review",
                        "self_evolution_signal_donation",
                        "improvement_proposal_review",
                    }
                ),
            )
        }
    )


def build_fixture_signature_verifier() -> StaticSignatureVerifier:
    return StaticSignatureVerifier({(FIXTURE_ISSUER_NODE_ID, FIXTURE_KEY_ID): FIXTURE_SIGNATURE})


def _fixture_signature() -> HybridEnvelopeSignature:
    return HybridEnvelopeSignature(
        algorithm="test-static-signature",
        key_id=FIXTURE_KEY_ID,
        signature=FIXTURE_SIGNATURE,
    )


def build_fixture_envelope(
    *,
    envelope_type: str,
    capability: str,
    data_class: str,
    purpose: str,
    payload: dict[str, object],
    nonce: str,
    session_id: str = "fixture-session",
    conversation_id: str = "fixture-conversation",
    audience: str = DEFAULT_CONTROL_PLANE_AUDIENCE,
    issued_at: str = FIXTURE_ISSUED_AT,
    expires_at: str = FIXTURE_EXPIRES_AT,
) -> HybridSignedEnvelope:
    return HybridSignedEnvelope(
        envelope_type=envelope_type,
        issuer_node_id=FIXTURE_ISSUER_NODE_ID,
        subject_user_id=FIXTURE_SUBJECT_USER_ID,
        account_ref=None,
        audience=audience,
        session_id=session_id,
        conversation_id=conversation_id,
        capability=capability,
        data_class=data_class,
        purpose=purpose,
        issued_at=issued_at,
        expires_at=expires_at,
        nonce=nonce,
        payload_hash=canonical_payload_hash(payload),
        payload=payload,
        signature=_fixture_signature(),
    )


def build_memory_candidate_fixture(*, nonce: str = "fixture-memory-candidate") -> HybridConnectorFixture:
    envelope = build_fixture_envelope(
        envelope_type="memory_candidate",
        capability="memory_candidate_review",
        data_class="memory_candidate",
        purpose="memory_candidate_review",
        nonce=nonce,
        payload={
            "candidate_summary": "Synthetic user prefers concise public-safe answers.",
            "evidence_summary": "Fixture-only conversation metadata, no raw prompts or completions.",
            "source_session_id": "fixture-session",
            "source_conversation_id": "fixture-conversation",
            "memory_persisted": False,
            "approval_required": True,
            "retention_hint": "ephemeral_fixture",
        },
    )
    return HybridConnectorFixture(
        envelope=envelope,
        trust_registry=build_fixture_trust_registry(),
        nonce_store=InMemoryNonceStore(),
        signature_verifier=build_fixture_signature_verifier(),
    )


def build_self_evolution_signal_fixture(*, nonce: str = "fixture-self-evolution-signal") -> HybridConnectorFixture:
    envelope = build_fixture_envelope(
        envelope_type="self_evolution_signal",
        capability="self_evolution_signal_donation",
        data_class="self_evolution_signal",
        purpose="self_evolution_proposal",
        nonce=nonce,
        payload={
            "signal_summary": "Synthetic fixture observed that error copy needs a policy test.",
            "suggested_tests": ["hybrid_connector_fixture_policy"],
            "automatic_mutation": False,
            "privacy_risk": "synthetic_fixture_only",
            "hype_debt": "none",
            "provider_independence_score": 1.0,
            "same_experience_score": 1.0,
        },
    )
    return HybridConnectorFixture(
        envelope=envelope,
        trust_registry=build_fixture_trust_registry(),
        nonce_store=InMemoryNonceStore(),
        signature_verifier=build_fixture_signature_verifier(),
    )


def build_improvement_proposal_fixture(*, nonce: str = "fixture-improvement-proposal") -> HybridConnectorFixture:
    envelope = build_fixture_envelope(
        envelope_type="improvement_proposal",
        capability="improvement_proposal_review",
        data_class="improvement_proposal",
        purpose="self_evolution_proposal",
        nonce=nonce,
        payload={
            "proposal_summary": "Add a fixture-only policy regression test.",
            "test_plan": ["pytest tests/test_hybrid_connector_fixture.py"],
            "rollback_plan": "Revert the fixture-only change if it weakens policy behavior.",
            "privacy_risk": "low_synthetic_fixture_only",
            "hype_debt": "none",
            "provider_independence_score": 1.0,
            "same_experience_score": 1.0,
            "automatic_mutation": False,
        },
    )
    return HybridConnectorFixture(
        envelope=envelope,
        trust_registry=build_fixture_trust_registry(),
        nonce_store=InMemoryNonceStore(),
        signature_verifier=build_fixture_signature_verifier(),
    )
