# YonerAI Status 統合用 JSON テンプレート

このページを「内部監視を JSON で受け取り、public feed を自由に出力できる」状態で使えるようにするための
コピペ可能な雛形です。

基本フロー:

1. healthcheck input (`yonerai.status.healthcheck.v1`) を収集
2. monitor 結果 (`yonerai.status.monitor.v1`) へ変換
3. source (`yonerai.status.source.v1`) へ展開
4. feed (`yonerai.status.feed.v1`) を生成してブラウザに配信

`tools/build-status-pipeline.mjs` は次の3種類を直接入力できます。

- `yonerai.status.healthcheck.v1`
- `yonerai.status.monitor.v1`
- `yonerai.status.source.v1`

主要スクリプト:

- `tools/collect-status-healthchecks.mjs`
- `tools/validate-status-healthcheck.mjs`
- `tools/build-status-source-from-monitor.mjs`
- `tools/build-status-feed.mjs`
- `tools/status-feed-bridge.example.mjs`
- `tools/status-healthcheck-bridge.example.mjs`
- `tools/validate-status-runtime-contract.mjs`
- `tools/validate-status-uiux-regression.mjs`
- `tools/validate-status-contract-suite.mjs`
- `tools/validate-status-integration-manifest.mjs`
- `tools/validate-status-public-feed-safety.mjs`
- `tools/status-runtime-browser-probe.js`
- `tools/fill-status-aws-metrics.mjs`
- `tools/fill-status-yonerai-health.mjs`
- `tools/validate-status-aws-metrics.mjs`
- `tools/validate-status-yonerai-health.mjs`
- `tools/promote-status-public-feed.mjs`
- `tools/restore-status-public-feed.mjs`
- `tools/sync-status-public-feed.mjs`
- `tools/build-status-public-package.mjs`
- `tools/run-status-browser-probe.mjs`
- `tools/audit-status-goal-readiness.mjs`

契約ファイル:

- `status-healthcheck.schema.json`
- `status-monitor.schema.json`
- `status-source.schema.json`
- `status-feed.schema.json`
- `status-aws-metrics.schema.json`
- `status-yonerai-health.schema.json`
- `status-runtime-api.contract.json`
- `STATUS_RUNTIME_FEED_API.md`
- `status-uiux-regression.contract.json`
- `STATUS_UIUX_REGRESSION_CONTRACT.md`
- `STATUS_PREPUBLISH_CHECKS.md`
- `status-integration.manifest.json`
- `STATUS_INTEGRATION_MANIFEST.md`
- `STATUS_OPERATIONS_RUNBOOK.md`
- `STATUS_GOAL_READINESS_AUDIT.md`

配信先:

- `.../status-feed.json`（通常表示）
- `.../status-feed/events`（SSE/EventSource）

---

## 1) 状態キー（state）と共通ルール

YonerAI内部・UI共通で扱える状態キー:

- `operational`
- `degraded`
- `partial_outage`
- `major_outage`
- `maintenance`
- `not_started`
- `alpha_only`
- `monitoring`
- `identified`
- `investigating`
- `resolved`
- `completed`

推奨色:

- operational: `#26c6a3`
- degraded: `#ffbf2f`
- partial_outage: `#ff9f43`
- major_outage: `#ef4e45`
- maintenance: `#ff8a34`
- not_started / alpha_only: `#aeb6c2`
- monitoring: `#3a9dff`
- identified: `#f6bd3f`
- investigating: `#ff6b6b`
- resolved / completed: `#26c6a3`

`label` は必須相当。
`label` キーのみ正規（`labels` は旧互換扱い）。

---

## 2) healthcheck 入力（`status-healthcheck-input...`）

### 2-1) YonerAI API + AWS を一緒に運用する例

