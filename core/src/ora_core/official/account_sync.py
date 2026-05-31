from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ACCOUNT_SYNC_SCHEMA_VERSION = "yonerai-account-sync/v0.1"
SYNC_AUDIT_SCHEMA_VERSION = "yonerai-sync-audit/v0.1"
OFFICIAL_API_SCHEMA_VERSION = "yonerai-official-api-contract/v0.1"
RATE_LIMIT_SCHEMA_VERSION = "yonerai-rate-limit-policy/v0.1"

AuthState = Literal["unauthenticated", "dry_run", "pending", "linked", "expired", "revoked"]
SyncDirection = Literal["cloud_to_local", "local_to_cloud"]
SyncDecisionState = Literal["allowed", "blocked", "approval_required"]
VALID_AUTH_STATES = {"unauthenticated", "dry_run", "pending", "linked", "expired", "revoked"}
VALID_SYNC_DIRECTIONS = {"cloud_to_local", "local_to_cloud"}


@dataclass(frozen=True)
class AccountIdentity:
    subject_ref: str
    provider: str = "google"
    display_email_redacted: str = "not-linked"
    scopes: tuple[str, ...] = ("openid", "email", "profile")

    def to_public_dict(self) -> dict[str, object]:
        return {
            "subject_ref": self.subject_ref,
            "provider": self.provider,
            "display_email_redacted": self.display_email_redacted,
            "scopes": list(self.scopes),
            "raw_subject_included": False,
            "raw_email_included": False,
        }


@dataclass(frozen=True)
class GoogleAuthSessionContract:
    auth_state: AuthState = "dry_run"
    pkce_required: bool = True
    state_required: bool = True
    loopback_redirect_only: bool = True
    minimal_scopes: tuple[str, ...] = ("openid", "email", "profile")
    refresh_token_plaintext_allowed: bool = False
    production_login_enabled: bool = False

    def to_public_dict(self) -> dict[str, object]:
        return {
            "auth_state": self.auth_state,
            "pkce_required": self.pkce_required,
            "state_required": self.state_required,
            "loopback_redirect_only": self.loopback_redirect_only,
            "minimal_scopes": list(self.minimal_scopes),
            "refresh_token_plaintext_allowed": self.refresh_token_plaintext_allowed,
            "production_login_enabled": self.production_login_enabled,
            "public_repo_mode": "contract_only",
        }


@dataclass(frozen=True)
class LocalUserProfile:
    profile_ref: str = "local-profile-fixture"
    secrets_stored: bool = False
    provider_keys_stored: bool = False
    refresh_token_stored: bool = False

    def to_public_dict(self) -> dict[str, object]:
        return {
            "profile_ref": self.profile_ref,
            "secrets_stored": self.secrets_stored,
            "provider_keys_stored": self.provider_keys_stored,
            "refresh_token_stored": self.refresh_token_stored,
        }


@dataclass(frozen=True)
class CloudAccountLinkState:
    auth_state: AuthState = "dry_run"
    selected_cloud_conversation: bool = False
    official_cloud_runtime_enabled: bool = False
    production_oracle_enabled: bool = False

    def to_public_dict(self) -> dict[str, object]:
        return {
            "auth_state": self.auth_state,
            "selected_cloud_conversation": self.selected_cloud_conversation,
            "official_cloud_runtime_enabled": self.official_cloud_runtime_enabled,
            "production_oracle_enabled": self.production_oracle_enabled,
            "can_sync_cloud_to_local": self.auth_state == "linked" and self.selected_cloud_conversation,
            "can_sync_local_to_cloud_by_default": False,
        }


@dataclass(frozen=True)
class CloudConversationRef:
    ref_id: str = "cloud-conversation-fixture"
    source: str = "official_cloud_contract"
    selected_by_user: bool = False
    raw_body_included: bool = False

    def to_public_dict(self) -> dict[str, object]:
        return {
            "ref_id": self.ref_id,
            "source": self.source,
            "selected_by_user": self.selected_by_user,
            "raw_body_included": self.raw_body_included,
        }


