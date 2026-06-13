# YonerAI Release Notes

This page is a public-safe index of current release notes and progress checkpoints.

## v0.8.1 Talkable CLI UX Repair

- GitHub release target: `v0.8.1`.
- Release title: `2026.06.13 - YonerAI CLI Local Runtime v0.8.1 UX Repair`.
- Release date: `2026-06-13`.
- Public release body: `docs/releases/0.8.1.md`.
- Status: stable CLI Local Runtime patch after `v0.8.0`.
- What users can try now:
  `irm https://install.yonerai.com | iex`, `yonerai`, normal text in the app,
  `/ログイン`, `/更新`, `/ローカルLLM`, `/設定`, `/認証`, `/同期`, `/記憶`, `/履歴`,
  `/API`, `/レート`, `/終了`, plus scriptable fallback commands `yonerai update`,
  `yonerai update stable`, `yonerai update beta`, `yonerai login`,
  `yonerai whoami`, `yonerai sessions`, `yonerai projects`, `yonerai ping`, and
  `yonerai rate-limit`.
- Boundary: stable for the local CLI runtime slice only; no production Google
  login, no Google token/refresh storage, no provider keys, no OpenAI shared
  traffic, no production Oracle/cloud runtime, no live Discord, no arbitrary
  shell/file/tool execution, no automatic local-to-cloud upload, and no
  production signing/trust store.
- Primary traceability range: `v0.8.0..v0.8.1`; every user-visible change is
  listed in `docs/releases/0.8.1.md`.

## v0.8.0 Normal Talkable CLI

- GitHub release target: `v0.8.0`.
- Release title: `2026.06.12 - YonerAI CLI Local Runtime v0.8.0`.
- Release date: `2026-06-12`.
- Public release body: `docs/releases/0.8.0.md`.
- Status: stable CLI Local Runtime after `v0.7.0`; latest prerelease carry-in
  before promotion was `v0.21.0-alpha.2`.
- What users can try now:
  `irm https://install.yonerai.com | iex`, `yonerai`, `yonerai chat`,
  `yonerai update`, `yonerai update stable`, `yonerai update beta`,
  `yonerai login`, `yonerai whoami`, `yonerai sessions`, `yonerai projects`,
  `yonerai ping`, `yonerai rate-limit`, and TUI `/設定`, `/更新`, `/ログイン`,
  `/認証`, `/セッション`, `/プロジェクト`, `/API`, `/レート`, `/同期`, `/記憶`,
  `/ヘルプ`, `/終了`.
- Boundary: stable for the local CLI runtime slice only; no production Google
  login, no Google token/refresh storage, no provider keys, no OpenAI shared
  traffic, no production Oracle/cloud runtime, no live Discord, no arbitrary
  shell/file/tool execution, no automatic local-to-cloud upload, and no
  production signing/trust store.
- Primary traceability range: `v0.7.0..v0.8.0`; every merged PR in that range
  is listed in `docs/releases/0.8.0.md`.

## v0.20.0-alpha.1 Web CLI API Control Spine

- GitHub pre-release target: `v0.20.0-alpha.1`.
- Release title: `2026.06.11 - YonerAI v0.20.0-alpha.1 Web CLI API Control Spine`.
- Release date: `2026-06-11`.
- Public release body: `docs/releases/0.20.0-alpha.1.md`.
- Status: prerelease staging Control Spine client after v0.19.0-alpha.1.
- What users can try now:
  `yonerai login --bridge --open-browser --wait-linked --pretty --lang ja`,
  `yonerai whoami --pretty --lang ja`,
  `yonerai api status --pretty --lang ja`,
  `yonerai api ping --pretty --lang ja`,
  `yonerai api rate-limit --pretty --lang ja`,
  `yonerai project list --pretty --lang ja`,
  `yonerai auth sessions --pretty --lang ja`,
  `yonerai auth revoke-session <session_id> --pretty --lang ja`,
  `yonerai audit list --pretty --lang ja`,
  TUI `/認証`, `/ログイン`, `/API`, `/プロジェクト`, `/セッション`, `/監査`,
  and `/同期`.
- Boundary: staging Control Spine only; no production Google login, no Google
  client secret in the public repo, no Google token storage, no refresh-token
  storage, no automatic local-to-cloud upload, no OpenAI shared traffic runtime,
  no local private content upload, no production AWS backend in the public repo,
  no production Oracle/cloud runtime, no live Discord, no arbitrary shell/file/tool
  execution, and no production signing/trust store.
- Security carry-in: linked auth state requires a validated `account/me`
  response and is not accepted from poll-only data.
- Primary traceability range: `v0.19.0-alpha.1..v0.20.0-alpha.1`.

## v0.19.0-alpha.1 Cloud Conversation Sync Preview

- GitHub pre-release target: `v0.19.0-alpha.1`.
- Release title: `2026.06.06 - YonerAI v0.19.0-alpha.1 Cloud Conversation Sync Preview`.
- Release date: `2026-06-06`.
- Public release body: `docs/releases/0.19.0-alpha.1.md`.
- Evidence: `docs/evidence/STAGING_CLOUD_SYNC_PREVIEW_E2E.md`.
- Status: prerelease staging cloud conversation sync preview after
  v0.18.0-alpha.2.
- What users can try now:
  `yonerai auth google login --staging --bridge --open-browser --wait-linked --pretty --lang ja`,
  `yonerai auth session status --pretty --lang ja`,
  `yonerai sync conversations --pretty --lang ja`,
  `yonerai sync conversation show <cloud_conversation_id> --pretty --lang ja`,
  `yonerai sync preview --direction cloud-to-local --audit-reason "user_selected_cloud_preview" --pretty --lang ja`,
  `yonerai sync preview --direction local-to-cloud --audit-reason "manual_preview_only" --pretty --lang ja`,
  TUI `/認証`, `/同期`, and `/クラウド`.
- Boundary: staging sync preview only; no production Google login, no Google
  client secret in the public repo, no Google token storage, no refresh-token
  storage, no automatic local-to-cloud upload, no OpenAI shared traffic runtime,
  no local private content upload, no production AWS backend, no production
  Oracle/cloud runtime, no live Discord, no arbitrary shell/file/tool execution,
  and no production signing/trust store.
- Primary traceability range: `v0.18.0-alpha.2..v0.19.0-alpha.1`.

## v0.18.0-alpha.2 Staging Google Login E2E

- GitHub pre-release target: `v0.18.0-alpha.2`.
- Release title: `2026.06.06 - YonerAI v0.18.0-alpha.2 Staging Google Login E2E`.
- Release date: `2026-06-06`.
- Public release body: `docs/releases/0.18.0-alpha.2.md`.
- Evidence: `docs/evidence/STAGING_GOOGLE_LOGIN_E2E.md`.
- Status: prerelease staging E2E evidence and bridge-hardening slice after
  v0.18.0-alpha.1.
- What users can try now:
  `yonerai auth google login --staging --bridge --open-browser --wait-linked --pretty --lang ja`,
  `yonerai auth status --pretty --lang ja`, TUI `/認証`, and `/auth`.
- Boundary: staging Google login only; no production Google login, no Google
  client secret in the public repo, no Google token storage, no refresh-token
  storage, no account sync, no OpenAI shared traffic runtime, no local private
  content upload, no production AWS backend, no production Oracle/cloud runtime,
  no live Discord, no arbitrary shell/file/tool execution, and no production
  signing/trust store.
- Security carry-in: backend-provided bridge paths now reject token-like query
  parameters and URL fragments before the public CLI prints or joins URLs.
- Primary traceability range: `v0.18.0-alpha.1..v0.18.0-alpha.2`.

## v0.18.0-alpha.1 Staging Google Login Linked UX

- GitHub pre-release target: `v0.18.0-alpha.1`.
- Release title: `2026.06.06 - YonerAI v0.18.0-alpha.1 Staging Google Login Linked UX`.
- Release date: `2026-06-06`.
- Public release body: `docs/releases/0.18.0-alpha.1.md`.
- Status: prerelease staging linked-login slice after v0.17.0-alpha.2.
- What users can try now:
  `yonerai auth google login --staging --bridge --open-browser --wait-linked --pretty --lang ja`,
  `yonerai auth status --pretty --lang ja`, TUI `/認証`, and `/auth`.