```json
{
  "schema_version": "yonerai.status.healthcheck.v1",
  "generated_at": "2026-06-18T00:00:00+09:00",
  "locale_default": "ja",
  "range": {
    "start": "2026-06-18",
    "days": 90
  },
  "states": {
    "operational": { "color": "#26c6a3", "label": { "ja": "稼働中", "en": "Operational" } },
    "degraded": { "color": "#ffbf2f", "label": { "ja": "性能低下", "en": "Degraded" } },
    "maintenance": { "color": "#ff8a34", "label": { "ja": "メンテナンス", "en": "Maintenance" } },
    "major_outage": { "color": "#ef4e45", "label": { "ja": "重大障害", "en": "Major outage" } },
    "not_started": { "color": "#aeb6c2", "label": { "ja": "準備中", "en": "Not started" } }
  },
  "contract_note": {
    "ja": "YonerAI API と AWS の本番運用接続サンプル。実運用環境では値を実データ置換してください。",
    "en": "YonerAI API and AWS live-input sample. Replace placeholders with real data."
  },
  "categories": [
    {
      "id": "core-api",
      "name": { "ja": "コアAPI", "en": "Core API" },
      "components": [
        {
          "id": "yonerai-api",
          "name": { "ja": "YonerAI API", "en": "YonerAI API" },
          "fact": { "ja": "API /health を監視します。", "en": "API /health healthcheck." },
          "monitoring": { "ja": "HTTP healthcheck", "en": "HTTP healthcheck" },
          "claim": { "ja": "実運用接続時のみ本番可用性を主張します。", "en": "Production claim only when live checks are connected." },
          "default_state": "not_started",
          "checks": [
            {
              "type": "http",
              "url": "https://api.yonerai.com/health",
              "method": "GET",
              "status_min": 200,
              "status_max": 399,
              "timeout_ms": 5000,
              "degraded_ms": 800,
              "label": "yonerai-api-health",
              "message": { "ja": "APIヘルスチェック", "en": "API healthcheck" },
              "message_on_error": { "ja": "API ヘルスチェック失敗", "en": "API healthcheck failed" },
              "headers": { "Authorization": "__REPLACE_WITH_BEARER_TOKEN__" }
            }
          ]
        },
        {
          "id": "run-api",
          "name": { "ja": "Run API", "en": "Run API" },
          "fact": { "ja": "Run API を監視します。", "en": "Run API is checked." },
          "monitoring": { "ja": "HTTP healthcheck", "en": "HTTP healthcheck" },
          "claim": { "ja": "実運用接続時のみ本番可用性を主張します。", "en": "Production claim only when live checks are connected." },
          "default_state": "not_started",
          "checks": [
            {
              "type": "http",
              "url": "https://api.yonerai.com/run/health",
              "method": "GET",
              "status_min": 200,
              "status_max": 399,
              "timeout_ms": 5000,
              "degraded_ms": 1200,
              "label": "yonerai-run-health",
              "message": { "ja": "Run APIヘルスチェック", "en": "Run API healthcheck" },
              "message_on_error": { "ja": "Run API ヘルスチェック失敗", "en": "Run API healthcheck failed" }
            }
          ]
        }
      ]
    },
    {
      "id": "public-surfaces",
      "name": { "ja": "公開サーフェス", "en": "Public surfaces" },
      "components": [
        {
          "id": "website",
          "name": { "ja": "Website", "en": "Website" },
          "fact": { "ja": "公開ページの表示可用性", "en": "Public website accessibility." },
          "monitoring": { "ja": "HTTP healthcheck", "en": "HTTP healthcheck" },
          "claim": { "ja": "公開運用時のみ本番稼働を主張します。", "en": "Production claim only for public runtime." },
          "default_state": "not_started",
          "checks": [
            {
              "type": "http",
              "url": "https://yonerai.com/",
              "method": "GET",
              "status_min": 200,
              "status_max": 399,
              "timeout_ms": 5000,
              "degraded_ms": 1000,
              "label": "website-home",
              "message": { "ja": "Website確認", "en": "Website check" },
              "message_on_error": { "ja": "Website 接続失敗", "en": "Website connection failed" }
            }
          ]
        },
        {
          "id": "web-demo",
          "name": { "ja": "Web demo", "en": "Web demo" },
          "fact": { "ja": "体験環境の到達性", "en": "Web demo reachability." },
          "monitoring": { "ja": "HTTP healthcheck", "en": "HTTP healthcheck" },
          "claim": { "ja": "監視接続中のみ本番運用状態を表示します。", "en": "Shows operational status only when connected." },
          "default_state": "not_started",
          "checks": [
            {
              "type": "http",
              "url": "https://app.yonerai.com/",
              "method": "GET",
              "status_min": 200,
              "status_max": 399,
              "timeout_ms": 5000,
              "degraded_ms": 1200,
              "label": "web-demo-home",
              "message": { "ja": "Web demo 確認", "en": "Web demo check" },
              "message_on_error": { "ja": "Web demo 到達性チェック失敗", "en": "Web demo check failed" }
            }
          ]
        }
      ]
    },
    {
      "id": "infrastructure",
      "name": { "ja": "インフラ", "en": "Infrastructure" },
      "components": [
        {
          "id": "aws-staging",
          "name": { "ja": "AWS staging", "en": "AWS staging" },
          "fact": { "ja": "CloudWatch 指標を集約して監視します。", "en": "Monitor CloudWatch aggregates." },
          "monitoring": { "ja": "AWS metric", "en": "AWS metric" },
          "claim": { "ja": "未本番対象のため本番可用性を主張しません。", "en": "No production claim; not a production target." },
          "default_state": "not_started",
          "checks": [
            {
              "type": "aws_metric",
              "namespace": "AWS/Lambda",
              "metric_name": "Errors",
              "period_seconds": 300,
              "statistic": "Sum",
              "value": 0,
              "comparison": "<=",
              "threshold": 0,
              "degraded_threshold": 1,
              "major_threshold": 5,
              "label": "lambda-errors",
              "message": { "ja": "Lambda Errors 集計", "en": "Lambda Errors aggregate" }
            }
          ]
        }
      ]
    }
  ]
}
```

