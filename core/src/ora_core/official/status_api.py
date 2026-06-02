from __future__ import annotations

import json
from pathlib import Path
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


STATUS_API_SCHEMA_VERSION = "yonerai-status-api/v0.1"
STATUS_FEED_SCHEMA_VERSION = "yonerai.status.feed.v1"
STATUS_CONTRACT_SCHEMA_VERSION = "yonerai-status-api-contract/v0.1"

StatusState = Literal[
    "operational",
    "degraded",
    "partial_outage",
    "major_outage",
    "maintenance",
    "contract_only",
    "not_production",
]

ALLOWED_STATUS_STATES: tuple[StatusState, ...] = (
    "operational",
    "degraded",
    "partial_outage",
    "major_outage",
    "maintenance",
    "contract_only",
    "not_production",
)
STATUS_FEED_DISPLAY_STATES = (
    "operational",
    "alpha_only",
    "not_started",
    "maintenance",
    "degraded",
    "partial_outage",
    "major_outage",
)
STATUS_COMPONENT_IDS = (
    "cli_release",
    "install",
    "update",
    "official_api",
    "oracle",
    "google_auth",
    "shared_traffic",
    "memory_sync",
    "self_evolution",
    "discord",
    "provider_runtime",
    "hybrid_node",
)
ALLOWED_STATUS_HOSTS = frozenset({"status.yonerai.com", "api.yonerai.com", "yonerai.com"})
DEFAULT_GENERATED_AT = "2026-06-02T00:00:00Z"
FORBIDDEN_STATUS_SOURCE_MARKERS = (
    "AKIA",
    "-----BEGIN",
    "PRIVATE KEY",
    "aws_secret",
    "secret_access_key",
    "arn:aws:",
    "C:\\Users",
    "C:\\\\Users",
    "C:/Users",
    "/Users/",
    "/home/",
    "sk-",
    "discord.com/api/webhooks",
)
PUBLIC_INCIDENT_FIELDS = frozenset(
    {
        "id",
        "date",
        "category_id",
        "component_id",
        "state",
        "impact",
        "kind",
        "title",
        "status_label",
        "impact_label",
        "kind_label",
        "summary",
        "description",
        "affected",
        "updates",
    }
)


def build_status_api_contract_fixture() -> dict[str, object]:
    return {
        "schema_version": STATUS_CONTRACT_SCHEMA_VERSION,
        "ok": True,
        "public_repo_mode": "fixture_only",
        "production_backend_included": False,
        "status_feed_schema_version": STATUS_FEED_SCHEMA_VERSION,
        "base_path": "/v1",
        "status_enum": list(ALLOWED_STATUS_STATES),
        "component_ids": list(STATUS_COMPONENT_IDS),
        "endpoints": [
            _status_endpoint("GET", "/v1/status", "read overall YonerAI public status", "status.response.schema.json"),
            _status_endpoint("GET", "/v1/status/components", "list status components", "components.response.schema.json"),
            _status_endpoint("GET", "/v1/status/incidents", "list public incidents", "incidents.response.schema.json"),
            _status_endpoint("GET", "/v1/releases", "read latest stable and alpha release state", "releases.response.schema.json"),
            _status_endpoint("GET", "/v1/install", "read install command and trust boundary", "install.response.schema.json"),
            _status_endpoint("GET", "/v1/rate-limit", "read status API rate-limit headers", "rate-limit.response.schema.json"),
        ],
        "privacy_rules": [
            "status fixtures must not include private runtime inventory",
            "status fixtures must not include AWS account IDs, ARNs, private IPs, tokens, or raw endpoints",
            "status.yonerai.com may consume status-feed JSON, but production monitoring remains a private/AWS lane",
            "public repo status URL fetch is opt-in and allowlisted only",
        ],
        "actions_not_performed": _status_non_actions(),
    }


