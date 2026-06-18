# YonerAI Status implementation contract

This document defines the reusable implementation rules for the YonerAI status page.
The goal is to keep the page feed-driven, visually consistent, and safe to reuse in other projects without reintroducing duplicate rendering, broken hover behavior, or conflicting animations.

## Purpose

- This is a status-page UI shell, not a live monitoring claim.
- The current production-safe default is preparation mode: gray bars, no uptime claim, no live incident claim.
- `?mockStatus=1` is a display/runtime test mode. It must never be presented as real YonerAI monitoring data.
- Real operation must come from a feed with the same contract as the mock feed, not from hardcoded DOM panels.

## File ownership

- `index.html`, `jp/index.html`, `en/index.html`
  - Own static fallback markup, metadata, and script/style loading.
  - Must start with `data-status-runtime="loading"` on `<html>` so fallback animation cannot run before the runtime feed decides ownership.
  - Must not contain real incident or uptime claims.
- `styles.css`
  - Own base layout and no-JS fallback visuals.
  - Must not own runtime feed animation behavior.
  - Must not add bar hover/selected rules that fight runtime classes.
- `runtime-status.css`
  - Own runtime-only overrides, dark/light theme, route detail panels, status bar states, and feed animation.
  - Must be written so feed bars and fallback bars are visually separated by attributes/classes.
- `mock-status-adapter.js`
  - Own feed loading, feed normalization, category aggregation, DOM rendering, route handling, selected state, hover tooltip, touch tooltip, and animation triggers.
  - Must be replaceable by a real feed adapter without changing the UI structure.
- `status-feed.mock.json`
  - Own mock runtime data only.
  - The mock data is allowed to show colored states for UI testing.

## Feed contract

The runtime adapter expects a feed-like object with these concepts:

- `schema_version`: feed schema identifier.
- `mode`: for example `mock`, `staging`, or `live`.
- `generated_at`: ISO timestamp or display-safe timestamp.
- `states`: status definitions such as `operational`, `degraded`, `partial_outage`, `major_outage`, `maintenance`, `not_started`, `alpha_only`.
- `categories`: top-level status groups.
- `categories[].children`: component rows under a category.
- `categories[].children[].days`: 90-day bar data.
- `incidents`: optional incident/detail records.

Required day fields:

- `date`: stable ISO-like date key, for example `2026-04-26`.
- `state`: status key from `states`.
- `label`: localized display label.
- `color`: optional per-day `#RRGGBB` override. If present, the runtime must carry it through normalization and use it for the bar, selected highlight, tooltip/detail accent, and category overview when that day becomes the worst category state.
- `detail`: optional detail text.
- `incident_id`: optional incident route target.

Reference integrity:

- If a day has `incident_id`, exactly one matching `incidents[].id` must exist in the same feed/source.
- Missing incident targets are data-contract failures, not UI fallback cases. Do not render a placeholder incident page for a broken reference.
- Source and monitor examples must keep the same rule so the reusable pipeline can be tested without hand-editing UI panels.
- Feed/source/monitor JSON examples should be written as BOM-free UTF-8 to keep Node validation and generation deterministic.

Aggregation rule:

- A category overview bar is derived from its child bars.
- The category state must be the worst child state for that date.
- Category overview must use the same status/color logic as component rows.
- When the worst child day has a per-day `color`, the category overview must preserve that color instead of falling back to the generic state color.
- Do not hardcode a separate category timeline that can drift from the component rows.

## Runtime invariants

These are mandatory. If any one is violated, UI bugs such as double bars, duplicate panels, stuck highlights, or broken waves can return.