@dataclass(frozen=True)
class LocalConversationRef:
    ref_id: str = "local-conversation-fixture"
    storage: str = "local_only"
    contains_private_file_content: bool = False
    contains_local_memory: bool = False
    contains_local_node_payload: bool = False
    raw_body_included: bool = False

    def to_public_dict(self) -> dict[str, object]:
        return {
            "ref_id": self.ref_id,
            "storage": self.storage,
            "contains_private_file_content": self.contains_private_file_content,
            "contains_local_memory": self.contains_local_memory,
            "contains_local_node_payload": self.contains_local_node_payload,
            "raw_body_included": self.raw_body_included,
        }


@dataclass(frozen=True)
class SyncDecision:
    state: SyncDecisionState
    direction: SyncDirection
    reason: str
    requires_explicit_approval: bool = False
    private_content_excluded: bool = True

    def to_public_dict(self) -> dict[str, object]:
        return {
            "state": self.state,
            "direction": self.direction,
            "reason": self.reason,
            "requires_explicit_approval": self.requires_explicit_approval,
            "private_content_excluded": self.private_content_excluded,
        }


@dataclass(frozen=True)
class SyncAudit:
    reason: str
    actor: str = "local_user"
    dry_run: bool = True
    raw_private_content_logged: bool = False
    provider_keys_logged: bool = False
    local_absolute_paths_logged: bool = False

    def to_public_dict(self) -> dict[str, object]:
        return {
            "schema_version": SYNC_AUDIT_SCHEMA_VERSION,
            "reason": self.reason,
            "actor": self.actor,
            "dry_run": self.dry_run,
            "raw_private_content_logged": self.raw_private_content_logged,
            "provider_keys_logged": self.provider_keys_logged,
            "local_absolute_paths_logged": self.local_absolute_paths_logged,
        }


@dataclass(frozen=True)
class SyncEnvelope:
    direction: SyncDirection
    decision: SyncDecision
    cloud_ref: CloudConversationRef
    local_ref: LocalConversationRef
    audit: SyncAudit
    shared_traffic_enabled: bool = False
    official_backend_called: bool = False
    sync_performed: bool = False

    def to_public_dict(self) -> dict[str, object]:
        return {
            "schema_version": ACCOUNT_SYNC_SCHEMA_VERSION,
            "direction": self.direction,
            "decision": self.decision.to_public_dict(),
            "cloud_conversation": self.cloud_ref.to_public_dict(),
            "local_conversation": self.local_ref.to_public_dict(),
            "audit": self.audit.to_public_dict(),
            "shared_traffic_enabled": self.shared_traffic_enabled,
            "official_backend_called": self.official_backend_called,
            "sync_performed": self.sync_performed,
            "actions_not_performed": _sync_non_actions(),
        }


def build_account_status_report(auth_state: AuthState = "dry_run", *, selected: bool = False) -> dict[str, object]:
    _validate_auth_state(auth_state)
    session = GoogleAuthSessionContract(auth_state=auth_state)
    link = CloudAccountLinkState(auth_state=auth_state, selected_cloud_conversation=selected)
    identity = AccountIdentity(subject_ref="redacted-subject-fixture")
    return {
        "schema_version": ACCOUNT_SYNC_SCHEMA_VERSION,
        "ok": True,
        "identity": identity.to_public_dict(),
        "auth_session": session.to_public_dict(),
        "local_profile": LocalUserProfile().to_public_dict(),
        "cloud_link": link.to_public_dict(),
        "actions_not_performed": [
            "no production Google login",
            "no live OAuth token exchange",
            "no refresh token plaintext storage",
            "no provider key storage",
            "no official cloud session created",
        ],
    }


