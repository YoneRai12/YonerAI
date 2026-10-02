# Security Runtime PR Validation 2026-05-21

Status: public-safe security/runtime backlog reduction checkpoint after the current-main fresh patch pass.

This document records which stale security/runtime PRs were replaced by a current-main v7.7-scoped patch. It is not a claim that the full security backlog is resolved.

## Verification Snapshot

- Source of truth: GitHub CLI PR state, PR file lists, merged PR #216, and local targeted validation.
- Current-main replacement PR: #216, `fix: harden security runtime backlog surfaces`.
- Replacement merge commit: `f26211b89cfc30c182ea7d7c8e8435f8f67cd457`.
- Open PR count before replacement close pass: 43.
- Open PR count after replacement close pass: 36.
- Latest GitHub Release observed during this goal: `v2026.5.20.6`.

## Fresh Patch Scope

PR #216 reimplemented the safe current-main subset of recently opened stale security/runtime PRs:

| area | current-main change | regression evidence |
|---|---|---|
| Surface Agent Run results | bounds accepted result count and result payload bytes in the in-memory run store | `tests/test_surface_api_run_contract.py::test_surface_agent_result_rejects_oversized_payload`, `tests/test_surface_api_run_contract.py::test_surface_agent_results_are_bounded_per_run` |
| Distribution file refs | rejects absolute `artifact_ref` values and path escape outside current working directory | `tests/test_distribution_node_mvp.py::test_distribution_node_rejects_absolute_artifact_paths`, `tests/test_distribution_node_mvp.py::test_distribution_node_files_are_refs_only_and_downloadable` |
| Hybrid donation policy | normalizes camelCase and PascalCase payload keys before forbidden-key checks | `tests/test_hybrid_signed_envelope_policy.py::test_camel_and_pascal_case_secret_keys_are_rejected` |
| CLI origin parsing | converts malformed `--api-origin` parse failures into deterministic CLI errors | `tests/test_surface_cli_smoke.py::test_cli_rejects_malformed_api_origin` |

## PRs Closed As Superseded

| PR | old lane | close reason | replacement evidence |
|---|---|---|---|
| #204 | unbounded Surface Agent Run result memory | Superseded by current-main #216 | same behavior landed with result-size and per-run result-count tests |
| #208 | Distribution Node `artifact_ref` path validation | Superseded by current-main #216 | same behavior landed with relative-path and absolute-path tests |
| #209 | duplicate Distribution Node `artifact_ref` path validation | Duplicate / superseded by #216 | duplicate of #208 lane, now replaced by #216 |
| #210 | Hybrid donation forbidden-key normalization | Superseded by current-main #216 | camelCase / PascalCase key regression test landed |
| #212 | duplicate Hybrid donation forbidden-key normalization | Duplicate / superseded by #216 | duplicate of #210 lane, now replaced by #216 |
| #211 | malformed CLI `--api-origin` crash | Superseded by current-main #216 | CLI malformed-origin regression test landed |
| #213 | duplicate malformed CLI `--api-origin` crash | Duplicate / superseded by #216 | duplicate of #211 lane, now replaced by #216 |

Each closed PR received a close comment citing PR #216, merge commit `f26211b89cfc30c182ea7d7c8e8435f8f67cd457`, and the relevant replacement test.

## PRs Left Open

A subset of security PRs remains open for follow-up review. Detailed vulnerability classes and tactical rationale are tracked in private or restricted channels to reduce public disclosure risk.

| PR | current classification | public-safe status note |
|---|---|---|
| #205 | `KEEP_SECURITY_REVIEW` | Open; pending follow-up security review. |
| #206 | `KEEP_SECURITY_REVIEW` | Open; pending follow-up security review. |
| #207 | `KEEP_SECURITY_REVIEW` | Open; pending follow-up security review. |
| #128 | `KEEP_SECURITY_REVIEW` | Open; pending follow-up security review. |
| #133 | `KEEP_SECURITY_REVIEW` | Open; pending follow-up security review. |
| #60 | `KEEP_SECURITY_REVIEW` | Open; pending follow-up security review. |
| #131 | `KEEP_SECURITY_REVIEW` | Open; pending follow-up security review. |
| #129 | `KEEP_SECURITY_REVIEW` | Open; pending follow-up security review. |
| #135 | `KEEP_SECURITY_REVIEW` | Open; pending follow-up security review. |
| #132 | `KEEP_SECURITY_REVIEW` | Open; pending follow-up security review. |

## Validation

- `python -m pytest tests/test_surface_api_run_contract.py tests/test_surface_cli_smoke.py tests/test_hybrid_signed_envelope_policy.py -q`
- `python -m pytest tests/test_distribution_node_mvp.py::test_distribution_node_files_are_refs_only_and_downloadable tests/test_distribution_node_mvp.py::test_distribution_node_rejects_absolute_artifact_paths -q`
- `python -m pytest tests/test_public_runnable_smoke.py tests/test_runtime_env_loader.py -q`
- `python -m pytest tests/test_public_core_message_mvp.py tests/test_core_api_access_security.py -q`
- `python -m pytest tests/test_local_llm_provider.py -q`
- `python -m ruff check` on touched Phase 3 Python paths and tests
- `python -m compileall` on touched Phase 3 Python package paths
- `git diff --check`
- Changed-file secret scan, local path scan, and mojibake / hidden Unicode scan

## Non-Claims

This pass does not claim production readiness, shipping completion, full security remediation, official-cloud completion, hybrid completion, persistent memory completion, Google login completion, Discord gateway completion, provider ecosystem completion, Tools/MCP completion, private runtime completion, official cloud runtime completion, or `src/cogs/ora.py` resolution.
