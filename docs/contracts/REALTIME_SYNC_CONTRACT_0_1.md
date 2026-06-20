# [SYNC-PROPOSAL-V1] YonerAI Realtime Sync Contract 0.1

Status: accepted in issue #552 after AWS and YonerAIWEB ACK
Owner: Public YonerAI contract lane
Schema version: `yonerai.realtime_sync.v1`
Date: 2026-06-20

This contract defines the public Web-to-CLI realtime sync projection. It is a
metadata-only projection contract. It does not implement production cloud sync,
production Google login, production Oracle, provider execution, or arbitrary
local file/tool access.

## Source Priority

1. Public contract in this file and issue #552.
2. AWS staging implementation ACK.
3. YonerAIWEB staging implementation ACK.
4. Older design docs and Codex summaries.

If AWS/Web behavior differs from this contract, the runtime must pause or reject
the incompatible event instead of guessing.

## Transport Boundary

Firestore, or any future realtime projection bus, carries metadata only.

Allowed:

- account-scoped conversation/message identifiers
- event type
- sync policy
- cursor and sequence metadata
- body reference
- projection version
- provider-consent reference
- safe audit reference

Forbidden:

- message body
- raw prompt or provider output
- local memory content
- local file content or file bytes
- local node payload
- provider keys or token-like values
- Google access token, ID token, refresh token, auth code
- internal hostnames, IPs, paths, ARNs, worker identity, account email
- raw audit details
- approval authority mutation from the projection bus

The CLI must fetch message body only from authenticated AWS official API using
the `body_ref` after validating the metadata event. There is no Firestore body
fallback.

## SyncEvent

Each projected event must be a JSON object with these public-safe fields:

```json
{
  "schema_version": "yonerai.realtime_sync.v1",
  "event_id": "evt_01H...",
  "account_id": "acct_public_opaque",
  "conversation_id": "conv_01H...",
  "message_id": "msg_01H...",
  "event_type": "message_created",
  "origin": "web",
  "sync_policy": "cloud_to_local",
  "cursor": "cursor_opaque",
  "sequence": 42,
  "idempotency_key": "sync_opaque",
  "created_at": "2026-06-20T00:00:00Z",
  "projection_version": 1,
  "body_ref": {
    "kind": "aws_message_body",
    "href": "/v1/conversations/conv_01H/messages/msg_01H/body",
    "body_included": false
  },
  "provider_consent_ref": {
    "state": "off",
    "conversation_id": "conv_01H"
  },
  "audit_ref": {
    "kind": "metadata_only",
    "audit_id": "aud_01H"
  },
  "reason": "cloud conversation selected by linked account"
}
```

Required fields:

- `schema_version`
- `event_id`
- `account_id`
- `conversation_id`
- `event_type`
- `origin`
- `sync_policy`
- `cursor`
- `idempotency_key`
- `created_at`
- `projection_version`
- `body_ref.body_included=false`

Optional fields:

- `message_id`
- `sequence`
- `body_ref.href`
- `provider_consent_ref`
- `audit_ref`
- `reason`

## Enumerations

`event_type`:

- `conversation_created`
- `conversation_updated`
- `message_created`
- `message_updated`
- `message_deleted`
- `policy_changed`
- `cursor_checkpoint`
- `projection_stale`

`origin`:

- `web`
- `cloud`
- `cli`
- `local`

`sync_policy`:

- `local_only`
- `cloud_to_local`
- `bidirectional_explicit`
- `paused`

`body_ref.kind`:

- `aws_message_body`
- `none`

## Policy Semantics

- Web/cloud origin defaults to `cloud_to_local`.
- CLI/local origin defaults to `local_only`.
- Local-to-cloud requires `bidirectional_explicit` and an AWS-owned approval
  decision for the conversation.
- `paused` means no body fetch and no projection mutation.
- `local_only` memory stays local and must never be projected.
- Provider-sharing consent is separate from sync policy.
- Provider-sharing defaults off.
- A sync policy change in Firestore is advisory only unless confirmed by AWS.

## Account Scope

The CLI must compare event `account_id` with the linked YonerAI account/session
claim. If it is missing, unknown, or mismatched, the CLI must reject the event
and avoid body fetch.

The projection must not expose raw email or Google subject. `account_id` is an
opaque public-safe identifier controlled by AWS.

## Cursor, Reconnect, And Idempotency

The CLI stores the last accepted cursor per account and conversation.

Rules:

- Duplicate `event_id` or `idempotency_key` is ignored.
- Reordered events may be buffered or fetched by cursor repair.
- Missing cursor on required events is invalid.
- Stale projection must surface as `projection_stale` and pause body fetch until
  AWS confirms the repair cursor.
