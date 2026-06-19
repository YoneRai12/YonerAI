# Security PR Intake - 2026-06

Public repository review/comment intake for the current Public YonerAI lane.
This file is public-safe: it avoids secrets, private runtime details, internal
hostnames, account data, and local private paths.

- last_scan_at: 2026-06-19T23:06:53+09:00
- current_main_head: bc0d9277
- latest_stable: v0.8.1
- latest_prerelease: v0.22.0-alpha.1
- highest_seen_pr_number: 557
- current_lane: public security/status gate before realtime sync

## Valid Findings Fixed In Current Lane

These open PR findings were valid against current main and are consolidated into
the current security intake branch instead of merging several stale PR branches:

| Source | Finding | Severity | Current disposition |
| --- | --- | --- | --- |
| #554 | Stored staging session `origin` could be an invalid sanitized value and crash URL construction. | security/correctness | Fixed in this branch with origin allowlist validation before saving and reuse. |
| #556 | Status public feed safety scan missed camelCase and mixed-separator secret-like metadata keys. | security/privacy | Fixed in this branch with normalized key scanning, path-redacted regression output, and temp cleanup. |
| #555 | Provider gateway client could follow redirects before failing, risking auth header forwarding to another endpoint. | security/privacy | Fixed in this branch by disabling redirects and adding regression coverage that closes test servers. |
| #557 review | Contract-compliant `/v1/account/me` responses containing `account.account_id` could be rejected before sanitizer redacted it. | P1/security/correctness | Fixed with account-path pre-sanitization and hashed account refs before public payload scanning. |
| #557 review | PR top-level conversation comments did not invalidate the intake gate. | P1/process/security | Fixed by adding `issue_comment` PR-event handling that removes `intake-reviewed`. |
| #543 / #540 / #541 | Loopback local LLM IME requests could honor environment proxies or redirects. | security/privacy | Fixed in this branch with proxy-disabled opener and redirect rejection. |
| #539 | Control Spine public payload markers did not reject generic token/secret names or private endpoint forms broadly enough. | security/privacy | Fixed in this branch with centralized forbidden markers, private URL regex, and regression tests. |
| #542 | Release note changes could skip generated artifact hash/size verification in Quality Wall. | release/security | Fixed in this branch with strict release-surface diff matching and regression tests. |

## Open PR Classification