- The runtime adapter must initialize once per page. It must not register duplicate `message`, custom feed, hash, or resize handlers.
- Feed application must have a single accepted sequence. An old fetch/reload result must not overwrite a newer direct feed update.
- Invalid direct/event feed input must fail before advancing the accepted sequence. A malformed event feed must not cancel a valid pending `reload()` or leave partially-rendered DOM.
- `reload()` must fetch and normalize the next feed before advancing the accepted sequence. If fetch, parse, or normalization fails, keep the last valid rendered feed and mark `data-status-feed-error`; do not clear the page into a half-rendered state.
- Server-Sent Events must parse first, then pass the complete feed through the same safe feed replacement path as `yonerai-status:set-feed`. A bad SSE payload may set `data-status-feed-event-error`, but it must not mutate the current rendered feed.
- Feed replacement must clear cascade timers, pending route timers, selected state, wave classes, touch tracking, tooltip state, and stale panels before scheduling the next route sync.
- `YonerAIStatusRuntime.setFeed(feed, options)` and the `yonerai-status:set-feed` event must support non-animated live updates with a `source` label, so internal monitors can update the UI without hardcoded DOM edits.
- Feed-rendered bars must always have `data-status-runtime="feed"`.
- After runtime render, `document.querySelectorAll(".bar:not([data-status-runtime='feed'])").length` must be `0` inside runtime status rows.
- `renderBars()` must only run against an empty parent, or must clear the parent before append.
- Only `.bar[data-status-runtime="feed"].is-runtime-cascade` may run the feed cascade keyframes.
- Fallback bar animation must be disabled while `html[data-status-runtime="loading"]` or `html[data-status-runtime="feed"]`.
- There must be one selected bar at most.
- During cascade, selected highlights must be cleared or visually suppressed.
- A selected bar must not wave, depress, scale, or inherit hover transforms.
- Selection is route-owned. Overview, incident, and invalid routes must have zero selected bars.
- Any deferred selection timer must be canceled when the route leaves a valid status route, when feed changes, and when a route target is not found.
- Hover must be row-level on `.bars`, not separate `pointerenter` handlers on every bar.
- Pointer movement over gaps between bars must resolve to the nearest bar in the same `.bars` row.
- Tooltip movement must be driven from one owner path. Do not mix bar-level and row-level tooltip movement.
- Tooltip content must not be rebuilt on every pointer move over the same anchor. Move position only unless the anchor changed.
- Touch tooltip must remain visible after finger release until another bar/area is touched or the page scrolls.
- Incident/detail panels must be generated from route/feed state, not duplicated from hardcoded fallback content.
- Runtime status detail panel and incident detail panel are singletons. At most one of each may exist, and stale panels must be removed before inserting a new one.
- Navigating back from a status detail route must clear stale selected state unless the current route still points at the same bar.
- No visible text may become `[object Object]`.
- `__category__` is a reserved component id for category overview routes and must not be accepted as a real child component id.
- Runtime-only CSS should be scoped under `html[data-status-runtime="feed"]` unless it is deliberately theme-level styling.
- `data-theme` is the only theme source of truth.
- Locale pages must not drift structurally. `/`, `/jp/`, and `/en/` must share template ids and runtime script contracts.

## Animation rules

- Page-load bar cascade is a runtime behavior.
- Page-load cascade must reveal bars from left to right, once.
- Expanding a category may trigger child-row cascades, but it must not retrigger parent cascades.
- Closing a disclosure must animate layout height, opacity, and clip, not force an instant `hidden` state before the transition finishes.
- Do not animate the same property from multiple independent systems at once.
- In particular, `transform` must not be owned simultaneously by selected highlight, hover wave, and cascade.
- If a new animation needs `transform`, it must document which state class owns it and which other state classes disable it.
- Respect `prefers-reduced-motion`.

Relevant platform references:

- MDN `animation`: multiple animations can compete for properties such as `transform`; the winning animation can override the other.
- MDN `animation-fill-mode`: delayed/finished animations can keep start/end styles, so use it carefully on elements that also receive runtime classes.
- MDN Pointer Events: pointer movement and pointer capture can retarget events, so hover and touch should have a single owner path.

## Route contract

Supported route shapes:

- `#status/<category-id>/<component-id>/<date>/<state>`
- `#status/<category-id>/__category__/<date>/<state>`
- `#incident/<incident-id>`

Legacy test routes may be supported only as aliases:

- `#status-test-<index>-<state>`
- `#incident-test-<index>-<state>`

Route behavior:

- A status route selects exactly one matching bar and opens exactly one detail panel.
- If a status route contains a stale state for the selected date, the runtime must canonicalize the hash to the actual feed day state before presenting the detail panel.
- An incident route shows the incident detail page and hides the normal status list if the route is intended as a detail-only view.
- Returning to the base URL must restore the normal status overview with no stale selected highlight.

## Theme contract

- Theme is a visual layer only. It must not change runtime state or feed selection.
- The theme toggle should set one source of truth, for example `data-theme`.
- Dark mode and light mode must share the same layout dimensions.
- Detail panels, affected components, updates timeline, tooltip, buttons, and nested child detail cards must all have both light and dark styles.
- Light mode may use a subtle grid background, but it must not introduce a colored page wash that makes text feel selected or disabled.

