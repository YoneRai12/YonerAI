# YonerAI Current Truth

This file is the public anchor that AI lanes should read before making
release, CLI, API, or status claims. It intentionally avoids private
runtime inventory, internal URLs, secrets, local paths, and control-plane
details.

- generated_date_utc: 2026-06-18
- latest_stable_tag: v0.8.1
- latest_prerelease_tag: v0.22.0-alpha.1
- main_head_short: aabf709e
- staging_api_base_host: api-staging.yonerai.com
- status_snapshot_schema: yonerai.status.v1
- official_api_contract_policy: yonerai-official-api-contract/v0.14

## Open Production Blockers

- Production Google login is not enabled in the public CLI.
- Official Managed Cloud remains external/private and contract-only from
  the public repository.
- Production Oracle/cloud runtime is not included in the public repository.
- Production signing/trust-store validation is not complete.
- Live Discord/token operation is not included.
- Local private memory/file content must not auto-upload.
- OpenAI shared traffic remains disabled by default.
- `agent:run` and `admin:*` scopes are frozen until a separate threat-model
  gate approves them.

## Required First Read

AI lanes must read this file together with `AGENTS.md` and
`docs/process/YONERAI_CODEX_WORKFLOW.md` before making public claims.
