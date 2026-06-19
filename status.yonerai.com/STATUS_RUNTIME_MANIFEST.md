# YonerAI Status runtime manifest

この manifest は `status.yonerai.com` を他プロジェクトでも再利用できる Status page runtime として扱うための所有範囲を定義します。

このページは UI runtime です。監視データそのものの真実ではありません。実運用では feed producer が source of truth になり、browser runtime は受理済み feed を描画するだけです。

## Runtime UI bundle

次のファイルは Status page runtime として一括で移植します。

- `index.html`: default URL shell。通常入口。URL を汚さない。
- `jp/index.html`: 日本語固定入口。
- `en/index.html`: 英語固定入口。
- `styles.css`: base visual system、fallback/preparation UI、layout token。
- `runtime-status.css`: feed-driven UI override。bar hover、selected state、tooltip、status detail、incident detail、timeline、theme compatibility を所有する。
- `mock-status-adapter.js`: feed renderer と browser runtime API の所有者。

この bundle をコピーする場合、HTML に状態を直書きしません。サービス名、カテゴリ、コンポーネント、バー色、詳細、障害タイムラインは feed から供給します。

## Final feed contracts

Browser runtime が直接読む complete feed は `yonerai.status.feed.v1` です。

- `status-feed.schema.json`: runtime feed の構造検証契約。
- `status-feed.mock.json`: 現行 UI の開発用 mock feed。実監視データではない。
- `status-feed.example.json`: 最小移植用の complete feed fixture。
- `status-feed.scenarios.example.json`: カテゴリ、コンポーネント、色付きバー、status detail、incident detail、affected components、updates timeline を含む再利用確認用 fixture。

実運用では `/status-feed.json` などの same-origin URL から complete feed を返します。Runtime は arbitrary remote URL を読みません。

## Source and monitor contracts

内部監視や他プロジェクトの状態を直接 HTML へ渡しません。必ず source または monitor payload から public-safe feed に変換します。

- `status-source.schema.json`: `yonerai.status.source.v1` の compact source 契約。
- `status-monitor.schema.json`: 内部 monitor result payload の公開前契約。
- `status-feed.source.example.json`: 既存 source fixture。
- `status-feed.scenarios.source.example.json`: clean source scenario fixture。compact day map から詳細 UI まで生成できることを示す。
- `status-monitor-results.example.json`: monitor result example。Browser runtime には直接読ませない。

Source / monitor layer は内部表現を受け取り、公開してよい項目だけを final feed に落とす境界です。

## Build, validation, and bridge tools

- `tools/build-status-feed.mjs`: source JSON から complete feed JSON を生成する。
- `tools/build-status-source-from-monitor.mjs`: monitor result payload から source JSON を生成する。
- `tools/build-status-pipeline.mjs`: monitor input -> source -> feed の順に生成して検証し、最後に complete feed を出力する pipeline。
- `tools/status-feed-bridge.example.mjs`: 内部監視ファイルを public feed に安全昇格する bridge example。
- `tools/validate-status-input.mjs`: source / monitor input の構造を検証する。
- `tools/validate-status-feed.mjs`: complete feed の構造、day、route、incident link を検証する。
- `tools/status-feed-dev-server.mjs`: local same-origin server。`/status-feed.json` と `/status-feed/events` を提供できる。
- `tools/status-runtime-acceptance.mjs`: Playwright-based runtime acceptance harness。

本番連携では pipeline が成功した feed だけを公開場所へ promote します。失敗した出力で既存の公開 feed を破壊しません。

## Runtime integration examples

- `status-runtime-bootstrap.example.js`: same-origin feed polling、SSE、manual runtime hook の例。invalid feed は現在の UI を保持する fail-closed path で扱う。
- `status-feed-client.example.js`: 他プロジェクトや内部 bridge が runtime に安全に feed を投入するための client helper。
- `hosting/cloudflare-status-feed-worker.example.js`: Cloudflare Workers で `/status-feed.json` と `/status-feed/events` を返す例。
- `hosting/README.md`: public feed boundary と hosting flow。

`status-runtime-bootstrap.example.js` は `yonerai-status:set-feed` の追加 listener を持ちません。Manual feed event の所有者は `mock-status-adapter.js` の runtime だけです。

