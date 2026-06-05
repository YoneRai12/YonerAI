# Codex / opencode Code-Level TUI Audit For YonerAI

Status: implementation audit for the public YonerAI CLI after PR #511.

This document records code-level findings from temporary read-only source
inspection. It does not vendor, copy, or relicense external code. YonerAI uses
the patterns only to shape its own public-safe CLI surfaces.

## Source State

| Project | Commit inspected | How it was inspected | Notes |
| --- | --- | --- | --- |
| OpenAI Codex CLI | `1d9c9c9f33735223cc564ec942001c9141a11eb1` | no-checkout temporary clone, `git show` / `git grep` against repository objects | No checkout was needed; files were read from Git objects to avoid Windows path issues. |
| opencode | `0a364330627e95aa723ff70959467ca62b13bf5b` | no-checkout temporary clone, `git show` / `git grep` | No files were copied into YonerAI. |

## Files Inspected

### Codex CLI

| Source file | Observed pattern | YonerAI translation |
| --- | --- | --- |
| `codex-rs/tui/src/app.rs` | TUI owns the event loop and routes protocol events into chat state, overlays, and file/search surfaces. | Keep `yonerai` as a thin interactive shell over `ask --auto`, not a separate runtime path. |
| `codex-rs/tui/src/chatwidget.rs` | Chat widget separates transcript/history cells from the active running turn. | YonerAI keeps chat output separate from `/進行` and redacted run history. |
| `codex-rs/tui/src/bottom_pane/chat_composer.rs` | Composer centralizes input editing, slash handling, file mentions, history navigation, and submit behavior. | Add a YonerAI `/入力` screen that explains the current composer contract and safe shortcuts without adding arbitrary file mentions. |
| `codex-rs/tui/src/bottom_pane/chat_composer/popup_state.rs` | Composer popups are stateful instead of ad hoc prints. | YonerAI keeps popup-like behavior in command metadata and explicit `/入力` guidance until a richer modal is proven on Windows. |
| `codex-rs/tui/src/bottom_pane/chat_composer/slash_input.rs` | Slash input is parsed separately from normal prompt text. | YonerAI keeps slash parsing in `tui/keymap.py` and `tui/aliases.py`, separate from `ask --auto` execution. |
| `codex-rs/tui/src/bottom_pane/command_popup.rs` | Slash suggestions are selectable, filtered, and scroll-aware. | Keep Japanese-first slash candidates and add category/search/paging guidance for terminals without reliable arrow UI. |
| `codex-rs/tui/src/bottom_pane/slash_commands.rs` | Commands are registered with metadata and feature gating. | Keep `tui/keymap.py` as the source of YonerAI command metadata and aliases. |
| `codex-rs/tui/src/bottom_pane/approval_overlay.rs` | Approval UI displays decisions; it does not replace policy evaluation. | Keep `/権限` and `/安全` separate from the runtime policy layer. |
| `codex-rs/tui/src/bottom_pane/bottom_pane_view.rs` | The bottom pane composes active views rather than dumping every setting at once. | YonerAI keeps settings/category screens separate and avoids adding a giant combined dump. |
| `codex-rs/tui/src/ascii_animation.rs` | Running state has a dedicated visual channel. | Add `/進行` for visible task phases while keeping raw chain-of-thought hidden. |
| `codex-rs/tui/src/bottom_pane/footer.rs` | Footer summarizes context and controls at compact width. | Keep YonerAI bottom toolbar concise: provider, model, mode, live, ledger. |
| `codex-rs/tui/src/bottom_pane/pending_input_preview.rs` | Pending input has its own preview surface. | YonerAI adds `/入力` for the input contract and keeps active ask output separate. |
| `codex-rs/tui/src/bottom_pane/mentions_v2/filter.rs` | Mentions use explicit candidate filtering. | YonerAI keeps `@planner`, `@reviewer`, `@researcher`, `@implementer`, and `@tester` as explicit preview-only roles. |
| `codex-rs/tui/src/keymap.rs` | Runtime keymap/default binding logic is isolated. | Keep aliases and completion in `tui/keymap.py` / `tui/aliases.py`, not embedded inside business logic. |
| `codex-rs/tui/src/bottom_pane/scroll_state.rs` | Scrolling is a reusable state object. | YonerAI documents paging and keeps numbered fallback until a richer scroll state is tested in PowerShell. |
| `codex-rs/tui/src/bottom_pane/list_selection_view.rs` | Selection lists can show side details and preserve navigation state. | YonerAI remains numbered fallback first; richer selection can be a later TUI dependency lane. |

### opencode