## Change protocol

Before changing runtime behavior:

- Create a backup under `backups/Statusweb-before-<short-change>-<yyyymmdd-hhmmss>`.
- State which file owns the change: `HTML fallback`, `base CSS`, `runtime CSS`, `runtime adapter`, or `feed`.
- Do not edit multiple ownership layers for one bug unless the reason is explicit.
- If changing routes or feed schema, update this document first.
- If changing animation, write down the trigger class, cancellation condition, and selected-state interaction.
- Update cache/version strings in all three HTML entrypoints when browser cache would hide the change.
- If changing `/`, also check whether `/jp/` and `/en/` need the same structural change. Locale pages may differ by language and metadata only.
- If changing tooltip behavior, define whether the owner is bar rows, affected segments, or incident timelines. Do not add another independent tooltip owner.
- If changing live feed wiring, define the sequence/cancellation mechanism before adding the new input path.

## Manual QA checklist

Run these checks against the local status page when behavior changes:

- Open `http://localhost:5500/?mockStatus=1&cacheBust=<change-id>`.
- Console has no errors or warnings from the status runtime.
- `document.documentElement.dataset.statusRuntime === "feed"`.
- `document.querySelectorAll(".bar:not([data-status-runtime='feed'])").length === 0`.
- Runtime adapter global event handlers are not duplicated after reload or repeated script insertion.
- Repeated `setFeed()` calls do not increase category count, bar count, tooltip count, or panel count.
- Invalid `reload()` and malformed Server-Sent Event payloads keep the last valid feed visible and do not duplicate categories, bars, status panels, or incident panels.
- During initial cascade, animation names are only `runtimeBarCascade` and `none`.
- After cascade completes, every bar has `animationName === "none"`.
- After cascade completes, no `.is-cascade-prep`, `.is-cascading`, `.is-cascade-pending`, or `.is-runtime-cascade` remains.
- A status route produces one selected bar, not two.
- Leaving a status route clears stale selected highlights.
- Incident, overview, and invalid routes produce zero selected bars.
- A stale hash or missing feed target does not leave an old status panel visible.
- Hovering bar gaps still moves the tooltip to the nearest bar.
- Moving the mouse across bars does not flicker the tooltip.
- Pointer movement over the same bar updates tooltip position without rebuilding tooltip content.
- On mobile/touch, dragging across bars shows the tooltip and keeps it visible after finger release.
- Opening and closing category rows animates layout without a final stutter.
- Opening and closing child detail rows animates layout without a final stutter.
- Dark mode keeps all text readable, including updates timeline and child detail cards.
- Light mode keeps status detail panels visually neutral and not washed out.
- `?mockStatus=1` text clearly says mock/display test and does not claim real monitoring.
- Japanese visible copy and metadata contain no mojibake.
- `/`, `/jp/`, and `/en/` share the same template ids and runtime script version.

## Anti-patterns that caused prior bugs

- Running fallback CSS animation and runtime cascade on the same bars.
- Binding pointer events to every bar and also to the parent `.bars` row.
- Using hover `transform` on selected bars.
- Allowing selected highlights to persist during a fresh cascade.
- Rendering hardcoded incident/detail cards outside the feed adapter.
- Creating category overview bars independently instead of deriving them from children.
- Hiding disclosure content before the closing transition finishes.
- Styling dark mode only for parent cards while nested cards stay light.
- Leaving old `reload()` promises able to overwrite newer feed data.
- Rebuilding tooltip DOM on every pointer movement over the same bar.
- Letting locale HTML copies drift from the root template.
- Letting fallback JS operate on `.runtime-tooltip`.

## Real monitoring integration checklist

When replacing the mock feed with a real feed:

- Keep the same normalized feed shape.
- Keep state color mapping in data or a single adapter map, not scattered CSS literals.
- Treat missing data as `not_started` or `no_data`, never as operational.
- Do not show uptime percentages until real uptime windows are collected.
- Do not show incident history until factual incident records exist.
- Keep mock mode visibly marked as mock or display test.
- Add schema validation before rendering external feed data.
- If feed loading fails, fall back to preparation mode, not green operational mode.

## 2026-06-01 runtime/feed ownership update

