# ORA Ecosystem (ORALLM Pro) | ⚡ Universal AI Interface

![ORA Banner](https://img.shields.io/badge/ORA-Universal_AI-7d5bf6?style=for-the-badge&logo=openai)
![Status](https://img.shields.io/badge/Status-Operational-brightgreen?style=for-the-badge&logo=discord)
![Python](https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge&logo=python)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

**ORA** は、単なるDiscord Botではありません。あなたのPC上で動作し、**視覚（Vision）**、**聴覚（Voice）**、そして **システム制御（Control）** を兼ね備えた、次世代のパーソナルAIアシスタント（Universal Interface）です。
ローカルLLM (LM Studio) と連携し、プライバシーを守りながら「あなただけの最強の秘書」として機能します。

---

## 🌌 Core Architecture (アーキテクチャ)

ORAは3つの要素で構成される「エコシステム」です。

### 1. 🧠 The BRAIN (思考中枢)
*   **Local LLM Integration**: LM Studio (Mistral, LLaMA 3, Qwen) を脳として使用。API代を気にせず無限に思考できます。
*   **Universal Memory (SQL)**: 会話履歴、生成された画像、ユーザー情報をSQLデータベースで一元管理。
*   **True Vision**: 画像を直接「見る」能力を持ち、グラフの解析やゲーム画面のアドバイスが可能です。

### 2. 🗣️ The BODY (身体・インターフェース)
*   **Neural Voice**: VoiceVoxエンジンを使用し、遅延を感じさせない自然な日本語で対話します。
*   **Automatic Deafening**: 接続安定化のため、Discord Gatewayに対し適切なステータス管理を行います。
*   **Ear (Whisper)**: あなたの話す言葉をリアルタイムでテキスト化し、聞き取ります。

### 3. 🛡️ The GUARDIAN (システム制御)
*   **Admin Sandbox**: PCの操作権限を持ちながらも、安全なサンドボックス内で動作（許可アプリのみ起動可能）。
*   **Self-Healing**: 自身のコードにエラーが発生した場合、自律的に修復を試みる「自己修復機能」を搭載。

---

## 🚀 Roadmap & Future Features (今後の展望)

現在、以下の機能を開発・計画中です。これにより、ORAはDiscordの枠を超えた「Webプラットフォーム」へと進化します。

### 🔐 Google OAuth Integration (実装予定)
*   **Secure Login**: Googleアカウントを使用した安全なシングルサインオン(SSO)を実装します。
*   **Personalized Experience**: ユーザーごとの設定や履歴をクラウドレベルで同期・管理可能にします。

### 📊 SQL Web Dashboard (実装予定)
*   **Web UI**: ブラウザから直接アクセスできる管理画面を提供します。
*   **Data Visualization**: 会話統計、トークン使用量、サーバー負荷などをグラフで可視化します。
*   **Log Explorer**: SQLデータベースに蓄積された過去の会話ログやエラーログを、Web上で検索・閲覧可能にします。

### 🖼️ Web Gallery & Chat Interface (実装予定)
*   **Image Gallery**: 生成した画像（Stable Diffusion）をWeb上で一覧表示・管理・ダウンロードできるギャラリー機能。
*   **Web Chat**: Discordを開かなくても、ブラウザからORAと直接会話できるインターフェース。
*   **Cross-Platform**: スマホやタブレットのブラウザからも、自宅のPCで動くORAを操作可能にします。

---

## 🎮 Command Reference (コマンド一覧)

### 🗣️ Voice & Music
| コマンド | 動作 | 詳細 |
| :--- | :--- | :--- |
| `join_voice_channel` | VC参加 | 読み上げを開始します。 |
| `music_play` | 音楽再生 | YouTubeからストリーミング再生します（メモリバッファリング）。 |
| `skip` / `stop` | 制御 | 曲のスキップ・停止。 |
| `change_voice` | 声変更 | 「ずんだもん」「四国めたん」などに変更。 |
| **「さっきの曲戻して」** | リプレイ | 履歴から1つ前の曲を再生します。 |

### 🛠️ System & Admin
| ツール名 | 動作 | 詳細 |
| :--- | :--- | :--- |
| `get_system_stats` | 監視 | CPU/GPU/VRAMの状態を表示。 |
| `system_control` | PC操作 | 音量調整、メモ帳起動など（管理者のみ）。 |
| `create_channel` | 管理 | チャンネル作成（Sub-Admin以上）。 |

---

## ⚠️ Setup Guide (導入手順)

### 必須要件
*   **OS**: Windows 10 / 11
*   **VoiceVox**: 音声合成エンジン
*   **LM Studio**: ローカルLLMサーバー
*   **Stable Diffusion (A1111)**: 画像生成用（API有効化必須）

### 重要: 依存ファイル
`libopus-0.x64.dll` がルートディレクトリに必須です。これがないとVC接続がタイムアウトします。

---

*Created by YoneRai12 | Powered by ORA Architecture*
