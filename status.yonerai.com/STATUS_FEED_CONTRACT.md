# YonerAI Status Feed Contract

この文書は `status.yonerai.com` の再利用可能な status page 実装契約です。
UI は JSON feed を唯一の状態入力として描画し、HTML にカテゴリ・コンポーネント・日別ステータス・障害タイムラインを直書きしないことを前提にします。

現在のページは公開ステータス運用前の UI/runtime プロトタイプです。実監視、稼働率収集、障害収集、本番運用、Google Login、Discord、Persistent Memory、Official Cloud 完了は主張しません。

## 1. 実装境界

- HTML はページ骨格、template、static copy、runtime loader だけを持つ。
- `mock-status-adapter.js` は feed を検証・正規化して DOM に描画する runtime owner とする。
- CSS は見た目と motion だけを担当し、状態判定や feed truth を持たない。
- `status-feed.mock.json` は表示検証用 feed であり、本番監視データではない。
- 本番化時は同じ feed shape の `/status-feed.json` または same-origin endpoint/SSE に差し替える。

## 2. Runtime public API

`mock-status-adapter.js` 読み込み後、ブラウザには `window.YonerAIStatusRuntime` を公開する。

- `setFeed(feed, options)`: feed を検証・正規化して UI 全体を置き換える。
- `trySetFeed(feed, options)`: 失敗時に現 UI を壊さず `{ ok, error, state }` を返す。
- `reload(url, options)`: same-origin URL から feed を取得して適用する。
- `connectEvents(url, options)`: same-origin SSE feed に接続する。
- `disconnectEvents()`: SSE 接続を閉じる。
- `syncRoute()`: 現在 hash を現 feed に対して再適用する。
- `clearInteractionState()`: tooltip、hover、touch、selected highlight など一時 UI 状態を消す。
- `rerender(options)`: in-memory feed を再描画する。
- `getFeed()`: 現在適用済み feed を返す。
- `getState()`: route、描画数、selected 数、panel 数、source、schema、live 状態、feed error を返す。

`options.source` は診断用であり、UI の正しさを `source` に依存させない。

## 3. Feed shape

ブラウザ runtime が読む最終 payload は `yonerai.status.feed.v1` とする。

```json
{
  "schema_version": "yonerai.status.feed.v1",
  "generated_at": "2026-05-30T00:00:00Z",
  "range": {
    "start": "2026-02-28",
    "end": "2026-05-28",
    "days": 90
  },
  "states": {},
  "categories": [],
  "incidents": []
}
```

正式な schema は `status-feed.schema.json`。runtime や pipeline はこの schema と追加 validator を通す。

## 4. Category と Component

Category は大枠の status row。Component は展開後の小さい status row。
Category overview bar は children の同日 `days[]` を集約して描画する。カテゴリ用に別の手書き day 配列を持たせない。

必要最小フィールド:

```json
{
  "id": "core-api",
  "name": { "ja": "コアAPI", "en": "Core APIs" },
  "children": [
    {
      "id": "api",
      "name": { "ja": "API", "en": "API" },
      "fact": { "ja": "API の可用性データはまだ収集していません。" },
      "monitoring": { "ja": "未接続" },
      "claim": { "ja": "本番運用は未主張" },
      "days": []
    }
  ]
}
```

## 5. Day と状態色

各 component は `range.days` と同じ日数の `days[]` を持つ。

```json
{
  "index": 58,
  "date": "2026-04-26",
  "state": "degraded",
  "incident_id": "incident-test-59-degraded",
  "label": { "ja": "2026-04-26: 性能低下" },
  "detail": { "ja": "この日は表示テストとして性能低下を示しています。" }
}
```

基本 state:

- `operational`
- `degraded`
- `partial_outage`
- `major_outage`
- `maintenance`
- `not_started`
- `alpha_only`

色は `feed.states[state].color` を優先し、未定義なら runtime token fallback を使う。selected highlight、tooltip accent、status detail panel、incident affected segments は同じ state color 系統で統一する。

## 6. Category aggregation

同じ date/index の child day を severity 順に比較し、最も重大な状態を category overview に出す。

Severity order:

1. `major_outage`
2. `partial_outage`
3. `degraded`
4. `maintenance`
5. `alpha_only`
6. `not_started`
7. `operational`