def build_status_check_report(
    *,
    source: str | None = None,
    allow_network: bool = False,
    profile: str = "operational",
) -> dict[str, object]:
    feed = _load_status_feed_source(source, allow_network=allow_network) if source else build_status_feed_fixture(profile=profile)
    components = _components_from_feed(feed, profile=profile)
    incidents = _public_incidents(feed.get("incidents"))
    releases = build_status_releases_report()
    install = build_status_install_report()
    overall_status = _aggregate_component_status(components)
    if profile == "oracle_not_production":
        overall_status = "not_production"
    if profile == "auth_dry_run_only":
        overall_status = "contract_only"
    return {
        "schema_version": STATUS_API_SCHEMA_VERSION,
        "ok": True,
        "generated_at": feed.get("generated_at") or DEFAULT_GENERATED_AT,
        "source": _source_report(source, allow_network=allow_network),
        "status": overall_status,
        "status_page_feed_schema_version": feed.get("schema_version"),
        "component_count": len(components),
        "components": components,
        "incidents": incidents,
        "releases": releases,
        "install": install,
        "rate_limit": build_status_rate_limit_report()["headers"],
        "status_yonerai_com_ready": True,
        "production_backend_included": False,
        "production_monitoring_connected": False,
        "private_runtime_details_included": False,
        "actions_not_performed": _status_non_actions(),
    }


def build_status_components_report(*, profile: str = "operational") -> dict[str, object]:
    feed = build_status_feed_fixture(profile=profile)
    components = _components_from_feed(feed, profile=profile)
    return {
        "schema_version": STATUS_API_SCHEMA_VERSION,
        "ok": True,
        "generated_at": DEFAULT_GENERATED_AT,
        "components": components,
        "component_ids": list(STATUS_COMPONENT_IDS),
        "production_backend_included": False,
        "private_runtime_details_included": False,
    }


def build_status_incidents_report(*, profile: str = "operational") -> dict[str, object]:
    feed = build_status_feed_fixture(profile=profile)
    incidents = _public_incidents(feed.get("incidents"))
    return {
        "schema_version": STATUS_API_SCHEMA_VERSION,
        "ok": True,
        "generated_at": DEFAULT_GENERATED_AT,
        "incidents": incidents,
        "production_backend_included": False,
        "private_runtime_details_included": False,
    }


def build_status_releases_report() -> dict[str, object]:
    return {
        "schema_version": STATUS_API_SCHEMA_VERSION,
        "ok": True,
        "latest_stable": "v0.6.4",
        "latest_alpha": "v0.15.0-alpha.1",
        "stable_channel_status": "operational",
        "alpha_channel_status": "operational",
        "release_channel": "stable",
        "update_available": False,
        "forced_update_enabled": False,
        "auto_update_apply_enabled": False,
        "docs_url": "https://yonerai.com/install",
    }


def build_status_install_report() -> dict[str, object]:
    return {
        "schema_version": STATUS_API_SCHEMA_VERSION,
        "ok": True,
        "status": "operational",
        "release_channel": "stable",
        "latest_stable": "v0.6.4",
        "quick_install_command": "irm https://install.yonerai.com | iex",
        "verified_install_command": "irm https://install.yonerai.com/verified | iex",
        "artifact_source": "GitHub Release assets",
        "yonerai_com_hosts_assets": False,
        "no_production_installer_claim": True,
        "no_path_mutation_by_default": True,
        "no_admin_required_by_default": True,
        "no_service_install": True,
        "no_registry_mutation": True,
    }


def build_status_rate_limit_report() -> dict[str, object]:
    return {
        "schema_version": STATUS_API_SCHEMA_VERSION,
        "ok": True,
        "policy_state": "contract_only",
        "headers": {
            "Retry-After": "required on 429 quota_exceeded responses",
            "X-YonerAI-RateLimit-Limit": "quota limit for the active bucket",
            "X-YonerAI-RateLimit-Remaining": "remaining quota for the active bucket",
            "X-YonerAI-RateLimit-Reset": "unix timestamp or RFC3339 reset time",
            "X-YonerAI-RateLimit-Bucket": "status, anonymous, authenticated, user_quota, device_quota, provider_quota, cloud_contract, oracle_queue, or abuse",
        },
        "quota_exceeded_response": {
            "status": 429,
            "code": "quota_exceeded",
            "retry_after_required": True,
            "local_fallback": "cached_status_or_local_fixture",
        },
        "enforced_in_public_repo": False,
    }


