from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from .signals import UnsafeSignalError


SELF_EVOLUTION_QUEUE_SCHEMA_VERSION = "yonerai-self-evolution-queue/v0.1"

ApprovalState = Literal["proposed", "approved", "rejected", "needs_owner"]

ALLOWED_SURFACES = {
    "cli",
    "tui",
    "installer",
    "auth",
    "privacy",
    "provider",
    "hybrid",
    "site",
    "docs",
}
ALLOWED_MODES = {"local_cli", "official_bridge", "hybrid_stub", "public_site", "dry_run"}
ALLOWED_OUTCOMES = {"completed", "blocked", "confused", "dropoff", "failed", "requested"}
ALLOWED_DROPOFF_STAGES = {
    "none",
    "install",
    "start",
    "settings",
    "provider_setup",
    "auth",
    "privacy",
    "update",
    "task_execution",
    "docs",
}
ALLOWED_COMPLAINT_CLASSES = {
    "none",
    "confusing_copy",
    "missing_guidance",
    "setup_failed",
    "provider_unavailable",
    "safety_blocked",
    "update_unknown",
    "trust_warning",
}
ALLOWED_PROVIDER_CLASSES = {"none", "mock", "local_llm", "openai_compatible", "anthropic", "gemini", "unknown"}
ALLOWED_LATENCY_BUCKETS = {"none", "lt_1s", "1_5s", "5_30s", "gt_30s", "unknown"}

SAFE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")
LOCAL_PATH_RE = re.compile(r"([A-Za-z]:[\\/]|\\\\|/Users/|/home/|/root/|/etc/|/var/|/tmp/)", re.IGNORECASE)
URL_RE = re.compile(r"https?://", re.IGNORECASE)
SECRET_RE = re.compile(
    r"(sk-[A-Za-z0-9_-]{10,}|ghp_[A-Za-z0-9_]{10,}|AIza[0-9A-Za-z_-]{10,}|"
    r"(?i:api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|password|private[_-]?key))"
)

FORBIDDEN_QUEUE_FIELDS = {
    "raw_prompt",
    "raw_completion",
    "raw_conversation",
    "chain_of_thought",
    "file_content",
    "user_id",
    "account_id",
    "email",
    "ip",
    "token",
    "secret",
    "api_key",
    "private_key",
    "local_path",
    "create_branch",
    "open_pr",
    "merge",
    "deploy",
    "commit",
    "push",
    "release",
}
FORBIDDEN_QUEUE_FIELD_COMPACTS = {field.replace("_", "") for field in FORBIDDEN_QUEUE_FIELDS}
FORBIDDEN_QUEUE_FIELD_TOKENS = {
    "account",
    "completion",
    "deploy",
    "email",
    "file",
    "merge",
    "password",
    "prompt",
    "push",
    "release",
    "secret",
    "token",
}

QUEUE_NON_ACTIONS = (
    "no real telemetry collection",
    "no raw prompt ingestion",
    "no completion ingestion",
    "no PII or stable user tracking",
    "no automatic issue creation",
    "no branch or PR creation",
    "no code mutation",
    "no merge",
    "no deploy",
    "no release",
)


@dataclass(frozen=True)
class QueueSignal:
    feature_id: str
    surface: str
    mode: str
    outcome: str
    dropoff_stage: str
    complaint_class: str
    provider_class: str
    latency_bucket: str

    def to_public_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ProposalCandidate:
    user_impact: int
    frequency_hint: int
    privacy_risk: int
    implementation_cost: int
    provider_independence_impact: int
    same_experience_impact: int
    test_plan: str
    rollback_plan: str
    release_note_draft: str
    social_post_draft: str

    def to_public_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ProposalQueueItem:
    proposal_id: str
    approval_state: ApprovalState
    signal: QueueSignal
    candidate: ProposalCandidate
    proposal_only: bool = True
    github_write_allowed: bool = False
    deploy_allowed: bool = False
    auto_apply_allowed: bool = False

    def to_public_dict(self) -> dict[str, object]:
        return {
            "proposal_id": self.proposal_id,
            "approval_state": self.approval_state,
            "proposal_only": self.proposal_only,
            "github_write_allowed": self.github_write_allowed,
            "deploy_allowed": self.deploy_allowed,
            "auto_apply_allowed": self.auto_apply_allowed,
            "signal": self.signal.to_public_dict(),
            "candidate": self.candidate.to_public_dict(),
            "actions_not_performed": list(QUEUE_NON_ACTIONS),
        }


DEFAULT_QUEUE_SIGNALS: tuple[QueueSignal, ...] = (
    QueueSignal(
        feature_id="install.first_run",
        surface="installer",
        mode="official_bridge",
        outcome="confused",
        dropoff_stage="install",
        complaint_class="missing_guidance",
        provider_class="none",
        latency_bucket="none",
    ),
    QueueSignal(
        feature_id="provider.local_llm_setup",
        surface="provider",
        mode="local_cli",
        outcome="blocked",
        dropoff_stage="provider_setup",
        complaint_class="provider_unavailable",
        provider_class="local_llm",
        latency_bucket="unknown",
    ),
)