def build_sync_status_report(auth_state: AuthState = "dry_run", *, selected: bool = False) -> dict[str, object]:
    _validate_auth_state(auth_state)
    link = CloudAccountLinkState(auth_state=auth_state, selected_cloud_conversation=selected)
    cloud_to_local_ready = link.auth_state == "linked" and link.selected_cloud_conversation
    return {
        "schema_version": ACCOUNT_SYNC_SCHEMA_VERSION,
        "ok": True,
        "auth_state": auth_state,
        "cloud_link": link.to_public_dict(),
        "directions": {
            "cloud_to_local": {
                "supported_by_contract": True,
                "enabled_now": cloud_to_local_ready,
                "requires": ["linked account", "user-selected cloud conversation"],
                "raw_private_content_uploaded": False,
            },
            "local_to_cloud": {
                "supported_by_contract": True,
                "enabled_by_default": False,
                "requires_explicit_approval": True,
                "private_file_content_excluded": True,
                "local_memory_excluded": True,
                "local_node_payload_excluded": True,
            },
        },
        "shared_traffic_enabled": False,
        "official_cloud_runtime_enabled": False,
        "production_oracle_enabled": False,
        "next_safe_commands": [
            "yonerai sync preview --direction cloud-to-local --json",
            "yonerai sync approve --dry-run --direction local-to-cloud --json",
        ],
        "actions_not_performed": _sync_non_actions(),
    }


def build_sync_preview_report(
    *,
    direction: SyncDirection = "cloud_to_local",
    auth_state: AuthState = "dry_run",
    selected: bool = False,
    explicit_approval: bool = False,
    contains_private_file_content: bool = False,
    contains_local_memory: bool = False,
    contains_local_node_payload: bool = False,
) -> dict[str, object]:
    _validate_direction(direction)
    _validate_auth_state(auth_state)
    decision = _sync_decision(
        direction=direction,
        auth_state=auth_state,
        selected=selected,
        explicit_approval=explicit_approval,
    )
    envelope = SyncEnvelope(
        direction=direction,
        decision=decision,
        cloud_ref=CloudConversationRef(selected_by_user=selected),
        local_ref=LocalConversationRef(
            contains_private_file_content=contains_private_file_content,
            contains_local_memory=contains_local_memory,
            contains_local_node_payload=contains_local_node_payload,
        ),
        audit=SyncAudit(reason=decision.reason),
    )
    report = envelope.to_public_dict()
    report.update(
        {
            "ok": decision.state != "blocked",
            "preview_only": True,
            "approval_recorded": False,
            "private_content_exclusion": {
                "private_file_content_excluded": True,
                "local_memory_excluded": True,
                "local_node_payload_excluded": True,
                "raw_prompt_excluded": True,
            },
        }
    )
    return report


def build_sync_approval_dry_run_report(
    *,
    direction: SyncDirection = "local_to_cloud",
    auth_state: AuthState = "dry_run",
    selected: bool = False,
    explicit_approval: bool = False,
) -> dict[str, object]:
    _validate_direction(direction)
    _validate_auth_state(auth_state)
    preview = build_sync_preview_report(
        direction=direction,
        auth_state=auth_state,
        selected=selected,
        explicit_approval=explicit_approval,
    )
    preview.update(
        {
            "operation": "sync_approve_dry_run",
            "dry_run": True,
            "approval_recorded": False,
            "sync_performed": False,
            "official_backend_called": False,
        }
    )
    return preview


def build_rate_limit_policy_report() -> dict[str, object]:
    return {
        "schema_version": RATE_LIMIT_SCHEMA_VERSION,
        "ok": True,
        "policy_state": "contract_only",
        "quotas": {
            "user_quota": {"scope": "official_account", "enforced_in_public_repo": False},
            "device_quota": {"scope": "local_device_ref", "enforced_in_public_repo": False},
            "provider_quota": {"scope": "provider_or_shared_pool", "enforced_in_public_repo": False},
        },
        "shared_traffic": {
            "openai_shared_traffic_enabled": False,
            "free_usage_claimed": False,
            "owner_or_org_eligibility_assumed": False,
            "private_content_excluded": True,
        },
        "fallback": {
            "cloud_quota_exceeded": "local_mock_or_loopback_provider",
            "private_task": "local_only_or_deny",
        },
        "abuse_prevention": [
            "rate-limit decisions must be made by the official backend",
            "public CLI stores no production quota tokens",
            "quota errors must not expose provider keys or account internals",
        ],
    }


