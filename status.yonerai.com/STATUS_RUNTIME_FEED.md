# YonerAI Status runtime feed contract

YonerAI Status は、UI/UX を固定し、状態データだけを feed で差し替えるステータスページです。AWS、YonerAI API、healthcheck、手動オペレーションのどれから生成しても、最終的には同じ `yonerai.status.feed.v1` JSON に変換します。

## 最終feedファイル

- `status-feed.json`: 公開用。本番監視が未接続なら、事実として `not_started` / 灰色を出す。
- `status-feed.mock.json`: UI/UX と runtime の表示テスト用。実データではない。
- `status-feed.example.json`: 外部システムが生成すべき最小例。

## feedの基本形

```json
{
  "schema_version": "yonerai.status.feed.v1",
  "generated_at": "2026-06-01T00:00:00+09:00",
  "range": {
    "start": "2026-02-27",
    "days": 90,
    "end": "2026-05-27"
  },
  "states": {
    "operational": {
      "severity": 0,
      "color": "#25c39a",
      "labels": { "ja": "稼働中", "en": "Operational" }
    }
  },
  "categories": [
    {
      "id": "core-api",
      "name": { "ja": "コアAPI", "en": "Core API" },
      "state": "not_started",
      "children": [
        {
          "id": "api",
          "name": "API",
          "state": "not_started",
          "fact": {
            "ja": "External API の可用性データはまだ収集していません。",
            "en": "External API availability is not collected yet."
          },
          "monitoring": { "ja": "未接続", "en": "Not connected" },
          "claim": { "ja": "本番運用は未主張", "en": "No production operation claim" },
          "days": [
            {
              "date": "2026-02-27",
              "state": "not_started",
              "source": "default_status"
            }
          ]
        }
      ]
    }
  ],
  "incidents": []
}
```

## 日別state

`children[].days[]` が棒1本に対応します。

```json
{
  "date": "2026-04-26",
  "state": "degraded",
  "incident_id": "incident-test-59-degraded",
  "message": { "ja": "mock feed connected", "en": "mock feed connected" },
  "source": "status feed override"
}
```

## incident

```json
{
  "id": "incident-test-29-major_outage",
  "date": "2026-03-28",
  "category_id": "status-bar-test",
  "component_id": "status-bar-test-component",
  "state": "major_outage",
  "impact": "partial_outage",
  "title": { "ja": "表示テスト: ランタイムサービス停止", "en": "Display test: runtime service outage" },
  "summary": { "ja": "障害詳細UIの表示テストです。", "en": "Display test for incident detail UI." },
  "affected": {
    "category_id": "status-bar-test",
    "component_id": "status-bar-test-component",
    "start_label": "2026-03-28 08:05",
    "end_label": "08:40",
    "segments": [
      { "state": "operational", "percent": 8 },
      { "state": "major_outage", "percent": 84 },
      { "state": "operational", "percent": 8 }
    ]
  },
  "updates": [
    {
      "state": "resolved",
      "title": { "ja": "解決済み", "en": "Resolved" },
      "body": { "ja": "この問題は解決済みとしてマークされました。", "en": "The issue has been marked as resolved." },
      "time_utc": "2026-05-07 11:44 UTC",
      "time_local": "2026-05-07 20:44 JST"
    }
  ]
}
```

## runtime API

外部ロジックは、ページ読み込み後に次のAPIでfeedを差し替えます。

```js
window.YonerAIStatusRuntime.validateFeed(feed);
window.YonerAIStatusRuntime.applyFeed(feed, { source: "internal-monitor" });
window.YonerAIStatusRuntime.setFeed(feed, { source: "aws-health" });
window.YonerAIStatusRuntime.trySetFeed(feed, { source: "yonerai-api" });
window.YonerAIStatusRuntime.reload("/status-feed.json");
window.YonerAIStatusRuntime.refresh();
window.YonerAIStatusRuntime.connectEvents("/status-feed/events");
window.YonerAIStatusRuntime.disconnectEvents();
window.YonerAIStatusRuntime.clearInteractionState();
window.YonerAIStatusRuntime.rerender();
window.YonerAIStatusRuntime.getState();
window.YonerAIStatusRuntime.getFeed();
window.YonerAIStatusRuntime.destroy();
```

Event経由でも差し替えできます。

```js
document.dispatchEvent(
  new CustomEvent("yonerai-status:set-feed", {
    detail: { feed, source: "external-runtime" }
  })
);
```

互換イベントとして `yonerai-status-feed:update` も受け付けます。

## bridge入力の考え方

各システムは、直接HTMLを触らず、monitor result か source JSON を出します。

```json
{
  "schema_version": "yonerai.status.monitor.v1",
  "generated_at": "2026-06-01T00:00:00+09:00",
  "checks": [
    {
      "category_id": "core-api",
      "component_id": "api",
      "date": "2026-06-01",
      "state": "operational",
      "message": { "ja": "API healthcheck passed", "en": "API healthcheck passed" },
      "source": "yonerai-api-healthcheck"
    }
  ],
  "incidents": []
}
```

`tools/status-feed-bridge.example.mjs` は monitor result を status feed に変換し、検証に成功した場合だけ publish します。検証に失敗した場合は最後の正常なfeedを残します。

HTTP healthcheck、YonerAI API probe、AWS CloudWatch などのメトリクス集計結果は、まず `tools/collect-status-healthchecks.mjs` で `yonerai.status.monitor.v1` に変換します。AWS認証情報や内部URLは公開feedに入れず、collector入力または外部AWS job側で閉じます。

## ルーティング

- `#status/<categoryId>/<componentId>/<YYYY-MM-DD>/<state>`: コンポーネント日別詳細。
- `#status/<categoryId>/__category__/<YYYY-MM-DD>/<state>`: カテゴリ集計日別詳細。
- `#incident/<incidentId>`: 障害詳細。
- local preview のみ、`#status-test-*` / `#incident-test-*` の legacy hash を mock feed に解釈します。
- 公開URLでは、legacy hash だけで mock feed を読みません。

## 検証

```powershell
node status.yonerai.com\tools\validate-status-feed.mjs status.yonerai.com\status-feed.json
node status.yonerai.com\tools\validate-status-feed.mjs status.yonerai.com\status-feed.mock.json
node status.yonerai.com\status-feed.verify.mjs
```
