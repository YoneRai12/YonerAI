# YonerAI Status integration checklist

このチェックリストは `status.yonerai.com` の UI を他プロジェクトや実運用 feed へ接続するときの標準手順です。目的は、カテゴリ、コンポーネント、バー色、ステータス詳細、障害タイムラインを feed から自由に出力しつつ、UI/UX を DOM 直書きで壊さないことです。

## 1. Copy the runtime bundle

移植先へ次の bundle をコピーします。

- `index.html`
- `jp/index.html`
- `en/index.html`
- `styles.css`
- `runtime-status.css`
- `mock-status-adapter.js`
- `status-feed-client.example.js`
- `status-runtime-bootstrap.example.js`

HTML 内へサービス状態、障害、稼働率、色付きバーを直書きしません。

## 2. Keep feed ownership separate

Runtime が読むのは complete feed だけです。

- Browser runtime input: `yonerai.status.feed.v1`
- Public source input: `yonerai.status.source.v1`
- Internal monitor input: `status-monitor.schema.json`

内部 monitor の生データを browser へ直接渡しません。必ず source または final feed へ変換してから公開します。

## 3. Generate feed through the pipeline

推奨手順:

1. Internal monitor result
2. `tools/build-status-source-from-monitor.mjs`
3. `yonerai.status.source.v1`
4. `tools/build-status-feed.mjs`
5. `yonerai.status.feed.v1`
6. `tools/validate-status-feed.mjs`
7. public `/status-feed.json`

Pipeline が失敗した場合は、既存の valid feed を保持します。壊れた feed で公開 UI を上書きしません。

## 4. Apply feed through runtime API

外部連携は DOM を直接触りません。

推奨 API:

- `YonerAIStatusRuntime.trySetFeed(feed, options)`
- `YonerAIStatusRuntime.reload('/status-feed.json', options)`
- `YonerAIStatusRuntime.connectEvents('/status-feed/events')`
- `YonerAIStatusFeedClient.applyWhenReady(feed, options, timeoutMs)`
- `YonerAIStatusFeedClient.loadWhenReady('/status-feed.json', options, timeoutMs)`

既に runtime が確実に存在する場合だけ、低レベル API の `apply()` / `load()` を使えます。

避けること:

- `#categoryList` へ直接 HTML を注入する。
- `.bar` class を外部 script から直接追加・削除する。
- tooltip DOM を外部 script で追加する。
- selected highlight を外部 script で直接操作する。
- `yonerai-status:set-feed` listener を二重登録する。

## 5. Route ownership

Selected highlight と detail panel は hash route が所有します。

Supported routes:

- `#overview`
- `#status/<category-id>/<component-id>/<date-or-index>/<state>`
- `#incident/<incident-id>`

`__category__` は category overview route 用の予約 sentinel です。実 component id として使いません。

## 6. Status overview aggregation

Category overview は child component days から集約します。

Severity order:

1. `major_outage`
2. `partial_outage`
3. `degraded`
4. `maintenance`
5. `alpha_only`
6. `not_started`
7. `operational`

Overview を別の直書き状態にしません。小さい component row と同じ feed から作ります。

## 7. Tooltip and touch behavior

Tooltip は runtime singleton にします。

Requirements:

- hover 中に点滅しない。
- bar gap では nearest bar を選ぶ。
- mobile touch で表示できる。
- vertical scroll では閉じる。
- detail route や feed reload 後に古い tooltip を残さない。

外部連携が一時状態を消したい場合は `YonerAIStatusRuntime.clearInteractionState()` を使います。

## 8. Theme behavior

Theme は CSS token が所有します。Feed に theme-specific color を入れません。

Light/dark の両方で次が読める必要があります。

- status card
- component row
- detail card
- status detail panel
- incident detail panel
- affected components timeline
- updates timeline
- tooltip
- theme toggle

## 9. Public wording boundary

実監視が接続されるまで、次を主張しません。

- live monitoring is active
- production is operational
- uptime is collected
- incident history is factual
- Google login / Discord / memory / cloud production is complete

表示テストは必ず display test として明示します。

## 10. Required pre-public checks

公開前の最小確認:

- Final feed validates against `status-feed.schema.json`.
- Source feed validates against `status-source.schema.json`.
- Monitor payload validates against `status-monitor.schema.json`.
- `trySetFeed()` rejects invalid feed without destroying current UI.
- `loadWhenReady()` works when helper loads before runtime.
- `reload()` accepts only same-origin URL.
- Category overview bars match child component severity.
- Status route opens the matching selected bar and detail panel.
- Incident route opens affected components and updates timeline.
- Dark/light mode keeps all text readable.
- Mobile touch tooltip works.
- No stale selected highlight remains after returning to overview.

このチェックが未完了なら、goal 完了とは扱いません。