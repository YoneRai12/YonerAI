# YonerAI Status Runtime Feed API

このファイルは、YonerAI Status のブラウザruntimeを外部システムから安全に更新するための契約です。
UI/CSS/DOMを直接触らず、必ず `yonerai.status.feed.v1` をruntimeに渡します。

対応する機械可読manifest:

- `status-runtime-api.contract.json`
- `status-uiux-regression.contract.json`

静的検査:

```powershell
node tools/validate-status-runtime-contract.mjs
```

UI/UX回帰契約:

- `STATUS_UIUX_REGRESSION_CONTRACT.md`

---

## 1) 基本原則

- AWS / YonerAI API / cron / 管理UI は DOM を直接編集しない。
- ブラウザruntimeに渡す最終入力は必ず `yonerai.status.feed.v1`。
- `healthcheck` / `monitor` / `source` はサーバー側またはビルド側で `feed` に変換する。
- UIUX完璧版のhover/touch/animation/selected stateは、feed差し替えで壊さない。
- 機密情報、token、内部ホスト一覧、private runtime truth は public feed に入れない。

---

## 2) 公開runtime global

メイン:

```js
window.YonerAIStatusRuntime
```

互換alias:

```js
window.YonerAIStatus
window.yoneraiStatusApplyFeed
window.yoneraiStatusSetFeed
window.yoneraiStatusTrySetFeed
window.yoneraiStatusReload
window.yoneraiStatusRefresh
window.yoneraiStatusGetState
window.yoneraiStatusGetFeed
```

---

## 3) 外部からfeedを反映する方法

### 3-1) 例外を投げない安全更新

```js
const result = window.YonerAIStatusRuntime.trySetFeed(feed, {
  source: "admin-panel"
});

if (!result.ok) {
  console.error(result.error);
}
```

### 3-2) 例外を投げる更新

```js
window.YonerAIStatusRuntime.setFeed(feed, {
  source: "status-feed-json"
});
```

### 3-3) ブラウザイベントで更新

```js
document.dispatchEvent(new CustomEvent("yonerai-status-feed:update", {
  detail: {
    feed,
    source: "external-runtime",
    options: {
      preserveRoute: true
    }
  }
}));
```

互換イベント:

```js
document.dispatchEvent(new CustomEvent("yonerai-status:set-feed", {
  detail: {
    feed,
    source: "legacy-adapter"
  }
}));
```

---

## 4) refresh / reload

公開feed endpointから読み直す:

```js
window.YonerAIStatusRuntime.refresh();
```

互換:

```js
window.yoneraiStatusRefresh();
```

---

## 5) runtime state確認

```js
const state = window.YonerAIStatusRuntime.getState();
console.log(state);
```

期待する用途:

- 現在のlocale
- feed schema
- category数
- bar数
- selected route
- panel重複の有無
- runtime error

この値は診断用であり、public feed以外の内部情報を含めない。

---

## 6) route contract

通常のstatus bar:

```text
#status/{category_id}/{component_id}/{date}/{state}
```

カテゴリ概要bar:

```text
#status/{category_id}/__category__/{date}/{state}
```

障害詳細:

```text
#incident-{incident_id}
```

旧表示テスト互換:

```text
#status-test-{index}-{state}
#incident-test-{index}-{state}
```

---

## 7) 外部システムが守ること

外部システムは以下だけを行う。

1. `healthcheck` / `monitor` / `source` / `feed` のいずれかを生成
2. `tools/build-status-pipeline.mjs` または bridge で `feed` 化
3. `status-feed.json` または runtime API へ反映

外部システムは以下をしない。

- `.category` / `.bar` / `.tooltip` / `.incident` などのDOMを直接書き換えない
- 選択中barのclassを直接付け替えない
- tooltipを別ノードで重ねない
- hash routeをfeedと矛盾する形で固定しない
- public feedへtokenや内部URLを入れない

---

## 8) feed更新時のUIUX不変条件

- bar hover時のtooltipは1つだけ。
- touch pin状態はruntimeが管理する。
- `clearInteractionState()` を明示しない限り、不要な全解除はしない。
- feed差し替え後に存在しないrouteを指している場合は、安全にoverviewへ戻す。
- selected highlightは現在routeと一致するbarだけに付く。
- incident/detail panelは重複生成しない。
- animationはfeed生成ではなくruntime renderer側で管理する。

---

## 9) 推奨運用

healthcheckから公開feedまで一括:

```powershell
node tools/build-status-pipeline.mjs `
  status-healthcheck-input.example.json `
  generated/pipeline-from-healthcheck
```

公開feedへatomic publish:

```powershell
node tools/status-feed-bridge.example.mjs `
  status-healthcheck-input.example.json `
  generated/status-feed.live.json
```

watch運用:

```powershell
node tools/status-feed-bridge.example.mjs `
  status-healthcheck-input.example.json `
  generated/status-feed.live.json --watch
```

公開前の最低限チェック:

```powershell
node tools/validate-status-contract-suite.mjs
node tools/validate-status-runtime-contract.mjs
node tools/validate-status-uiux-regression.mjs
node tools/validate-status-healthcheck.mjs status-healthcheck-input.example.json
node tools/build-status-pipeline.mjs status-healthcheck-input.example.json generated/pipeline-from-healthcheck
```
