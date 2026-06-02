# AWS Status API Handoff

This is a private/official implementation handoff for a future
status.yonerai.com and AWS-backed YonerAI status API. It is not a deployment
plan for the public repository and must not be treated as proof that production
AWS, Official Managed Cloud, or production Oracle is implemented.

## Public/Private Split

Public repo owns:

- status API contract
- JSON schemas and fixtures
- CLI/TUI status readers
- doctor status summary
- status feed conformance tests
- release/install status mapping

Private/AWS lane owns:

- production status API implementation
- health aggregation from real services
- incident workflow
- status page publishing
- CloudWatch metrics/logs
- WAF/rate-limit enforcement
- secrets, route inventory, production ids, and deployment state

No production AWS credential, private hostname, route inventory, secret, account
id, ARN, private IP, break-glass detail, or control-plane internal belongs in
the public repo.

## Recommended Architecture

Use one of these ingress patterns:

- API Gateway HTTP API plus Lambda for JSON status endpoints.
- CloudFront plus WAF in front of API Gateway when shared web/API edge behavior
  is needed.
- ECS/Fargate only if status aggregation needs a long-running collector.

Recommended endpoints:

- `GET /v1/status`
- `GET /v1/status/components`
- `GET /v1/status/incidents`
- `GET /v1/releases`
- `GET /v1/install`
- `GET /v1/rate-limit`

status.yonerai.com can either read the JSON API directly or receive a generated
`yonerai.status.feed.v1` artifact from the private backend.

## CloudFront and WAF

Recommended edge controls:

- WAF managed rules where compatible with JSON traffic.
- WAF rate-based rules for anonymous bursts.
- cache policy that allows short TTL status responses.
- separate cache behavior for static page assets and JSON API responses.
- staging/prod hostnames separated.

Do not put private runtime details into edge-visible headers, HTML, JavaScript,
or JSON.

## Health Aggregation

Private aggregation may collect:

- CLI release availability.
- GitHub Release asset availability.
- install/update manifest availability.
- official API health.
- Oracle queue health.
- Google auth configured/dry-run/disabled state.
- shared traffic disabled/enabled policy state.
- memory sync availability.
- self-evolution proposal queue health.
- Discord production status.
- provider runtime health.
- hybrid node relay health.

Public output must be reduced to component status, user-facing message,
incident id, next action, docs URL, release channel, and public-safe source
type. Do not publish internal target ids, private URLs, raw CloudWatch links,
ARNs, account ids, tokens, hostnames, or support-only runbooks.

## CloudWatch Metrics and Logs

Recommended metrics:

- endpoint
- status code
- latency bucket
- component id
- component status
- incident id
- cache hit/miss class
- quota bucket

Recommended logs:

- request id
- endpoint
- component id
- public status
- reason code
- cache key class
- rate-limit bucket

Do not log provider keys, OAuth tokens, raw prompts, private file content, local
memory content, local node payloads, local absolute paths, raw chain-of-thought,
or private route inventory.

## Incident Workflow

Private incident workflow should:

1. Create or update a private incident record.
2. Produce public-safe `incident_id`, severity, component list, timeline, and
   user message.
3. Publish the reduced status feed.
4. Keep internal root cause, private ids, and remediation runbooks private.
5. Expire or resolve the incident through an explicit owner or operator action.

Public incident severity should map to:

- `degraded`
- `partial_outage`
- `major_outage`
- `maintenance`

## Cache Headers

Suggested JSON API defaults:

- `Cache-Control: public, max-age=60, stale-while-revalidate=300` for status.
- shorter TTL for incident-active responses.
- longer TTL for release/install metadata that is tied to immutable GitHub
  Release assets.

The CLI can read local fixtures by default and may fetch allowlisted HTTPS status
only when explicitly requested by the user.

## Rate Limit Integration

Status endpoints should emit:

- `Retry-After`
- `X-YonerAI-RateLimit-Limit`
- `X-YonerAI-RateLimit-Remaining`
- `X-YonerAI-RateLimit-Reset`
- `X-YonerAI-RateLimit-Bucket`

Use WAF for abusive bursts and application quota for API-level behavior. The
status bucket should be generous but not unlimited.

## Example Public JSON

```json
{
  "schema_version": "yonerai-status-api/v0.1",
  "ok": true,
  "status": "operational",
  "component_count": 12,
  "production_backend_included": false,
  "private_runtime_details_included": false
}
```

## Deployment Checklist

Before any private status launch:

- Contracts match `docs/contracts/STATUS_API_CONTRACT_0_1.md`.
- Schemas and fixtures pass public conformance tests.
- Public JSON contains no secrets, private routes, account ids, ARNs, IPs, local
  paths, or internal runbook detail.
- Staging and production are separated.
- WAF and app-level rate limit are enabled.
- CloudWatch logging excludes private content.
- Incident workflow has owner/operator review.
- Cache headers are tested.
- CLI can still run without network using local fixtures.

