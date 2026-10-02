# YonerAI `src/cogs/ora.py` Import Map Step 0

Date: 2026-05-19

Status: refactor Step 0 checkpoint

Runtime behavior changed: no

## Open

`src/cogs/ora.py` remains the current compatibility module for the Discord-facing runtime residue. This checkpoint does not rename it and does not move runtime responsibilities.

The purpose of Step 0 is to pin the current static surface so later extraction PRs can prove they preserve behavior before moving code.

## Closed

- Added a static AST analyzer for `src/cogs/ora.py`.
- Added facade contract tests for the current `ORACog` surface.
- Added inbound reference tests for known direct `src.cogs.ora` users.
- Added a deterministic JSON output check for future import map comparisons.

## Current Facade Surface Pinned

The Step 0 tests pin these current `ORACog` methods:

- `handle_prompt`
- `get_context_tools`
- `_check_permission`
- `_get_tool_schemas`
- `_is_input_spam`
- `_perform_guardrail_check`
- `_process_attachments`
- `_process_embed_images`

The Step 0 tests also pin these constructor-assigned attributes:

- `bot`
- `tool_handler`
- `vision_handler`
- `chat_handler`
- `cost_manager`
- `safe_shell`
- `user_prefs`
- `soul_prompt`
- `unified_client`

## Current Inbound References

The static analyzer currently detects direct references from:

- `src/bot.py`
- `scripts/verify_startup.py`
- `scripts/verify_tool_integrity.py`
- `src/utils/health_inspector.py`

Handler, tool, skill, and cog consumers that reach `ORACog` through object references remain part of later extraction tests.

## Security and Hygiene

- The analyzer reads source files statically.
- It does not import `src.cogs.ora`.
- It does not login to Discord.
- It does not call model providers.
- It does not inspect private repositories.
- It does not run host-control or deployment code.

## Not Included

This checkpoint does not include:

- `src/cogs/ora.py` rename
- runtime responsibility moves
- behavior changes
- Discord gateway completion
- Web chat completion
- Google login completion
- memory synchronization completion
- official cloud completion
- deployment
- production readiness

## Next

The next extraction branch should be `refactor/ora-py-tool-catalog` or `refactor/ora-py-policy-boundary`, only after Step 0 tests are green on `main`.