- Boundary: staging Google login only; no production Google login, no Google
  client secret in the public repo, no Google token storage, no refresh-token
  storage, no account sync, no OpenAI shared traffic runtime, no local private
  content upload, no production AWS backend, no production Oracle/cloud runtime,
  no live Discord, no arbitrary shell/file/tool execution, and no production
  signing/trust store.
- Live staging smoke reached linked state through `api-staging.yonerai.com`, and
  `GET /v1/account/me` returned 200 with token printing/storage disabled.
- Primary traceability range: `v0.17.0-alpha.2..v0.18.0-alpha.1`.

## v0.17.0-alpha.1 Staging Google Login UX

- GitHub pre-release target: `v0.17.0-alpha.1`.
- Release title: `2026.06.05 - YonerAI v0.17.0-alpha.1 Staging Google Login UX`.
- Release date: `2026-06-05`.
- Public release body: `docs/releases/0.17.0-alpha.1.md`.
- Status: prerelease staging-auth UX slice after v0.16.0-alpha.1.
- What users can try now: `yonerai auth status --pretty --lang ja`,
  `yonerai auth google login --dry-run --pretty --lang ja`,
  `yonerai auth google login --staging --pretty --lang ja` with an allowlisted
  staging origin, TUI `/認証`, and first-launch account onboarding.
- Boundary: staging/auth-contract UX only; no production Google login, no
  Google client secret in the public repo, no token exchange in the public CLI,
  no refresh token plaintext storage, no production AWS backend, no production
  Oracle/cloud runtime, no live Discord, no OpenAI shared traffic runtime, no
  private content upload, no arbitrary shell/file/tool execution, and no
  production signing/trust store.
- Primary traceability range: `v0.16.0-alpha.1..v0.17.0-alpha.1`; PR #513.

## v0.16.0-alpha.1 CLI Architecture and Policy Runtime

- GitHub pre-release target: `v0.16.0-alpha.1`.
- Release title: `2026.06.05 - YonerAI v0.16.0-alpha.1 CLI Architecture and Policy Runtime`.
- Release date: `2026-06-05`.
- Public release body: `docs/releases/0.16.0-alpha.1.md`.
- Status: prerelease CLI architecture and policy-runtime slice after
  v0.15.0-alpha.1.
- What users can try now: `yonerai`, `yonerai chat --lang ja`,
  `yonerai policy status --pretty --lang ja`, `yonerai policy status --json`,
  `yonerai auth status --pretty --lang ja`,
  `yonerai auth google login --dry-run --pretty --lang ja`,
  `yonerai install status --json`, `yonerai demo --json`, and TUI
  `/ポリシー`.
- Boundary: architecture/policy/onboarding prerelease only; no production
  AWS backend, no production Oracle/cloud runtime, no production Google login,
  no live Discord, no OpenAI shared traffic runtime, no private content upload,
  no deploy/public tunnel, no arbitrary shell/file/tool execution, no
  production signing/trust store, and no production network installer.
- Security carry-in: explicit allowlisted status fetch now rejects redirects
  before reaching loopback or private endpoints.
- Primary traceability range: `v0.15.0-alpha.1..v0.16.0-alpha.1`; PRs #507
  and #509.

## v0.15.0-alpha.1 Status API Bridge

- GitHub pre-release target: `v0.15.0-alpha.1`.
- Release title: `2026.06.03 - YonerAI v0.15.0-alpha.1 Status API Bridge`.
- Release date: `2026-06-03`.
- Public release body: `docs/releases/0.15.0-alpha.1.md`.
- Status: prerelease status/API contract slice after v0.14.0-alpha.1.
- What users can try now: `yonerai status check --pretty --lang ja`,
  `yonerai status check --json`, `yonerai api status --pretty --lang ja`,
  `yonerai api status --json`,
  `yonerai api status --status-source docs/contracts/fixtures/status-api-0.1/status-feed.fixture.json --json`,
  `yonerai doctor --pretty --lang ja`, TUI `/状態`, `/API`, and `/公式`.
- Boundary: contract/schemas/fixtures/CLI/TUI visibility only; no production
  AWS backend, no production Oracle/cloud runtime, no production Google login,
  no live Discord, no OpenAI shared traffic runtime, no private content upload,
  no deploy/public tunnel, no arbitrary shell/file/tool execution, no
  production signing/trust store, and no production network installer.
- Public JSON guard: local or allowlisted status feeds now reject
  private/reserved IP URLs, internal hostnames, AWS ARNs, local paths, and
  secret-like markers before public JSON is printed.
- Primary traceability range: `v0.14.0-alpha.1..v0.15.0-alpha.1`; PRs #500
  and #501.

## v0.14.0-alpha.1 Official API Contract

- GitHub pre-release target: `v0.14.0-alpha.1`.
- Release title: `2026.06.02 - YonerAI v0.14.0-alpha.1 Official API Contract`.
- Release date: `2026-06-02`.
- Public release body: `docs/releases/0.14.0-alpha.1.md`.
- Status: prerelease official API contract slice after v0.13.0-alpha.2.
- What users can try now: `yonerai api status --pretty --lang ja`,
  `yonerai api status --json`, `yonerai api contract --pretty --lang ja`,
  `yonerai api contract --json`, `yonerai api rate-limit --pretty --lang ja`,
  `yonerai sync api-contract --json`, and TUI `/API`, `/api`, `/公式`.
- Boundary: contract/schemas/fixtures/CLI/TUI visibility only; no production
  AWS backend, no production Oracle/cloud runtime, no production Google login,
  no live Discord, no OpenAI shared traffic runtime, no private content upload,
  no deploy/public tunnel, no arbitrary shell/file/tool execution, no
  production signing/trust store, and no production network installer.
- Primary traceability range: `v0.13.0-alpha.2..v0.14.0-alpha.1`; PRs #497
  and #498.

## v0.13.0-alpha.2 Agent Console Dogfood Patch

- GitHub pre-release target: `v0.13.0-alpha.2`.
- Release title: `2026.06.02 - YonerAI v0.13.0-alpha.2 Agent Console Dogfood Patch`.
- Release date: `2026-06-02`.
- Public release body: `docs/releases/0.13.0-alpha.2.md`.
- Status: prerelease dogfood patch after v0.13.0-alpha.1.
- What users can try now: `yonerai`, `yonerai chat --lang ja`,
  `/コマンド`, `/パレット`, `/設定`, `/設定 記憶`, `/記憶`, `/メモリ`,
  `/更新`, `/モード`, `/計画 <task>`, `/レビュー <text>`,
  `/権限 read-only`, `/権限 dry-run-only`, `@planner <task>`,
  `@reviewer <task>`, and `@researcher <task>`.
- Boundary: alpha dogfood stabilization only; no stable v0.7.0 promotion, no
  uncontrolled autonomous agents, no production cloud memory, no production
  Oracle/cloud runtime, no production Google login, no OpenAI shared traffic
  runtime, no live Discord, no automatic local-to-cloud private upload, no
  deploy/public tunnel, no arbitrary shell/file/tool execution, no production
  signing/trust store, and no production network installer.
- Primary traceability range: `v0.13.0-alpha.1..v0.13.0-alpha.2`; PR #494.

## v0.13.0-alpha.1 Agent Console Runtime

- GitHub pre-release target: `v0.13.0-alpha.1`.
- Release title: `2026.06.01 - YonerAI v0.13.0-alpha.1 Agent Console Runtime`.
- Release date: `2026-06-01`.
- Public release body: `docs/releases/0.13.0-alpha.1.md`.
- Status: prerelease agent-console interaction layer after
  v0.12.0-alpha.2.
