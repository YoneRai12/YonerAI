# Alpha security PR intake - 2026-05-21

## Result

Security intake is required before publishing `v0.1.0-alpha.1`.

No tag or GitHub Release was created during this intake.

## Owner security PR classification

| PR | Classification | Decision |
| --- | --- | --- |
| #297 `fix: enforce required-session route preview gate for not_required sentinel` | ALPHA_BLOCKER_MUST_MERGE | Integrated in the current-main security intake patch. |
| #298 `fix: validate audience in local node action envelope verification` | ALPHA_BLOCKER_MUST_MERGE | Integrated in the current-main security intake patch. |
| #299 `fix: align local-dev session binding default timestamp with pairing validity` | DUPLICATE_OR_SUPERSEDED | Superseded by runtime-clock default hardening plus explicit fixture times for deterministic demo tests. |
| #300 `fix: prevent pairing verifier exposure in public challenge payload` | ALPHA_BLOCKER_MUST_MERGE | Integrated in the current-main security intake patch. |
| #301 `fix: use runtime clock for local-dev manifest verification` | ALPHA_BLOCKER_NEEDS_FIX | Integrated with fixes: public demo and tests pass explicit fixture times where deterministic behavior is required. |
| #302 `fix(cli): trust-load public smoke module to prevent import hijack` | ALPHA_BLOCKER_NEEDS_FIX | Integrated with fixes: both public smoke and public demo load repo scripts by absolute trusted path. |
| #290 `fix: ignore malformed download URLs in final download filter` | ALPHA_BLOCKER_MUST_MERGE | Integrated in the current-main security intake patch. |

## Older security PR classification

| PR | Classification | Reason |
| --- | --- | --- |
| #133 `fix: block unsafe embed image URLs` | DUPLICATE_OR_SUPERSEDED | Current main already includes the embed image URL SSRF guard from merged #296. |
| #135 `fix: restrict Discord log forwarding and mask sensitive fields` | POST_ALPHA_SAFE | Live Discord forwarding is outside the alpha CLI demo path and still needs a dedicated current-main patch later. |
| #128 `fix: constrain dashboard user detail paths` | POST_ALPHA_SAFE | Dashboard user detail handling is outside the alpha CLI demo path and should be patched separately from current main. |
| #60 `fix: guard image crop upscale fetches` | POST_ALPHA_SAFE | Image crop/upscale fetching is outside the alpha CLI demo path and should be patched separately from current main. |

## Integrated patch scope

- Route preview treats `session_verification_state=not_required` as missing when an enrolled verified session is explicitly required.
- Local Node signed action envelope verification checks the expected audience before nonce acceptance and signature verification.
- Pairing challenge public output no longer exposes the verifier hash.
- Local-dev control-plane helpers use the runtime clock by default; demo and smoke fixtures pass explicit public-safe fixture times for deterministic output.
- Final download filtering ignores malformed URLs before constructing download metadata.
- CLI public smoke and demo commands trust-load repo scripts by absolute path instead of importable package names.

## Boundary confirmation

- No production Oracle, live Discord, provider API, deployment, production trust store, persistent memory, Google login, or telemetry ingestion was added.
- Official Managed Cloud remains contract-only/external in the public repository.
- The fixes remain public-safe simulator and contract behavior only.
- `src/cogs/ora.py` and `reference_clawdbot` were not modified.

## Release implication

The alpha release gate must be rerun after this intake is merged.
