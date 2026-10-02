# YonerAI Official API Rate-Limit Policy

This policy defines the public contract for future official API quota behavior.
The public repository does not enforce production rate limits and does not enable
shared OpenAI traffic by default.

## Buckets

| Bucket | Purpose | Public repo state |
| --- | --- | --- |
| anonymous | unauthenticated status and abuse control | contract only |
| authenticated | linked account baseline requests | contract only |
| user_quota | per-account API quota | contract only |
| device_quota | per-device posture and quota | contract only |
| provider_quota | provider or shared pool budget | contract only |
| cloud_contract | sync preview/approve and cloud-contract candidate work | contract only |
| oracle_queue | official Oracle run enqueue/result polling | contract only |
| abuse | edge abuse prevention and anomalous traffic | contract only |

## Required Headers

Official responses should include these headers where applicable:

- `Retry-After`
- `X-YonerAI-RateLimit-Limit`
- `X-YonerAI-RateLimit-Remaining`
- `X-YonerAI-RateLimit-Reset`
- `X-YonerAI-RateLimit-Bucket`

`Retry-After` is required for `429 quota_exceeded` responses.

## Quota Exceeded Behavior

When quota is exceeded:

1. Return HTTP `429`.
2. Include a machine-readable `quota_exceeded` error code.
3. Include `Retry-After`.
4. Explain which bucket blocked the request.
5. In CLI/TUI, show a safe fallback when available.

Safe fallback:

- local mock provider
- loopback local LLM if explicitly configured and safe
- deny or wait when the request requires official cloud or Oracle

Unsafe fallback:

- uploading private content to bypass quota
- using OpenAI shared traffic without explicit opt-in and eligibility
- running production Oracle from the public repo
- using provider keys from config output, logs, or ledger

## Shared Traffic Policy

OpenAI shared traffic is off by default.

Requirements before any future enablement:

- explicit user opt-in
- public/safe prompts only
- private file content excluded
- local memory excluded
- local node payload excluded
- account eligibility verified outside the public repo
- daily quota and abuse controls
- ledger records `shared_traffic=false` by default and true only after explicit
  policy approval

The public repo must not claim free usage or owner/org eligibility.

## Sync and Privacy Coupling

Rate-limit handling cannot weaken sync policy.

- `cloud_to_local` requires linked account and selected cloud conversation.
- `local_to_cloud` is disabled by default.
- `local_to_cloud` requires explicit approval and audit reason.
- local private memory, secret-like content, private file content, and local node
  payloads cannot sync.

## CLI Expectations

Commands:

```powershell
yonerai api rate-limit --pretty --lang ja
yonerai api status --pretty --lang ja
yonerai sync rate-limit --json
```

These commands show contract state only. They do not contact AWS, production
Official Managed Cloud, or production Oracle.