def build_status_feed_fixture(*, profile: str = "operational") -> dict[str, object]:
    categories = _base_feed_categories(profile=profile)
    incidents = _profile_incidents(profile)
    if profile == "degraded_api":
        _set_component_override(
            categories,
            "official-api",
            "official_api",
            {
                "date": "2026-06-02",
                "status": "degraded",
                "incident_id": "incident-20260602-api-degraded",
                "message": {"ja": "公式API契約の接続確認は degraded fixture です。", "en": "Official API contract connectivity is degraded in this fixture."},
                "source": "fixture",
            },
        )
    if profile == "maintenance":
        _set_component_override(
            categories,
            "release-distribution",
            "install",
            {
                "date": "2026-06-02",
                "status": "maintenance",
                "incident_id": "maintenance-20260602-install",
                "message": {"ja": "install 導線のメンテナンス fixture です。", "en": "Install path maintenance fixture."},
                "source": "fixture",
            },
        )
    return {
        "schema_version": STATUS_FEED_SCHEMA_VERSION,
        "generated_at": DEFAULT_GENERATED_AT,
        "meta": {
            "product": "YonerAI Status",
            "source": "yonerai.status.feed.public.v1",
            "live_monitoring": False,
            "refresh_ms": 0,
            "environment": "public",
            "note": {
                "ja": "公開リポジトリの fixture です。本番監視運用や private runtime は含みません。",
                "en": "Public repository fixture. Production monitoring and private runtime are not included.",
            },
        },
        "range": {"start": "2026-06-02", "days": 90},
        "states": _feed_states(),
        "categories": categories,
        "incidents": incidents,
    }


def _load_status_feed_source(source: str, *, allow_network: bool) -> dict[str, object]:
    parsed = urlparse(source)
    if parsed.scheme and not _looks_like_windows_path(source):
        if parsed.scheme != "https" or parsed.hostname not in ALLOWED_STATUS_HOSTS:
            raise ValueError("status source URL must use HTTPS and an allowlisted yonerai.com status/API host")
        if not allow_network:
            raise ValueError("status URL fetch requires --allow-network-status-fetch")
        request = Request(source, headers={"User-Agent": "YonerAI-CLI-status-contract/0.1"})
        try:
            with urlopen(request, timeout=5) as response:  # noqa: S310 - explicit allowlisted status fetch only
                body = response.read(1_000_000)
        except HTTPError as exc:
            raise ValueError(f"status source returned HTTP {exc.code}") from exc
        except URLError as exc:
            raise ValueError("status source could not be fetched") from exc
        try:
            loaded = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError(f"status source response is not valid JSON: {exc}") from exc
    else:
        path = Path(source).expanduser().resolve()
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ValueError(f"failed to read status source file: {exc}") from exc
        try:
            loaded = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError(f"status source file is not valid JSON: {exc}") from exc
    if not isinstance(loaded, dict):
        raise ValueError("status source must be a JSON object")
    if loaded.get("schema_version") != STATUS_FEED_SCHEMA_VERSION:
        raise ValueError(f"unsupported status feed schema_version: {loaded.get('schema_version')}")
    return loaded


def _components_from_feed(feed: dict[str, object], *, profile: str) -> list[dict[str, object]]:
    categories = feed.get("categories") if isinstance(feed.get("categories"), list) else []
    components: list[dict[str, object]] = []
    for category in categories:
        if not isinstance(category, dict):
            continue
        for component in category.get("components", []):
            if not isinstance(component, dict):
                continue
            component_id = str(component.get("id") or "")
            if component_id not in STATUS_COMPONENT_IDS:
                continue
            state = _api_state_from_feed_state(str(component.get("default_status") or category.get("default_status") or "not_started"))
            override_state = _latest_override_state(component)
            if override_state is not None:
                state = _api_state_from_feed_state(override_state)
            if profile == "oracle_not_production" and component_id == "oracle":
                state = "not_production"
            if profile == "auth_dry_run_only" and component_id == "google_auth":
                state = "contract_only"
            if profile == "install_operational" and component_id == "install":
                state = "operational"
            if profile == "alpha_available_stable_current" and component_id in {"cli_release", "update"}:
                state = "operational"
            public_component = {
                "component_id": component_id,
                "name": _public_component_name(component.get("name"), component_id),
                "status": state,
                "user_message_ja": _message_value(component.get("fact"), "ja"),
                "user_message_en": _message_value(component.get("fact"), "en"),
                "next_action": _next_action(component_id, state),
                "docs_url": _docs_url(component_id),
                "release_channel": _release_channel(component_id),
                "source": _public_source(component.get("source")),
                "private_runtime_details_included": False,
            }
            _assert_public_status_payload(public_component, context="component")
            components.append(public_component)
    return components


def _public_incidents(raw_incidents: object) -> list[dict[str, object]]:
    if not isinstance(raw_incidents, list):
        return []
    incidents: list[dict[str, object]] = []
    for raw_incident in raw_incidents:
        if not isinstance(raw_incident, dict):
            continue
        public_incident = {key: value for key, value in raw_incident.items() if key in PUBLIC_INCIDENT_FIELDS}
        _assert_public_status_payload(public_incident, context="incident")
        incidents.append(public_incident)
    return incidents


