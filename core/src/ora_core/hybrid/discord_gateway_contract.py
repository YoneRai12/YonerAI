from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .envelope import HybridSignedEnvelope


DISCORD_GATEWAY_PREFLIGHT_CONTRACT_VERSION = "discord-hybrid-signed-contract-preflight-0.1"
DISCORD_GATEWAY_MODES = frozenset({"official_hybrid_private", "full_private_self_host"})
DISCORD_TERMINAL_EVENTS = frozenset({"final", "controlled_error"})
DISCORD_REQUIRED_EVENTS = frozenset({"mention_received", "bootstrap_status_embed", "progress_edit_sent"})
DISCORD_PUBLIC_SAFE_FORBIDDEN_KEYS = frozenset(
    {
        "raw_prompt",
        "raw_completion",
        "chain_of_thought",
        "discord_token",
        "bot_token",
        "private_runtime_inventory",
        "break_glass",
        "control_plane_routes",
        "local_absolute_path",
    }
)
DISCORD_PUBLIC_SAFE_FORBIDDEN_VALUE_MARKERS = (
    "C:" + "\\Users\\",
    "/" + "home/",
    "/" + "Users/",
    "-----BEGIN ",
    "DISCORD_BOT_TOKEN",
)


@dataclass(frozen=True)
class DiscordGatewayContractDecision:
    ok: bool
    errors: tuple[str, ...] = field(default_factory=tuple)


def build_synthetic_discord_gateway_payload(
    *,
    node_id: str,
    final_text: str = "Synthetic Discord gateway response.",
) -> dict[str, Any]:
    return {
        "contract_version": DISCORD_GATEWAY_PREFLIGHT_CONTRACT_VERSION,
        "gateway_mode": "official_hybrid_private",
        "production_reply_source": "private_gateway",
        "public_python_bot_role": "legacy_public_residue_not_responder",
        "responder_policy": {
            "canonical_responder": "private_gateway",
            "private_gateway_responder": True,
            "public_python_bot_responder": False,
        },
        "node_identity": {"node_id": node_id, "mode": "official_hybrid_private"},
        "message_ref": {
            "guild_ref": "guild-fixture",
            "channel_ref": "channel-fixture",
            "message_ref": "message-fixture",
            "reply_to_ref": "parent-message-fixture",
        },
        "reply_chain_policy": {"continue_thread": True},
        "files_policy": {"file_refs_only": True, "external_url_direct_download": False},
        "live_discord": False,
        "credentials_required": False,
        "synthetic_fixture": True,
        "events": [
            {"event": "mention_received", "sequence": 1},
            {"event": "bootstrap_status_embed", "sequence": 2, "status_message_ref": "status-message-fixture"},
            {
                "event": "progress_edit_sent",
                "sequence": 3,
                "status": "queued",
                "status_message_ref": "status-message-fixture",
            },
            {
                "event": "progress_edit_sent",
                "sequence": 4,
                "status": "running",
                "status_message_ref": "status-message-fixture",
            },
            {
                "event": "final",
                "sequence": 5,
                "output_text": final_text,
                "status_message_ref": "status-message-fixture",
                "downloads": [{"file_ref": "fileref:fixture-discord-result", "label": "result.txt"}],
            },
        ],
    }


