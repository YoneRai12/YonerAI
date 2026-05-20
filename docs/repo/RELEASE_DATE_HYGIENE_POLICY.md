# Release Date Hygiene Policy

Status: public-safe release hygiene policy for YonerAI checkpoint naming. This policy does not delete, retag, or rewrite any existing release.

## Purpose

YonerAI checkpoint labels should be useful to users reading the public GitHub surface. A release name must not imply that the repository is ahead of the verified calendar date, production-ready, or complete.

## Date Source

Before creating a checkpoint tag, GitHub Release, or markdown release note:

- verify the local date and UTC date;
- use the owner-intended current date when the owner explicitly states it;
- treat future-dated labels as a release hygiene issue, not as the current public truth;
- record any drift in the PR or release note.

For this cleanup lane, the verified date is 2026-05-20.

## Version Format

Use:

- first checkpoint of the day: `vYYYY.M.D`
- second checkpoint of the same day: `vYYYY.M.D.1`
- third checkpoint of the same day: `vYYYY.M.D.2`
- continue monotonically with the next unused suffix

Determine the next suffix by checking both:

- GitHub Releases and remote tags
- `docs/releases/` markdown notes

If markdown notes and GitHub Releases disagree, choose the next highest same-day suffix plus one. Do not backfill lower suffixes unless the owner explicitly approves.

## GitHub Releases

GitHub Releases should follow the same date/suffix discipline as markdown notes. A markdown release note alone is not a visible GitHub Release.

Release titles must be product-facing:

- use checkpoint capability names;
- do not lead with PR numbers;
- include PR numbers only in a late `Traceability` section when useful.

## Existing Future-Dated Labels

If a future-dated tag or GitHub Release already exists:

- do not delete it;
- do not retag it;
- do not rewrite history;
- create a corrected current-date release only when the target commit is verified and no tag conflict exists;
- avoid treating the future-dated release as the public latest checkpoint in README-first-screen surfaces.

## Non-Claims

Release hygiene does not claim:

- production readiness;
- shipping completeness;
- official cloud completion;
- live operations completion;
- full product completion;
- hybrid completion;
- persistent memory completion;
- Google login completion;
- Discord gateway completion;
- provider ecosystem completion.