- `index.html`, `jp/index.html`, and `en/index.html` load `runtime-status.css` after `styles.css` so runtime-only visual fixes are not hidden by the older base stylesheet.
- `mock-status-adapter.js` is the single owner for feed rendering when a feed is active. It exposes `window.YonerAIStatusRuntime.setFeed()`, `reload()`, `syncRoute()`, `getFeed()`, and `getState()`.
- `status-feed.mock.json` is now a `yonerai.status.feed.v1` sample feed. It is not production monitoring data; it is a reusable adapter contract fixture.
- Normal preparation categories remain gray and unclaimed. Only `status-bar-test` intentionally contains colored daily states and incident timeline fixtures.
- Category overview bars must be derived from child/component day states by severity. Do not hard-code parent category bars separately.
- Status detail routes use `#status/<category-id>/<component-id>/<date>/<state>`. Category overview rows use the reserved component id `__category__`.
- Incident routes use `#incident/<incident-id>`. Legacy `#incident-test-*` and `#status-test-*` routes are compatibility only.
- Selected bar highlight is route-owned. Rendering overview or replacing a feed must clear stale selected bars before cascade animation starts.

## 2026-06-01 interaction guard update

- Runtime bar wave animation now avoids re-applying wave classes while the pointer stays on the same bar. This prevents hover flicker caused by class churn.
- Runtime selected bars use a color-matched ring without vertical depression. The selected state is route-owned and should not participate in hover wave transforms.
- Runtime tooltip motion is owned by the adapter's requestAnimationFrame interpolation. CSS no longer adds a second transform transition on top of it.
- Affected incident segments use the same runtime tooltip surface as 90-day bars. Segment tooltip text must come from feed `affected.segments[].tooltip`.
- Invalid status or incident routes must clear stale selected state, remove panels, and return `data-status-route` to `overview`.

## 2026-06-01 reusable runtime artifacts

- `STATUS_RUNTIME_USAGE.md` explains how another project or internal monitoring layer should call the runtime API.
- `status-feed.example.json` is the minimal reusable `yonerai.status.feed.v1` fixture for category, component, colored day bar, status detail, affected window, and updates timeline output.
- `status-feed.scenarios.source.example.json` is the clean Japanese/English source fixture for generating feed-driven categories, components, bar colors, status details, affected windows, and updates timelines without hand-writing final day arrays.
- `status-feed.scenarios.example.json` is the clean Japanese/English state-scenario fixture for testing feed-driven categories, components, bar colors, status details, affected windows, and updates timelines without hardcoding DOM.
- `status-feed.schema.json` is the portable final-feed JSON Schema for other projects. It must include the fields the runtime actually renders, including `range`, `states`, category/component `days`, `day.message`, `day.detail`, incident `affected.category_id`, `affected.component_id`, `affected.segments`, and `updates`.
- Do not add new status rows by hand-editing DOM in `index.html`. Add them to a feed and let `mock-status-adapter.js` render them.
- When a production endpoint exists, prefer `/status-feed.json` or another same-origin JSON endpoint and load it through `YonerAIStatusRuntime.reload(url)`.

## 2026-06-01 validation and production bootstrap artifacts

- `tools/validate-status-feed.mjs` is a dependency-free feed contract validator. Use it before publishing a feed or porting this page to another project.
- `status-runtime-bootstrap.example.js` shows the production pattern for polling a same-origin status feed and applying it through `YonerAIStatusRuntime.reload()`.
- Do not load the production bootstrap from `index.html` until a real feed endpoint exists. Mock feed display must not be confused with live monitoring.

## 2026-06-01 source-to-feed builder artifacts

- `status-feed.source.example.json` is a compact source fixture for internal monitoring data or other projects.
- `tools/build-status-feed.mjs` expands source data into `yonerai.status.feed.v1` without requiring manual 90-day day arrays.
- Builder-generated affected count labels must be localized. Japanese should not inherit English UI copy such as `1 affected component`.
- If one incident affects multiple component routes, the builder must count unique component routes and must not auto-fill a single `affected.component_id`. Single-component incidents may auto-fill the exact component route for clickable detail navigation.
- Builder-generated incident data must preserve exact affected routes in `affected.components[]`. This keeps category/component identity, state, and first/last affected dates available to the runtime without inventing a fake single component.
- Source/monitor fixtures may also provide `affected.components[]` explicitly. The builder preserves explicit lists and fills missing lists from `incident_id` links.
- The intended pipeline is: internal monitor output -> source JSON -> `build-status-feed.mjs` -> `validate-status-feed.mjs` -> validated feed promotion -> runtime `reload()` or `setFeed()`.
- `tools/build-status-pipeline.mjs` must generate into `status-feed.generated.pending.json` first and promote to `status-feed.generated.json` only after final feed validation succeeds.
- A failed pipeline must not replace the last known-good public feed. `--skip-validate` is debug-only and must not be treated as a publish path.
- Keep `status-feed.mock.json` as the visual/runtime demo fixture. Use generated feeds for operational integration tests.