def _assert_public_status_payload(value: object, *, context: str) -> None:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
    if any(marker in serialized for marker in FORBIDDEN_STATUS_SOURCE_MARKERS):
        raise ValueError(f"status source {context} contains a non-public marker")


def _public_component_name(value: object, fallback: str) -> object:
    if isinstance(value, dict):
        return {key: str(value.get(key) or fallback) for key in ("ja", "en") if value.get(key)}
    if value:
        return str(value)
    return fallback


def _base_feed_categories(*, profile: str) -> list[dict[str, object]]:
    default = "not_started" if profile not in {"operational", "install_operational", "alpha_available_stable_current"} else "operational"
    return [
        {
            "id": "release-distribution",
            "name": {"ja": "リリースと配布", "en": "Release and distribution"},
            "default_status": default,
            "components": [
                _feed_component("cli_release", "CLI release", default, "CLI Local Runtime の公開リリース情報です。", "CLI Local Runtime public release state."),
                _feed_component("install", "Install", default, "GitHub Release assets を正本にした install 導線です。", "Install path uses GitHub Release assets as source of truth."),
                _feed_component("update", "Update", default, "自動適用なしの update check / plan 導線です。", "Update check and plan path without auto-apply."),
            ],
        },
        {
            "id": "official-api",
            "name": {"ja": "公式API契約", "en": "Official API contract"},
            "default_status": "alpha_only",
            "components": [
                _feed_component("official_api", "Official API", "alpha_only", "公式APIは public repo では契約/fixture のみです。", "Official API is contract/fixture only in the public repo."),
                _feed_component("oracle", "Oracle", "not_started", "production Oracle は public repo に含みません。", "Production Oracle is not included in the public repo."),
                _feed_component("google_auth", "Google auth", "alpha_only", "Google auth は dry-run 契約のみです。", "Google auth is dry-run contract only."),
                _feed_component("shared_traffic", "Shared traffic", "not_started", "OpenAI shared traffic は既定で無効です。", "OpenAI shared traffic is off by default."),
            ],
        },
        {
            "id": "runtime-boundaries",
            "name": {"ja": "ランタイム境界", "en": "Runtime boundaries"},
            "default_status": "alpha_only",
            "components": [
                _feed_component("memory_sync", "Memory sync", "alpha_only", "local -> cloud memory sync は既定で無効です。", "Local-to-cloud memory sync is disabled by default."),
                _feed_component("self_evolution", "Self-evolution", "alpha_only", "public repo の self-evolution は proposal-only です。", "Public repo self-evolution is proposal-only."),
                _feed_component("discord", "Discord", "not_started", "live Discord は復元されていません。", "Live Discord is not restored."),
                _feed_component("provider_runtime", "Provider runtime", default, "mock/local/provider runtime の公開安全境界です。", "Public-safe mock/local/provider runtime boundary."),
                _feed_component("hybrid_node", "Hybrid node", "alpha_only", "Hybrid Node は local-dev / fixture 境界です。", "Hybrid Node is a local-dev/fixture boundary."),
            ],
        },
    ]


def _feed_component(component_id: str, name: str, status: str, fact_ja: str, fact_en: str) -> dict[str, object]:
    return {
        "id": component_id,
        "name": name,
        "default_status": status,
        "fact": {"ja": fact_ja, "en": fact_en},
        "monitoring": {"ja": "fixture", "en": "fixture"},
        "claim": {"ja": "本番運用は未主張", "en": "No production operation claim"},
        "source": {"type": "fixture", "provider": "yonerai", "target": "public-status-contract"},
        "day_overrides": [],
    }


def _feed_states() -> dict[str, object]:
    return {
        "operational": {"severity": 0, "color": "#25c39a", "label": {"ja": "稼働中", "en": "Operational"}},
        "alpha_only": {"severity": 10, "color": "#a9b0ba", "label": {"ja": "alpha のみ", "en": "Alpha only"}},
        "not_started": {"severity": 20, "color": "#a9b0ba", "label": {"ja": "準備中", "en": "Preparing"}},
        "maintenance": {"severity": 30, "color": "#f97316", "label": {"ja": "メンテナンス", "en": "Maintenance"}},
        "degraded": {"severity": 40, "color": "#f6bd3f", "label": {"ja": "性能低下", "en": "Degraded"}},
        "partial_outage": {"severity": 50, "color": "#ff7a59", "label": {"ja": "一部障害", "en": "Partial outage"}},
        "major_outage": {"severity": 60, "color": "#ef5b4a", "label": {"ja": "重大障害", "en": "Major outage"}},
    }


