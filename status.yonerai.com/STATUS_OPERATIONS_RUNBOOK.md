# YonerAI Status Operations Runbook

このrunbookは、`status.yonerai.com` をfeed駆動で運用するための手順です。
UI/CSS/DOMを直接編集せず、内部データを `yonerai.status.feed.v1` に変換してruntimeへ渡します。

---

## 0) 基本方針

- ブラウザが読むのは `yonerai.status.feed.v1` だけ。
- AWS/YonerAI/API/cron/管理UIはDOMを直接触らない。
- 公開前にschema検査とpublic feed safety検査を通す。
- `status-feed.json` は `promote-status-public-feed.mjs` または `sync-status-public-feed.mjs` で更新する。
- 問題が出たら `restore-status-public-feed.mjs` でfeedだけ戻す。

---

## 1) 最短: healthcheck inputから公開feedへ同期

```powershell
cd status.yonerai.com
node tools/sync-status-public-feed.mjs --input status-healthcheck-input.example.json --public status-feed.json
```

これは以下を内部で実行します。

```text
healthcheck input
-> build-status-pipeline
-> validate-status-feed
-> validate-status-public-feed-safety
-> promote-status-public-feed
-> status-feed.json
```

---

## 2) YonerAI health summaryから同期

YonerAI側が出すJSON:

```json
{
  "schema_version": "yonerai.status.yonerai-health.v1",
  "components": [
    {
      "category_id": "core-api",
      "component_id": "yonerai-api",
      "state": "operational",
      "message": {
        "ja": "YonerAI API operational",
        "en": "YonerAI API operational"
      }
    }
  ]
}
```

同期:

```powershell
cd status.yonerai.com
node tools/sync-status-public-feed.mjs --input status-yonerai-health.example.json --public status-feed.json
```

テンプレートhealthcheckを指定する場合:

```powershell
node tools/sync-status-public-feed.mjs `
  --input status-yonerai-health.example.json `
  --healthcheck status-healthcheck-input.yonerai-api-http.example.json `
  --public status-feed.json
```

---

## 3) AWS metrics summaryから同期

AWS側または別collectorが出すJSON:

```json
{
  "schema_version": "yonerai.status.aws-metrics.v1",
  "metrics": [
    {
      "label": "lambda-errors",
      "namespace": "AWS/Lambda",
      "metric_name": "Errors",
      "statistic": "Sum",
      "value": 0
    }
  ]
}
```

同期:

```powershell
cd status.yonerai.com
node tools/sync-status-public-feed.mjs --input status-aws-metrics.example.json --public status-feed.json
```

テンプレートhealthcheckを指定する場合:

```powershell
node tools/sync-status-public-feed.mjs `
  --input status-aws-metrics.example.json `
  --healthcheck status-healthcheck-input.aws-cloudwatch.example.json `
  --public status-feed.json
```

---

## 4) 生成だけして公開しない

```powershell
cd status.yonerai.com
node tools/sync-status-public-feed.mjs `
  --input status-healthcheck-input.example.json `
  --workdir generated/sync-preview `
  --no-promote
```

出力:

```text
generated/sync-preview/pipeline/status-feed.generated.json
generated/sync-preview/status-sync-report.json
```

---

## 5) 生成済みfeedを公開feedへ昇格

```powershell
cd status.yonerai.com
node tools/promote-status-public-feed.mjs generated/status-feed.live.json status-feed.json
```

promote時に行うこと:

- `validate-status-feed.mjs`
- `validate-status-public-feed-safety.mjs`
- 既存 `status-feed.json` のbackup
- atomic replace

---

## 6) feedだけロールバック

最新backupから戻す:

```powershell
cd status.yonerai.com
node tools/restore-status-public-feed.mjs
```

backupを指定:

```powershell
node tools/restore-status-public-feed.mjs `
  generated/public-feed-backups/status-feed.json.xxxxx.bak `
  status-feed.json
```

restore時にもfeed schema検査とpublic feed safety検査を通します。

---

## 7) Cloudflare/static hosting用package作成

```powershell
cd status.yonerai.com
node tools/build-status-public-package.mjs --feed status-feed.json --out generated/public-package
```

packageに入るもの:

- `index.html`
- `styles.css`
- `mock-status-adapter.js`
- `status-feed.json`
- `status-runtime-api.contract.json`
- `status-uiux-regression.contract.json`
- `package-manifest.json`

packageに入れないもの:

- healthcheck input
- monitor/source input
- AWS/YonerAI summary
- pipeline report
- backup
- tools
- token/secret

---

## 8) 公開前チェック

静的contract suite:

```powershell
cd status.yonerai.com
node tools/validate-status-contract-suite.mjs
```

軽量版:

```powershell
node tools/validate-status-contract-suite.mjs --quick
```

実ブラウザprobe（Playwrightがある場合）:

```powershell
node tools/run-status-browser-probe.mjs --viewport desktop
node tools/run-status-browser-probe.mjs --viewport mobile
node tools/run-status-browser-probe.mjs --viewport scaled
```

---

## 9) 障害時の優先順位

1. `status-feed.json` だけ壊れた
   `restore-status-public-feed.mjs` で戻す。

2. 生成feedにsecret/private URLが混ざる
   `validate-status-public-feed-safety.mjs` の失敗内容を見て、healthcheck/source側から削る。

3. AWS/YonerAI入力が壊れている
   `validate-status-aws-metrics.mjs` または `validate-status-yonerai-health.mjs` を先に通す。

4. UIでtooltip/panel/selectedが壊れている
   `run-status-browser-probe.mjs` と `STATUS_UIUX_REGRESSION_CONTRACT.md` を見る。

5. 公開packageに不要ファイルが混ざる
   `build-status-public-package.mjs` を使い、`status.yonerai.com` 全体を直接公開しない。

---

## 10) Goal完了に必要な証拠

このrunbookや静的ツールだけではgoal完了ではありません。
完了主張には最低限、以下が必要です。

- `validate-status-contract-suite.mjs` が通る
- `run-status-browser-probe.mjs` が主要viewportで通る
- 実ブラウザでhover/touch/animation/selected stateを確認する
- `status-feed.json` がfeed駆動で更新される
- public packageにprivate/generated/internalファイルが混ざらない
- Cloudflare Zero Trust配下の公開経路で不要なsecret/private情報が見えない

要件別のreadiness audit:

```powershell
node tools/audit-status-goal-readiness.mjs
```

詳細は `STATUS_GOAL_READINESS_AUDIT.md` を参照します。
