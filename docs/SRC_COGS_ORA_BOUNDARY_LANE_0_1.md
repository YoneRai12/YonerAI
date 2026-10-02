# src/cogs/ora.py Boundary Lane 0.1

Status:

- planning handoff
- docs-only
- no implementation
- no Pass 2 execution

## Decision

`src/cogs/ora.py` is reclassified as private/runtime/control-plane boundary lane residue.

It is not included in the `v2026.4.28` public progress checkpoint release scope and is not a hard blocker for that release.

It remains unresolved for shipping-complete, full product completion, official-cloud completion, and live operational completion.

## Why It Is Not A Narrow Public Patch

Stage 6t found that `src/cogs/ora.py` contains or coordinates high-risk runtime surfaces:

- Discord gateway/runtime behavior
- subprocess / tunnel startup behavior
- `SafeShell`
- file and code read tools
- moderation actions
- media and web tools
- dynamic tool registry injection
- owner/public tool filtering dependencies

Closing that truthfully requires boundary planning across private/runtime/control-plane ownership, not a narrow public-mainline patch.

## Current Ownership Classification

- public progress release lane = exclude
- private/runtime lane = likely owner for official Discord gateway behavior
- control-plane lane = possible owner for host / tunnel / supervision behavior
- public core lane = only contract and public-safe boundary surfaces
- exact split = unresolved

## Planning Questions

The next lane must answer:

- which parts remain in private runtime?
- which parts belong to control-plane?
- which public-safe abstractions, if any, stay in public core?
- which tools are owner-only, operator-only, or excluded?
- which subprocess / shell / file / moderation / media surfaces are allowed?
- which validation suites prove the boundary?
- what docs must be updated before any implementation?

## Hard Non-Claims

- `src/cogs/ora.py` has not landed.
- `src/cogs/ora.py` is not unblocked.
- Pass 2 has not landed.
- shipping-complete is not truthful.
- full product / official-cloud / live ops completion is not truthful.

## Next Strict Move

Start a private/runtime/control-plane boundary planning batch for `src/cogs/ora.py`.

Do not implement that lane without explicit execution approval.