| Source file | Observed pattern | YonerAI translation |
| --- | --- | --- |
| `packages/opencode/src/index.ts` | CLI entrypoint routes to TUI, run, attach, provider, agent, and upgrade commands. | Keep `yonerai` and `yonerai chat` as interactive aliases while preserving scriptable subcommands. |
| `packages/opencode/src/cli/cmd/tui/thread.ts` | TUI startup resolves project context, connects to a worker/server, and handles platform terminal quirks. | YonerAI public CLI does not start production daemons; local node remains loopback/local-dev only. |
| `packages/opencode/src/cli/cmd/run.ts` | Non-interactive run path streams events and supports machine-readable output. | Keep `yonerai ask --auto` and JSON output as the scriptable path under the interactive UI. |
| `packages/opencode/src/cli/cmd/agent.ts` | Agent setup is explicit and permission-aware. | YonerAI keeps `@planner`, `@reviewer`, `@researcher`, `@implementer`, and `@tester` preview-only. |
| `packages/opencode/src/permission/index.ts` | Permission decisions are allow/deny/ask and pending approvals are explicitly tracked. | YonerAI public runtime remains deny-by-default for arbitrary shell/file/tool execution, with visible approval mode. |
| `packages/opencode/src/agent/agent.ts` | Agent schemas include mode and permission rules. | YonerAI agent modes stay simple policy selectors: plan/read-only, build-safe, review, memory. |
| `packages/opencode/src/agent/subagent-permissions.ts` | Subagent permissions are derived from parent constraints and deny rules are forwarded. | YonerAI does not run uncontrolled subagents; future execution must inherit public safety constraints. |
| `packages/opencode/src/command/index.ts` | Commands are first-class objects with metadata and hints. | YonerAI keeps command metadata centralized and exposes Japanese-first help. |
| `packages/opencode/src/acp/permission.ts` | ACP permission requests are routed through an explicit request/reply path. | YonerAI keeps approval/safety screens visible and avoids implicit tool execution. |
| `packages/opencode/src/cli/ui.ts` | CLI help/logo utilities are separate from command execution. | YonerAI keeps startup branding in `startup_home.py` and command handling in `interactive.py`. |
| `packages/opencode/src/cli/logo.ts` | Logo data is isolated from runtime logic. | YonerAI keeps the compact startup mark separate from chat execution. |
| `packages/opencode/src/cli/cmd/export.ts` | Export has a sanitizing path for session data. | YonerAI keeps `_safe()` redaction for local paths, control characters, and secret-like values in public output. |
| `packages/sdk/openapi.json` | TUI events include prompt append, command execution, toast, control, permission, and session events. | YonerAI can later expose a similar internal event contract, but public repo must not expose private runtime inventory. |
| `packages/ui/src/hooks/use-filtered-list.tsx` | Filtered lists are reusable and selected-row aware. | YonerAI uses grouped command metadata now; reusable selection state remains a future lane. |
| `packages/ui/src/hooks/create-auto-scroll.tsx` | Transcript UIs need explicit follow-bottom behavior. | YonerAI has not added scroll-follow behavior yet; this is a future richer TUI item. |

## Adopted YonerAI Changes

| UX area | Change | Boundary |
| --- | --- | --- |
| Home | Keep startup branding separate and compact when terminal width is limited. | No production cloud/auth claim is added to the home screen. |
| Home/composer | Add `/入力` / `/composer` screen for the input contract, shortcuts, and current provider/model/mode state. | It does not auto-read files, send prompts to live providers, or store keys. |
| Running/thinking | Add `/進行` / `/progress` screen with classify, route, provider selection, execute, review, result phases. | It never displays raw chain-of-thought. |
| Slash palette | Add `/入力` and `/進行` to command metadata and grouped palette output, with search/paging/numbered fallback guidance. | English aliases are accepted but Japanese remains primary in Japanese mode. |
| Agent modes | Extend safe mention previews to `@implementer` and `@tester`. | Mentions remain preview-only and do not start autonomous work. |
| Context panel | Extend `/コンテキスト` with allowed reference types and explicit non-auto-loaded boundaries. | No arbitrary `@file` loading, no private memory/cloud upload, no internal endpoint fetch. |

## Non-Adopted Patterns

- No `!` shell command shortcut.
- No automatic file mention body loading.
- No external URL fetch as implicit context.
- No production worker/server/daemon launch from the public CLI.
- No automatic live provider call.
- No production Oracle/cloud runtime.
- No production Google login.
- No local private memory auto-upload.

## Next Safe Lane

The next non-broad lane should keep `interactive.py` thin by extracting command
handlers into `commands/interactive_*` modules, then add characterization tests
for each handler before moving code. Richer arrow-key modal selection should wait
until prompt-toolkit behavior is proven on Windows PowerShell and non-TTY
fallback remains covered.