| PR | Title | Classification | Review/comment state | CI state | Decision / tracking |
| --- | --- | --- | --- | --- | --- |
| #557 | fix: 公開セキュリティPR指摘を統合し intake gate を追加 | valid-now | Gemini readability comment and Codex P1 comments were valid and fixed | pending | Canonical replacement for #539/#540/#541/#542/#543/#554/#555/#556. |
| #556 | fix: block camelCase status feed secret keys | valid-now | Gemini robustness comment valid | security-static failed on PR branch | Superseded by current branch with stronger normalization and safer test output. |
| #555 | fix: reject provider gateway redirects | valid-now | Gemini server cleanup comment valid | pass but behind main | Superseded by current branch with explicit server close. |
| #554 | fix: validate stored staging session origins | valid-now | Gemini no-comment review; no unresolved thread | pass but behind main | Superseded by current branch canonical fix. |
| #548 | chore(deps-dev): bump js-yaml | deferred-with-tracked-issue | Dependabot dependency update | not revalidated here | Dependency PR remains its tracker; not blocking realtime sync. |
| #547 | fix: preserve update parent language option | deferred-with-tracked-issue | No P0/P1/security found in current intake | not revalidated here | UX/correctness PR remains its tracker; not blocking. |
| #545 | fix: allow CLI config theme setting | duplicate | Overlaps #544 | not revalidated here | Prefer newer #545 if theme config work resumes. |
| #544 | fix: allow CLI theme config setter | duplicate | Overlaps #545 | not revalidated here | Superseded by #545. |
| #543 | fix: keep local LLM IME calls off proxies | valid-now | Gemini no-comment review | pass but behind main | Superseded by current branch canonical fix. |
| #542 | fix: validate release-note archive changes | valid-now | Gemini P2 regex precision comment valid | pass but behind main | Superseded by current branch with stricter regex. |
| #541 | fix: keep local llm enhancer off proxies | duplicate | Same vulnerability family as #543/#540 | not revalidated here | Superseded by #543/current branch. |
| #540 | fix: keep local LLM IME calls off proxies | duplicate | Same vulnerability family as #543/#541 | not revalidated here | Superseded by #543/current branch. |
| #539 | fix: reject generic Control Spine secret markers | valid-now | Gemini comment about private IP matching was valid | pass but behind main | Superseded by current branch with stronger private URL matching. |
| #523 | docs: add README alpha state warning | deferred-with-tracked-issue | Docs-only warning | not revalidated here | PR remains tracker; not a security blocker. |
| #521 | fix: require validated staging account claim | valid-but-already-fixed | Gemini minor cleanup only | old pass | Current main already validates `account_me.ok` before claim persistence. |
| #413 | transformers requirement update | deferred-with-tracked-issue | Dependabot | not revalidated here | Dependency PR remains tracker. |
| #412 | chromadb bump | deferred-with-tracked-issue | Dependabot | not revalidated here | Dependency PR remains tracker. |
| #411 | aiosqlite update | deferred-with-tracked-issue | Dependabot | not revalidated here | Dependency PR remains tracker. |
| #410 | numpy update | deferred-with-tracked-issue | Dependabot | not revalidated here | Dependency PR remains tracker. |
| #156 | softprops/action-gh-release bump | deferred-with-tracked-issue | Dependabot | not revalidated here | Dependency PR remains tracker. |
| #151 | discord-py update | deferred-with-tracked-issue | Dependabot | not revalidated here | Dependency PR remains tracker. |
| #148 | pytesseract update | deferred-with-tracked-issue | Dependabot | not revalidated here | Dependency PR remains tracker. |
| #147 | soundfile update | deferred-with-tracked-issue | Dependabot | not revalidated here | Dependency PR remains tracker. |
| #146 | aiohttp update | deferred-with-tracked-issue | Dependabot | not revalidated here | Dependency PR remains tracker. |
| #145 | pynacl update | deferred-with-tracked-issue | Dependabot | not revalidated here | Dependency PR remains tracker. |
| #134 | image_gen double defer | stale | Old feature PR | not revalidated here | Not current public security blocker. |
| #121 | managed-cloud MVP surface | owner-only-blocker | Draft production-adjacent surface | not revalidated here | Owner approval required before any managed-cloud claim or merge. |
| #111 | public ORA branding cleanup | stale | Broad rename surface | not revalidated here | Requires compatibility plan; not current blocker. |
| #108 | IP valuation report | duplicate | Overlaps #107 | not revalidated here | Prefer one owner-approved IP/legal lane only. |
| #107 | IP valuation report draft | duplicate | Overlaps #108 | not revalidated here | Superseded by #108 if lane resumes. |
| #81 | CUA sidecar adoption guide | stale | Old docs/guide surface | not revalidated here | Not current blocker. |
| #79 | broaden generic image explanations | stale | Non-main base branch | not revalidated here | Needs rebase/new PR before consideration. |
| #34 | git-auto-commit-action bump | deferred-with-tracked-issue | Dependabot | not revalidated here | Dependency PR remains tracker. |
| #26 | Cloudflare DNS/tunnel plan | stale | Old docs/tunnel surface | not revalidated here | Not current blocker. |
| #18 | pycountry update | deferred-with-tracked-issue | Dependabot | not revalidated here | Dependency PR remains tracker. |
| #7 | setup-python bump | deferred-with-tracked-issue | Dependabot | not revalidated here | Dependency PR remains tracker. |
| #6 | checkout bump | deferred-with-tracked-issue | Dependabot | not revalidated here | Dependency PR remains tracker. |

## Status Gates

- PR #553 is merged and fixed Public CLI StatusSnapshot review blockers.
- PR #551 is merged and fixed StatusWEB StatusSnapshot review blockers.
- PR #557 is the canonical replacement PR for #539/#540/#541/#542/#543/#554/
  #555/#556.
- Issue #549 has Public and StatusWEB readiness comments and AWS implementation
  evidence. Closing remains gated on owner/AWS final acknowledgement if exact
  `[AWS-STATUS-FINAL-ACK]` wording is required by the active goal.

## Next Rules

- No next product phase may proceed with open current P0/P1/security findings.
- P2/P3/dependency/UX items above remain tracked but do not block realtime sync.
- New or synchronized PRs should be marked `needs-intake` and must not pass the
  PR Intake Gate until a maintainer adds `intake-reviewed` after classification.