- What users can try now: `yonerai`, `yonerai chat --lang ja`, `/`,
  `/コマンド`, `/パレット`, `/モード`, `/モード 計画`, `/モード ビルド`,
  `/計画 <task>`, `/レビュー <text>`, `/権限`, `/権限 読み取りのみ`,
  `/権限 ドライランのみ`, `@planner <task>`, `@reviewer <task>`,
  `@researcher <task>`, `/記憶`, `/メモリ`, `/memory`, and `/更新`.
- Boundary: command palette, mode/permission UX, public-safe subagent previews,
  and TUI discoverability only; no uncontrolled autonomous agents, no
  production cloud memory, no production Oracle/cloud runtime, no production
  Google login, no OpenAI shared traffic runtime, no live Discord, no automatic
  local-to-cloud private upload, no deploy/public tunnel, no arbitrary
  shell/file/tool execution, no production signing/trust store, and no
  production network installer.
- Primary traceability range: `v0.12.0-alpha.2..v0.13.0-alpha.1`; PR #492.

## v0.12.0-alpha.2 Memory UX and Update Notice

- GitHub pre-release target: `v0.12.0-alpha.2`.
- Release title: `2026.06.01 - YonerAI v0.12.0-alpha.2 Memory UX and Update Notice`.
- Release date: `2026-06-01`.
- Public release body: `docs/releases/0.12.0-alpha.2.md`.
- Status: prerelease memory UX and update notice hardening after
  v0.12.0-alpha.1.
- What users can try now: `yonerai memory status --pretty --lang ja`,
  `yonerai memory add "..." --scope local --pretty --lang ja`,
  `yonerai memory list --scope local --pretty --lang ja`,
  `yonerai memory forget <memory_id> --pretty --lang ja`,
  `yonerai memory sync preview --direction cloud-to-local --pretty --lang ja`,
  `yonerai memory sync preview --direction local-to-cloud --pretty --lang ja`,
  `yonerai config set memory_enabled off`,
  `yonerai config set memory_cloud_preview off`, TUI `/記憶`, `/メモリ`,
  `/memory`, `/設定 記憶`, and `/更新`.
- Boundary: local memory UX and preview-contract hardening only; no production
  cloud memory, no production Oracle/cloud runtime, no production Google login,
  no OpenAI shared traffic runtime, no live Discord, no automatic local-to-cloud
  private upload, no deploy/public tunnel, no arbitrary shell/file/tool
  execution, no production signing/trust store, and no production network
  installer.
- Primary traceability range: `v0.12.0-alpha.1..v0.12.0-alpha.2`; PRs #486,
  #487, and #488.

## v0.12.0-alpha.1 Memory Boundary Runtime

- GitHub pre-release target: `v0.12.0-alpha.1`.
- Release title: `2026.06.01 - YonerAI v0.12.0-alpha.1 Memory Boundary Runtime`.
- Release date: `2026-06-01`.
- Public release body: `docs/releases/0.12.0-alpha.1.md`.
- Status: prerelease local memory boundary runtime after
  v0.11.0-alpha.1.
- What users can try now: `yonerai memory status --pretty --lang ja`,
  `yonerai memory add "..." --scope local --pretty --lang ja`,
  `yonerai memory list --scope local --pretty --lang ja`,
  `yonerai memory forget <memory_id> --pretty --lang ja`,
  `yonerai memory sync preview --direction cloud-to-local --pretty --lang ja`,
  `yonerai memory sync preview --direction local-to-cloud --pretty --lang ja`,
  `yonerai ask "hello" --auto --memory-store <local.jsonl> --json`, TUI
  `/記憶`, `/メモリ`, `/設定`, `/設定 記憶`, and `/設定 更新`.
- Boundary: local JSONL memory store, redacted summaries, memory-id-only ledger
  integration, sync preview contracts, TUI visibility, and low-resolution
  self-evolution signal validation only; no production cloud memory, no
  production Oracle/cloud runtime, no production Google login, no OpenAI shared
  traffic runtime, no live Discord, no automatic local-to-cloud private upload,
  no deploy/public tunnel, no arbitrary shell/file/tool execution, no
  production signing/trust store, and no production network installer.
- Primary traceability range: `v0.11.0-alpha.1..v0.12.0-alpha.1`; PR #482.

## v0.11.0-alpha.1 Account Sync and Oracle API Foundation

- GitHub pre-release target: `v0.11.0-alpha.1`.
- Release title: `2026.05.31 - YonerAI v0.11.0-alpha.1 Account Sync and Oracle API Foundation`.
- Release date: `2026-05-31`.
- Public release body: `docs/releases/0.11.0-alpha.1.md`.
- Status: prerelease account-sync and Official API contract foundation after
  v0.10.0-alpha.1.
- What users can try now: `yonerai`, `/認証`, `/同期`, `/プライバシー`,
  `yonerai auth status --pretty --lang ja`,
  `yonerai privacy status --pretty --lang ja`,
  `yonerai sync status --pretty --lang ja`,
  `yonerai sync preview --direction cloud-to-local --json`,
  `yonerai sync approve --dry-run --direction local-to-cloud --json`,
  `yonerai sync api-contract --json`, `yonerai sync rate-limit --json`, and
  local manifest dry-run commands against
  `releases/manifest.v0.11.0-alpha.1.json`.
- Boundary: account/sync/API/rate-limit contracts, fixtures, conformance tests,
  CLI/TUI visibility, and sanitized private YonerAIOracle handoff only; no
  production Oracle/cloud runtime, no production Google login, no OpenAI shared
  traffic runtime, no live Discord, no automatic local-to-cloud private upload,
  no deploy/public tunnel, no arbitrary shell/file/tool execution, no
  production signing/trust store, and no production network installer.
- Primary traceability range: `v0.10.0-alpha.1..v0.11.0-alpha.1`; PRs #479
  and #480.

## v0.10.0-alpha.1 Public Orchestration Boundary

- GitHub pre-release target: `v0.10.0-alpha.1`.
- Release title: `2026.06.01 - YonerAI v0.10.0-alpha.1 Public Orchestration Boundary`.
- Release date: `2026-06-01`.
- Public release body: `docs/releases/0.10.0-alpha.1.md`.
- Status: prerelease boundary/orchestration update after v0.9.0-alpha.1.
- What users can try now: `yonerai`, `/ホーム`, `/状態`, `/設定`, `/モデル`,
  `/ローカルLLM`, `/提供元選択`, `/安全`, `/認証`, `/プライバシー`,
  `/自己進化`, `/更新`, Google auth dry-run/privacy status commands, and local
  manifest dry-run commands against `releases/manifest.v0.10.0-alpha.1.json`.
- Boundary: TUI orientation, auth/privacy boundary hardening, Quality Wall
  hardening, and plan-only installer/site alignment only; no production
  Oracle/cloud runtime, no live Discord, no production Google login, no OpenAI
  shared traffic runtime, no deploy/public tunnel, no arbitrary shell/file/tool
  execution, no production signing/trust store, and no production network
  installer.
- Primary traceability range: `v0.9.0-alpha.1..v0.10.0-alpha.1`; PRs #474,
  #475, #476, #477, and #478.

## v0.9.0-alpha.1 TUI Value Completion and Quality Wall

- GitHub pre-release target: `v0.9.0-alpha.1`.
- Release title: `2026.05.31 - YonerAI v0.9.0-alpha.1 TUI Value Completion and Quality Wall`.
- Release date: `2026-05-31`.
- Public release body: `docs/releases/0.9.0-alpha.1.md`.
- Status: prerelease TUI usability and safety-gate update after
  v0.8.0-alpha.1.
- What users can try now: `yonerai`, `/`, `/提供元選択`, `/選択 2`,
  `/選択 5`, `/ライブ`, `/更新通知`, `/設定`, `/状態`, `/モデル`, `/ローカルLLM`,
  `/安全`, `/認証`, `/プライバシー`, `/自己進化`, `/更新`, and local manifest
  dry-run commands against `releases/manifest.v0.9.0-alpha.1.json`.
- Boundary: Japanese-first TUI value completion and quality-wall hardening
  only; no production Oracle/cloud runtime, no live Discord, no production
  Google login, no OpenAI shared traffic runtime, no deploy/public tunnel, no
  arbitrary shell/file/tool execution, no production signing/trust store, and
  no production network installer.
