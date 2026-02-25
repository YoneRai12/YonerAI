# DECISION_CHAT_SDK

対象範囲: 公開技術判断（docs-only）
最終更新対象: docs-only
一次ソース:
- https://chat-sdk.dev/
- https://github.com/vercel/chat-sdk
- https://vercel.com/changelog/ai-sdk-5

## 結論
Chat SDK は **アダプタ層としてのみ採用** する。
Core意思決定・安全制御・監査の正本は引き続き Python 側に置く。

## 得られるもの（採用メリット）
1. クライアント/チャネル接続の実装効率向上（UI/チャネル差分の吸収）
2. ストリーミングUI統合の標準化
3. 将来の複数プラットフォーム展開における接続層の共通化

## 得られないもの（非目標）
1. Coreの実行ロジック・ポリシー制御の代替
2. 既存の risk -> policy -> approval -> audit の置換
3. 内部認証境界・監査境界の簡略化

## 採用形（本プロジェクト）
- Chat SDK: 入出力アダプタ（Gateway側）
- Python Core: ルーティング判断、実行、監査、失敗分類の正本
- 連携方式: Chat SDKサービスが既存Core APIへフォワード

## リスク
1. SDKの更新速度が速く、バージョン差分追随が必要
2. チャネル別機能差（同一機能が全チャネルで揃わない）
3. 追加アダプタ導入時のセキュリティ面積増大

## リスク緩和
- PoCは private 側で限定実装し、公開側は設計文書まで
- 既存防衛線（service-auth / reason_code / approval）を必須条件にする
- ロールアウトは read-only観測→限定有効化→段階展開

## 最終判断
- **Use as adapter layer only**
- **Do not migrate core decision logic out of Python**

## 次ステップ
1. private repo で chat-gateway PoC
2. Discord経路で実運用検証
3. 問題なければ他プラットフォームアダプタを段階追加