def normalize_queue_signal(payload: dict[str, Any] | QueueSignal) -> QueueSignal:
    if isinstance(payload, QueueSignal):
        signal = payload
    else:
        if not isinstance(payload, dict):
            raise UnsafeSignalError("queue signal payload must be an object")
        _walk_queue_safe(payload)
        required = {
            "feature_id",
            "surface",
            "mode",
            "outcome",
            "dropoff_stage",
            "complaint_class",
            "provider_class",
            "latency_bucket",
        }
        missing = required.difference(payload)
        if missing:
            raise UnsafeSignalError(f"missing required queue signal fields: {', '.join(sorted(missing))}")
        signal = QueueSignal(
            feature_id=_bounded_value(payload["feature_id"], field="feature_id"),
            surface=_bounded_value(payload["surface"], field="surface"),
            mode=_bounded_value(payload["mode"], field="mode"),
            outcome=_bounded_value(payload["outcome"], field="outcome"),
            dropoff_stage=_bounded_value(payload["dropoff_stage"], field="dropoff_stage"),
            complaint_class=_bounded_value(payload["complaint_class"], field="complaint_class"),
            provider_class=_bounded_value(payload["provider_class"], field="provider_class"),
            latency_bucket=_bounded_value(payload["latency_bucket"], field="latency_bucket"),
        )
    _validate_queue_signal(signal)
    return signal


def load_queue_signal_fixture(path: str | Path) -> list[QueueSignal]:
    fixture_path = Path(path)
    if not fixture_path.is_file():
        raise UnsafeSignalError("queue fixture path must be a local file")
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    signals = payload.get("signals") if isinstance(payload, dict) else payload
    if not isinstance(signals, list):
        raise UnsafeSignalError("queue fixture must contain a list of signals")
    return [normalize_queue_signal(item) for item in signals]


def build_queue_status_report() -> dict[str, object]:
    return {
        "schema_version": SELF_EVOLUTION_QUEUE_SCHEMA_VERSION,
        "ok": True,
        "status": "proposal_queue_ready",
        "proposal_only": True,
        "input_policy": {
            "allowed_sources": ["built_in_synthetic_fixture", "local_public_safe_fixture"],
            "required_signal_fields": [
                "feature_id",
                "surface",
                "mode",
                "outcome",
                "dropoff_stage",
                "complaint_class",
                "provider_class",
                "latency_bucket",
            ],
            "raw_prompt_allowed": False,
            "pii_allowed": False,
            "stable_user_tracking_allowed": False,
        },
        "approval_states": ["proposed", "approved", "rejected", "needs_owner"],
        "default_signal_count": len(DEFAULT_QUEUE_SIGNALS),
        "actions_not_performed": list(QUEUE_NON_ACTIONS),
    }


def build_queue_simulation_report(signals: list[dict[str, Any] | QueueSignal] | None = None) -> dict[str, object]:
    normalized = [normalize_queue_signal(item) for item in (signals or list(DEFAULT_QUEUE_SIGNALS))]
    proposals = [build_queue_item(signal).to_public_dict() for signal in normalized]
    return {
        "schema_version": SELF_EVOLUTION_QUEUE_SCHEMA_VERSION,
        "ok": True,
        "dry_run": True,
        "source": "synthetic_low_resolution_fixture",
        "signal_count": len(normalized),
        "proposal_count": len(proposals),
        "proposals": proposals,
        "actions_not_performed": list(QUEUE_NON_ACTIONS),
    }


def build_queue_list_report(signals: list[dict[str, Any] | QueueSignal] | None = None) -> dict[str, object]:
    report = build_queue_simulation_report(signals)
    proposals = report["proposals"]
    assert isinstance(proposals, list)
    return {
        "schema_version": SELF_EVOLUTION_QUEUE_SCHEMA_VERSION,
        "ok": True,
        "proposal_only": True,
        "proposals": [
            {
                "proposal_id": item["proposal_id"],
                "approval_state": item["approval_state"],
                "feature_id": item["signal"]["feature_id"],
                "surface": item["signal"]["surface"],
                "outcome": item["signal"]["outcome"],
            }
            for item in proposals
            if isinstance(item, dict) and isinstance(item.get("signal"), dict)
        ],
        "actions_not_performed": list(QUEUE_NON_ACTIONS),
    }


