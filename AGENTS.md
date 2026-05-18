# AGENTS.md - YonerAI

<INSTRUCTIONS>
## Skills
A skill is a set of local instructions to follow that is stored in a `SKILL.md` file. Below is the list of skills that can be used. Each entry includes a name, description, and file path so you can open the source for full instructions when using a specific skill.
### Available skills
- skill-creator: Guide for creating effective skills. This skill should be used when users want to create a new skill (or update an existing skill) that extends Codex's capabilities with specialized knowledge, workflows, or tool integrations. (file: local Codex skill path; not a repository contract)
- skill-installer: Install Codex skills into $CODEX_HOME/skills from a curated list or a GitHub repo path. Use when a user asks to list installable skills, install a curated skill, or install a skill from another repo (including private repos). (file: local Codex skill path; not a repository contract)
### How to use skills
- Discovery: The list above is the skills available in this session (name + description + file path). Skill bodies live on disk at the listed paths.
- Trigger rules: If the user names a skill (with `$SkillName` or plain text) OR the task clearly matches a skill's description shown above, you must use that skill for that turn. Multiple mentions mean use them all. Do not carry skills across turns unless re-mentioned.
- Missing/blocked: If a named skill isn't in the list or the path can't be read, say so briefly and continue with the best fallback.
- How to use a skill (progressive disclosure):
  1) After deciding to use a skill, open its `SKILL.md`. Read only enough to follow the workflow.
  2) When `SKILL.md` references relative paths (e.g., `scripts/foo.py`), resolve them relative to the local skill directory first, and only consider other paths if needed.
  3) If `SKILL.md` points to extra folders such as `references/`, load only the specific files needed for the request; don't bulk-load everything.
  4) If `scripts/` exist, prefer running or patching them instead of retyping large code blocks.
  5) If `assets/` or templates exist, reuse them instead of recreating from scratch.
- Coordination and sequencing:
  - If multiple skills apply, choose the minimal set that covers the request and state the order you'll use them.
  - Announce which skill(s) you're using and why (one short line). If you skip an obvious skill, say why.
- Context hygiene:
  - Keep context small: summarize long sections instead of pasting them; only load extra files when needed.
  - Avoid deep reference-chasing: prefer opening only files directly linked from `SKILL.md` unless you're blocked.
  - When variants exist (frameworks, providers, domains), pick only the relevant reference file(s) and note that choice.
- Safety and fallback: If a skill can't be applied cleanly (missing files, unclear instructions), state the issue, pick the next-best approach, and continue.
</INSTRUCTIONS>

## Repo Notes
- YonerAI runtime skills live in `src/skills/<skill_name>/` (each has `SKILL.md` + `tool.py`). (internal code still uses many ORA names)
- MCP tool servers are configured via `.env` (`ORA_MCP_ENABLED`, `ORA_MCP_SERVERS_JSON`). See `README.md`.

## Durable Operating Guardrails

- Keep only durable rules in `AGENTS.md`; phase-specific truth belongs in `docs/CURRENT_PHASE_CONTEXT.md`.
- Rehydrate `docs/CURRENT_PHASE_CONTEXT.md`, the latest numeric `docs/TRACEABILITY_MATRIX_*.md`, and the latest numeric `docs/PLANNING_EXIT_SCORECARD_*.md` before making delivery or readiness claims.
- Do not invent missing exact truth. Use `unknown`, `GAP`, `UNRESOLVED`, or `TODO` instead of filling gaps by guesswork.
- Do not claim shipping-complete, production-ready, official-cloud complete, live-ops complete, or full product complete unless a later explicit release/readiness batch verifies that exact claim.
- Do not expose raw chain-of-thought in public chat, API, SSE, logs, docs, or trace surfaces. Only public-safe reasoning summaries may cross public surfaces.
- Never commit secrets, credentials, raw production inventory, live route maps, control-plane DDL, private renderer truth, operational ledgers, break-glass internals, or raw version-lock exports unless already intentionally versioned and explicitly approved.

## Repo Boundary Rules

- Canonical repositories are `YoneRai12/YonerAI`, `YoneRai12/YonerAI-private`, and `YoneRai12/YonerAI-oracle-control-plane`.
- `YonerAI-VPS-private` is not the all-in-one private repository. If present, treat it only as a possible seed for `YonerAI-oracle-control-plane`.
- Public artifacts must not directly import private internals.
- Cross-repo interaction must happen through contracts: API, event, files, auth claims, capability manifest, protocol, or schema.
- Oracle host, deploy, rollback, supervision, service-manager, cloudflared, and hook-specific control belongs in the control-plane lane, not in public contract artifacts.
- Public-safe self-evolution contracts may describe signals, scoring, privacy boundaries, and approval gates; they must not implement unapproved code mutation.

## Branch And Delivery Safety

- Dirty keep-set or quarantine branches must not be reset, cleaned, stashed, rebased, merged, deleted, or used as delivery sources without explicit owner approval.
- Use clean worktrees and lane-separated branches for delivery work when the active branch is dirty or mixed.
- Do not push, create PRs, create releases, tag, deploy, migrate, or broaden scope unless the current user request explicitly authorizes that exact action.
- `src/cogs/ora.py` is a sensitive private/runtime/control-plane boundary area; do not treat it as a narrow public patch target without a dedicated boundary-planning lane.