def validate_discord_gateway_payload(payload: Mapping[str, Any]) -> DiscordGatewayContractDecision:
    errors: list[str] = []

    if payload.get("contract_version") != DISCORD_GATEWAY_PREFLIGHT_CONTRACT_VERSION:
        errors.append("unsupported_contract_version")
    if payload.get("gateway_mode") not in DISCORD_GATEWAY_MODES:
        errors.append("unsupported_gateway_mode")
    if payload.get("production_reply_source") != "private_gateway":
        errors.append("private_gateway_required")
    if payload.get("public_python_bot_role") in {"responder", "production_responder"}:
        errors.append("public_python_bot_must_not_respond")
    _validate_responder_policy(payload.get("responder_policy"), errors)
    if payload.get("live_discord") is not False:
        errors.append("live_discord_not_allowed")
    if payload.get("credentials_required") is not False:
        errors.append("live_credentials_not_allowed")
    if payload.get("synthetic_fixture") is not True:
        errors.append("synthetic_fixture_required")
    _validate_public_safe_payload(payload, errors)

    node_identity = payload.get("node_identity")
    if not isinstance(node_identity, Mapping) or not str(node_identity.get("node_id") or "").strip():
        errors.append("node_identity_required")
    elif node_identity.get("mode") != payload.get("gateway_mode"):
        errors.append("node_identity_mode_must_match_gateway_mode")

    message_ref = payload.get("message_ref")
    if not isinstance(message_ref, Mapping):
        errors.append("message_ref_required")
    else:
        for key in ("channel_ref", "message_ref", "reply_to_ref"):
            if not str(message_ref.get(key) or "").strip():
                errors.append(f"{key}_required")

    reply_policy = payload.get("reply_chain_policy")
    if not isinstance(reply_policy, Mapping) or reply_policy.get("continue_thread") is not True:
        errors.append("reply_chain_continuation_required")

    files_policy = payload.get("files_policy")
    if not isinstance(files_policy, Mapping):
        errors.append("files_policy_required")
    else:
        if files_policy.get("file_refs_only") is not True:
            errors.append("file_refs_only_required")
        if files_policy.get("external_url_direct_download") is not False:
            errors.append("external_url_direct_download_not_allowed")

    events = payload.get("events")
    if not isinstance(events, list) or not events:
        errors.append("events_required")
        return _decision(errors)

    event_names: list[str] = []
    sequences: list[int] = []
    terminal_count = 0
    terminal_index = -1
    status_message_ref = ""
    for event in events:
        if not isinstance(event, Mapping):
            errors.append("event_object_required")
            continue
        event_name = str(event.get("event") or "")
        event_names.append(event_name)
        sequence = event.get("sequence")
        if not isinstance(sequence, int):
            errors.append("event_sequence_required")
        else:
            sequences.append(sequence)
        if event_name == "bootstrap_status_embed":
            status_message_ref = str(event.get("status_message_ref") or "")
            if not status_message_ref:
                errors.append("status_message_ref_required")
        if event_name == "progress_edit_sent" and not str(event.get("status_message_ref") or "").strip():
            errors.append("progress_status_message_ref_required")
        if event_name in DISCORD_TERMINAL_EVENTS:
            terminal_count += 1
            terminal_index = len(event_names) - 1
            if status_message_ref and event.get("status_message_ref") != status_message_ref:
                errors.append("terminal_status_message_ref_must_match")
            if event_name == "final" and not str(event.get("output_text") or "").strip():
                errors.append("final_output_text_required")
            if event_name == "controlled_error" and not str(event.get("safe_message") or "").strip():
                errors.append("controlled_error_safe_message_required")
        for download in event.get("downloads") or []:
            if not isinstance(download, Mapping):
                errors.append("download_object_required")
                continue
            if "url" in download or "download_url" in download:
                errors.append("external_download_url_not_allowed")
            if not str(download.get("file_ref") or "").startswith("fileref:"):
                errors.append("download_file_ref_required")

    missing = DISCORD_REQUIRED_EVENTS - set(event_names)
    if missing:
        errors.append("required_event_missing")
    if terminal_count != 1:
        errors.append("terminal_event_must_be_exactly_once")
    if sequences != sorted(sequences) or len(sequences) != len(set(sequences)):
        errors.append("event_sequence_must_be_strictly_increasing")
    if terminal_index != -1 and terminal_index != len(event_names) - 1:
        errors.append("terminal_event_must_be_last")
    if "progress_edit_sent" in event_names and terminal_index != -1:
        first_progress_index = event_names.index("progress_edit_sent")
        if first_progress_index > terminal_index:
            errors.append("progress_edit_must_precede_terminal")

    return _decision(errors)


def validate_discord_gateway_envelope(envelope: HybridSignedEnvelope) -> DiscordGatewayContractDecision:
    decision = validate_discord_gateway_payload(envelope.payload)
    errors = list(decision.errors)
    node_identity = envelope.payload.get("node_identity")
    if isinstance(node_identity, Mapping) and node_identity.get("node_id") != envelope.issuer_node_id:
        errors.append("node_identity_must_match_envelope_issuer")
    return _decision(errors)


def _decision(errors: list[str]) -> DiscordGatewayContractDecision:
    unique_errors = tuple(dict.fromkeys(errors))
    return DiscordGatewayContractDecision(ok=not unique_errors, errors=unique_errors)


def _validate_responder_policy(value: object, errors: list[str]) -> None:
    if not isinstance(value, Mapping):
        errors.append("responder_policy_required")
        return
    if value.get("canonical_responder") != "private_gateway":
        errors.append("private_gateway_required")
    if value.get("private_gateway_responder") is not True:
        errors.append("private_gateway_responder_required")
    if value.get("public_python_bot_responder") is not False:
        errors.append("public_python_bot_must_not_respond")


def _validate_public_safe_payload(value: object, errors: list[str]) -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            normalized_key = str(key).lower()
            if normalized_key in DISCORD_PUBLIC_SAFE_FORBIDDEN_KEYS:
                errors.append("public_safe_payload_forbidden_key")
            _validate_public_safe_payload(nested, errors)
        return
    if isinstance(value, list):
        for nested in value:
            _validate_public_safe_payload(nested, errors)
        return
    if isinstance(value, str):
        if value.startswith(("sk-", "AKIA", "ASIA")):
            errors.append("public_safe_payload_secret_marker")
        if any(marker in value for marker in DISCORD_PUBLIC_SAFE_FORBIDDEN_VALUE_MARKERS):
            errors.append("public_safe_payload_private_marker")
