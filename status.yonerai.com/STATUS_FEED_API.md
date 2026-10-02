# YonerAI Status feed API contract

This document is the reusable integration contract for connecting YonerAI Status
to an internal monitor, another project, or a hosting layer.

The status page is feed-driven. Integrations must replace the complete feed
object; they must not patch DOM nodes, bars, panels, selected state, or
timelines directly.

## Runtime surface

`mock-status-adapter.js` exposes this browser API after it loads:

```js
const runtime = window.YonerAIStatusRuntime;

await runtime.reload("/status-feed.json", {
  animate: false,
  source: "polling"
});

runtime.setFeed(nextFeed, {
  animate: false,
  source: "internal-monitor"
});

runtime.connectEvents("/status-feed/events");
runtime.disconnectEvents();
runtime.syncRoute();

const currentFeed = runtime.getFeed();
const runtimeState = runtime.getState();
```

Runtime methods:

- `setFeed(feed, options)`: validate, normalize, and render a complete feed object.
- `applyFeed(feed, options)`: compatibility alias for `setFeed(feed, options)`.
- `trySetFeed(feed, options)`: apply a feed without throwing. On invalid input it keeps the current UI and returns an error object plus runtime state.
- `validateFeed(feed)`: validate feed shape before rendering.
- `reload(url, options)`: fetch a same-origin feed URL and render it only after it is accepted.
- `refresh()`: reload the last configured same-origin feed URL.
- `connectEvents(url)`: subscribe to same-origin Server-Sent Events that emit complete `status-feed` payloads.
- `disconnectEvents()`: close the active SSE connection.
- `syncRoute()`: re-apply the current hash route after a feed update.
- `YonerAIStatusRuntime.clearInteractionState()`: clear transient tooltip, wave, touch, and selected UI state without replacing the feed.
- `YonerAIStatusRuntime.rerender(options)`: re-render the current in-memory feed without fetching a new feed.
- `YonerAIStatusRuntime.getState()`: inspect runtime diagnostics such as route, rendered counts, selected count, active panels, schema, last feed source, live status, and feed error flags.
- `YonerAIStatusRuntime.getFeed()`: return the last accepted feed object.
- `YonerAIStatusRuntime.destroy()`: remove active listeners/timers/SSE before replacing or reloading the runtime script.

Optional helper:

- `status-feed-client.example.js`: exposes `window.YonerAIStatusFeedClient.apply(feed, options)`, `applyWhenReady(feed, options, timeoutMs)`, `load(url, options)`, `loadWhenReady(url, options, timeoutMs)`, `dispatch(feed, options)`, and `waitForRuntime(timeoutMs)` for integrations that should not touch DOM internals.
- `status-runtime-bootstrap.example.js`: production bootstrap pattern for polling and SSE. It applies remote feeds through the safe runtime path and keeps the current UI when a feed is rejected.
- `getState()`: return public runtime state for diagnostics.

`options.source` should identify the integration path, for example
`"boot"`, `"polling"`, `"sse"`, `"internal-monitor"`, or `"manual"`.

Live updates should normally pass `animate: false`. Full cascade animation is
for initial display and explicit visual tests, not for frequent monitoring
updates.

## Manual feed event

The runtime already listens for `yonerai-status:set-feed`.

```js
document.dispatchEvent(new CustomEvent("yonerai-status:set-feed", {
  detail: {
    feed: nextFeed,
    options: {
      animate: false,
      source: "internal-monitor"
    }
  }
}));
```

When the helper may load before `mock-status-adapter.js`, prefer the ready-waiting
API instead of dispatching manually:

```js
await window.YonerAIStatusFeedClient.applyWhenReady(nextFeed, {
  animate: false,
  source: "internal-monitor"
});

await window.YonerAIStatusFeedClient.loadWhenReady("/status-feed.json", {
  animate: false,
  source: "polling"
});
```

Do not add another listener for this same event in a production bootstrap. A
second listener would call `setFeed()` twice and can recreate duplicate-render
bugs.

The runtime emits this event after a feed is accepted:

```js
document.addEventListener("yonerai-status-feed-applied", (event) => {
  console.log(event.detail.version, event.detail.source, event.detail.feed);
});
```

## Same-origin feed endpoints

Cloudflare Tunnel / Zero Trust should expose feed endpoints on the same origin
as the status page:

```text
GET /status-feed.json
GET /status-feed/events
```

The runtime rejects cross-origin `reload()` and SSE URLs. This keeps the static
page reusable without turning it into a generic cross-origin data fetcher.

`/status-feed.json` returns the complete `yonerai.status.feed.v1` object.

`/status-feed/events` emits complete feed objects:

```text
event: status-feed
data: {"schema_version":"yonerai.status.feed.v1", ...}
```

Malformed SSE payloads must not partially mutate the UI. The runtime parses the
payload first, then routes it through the same safe full-feed replacement path.

## Local bridge example

`tools/status-feed-bridge.example.mjs` is the reusable internal-monitor bridge
example. It converts monitor-output JSON into a validated public feed and
atomically promotes the result to a feed file.

If the upstream system only has HTTP health endpoints, YonerAI API probes, or
already-collected AWS metric values, generate the monitor-output JSON first:

```powershell
node status.yonerai.com/tools/collect-status-healthchecks.mjs `
  status.yonerai.com/status-healthcheck-input.example.json `
  status.yonerai.com/generated/status-monitor-results.generated.json
```

`collect-status-healthchecks.mjs` supports:

- `static`: deterministic fixture/manual state.
- `http`: direct HTTP healthcheck for YonerAI API or other same-controlled endpoints.
- `aws_metric`: AWS CloudWatch-style values that were collected by an external AWS job.

It intentionally does not put AWS credentials, private routes, or control-plane
details into the browser feed. Internal systems should collect those details
privately and pass only public-safe status results into this pipeline.

```powershell
node status.yonerai.com/tools/status-feed-bridge.example.mjs `
  status.yonerai.com/status-monitor-results.example.json `
  status.yonerai.com/generated/status-feed.live.json
```

Watch mode continuously rebuilds the public feed when monitor-output JSON
changes:

```powershell
node status.yonerai.com/tools/status-feed-bridge.example.mjs `
  status.yonerai.com/status-monitor-results.example.json `
  status.yonerai.com/generated/status-feed.live.json `
  --watch
```

Serve that generated feed through the same-origin dev server:

```powershell
$env:STATUS_FEED_FILE = "status.yonerai.com/generated/status-feed.live.json"
node status.yonerai.com/tools/status-feed-dev-server.mjs 5500
```

Then open:

```text
http://127.0.0.1:5500/?liveStatus=1
```

The bridge keeps the previous public feed if generation or validation fails.
That behavior is required for production-style status pages because a bad
monitor payload must not clear or partially redraw the public UI.

## Public data pipeline

Recommended production pipeline:

```text
HTTP healthcheck / YonerAI API probe / AWS metric job
  -> tools/collect-status-healthchecks.mjs
  -> yonerai.status.monitor.v1
  -> tools/build-status-source-from-monitor.mjs
  -> yonerai.status.source.v1
  -> tools/build-status-feed.mjs
  -> yonerai.status.feed.v1
  -> tools/validate-status-feed.mjs
  -> /status-feed.json or /status-feed/events
```

Only the final `yonerai.status.feed.v1` object is loaded by the browser.

Monitor/source inputs may be private build artifacts, but the final feed is a
public browser artifact. Do not include secrets, private route inventory,
break-glass details, raw user data, live control-plane internals, or production
credential material.

## Final feed ownership

The final feed owns:

- category names and order
- component names and order
- component day states
- per-day bar colors
- day messages and detail summaries
- route ids
- incident summaries
- affected component lists
- affected window segments
- incident update timelines
- localized copy that appears inside feed-rendered rows and panels

`status-feed.scenarios.source.example.json` is the clean reusable source fixture
for this contract. It demonstrates source-driven:

- category and component output from feed data
- gray preparation rows
- operational, degraded, maintenance, and major outage bar colors
- per-day status detail summaries
- incident detail cards
- affected component lists
- affected window segments
- updates timelines

Build it into a final browser feed with:

```powershell
node status.yonerai.com/tools/build-status-feed.mjs `
  status.yonerai.com/status-feed.scenarios.source.example.json `
  status.yonerai.com/generated/status-feed.scenarios.generated.json
