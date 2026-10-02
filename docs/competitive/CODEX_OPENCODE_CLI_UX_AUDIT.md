# Codex / opencode CLI UX audit for YonerAI

Status: implementation audit for the YonerAI public CLI runtime after
`v0.16.0-alpha.1`.

This file is not a production-cloud claim. It records which interaction ideas are
safe for YonerAI public runtime and which are intentionally blocked.

## Sources checked

- OpenAI Codex CLI: <https://developers.openai.com/codex/cli>
- OpenAI Codex CLI slash-command manual snapshot, fetched with the local
  `openai-docs` skill from official OpenAI docs cache.
- OpenAI Codex approval/sandbox notes from the local Codex manual snapshot.
- opencode TUI: <https://opencode.ai/docs/tui/>
- opencode agents/permissions: <https://opencode.ai/docs/agents/>
- opencode modes: <https://opencode.ai/docs/modes/>

## Findings

| Area | Codex behavior | opencode behavior | YonerAI decision |
| --- | --- | --- | --- |
| Start UX | `codex` starts an interactive terminal UI. | `opencode` starts the TUI for the current directory. | Keep `yonerai` as the interactive Mission Control entry point and `yonerai chat` as alias. |
| Slash commands | `/` opens slash-command suggestions; Tab completes commands. | `/` commands include help, models, sessions, share, undo/redo, themes, thinking, connect. | Keep Japanese-first `/` commands and English aliases. Add category-based palette so non-engineers can scan commands without knowing names. |
| Provider/model selection | `/model` and model/provider flags are first-class. | `/connect` and `/models` are visible provider/model surfaces. | Keep `/モデル`, `/提供元`, local LLM loopback guidance, and external provider opt-in. Do not print or store provider keys. |
| Modes | Codex exposes planning/review/permissions workflows. | Build and Plan are built-in; custom modes can disable write/edit/bash. | Keep YonerAI modes: plan/read-only, build-safe, review, memory. Modes are public-safe UI and policy selectors, not uncontrolled execution. |
| Subagents | Codex exposes review and subagent workflows with explicit invocation. | Agents can have per-agent permissions and controlled task invocation. | Keep `@planner`, `@reviewer`, `@researcher` as preview-only public-safe subagent plans. No autonomous subagent execution in public runtime. |
| Approval/sandbox | Codex separates sandbox boundaries from approval policy. | opencode permissions can allow/ask/deny read/edit/bash/task/web tools. | Keep `/権限` and `/安全` separate. Public YonerAI denies arbitrary shell/file/tool execution and keeps network/live provider off by default. |
| Context selection | Codex supports references and attachments in controlled surfaces. | opencode uses `@` fuzzy file references and configured references. | Add `/コンテキスト` to explain safe references. Do not implement automatic `@file` body loading in this lane. Workspace file access stays explicit and guarded. |
| Shell command shortcut | Codex can run commands under sandbox/approval. | opencode supports `!` shell commands. | Do not adopt `!` shell execution. YonerAI public runtime has no arbitrary shell/tool execution. |
| Undo/redo/session mutation | Codex and opencode expose session/history tools. | opencode `/undo` and `/redo` use Git-backed changes. | Keep redacted run history. Do not add file-change undo/redo until YonerAI has a stronger execution/snapshot boundary. |
| Thinking display | Codex and opencode have richer progress/thinking displays. | opencode can toggle thinking display. | Show task-progress states and route/provider/run_id, but never raw chain-of-thought. |

## Concrete YonerAI changes in this lane

- Add category grouping to the command palette.
- Keep Japanese commands first and English aliases hidden-compatible.
- Add `/コンテキスト` and `/参照` aliases for safe context guidance.
- Make the palette show that context references are limited to public-safe
  subagent previews and explicit memory/run inspection.
- Keep shell, automatic file reference loading, cloud upload, production Oracle,
  and production auth out of scope.

## Non-claims

- No production Oracle/cloud runtime is added.
- No production Google login is added.
- No provider key storage is added.
- No OpenAI shared traffic is enabled.
- No arbitrary shell/file/tool execution is added.
- No automatic local private memory upload is added.
- No `src/cogs/ora.py` refactor is included.
