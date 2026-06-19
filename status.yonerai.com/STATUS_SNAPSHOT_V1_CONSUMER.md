# StatusSnapshot v1 consumer

StatusSnapshot v1 is the public-safe handoff from AWS/Public YonerAI runtime evidence into StatusWEB.

StatusWEB does not own runtime truth. The browser renderer still consumes only `yonerai.status.feed.v1`.

Current accepted upstream schema:

- `yonerai.status.v1`

Flow:

```text
GET https://api-staging.yonerai.com/v1/status
  -> yonerai.status.v1
  -> tools/build-status-source-from-snapshot.mjs
  -> yonerai.status.source.v1
  -> tools/build-status-pipeline.mjs
  -> yonerai.status.feed.v1
  -> mock-status-adapter.js renderer
```

Expected HTTP metadata:

- `ETag: W/"snapshot_id"`
- `Cache-Control: public, max-age=15, stale-while-revalidate=60`
- `X-YonerAI-Status-Schema: yonerai.status.v1`

Copy-paste contract:

```json
{
  "schema_version": "yonerai.status.v1",
  "snapshot_id": "preview-2026-06-01T00:00:00Z",
  "generated_at": "2026-06-01T00:00:00Z",
  "stale_after_seconds": 60,
  "overall": {
    "health": "degraded",
    "availability": "limited",
    "stage": "staging",
    "message": {
      "ja": "YonerAI Status はstaging/previewの公開safeステータスです。本番稼働や24時間運用は主張していません。",
      "en": "YonerAI Status is a public-safe staging/preview status surface. It does not claim production or 24/7 operation."
    }
  },
  "components": [
    {
      "id": "official_execution_worker",
      "health": "offline",
      "availability": "unavailable",
      "stage": "staging",
      "message": {
        "ja": "worker heartbeat が stale のため、公式実行は利用不可です。",
        "en": "Official execution is unavailable because the worker heartbeat is stale."
      },
      "updated_at": "2026-06-01T00:00:00Z",
      "stale": true,
      "incident_ref": null
    }
  ]
}
```

Component IDs:

- `api`
- `auth`
- `provider_gateway`
- `official_execution_worker`
- `run_queue`
- `realtime_sync`
- `web`
- `audit`
- `discord`

Health values:

- `operational`
- `degraded`
- `partial_outage`
- `major_outage`
- `maintenance`
- `offline`
- `unknown`

Availability values:

- `available`
- `limited`
- `unavailable`

Stage values:

- `preview`
- `staging`

Rendering rules:

- `stage` is not a health state.
- `preview` is not an outage.
- `not_production` is copy/disclosure, not a health value.
- `unknown` must not render green.
- `official_execution_worker.health=offline` plus `availability=unavailable` means official execution is unavailable.
- Provider gateway and official execution worker are separate components.
- Firestore or realtime fixture data must not be presented as operational unless explicitly deployed and verified.
- `incident_ref` may be present, but StatusWEB must not invent public incident details from internal notes.
- If the upstream snapshot lacks historical daily data, StatusWEB must not fabricate 90 days of operational history.
- Missing history must render as `unknown` with: `履歴データはまだありません / History data is not yet available`.

Safety rules:

- Do not include secrets, tokens, ARNs, account details, emails, local paths, hostnames, worker PC identity, run contents, conversation metadata, provider prompt/output, or audit detail.
- Do not put direct private API endpoints in the snapshot.
- Do not claim production, 24/7 operation, restored Discord, or completed Google Login from this contract.

Local commands:

```powershell
cd status.yonerai.com
node tools/validate-status-snapshot.mjs status-snapshot.example.json
node tools/build-status-source-from-snapshot.mjs status-snapshot.example.json generated/status-feed.source.from-snapshot.json
node tools/build-status-pipeline.mjs status-snapshot.example.json generated/from-snapshot
node tools/sync-status-public-feed.mjs --input status-snapshot.example.json --public generated/snapshot-sync/status-feed.json --workdir generated/snapshot-sync/work
```
