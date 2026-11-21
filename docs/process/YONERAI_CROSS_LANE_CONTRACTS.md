# YonerAI Cross-Lane Contracts

Canonical detail for live integration windows, owner-only smoke, E2E, and cross-lane runtime work. Every agent must follow these rules; `AGENTS.md` summarizes them and links here.

## Cross-Lane Contract Pre-Verification

Before any live integration window, owner-only smoke, E2E, or cross-lane runtime test, every lane MUST verify the contract at every interface it shares with another lane by using cross-thread Codex messages and the canonical coordination issue.

Do not discover contract mismatches by opening a live window.

A contract means the exact public-safe shape of the interface, including:

- request JSON shape
- response JSON shape
- required fields
- forbidden fields
- auth credential type at that hop
- status codes
- error shape
- Firestore security rule shape
- Firestore query shape
- body fetch shape
- status snapshot shape
- event schema
- retry/idempotency/cursor semantics

The producing lane MUST publish its exact public-safe contract before live execution.

The consuming lane MUST reply with an explicit ACK or mismatch report before live execution.

Examples:

- AWS publishes the body endpoint response shape.
- Public CLI ACKs that its sanitizer accepts that exact shape.
- AWS publishes the Firestore rule shape.
- Public CLI publishes its Firestore query shape.
- AWS and Public verify rule/query compatibility before any sync window.
- YonerAIWEB publishes that live `/jp/chat` serves the sync runtime and not a stale MVP-only runtime.
- StatusWEB publishes that it consumes only public-safe StatusSnapshot/feed fields.

Cross-thread messages are mandatory for cross-lane runtime work. They are not optional status updates.

The canonical coordination ledger is issue #552 unless a newer manager-approved ledger is specified.

Live smoke MUST NOT begin unless all required producer/consumer ACKs exist as fresh standalone tags or explicit ACK comments in the ledger.

Forbidden:

- implementing against guessed peer behavior
- widening security rules to make a client query pass
- accepting stale tags from old failed windows
- treating "missing" text as a present tag
- using old window evidence after rollback
- consuming owner approval to discover a static contract mismatch
- adding helper scripts/runbooks/templates while the direct blocker is an unverified cross-lane contract

Firestore-specific rule learned from the 2026-06 Firestore read 400 incident:

Firestore Security Rules are not filters. A client query is rejected unless the query itself carries the same constraints that the rules require.

Therefore, before any Firestore live read smoke:

- AWS must publish the deployed rule shape.
- Public/YonerAIWEB must publish their query shape.
- The rule and query must be compared before opening a sync window.
- If they mismatch, fix the client query to match the strict rule.
- Do not broaden the rule unless manager explicitly approves a security tradeoff.
- Broad `sync_events` list relaxation is forbidden for closed-alpha sync.

Owner approval is expensive and bounded. It must never be consumed to discover a mismatch that static cross-lane contract comparison could have caught.

## Cross-Lane Contract Matrix

Before opening any live integration window, owner smoke, E2E, or cross-lane runtime test, every producing and consuming lane must complete a public-safe contract matrix on issue #552.

A live smoke window must never be used to discover a contract mismatch that could have been caught by comparing public-safe contracts.

For every interface, record:

- producer lane
- consumer lane
- endpoint/path
- request JSON shape
- response JSON shape
- required fields
- forbidden fields
- auth credential type
- status codes
- error shape
- Firestore rule shape if applicable
- client query shape if applicable
- ACK tag from producer
- ACK tag from consumer
- AWS verification tag if AWS owns the rule or endpoint

Interfaces include at minimum:

1. AWS body endpoint -> Public CLI body fetch
2. AWS body endpoint -> YonerAIWEB body fetch
3. AWS Firestore rules -> Public CLI Firestore query
4. AWS Firestore rules -> YonerAIWEB onSnapshot query
5. YonerAIWEB Web sender -> AWS Web receiver endpoint
6. AWS firebase-config -> Public CLI / YonerAIWEB Firebase init
7. AWS firebase-token -> Public CLI / YonerAIWEB Firebase sign-in
8. AWS status snapshot -> StatusWEB feed adapter

## Firestore Consumers

Firestore security rules are not filters.

Every Firestore consumer must make a query that already satisfies the same constraints required by the rules.

This applies to:

- Public CLI one-shot receiver
- YonerAIWEB onSnapshot listener
- any future Local UI listener
- any future mobile/client listener

Before owner-only sync smoke:

- AWS must publish the deployed safe Firestore rule shape.
- Public must ACK its CLI query shape.
- YonerAIWEB must ACK its Web/onSnapshot query shape.
- AWS must verify both consumer query shapes against deployed rules.
- The live window must not open until both consumer queries are verified.

Never fix a Firestore rule-vs-query failure by broadening rules unless the rule itself is proven wrong. Prefer fixing the query to match the strict safe rule.

## Web Send Contract

The Web sender path is also a cross-lane contract.

Before owner-only sync smoke:

- YonerAIWEB must publish the exact live Web sender endpoint and request shape.
- AWS must confirm the matching endpoint exists in the currently deployed staging API.
- AWS must confirm the response shape includes the body commit acknowledgement fields the Web runtime expects.
- YonerAIWEB must ACK the response shape.
- The smoke window must not open until Web sender and AWS receiver match.

A Web-side send helper alone is not sufficient. The producer/consumer pair must match.

## Auth Session Persistence Contract

A staging login is not considered ready merely because a client saved a local claim or `whoami` appears successful.

For any owner-only sync smoke, login readiness means all of the following are true:

- the client can authenticate to staging
- the server-side canonical staging session store contains an active row for the same authenticated owner
- `whoami` and owner allowlist construction read from the same canonical session source
- expired or stale rows are rejected
- a completed login writes exactly one active canonical session row
- no token, account identifier, raw body, private path, provider key, or secret is logged

If `whoami` succeeds but the owner allowlist builder cannot find an active canonical session row, this is a session persistence contract failure. Do not ask the client to repeatedly re-login. Fix the persistence path or the source mismatch.

Routine session refresh may be autonomous during staging preflight. Opening a sync window remains owner-gated.