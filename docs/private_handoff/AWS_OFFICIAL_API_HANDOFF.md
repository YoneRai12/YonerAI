# AWS Official API Handoff

This is a private/official implementation handoff for a future YonerAI official
backend. It is not a deployment plan for the public repository and must not be
treated as proof that production Official Managed Cloud or production Oracle is
implemented.

## Public/Private Split

Public repo owns:

- official API contracts
- JSON schemas
- fixture-only CLI and TUI status surfaces
- sync/privacy/rate-limit conformance tests
- non-production install and update boundaries

Private/AWS lane owns:

- production API Gateway or CloudFront route
- WAF policy
- account auth backend
- rate-limit enforcement
- sync backend
- Oracle run queue and worker
- self-evolution proposal ingestion and owner approval console
- secrets, production logs, deployment state, and rollback operations

No production AWS credential, route inventory, secret, break-glass detail, or
control-plane internal belongs in the public repo.

## Recommended Boundary Architecture

Use one of these ingress patterns:

- API Gateway HTTP API plus WAF where the route mix is mostly JSON API calls.
- CloudFront plus WAF in front of API Gateway or Lambda Function URLs when
  shared web/API edge behavior is needed.

Required edge controls:

- WAF rate-based rules for anonymous abuse and high-cardinality bursts.
- WAF managed rules where compatible with JSON API traffic.
- IP and device-abuse throttles that do not become the sole auth decision.
- Separate staging and production hostnames and accounts.

API Gateway throttling and usage plans are useful but should not be the only
quota layer. Official YonerAI quota must also account for user, device, provider,
cloud-contract, and Oracle queue buckets.

## Auth

Recommended options:

- Lambda authorizer for custom YonerAI account state.
- Cognito user pool only if it does not force a product UX mismatch.

Contract requirements:

- Google installed-app OAuth with PKCE.
- State parameter required.
- Loopback redirect only for CLI.
- Minimal scopes: `openid email profile`.
- No embedded webview.
- Public client; no client secret in the public repo.
- No plaintext refresh token storage.
- Account states: unauthenticated, pending, linked, expired, revoked.

## Suggested Data Stores

DynamoDB tables:

- `YonerAIAccounts`: account id, provider subject hash, email verification
  state, account status.
- `YonerAIDevices`: account id, device ref hash, posture, revocation state.
- `YonerAIConversationRefs`: user-selected cloud conversation references and
  redacted metadata.
- `YonerAISyncAudits`: direction, decision, audit reason, content class, approval
  ref.
- `YonerAIRateLimitCounters`: bucket, account/device/provider key, window,
  remaining quota.
- `YonerAIOracleRuns`: run id, request envelope metadata, status, result envelope.
- `YonerAIEvolveProposals`: low-resolution signal class, owner approval state,
  rollback notes.

SQS queues:

- `YonerAIOracleRunsQueue` for official Oracle run requests.
- optional dead-letter queue for failed or blocked envelopes.

Do not store raw private file content, provider keys, local node payloads, raw
chain-of-thought, or local absolute paths.

## Secrets and Logs

Use AWS Secrets Manager or SSM Parameter Store for production secrets. Public
repo fixtures must never include secret names, ARNs, account ids, hostnames, or
private route details.

CloudWatch logs and metrics should record:

- request id
- account/device hash
- endpoint
- quota bucket
- sync direction
- decision state
- reason code
- latency bucket

Do not log provider keys, OAuth tokens, raw prompts, private content, or local
paths.

## Rate-Limit Enforcement

Enforce at multiple layers:

- WAF: anonymous abuse and edge bursts.
- API Gateway: route-level throttling.
- Lambda/application: user, device, provider, cloud-contract, Oracle queue, and
  self-evolution proposal quotas.

Required response headers:

- `Retry-After`
- `X-YonerAI-RateLimit-Limit`
- `X-YonerAI-RateLimit-Remaining`
- `X-YonerAI-RateLimit-Reset`
- `X-YonerAI-RateLimit-Bucket`

Quota exceeded should return `429` with a machine-readable reason and a local
fallback instruction where safe.

## Deployment Checklist

Before any private production launch:

- Contracts match `docs/contracts/OFFICIAL_API_CONTRACT_0_1.md`.
- Contract schemas pass public conformance tests.
- Staging and production are separated.
- WAF rules and throttles are tested.
- Auth rejects missing, expired, revoked, and malformed sessions.
- Local-to-cloud sync requires explicit approval.
- Private/local content exclusion tests pass.
- OpenAI shared traffic remains off unless a separate owner-approved policy
  enables it for eligible public-safe tasks.
- Oracle run queue rejects private/local payloads.
- Rollback and incident procedures exist outside the public repo.
- No production secrets are committed or printed by CLI/TUI.

## Non-Claims

This handoff does not mean:

- production AWS is deployed
- production Oracle is implemented
- production Google login is complete
- production cloud memory is complete
- live Discord is restored
- public repo can run Official Managed Cloud
