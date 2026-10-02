# YonerAI Status hosting examples

This folder contains examples for serving the public YonerAI Status feed from the same origin as the status page.

## Cloudflare Worker example

`cloudflare-status-feed-worker.example.js` is a minimal same-origin endpoint example:

- `GET /status-feed.json`
- `GET /status-feed/events`

Open the status page with live updates enabled:

```text
https://status.yonerai.com/?liveStatus=1
```

The browser runtime loads `/status-feed.json` first, then subscribes to `/status-feed/events`. Each `status-feed` Server-Sent Event must contain a complete `yonerai.status.feed.v1` JSON payload.

## Security boundary

The public feed may contain only information that is safe to show on the public status page.

Do not include:

- secrets
- private runtime inventory
- break-glass details
- raw production routing
- internal-only incident context
- raw logs
- user data

## Production flow

```text
internal monitor
-> yonerai.status.monitor.v1
-> tools/build-status-pipeline.mjs
-> tools/validate-status-feed.mjs
-> same-origin /status-feed.json
-> same-origin /status-feed/events
-> browser YonerAIStatusRuntime.setFeed()
```

If real monitoring is not connected, keep public feed entries in `not_started` or another explicitly truthful non-operational state. Do not imply production monitoring until the feed producer is actually connected.
