from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from ora_core.hybrid import (
    FIXTURE_ISSUER_NODE_ID,
    build_synthetic_discord_gateway_payload,
    validate_discord_gateway_payload,
)


DISCORD_GATEWAY_ADAPTER_SCHEMA_VERSION = "yonerai-discord-gateway-adapter/v0.1"


@dataclass(frozen=True)
class DiscordGatewayAdapterResult:
    schema_version: str
    adapter: str
    ok: bool
    synthetic: bool
    live_discord: bool
    token_required: bool
    duplicate_responder_prevented: bool
    final_once: bool
    progress_events: int
    run_request: dict[str, object]
    payload: dict[str, Any]
    errors: tuple[str, ...]

    def to_public_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


class SyntheticDiscordGatewayAdapter:
    """Public-safe Discord gateway adapter for alpha fixtures.

    This adapter does not connect to Discord and does not require a token. It
    exercises the gateway event contract and responder policy using synthetic
    refs only.
    """

    adapter_id = "synthetic-discord-gateway"

    def handle_mention(
        self,
        prompt: str,
        *,
        node_id: str = FIXTURE_ISSUER_NODE_ID,
        final_text: str = "Synthetic Discord gateway response.",
    ) -> DiscordGatewayAdapterResult:
        task_summary = " ".join(str(prompt or "").split())[:160] or "synthetic discord mention"
        payload = build_synthetic_discord_gateway_payload(node_id=node_id, final_text=final_text)
        decision = validate_discord_gateway_payload(payload)
        events = payload.get("events") if isinstance(payload.get("events"), list) else []
        terminal_events = [event for event in events if isinstance(event, dict) and event.get("event") in {"final", "controlled_error"}]
        progress_events = [event for event in events if isinstance(event, dict) and event.get("event") == "progress_edit_sent"]
        responder_policy = payload.get("responder_policy") if isinstance(payload.get("responder_policy"), dict) else {}
        return DiscordGatewayAdapterResult(
            schema_version=DISCORD_GATEWAY_ADAPTER_SCHEMA_VERSION,
            adapter=self.adapter_id,
            ok=decision.ok,
            synthetic=True,
            live_discord=False,
            token_required=False,
            duplicate_responder_prevented=responder_policy.get("public_python_bot_responder") is False,
            final_once=len(terminal_events) == 1,
            progress_events=len(progress_events),
            run_request={
                "task_summary": task_summary,
                "requested_surface": "discord_gateway_synthetic",
                "execution_mode": "mock_or_preview_only",
                "live_provider_allowed": False,
                "raw_prompt_persisted": False,
            },
            payload=payload,
            errors=decision.errors,
        )