- Reconnect must request events after the last accepted cursor.
- The CLI must not infer missing message body from cached local/private content.

## AWS Body Fetch

After validating the event, the CLI may call authenticated AWS official API:

- `GET /v1/conversations/{conversation_id}/messages/{message_id}`
- or a compatible AWS-approved body endpoint named by `body_ref.href`.

Required response boundary:

- body comes from AWS official API, not from Firestore
- no provider key/token/auth code in response
- no internal hostname/path/ARN
- no raw audit detail
- only the selected account/conversation can read the body

If the CLI session is expired, revoked, schema-mismatched, origin-mismatched, or
missing, the CLI must show a controlled login/repair message and avoid body
fetch.

## Firebase Read-Auth Bridge

Status: Public/YonerAIWEB ACK accepted; live staging endpoint proof and
Web-to-CLI E2E remain pending.

The Firestore SDK listener needs a read-auth bridge because the CLI must not use
Google tokens directly and must not store Google or refresh tokens. The proposed
staging bridge is:

- `POST /v1/sync/firebase-token`
- authenticated only by the AWS-issued opaque YonerAI staging session
- returns a short-lived Firebase custom token for Firestore metadata reads
- does not return Google access tokens, Google ID tokens, refresh tokens,
  OAuth auth codes, provider keys, or production login state

Accepted response metadata:

- `firebase_auth_contract_version=yonerai.firebase.custom_token.v1`
- `token_type=firebase_custom_token`
- `uid` and `account_id` equal the opaque YonerAI account id
- `expires_in_seconds` is positive and no more than 900
- `firestore.sync_enabled=false` until live Web-to-CLI E2E is proven and the
  owner explicitly flips the staging flag
- `firestore.sync_event_path_template=/accounts/{account_id}/sync_events/{event_id}`

Public CLI reporting rules:

- may report that a Firebase custom token was received
- must not print or persist the Firebase custom token value
- must fail closed if the account binding, path template, boundary flags, or
  expiry are invalid
- must fail closed if the response contains Google/provider/token/private path
  material outside the explicit false boundary flags
- may expose `yonerai sync listener readiness` as a safe diagnostic. The command
  may report a non-ready state such as a 404 endpoint without failing the CLI,
  but token/private payload or contract mismatch must still fail closed.
- must not treat receipt of `firebase_custom_token` alone as proof that the
  Firestore SDK listener is ready. Public must also have a reviewed client
  dependency and a public-safe Firebase client sign-in exchange/config before
  starting a live SDK listener.

## Security Fixtures

The canonical shared golden fixture bytes live at:

- `docs/contracts/fixtures/realtime-sync-v1/golden.fixture.json`

AWS, Public, and YonerAIWEB must use identical bytes for this golden fixture
set. A lane-specific validator may add additional local regression fixtures, but
it must not reinterpret the shared golden fixtures. If a lane disagrees with the
expected accept/reject result, fix that lane's validator or request a new
contract version. Do not mutate the fixture ad hoc in only one lane.

The golden fixture set covers:

- valid cloud-to-local `message_created`
- forbidden body projection
- forbidden token-like value
- forbidden local path
- forbidden internal endpoint
- forbidden body-ref traversal/query
- forbidden account mismatch
- forbidden provider-sharing default-on
- forbidden unknown/private fields

Additional implementation regression fixtures should also cover:

- valid local-only CLI-origin event that does not fetch body
- duplicate event/idempotency key ignored
- reordered event handling
- stale projection pause
- local-to-cloud without explicit approval rejected
- forbidden raw body rejected
- forbidden raw audit rejected
- forbidden token-like field rejected
- forbidden local path/internal hostname/IP/ARN rejected
- body fetch only through authenticated AWS API

## Acceptance Rules

Public sends `[SYNC-PROPOSAL-V1]` in issue #552.

AWS must ACK with `[AWS-SYNC-ACK]` only after confirming it can produce this
metadata-only projection and authenticated AWS body fetch boundary.

YonerAIWEB must ACK with `[YONERAIWEB-SYNC-ACK]` only after confirming Web can
consume/emit only this metadata projection and does not claim approval authority.

After both ACKs, Public sends `[SYNC-CONTRACT-ACCEPTED]`.

No runtime may claim live Web-to-CLI realtime sync before live E2E proves:

1. Web creates a conversation/message.
2. AWS stores body.
3. Firestore emits body-free SyncEvent.
4. CLI receives and validates the event.
5. CLI fetches body from AWS.
6. Same message appears in CLI.
7. Local-origin remains local-only.
8. No local memory/body/provider data leaks into projection.
