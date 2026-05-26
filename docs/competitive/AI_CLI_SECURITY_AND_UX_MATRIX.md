# AI CLI Security And UX Matrix

Date checked: 2026-05-26

This matrix records current public behavior from primary vendor sources and converts it into concrete YonerAI CLI Local Runtime work. It is not a parity claim and it is not a production-cloud claim.

## Primary Sources

- OpenAI Codex CLI README: <https://github.com/openai/codex/blob/main/README.md>
- OpenAI, "Running Codex safely": <https://openai.com/index/running-codex-safely/>
- OpenAI, "Building a safe, effective sandbox to enable Codex on Windows": <https://openai.com/index/building-codex-windows-sandbox/>
- Anthropic Claude Code security: <https://code.claude.com/docs/en/security>
- Anthropic Claude Code permissions: <https://code.claude.com/docs/en/permissions>
- Anthropic Claude Code sandboxing: <https://code.claude.com/docs/en/sandboxing>
- Google Gemini CLI docs: <https://google-gemini.github.io/gemini-cli/docs/>
- Google Gemini CLI sandbox docs: <https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/sandbox.md>
- Google Gemini CLI file-system tools docs: <https://google-gemini.github.io/gemini-cli/docs/tools/file-system.html>
- xAI Grok Build announcement: <https://x.ai/news/grok-build-cli>
- xAI Grok Build overview: <https://docs.x.ai/build/overview>

## Comparison

| Area | Codex CLI | Claude Code | Gemini CLI | Grok Build | YonerAI v0.5 local-runtime decision |
| --- | --- | --- | --- | --- | --- |
| Install/start UX | `codex` starts a local coding agent; README separates CLI, desktop app, and cloud Codex. | Terminal coding agent with permission prompts and settings UI. | REPL-style terminal client backed by a local core package. | Early beta terminal coding agent with a plan/review/approve surface. | `yonerai` starts Mission Control CLI; `yonerai chat` remains alias; non-TTY falls back to command guidance. |
| Language/first run | English-first vendor UX. | English-first vendor UX. | English-first vendor UX. | English-first vendor UX. | Japanese-first first launch, with English slash aliases still accepted. Japanese mode avoids requiring English slash commands. |
| Provider/model selection | ChatGPT sign-in recommended; API key path exists with extra setup. | Anthropic provider first. | Gemini auth/config drives the model path. | xAI account/API-key oriented. | Mock is ready by default. Local LLM is loopback-only. OpenAI-compatible, Anthropic, and Gemini remain explicit live/env opt-in. |
| Settings surface | CLI config plus approval/sandbox flags. | `/permissions` and settings files expose allow/ask/deny rules. | Config files and command settings govern auth, tools, sandbox, telemetry. | Public launch page emphasizes plan mode and approval before edits. | `/設定` shows provider, local LLM state, approval, file access, ledger, live provider, and network status. `/選択` provides numbered fallback. |
| Task/progress UX | Agent shows actions and approval prompts. | Plans, tool calls, and permission prompts are visible. | REPL/tool flow exposes tool use and sandbox expansion requests. | Launch page highlights progress rows, plan review, and diff approval. | `/タスク` and chat responses show classify, route, provider selection, execution, review, and result states. |
| Subagent/reviewer visibility | Managed agent/review workflows are surfaced in Codex products. | Claude Code has Agent/subagent permission concepts. | Tool and extension model is explicit; autonomous subagents are not assumed. | Launch page shows multiple running plan items. | `/エージェント` displays planner/researcher/reviewer/implementer/tester plan only. It does not start uncontrolled agents. |
| Tool execution policy | Sandbox and approval policy are separate controls; high-risk actions require approval or are blocked. | Read-only default, explicit approvals, deny/ask/allow rules, fail-closed matching, network approval. | Tool system includes filesystem, shell, web fetch/search, and sandbox expansion request. | Public details are limited; launch page emphasizes plan/review/approve. | No arbitrary shell/file/tool execution. SafeShell remains diagnostic/dry-run only. Dangerous tasks route to approval_required or deny. |
| Web/search policy | Network boundary is part of sandbox and approval policy. | Network tools require approval by default. | Web fetch/search tools exist under tool management. | Public security detail is limited. | Network and live provider are off by default. Mock search remains default unless a separate live lane is explicitly enabled. |
| Local file policy | Sandbox controls writable roots and protected paths. | Writes stay within started folder/subfolders unless explicitly allowed; sensitive operations prompt. | File tools use a security root directory. | Public docs emphasize repo context. | Workspace File Access Guard only reads explicitly selected files inside the workspace allowlist. No folder crawl, arbitrary read, PDF/image parsing, or full summarization claim. |
| Auth/secret handling | Sign-in/API-key paths exist; safety articles emphasize governance, approval, and audit. | Secure credential storage and prompt-injection guidance are documented. | Auth/config and telemetry are documented. | API-key/account setup is vendor-managed. | Provider keys are never printed or stored in YonerAI config/ledger. Env presence is redacted. |
| Sandbox/approval | OpenAI distinguishes technical sandbox boundaries from approval policy. | Permissions and sandboxing are complementary; denial rules take precedence. | Sandbox expansion asks for broader filesystem/network access. | Plan approval is highlighted; detailed public sandbox policy was not found. | YonerAI displays sandbox-like boundaries separately from approval mode: network, file, shell, tools, live provider, and cloud escape. |
| Telemetry/privacy | Governance articles discuss audit and telemetry for managed use. | Monitoring and OpenTelemetry are documented. | Telemetry is documented and configurable. | Public detail is limited. | No telemetry ingestion in public repo. Ledger is opt-in, redacted, local-only, and does not store provider keys or raw chain-of-thought. |
| Release-note style | Install-first, surface-separated, operational docs. | Security pages explain defaults and user responsibility. | Tool-specific operational docs. | Product announcement plus quick install. | Release notes must be operation-manual style: commands, what happens, what does not happen, validation, traceability, and non-claims. |