- Primary traceability range: `v0.8.0-alpha.1..v0.9.0-alpha.1`; PRs #471 and
  #472.

## v0.8.0-alpha.1 Official Install/Auth Boundary

- GitHub pre-release target: `v0.8.0-alpha.1`.
- Release title: `2026.05.31 - YonerAI v0.8.0-alpha.1 Official Install/Auth Boundary`.
- Release date: `2026-05-31`.
- Public release body: `docs/releases/0.8.0-alpha.1.md`.
- Status: prerelease boundary after v0.7.0-alpha.1.
- What users can try now: `yonerai`, `/認証`, `/プライバシー`, `/自己進化`,
  `/更新`, `yonerai auth status --pretty --lang ja`,
  `yonerai auth google login --dry-run --pretty --lang ja`,
  `yonerai privacy status --pretty --lang ja`,
  `yonerai evolve status --pretty --lang ja`, `.\install.ps1`, and local
  manifest dry-run commands against `releases/manifest.v0.8.0-alpha.1.json`.
- Boundary: plan-only installer, Google OAuth dry-run/contract only, OpenAI
  shared traffic disabled by default, self-evolution proposal-only, no
  production Oracle/cloud runtime, no live Discord, no deploy/public tunnel, no
  arbitrary shell/file/tool execution, no production signing/trust store, and
  no production network installer.
- Primary traceability range: `v0.7.0-alpha.1..v0.8.0-alpha.1`; PR #470.

## v0.7.0-alpha.1 Official Bridge Foundation

- GitHub pre-release target: `v0.7.0-alpha.1`.
- Release title: `2026.05.31 - YonerAI v0.7.0-alpha.1 Official Bridge Foundation`.
- Release date: `2026-05-31`.
- Public release body: `docs/releases/0.7.0-alpha.1.md`.
- Status: prerelease bridge foundation after v0.6.0 stable CLI Local Runtime.
- What users can try now: `yonerai evolve status --pretty --lang ja`,
  `yonerai evolve simulate --fixture tests/fixtures/self_evolution/queue_signals.json --pretty --lang ja`,
  `yonerai evolve proposals list/show`, `/自己進化`, `/evolve`,
  `yonerai auth status --pretty --lang ja`,
  `yonerai auth google login --dry-run --pretty --lang ja`,
  `yonerai privacy status --pretty --lang ja`, and local manifest dry-run
  commands against `releases/manifest.v0.7.0-alpha.1.json`.
- Boundary: proposal-only self-evolution, Google OAuth dry-run/contract only,
  OpenAI shared traffic disabled by default, no production Oracle/cloud
  runtime, no live Discord, no deploy/public tunnel, no arbitrary
  shell/file/tool execution, no production signing/trust store, and no
  production network installer.
- Primary traceability range: `v0.6.0..v0.7.0-alpha.1`; PR #469.

## v0.6.0 CLI Local Runtime

- GitHub release target: `v0.6.0`.
- Release title: `2026.05.27 — YonerAI CLI Local Runtime v0.6.0`.
- Release date: `2026-05-27`.
- Public release body: `docs/releases/0.6.0.md`.
- Status: stable release for the local CLI runtime slice only, not full YonerAI
  cloud production and not a production network installer.
- What users can try now: `yonerai`, `yonerai chat`, `/設定`, `/提供元`,
  `/モデル`, `/ローカルLLM`, `/安全`, `/認証`, `/プライバシー`, `/履歴`, `/タスク`,
  `/エージェント`, `/更新`, `yonerai auth status --pretty --lang ja`,
  `yonerai privacy status --pretty --lang ja`, `yonerai update check --pretty`,
  `yonerai manifest verify releases/manifest.v0.6.0.json --pretty`,
  `yonerai install plan --manifest releases/manifest.v0.6.0.json --pretty`, and
  `yonerai update plan --manifest releases/manifest.v0.6.0.json --pretty`.
- Boundary: no production Oracle/cloud runtime, no live Discord, no
  deploy/public tunnel, no arbitrary shell/file/tool execution, no default live
  provider calls, no provider key output/storage, no production Google login,
  no refresh token storage, no OpenAI shared traffic, no production
  signing/trust store, and no production installer.
- Primary traceability range: `v0.6.0-alpha.1..v0.6.0`; PRs #456, #457, #458,
  #460, #461, #462, #463, #464, #465, and #466.
- Release body includes operation-manual commands, security boundaries,
  update/install status, known limitations, and traceability.

## v0.6.0-alpha.1 CLI TUI Runtime

- GitHub pre-release target: `v0.6.0-alpha.1`.
- Release title: `2026.05.27 — YonerAI v0.6.0-alpha.1 CLI TUI Runtime`.
- Release date: `2026-05-27`.
- Public release body: `docs/releases/0.6.0-alpha.1.md`.
- TUI note: `yonerai` and `yonerai chat` now use `prompt_toolkit` completion
  and Rich terminal panels/status when available, with plain fallback for
  non-TTY and CI.
- What users can try now: `/`, `/設定`, `/モデル`, `/提供元`, `/安全`, `/履歴`,
  `/タスク`, `/エージェント`, `/更新`, `yonerai update check --pretty`,
  `yonerai update check --json`, and `.\install.ps1`.
- Boundary: alpha TUI runtime only; no production Oracle/cloud runtime, no live
  Discord, no deploy/public tunnel, no arbitrary shell/file/tool execution, no
  default live provider calls, no provider key output/storage, no production
  signing/trust store, and no production installer.
- Primary traceability range: `v0.5.1..v0.6.0-alpha.1`; implementation PRs:
  #454 `feat: YonerAI CLI TUIランタイムを追加する` and #455
  `fix: v0.6 alpha manifest hashを更新する`.
- Post-tag correction: #456 synchronizes the current-main manifest with the
  actual GitHub Release ZIP uploaded by the release workflow. The tag is not
  moved.
- Release body includes explicit validation evidence, release asset hash/size,
  not-included boundaries, known limitations, and traceability.

## v0.5.1 CLI Local Runtime Distribution Trust Update

- GitHub release target: `v0.5.1`.
- Release title: `2026.05.26 — YonerAI CLI Local Runtime v0.5.1 Distribution Trust Update`.
- Release date: `2026-05-26`.
- Public release body: `docs/releases/0.5.1.md`.
- Distribution note: this is a stable patch release for local CLI runtime
  distribution trust hardening, not full YonerAI cloud production and not a
  production installer.
- Installer manifest note: `releases/manifest.v0.5.1.json` records the v0.5.1
  GitHub Release ZIP asset with SHA256, size, and non-production placeholder
  signature status for local manifest verification and dry-run planning.
- What users can try now: `.\install-local.ps1`, `.\install-local.ps1 -Execute
  -Launch`, `yonerai`, `yonerai doctor --pretty --lang ja`, `yonerai manifest
  verify releases/manifest.v0.5.1.json --pretty`, `yonerai install plan
  --manifest releases/manifest.v0.5.1.json --pretty`, and `yonerai update plan
  --manifest releases/manifest.v0.5.1.json --pretty`.
- Boundary: no production installer, no `irm ... | iex`, no network
  download-and-execute installer, no PATH mutation by default, no production
  signing/trust store, no production Oracle/cloud runtime, no live Discord, no
  npm/winget channel, and no provider keys printed or stored.
- Primary traceability range: `v0.5.0..v0.5.1`, PRs #451, #452, and #453.

## v0.5.0 CLI Local Runtime

- GitHub release target: `v0.5.0`.
- Release title: `2026.05.26 - YonerAI CLI Local Runtime v0.5.0`.
- Release date: `2026-05-26`.
- Public release body: `docs/releases/0.5.0.md`
- Distribution note: YonerAI is source-available and noncommercial, not OSI
  open source. Code is under PolyForm Noncommercial License 1.0.0; docs/assets
  are CC BY-NC-ND 4.0 unless stated otherwise; the YonerAI brand is All Rights
  Reserved.
