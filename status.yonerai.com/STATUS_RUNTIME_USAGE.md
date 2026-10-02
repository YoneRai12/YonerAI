# YonerAI Status runtime usage

This page is a reusable status-page shell. The UI is rendered from a public status feed. Do not add categories, bars, details, or incident timelines by hand-editing DOM in `index.html`.

For the reusable integration contract, see `STATUS_FEED_API.md`.

## Runtime API

The browser runtime is exposed as `window.YonerAIStatusRuntime` after `mock-status-adapter.js` loads.

```js
await window.YonerAIStatusRuntime.reload('/status-feed.json', {
  animate: false,
  source: 'polling'
});

const appliedFeed = window.YonerAIStatusRuntime.setFeed(nextFeed, {
  animate: false,
  source: 'internal-monitor'
});

window.YonerAIStatusRuntime.syncRoute();
window.YonerAIStatusRuntime.getFeed();
window.YonerAIStatusRuntime.getState();
```

`reload(url, options)` accepts same-origin URLs only. On Cloudflare Zero Trust or Tunnel, expose the feed as same-origin paths such as `/status-feed.json` and `/status-feed/events`.

`reload()` is fail-closed for already rendered pages. It fetches and normalizes the next feed before advancing the accepted runtime sequence. If fetch, JSON parse, or feed normalization fails after a valid feed is already visible, the page keeps the last rendered feed and marks `<html data-status-feed-error="reload-failed">`.

## Event-based update

An internal status bridge can update the UI without touching DOM:

```js
document.dispatchEvent(new CustomEvent('yonerai-status:set-feed', {
  detail: nextFeed
}));
```

or with options:

```js
document.dispatchEvent(new CustomEvent('yonerai-status:set-feed', {
  detail: {
    feed: nextFeed,
    options: { animate: false },
    source: 'internal-monitor'
  }
}));
```

When a feed is applied, the runtime dispatches:

```js
document.addEventListener('yonerai-status-feed-applied', (event) => {
  console.log(event.detail.version, event.detail.source, event.detail.feed);
});
```

Invalid event feeds are rejected before replacing the active feed. The page keeps the last valid rendered state and sets `data-status-feed-event-error="invalid-feed"` on `<html>`. Server-Sent Event payloads use the same safe replacement path after JSON parsing, so a malformed SSE message cannot partially redraw the status list.

## Feed ownership

A feed owns these public UI surfaces:

- category rows
- component rows
- 90-day status bars
- per-day bar color
- status detail panel content
- affected component timeline
- incident updates timeline
- route targets

The runtime owns these behaviors:

- category overview aggregation from child component days
- selected bar state
- route synchronization
- tooltip and touch tooltip binding
- detail panel singleton rendering
- incident panel singleton rendering
- cascade and disclosure animation triggers

## Feed shape

A reusable feed must provide:

- `schema_version`: `yonerai.status.feed.v1`
- `generated_at`: display-safe timestamp
- `range.days`: number of bars, usually `90`
- `range.start` and `range.end`: ISO date strings
- `states`: state label and color map
- `categories[]`: top-level status groups
- `categories[].children[]`: component rows
- `categories[].children[].days[]`: day bars
- `incidents[]`: incident records, empty array when none exist

Day fields:

- `index`: zero-based day index
- `date`: `YYYY-MM-DD`
- `state`: status key
- `label`: localized label, optional
- `color`: optional `#RRGGBB` per-day override
- `message`: tooltip/detail summary source, optional
- `detail.summary`: status detail body, optional
- `incident_id`: optional incident route target

If `day.color` exists, the runtime uses it for the component bar, selected ring, status detail accent, and the category overview bar when that day becomes the category's worst state.

`tools/build-status-feed.mjs` emits `day.index` and resolves `day.color` from the daily override first, then `states[state].color`. This keeps generated feeds visually complete even when an internal monitor only sends state keys.

## Route contract

Supported routes:

```text
#status/<category-id>/<component-id>/<date>/<state>
#status/<category-id>/__category__/<date>/<state>
#incident/<incident-id>
```

`__category__` is reserved for category overview rows. Do not use it as a real component id.

Legacy test routes are compatibility aliases only:

```text
#status-test-<index>-<state>
#incident-test-<index>-<state>
```

If a status route contains a stale `state`, the runtime canonicalizes the hash to the actual feed day state before showing detail.

## Source-to-feed pipeline