## Concrete YonerAI Improvements Required By This Benchmark

- Keep `yonerai` as the default interactive entry point and `yonerai chat` as an alias.
- Keep first-run language selection persistent and secret-free.
- Keep Japanese mode useful without requiring English slash commands; English aliases remain accepted.
- Add visible task progress from the same `ask --auto` path used by scripted CLI.
- Add a provider/local LLM setup surface that explains loopback-only endpoints without storing secrets.
- Expose network/live provider state separately from approval state.
- Keep workspace file access named as an access guard, not a full summarizer.
- Keep subagents as plan/reviewer display only until a dedicated controlled execution lane exists.
- Keep all local ledgers opt-in, redacted, and local-only.
- Keep release/install wording scoped to "CLI Local Runtime", not full YonerAI cloud production.

## Implemented In The Current v0.5 Candidate Lane

- `/タスク` and `/tasks` show current/recent task progress and recent ledger-backed task summaries.
- `/ローカルLLM` and `/local-llm` show loopback-only setup guidance for Ollama-style and LM Studio/OpenAI-compatible local endpoints.
- `/ライブ接続`/`/live` and `/ネットワーク`/`/network` allow explicit local config toggles while preserving off-by-default behavior.
- `/設定` shows numbered rows for language, provider, approval, workspace file access, ledger, live provider, and network.
- Japanese mode continues to accept English aliases without printing English command names as the primary UI.

## YonerAI Non-Claims

- No production Oracle or official managed cloud runtime is implemented in the public repo.
- No production signing key, production trust store, deployment, public tunnel, live Discord token path, Google login, or production DB behavior is added.
- No arbitrary shell execution, arbitrary file read, remote installer execution, or hidden tool execution is added.
- External providers are not live by default and require explicit `--live` plus provider-specific environment opt-in.
- Local LLM execution remains loopback-only and must be explicitly enabled.
- Persistent memory is not complete; local ledger/history remains an opt-in redacted local feature.