## 2026-06-01 source schema artifact

- `status-source.schema.json` defines the compact `yonerai.status.source.v1` input contract for `tools/build-status-feed.mjs`.
- Source schema and feed schema are intentionally separate: source is authoring/monitor-output friendly, feed is runtime-rendering friendly.
- A source file is not loaded by the browser runtime directly. It must be built into `yonerai.status.feed.v1` first.
- `status-feed.schema.json` describes the final browser feed. Cross-reference rules such as matching `incident_id` targets and exact affected component routes are enforced by `tools/validate-status-feed.mjs`.
- Final feed `affected.components[]` is the reusable drill-down contract for multi-component incidents. `affected.component_id` is only an exact shortcut for single-component incidents.
- `status-source.schema.json` and `status-monitor.schema.json` now document the same `affected.components[]` shape so integrations can choose explicit impact lists instead of relying only on builder inference.

## 2026-06-01 acceptance harness artifact

- `tools/status-runtime-acceptance.mjs` is the browser-level manual acceptance gate. It is not a replacement for visual review, but it catches duplicate panels, stale selected bars, missing runtime CSS, missing feed rendering, broken status/incident route basics, invalid reload preservation, and malformed SSE preservation.

## 2026-06-01 live bootstrap update

- `status-runtime-bootstrap.example.js` now documents three live update paths: same-origin polling, Server-Sent Events `status-feed`, and manual `yonerai-status:set-feed` dispatch.
- The bootstrap exposes `window.YonerAIStatusLive` for reload/apply/reconnect/state hooks. It remains an example and is not loaded by the static shell until a real feed endpoint exists.
- `status-runtime-bootstrap.example.js` must not register its own `yonerai-status:set-feed` listener because `mock-status-adapter.js` already owns that event. A second listener can apply the same feed twice and recreate duplicate-render bugs.

## 2026-06-01 hosting feed endpoint example

- `hosting/cloudflare-status-feed-worker.example.js` documents the same-origin JSON/SSE endpoint shape expected by `status-runtime-bootstrap.example.js`.
- The example intentionally keeps all components `not_started` and does not claim production monitoring.

## 2026-06-01 local feed dev server artifact

- `tools/status-feed-dev-server.mjs` serves the static status page and same-origin JSON/SSE feed endpoints for local runtime integration checks.
- It intentionally reads an explicit feed file and does not know private monitoring internals.

## 2026-06-01 internal monitor adapter artifacts

- `status-monitor-results.example.json` and `tools/build-status-source-from-monitor.mjs` define the monitor-output boundary before source/feed generation.
- Internal monitors should not write browser DOM or runtime panel state directly. They should output monitor result data that can be converted and validated before publication.

## 2026-06-01 monitor schema artifact

- `status-monitor.schema.json` defines the public-safe monitor result boundary. It prevents monitor integrations from inventing ad-hoc fields that bypass source/feed validation.
- Monitor result payloads are still pre-publication data and must not include private runtime truth or secrets.
- `status-monitor.schema.json` and `status-source.schema.json` both define `incidentUpdate`, `affectedSegment`, and `affected.window` shapes so malformed updates timelines and affected windows are rejected before the browser runtime renders them.

## 2026-06-01 runtime API contract artifact

- `STATUS_FEED_API.md` is the reusable contract for connecting other projects, internal monitors, same-origin JSON feeds, and SSE feeds to this status page.
- Production polling/SSE examples should call `YonerAIStatusRuntime.reload()` or `setFeed()` with `animate: false` and a clear `source` label.
- Runtime updates must replace complete feed objects after validation/normalization. They must not patch category rows, component rows, bars, selected state, detail panels, or incident timelines directly.

## 2026-06-01 feed bridge example artifact