def build_official_api_contract_fixture() -> dict[str, object]:
    return {
        "schema_version": OFFICIAL_API_SCHEMA_VERSION,
        "ok": True,
        "public_repo_mode": "fixture_only",
        "production_backend_included": False,
        "base_path": "/v1",
        "auth": {
            "google_pkce_loopback_required": True,
            "minimal_scopes": ["openid", "email", "profile"],
            "refresh_token_plaintext_allowed": False,
            "production_login_enabled_in_public_repo": False,
        },
        "endpoints": [
            _endpoint("GET", "/v1/account/me", "return the linked account summary"),
            _endpoint("GET", "/v1/conversations", "list user-selected cloud conversation refs"),
            _endpoint("POST", "/v1/sync/preview", "preview sync decision and audit reason"),
            _endpoint("POST", "/v1/sync/approve", "record explicit sync approval in official backend"),
            _endpoint("POST", "/v1/oracle/runs", "enqueue official Oracle run request"),
            _endpoint("GET", "/v1/oracle/runs/{id}", "read official Oracle run result envelope"),
            _endpoint("GET", "/v1/rate-limit", "read quota and local fallback state"),
            _endpoint("GET", "/v1/status", "read official service status"),
        ],
        "privacy_rules": [
            "cloud-to-local sync requires linked account and user-selected cloud conversation",
            "local-to-cloud sync is disabled by default",
            "local-to-cloud sync requires explicit approval and audit reason",
            "private file, local memory, local node payload, secrets, and provider keys are excluded by default",
            "public fixtures must not contain raw user conversation bodies",
        ],
        "self_evolution_boundary": {
            "public_repo": "proposal_only_synthetic_signals",
            "official_backend": "private_future_lane",
            "raw_prompts_allowed_in_public_repo": False,
            "pii_allowed_in_public_repo": False,
            "auto_pr_merge_deploy_allowed": False,
        },
    }


def _sync_decision(
    *,
    direction: SyncDirection,
    auth_state: AuthState,
    selected: bool,
    explicit_approval: bool,
) -> SyncDecision:
    _validate_direction(direction)
    _validate_auth_state(auth_state)
    if auth_state != "linked":
        return SyncDecision(
            state="blocked",
            direction=direction,
            reason="account_not_linked",
            requires_explicit_approval=direction == "local_to_cloud",
        )
    if direction == "cloud_to_local":
        if not selected:
            return SyncDecision(
                state="blocked",
                direction=direction,
                reason="cloud_conversation_not_selected",
            )
        return SyncDecision(state="allowed", direction=direction, reason="linked_selected_cloud_conversation")
    if not explicit_approval:
        return SyncDecision(
            state="approval_required",
            direction=direction,
            reason="local_to_cloud_requires_explicit_approval",
            requires_explicit_approval=True,
        )
    return SyncDecision(
        state="allowed",
        direction=direction,
        reason="explicit_local_to_cloud_approval_dry_run",
        requires_explicit_approval=True,
    )


def _endpoint(method: str, path: str, summary: str) -> dict[str, object]:
    return {
        "method": method,
        "path": path,
        "summary": summary,
        "implemented_in_public_repo": False,
        "fixture_available": True,
    }


def _validate_direction(direction: str) -> None:
    if direction not in VALID_SYNC_DIRECTIONS:
        raise ValueError(f"unsupported sync direction: {direction}")


def _validate_auth_state(auth_state: str) -> None:
    if auth_state not in VALID_AUTH_STATES:
        raise ValueError(f"unsupported auth state: {auth_state}")


def _sync_non_actions() -> list[str]:
    return [
        "no network request",
        "no production Oracle call",
        "no official cloud runtime execution",
        "no automatic local-to-cloud upload",
        "no private file content upload",
        "no local memory upload",
        "no local node payload upload",
        "no provider key upload",
        "no OpenAI shared traffic",
    ]
