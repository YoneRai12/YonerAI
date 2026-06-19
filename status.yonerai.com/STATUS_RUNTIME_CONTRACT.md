# YonerAI Status runtime contract

This page is a reusable status UI. Keep the runtime ownership boundaries strict.

## Ownership

- `index.html` owns the static shell only: templates, base markup, theme bootstrap, and script loading.
- `status-feed.json` owns public status data.
- `status-feed.mock.json` owns display-test data only.
- `mock-status-adapter.js` owns feed normalization, category rendering, bars, selected state, tooltip state, route handling, status detail panels, incident detail panels, and polling.
- `styles.css` owns presentation and animation only. CSS must not rely on mock-only class names for production behavior.

## Feed switching

- Default URL uses `/status-feed.json`.
- `?feed=/path.json` explicitly replaces the feed source.
- `?mockStatus=1` explicitly uses `/status-feed.mock.json`.
- Legacy `#status-test-*` and `#incident-test-*` hashes may auto-load mock data on localhost or file URLs only.
- Public `status.yonerai.com` must not load mock data just because a legacy test hash is present.

## Rendering invariants

- Runtime feed bars must have `data-status-runtime="feed"`.
- A healthy runtime exposes `html[data-status-runtime-global="ready"]`, `html[data-status-runtime-api="ready"]`, and `html[data-status-feed-applied]` after feed render.
- External harnesses may wait for `yonerai-status-runtime-ready` and `yonerai-status-feed-applied`, or read `window.yoneraiStatusGetState()` when page context access is available.
- A healthy render has zero legacy bars: `.bar:not([data-status-runtime="feed"])` must be `0`.
- Overview routes show notice, system status, history button, and past incidents.
- Incident routes hide overview sections and render exactly one `#incidentDetailPanel`.
- Missing incident routes return to overview and set `html[data-status-route-type="overview"]`.
- Missing or stale status routes return to overview; stale state hashes are canonicalized to the actual feed state when the date exists.
- Status routes render at most one selected bar and at most one status detail panel.
- Component status routes open the owning category before selection so the selected bar is visible and hit-testing stays aligned.

## Interaction invariants

- Selection state is owned by the runtime and must be cleared before a route change or re-render.
- Hover state is owned by the runtime and must be cleared before a route change or re-render.
- Tooltip movement is driven by JS transform smoothing. CSS should not add a competing transform transition.
- Touch input must use the same nearest-bar logic as pointer input, so dragging across bar gaps still resolves to the nearest day.

## Verification URLs

- Public pre-operations feed:
  `https://status.yonerai.com/?cacheBust=manual`
- Local pre-operations feed:
  `http://localhost:5500/?cacheBust=manual`
- Local mock feed:
  `http://localhost:5500/?mockStatus=1&cacheBust=manual`
- Explicit feed override:
  `http://localhost:5500/?feed=/status-feed.mock.json&cacheBust=manual`
- Status detail example:
  `http://localhost:5500/?mockStatus=1&cacheBust=manual#status/status-bar-test/status-bar-test-component/2026-04-26/degraded`
- Incident detail example:
  `http://localhost:5500/?mockStatus=1&cacheBust=manual#incident-test-81-maintenance`