```

`status-feed.scenarios.example.json` is the equivalent final-feed fixture for
runtime-level checks. Both files are display-test data, not real YonerAI
monitoring data.

The runtime owns:

- DOM creation
- category overview aggregation from child components
- selected bar state
- tooltip ownership
- touch tooltip behavior
- route synchronization
- singleton status detail panel
- singleton incident panel
- cascade and disclosure animation triggers
- dark/light theme application

## Category overview aggregation

Do not hand-author category overview bars separately.

For each day, the runtime derives a category overview bar from child component
days using severity order. The worst child state for that date becomes the
category overview state.

If the chosen child day has `color`, that color must propagate to the category
overview bar, selected ring, tooltip/detail accent, and any route-owned
highlight.

This keeps the top-level row consistent with the component rows and prevents
the overview from drifting when more components are added.

## Incident and affected component contract

Use `affected.components[]` for multi-component incidents:

```json
{
  "affected": {
    "name": "2 affected components",
    "components": [
      {
        "category_id": "core-api",
        "component_id": "api",
        "name": "API",
        "state": "major_outage",
        "date": "2026-05-07",
        "end_date": "2026-05-07"
      }
    ],
    "segments": [
      {
        "state": "operational",
        "percent": 8,
        "color": "#2fc6a3",
        "tooltip": "Recovered window"
      },
      {
        "state": "major_outage",
        "percent": 84,
        "color": "#f45b4f",
        "tooltip": "Incident window"
      },
      {
        "state": "operational",
        "percent": 8,
        "color": "#2fc6a3",
        "tooltip": "Recovered window"
      }
    ]
  }
}
```

For a single-component incident, `affected.category_id` and
`affected.component_id` may be present as an exact shortcut. For multiple
components, do not pretend one component is the only affected target.

## Safety behavior

The runtime is fail-closed for feed replacement:

- A new feed must parse and normalize before it replaces the current UI.
- A failed `reload()` keeps the last valid feed visible and sets a data-status error flag.
- A malformed SSE event keeps the last valid feed visible and sets a feed-event error flag.
- A stale hash is canonicalized to the current feed state or returned to overview.
- Overview and incident routes clear selected status bars.

Missing monitoring data must render as `not_started`, `maintenance`,
`alpha_only`, or another explicit non-operational/preparation state. It must not
default to `operational`.

## Minimal integration checklist

Before another project reuses the page:

- Build or provide a complete `yonerai.status.feed.v1` feed.
- Validate it with `tools/validate-status-feed.mjs`.
- For monitor-output integrations, publish through `tools/status-feed-bridge.example.mjs` or an equivalent validated atomic promotion step.
- Serve it from a same-origin URL.
- Load it with `YonerAIStatusRuntime.reload(url, { animate: false, source })` or `YonerAIStatusFeedClient.loadWhenReady(url, { animate: false, source })`.
- Use `connectEvents()` only when the endpoint emits complete feed objects.
- Do not add direct DOM writes for bars, panels, or timelines.
- Do not add a second `yonerai-status:set-feed` listener.
- Keep mock/demo feed text visibly marked as mock/display-test.
- Use `status-feed.scenarios.source.example.json` as the reference source fixture when another project wants to generate the status UI from compact monitor/source data.
- Use `status-feed.scenarios.example.json` as the final-feed fixture when checking that the browser runtime can drive all visible status surfaces.

## Runtime readiness event

`mock-status-adapter.js` dispatches `yonerai-status-runtime-ready` after `window.YonerAIStatusRuntime` is assigned.

```js
document.addEventListener('yonerai-status-runtime-ready', (event) => {
  console.log(event.detail.version, event.detail.state);
});
```

Integrations should normally call `YonerAIStatusFeedClient.applyWhenReady()` or `loadWhenReady()` instead of listening to this event directly. Direct listeners are useful for diagnostics only. Do not use the ready event to patch DOM or attach another `yonerai-status:set-feed` listener.

Feed endpoints should only serve feeds that pass text safety validation. Mojibake, replacement characters, `[object Object]`, `undefined`, and `null` literals are treated as feed errors, not display quirks.

## Public-safe StatusSnapshot ingestion

The live-ingestion path is feed-first and same-origin from the browser's point of view:

```powershell
node status.yonerai.com/tools/sync-status-public-feed.mjs `
  --input-url https://api-staging.yonerai.com/v1/status `
  --public status-feed.json `
  --workdir generated/sync `
  --refresh-ms 15000
```

Contract:

- The browser still loads only same-origin `/status-feed.json`; it must not call the staging API directly.
- `--input-url` accepts only HTTPS public-safe `yonerai.status.v1` snapshots from the approved staging status host.
- The generated feed is validated with `tools/validate-status-feed.mjs` and `tools/validate-status-public-feed-safety.mjs` before promotion.
- A validated last-known-good feed is saved under the workdir.
- Upstream failures or malformed snapshots use last-known-good fallback with `meta.live_ingestion.status="stale"` and `meta.stale=true`.
- Stale fallback degrades operational component states instead of rendering stale data as green.
- `meta.refresh_ms` provides the bounded same-origin browser refresh interval.
- Upstream errors are reported as public error classes such as `upstream_unavailable` or `upstream_invalid`; raw upstream bodies are not written to the public feed.
- Raw upstream snapshots are projected to the canonical public fields before they are cached in the StatusWEB workdir.
- This is staging/preview status ingestion only and is not a production-service claim.