- Installer manifest note: `releases/manifest.v0.5.0.json` records the v0.5.0
  GitHub Release ZIP asset with SHA256 and non-production placeholder signature
  status for local manifest verification and dry-run planning.
- GitHub release lane: non-prerelease semantic release for the local CLI runtime
  slice only. This is not full cloud production.
- What users can try now: `yonerai`, `yonerai chat`, first-launch language
  selection, Japanese-first settings/safety/provider/task/agent/run-history
  views, English slash aliases, `yonerai ask ... --auto`, `yonerai providers`,
  `yonerai doctor --lang ja`, and explicit local run ledger commands.
- Capability slice: installable `yonerai` console entrypoint, Mission Control
  header, task progress timeline, deterministic reviewer/subagent plan,
  provider capability negotiation, loopback-only local LLM readiness, redacted
  run history, and conservative safety controls.
- Boundary: no production Oracle, no Official Managed Cloud runtime, no live
  Discord, no deploy/public tunnel, no arbitrary shell/file/tool execution, no
  default live provider calls, no production signing/trust store, and no
  provider keys printed or stored.
- Primary traceability range: `v0.4.0-alpha.1..v0.5.0`, PRs #447, #448, #449,
  and release-prep PR #450.

## v0.4.0-alpha.1 Mission Control CLI Slice

- GitHub pre-release target: `v0.4.0-alpha.1`.
- Release title: `2026.05.26 — YonerAI v0.4.0-alpha.1 Mission Control CLI Slice`.
- Release date: `2026-05-26`.
- Public release body: `docs/releases/0.4.0-alpha.1.md`
- GitHub release lane: semantic alpha **pre-release** only. Do not mark this as
  stable/latest. The normal public GitHub Release stream remains date-tagged
  unless the owner separately approves a date-tag production release.
- What users can try now: `yonerai`, `yonerai chat`, `/設定`, `/安全`,
  `/エージェント`, `/履歴`, `/表示 <実行ID>`, English compatibility aliases such
  as `/settings` and `/agents`, `yonerai ask ... --auto --json/--pretty`, and
  `yonerai runs show ... --pretty --lang ja`.
- Capability slice: Mission Control header, task progress timeline, redacted
  ledger progress events, visible deterministic reviewer/subagent plan, Japanese
  labels, and terminal-control output escaping.
- Boundary: no production Oracle, no Official Managed Cloud runtime, no live
  Discord, no deploy/public tunnel, no arbitrary shell/file/tool execution, no
  default live provider calls, no production signing/trust store, and no
  provider keys printed or stored.
- Primary traceability range: `v0.3.0-alpha.1..v0.4.0-alpha.1`, PRs #442, #444,
  and #445.

## v0.3.0-alpha.1 Interactive CLI Slice

- GitHub pre-release target: `v0.3.0-alpha.1`.
- Release title: `2026.05.26 — YonerAI v0.3.0-alpha.1 Interactive CLI Slice`.
- Release date: `2026-05-26`.
- Public release body: `docs/releases/0.3.0-alpha.1.md`
- GitHub release lane: semantic alpha **pre-release** only. Do not mark this as
  stable/latest. The normal public GitHub Release stream remains date-tagged
  (for example `v2026.5.21.5`) unless the owner separately approves a date-tag
  production release.
- What users can try now: `yonerai`, `yonerai chat`, first-launch Japanese/English selection, Japanese slash commands such as `/設定`, `/提供元`, `/安全`, `/履歴`, `/表示 <実行ID>`, local preference commands `yonerai config show/set`, and compatibility aliases such as `/settings` in Japanese mode.
- Capability slice: Japanese-first interactive chat shell, settings/provider/safety/run-history screens, local non-secret config, `ask --auto` chat execution, non-TTY fallback, scripted chat mode for tests/automation, and current-main P1/P2 review-debt fixes including Oracle stub privacy routing, missing hybrid dependency handling, deployment classification, relay auto URL trust checks, extension manifest redaction, unknown capability evaluation ordering, duplicate unknown-capability redaction, and relay pretty output status.
- Boundary: no production Oracle, no Official Managed Cloud runtime, no live Discord, no deploy/public tunnel, no arbitrary shell/file/tool execution, no default live provider calls, no production signing/trust store, and no provider keys printed or stored.
- Primary traceability range: `v0.2.0-alpha.1..v0.3.0-alpha.1`, PRs #429, #430, #431, #435, #437, #440, and #441.

## v0.2.0-alpha.1 Real CLI Runtime Slice

- GitHub pre-release target: `v0.2.0-alpha.1`.
- Release title: `2026.05.26 — YonerAI v0.2.0-alpha.1 Real CLI Runtime Slice`.
- Release date: `2026-05-26`.
- Public release body: `docs/releases/0.2.0-alpha.1.md`
- What users can try now: `yonerai start --guided --lang ja`, `yonerai providers --pretty --lang ja`, `yonerai providers --json`, `yonerai ask "hello" --auto --pretty --lang ja`, `yonerai ask "hard public reasoning over public API docs" --auto --json`, workspace-scoped `yonerai ask ... --auto --file <path> --workspace <dir> --json`, explicit local `yonerai ask "hello" --provider local --live --json`, explicit external `yonerai ask ... --provider openai-compatible|anthropic|gemini --live --json`, `yonerai runs list/show --pretty --lang ja`, `yonerai demo --pretty`, and `yonerai doctor --pretty --lang ja`.
- Capability slice: provider readiness CLI, Japanese-first auto/runs output, auto routing guardrails, local LLM loopback opt-in, external-provider live opt-in, local-only redacted ledger visibility, Workspace File Access Guard, and current security/runtime review fixes.
- Boundary: no production Oracle, no Official Managed Cloud runtime, no live Discord, no deploy/public tunnel, no arbitrary shell/file/tool execution, no default live provider calls, no production signing/trust store, and no provider keys printed or stored.
- Primary traceability range: `v0.1.0-alpha.4..v0.2.0-alpha.1`, 2 PRs: #427 and #428.

## v0.1.0-alpha.4 CLI Auto Runtime Slice

- GitHub pre-release target: `v0.1.0-alpha.4`.
- Release title: `2026.05.26 — YonerAI v0.1.0-alpha.4 CLI Auto Runtime Slice`.
- Release date: `2026-05-26`.
- Public release body: `docs/releases/0.1.0-alpha.4.md`
- What users can try now: `yonerai ask "hello" --auto --json`, `yonerai ask "hard public reasoning over public API docs" --auto --json`, workspace-scoped `yonerai ask ... --auto --file <path> --workspace <dir> --json`, `yonerai ask "search the web for YonerAI alpha docs" --auto --json`, `yonerai ask "delete files and run shell command" --auto --json`, `yonerai ask ... --auto --ledger <local.jsonl> --json`, `yonerai demo --pretty`, `yonerai doctor --json`, and `yonerai start --guided --lang ja --pretty`.
- Capability slice: task difficulty/privacy classification, automatic local/stub route selection, mock provider execution, loopback-only local LLM opt-in, mock search, reviewer/subtask plan, local-dev Oracle stub envelope, explicit local ledger events, workspace file access guard, and deny-by-default dangerous-operation handling.
- Boundary: no production Oracle, no Official Managed Cloud runtime, no live Discord, no public tunnel, no deploy, no arbitrary shell/file/tool execution, no default live provider calls, and no private file content or provider keys sent to Oracle stub/cloud-candidate payloads.
- Primary traceability range: `v0.1.0-alpha.3..v0.1.0-alpha.4`, 4 PRs.
- Primary traceability PRs: #423, #424, #425, and #426.

## v0.1.0-alpha.3 Real Hybrid Execution Slice

