# YonerAI Status Goal Readiness Audit

このファイルは、active goalを完了扱いにできるかを要件別に確認するためのaudit手順です。

機械可読audit:

```powershell
cd status.yonerai.com
node tools/audit-status-goal-readiness.mjs
```

出力:

```text
generated/status-goal-readiness-audit.json
```

---

## 1) audit対象

- UIUX完璧版を壊さず維持できているか
- runtime feed APIが契約化されているか
- JSON schema / example / docs / adapterが揃っているか
- DOM直書きではなくfeed駆動になっているか
- AWS / YonerAI / healthcheck からfeed化できるか
- hover / touch / animation / selected stateの回帰を検出できるか
- public feed / packageにprivate情報が混ざらないか

---

## 2) 注意

このauditは静的証拠を整理するだけです。
以下がない場合、goal完了扱いにはしません。

- `validate-status-contract-suite.mjs` の成功
- `run-status-browser-probe.mjs` の主要viewport成功
- 実ブラウザでのhover/touch/animation/selected確認
- public packageの中身確認
- Cloudflare Zero Trust配下の公開経路確認

---

## 3) 推奨順序

```powershell
cd status.yonerai.com

node tools/validate-status-contract-suite.mjs
node tools/sync-status-public-feed.mjs --input status-healthcheck-input.example.json --public status-feed.json
node tools/build-status-public-package.mjs --feed status-feed.json --out generated/public-package
node tools/run-status-browser-probe.mjs --root generated/public-package --viewport desktop
node tools/run-status-browser-probe.mjs --root generated/public-package --viewport mobile
node tools/run-status-browser-probe.mjs --root generated/public-package --viewport scaled
node tools/audit-status-goal-readiness.mjs
```

この順序を通した上で、実UIの手触りを確認して初めてgoal完了判断ができます。