For real monitoring integration, prefer this pipeline:

```text
internal monitor output
  -> yonerai.status.monitor.v1
  -> tools/build-status-source-from-monitor.mjs
  -> yonerai.status.source.v1
  -> tools/build-status-feed.mjs
  -> yonerai.status.feed.v1
  -> tools/validate-status-feed.mjs
  -> YonerAIStatusRuntime.reload() or setFeed()
```

Monitor/source inputs should contain only public-safe status information. Do not include secrets, private runtime inventory, break-glass details, raw production routing, user data, or control-plane internals.

When source days reference `incident_id`, `tools/build-status-feed.mjs` collects the matching category/component routes and uses them to fill incident affected metadata. If exactly one component route is affected, it fills `affected.category_id` and `affected.component_id`. If multiple component routes are affected, it fills localized `affected.name`, `affected.count`, and the affected window without pretending that one component is the only target.

If `affected.count` is missing, `tools/build-status-feed.mjs` generates a localized count label. Japanese output uses `N件の影響コンポーネント`; English output uses singular/plural `N affected component(s)`.

Example files are intentionally split by pipeline stage:

- `status-monitor-results.example.json`: monitor-output shaped input for an internal bridge.
- `status-feed.source.example.json`: public-safe source input for `tools/build-status-feed.mjs`.
- `status-feed.scenarios.source.example.json`: clean state-scenario source fixture for generating category/component/bar/detail/incident/timeline output without hand-writing the final day array.
- `status-feed.example.json`: final browser feed shape.
- `status-feed.scenarios.example.json`: clean state-scenario final feed fixture for category/component/bar/detail/incident/timeline rendering.
- `status-feed.schema.json`: portable JSON Schema for the final browser feed shape.
- `tools/status-feed-bridge.example.mjs`: monitor-output to validated public feed publisher example.

All three examples are display-test data. They should stay valid JSON and should stay free of private infrastructure detail.

`status-feed.scenarios.source.example.json` is the preferred authoring fixture when checking that UI surfaces can be generated from compact source data rather than hardcoded DOM or hand-written final day arrays. `status-feed.scenarios.example.json` is the equivalent final-feed fixture for runtime checks. Both intentionally include Japanese copy, multiple states, colored bars, incident summaries, affected windows, and updates timelines.

Generate the source scenario fixture into a final feed with:

```powershell
node status.yonerai.com/tools/build-status-feed.mjs status.yonerai.com/status-feed.scenarios.source.example.json status.yonerai.com/generated/status-feed.scenarios.generated.json
```

Incidents can carry exact impacted surfaces with `affected.components[]` at any stage:

- monitor input may provide it directly when the monitor already knows impacted component routes
- source input may provide it directly for hand-authored or upstream-normalized public incidents
- final feed always receives it when day-level `incident_id` links can be resolved by the builder

Each affected component entry should include `category_id`, `component_id`, and optionally `name`, `state`, `date`, `end_date`, `date_label`, and `end_date_label`.

## Validation before publishing

Run validators before publishing or connecting a real endpoint:

```powershell
node status.yonerai.com/tools/validate-status-input.mjs status.yonerai.com/status-monitor-results.example.json
node status.yonerai.com/tools/build-status-pipeline.mjs status.yonerai.com/status-monitor-results.example.json status.yonerai.com/generated
node status.yonerai.com/tools/validate-status-feed.mjs status.yonerai.com/generated/status-feed.generated.json
```

`tools/build-status-pipeline.mjs` writes `status-feed.generated.pending.json` first. It only promotes that file to `status-feed.generated.json` after final feed validation succeeds. If validation fails, keep serving the previous valid `status-feed.generated.json`.

`tools/status-feed-bridge.example.mjs` wraps that pipeline for local or hosting-layer integration. It writes a public feed file only after the pipeline succeeds, so `tools/status-feed-dev-server.mjs` can serve the last known-good feed and push changes over SSE when the file changes.

`--skip-validate` is a debug-only escape hatch. Reports created with that flag use `feed_promotion: "unvalidated-debug"` and should not be published as the public status feed.

The feed validator checks:

- schema version
- range dates and day count
- category/component/incident ids
- reserved `__category__` misuse
- category children sharing the same ordered day dates for aggregate bars
- day index/date/state
- day color format
- localized component facts, monitoring text, claims, day labels, messages, and detail summaries
- `day.incident_id` resolving to `incidents[].id`
- `incidents` existing as an array
- incident meta, summary, footer, updates, and affected component structure
- affected component route references when `affected.category_id` and `affected.component_id` are supplied
- affected component list route references when `affected.components[]` is supplied
- affected segment state/color/tooltip and percent totals