def build_queue_show_report(proposal_id: str, signals: list[dict[str, Any] | QueueSignal] | None = None) -> dict[str, object]:
    if not SAFE_ID_RE.fullmatch(proposal_id):
        raise UnsafeSignalError("proposal_id must be a safe local identifier")
    report = build_queue_simulation_report(signals)
    proposals = report["proposals"]
    assert isinstance(proposals, list)
    for item in proposals:
        if isinstance(item, dict) and item.get("proposal_id") == proposal_id:
            return {
                "schema_version": SELF_EVOLUTION_QUEUE_SCHEMA_VERSION,
                "ok": True,
                "proposal": item,
            }
    return {
        "schema_version": SELF_EVOLUTION_QUEUE_SCHEMA_VERSION,
        "ok": False,
        "error": "proposal_not_found",
        "proposal_id": proposal_id,
        "actions_not_performed": list(QUEUE_NON_ACTIONS),
    }


def build_queue_item(signal: QueueSignal) -> ProposalQueueItem:
    user_impact = _impact(signal)
    privacy_risk = 1 if signal.mode in {"local_cli", "dry_run", "public_site", "official_bridge"} else 2
    candidate = ProposalCandidate(
        user_impact=user_impact,
        frequency_hint=_frequency_hint(signal),
        privacy_risk=privacy_risk,
        implementation_cost=_implementation_cost(signal),
        provider_independence_impact=3 if signal.provider_class in {"local_llm", "openai_compatible"} else 2,
        same_experience_impact=4 if signal.surface in {"installer", "provider", "tui"} else 2,
        test_plan=f"Add a public-safe regression fixture for {signal.surface}/{signal.dropoff_stage}.",
        rollback_plan="Reject or archive this proposal without code, branch, PR, deploy, release, or config mutation.",
        release_note_draft=(
            f"Proposal-only bridge candidate: improve {signal.surface} guidance for {signal.feature_id}."
        ),
        social_post_draft=(
            f"YonerAI is testing a proposal-only improvement path for {signal.surface}; "
            "no real telemetry or automatic mutation is enabled."
        ),
    )
    return ProposalQueueItem(
        proposal_id=f"proposal-{signal.feature_id}",
        approval_state="needs_owner" if user_impact >= 4 or privacy_risk >= 2 else "proposed",
        signal=signal,
        candidate=candidate,
    )


def _validate_queue_signal(signal: QueueSignal) -> None:
    if not SAFE_ID_RE.fullmatch(signal.feature_id):
        raise UnsafeSignalError("feature_id must be a safe local identifier")
    _require_member(signal.surface, ALLOWED_SURFACES, field="surface")
    _require_member(signal.mode, ALLOWED_MODES, field="mode")
    _require_member(signal.outcome, ALLOWED_OUTCOMES, field="outcome")
    _require_member(signal.dropoff_stage, ALLOWED_DROPOFF_STAGES, field="dropoff_stage")
    _require_member(signal.complaint_class, ALLOWED_COMPLAINT_CLASSES, field="complaint_class")
    _require_member(signal.provider_class, ALLOWED_PROVIDER_CLASSES, field="provider_class")
    _require_member(signal.latency_bucket, ALLOWED_LATENCY_BUCKETS, field="latency_bucket")


def _require_member(value: str, allowed: set[str], *, field: str) -> None:
    if value not in allowed:
        raise UnsafeSignalError(f"{field} is not allowed")


def _bounded_value(value: object, *, field: str) -> str:
    text = str(value).strip()
    if len(text) > 80:
        raise UnsafeSignalError(f"{field} is too long")
    return text


def _walk_queue_safe(value: Any) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            _check_queue_key(str(key))
            _walk_queue_safe(nested)
        return
    if isinstance(value, list):
        for nested in value:
            _walk_queue_safe(nested)
        return
    if isinstance(value, str):
        _check_queue_string(value)


def _check_queue_key(key: str) -> None:
    normalized = re.sub(r"[^a-z0-9]+", "_", key.strip().lower()).strip("_")
    compact = normalized.replace("_", "")
    tokens = set(normalized.split("_"))
    if (
        normalized in FORBIDDEN_QUEUE_FIELDS
        or compact in FORBIDDEN_QUEUE_FIELD_COMPACTS
        or tokens.intersection(FORBIDDEN_QUEUE_FIELD_TOKENS)
    ):
        raise UnsafeSignalError(f"forbidden queue field: {key}")


def _check_queue_string(value: str) -> None:
    if LOCAL_PATH_RE.search(value):
        raise UnsafeSignalError("local or user-machine path is not allowed")
    if URL_RE.search(value):
        raise UnsafeSignalError("live URL input is not allowed in proposal queue fixtures")
    if SECRET_RE.search(value):
        raise UnsafeSignalError("secret-shaped value is not allowed")


def _impact(signal: QueueSignal) -> int:
    if signal.outcome in {"blocked", "failed", "dropoff"}:
        return 4
    if signal.outcome == "confused":
        return 3
    return 2


def _frequency_hint(signal: QueueSignal) -> int:
    if signal.dropoff_stage in {"install", "start", "provider_setup", "update"}:
        return 4
    if signal.complaint_class != "none":
        return 3
    return 2


def _implementation_cost(signal: QueueSignal) -> int:
    if signal.surface in {"installer", "auth", "provider"}:
        return 3
    return 2
