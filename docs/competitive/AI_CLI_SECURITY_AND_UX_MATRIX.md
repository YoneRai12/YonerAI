# AI CLI Security And UX Matrix

Date checked: 2026-05-26

This matrix records current public behavior from primary vendor sources and converts it into concrete YonerAI v0.2 CLI/runtime work. It is not a claim that YonerAI has parity with these tools.

## Sources

- OpenAI Codex CLI README: <https://github.com/openai/codex/blob/main/README.md>
- OpenAI, "Running Codex safely": <https://openai.com/index/running-codex-safely/>
- Anthropic Claude Code security: <https://code.claude.com/docs/en/security>
- Anthropic Claude Code permissions: <https://code.claude.com/docs/en/permissions>
- Google Gemini CLI docs: <https://google-gemini.github.io/gemini-cli/docs/>
- Google Gemini CLI sandbox docs: <https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/sandbox.md>
- Google Gemini CLI file-system tools docs: <https://google-gemini.github.io/gemini-cli/docs/tools/file-system.html>
- xAI Grok Build announcement: <https://x.ai/news/grok-build-cli>
- xAI Grok Build getting started: <https://docs.x.ai/build/overview>

## Comparison

| Area | Codex CLI | Claude Code | Gemini CLI | Grok Build | YonerAI v0.2 direction |
| --- | --- | --- | --- | --- | --- |
| Install/start UX | `codex` starts a local coding agent after install; README separates CLI, desktop app, and Codex Web. | Terminal agent with conservative default permissions. | REPL-style terminal client backed by local core package. | Early beta terminal coding agent; official docs show one-line install scripts. | Add a plain `yonerai providers`, improve `yonerai ask --auto --pretty --lang ja`, and keep install/update dry-run only. |
| Provider/model selection | ChatGPT sign-in recommended; API key path exists with additional setup. | Anthropic API provider first. | Gemini auth/config drives the model path. | xAI account/API-key oriented. | Show mock/local/OpenAI-compatible/Anthropic/Gemini readiness without requiring keys. Live external calls remain explicit. |
| Tool execution policy | Sandbox and approval policy are separate controls; rules allow benign commands while forcing review or blocking risky patterns. | Read-only default; edits, tests, and shell commands request permission. | Tool system includes filesystem, shell, web fetch, search, and MCP tools. Sandbox expansion asks before broader access. | Public docs emphasize plan/review/approve and diffs; detailed public tool policy was not found. | Do not add arbitrary shell/file/tool execution. Keep SafeShell diagnostic planning and deny/approval states visible in routing. |
| Web/search policy | Network boundary is part of sandbox configuration and approval policy. | Network-requesting tools require approval by default. | Web fetch/search tools exist under CLI tool management. | Public docs do not provide enough detail for a security model. | Mock search by default; live search remains opt-in and non-default. |
| Local file policy | Sandbox determines writable roots and protected paths. | Writes are confined to the started folder/subfolders unless explicitly allowed; reads may go wider depending on permission configuration. | File-system tools operate within a `rootDirectory` for security. | Public docs emphasize repo context but not a detailed file policy. | Workspace File Access Guard: only explicit selected files under allowlisted workspace; no folder crawl, arbitrary read, PDF/image parsing, or real summarization claim. |
| Auth/secret handling | Enterprise examples mention OS keyring, ChatGPT sign-in, and policy-controlled telemetry/logging. | User controls permissions; docs warn about trust and prompt injection. | Auth/config docs plus telemetry configuration; sandbox state appears in telemetry fields. | Official docs show API key env setup. | Provider reports redact env status, never print keys, and tests assert key-output non-actions. |
| Sandbox/approval | Codex treats sandbox and approvals as complementary controls. | Permissions and sandboxing are complementary; hooks can deny/prompt before tool calls. | Sandbox expansion is a specific request/approval flow for extra filesystem/network permission. | Public docs show plan approval and clean diffs, but not full sandbox policy. | Route preview and ask auto expose approval-required/deny states; risky route comments from #414/#417/#398/#419 are hardened before release. |
| Telemetry/privacy | OpenTelemetry export can include prompts, tool approvals, tool results, MCP use, and network policy decisions when configured. | Trust verification and prompt-injection guidance are documented. | Telemetry is configurable and documented. | Public docs do not provide enough detail for telemetry handling. | No telemetry ingestion in public repo. Ledger is opt-in, redacted, local-only, and does not store raw prompt/completion/provider keys. |
| Release-note style | README is short, install-first, and separates surfaces. | Security pages explain defaults and user responsibility. | Docs are operational and tool-specific. | Announcement is product/press style; docs provide quick install. | v0.2 release notes should be operation-manual style: commands, what happens, what does not happen, and full traceability. |

## Implemented YonerAI Improvements In This Lane

- Added `yonerai providers` to show provider readiness and safe setup guidance for mock, local LLM, OpenAI-compatible, Anthropic, and Gemini.
- Improved `yonerai ask --auto --pretty --lang ja` so non-engineers can see route, privacy, approval state, selected provider, ledger status, and non-actions without reading internal JSON.
- Improved `yonerai runs list/show --pretty --lang ja` to explain local ledger opt-in instead of showing an empty technical surface.
- Hardened route preview so snake_case `dangerous_operation` risk hints remain denied/approval-required.
- Hardened self-host public reasoning so it stays local-preferred instead of falling into a disabled cloud-oriented preview.
- Hardened extension manifest audit flags so string values such as `"false"` and `"0"` fail closed instead of being coerced to true.
- Hardened cloud-contract auto routing to build route metadata from the actual task plus an explicit public-reasoning hint instead of a fixed fixture phrase.
- Hardened Oracle queue CLI so `YONERAI_RUN_LEDGER_PATH` is respected without requiring duplicate `--ledger`.
- Hardened Hybrid pretty output so `relay_loopback_only=false` is displayed as failure, not OK.

## YonerAI Non-Claims

- No production Oracle or official managed cloud runtime is implemented in the public repo.
- No production signing key, production trust store, deployment, public tunnel, live Discord token path, Google login, or production DB behavior is added.
- No arbitrary shell execution, arbitrary file read, or remote installer execution is added.
- External providers are not live by default and require explicit `--live` plus provider-specific environment opt-in.
- Local LLM execution remains loopback-only.
