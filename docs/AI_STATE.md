# AI_STATE

対象範囲: 公開リポジトリ `YonerAI`（配布ノードモデル #5）
最終更新対象: docs-only
信頼できる一次ソース: `README.md`, `docs/SYSTEM_ARCHITECTURE.md`, `docs/EXTENSIONS.md`, `src/cogs/handlers/chat_handler.py`, `src/cogs/tools/tool_handler.py`

## いまの到達点（公開可能）
- ORA/YonerAI は「Node + Clients + Relay + Core」のマルチプラットフォーム基盤。
- Web は入口の 1 つで、Discord など他経路と同じ Core/Tool 防衛線に接続される。
- ツール実行は常に `risk -> policy -> approval -> audit` の順で評価される。
- `reason_code` と参照IDにより、失敗を追跡可能な形で返す設計を維持している。
- `route_score` は単一軸（0..1）で扱い、`FAST/TASK/AGENT` の実行深度を切り替える方針。

## 現在フォーカス
1. 配布版 (#5) を壊さない速度で機能追加する。
2. 公開範囲と私用運用情報の境界を維持する。
3. route_score を運用ログで較正し、閾値を段階調整する。

## #4 と #5 の境界（公開版）
- #5（公開repo）: ユーザーPCで動く Node/Client 配布モデル。
- #4（私用/運用repo）: 常時運用・内部Runbook・運用自動化。
- 公開repoには、実運用の内部経路/秘密設定/内部診断値を直接入れない。

## 回帰禁止
- text-only チャットの payload / route / UI / streaming を壊さない。
- service-auth 境界、domain split、skills strict policy を弱めない。

## 次の実装方針（公開可能）
- Chat SDK は「アダプタ層」に限定して採用判断する。
- Core の意思決定ロジック（Python）を置き換えない。
- 機能拡張は防衛線を通る最小差分で行う。

## 参照
- `docs/ARCH_V5.md`
- `docs/DEV_QUICKSTART.md`
- `docs/DECISION_CHAT_SDK.md`