- GitHub pre-release target: `v0.1.0-alpha.3`.
- Release title: `2026.05.26 — YonerAI v0.1.0-alpha.3 Real Hybrid Execution Slice`.
- Release date: `2026-05-26`.
- Public release body: `docs/releases/0.1.0-alpha.3.md`
- What users can try now: `yonerai hybrid run --pretty`, `yonerai hybrid run --json`, `yonerai node status --json`, `yonerai node pair --dry-run --json`, `yonerai oracle status --json`, `yonerai oracle queue --json`, `yonerai route preview ... --json`, `yonerai start --guided --lang ja --pretty`, `yonerai demo --pretty`, and `yonerai doctor --json`.
- Capability slice: local-dev Local Node fixture, hash-only session evidence, in-memory loopback relay transport, mock provider execution, redacted run events, Oracle stub request/result envelopes, route matrix for local/hybrid/cloud-contract/deny decisions, and demo/doctor/start integration.
- Boundary: no production Oracle, no Official Managed Cloud runtime, no live Discord, no public tunnel, no deploy, no production signing keys, no production trust stores, no arbitrary shell/file/tool execution, no default live provider calls, and no private file content or provider keys sent to Oracle stub/cloud-candidate payloads.
- Primary traceability range: `v0.1.0-alpha.2..v0.1.0-alpha.3`, 75 PRs.
- Primary traceability PRs: #324, #325, #326, #327, #335, #336, #337, #338, #339, #340, #341, #342, #343, #345, #357, #358, #359, #360, #361, #362, #363, #364, #365, #366, #367, #368, #369, #370, #371, #372, #373, #374, #375, #376, #377, #378, #379, #380, #381, #382, #383, #384, #385, #386, #387, #388, #389, #390, #391, #392, #393, #394, #395, #396, #397, #398, #399, #400, #401, #402, #403, #404, #405, #406, #407, #408, #409, #414, #415, #417, #418, #419, #420, #421, and #422.

## v0.1.0-alpha.2 Capability Slice

- GitHub pre-release: `v0.1.0-alpha.2`.
- Release title: `YonerAI v0.1.0-alpha.2 Capability Slice`.
- Release date: `2026-05-22`.
- Public release body: `docs/releases/0.1.0-alpha.2.md`
- What users can try now: `yonerai demo`, `yonerai doctor`, `yonerai status`, `yonerai ask --provider mock`, workspace-scoped `yonerai ask --file ... --workspace ...`, `yonerai plan`, `yonerai search mock`, `yonerai ops plan`, explicit local `yonerai memory`, `yonerai discord synthetic`, `yonerai manifest verify`, `yonerai install plan --manifest releases/manifest.example.json`, and `yonerai install plan-windows`.
- Capability slice: opt-in provider adapters, loopback-only local LLM, workspace file summarize, mock search, SafeShell planning, explicit local memory, synthetic Discord gateway, official status contracts, installer dry-run planning, run ledger/history, and deterministic demo integration.
- Boundary: no default live provider calls, no live Discord, no arbitrary shell, no arbitrary local file access, no production Oracle/control-plane implementation, no production signing keys, no production trust stores, no Google login, no production DB behavior, and no Official Managed Cloud runtime in this public repo.
- Primary traceability range: `v0.1.0-alpha.1..v0.1.0-alpha.2`, 16 PRs.
- Primary traceability PRs: #307, #308, #309, #310, #311, #312, #314, #315, #316, #317, #318, #319, #320, #321, #322, and #323.
- External/date-checkpoint comparison range: `v2026.5.21.5..v0.1.0-alpha.2`, 68 PRs.
- Post-tag correction and installer-continuation PRs: #324, #325, #326, #327, #335, #336, and #337.
- Note: the tag was not moved. Post-tag PRs describe current `main` continuation and corrected release guidance.

## v0.1.0-alpha.1 Public Demo Slice

- GitHub pre-release target: `v0.1.0-alpha.1`.
- Public release body: `docs/releases/0.1.0-alpha.1.md`
- YonerAI CLI: `yonerai demo --pretty`, `yonerai demo --json`, and `yonerai quickstart`.
- Demo Experience: public Core health/mock/run contract, mode boundary, route preview, test-only Hybrid Local Node trust/session simulator, managed download guard, and proposal-only self-evolution.
- Large-codebase connections: managed download guard and Hybrid memory quarantine fixture.
- Security/runtime patch: embed image URL SSRF guard for Discord vision handling.
- Boundary: Official Managed Cloud remains external contract-only in this public repo; no production Oracle, production trust store, live Discord, persistent memory, Google login, deploy, or external provider live generation is included.
- Validation target: stable JSON contract `yonerai-public-demo/v1` with `schema_version: "1.0"`, public demo/CLI/public smoke tests, version/release workflow tests, SSRF regression tests, secret/local path scan, and mojibake/hidden Unicode scan.
- Traceability: PRs #292, #293, #294, #295, and #296.

## v2026.5.21.5 Implementation Continuation Checkpoint

- Public checkpoint note: `docs/releases/v2026.5.21.5-implementation-continuation-checkpoint.md`
- GitHub Release target: `v2026.5.21.5` after this alignment PR lands and the release is created.
- Scope: layer image upload security/runtime hardening, first behavior-preserving `src/cogs/ora.py` pure-helper extraction, ORA/YonerAI naming compatibility policy, and three-mode docs-only capability acceptance harness extension.
- Status: implementation continuation checkpoint, not production, not deploy, not Discord restoration, not `src/cogs/ora.py` resolution, not broad ORA rename, and not a v7.8 start.
- Still open: remaining security/runtime PRs, dependency PR lane decisions, root launcher/config migration, live/private Discord gateway implementation, README_JP broader mojibake restoration, and future `src/cogs/ora.py` extraction.

## v2026.5.21.4 Implementation Guardrail Compression Checkpoint

- Public checkpoint note: `docs/releases/v2026.5.21.4-implementation-guardrail-compression-checkpoint.md`
- GitHub Release target: `v2026.5.21.4` after this alignment PR lands and the release is created.
- Scope: `/say` security/runtime patch, Discord hybrid contract acceptance tests, three-mode capability harness, `src/cogs/ora.py` extraction plan, and ORA pure-helper contract tests.
- Status: implementation-first v7.7 checkpoint, not production, not deploy, not Discord restoration, not `src/cogs/ora.py` resolution, and not a v7.8 start.
- Still open: remaining security/runtime PRs, dependency PR lane decisions, root launcher/config migration, live/private Discord gateway implementation, README_JP broader mojibake restoration, and future `src/cogs/ora.py` extraction.

## v2026.5.21.2 Final Public Presentation Checkpoint

- Public checkpoint note: `docs/releases/v2026.5.21.2-final-public-presentation-checkpoint.md`
- GitHub Release target: `v2026.5.21.2` after this alignment PR lands.
- Scope: v7.7 evidence ledger, v7.8 readiness decision, `SECURITY.md`, and PR template presentation hardening.
- Status: public repository presentation addendum, not production, not deploy, not full product completion, and not a v7.8 start.
- Still open: remaining security/runtime PR reproduction, dependency PR lane decisions, root launcher/config migration, README_JP broader UTF-8 presentation review, and future `src/cogs/ora.py` extraction.

## v2026.5.21.3 Clean Continuation Security and Discord Preflight Checkpoint

- Public checkpoint note: `docs/releases/v2026.5.21.3-clean-continuation-security-discord-preflight-checkpoint.md`
- GitHub Release target: `v2026.5.21.3` after this alignment PR lands and the release is created.
- Scope: dirty-worktree rescue traceability, `/listen` owner/admin boundary restoration, and Discord Hybrid/Self-Host signed-contract preflight fixtures.
- Status: clean-continuation checkpoint, not production, not deploy, not Discord gateway completion, and not a v7.8 start.
- Still open: remaining stale security/runtime PRs, dependency PR lane decisions, root launcher/config migration, live/private Discord gateway implementation, and future `src/cogs/ora.py` extraction.

## v2026.5.21.1 Public Repository Hardening Checkpoint

- Public checkpoint note: `docs/releases/v2026.5.21.1-public-repository-hardening-checkpoint.md`
- GitHub Release target: `v2026.5.21.1` after this alignment PR lands.
- Scope: public GitHub state ledger, file-to-PR traceability, large-codebase integration map, local LLM public access hardening, dependency lane triage, root physical cleanup decision, and release alignment.
- Status: public repository hardening checkpoint, not production, not deploy, not full product completion, and not a v7.8 start.
- Still open: remaining security/runtime PR reproduction, dependency PR lane decisions, root launcher/config migration, README_JP UTF-8 restoration, v7.7 evidence ledger, and future `src/cogs/ora.py` extraction.