Category row の current state も children の最新 day から集約する。手書きの category state と矛盾する場合は集約結果を優先する。

## 7. Routes

Runtime supports these hash routes:

- Overview: `#overview`
- Status day: `#status/<category-id>/<component-id>/<date-or-index>/<state>`
- Category day: `#status/<category-id>/__category__/<date-or-index>/<state>`
- Incident: `#incident/<incident-id>`

`__category__` は予約語。component id として使わない。
Legacy display-test route は受けてもよいが、最終的には現 route へ canonicalize する。
存在しない route は blank page にせず overview へ戻す。

## 8. Status detail panel

Status detail は bar click から出る小さい日別詳細。
この panel は day/category/component/feed から生成し、直書きしない。

表示項目:

- state label
- category/component name
- date
- display state
- fact/monitoring/claim
- incident_id がある場合は「障害タイムラインを見る」導線

Status detail route から overview に戻る時は stale selected highlight を必ず消す。

## 9. Incident detail panel

Incident は `incidents[]` から描画する。

必要項目:

- title
- status / state / summary
- affected components
- affected timeline segments
- updates timeline

Affected timeline segment は `state` と `percent` から描画し、合計は 100 を目安に validator で警告する。
色は segment state の color を使う。白線や透明線で代替しない。

## 10. Updates timeline

障害更新は structured timeline として描画する。

```json
{
  "status": "monitoring",
  "label": { "ja": "監視中", "en": "Monitoring" },
  "body": { "ja": "修正パッチを適用し、復旧状況を監視しています。" },
  "utc": "2026-05-07 11:26 UTC",
  "jst": "2026-05-07 20:26 JST"
}
```

Timeline label は status color を使ってよいが、本文は light/dark どちらでも読める本文色を維持する。

## 11. Motion / interaction requirements

- 90-day bars はページロード時と展開時に左から右へ cascade 表示する。
- cascade は二重実行しない。fallback animation と runtime animation を同時に走らせない。
- hover/touch tooltip は pointer 上で点滅しない。
- bar gap 上でも近傍 bar を拾うか、tooltip を急に消さない。
- selected highlight は現在 route のみを表す。別 route に移動したら残さない。
- mobile touch では指でなぞった時に tooltip を出し、縦 scroll を塞がない。

## 12. Theme requirements

Light/dark は `<html data-theme>` と CSS token で切り替える。
Feed に theme 専用色を入れない。

必ず読める必要があるもの:

- overview cards
- component rows
- detail cards
- status detail panels
- incident detail panels
- affected component timelines
- update timelines
- tooltips
- buttons and theme toggle

## 13. Source pipeline

ブラウザが読むのは final feed のみ。内部監視 payload を直接ブラウザへ出さない。

推奨 pipeline:

```text
internal monitor output
  -> tools/build-status-source-from-monitor.mjs
  -> yonerai.status.source.v1
  -> tools/build-status-feed.mjs
  -> yonerai.status.feed.v1
  -> tools/validate-status-feed.mjs
  -> /status-feed.json or /status-feed/events
```

## 14. Acceptance checks

最低限、変更ごとに以下を確認する。

- feed categories and components render from JSON.
- Category overview bars aggregate from child components.
- Colored component bars open status detail pages.
- Incident bars open incident detail pages with affected components and timeline updates.
- `trySetFeed()` rejects invalid feed without destroying current UI.
- `loadWhenReady()` can connect feed after runtime load order changes.
- Hash routes preserve category, component, date, and state.
- Invalid or stale hash routes do not blank the page.
- Light and dark themes do not hide text or panels.
- Hover tooltip does not flicker while crossing bars or bar gaps.
- Mobile/touch pointer movement can show bar tooltip information without blocking vertical scroll.
- Returning from detail routes clears stale selected highlights.
- `/`, `/jp/`, `/en/` load the same current CSS/runtime version.

## 15. Text safety

Public text must not contain mojibake, replacement characters, `[object Object]`, `undefined`, or raw `null` literals.

- `tools/validate-status-input.mjs` checks monitor/source layer text.
- `tools/validate-status-feed.mjs` checks final feed text.
- Public copy must not claim live production operation before verified monitoring is connected.
