# YonerAI Status Integration Manifest

機械可読版:

- `status-integration.manifest.json`

このmanifestは、`status.yonerai.com` を他プロジェクトやYonerAI内部監視へ接続するときの地図です。
UIを直接編集せず、内部データをfeedへ変換してruntimeに渡す構造を固定します。

運用手順は `STATUS_OPERATIONS_RUNBOOK.md` にまとめています。

---

## 1) 公開runtime

公開ページ:

- `index.html`
- `styles.css`
- `mock-status-adapter.js`

runtime契約:

- `status-runtime-api.contract.json`
- `STATUS_RUNTIME_FEED_API.md`

UI/UX回帰契約:

- `status-uiux-regression.contract.json`
- `STATUS_UIUX_REGRESSION_CONTRACT.md`

---

## 2) データの流れ

```text
YonerAI API / AWS / manual / scheduler
-> yonerai.status.healthcheck.v1
-> yonerai.status.monitor.v1
-> yonerai.status.source.v1
-> yonerai.status.feed.v1
-> runtime feed API
-> UI
```

ブラウザが直接読む最終入力は `yonerai.status.feed.v1` だけです。

---

## 3) どこを編集すれば表示が変わるか

運用状態を変える:

- `healthcheck` inputを更新
- または `source` の `days` / `incidents` を更新
- `tools/build-status-pipeline.mjs` でfeed生成
- 通常のpipelineはpromote前にfeed schema検証とpublic feed safety検査を通す

AWS CloudWatchなどの集計結果を反映する:

- `status-aws-metrics.example.json` と同じ形式で数値JSONを出す
- `tools/validate-status-aws-metrics.mjs` で検査する
- `tools/fill-status-aws-metrics.mjs` で `aws_metric.value` を埋める
- `fill-status-aws-metrics.mjs` は実行時にもhealthcheck inputとAWS metrics summaryを検査する
- 埋めたhealthcheck inputを `tools/build-status-pipeline.mjs` またはbridgeへ渡す

YonerAI API側の集計済みhealth summaryを反映する:

- `status-yonerai-health.example.json` と同じ形式で `component_id/state/message` を出す
- `tools/validate-status-yonerai-health.mjs` で検査する
- `tools/fill-status-yonerai-health.mjs` で対象componentの `checks` をstatic checkへ置き換える
- `fill-status-yonerai-health.mjs` は実行時にもhealthcheck inputとYonerAI health summaryを検査する
- 生成されたhealthcheck inputを `tools/build-status-pipeline.mjs` またはbridgeへ渡す

見た目を変える:

- `styles.css`
- `mock-status-adapter.js`

ただし、見た目を変える場合は `STATUS_UIUX_REGRESSION_CONTRACT.md` の不変条件を守ります。

---

## 4) 公開してよいもの

- `index.html`
- `styles.css`
- `mock-status-adapter.js`
- `status-feed.json`
- `generated/status-feed.live.json`
- `status-runtime-api.contract.json`
- `status-uiux-regression.contract.json`

---

## 5) 公開してはいけないもの

- token入りhealthcheck input
- private URLを含むraw monitor result
- local absolute pathを含むpipeline report
- AWS credentials
- YonerAI API bearer token
- private runtime inventory

---

## 6) 1コマンド検査

```powershell
cd status.yonerai.com
node tools/validate-status-contract-suite.mjs
```

通常の `tools/build-status-pipeline.mjs` は、`--skip-validate` を付けない限り、生成feedをpromoteする前にpublic feed safety検査も実行します。

public feed安全検査:

```powershell
node tools/validate-status-public-feed-safety.mjs generated/status-feed.live.json
```

公開feedへ昇格:

```powershell
node tools/promote-status-public-feed.mjs generated/status-feed.live.json status-feed.json
```

このpromoteは、feed schema検査とpublic feed safety検査を通してから既存 `status-feed.json` をbackupし、atomic replaceします。

外部入力から公開feedまで同期:

```powershell
node tools/sync-status-public-feed.mjs --input status-healthcheck-input.example.json --public status-feed.json
```

`sync-status-public-feed.mjs` は入力schemaを自動判定します。`aws-metrics` / `yonerai-health` の場合は対応するfillを実行してからpipelineとpromoteへ進みます。

Cloudflare等へ渡す公開パッケージ作成:

```powershell
node tools/build-status-public-package.mjs --feed status-feed.json --out generated/public-package
```

このpackageには、公開runtimeと検証済み `status-feed.json` だけを入れます。healthcheck input、AWS/YonerAI summary、pipeline report、backup、toolsは含めません。

公開feedをbackupから復元:

```powershell
node tools/restore-status-public-feed.mjs
```

引数なしの場合、`generated/public-feed-backups/` の最新backupを使います。復元前にもfeed schema検査とpublic feed safety検査を通します。

AWS metric値をhealthcheckへ反映:

```powershell
node tools/validate-status-aws-metrics.mjs status-aws-metrics.example.json

node tools/fill-status-aws-metrics.mjs `
  status-healthcheck-input.aws-cloudwatch.example.json `
  status-aws-metrics.example.json `
  generated/status-healthcheck-input.aws-filled.json
```

YonerAI health summaryをhealthcheckへ反映:

```powershell
node tools/validate-status-yonerai-health.mjs status-yonerai-health.example.json

node tools/fill-status-yonerai-health.mjs `
  status-healthcheck-input.yonerai-api-http.example.json `
  status-yonerai-health.example.json `
  generated/status-healthcheck-input.yonerai-filled.json
```

この検査はブラウザを起動しません。
実UIのhover/touch/animation確認は別途必要です。

---

## 7) claim rules

- `not_started` は準備中または未接続であり、障害ではない
- `alpha_only` はalpha限定であり、本番運用ではない
- `operational` は実データまたは明示mock feedがそう示す場合のみ
- live monitoring接続前にproduction availabilityを主張しない
- mock/display-test feedはmock/display-testであることを表示する