- `tools/status-feed-bridge.example.mjs` is the reusable monitor-output bridge example. It runs the existing monitor -> source -> feed -> validate pipeline and atomically promotes the generated feed only after success.
- The bridge keeps the previous public feed when generation or validation fails. This is the same fail-closed behavior expected from the browser runtime and prevents bad monitor payloads from clearing the public UI.
- The bridge is intentionally file/feed based. It must not write DOM, selected bar state, hover state, route panels, or timeline markup directly.

## 2026-06-01 runtime copy cleanup

- Runtime-owned fallback labels in `mock-status-adapter.js` must stay clean UTF-8. Mojibake in `STATES` or `COPY` can break the adapter before feed data is rendered.
- Runtime fixed copy is limited to UI chrome such as scale labels, detail field labels, back buttons, affected-component headings, and safety fallback text.
- Service truth, component names, day labels, day details, incident summaries, affected windows, update timelines, and status colors still come from the feed.
- Separator copy used by runtime-generated meta text should be stable (` ・ `) and must not leak mojibake into Japanese pages.

## 2026-06-01 runtime readiness event

- `mock-status-adapter.js` emits `yonerai-status-runtime-ready` after `window.YonerAIStatusRuntime` is assigned.
- `status-feed-client.example.js` uses that event inside `waitForRuntime()` and keeps a polling fallback for unusual script order.
- The ready event is not a rendering path. Integrations must still apply complete feeds through `trySetFeed()`, `reload()`, `applyWhenReady()`, or `loadWhenReady()`.
- Do not attach DOM patching, tooltip binding, or a second `yonerai-status:set-feed` listener from the ready event.

## 2026-06-01 feed text safety validation

- `tools/validate-status-feed.mjs` now fails localized display text that appears to contain mojibake, replacement characters, `[object Object]`, `undefined`, or `null` literals.
- This check applies to feed-owned public text such as component names, facts, monitoring labels, claims, day labels/messages/details, incident copy, affected labels, segment tooltips, and update timelines.
- Public feed producers must fix encoding/source data before publication instead of relying on browser fallback copy.

## 2026-06-01 source and monitor text safety validation

- `tools/validate-status-input.mjs` now applies the same public text safety gate before source/monitor data is converted into the final browser feed.
- Mojibake, replacement characters, `[object Object]`, `undefined`, and `null` literals must be fixed at the monitor/source boundary, not after they become rendered feed output.
- This keeps upstream integrations reusable: a monitor adapter can fail before publishing broken public copy or broken timeline text.

## Runtime Feed UI/UX Contract - 2026-06-01

This status page is reusable only when the feed runtime owns the rendered status table.
The static HTML is a boot shell and safe fallback, not the source of truth for component rows.

Required runtime invariants:

- `status-feed.json` is the production/public feed. `status-feed.mock.json` is loaded only with `?mockStatus=1` or an explicit same-origin feed override.
- `/`, `/jp`, and `/en` must reference the same cache version for `styles.css`, `runtime-status.css`, and `mock-status-adapter.js`.
- `mock-status-adapter.js` must disconnect an older runtime instance before installing listeners again. This prevents duplicate pointer, hash, and reload handlers.
- The runtime route format is `#status/{categoryId}/{componentId}/{date}/{state}`. Unknown legacy demo hashes must safely return to overview instead of hiding the table.
- Closed disclosure panels must not leak children into layout or hit testing. Closed panels are hidden; open panels participate in normal document flow.
- A collapsed child row must never overlap the next category row. Hover hit testing must resolve to the visual row under the pointer.
- Base feed bars must have no stale transform. Only these states may transform bars: cascade reveal, hover wave, and explicit selected-state styling.
- Tooltip position is JS-owned. CSS may fade opacity/visibility but must not add a competing transform transition.
- Selected bars are route-owned. Returning to overview must clear selected bars, tooltip state, wave classes, and route panels.
- Category overview rows may aggregate child states, but drill-down rows must keep the component/day identity needed for real incidents and future monitoring data.

Regression checks:

- Run `node status.yonerai.com/tools/validate-status-feed.mjs status.yonerai.com/status-feed.json`.
- Run `node status.yonerai.com/tools/validate-status-feed.mjs status.yonerai.com/status-feed.mock.json`.
- Run `node status.yonerai.com/tools/status-uiux-smoke.mjs`.
- Browser smoke must confirm: `data-status-runtime=feed`, zero fallback bars, expected category/bar counts, no stale selected bar after overview, and correct `elementFromPoint` on a colored mock bar.
