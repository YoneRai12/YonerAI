# OpenAI Usage & Policy (ORA System)

## 1. 共有無料枠 (Daily Free Allowance)
OpenAI と共有されるトラフィックを毎日無料でご利用いただけます。
詳細なモデルリストやトークン制限は、ルートディレクトリの **`config.yaml`** を参照してください。

### 🚀 High Intel Lane
複雑な推論や高度なコーディングタスクに使用されます。
`gpt-5` シリーズや `o1` (Reasoning) モデルが含まれます。

### ⚡ Stable/Mini Lane
日常会話や軽量なタスクに使用されます。
`gpt-4o-mini` などの高速モデルが含まれます。

## 2. 制限事項 (Critical Constraints)
- **温度 (Temperature) の禁止**: 
  Reasoningモデル（`o1`, `gpt-5`等）に対して `temperature` パラメータを送信するとエラーになります。
  **システム側で自動的に除去されますが**、意図的なパラメータ指定は避けてください。
  対象モデルのリストは `config.yaml` の `model_policies` セクションで確認できます。

- **超過料金**: 
  指定された無料枠を超える使用については、標準料金が適用される場合があります。

## 3. 設定の変更
運用ポリシー（モデルの追加・削除、コスト上限）を変更する場合は、`src` コードではなく **`config.yaml`** を編集してください。
Botの再起動により変更が適用されます。
