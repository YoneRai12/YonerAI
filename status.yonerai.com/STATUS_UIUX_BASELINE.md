# YonerAI Status UIUX Baseline

このファイルは、runtime/feed化の作業で UI/UX を壊さないための基準です。目的は「見た目と操作感は固定し、カテゴリ・コンポーネント・バー色・詳細・障害タイムラインだけを feed から差し替える」ことです。

## 正のUIUX参照

次のURLを、現在の UI/UX 参照として扱います。

```text
http://127.0.0.1:5500/?mockStatus=1&cacheBust=20260601-feed-label-ja-check#incident-test-29-major_outage
```

このURLは mock feed と legacy incident hash を使い、障害詳細、影響コンポーネント、更新タイムライン、色付きバー、hover/touch tooltip を同時に確認するための参照です。

## 参照にしてはいけないURL

```text
http://127.0.0.1:5500/ は UIUX 完成基準ではありません
```

bare URL は公開用 feed の通常入口です。公開用 feed は未運用の事実を灰色で表示するため、mock の障害詳細 UI や色付きバーの基準にはしません。

## 固定するUI契約

- `index.html` の `#categoryTemplate` / `#childTemplate` / `#categoryList` / `#barTooltip` は維持する。
- `.category-summary` / `.category-bars` / `.children-content` / `.child-summary` / `.child-bars` / `.child-detail` / `.detail-card` の class 契約を維持する。
- 棒は `button.bar.bar-state-<state>.is-clickable` として生成する。
- 棒には `data-route` / `data-category-id` / `data-component-id` / `data-date` / `data-status` / `data-status-runtime="feed"` を必ず付ける。
- 互換CSSのため、当面は `data-mock-status` も残す。
- 選択中は `.bar.is-selected` と `aria-current="date"` だけで表現する。
- hover/touch tooltip は `#barTooltip` を単一インスタンスとして使う。棒ごとに tooltip DOM を作らない。
- overview / incident route では、不要な `.bar.is-selected` を残さない。
- `#barDetailPanel` と `#incidentDetailPanel` は feed-driven panel として1つだけ表示する。

## 変えてよいもの

- `status-feed.json` / `status-feed.mock.json` / `status-feed.example.json` の中身。
- feed から出るカテゴリ、コンポーネント、日別 state、incident、affected、updates。
- `mock-status-adapter.js` の正規化、検証、API、route同期、EventSource接続。

## 変えてはいけないもの

- 棒が左から右に流れるアニメーションの基本挙動。
- hover/touch tooltip の滑らかな追従。
- 選択ハイライトが state 色に追従する設計。
- 展開・折りたたみ時のレイアウト移動アニメーション。
- light/dark のトーンとカード密度。

## 最小検証

```powershell
node --check status.yonerai.com\mock-status-adapter.js
node status.yonerai.com\tools\validate-status-feed.mjs status.yonerai.com\status-feed.json
node status.yonerai.com\tools\validate-status-feed.mjs status.yonerai.com\status-feed.mock.json
node status.yonerai.com\status-feed.verify.mjs
```

ブラウザでは以下を確認します。

- good URLで incident panel が1つだけ出る。
- status routeで detail panel が1つだけ出る。
- 選択ハイライトが対象の1本だけに残る。
- hover/touch tooltip が点滅せず、画面外にはみ出さない。
- mock feedなしの公開入口は、未運用の事実を灰色で表示する。
