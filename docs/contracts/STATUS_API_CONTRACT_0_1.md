# YonerAI Status API Contract 0.1

This contract defines the public status shape shared by YonerAI CLI Local
Runtime, status.yonerai.com, and a future private/AWS official backend.

The public repository contains only contracts, fixtures, schemas, CLI/TUI
readers, and conformance tests. It does not contain production AWS secrets,
production Oracle/cloud runtime, production Google login, live Discord, provider
keys, private runtime inventory, or private monitoring routes.

## Public Repo Status

- Contract and fixture only.
- Network fetch is disabled by default.
- Local JSON status fixtures are allowed.
- URL status fetch, if used, must be explicit and allowlisted.
- status.yonerai.com may consume the same feed shape, but production monitoring
  belongs to the private/AWS lane.
- The public fixture must not include AWS account ids, ARNs, private IPs,
  production hostnames beyond public product hosts, tokens, raw endpoint
  inventory, local absolute paths, or control-plane internals.

## Public JSON Boundary

Public status JSON is a reduced user-facing feed, not an internal monitoring
dump. It may publish only coarse component state, public incident text, next
user action, public docs URL, and release/install channel state.

Do not publish these fields through status.yonerai.com or public fixtures:

- AWS account ids, ARNs, private IPs, private hostnames, or private routes
- CloudWatch links, runbook links, break-glass detail, or internal ticket ids
- provider keys, OAuth tokens, webhook URLs, or secret-like values
- raw exception text, raw logs, raw provider errors, or raw monitoring payloads
- local absolute paths, usernames, hostnames, local node inventory, or private
  runtime inventory
- detailed capacity, abuse, WAF, rate-limit tuning, or infrastructure topology
  that would help an attacker

The public repo readers must fail closed or strip non-public fields before
printing JSON. Internal monitoring data belongs only in the private/AWS lane,
where it is reduced into this contract before publication.

The public reader must reject sourced payload text that contains private or
reserved endpoint material before it is printed. This includes RFC1918 IPv4,
loopback, link-local, metadata-service IPs, IPv6 loopback, unique-local,
link-local, multicast/reserved addresses, internal hostname suffixes such as
`.internal` or `.local`, AWS ARNs/instance ids, local paths, and secret-like
markers. Controlled errors must not echo the offending URL, local path, or raw
private endpoint.

## Endpoints

All endpoints are JSON and public-safe. Production responses should include
cache headers and rate-limit headers, but public fixtures do not call a backend.

| Method | Path | Auth | Public repo support |
| --- | --- | --- | --- |
| `GET` | `/v1/status` | anonymous allowed | fixture only |
| `GET` | `/v1/status/components` | anonymous allowed | fixture only |
| `GET` | `/v1/status/incidents` | anonymous allowed | fixture only |
| `GET` | `/v1/releases` | anonymous allowed | fixture only |
| `GET` | `/v1/install` | anonymous allowed | fixture only |
| `GET` | `/v1/rate-limit` | anonymous allowed | fixture only |

Schema files live under:

- `docs/contracts/schemas/status-api-0.1/status.response.schema.json`
- `docs/contracts/schemas/status-api-0.1/components.response.schema.json`
- `docs/contracts/schemas/status-api-0.1/incidents.response.schema.json`
- `docs/contracts/schemas/status-api-0.1/releases.response.schema.json`
- `docs/contracts/schemas/status-api-0.1/install.response.schema.json`
- `docs/contracts/schemas/status-api-0.1/rate-limit.response.schema.json`
- `docs/contracts/schemas/status-api-0.1/status-feed.schema.json`
- `docs/contracts/schemas/status-api-0.1/contract.schema.json`

Fixture files live under:

- `docs/contracts/fixtures/status-api-0.1/`

## Status Enum

API response statuses:

- `operational`
- `degraded`
- `partial_outage`
- `major_outage`
- `maintenance`
- `contract_only`
- `not_production`

Status page feed display states:

- `operational`
- `alpha_only`
- `not_started`
- `maintenance`
- `degraded`
- `partial_outage`
- `major_outage`

## Component IDs

Required component ids:

- `cli_release`
- `install`
- `update`
- `official_api`
- `oracle`
- `google_auth`
- `shared_traffic`
- `memory_sync`
- `self_evolution`
- `discord`
- `provider_runtime`
- `hybrid_node`

Every component must expose:

- `component_id`
- `status`
- `name`
- `user_message_ja`
- `user_message_en`
- `next_action`
- `docs_url`
- `release_channel`
- `source`

The `source` object may identify public-safe source type such as `fixture`,
`github_release`, `status_feed`, `aws_future`, or `manual_incident`. It must not
contain private AWS ids, private routes, tokens, ARNs, local paths, hostnames, or
break-glass detail. If a local or allowlisted feed provides a non-public source
field, the public reader must either reduce it to the public-safe source shape
or reject the payload before printing.

## Status Feed Shape

status.yonerai.com can consume `yonerai.status.feed.v1`.

The feed uses:

- `default_status` for normal state.
- `day_overrides` only for exceptions.
- `incidents` for timeline/detail.
- categories for large status groups.
- components for actual monitored targets.

Category status should be aggregated from component status. Higher severity wins:

`major_outage` > `partial_outage` > `degraded` > `maintenance` >
`not_started` > `alpha_only` > `operational`.

Minimal feed shape:

```json
{
  "schema_version": "yonerai.status.feed.v1",
  "generated_at": "2026-06-02T00:00:00Z",
  "meta": {
    "product": "YonerAI",
    "source": "public fixture",
    "live_monitoring": false,
    "refresh_ms": 300000,
    "environment": "public-contract"
  },
  "states": {
    "operational": {
      "severity": 0,
      "label": {"ja": "正常", "en": "Operational"}
    }
  },
  "categories": [
    {
      "id": "release-distribution",
      "name": {"ja": "配布", "en": "Distribution"},
      "default_status": "operational",
      "components": [
        {
          "id": "install",
          "name": {"ja": "インストール", "en": "Install"},
          "default_status": "operational",
          "fact": {"ja": "GitHub Release assetを使います", "en": "Uses GitHub Release assets"},
          "monitoring": "fixture",
          "claim": "contract_only",
          "source": "fixture",
          "day_overrides": []
        }
      ]
    }
  ],
  "incidents": []
}
```

## CLI and TUI Consumers

Users can inspect this contract with:

```powershell
yonerai status check --json
yonerai status check --pretty --lang ja
yonerai api status --json
yonerai api status --status-source docs/contracts/fixtures/status-api-0.1/status-feed.fixture.json --json
```

Interactive CLI:

- `/状態`
- `/status`
- `/API`
- `/公式`

`--status-source` accepts a local JSON feed path. HTTPS URLs are rejected unless
`--allow-network-status-fetch` is passed and the host is allowlisted. Allowed
public hosts are limited to:

- `status.yonerai.com`
- `api.yonerai.com`
- `yonerai.com`

## Install and Release Mapping

Status output may include:

- latest stable release
- latest alpha release
- install channel status
- update availability
- quick install command
- verified install command

It must not claim production installer readiness. Public install assets remain
GitHub Release assets unless a future signed hosting lane explicitly changes the
distribution source.

## Rate Limit Contract

Status API responses should expose:

- `Retry-After`
- `X-YonerAI-RateLimit-Limit`
- `X-YonerAI-RateLimit-Remaining`
- `X-YonerAI-RateLimit-Reset`
- `X-YonerAI-RateLimit-Bucket`

The status bucket is public-read friendly but still needs abuse protection.

## Non-Claims

This contract does not mean:

- production AWS backend is implemented
- production Oracle is implemented
- Official Managed Cloud is runnable from this repo
- production Google login is enabled
- live Discord is restored
- OpenAI shared traffic is enabled
- production installer/npm/winget is ready
- private runtime inventory can be exposed
