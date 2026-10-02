# Rust Boundary Proposal

YonerAI CLI Local Runtime remains Python-first for v0.7.x. The current goal is to keep product behavior moving while separating high-risk native surfaces from policy and user-experience code.

## Stays Python

- CLI command orchestration and argparse compatibility.
- Japanese-first interactive screens and command palette behavior.
- Provider adapters, local LLM loopback checks, route preview, memory contracts, and run ledger integration.
- Policy report generation while provider/model/pricing/permission/runtime/update rules are still evolving.
- Public contract fixtures and conformance tests.

## Rust Candidates

Rust is a future boundary for small, testable surfaces where startup reliability, process isolation, and binary distribution matter more than iteration speed.

| Candidate | Why Rust May Help | Required Interface |
| --- | --- | --- |
| Launcher | Fast `yonerai` startup and Windows-friendly entry behavior. | Spawn Python CLI with sanitized argv/env and stable exit codes. |
| Updater / install verifier | Hash verification, archive checks, and fail-closed update planning. | JSON manifest in, JSON result out; no PATH/admin/service mutation by default. |
| Local Node daemon | Long-lived local-dev runtime posture and heartbeat. | Loopback-only IPC; no private payload persistence. |
| Relay client | Future hybrid/local relay transport. | Signed envelope transport contract; public/private payload split enforced before send. |

## Interface Boundaries

- Python policy runtime is the source of product policy until a Rust verifier consumes the same JSON schema.
- Rust components must accept policy/config as explicit JSON input. They must not read provider keys, private memory, or arbitrary local files.
- Rust stdout/stderr must follow the existing public CLI redaction rules: no secrets, local absolute paths, host inventory, raw prompts, or private runtime details.
- Native update/install work stays plan-only unless the user explicitly requests execution and the manifest/artifact hash checks pass.

## Migration Plan

1. Keep `cli.py` as a thin entrypoint and move command/screen/service logic into Python modules first.
2. Stabilize JSON contracts for policy status, install/update plan, and local node status.
3. Add a no-op Rust launcher only when packaging needs it; do not rewrite interactive UX in Rust.
4. Move install verification only after Python tests prove the exact hash/signature/path-mutation behavior.
5. Keep Python and Rust implementations under the same conformance tests during any transition.

## Risks

- A full Rust rewrite would slow feature iteration and duplicate policy logic.
- Native packaging increases signing and trust-store pressure before production trust is ready.
- Windows path and encoding behavior must be proven before any Rust launcher replaces the Python entrypoint.
- Splitting too early can hide policy drift between Python UI and native updater code.

## Current Decision

No Rust code is added in this lane. The safe next step is Python modularization plus schema-backed policy status. Rust remains a later launcher/updater/daemon boundary, not the product runtime rewrite.