`__REPLACE_WITH_BEARER_TOKEN__` は実行直前に環境変数差し替えにしてください（CIやスケジューラから安全に差し込み）。

---

### 2-2) コマンド

```powershell
cd status.yonerai.com

node tools/validate-status-healthcheck.mjs `
  status-healthcheck-input.example.json

node tools/collect-status-healthchecks.mjs `
  status-healthcheck-input.example.json `
  generated/status-monitor-results.generated.json

node tools/build-status-source-from-monitor.mjs `
  generated/status-monitor-results.generated.json `
  generated/status-feed.source.generated.json

node tools/build-status-feed.mjs `
  generated/status-feed.source.generated.json `
  generated/status-feed.generated.json

node tools/validate-status-feed.mjs generated/status-feed.generated.json
```

通常の `build-status-pipeline.mjs` は、feed schema検証後に `validate-status-public-feed-safety.mjs` も実行してから `status-feed.generated.json` へpromoteします。
`--skip-validate` / `--no-validate` はデバッグ用で、公開前には使わないでください。

または、入力schemaを自動判定して一括生成:

```powershell
node tools/build-status-pipeline.mjs `
  status-healthcheck-input.example.json `
  generated/pipeline-from-healthcheck
```

---

## 3) source (`yonerai.status.source.v1`) 直接編集サンプル

```json
{
  "schema_version": "yonerai.status.source.v1",
  "generated_at": "2026-06-18T10:00:00+09:00",
  "locale_default": "ja",
  "range": { "start": "2026-06-18", "days": 90 },
  "contract_note": { "ja": "source入力の手動編集用テンプレート", "en": "Manual source input template" },
  "states": {
    "operational": { "color": "#26c6a3", "label": { "ja": "稼働中", "en": "Operational" } },
    "degraded": { "color": "#ffbf2f", "label": { "ja": "性能低下", "en": "Degraded" } },
    "major_outage": { "color": "#ef4e45", "label": { "ja": "重大障害", "en": "Major outage" } },
    "not_started": { "color": "#aeb6c2", "label": { "ja": "準備中", "en": "Not started" } },
    "maintenance": { "color": "#ff8a34", "label": { "ja": "メンテナンス", "en": "Maintenance" } }
  },
  "categories": [
    {
      "id": "core-api",
      "name": { "ja": "コアAPI", "en": "Core API" },
      "children": [
        {
          "id": "yonerai-api",
          "name": { "ja": "YonerAI API", "en": "YonerAI API" },
          "default_state": "not_started",
          "fact": { "ja": "healthcheck結果を反映", "en": "Reflect healthcheck result" },
          "monitoring": { "ja": "http", "en": "http" },
          "claim": { "ja": "本番可用性は本番接続時のみ主張", "en": "Production claim only for live checks" },
          "days": {
            "2026-06-18": { "state": "operational", "message": { "ja": "初日OK", "en": "First day OK" } },
            "2026-06-19": { "state": "degraded", "message": { "ja": "レスポンス悪化", "en": "Latency increased" }, "incident_id": "incident-2026-06-19" }
          }
        }
      ]
    }
  ],
  "incidents": [
    {
      "id": "incident-2026-06-19",
      "state": "degraded",
      "status": "resolved",
      "date": "2026-06-19",
      "title": { "ja": "YonerAI API 速度劣化", "en": "YonerAI API slowdown" },
      "meta": [ { "ja": "Resolved", "en": "Resolved" }, { "ja": "Degraded", "en": "Degraded" } ],
      "summary": {
        "ja": ["監視上の応答遅延を確認し、キャッシュ調整と再試行により回復しました。"],
        "en": ["Response latency spike was observed and recovered after cache tuning and retry adjustments."]
      },
      "affected": {
        "components": [
          {
            "category_id": "core-api",
            "component_id": "yonerai-api",
            "name": { "ja": "YonerAI API", "en": "YonerAI API" },
            "state": "degraded",
            "date": "2026-06-19"
          }
        ],
        "segments": [
          { "state": "operational", "percent": 60 },
          { "state": "degraded", "percent": 40 }
        ]
      },
      "updates": [
        {
          "status": "resolved",
          "label": { "ja": "解決済み", "en": "Resolved" },
          "body": {
            "ja": ["調査後、再試行制御とキャッシュ再構成で回復しました。"],
            "en": ["Recovered after retry control and cache reconfiguration."]
          },
          "utc": "2026-06-19 11:20 UTC",
          "jst": "2026-06-19 20:20 JST"
        }
      ]
    }
  ]
}
```

---

## 4) feed (`yonerai.status.feed.v1`) 出力サンプル

```json
{
  "schema_version": "yonerai.status.feed.v1",
  "generated_at": "2026-06-18T10:05:00Z",
  "locale_default": "ja",
  "range": {
    "start": "2026-06-18",
    "days": 90,
    "end": "2026-09-15"
  },
  "contract_note": { "ja": "UIがそのまま描画する最終入力", "en": "Final input consumed directly by status UI" },
  "states": {
    "operational": { "color": "#26c6a3", "label": { "ja": "稼働中", "en": "Operational" }, "severity": 1 },
    "degraded": { "color": "#ffbf2f", "label": { "ja": "性能低下", "en": "Degraded" }, "severity": 3 },
    "major_outage": { "color": "#ef4e45", "label": { "ja": "重大障害", "en": "Major outage" }, "severity": 6 }
  },
  "categories": [
    {
      "id": "core-api",
      "name": { "ja": "コアAPI", "en": "Core API" },
      "children": [
        {
          "id": "yonerai-api",
          "name": { "ja": "YonerAI API", "en": "YonerAI API" },
          "fact": { "ja": "このコンポーネントは feed から描画されます。", "en": "Rendered from feed." },
          "monitoring": { "ja": "mock feed connected", "en": "mock feed connected" },
          "claim": { "ja": "本番運用は実接続時のみ", "en": "Production claim only when live checks are connected" },
          "state": "operational",
          "days": [
            {
              "index": 0,
              "date": "2026-06-18",
              "date_label": { "ja": "2026年06月18日", "en": "2026-06-18" },
              "state": "operational",
              "label": { "ja": "稼働中", "en": "Operational" },
              "color": "#26c6a3",
              "message": { "ja": "OK", "en": "OK" },
              "incident_id": null
            },
            {
              "index": 1,
              "date": "2026-06-19",
              "date_label": { "ja": "2026年06月19日", "en": "2026-06-19" },
              "state": "degraded",
              "label": { "ja": "性能低下", "en": "Degraded" },
              "color": "#ffbf2f",
              "message": { "ja": "表示テスト上の性能低下", "en": "Display-test degraded bar." },
              "detail": {
                "summary": {
                  "ja": [
                    "詳細は days[].detail.summary から描画",
                    "色・バー・ハイライトは state/color と同期"
                  ],
                  "en": [
                    "Detail is rendered from days[].detail.summary.",
                    "Bar and highlight follow state/color."
                  ]
                }
              },
              "incident_id": "incident-2026-06-19"
            }
          ]
        }
      ]
    },
    {
      "id": "public-surfaces",
      "name": { "ja": "公開サーフェス", "en": "Public surfaces" },
      "children": [
        {
          "id": "website",
          "name": { "ja": "Website", "en": "Website" },
          "fact": { "ja": "トップページを監視", "en": "Monitor public homepage" },
          "monitoring": { "ja": "http", "en": "http" },
          "claim": { "ja": "未接続時は準備中", "en": "Not started when disconnected" },
          "state": "not_started",
          "days": []
        }
      ]
    }
  ],
  "incidents": [
    {
      "id": "incident-2026-06-19",
      "state": "degraded",
      "status": "resolved",
      "date": "2026-06-19",
      "title": { "ja": "YonerAI API 速度低下", "en": "YonerAI API degraded performance" },
      "meta": [
        { "ja": "Resolved", "en": "Resolved" },
        { "ja": "Degraded", "en": "Degraded" },
        { "ja": "Display test", "en": "Display test" }
      ],
      "summary": {
        "ja": ["応答遅延を確認、再試行増幅対策で回復。"],
        "en": ["Response latency observed, recovered after retry amplification control."]
      },
      "footer": { "ja": "2026-06-19 20:20", "en": "2026-06-19 20:20" },
      "affected": {
        "components": [
          {
            "category_id": "core-api",
            "component_id": "yonerai-api",
            "name": { "ja": "YonerAI API", "en": "YonerAI API" },
            "state": "degraded",
            "date": "2026-06-19"
          }
        ],
        "segments": [
          { "state": "operational", "percent": 60 },
          { "state": "degraded", "percent": 40 }
        ]
      },
      "updates": [
        {
          "status": "resolved",
          "label": { "ja": "解決済み", "en": "Resolved" },
          "body": { "ja": ["調査が完了し、復旧済み。"], "en": ["Investigation complete and resolved."] },
          "utc": "2026-06-19 11:20 UTC",
          "jst": "2026-06-19 20:20 JST"
        }
      ]
    }
  ]
}
```

---

## 5) 実運用ブリッジ（1本化）

`status-monitor-results.example.json` などの status input を更新したら:

```powershell
node tools/status-feed-bridge.example.mjs `
  status-monitor-results.example.json `
  generated/status-feed.live.json --watch
