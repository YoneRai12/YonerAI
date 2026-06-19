# StatusSnapshot Review Checkpoint

- last_scan_at: 2026-06-19T15:24:58+09:00
- lane: public-status-snapshot
- highest_seen_pr_number: 553

## PR 550

- updated_at: 2026-06-18T23:23:42Z
- classification: valid-now findings fixed by replacement PR
- review/comment state:
  - Gemini medium: explicit HTTPS `:443` and whitespace normalization were valid-but-already-fixed before merge.
  - Codex P1/P2: default live status fetch, bare private identifiers, timeout validation, private runtime details flag, and empty components were valid-now.
- CI state: original PR passed before merge; replacement PR #553 opened for remaining merged-review fixes.
- decision: fixed in PR #553.
- replacement PR or tracking issue: #553

## PR 551

- updated_at: 2026-06-18T23:46:05Z
- classification: valid-now but separate StatusWEB lane
- review/comment state:
  - Latest inline comments include P1/P2 findings on `status.yonerai.com` packaging/feed safety and UI behavior.
  - This public CLI/StatusSnapshot patch does not edit StatusWEB files.
- CI state: previous checks passed, but comments arrived after the recorded ACK.
- decision: defer to StatusWEB lane; do not mix into PR #553.
- replacement PR or tracking issue: StatusWEB lane must address before merge/deploy.

## PR 553

- updated_at: 2026-06-19T06:20:19Z
- classification: valid-but-already-fixed by current PR head
- review/comment state:
  - Gemini high/security-high: bare `localhost` could bypass private host rejection.
  - The fix centralizes `localhost` rejection in `_is_private_host()` and adds a regression test that checks the offending host is not printed.
- CI state: Quality Wall passed on PR head `2cb84a74`.
- decision: ready after final review scan; merge only if no newer P0/P1/security finding appears.
- replacement PR or tracking issue: #553