def _profile_incidents(profile: str) -> list[dict[str, object]]:
    if profile == "degraded_api":
        return [
            {
                "id": "incident-20260602-api-degraded",
                "date": "2026-06-02",
                "category_id": "official-api",
                "component_id": "official_api",
                "state": "degraded",
                "impact": "degraded",
                "kind": "incident",
                "title": {"ja": "公式API degraded fixture", "en": "Official API degraded fixture"},
                "status_label": {"ja": "fixture", "en": "fixture"},
                "impact_label": {"ja": "性能低下", "en": "Degraded"},
                "kind_label": {"ja": "Incident", "en": "Incident"},
                "summary": {"ja": "公式API bridge の degraded fixture です。", "en": "Degraded fixture for the official API bridge."},
                "description": {"ja": "公開 contract 用のサンプルであり本番障害ではありません。", "en": "Public contract sample; not a production incident."},
                "affected": {
                    "start_label": "2026-06-02 08:05",
                    "end_label": "08:40",
                    "component_label": {"ja": "公式API", "en": "Official API"},
                    "count_label": {"ja": "1 affected component", "en": "1 affected component"},
                    "tooltip": {"ja": "公式API: 性能低下 08:05 -> 08:40", "en": "Official API: degraded 08:05 -> 08:40"},
                    "segments": [
                        {"status": "operational", "width": 10},
                        {"status": "degraded", "width": 80},
                        {"status": "operational", "width": 10},
                    ],
                },
                "updates": [
                    {
                        "status": "monitoring",
                        "title": {"ja": "監視中", "en": "Monitoring"},
                        "body": {"ja": "fixture の監視状態です。", "en": "Fixture monitoring state."},
                        "time_utc": "2026-06-02 11:26 UTC",
                        "time_local": "2026-06-02 20:26 JST",
                    }
                ],
            }
        ]
    if profile == "maintenance":
        return [
            {
                "id": "maintenance-20260602-install",
                "date": "2026-06-02",
                "category_id": "release-distribution",
                "component_id": "install",
                "state": "maintenance",
                "impact": "maintenance",
                "kind": "maintenance",
                "title": {"ja": "install 導線メンテナンス fixture", "en": "Install path maintenance fixture"},
                "status_label": {"ja": "予定", "en": "Scheduled"},
                "impact_label": {"ja": "メンテナンス", "en": "Maintenance"},
                "kind_label": {"ja": "Maintenance", "en": "Maintenance"},
                "summary": {"ja": "公開 install 導線のメンテナンス fixture です。", "en": "Public install path maintenance fixture."},
                "description": {"ja": "本番メンテナンスではありません。", "en": "Not production maintenance."},
                "affected": {
                    "start_label": "2026-06-02 08:05",
                    "end_label": "08:40",
                    "component_label": {"ja": "Install", "en": "Install"},
                    "count_label": {"ja": "1 affected component", "en": "1 affected component"},
                    "tooltip": {"ja": "Install: メンテナンス 08:05 -> 08:40", "en": "Install: maintenance 08:05 -> 08:40"},
                    "segments": [{"status": "maintenance", "width": 100}],
                },
                "updates": [],
            }
        ]
    return []


def _set_component_override(categories: list[dict[str, object]], category_id: str, component_id: str, override: dict[str, object]) -> None:
    for category in categories:
        if category.get("id") != category_id:
            continue
        for component in category.get("components", []):
            if isinstance(component, dict) and component.get("id") == component_id:
                component["day_overrides"] = [override]
                return


def _latest_override_state(component: dict[str, object]) -> str | None:
    overrides = component.get("day_overrides")
    if not isinstance(overrides, list) or not overrides:
        return None
    last = overrides[-1]
    if not isinstance(last, dict):
        return None
    status = last.get("status")
    return str(status) if status else None


def _api_state_from_feed_state(state: str) -> StatusState:
    mapping: dict[str, StatusState] = {
        "operational": "operational",
        "degraded": "degraded",
        "partial_outage": "partial_outage",
        "major_outage": "major_outage",
        "maintenance": "maintenance",
        "alpha_only": "contract_only",
        "not_started": "not_production",
        "contract_only": "contract_only",
        "not_production": "not_production",
    }
    return mapping.get(state, "contract_only")


