# ARCH_V5

対象範囲: 公開アーキテクチャ（配布ノードモデル #5）
最終更新対象: docs-only
信頼できる一次ソース: `README.md`, `docs/SYSTEM_ARCHITECTURE.md`, `docs/EXTENSIONS.md`

## 概要
YonerAI/ORA は、ユーザーPC上の Node と複数クライアントを中心にしたマルチプラットフォーム基盤。
Web, Discord, 将来のモバイル/デスクトップクライアントは共通の実行面（Core + Tool boundary）に接続する。

## コンポーネント（公開粒度）
- Clients: Web / Discord / 将来の mobile / desktop
- Gateway/API: クライアント入口、認証境界、応答整形
- Core: 実行フローの所有者（推論/実行計画/イベント）
- Tool boundary: risk -> policy -> approval -> audit
- Skills: ローカル/取り込みスキル。strict policy で実行可否を制御
- Relay/Connector: リモート接続・中継（必要時）

## #4 と #5 の責務分離
- #5 (public): 配布可能なNode基盤、公開可能な設計・実装
- #4 (private): 運用詳細、内部Runbook、環境固有オペレーション

## セキュリティ原則（公開可能）
- ユーザー認証と内部サービス認証を分離する
- fail-closed（認証/検証失敗時は止める）
- reason_code + 参照IDで可観測に失敗させる
- 高リスク操作は approval を必須化
- imported skills は strict policy を維持する

## route_score v1（公開方針）
- 単一軸スコアで実行深度を選択
  - 低: 低遅延応答
  - 中: 計画→実行→検証
  - 高: ループ実行（安全ゲート前提）
- 本番閾値はログで較正し、段階的に最適化する

## Vision（画像）方針
- 画像は upload 分離を優先し、メッセージには参照IDを渡す
- 生バイナリをログ/メタに保存しない
- text-only 経路は回帰させない

## 参照
- `docs/AI_STATE.md`
- `docs/DEV_QUICKSTART.md`
- `docs/DECISION_CHAT_SDK.md`
