from __future__ import annotations

import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
core_src = repo_root / "core" / "src"
if str(core_src) not in sys.path:
    sys.path.insert(0, str(core_src))

from ora_core.hybrid import (  # noqa: E402
    FIXTURE_ISSUER_NODE_ID,
    FIXTURE_NOW,
    build_memory_candidate_fixture,
    build_synthetic_discord_gateway_payload,
    evaluate_donation_policy,
    validate_discord_gateway_envelope,
    validate_discord_gateway_payload,
)
from ora_core.hybrid.connector_fixture import build_fixture_envelope, build_fixture_trust_registry  # noqa: E402
from ora_core.hybrid.policy import InMemoryNonceStore  # noqa: E402


def _discord_gateway_envelope(payload: dict[str, object] | None = None):
    return build_fixture_envelope(
        envelope_type="conversation_result",
        capability="local_llm_result_donation",
        data_class="local_llm_result",
        purpose="local_result_donation",
        nonce="discord-gateway-fixture",
        payload=payload or build_synthetic_discord_gateway_payload(node_id=FIXTURE_ISSUER_NODE_ID),
    )


def test_signed_discord_gateway_fixture_is_valid_but_quarantined() -> None:
    envelope = _discord_gateway_envelope()

    contract = validate_discord_gateway_envelope(envelope)
    donation = evaluate_donation_policy(
        envelope,
        trust_registry=build_fixture_trust_registry(),
        nonce_store=InMemoryNonceStore(),
        signature_verifier=build_memory_candidate_fixture().signature_verifier,
        now=FIXTURE_NOW,
    )

    assert contract.ok is True
    assert contract.errors == ()
    assert donation.action == "quarantine"
    assert donation.trusted is False
    assert donation.requires_approval is True


def test_discord_gateway_contract_denies_duplicate_terminal_and_public_responder() -> None:
    payload = build_synthetic_discord_gateway_payload(node_id=FIXTURE_ISSUER_NODE_ID)
    payload["public_python_bot_role"] = "production_responder"
    payload["responder_policy"] = {
        "canonical_responder": "public_python_bot",
        "private_gateway_responder": False,
        "public_python_bot_responder": True,
    }
    payload["events"] = [
        *payload["events"],
        {"event": "final", "sequence": 6, "output_text": "duplicate"},
    ]

    decision = validate_discord_gateway_payload(payload)

    assert decision.ok is False
    assert "public_python_bot_must_not_respond" in decision.errors
    assert "private_gateway_required" in decision.errors
    assert "private_gateway_responder_required" in decision.errors
    assert "terminal_event_must_be_exactly_once" in decision.errors


def test_discord_gateway_contract_denies_live_credentials_and_external_downloads() -> None:
    payload = build_synthetic_discord_gateway_payload(node_id=FIXTURE_ISSUER_NODE_ID)
    payload["live_discord"] = True
    payload["credentials_required"] = True
    payload["files_policy"] = {"file_refs_only": False, "external_url_direct_download": True}
    payload["events"][-1]["downloads"] = [{"download_url": "https://example.invalid/file.txt"}]

    decision = validate_discord_gateway_payload(payload)

    assert decision.ok is False
    assert "live_discord_not_allowed" in decision.errors
    assert "live_credentials_not_allowed" in decision.errors
    assert "file_refs_only_required" in decision.errors
    assert "external_url_direct_download_not_allowed" in decision.errors
    assert "external_download_url_not_allowed" in decision.errors
    assert "download_file_ref_required" in decision.errors


def test_discord_gateway_contract_accepts_controlled_error_as_terminal() -> None:
    payload = build_synthetic_discord_gateway_payload(node_id=FIXTURE_ISSUER_NODE_ID)
    payload["events"][-1] = {
        "event": "controlled_error",
        "sequence": 5,
        "safe_message": "The synthetic gateway returned a controlled error.",
        "status_message_ref": "status-message-fixture",
    }

    decision = validate_discord_gateway_payload(payload)

    assert decision.ok is True
    assert decision.errors == ()


def test_discord_gateway_contract_requires_ordered_same_message_edit_flow() -> None:
    payload = build_synthetic_discord_gateway_payload(node_id=FIXTURE_ISSUER_NODE_ID)
    payload["events"] = [
        {"event": "mention_received", "sequence": 1},
        {
            "event": "progress_edit_sent",
            "sequence": 4,
            "status": "running",
            "status_message_ref": "different-status-message",
        },
        {
            "event": "final",
            "sequence": 3,
            "output_text": "done",
            "status_message_ref": "status-message-fixture",
        },
        {"event": "bootstrap_status_embed", "sequence": 2, "status_message_ref": "status-message-fixture"},
    ]

    decision = validate_discord_gateway_payload(payload)

    assert decision.ok is False
    assert "event_sequence_must_be_strictly_increasing" in decision.errors
    assert "terminal_event_must_be_last" in decision.errors
    assert "progress_edit_must_precede_terminal" not in decision.errors


def test_discord_gateway_contract_rejects_public_unsafe_payload_fields() -> None:
    payload = build_synthetic_discord_gateway_payload(node_id=FIXTURE_ISSUER_NODE_ID)
    payload["raw_prompt"] = "do not publish raw prompts"
    payload["diagnostics"] = {
        "chain_of_thought": "private reasoning must not be exposed",
        "path": "C:" + "\\Users\\Example\\private-runtime.txt",
        "token": "sk-" + "testmarkerthatshouldnotbeaccepted",
    }

    decision = validate_discord_gateway_payload(payload)

    assert decision.ok is False
    assert "public_safe_payload_forbidden_key" in decision.errors
    assert "public_safe_payload_private_marker" in decision.errors
    assert "public_safe_payload_secret_marker" in decision.errors


def test_discord_gateway_node_mode_must_match_gateway_mode() -> None:
    payload = build_synthetic_discord_gateway_payload(node_id=FIXTURE_ISSUER_NODE_ID)
    payload["node_identity"] = {"node_id": FIXTURE_ISSUER_NODE_ID, "mode": "full_private_self_host"}

    decision = validate_discord_gateway_payload(payload)

    assert decision.ok is False
    assert "node_identity_mode_must_match_gateway_mode" in decision.errors


def test_discord_gateway_contract_requires_reply_chain_and_progress_flow() -> None:
    payload = build_synthetic_discord_gateway_payload(node_id=FIXTURE_ISSUER_NODE_ID)
    payload["message_ref"] = {"channel_ref": "channel-fixture", "message_ref": "message-fixture"}
    payload["reply_chain_policy"] = {"continue_thread": False}
    payload["events"] = [{"event": "final", "sequence": 1, "output_text": "done"}]

    decision = validate_discord_gateway_payload(payload)

    assert decision.ok is False
    assert "reply_to_ref_required" in decision.errors
    assert "reply_chain_continuation_required" in decision.errors
    assert "required_event_missing" in decision.errors


def test_discord_gateway_node_identity_must_match_signed_issuer() -> None:
    payload = build_synthetic_discord_gateway_payload(node_id="different-node")
    envelope = _discord_gateway_envelope(payload)

    decision = validate_discord_gateway_envelope(envelope)

    assert decision.ok is False
    assert "node_identity_must_match_envelope_issuer" in decision.errors