## v2026.5.20.14 Tools/MCP Safe Subset Contract Checkpoint

- Public checkpoint note: `docs/releases/v2026.5.20.14-tools-mcp-safe-subset-contract-checkpoint.md`
- Scope: public-safe Tools/MCP subset contract, disabled-by-default requirements, approval/audit boundaries, and contract tests.
- Status: public contract checkpoint, not runtime Tools/MCP completion, not production, and not deploy.
- Style: follows `docs/repo/RELEASE_NOTE_STYLE_GUIDE.md`.
- Still open: safe tool decision fixture, remaining security PR backlog review, agent swarm releaseability, and `src/cogs/ora.py` extraction lane.

## v2026.5.20.13 Capability / Extension Boundary Checkpoint

- Public checkpoint note: `docs/releases/v2026.5.20.13-capability-extension-boundary-checkpoint.md`
- Scope: code-level public capability manifest, unknown-capability deny-by-default tests, and capability boundary contract.
- Status: public boundary hardening checkpoint, not production, not deploy, and not tools/MCP completion.
- Still open: safe tool decision fixture, security PR backlog resolution, agent swarm releaseability, and `src/cogs/ora.py` extraction lane.

## v2026.5.20.12 Local LLM Error Reporting Hardening Checkpoint

- Public checkpoint note: `docs/releases/v2026.5.20.12-local-llm-error-reporting-hardening-checkpoint.md`
- Scope: safe local LLM error metadata for public messages, Surface API runs, and local smoke CLI output.
- Status: public local-provider hardening checkpoint, not production, not deploy, and not provider ecosystem completion.
- Still open: tools/MCP safe subset contract, security PR backlog resolution, and local model listing.

## v2026.5.20.11 Growth/SNS Claim Guardrails Checkpoint

- Public checkpoint note: `docs/releases/v2026.5.20.11-growth-sns-claim-guardrails-checkpoint.md`
- Scope: claim-guarded demo plan, public FAQ, and SNS/release/README wording guardrails for the v7.7 public surface ladder.
- Status: public distribution-documentation checkpoint, not production, not deploy, and not a launch-complete claim.
- Still open: approved public assets, capability/extension boundary hardening, final Web UI decision, and broader old PR review.

## v2026.5.20.10 Web Surface Capability Manifest Checkpoint

- Public checkpoint note: `docs/releases/v2026.5.20.10-web-surface-capability-manifest-checkpoint.md`
- Scope: Web surface capability manifest and same-experience ledger alignment for the temporary `clients/web` smoke-demo surface.
- Status: public Web contract checkpoint, not final Web UI, not production, and not deploy.
- Still open: Web manifest display fixture, final Web UI decision, and old web dependency PR refresh.

## v2026.5.20.9 Native Japanese CLI Contract Checkpoint

- Public checkpoint note: `docs/releases/v2026.5.20.9-native-japanese-cli-contract-checkpoint.md`
- Scope: native Japanese CLI UX contract for intent mapping, ambiguity handling, dry-run, approval binding, capability allowlist, and audit event shape.
- Status: public contract checkpoint, not an implementation, not final CLI, not production, and not deploy.
- Still open: parser fixtures, dry-run tests, Web capability manifest, Growth/SNS claim guardrails, and final package decision.

## v2026.5.20.8 Surface CLI Smoke Checkpoint

- Public checkpoint note: `docs/releases/v2026.5.20.8-surface-cli-smoke-checkpoint.md`
- Scope: temporary local smoke CLI under `clients/cli` for health, public message, and Surface API run checks against loopback Core.
- Status: public CLI smoke checkpoint, not final CLI, not native Japanese CLI, not production, and not deploy.
- Still open: native Japanese CLI contract, Web capability manifest, Growth/SNS claim guardrails, final packaging/signing, and broader old PR review.

## v2026.5.20.7 Surface API Run Contract Checkpoint

- Public checkpoint note: `docs/releases/v2026.5.20.7-surface-api-run-contract-checkpoint.md`
- Scope: public Core Surface API 0.1 run contract, in-memory run events/results, and a fresh narrow #142 access-gate fix for current main.
- Status: public API surface checkpoint, not production and not official-cloud completion.
- Still open: CLI smoke client, native Japanese CLI contract, Web capability manifest, Growth/SNS claim guardrails, and broader old security PR review.

## v2026.5.20.6 Hybrid Envelope Policy Semantics Checkpoint

- Public checkpoint note: `docs/releases/v2026.5.20.6-hybrid-envelope-policy-semantics-checkpoint.md`
- Scope: post-merge hybrid policy semantics fix so memory-candidate and improvement-proposal policy checks cannot be bypassed by spoofing `data_class` or mixing inconsistent semantic fields.
- Status: public policy/correctness checkpoint, not production and not a full hybrid connector.
- Still open: production key lifecycle, durable replay protection, root helper retirement, persistent memory decision, and future `src/cogs/ora.py` extraction.

## v2026.5.20.5 Public Surface and Release Hygiene Checkpoint

- Public checkpoint note: `docs/releases/v2026.5.20.5-public-surface-release-hygiene-checkpoint.md`
- Scope: public README/checkpoint hygiene, same-day release suffix policy, root surface policy/inventory updates, PR-number presentation policy, and zero-trust practicality matrix.
- Status: public surface checkpoint, not production and not a deploy.
- Still open: older future-dated release metadata correction decision, safe root helper movement lane, provider boundary hardening, local LLM error UX, memory policy, and future `src/cogs/ora.py` extraction.

## v2026.5.20.4 Hybrid Connector Fixture and Memory Policy Checkpoint

- Public checkpoint note: `docs/releases/v2026.5.20.4-hybrid-connector-fixture-memory-policy-checkpoint.md`
- Scope: synthetic Hybrid Connector Fixture, memory candidate quarantine policy scaffold, public fixture helpers, and capability priority map.
- Status: hybrid fixture checkpoint, not production and not a full hybrid connector.
- Still open: real private connector implementation, production signing/key lifecycle, durable replay protection, approval workflow UI, persistent memory decision, and capability/extension boundary hardening.

## v2026.5.20.3 Hybrid Signed Envelope Donation Policy Checkpoint

- Public checkpoint note: `docs/releases/v2026.5.20.3-hybrid-signed-envelope-donation-policy-checkpoint.md`
- Scope: public-safe Hybrid Signed Envelope contract, donation quarantine policy, schema helpers, and tests proving signed donated payloads are not trusted automatically.
- Status: hybrid contract checkpoint, not a production release and not a full hybrid connector.
- Still open: private/local signing fixture, production-grade key lifecycle design, durable replay store, owner approval UI contract, persistent memory decision, and official control-plane deployment-free ingress review.

## Historical Future-Dated Labels Requiring Correction

These entries are kept for traceability. Some labels were future-dated relative to the verified 2026-05-20 cleanup date, and one `v2026.5.22` markdown note remains future-dated relative to 2026-05-21. They should not be used as the current public latest checkpoint.

## v2026.5.22 Web Chat MVP Review-gate Checkpoint

- Public checkpoint note: `docs/releases/v2026.5.22-web-chat-mvp-review-gate-checkpoint.md`
- Scope: clarify `clients/web` as a temporary Web Chat MVP, add mock/local provider controls, improve safe Core API error display, and fix the remaining observed `clients/web` `postcss` advisory locally.
- Status: public temporary Web Chat MVP checkpoint, not a production release.
- Still open: GitHub Dependabot rescan after merge, final Web product UI, Google login, persistent memory, Discord gateway completion, old security PR review, safe branch/worktree cleanup, model listing, local LLM error UX, and future `src/cogs/ora.py` extraction.

Note: this historical markdown note remains future-dated relative to the verified 2026-05-21 repository state. It should not be treated as the current public latest checkpoint.