## Recommended external API

他プロジェクトから feed を投入するときは、DOM ではなく runtime API を使います。

```js
await window.YonerAIStatusFeedClient.loadWhenReady('/status-feed.json', {
  animate: false,
  source: 'internal-monitor'
});
```

Runtime がすでに存在することが確実な場合は次を使えます。

```js
window.YonerAIStatusRuntime.trySetFeed(nextFeed, {
  animate: false,
  source: 'internal-monitor'
});
```

避けること:

- `#categoryList` や `.bar` へ直接 DOM を足す。
- selected highlight を外部 script で直接操作する。
- tooltip DOM を外部 script で複製する。
- `yonerai-status:set-feed` listener を二重登録する。

## Documentation

- `STATUS_FEED_API.md`: external integration API、SSE、bridge、fail-closed rules。
- `STATUS_FEED_CONTRACT.md`: feed schema と route/theme/wording boundary。
- `STATUS_RUNTIME_USAGE.md`: local usage、runtime API、adapter、scenario fixture、hosting hook。
- `STATUS_IMPLEMENTATION.md`: UI/runtime guardrails、file ownership、route contract、theme contract、manual QA checklist。
- `STATUS_INTEGRATION_CHECKLIST.md`: 他プロジェクトへ移植するときの実務 checklist。
- `STATUS_RUNTIME_MANIFEST.md`: このファイル。移植単位と責任境界の正本。

## Copy rules for other projects

他プロジェクトへ移植するときは、次を bundle としてコピーします。

- Runtime UI bundle。
- `status-feed.schema.json`。
- `status-source.schema.json` and `status-monitor.schema.json`。
- build / validate / bridge tools。
- `STATUS_FEED_API.md` and `STATUS_FEED_CONTRACT.md`。
- `STATUS_INTEGRATION_CHECKLIST.md`。

プロジェクトごとに差し替えるものは feed producer、source data、monitor result、ブランド文言、hosting endpoint だけです。

## Runtime invariants

- HTML にカテゴリ、コンポーネント、バー色、障害更新を直書きしない。
- `__category__` は route sentinel 予約名。Component id として使わない。
- selected highlight は route state だけで決める。hover state や pointer state と混ぜない。
- tooltip は singleton にする。bar ごとに tooltip DOM を増やさない。
- 外部連携が一時 UI 状態を削除するときは `YonerAIStatusRuntime.clearInteractionState()` を使う。
- 外部連携が同じ feed を再描画するときは `YonerAIStatusRuntime.rerender()` を使う。HTML を直接書き換えない。
- 外部連携が feed を安全に差し替えるときは `YonerAIStatusRuntime.trySetFeed()` または `YonerAIStatusFeedClient.loadWhenReady()` を使う。失敗時は現在の UI を保持し、error/state を返す。
- Category overview は child component days から集約する。
- Dark/light theme は feed ではなく CSS token で制御する。
- Feed reload で stale selected highlight、duplicate panel、duplicate tooltip を残さない。
- Unknown state は安全側に倒し、実運用 claim として表示しない。

## Required completion evidence

この goal を完了扱いにするには、最低でも次の evidence が必要です。

- `status-feed.mock.json` と `status-feed.scenarios.example.json` が feed validator を通る。
- `status-feed.scenarios.source.example.json` が source validator を通り、builder で complete feed を生成できる。
- Monitor result から pipeline 経由で complete feed を生成できる。
- Generated feed を `YonerAIStatusRuntime.setFeed()` または same-origin `reload()` で読み込める。
- `localhost:5500/?mockStatus=1` でカテゴリ、コンポーネント、バー、詳細、障害 timeline が feed から描画される。
- `#status/<category>/<component>/<date>/<state>` で selected bar と detail panel が一致する。
- `#incident/<incident-id>` で affected components と updates timeline が feed から描画される。
- Hover tooltip が点滅せず、bar gap 上でも nearest bar を選ぶ。
- Touch tooltip が mobile viewport で表示され、scroll 時に閉じる。
- Dark/light mode で detail card、incident detail、timeline、tooltip の文字が読める。
- Stale selected highlight が overview、detail、incident、feed reload の間に残らない。

未検証の時点では goal は完了扱いにしません。