def _aggregate_component_status(components: list[dict[str, object]]) -> StatusState:
    severity = {
        "operational": 0,
        "contract_only": 10,
        "not_production": 20,
        "maintenance": 30,
        "degraded": 40,
        "partial_outage": 50,
        "major_outage": 60,
    }
    worst = max((str(component.get("status") or "contract_only") for component in components), key=lambda value: severity.get(value, 10), default="contract_only")
    return _api_state_from_feed_state(worst)


def _message_value(value: object, lang: str) -> str:
    if isinstance(value, dict):
        raw = value.get(lang) or value.get("en") or value.get("ja")
        if raw:
            return str(raw)
    return "status fixture"


def _next_action(component_id: str, state: str) -> str:
    if component_id == "install":
        return "irm https://install.yonerai.com | iex"
    if component_id == "update":
        return "yonerai update check --pretty"
    if component_id == "official_api":
        return "yonerai api status --pretty --lang ja"
    if component_id == "google_auth":
        return "yonerai auth google login --dry-run --pretty --lang ja"
    if component_id == "memory_sync":
        return "yonerai memory sync preview --direction local-to-cloud --pretty"
    if state in {"degraded", "partial_outage", "major_outage", "maintenance"}:
        return "check status.yonerai.com"
    return "no action required"


def _docs_url(component_id: str) -> str:
    if component_id in {"install", "update", "cli_release"}:
        return "https://yonerai.com/install"
    return "https://yonerai.com/status"


def _release_channel(component_id: str) -> str:
    return "stable" if component_id in {"cli_release", "install", "update"} else "alpha"


def _public_source(source: object) -> dict[str, object]:
    allowed_types = {"fixture", "github_release", "status_feed", "aws_future", "manual_incident"}
    if not isinstance(source, dict):
        return {"type": "fixture", "provider": "yonerai", "public_safe": True}
    source_type = str(source.get("type") or "fixture")
    if source_type not in allowed_types:
        source_type = "status_feed"
    return {
        "type": source_type,
        "provider": "yonerai",
        "target": "public-status-contract",
        "public_safe": True,
    }


def _source_report(source: str | None, *, allow_network: bool) -> dict[str, object]:
    if not source:
        return {"kind": "fixture", "network_fetch_performed": False, "allow_network": allow_network}
    parsed = urlparse(source)
    if parsed.scheme and not _looks_like_windows_path(source):
        return {
            "kind": "url",
            "host": parsed.hostname,
            "network_fetch_performed": bool(allow_network),
            "allow_network": allow_network,
        }
    return {"kind": "local_file", "network_fetch_performed": False, "allow_network": allow_network}


def _looks_like_windows_path(value: str) -> bool:
    return len(value) >= 3 and value[1] == ":" and value[0].isalpha() and value[2] in {"\\", "/"}


def _status_endpoint(method: str, path: str, summary: str, response_schema_ref: str) -> dict[str, object]:
    return {
        "method": method,
        "path": path,
        "summary": summary,
        "auth": "anonymous_allowed",
        "response_schema": {"schema_ref": f"status-api-0.1/{response_schema_ref}"},
        "error_schema": _status_error_schema(),
        "rate_limit": {
            "bucket": "status",
            "headers": build_status_rate_limit_report()["headers"],
            "quota_exceeded_status": 429,
        },
        "privacy_boundary": {
            "private_runtime_details_allowed": False,
            "provider_keys_allowed": False,
            "local_absolute_paths_allowed": False,
            "aws_account_ids_allowed": False,
            "arn_allowed": False,
            "private_ip_allowed": False,
            "raw_endpoint_allowed": False,
        },
        "implemented_in_public_repo": False,
        "fixture_available": True,
    }


def _status_error_schema() -> dict[str, object]:
    return {
        "type": "object",
        "required": ["ok", "error"],
        "properties": {
            "ok": {"const": False},
            "error": {
                "type": "object",
                "required": ["code", "message", "retry_after"],
                "properties": {
                    "code": {"type": "string"},
                    "message": {"type": "string"},
                    "retry_after": {"type": ["integer", "null"]},
                    "request_id": {"type": ["string", "null"]},
                },
                "additionalProperties": False,
            },
        },
        "additionalProperties": False,
    }


def _status_non_actions() -> list[str]:
    return [
        "no production AWS request",
        "no production Oracle call",
        "no official cloud runtime execution",
        "no live Discord call",
        "no production Google login",
        "no private runtime inventory output",
        "no provider key output",
        "no OpenAI shared traffic",
        "no private/local content upload",
        "no forced update",
        "no auto install",
    ]