## v2026.5.21 ora-ui Retirement and Security Backlog Cleanup Checkpoint

- Public checkpoint note: `docs/releases/v2026.5.21-ora-ui-retirement-security-cleanup-checkpoint.md`
- Scope: retire obsolete `ora-ui`, remove its dependency manifest from the active public surface, and update security/backlog triage.
- Status: public maintenance checkpoint, not a production release.
- Still open: remaining `clients/web` dependency alert until the later web checkpoint reaches main and GitHub rescans, non-`ora-ui` Dependabot PRs, old security PR review, safe branch/worktree cleanup, model listing, local LLM error UX, and future `src/cogs/ora.py` extraction.

Note: this historical markdown note was future-dated during the 2026-05-20 cleanup pass and is retained for traceability. It should not be treated as the current public latest checkpoint unless a later release-hygiene pass explicitly supersedes it.

## v2026.5.21 Local LLM Provider Compatibility Checkpoint

- Public checkpoint note: `docs/releases/v2026.5.21-local-llm-provider-compatibility-checkpoint.md`
- Scope: provider-neutral local LLM compatibility for Ollama-style `/api/chat` and OpenAI-compatible local `/v1/chat/completions` servers.
- Status: public local provider compatibility checkpoint, not a production release.
- Still open: optional loopback-only model listing endpoint, final Web product UI, Google login, persistent memory, Discord gateway completion, non-loopback/private provider lanes, and future `src/cogs/ora.py` extraction.

Note: the GitHub Release/tag exists and was future-dated during the 2026-05-20 cleanup pass. Do not delete or retag it without explicit owner approval; use a corrected current-date release for latest visibility when safe.

## Same-Day 2026-05-20 Checkpoint History

## v2026.5.20.2 Conversation Session Scaffold Checkpoint

- Public checkpoint note: `docs/releases/v2026.5.20.2-conversation-session-scaffold-checkpoint.md`
- Scope: public Core API conversation session metadata, feature inventory, and releaseability map.
- Status: public conversation session scaffold checkpoint, not a production release and not persistent memory.
- Still open: memory policy scaffold, identity/login, cross-device history, official cloud runtime, stale dashboard/login route isolation, and future `src/cogs/ora.py` extraction.

## v2026.5.20.1 Official Cloud Control Plane MVP Planning Checkpoint

- Public checkpoint note: `docs/releases/v2026.5.20.1-official-cloud-control-plane-mvp-planning-checkpoint.md`
- Scope: cross-repo same-experience matrix, Official Cloud Control Plane MVP contract, and official self-evolution proposal queue boundary.
- Status: public-safe planning checkpoint, not a production release and not a claim that official cloud is complete.
- Still open: control-plane skeleton PR review, private runtime clean-baseline decision, hybrid private result-envelope contract, memory policy scaffold, owner approval UI contract, and deployment-free official control-plane tests.

## v2026.5.20 Local LLM Conversation MVP Checkpoint

- Public checkpoint note: `docs/releases/v2026.5.20-local-llm-conversation-mvp-checkpoint.md`
- GitHub Release: `v2026.5.20` normal visible checkpoint
- Scope: loopback-only local LLM adapter, `POST /v1/public/messages` local mode, Dependabot triage refresh, and open PR backlog gate.
- Status: public Local LLM conversation MVP checkpoint, not a production release.
- Still open: final Web product UI, Google login, persistent memory, Discord gateway completion, `ora-ui` dependency remediation, non-loopback/private provider lanes, and future `src/cogs/ora.py` extraction.

## v2026.5.20 Web UI Mock-chat Security Checkpoint

- Public checkpoint note: `docs/releases/v2026.5.20-web-ui-mock-chat-security-checkpoint.md`
- Scope: Dependabot triage, public message API follow-up hardening, `clients/web` dependency cleanup, and a local mock/offline Web UI surface.
- Status: public Web UI mock-chat checkpoint, not a production release.
- Still open: live provider generation, Google login, persistent memory, Discord gateway completion, `ora-ui` dependency remediation, and future `src/cogs/ora.py` extraction.

## v2026.5.20 Public Core Message MVP Checkpoint

- Public checkpoint note: `docs/releases/v2026.5.20-public-core-message-mvp-checkpoint.md`
- Scope: credential-free local Core API mock/offline message contract plus refactor Step 0.1 static analyzer hardening.
- Status: public core message MVP checkpoint, not a production release.
- Still open: Web UI chat, provider adapter boundary, memory persistence, Google login, Discord gateway completion, web search, official cloud, and future `src/cogs/ora.py` extraction.

## v2026.5.19 `ora.py` Import Map Checkpoint

- Public checkpoint note: `docs/releases/v2026.5.19-ora-py-import-map-checkpoint.md`
- Scope: static import map tooling and facade contract tests for `src/cogs/ora.py`.
- Status: refactor Step 0 checkpoint, not a production release.
- Still open: implementation extraction, rename, runtime split, private/control-plane ownership, and behavior-preservation tests for later PRs.

## v2026.5.19 Self-Evolution Proposal-only Checkpoint

- Public checkpoint note: `docs/releases/v2026.5.19-self-evolution-proposal-only-checkpoint.md`
- Scope: synthetic fixture signal normalization, proposal scoring, owner-reviewable Markdown proposal packets, and approval-gate tests.
- Status: public-safe proposal-only MVP checkpoint, not a production release.
- Still open: real telemetry remains out of scope, SNS scraping remains out of scope, and execution lanes require owner approval.

## v2026.5.19 Branch Hygiene and Refactor Readiness Checkpoint

- Public checkpoint note: `docs/releases/v2026.5.19-branch-hygiene-refactor-readiness-checkpoint.md`
- Scope: branch / PR / worktree hygiene inventory plus `src/cogs/ora.py` decomposition planning.
- Status: maintenance checkpoint, not a production release.
- Still open: PR #169 review fixes, dedicated worktree cleanup, dedicated remote branch deletion, dependency-security triage, and future `src/cogs/ora.py` implementation.

## v2026.5.19 Public Runnable MVP Checkpoint

- Public checkpoint note: `docs/releases/v2026.5.19-public-runnable-mvp-checkpoint.md`
- GitHub Release: `v2026.5.19` prerelease checkpoint
- Scope: PR #163 boundary-plan closure plus a credential-free local Core API smoke path for fresh public checkouts.
- Status: public runnable MVP checkpoint, not a production release.
- Still open: broader runtime hardcoded path cleanup, deployment/control-plane docs, optional history remediation decision, dependency-security lane, and future `src/cogs/ora.py` implementation.

## v2026.5.18 Public Progress Checkpoint

- Public checkpoint note: `docs/releases/v2026.5.18-public-progress-checkpoint.md`
- Scope: v7.7 source-of-truth alignment, public GitHub hygiene cleanup, self-evolution product intelligence specification, and PR #165 public README/root-surface/release-note cleanup.
- Status: public progress checkpoint, not a production release.
- Still open: PR #163 boundary plan, runtime/tooling hardcoded path cleanup, optional history remediation decision, and dependency-security lane.

## v2026.4.28 Public Progress Checkpoint

- Public checkpoint note: `docs/releases/v2026.4.28-public-progress-checkpoint.md`
- Scope: post-PR #153 / #154 / #155 public progress record and reasoning-summary exactness guardrails for delivered public-core scope.
- Status: public progress checkpoint, not a production release.
- Still open: Pass 2 remains stopped / not landed, and `src/cogs/ora.py` remains unresolved boundary residue.

## Older Date-Version Notes

Older release note files remain under `docs/releases/` for historical reference.

They are not production-readiness claims, and they should not be read as current private runtime, live operations, or control-plane truth.

Current status and boundary truth should be checked against:

- `docs/CURRENT_PHASE_CONTEXT.md`
- `docs/TRACEABILITY_MATRIX_0_19.md`
- `docs/releases/v2026.5.20.14-tools-mcp-safe-subset-contract-checkpoint.md`
- `docs/repo/RELEASE_NOTE_STYLE_GUIDE.md`