`status-feed.schema.json` is useful for editor integration and external project reuse. `tools/validate-status-feed.mjs` is still required before publishing because it enforces cross-field rules that JSON Schema cannot express cleanly, such as day date alignment, incident reference integrity, and affected component route integrity.

`tools/validate-status-input.mjs` performs the same kind of public-shape checks before generation for `yonerai.status.monitor.v1` and `yonerai.status.source.v1`: range, category/component ids, result/day dates, state keys, colors, localized copy, incident references, affected segments, `affected.category_id/component_id`, and `affected.components[]` route references when supplied.

`status-source.schema.json` and `status-monitor.schema.json` also define the public shape for incident `updates[]`, `affected.window`, and `affected.segments[]`. Integrations should satisfy those schemas before relying on browser rendering, because malformed timeline entries or affected-window segments can otherwise become UI bugs rather than feed errors.

## Live update options

Supported update paths:

- polling: `YonerAIStatusRuntime.reload('/status-feed.json', { animate: false, source: 'polling' })`
- Server-Sent Events: `/status-feed/events` emits `status-feed` events with complete feed JSON
- manual event: `yonerai-status:set-feed` for compatibility only; prefer `YonerAIStatusFeedClient.applyWhenReady()` when load order is uncertain
- direct API: `YonerAIStatusRuntime.trySetFeed(feed, options)` or `YonerAIStatusRuntime.setFeed(feed, options)`

Do not add another listener for `yonerai-status:set-feed` in a production bootstrap. The runtime adapter already owns that event. A second listener can apply the same feed twice and reintroduce duplicate render bugs.

Live updates should normally use `animate: false` so a real-time status change does not replay the full page-load cascade.

If a live update fails validation or normalization, keep serving the last valid feed. Do not replace the UI with partial data. A new feed should become visible only after the full feed object passes normalization and wins the runtime sequence check.

## Production safety

- Missing data must render as `not_started` or another explicit non-operational state, never as operational by default.
- Do not show uptime percentages until real uptime windows are collected.
- Do not show incident history until factual public incident records exist.
- Mock/demo feeds must remain visibly marked as mock or display test.
- If feed loading fails, fall back to preparation mode rather than green operational mode.
- For multi-component incidents, render from `incident.affected.components[]` rather than deriving affected surfaces from copy text. This keeps the UI reusable when a real monitor supplies many impacted components.

## Manual QA checklist

Before calling the page reusable, check:

- `document.documentElement.dataset.statusRuntime === 'feed'`
- there are no `.bar:not([data-status-runtime='feed'])` inside runtime rows
- repeated `setFeed()` calls do not duplicate categories, bars, panels, or tooltips
- invalid `reload()` keeps the last valid feed visible and sets `data-status-feed-error="reload-failed"`
- malformed SSE `status-feed` payloads keep the last valid feed visible and set `data-status-feed-event-error="parse"`
- status route shows exactly one selected bar and one status detail panel
- incident route shows incident panel and no stale selected bar
- returning to overview clears selected state
- hover over gaps chooses the nearest bar and does not flicker
- touch drag over bars shows the tooltip and keeps it visible after finger release
- dark/light mode keeps all text readable
- mobile layout keeps route panels and timelines readable

## Runtime readiness

`mock-status-adapter.js` emits `yonerai-status-runtime-ready` once the runtime object exists. `status-feed-client.example.js` waits for that event and also keeps a short polling fallback, so another project can load the helper before or after the runtime script.

Preferred load-order safe pattern:

```js
await window.YonerAIStatusFeedClient.loadWhenReady('/status-feed.json', {
  animate: false,
  source: 'internal-monitor'
});
```

Do not use the ready event as a second rendering path. It is only a readiness signal.

Feed text safety is part of publishing. `tools/validate-status-feed.mjs` rejects localized display text that looks like mojibake or unsafe runtime leakage such as `[object Object]`, `undefined`, or `null`. Fix the source or monitor adapter before serving the feed.

Source and monitor inputs also have text safety gates. `tools/validate-status-input.mjs` rejects public-facing localized text that appears to contain mojibake or runtime leakage before `tools/build-status-feed.mjs` generates the final browser feed.
