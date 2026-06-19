# YonerAI v7.8 Delta Draft

Status: current-truth delta draft after YonerAI CLI Local Runtime v0.5.0. This
document does not declare v7.8 complete and does not claim full YonerAI
production readiness.

## Source truth

The current design anchor remains v7.7:

- provider independence;
- same user-facing experience across official, local, and self-hosted
  directions;
- public/private/control-plane separation by contract;
- approval-gated self-evolution product intelligence;
- dangerous capabilities deny-by-default.

The previous explicit decision was `docs/design/V7_8_READINESS_DECISION_2026_05_21.md`,
which said v7.8 was not ready. The implementation evidence since then is now
large enough to draft a v7.8 delta, but not enough to replace every v7.7
contract or claim full production readiness.

## Implementation-backed deltas

| Design intent | Implemented evidence | Remaining gap | Next action |
| --- | --- | --- | --- |
| Make YonerAI usable as a local CLI runtime, not only as contracts and demos. | v0.5.0 release, `yonerai` console entrypoint, install-like test, README ZIP start guide. | Stable packaging is local/editable install from a ZIP or checkout, not a production installer. | Keep CLI Local Runtime stable while adding verified installer bootstrap work separately. |
| Provide a non-engineer Mission Control CLI. | Interactive `yonerai` / `yonerai chat`, first-run language selection, Japanese-first slash commands, settings, provider, safety, runs, tasks, agents. | No full-screen TUI dependency; numbered/menu fallback remains the safe default. | Add richer TUI only if dependency and fallback policy stay safe. |
| Preserve provider independence with useful local status. | `yonerai providers`, mock default provider, loopback-only local LLM guidance, OpenAI-compatible/Anthropic/Gemini readiness without default live calls. | External live providers still require explicit env opt-in and are not default CI paths. | Continue provider capability negotiation without storing or printing keys. |
| Route work by difficulty, privacy, and safety. | `yonerai ask --auto` route decisions, local/mock execution, cloud-contract candidate visibility, deny/approval-required paths. | Cloud-contract/Oracle behavior is still local-dev/stub, not production Oracle. | Keep private/local-file content local and expand route tests before adding any live lane. |
| Show task progress and reviewer/subagent plan. | Task timeline steps and deterministic planner/researcher/reviewer/implementer/tester plan in CLI/ledger output. | Plans are visible and deterministic; they do not run uncontrolled autonomous subagents. | Add real subagent execution only behind approval, provider capability checks, and audit. |
| Make run history inspectable without leaking secrets. | Redacted local run ledger list/show paths, provider/route/progress summaries, no raw chain-of-thought. | Ledger is explicit local-only; not cloud memory or complete persistent memory. | Keep redaction tests and add search/list improvements without cloud-sync claims. |
| Keep Hybrid/Oracle visible but public-safe. | Hybrid Wire/Local Node local-dev fixture, Oracle stub request/result envelope, route preview and demo/doctor/status output. | No production Oracle/control-plane or Official Managed Cloud runtime in public repo. | Keep official/private lane separate; public repo remains contract/dev-simulator only. |
| Move installer work from issue text to executable dry-run checks. | `yonerai manifest verify`, `yonerai install plan`, `yonerai update plan`, non-production/test trust fixture, v0.5.0 manifest. | No production signing key/trust store, no network installer, no npm/winget channel. | Add manifest-to-release-asset consistency checks and signed official manifest lane later. |
| Correct public distribution and legal posture. | PolyForm Noncommercial code license policy, CC BY-NC-ND docs/assets policy, brand reserved, v0.5.0 install content foundation. | Commercial license process/contact is still a placeholder owner channel. | Publish a dedicated commercial licensing contact and production brand-use policy when ready. |

## Current public claims allowed

- YonerAI CLI Local Runtime v0.5.0 is stable for the local CLI runtime slice.
- Users can download the v0.5.0 release ZIP, install the CLI into a local
  virtual environment, and run `yonerai`.
- Mission Control CLI exists with Japanese-first settings/safety/history/task
  visibility.
- Mock provider works by default without keys.
- Local LLM guidance and execution are loopback-only and opt-in.
- External provider live calls are explicit opt-in only.
- Hybrid/Oracle behavior is local-dev/stub visibility only.
- Installer work is manifest-verify / install-plan / update-plan dry-run only.
- The public repository is source-available/noncommercial, not OSI open source.

## Non-claims that remain

- No full YonerAI production readiness.
- No production Oracle/control-plane runtime.
- No Official Managed Cloud runtime in the public repo.
- No live Discord restoration.
- No production installer.
- No `irm ... | iex` ready-to-run flow.
- No production signing keys or production trust stores.
- No npm or winget distribution.
- No arbitrary shell/file/tool execution.
- No complete persistent memory.
- No Google login or production DB behavior.
- No claim that `src/cogs/ora.py` is solved.

## Recommended next v7.8 gate

The next v7.8 gate should require:

1. manifest-to-release-asset hash/name consistency checks with no live install;
2. signed manifest verification against a non-production test trust fixture for
   the current release manifest;
3. a dedicated public install page deployment plan for `yonerai.com/install`;
4. a production/private signing and trust-source design that remains outside
   the public repo;
5. continued CLI runtime regression tests around Japanese-first Mission Control,
   provider selection, safety, task progress, and redacted run history.