```

失敗時は指定した公開feedファイルを上書きしないため、直前の正常feedを維持できます。

`STATUS_MONITOR_FILE` / `STATUS_PUBLIC_FEED_FILE` / `STATUS_PIPELINE_DIR` は環境変数で上書き可能。

healthcheck入力から公開feedまで一気に通す場合:

```powershell
node tools/status-healthcheck-bridge.example.mjs `
  status-healthcheck-input.example.json `
  generated/status-feed.live.json --watch
```

生成済みfeedを `status-feed.json` として公開配置する場合:

```powershell
node tools/promote-status-public-feed.mjs `
  generated/status-feed.live.json `
  status-feed.json
```

外部入力から `status-feed.json` まで一気に同期する場合:

```powershell
node tools/sync-status-public-feed.mjs `
  --input status-healthcheck-input.example.json `
  --public status-feed.json
```

静的ホスティング用の公開パッケージを作る場合:

```powershell
node tools/build-status-public-package.mjs `
  --feed status-feed.json `
  --out generated/public-package
```

公開feedを最新backupから戻す場合:

```powershell
node tools/restore-status-public-feed.mjs
```

`STATUS_HEALTHCHECK_FILE` / `STATUS_PUBLIC_FEED_FILE` / `STATUS_PIPELINE_DIR` は環境変数で上書き可能。

このブリッジは内部で `validate-status-healthcheck.mjs` を先に実行します。
入力が壊れている場合は `collect -> source -> feed` に進まず、公開feedを上書きしません。

AWS CloudWatchなどの数値集計を `aws_metric.value` に反映する場合:

```powershell
node tools/validate-status-aws-metrics.mjs status-aws-metrics.example.json

node tools/fill-status-aws-metrics.mjs `
  status-healthcheck-input.aws-cloudwatch.example.json `
  status-aws-metrics.example.json `
  generated/status-healthcheck-input.aws-filled.json

node tools/build-status-pipeline.mjs `
  generated/status-healthcheck-input.aws-filled.json `
  generated/pipeline-from-aws
```

`fill-status-aws-metrics.mjs` は実行時にもhealthcheck inputとAWS metrics summaryを検査します。

YonerAI内部APIや管理側が出したhealth summaryを反映する場合:

```powershell
node tools/validate-status-yonerai-health.mjs status-yonerai-health.example.json

node tools/fill-status-yonerai-health.mjs `
  status-healthcheck-input.yonerai-api-http.example.json `
  status-yonerai-health.example.json `
  generated/status-healthcheck-input.yonerai-filled.json

node tools/build-status-pipeline.mjs `
  generated/status-healthcheck-input.yonerai-filled.json `
  generated/pipeline-from-yonerai
```

`fill-status-yonerai-health.mjs` は実行時にもhealthcheck inputとYonerAI health summaryを検査します。
