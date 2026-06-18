# YonerAI Status Pre-publish Checks

このファイルは、`status.yonerai.com` を公開・反映する前の最低限チェックです。
UI/UXの実ブラウザ確認は別途必要ですが、契約・feed・bridgeの明らかな破綻はここで先に止めます。

運用全体の流れは `STATUS_OPERATIONS_RUNBOOK.md` を参照します。
Goal完了判断の要件別整理は `STATUS_GOAL_READINESS_AUDIT.md` を参照します。

---

## 1) まとめて実行

```powershell
cd status.yonerai.com
node tools/validate-status-contract-suite.mjs
```

軽量版:

```powershell
cd status.yonerai.com
node tools/validate-status-contract-suite.mjs --quick
```

出力:

```text
generated/status-contract-suite-report.json
```

manifestだけ確認:

```powershell
cd status.yonerai.com
node tools/validate-status-integration-manifest.mjs
```

public feedだけ安全検査:

```powershell
cd status.yonerai.com
node tools/validate-status-public-feed-safety.mjs generated/status-feed.live.json
```

生成feedを公開feedへ昇格:

```powershell
cd status.yonerai.com
node tools/promote-status-public-feed.mjs generated/status-feed.live.json status-feed.json
```

外部入力から公開feedまで同期:

```powershell
cd status.yonerai.com
node tools/sync-status-public-feed.mjs --input status-healthcheck-input.example.json --public status-feed.json
```

Cloudflare等へ渡す公開パッケージを作成:

```powershell
cd status.yonerai.com
node tools/build-status-public-package.mjs --feed status-feed.json --out generated/public-package
```

公開feedを直前backupから復元:

```powershell
cd status.yonerai.com
node tools/restore-status-public-feed.mjs
```

---

## 2) スイートが見るもの

- integration manifest
- runtime API contract
- UI/UX regression contract
- healthcheck input examples
- healthcheck -> monitor -> source -> feed pipeline
- AWS metrics summary -> healthcheck -> feed pipeline
- YonerAI health summary -> healthcheck -> feed pipeline
- monitor -> source -> feed pipeline
- source -> feed pipeline
- generated feed -> public status-feed.json promotion
- external input -> public status-feed.json sync
- public-only package build for static hosting
- public status-feed.json restore from backup
- final feed examples
- public feed secret/private endpoint safety

---

## 3) スイートが見ないもの

- 実ブラウザでのhover滑らかさ
- mobile Safari touch挙動
- 4K 200%表示
- Cloudflare Zero Trust配下の実配信
- 実YonerAI API/AWS接続の認証・ネットワーク状態

これらは手動またはブラウザ自動化で別途確認します。

---

## 4) 公開前の判断

最低条件:

- `validate-status-contract-suite.mjs` が通る
- 主要viewportで `STATUS_UIUX_REGRESSION_CONTRACT.md` の項目を確認する
- public feedにsecret/token/private endpointが含まれない
- `build-status-pipeline.mjs` の通常実行では、promote前にpublic feed safety検査が走る
- 監視未接続のものは `準備中` / `not_started` として明示する
- 本番運用claimを実データ接続前に書かない
- `STATUS_INTEGRATION_MANIFEST.md` の公開可/不可ファイル境界を守る
- 必要に応じて `tools/status-runtime-browser-probe.js` をdev環境で読み込み、実画面上のpanel/tooltip/selected数を確認する
- Playwright環境がある場合は `tools/run-status-browser-probe.mjs --viewport mobile|desktop|scaled` で実ブラウザprobeを実行する

Goal完了を主張するには、この静的スイートだけでなく実UI挙動の確認も必要です。
