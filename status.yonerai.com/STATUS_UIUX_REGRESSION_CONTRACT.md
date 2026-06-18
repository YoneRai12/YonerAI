# YonerAI Status UI/UX Regression Contract

このファイルは、内部feedやruntime bridgeを変更しても、YonerAI Status のUI/UXを壊さないための回帰契約です。
機械可読版は `status-uiux-regression.contract.json` です。

静的検査:

```powershell
node tools/validate-status-uiux-regression.mjs
```

実ブラウザ上の状態確認probe:

```js
window.YonerAIStatusProbe.run({ log: true })
```

dev環境で `tools/status-runtime-browser-probe.js` を読み込んでから実行します。

Playwrightが使える環境では、任意runnerでも実行できます。

```powershell
cd status.yonerai.com
node tools/run-status-browser-probe.mjs --viewport desktop
node tools/run-status-browser-probe.mjs --viewport mobile
node tools/run-status-browser-probe.mjs --viewport scaled
```

---

## 1) 絶対に壊してはいけないもの

- hover tooltip が点滅しない
- mobile touch でtooltipが出る
- mobile tooltip は指で隠れない位置に出る
- selected highlight は現在routeに一致するbarだけに付く
- 一度選んだbarのhighlightが、戻る/開き直し/再renderで残留しない
- bar cascade は左から右へ1回だけ流れる
- category / child の開閉で最後にガクッと跳ねない
- `#barTooltip` / `#barDetailPanel` / `#incidentDetailPanel` が二重生成されない
- category overview は子component rowの状態から集約する
- dark mode で detail card / incident timeline / affected row が白浮き・黒文字化しない
- mobileと4K 200%相当で日付範囲や「今日」表示が縦文字にならない

---

## 2) 重要なselector

```text
#barTooltip
#barDetailPanel
#incidentDetailPanel
.bar
.bar.is-selected
.bar.is-hovered
.category
.category-summary
.child
.child-summary
.affected-timeline
#themeToggle
```

---

## 3) runtimeで見るべき診断値

```js
const state = window.YonerAIStatusRuntime.getState();
```

最低限:

- `selectedCount` は `0` または `1`
- `statusPanels` は `0` または `1`
- `incidentPanels` は `0` または `1`
- `error` は valid feed では空
- `bars` はfeed由来の描画数と一致
- `selectedRoute` は現在hashと矛盾しない

---

## 4) viewport別の確認

### Mobile Safari相当

- `390x844`
- coarse pointer
- touchでbarをなぞってtooltipが出る
- tooltipが指の上側に出る
- scrollまたは外側touchまでtooltipが不自然に消えない
- range headerが折れて縦文字にならない

### Desktop

- `1440x1000`
- fine pointer
- hover tooltipが滑らか
- bar間を移動してもtooltipが点滅しない
- cursor形状が不自然に切り替わらない

### 4K 200%相当

- `1920x1600`
- scale labelが横向き
- 「今日」の右余白が潰れない
- status scale lineが文字幅で暴れない

---

## 5) feed/runtime変更時の必須観点

feed生成・bridge・runtime APIを変更した場合は、UIを直接いじっていなくても以下を確認します。

- feed差し替え後、存在しないrouteのselected highlightが残らない
- invalid feedをrejectした後、既存UIが壊れない
- `trySetFeed` が失敗してもtooltip/panelが二重化しない
- category overviewが子componentの最大severityから導出されている
- incident detailとbar detailが同時に出ない
- `clearInteractionState()` は明示した時だけhover/touch/selectedを掃除する

---

## 6) 自動化する場合の期待値

```js
const tooltipCount = document.querySelectorAll("#barTooltip").length;
const selectedCount = document.querySelectorAll(".bar.is-selected").length;
const statusPanels = document.querySelectorAll("#barDetailPanel").length;
const incidentPanels = document.querySelectorAll("#incidentDetailPanel").length;

if (tooltipCount !== 1) throw new Error("tooltip duplicated");
if (selectedCount > 1) throw new Error("selected highlight duplicated");
if (statusPanels > 1) throw new Error("bar detail panel duplicated");
if (incidentPanels > 1) throw new Error("incident detail panel duplicated");
```

同じ観点をまとめて読むprobe:

```js
const report = window.YonerAIStatusProbe.run();
if (!report.ok) console.error(report.failed);
```

契約とruntime adapterの最低限のズレは以下で確認します。

```powershell
node tools/validate-status-uiux-regression.mjs
```

---

## 7) 方針

UI/UXが完璧な版を壊さないため、内部ロジック変更では以下を守ります。

- DOM直書きではなくfeed更新だけにする
- 生成feedのschema validationを通す
- runtime API contractを通す
- UIUX regression contractの不変条件に反する変更をしない
