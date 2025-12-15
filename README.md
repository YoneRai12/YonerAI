# ORA Ecosystem (ORALLM Pro) | ⚡ Universal AI Interface

![ORA Banner](https://img.shields.io/badge/ORA-Universal_AI-7d5bf6?style=for-the-badge&logo=openai)
![Status](https://img.shields.io/badge/Status-Operational-brightgreen?style=for-the-badge&logo=discord)
![Python](https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge&logo=python)
![Architecture](https://img.shields.io/badge/Architecture-Event--Driven-orange?style=for-the-badge)

> **"Your PC, Your Data, Your AI."**
> ORAは、クラウドAIの制約からあなたを解放する、完全ローカル指向の次世代AIアシスタントです。

---

## ✨ v2.3 Update Highlights (最新アップデート)
*   **🎨 FLUX.2 & FLUX.1 Integration**: 最新鋭の画像生成モデル **FLUX.2** および **FLUX.1 dev** に完全対応。サーバーグレードの超高画質生成が可能になりました。
*   **🚀 RTX 5090 Optimized**: 次世代GPU **RTX 5090** のパワーを最大限引き出す **Normal/Low VRAMハイブリッド制御** を搭載。32GB VRAMを効率的に使い切り、巨大モデルでもクラッシュしません。
*   **🧠 Auto-Healing Workflow**: ComfyUIの接続エラーやメモリ不足（OOM）を自動検知。必要に応じて設定を自動調整し、ユーザーの手を煩わせることなく復旧します。
*   **🔍 Enhanced Search Visualization**: Google検索機能が進化。サムネイル画像とスニペット要約を表示し、リンクを開かずに情報を把握できます。
*   **🎮 Shiritori Game**: AIとしりとり対決が可能。Botはルールを自律的に判定します。
*   **🛠️ Diagnostic Tools**: 接続やクラッシュの原因を特定する診断ツール (`diagnose_connection.ps1`, `debug_comfy_trace.ps1`) を標準同梱しました。
*   **👥 Multi-User Voice Support**: 複数人の同時発話を個別に認識・処理可能です。
*   **💰 Points System**: チャットでポイントが貯まるシステムを搭載。
*   **🛡️ Safety First**: NSFWフィルターと標準モデル固定により安全性を確保。
*   **🔊 Voice Utilities**: 召喚、ミュート操作、タイマー機能などを追加。
*   **💳 Visual Card Responses**: 美しいEmbed形式での応答。
*   **💭 Interactive Thoughts**: 思考中のリアルタイムアニメーション表示。

---

## 🌟 What makes ORA Amazing? (ORAの何が凄いの？)

ORAは単なる「チャットボット」ではありません。あなたのPCの中に住む、**独立した人格を持つパートナー**です。

### 1. 🧠 完全ローカル思考 (Local Brain)
ChatGPTやGeminiのAPIに依存せず、あなたのPC内にある **LM Studio** を脳として使用します。
*   **プライバシー完全保護**: あなたの会話内容が外部サーバーに送信され、学習に使われることはありません。
*   **検閲なし**: 商用AIのような厳しいフィルタリングがなく、あなたが望む通りの自由な会話が可能です。
*   **コストゼロ**: どれだけ会話しても、どれだけ画像を解析しても、API料金は一切かかりません。

### 2. 👁️ 真の視覚能力 (True Vision)
ORAは画像を「文字」としてではなく「映像」として理解します。
*   「このエラー何？」と画面写真を送れば、ログを読んで解決策を提示します。
*   「このグラフを分析して」と言えば、トレンドを読み解きます。
*   **Replay Vision**: メッセージの返信先にある画像も自動で認識します。

### 3. 🔊 感情を持つ声 (Neural Voice)
ただの機械音声ではありません。**VoiceVox** エンジンと連携し、感情豊かに喋ります。
まるで隣にいるかのようなレスポンス速度で、あなたのDiscord通話に参加し、読み上げや雑談を行います。

### 4. 🛡️ 鉄壁の守り (The Guardian & Lockdown)
「AIにPCを乗っ取られるのでは？」という心配は無用です。
*   **Sandbox**: 許可されたアプリ（メモ帳、電卓等）以外には指一本触れることができません。
*   **Creator Lockdown**: ファイル作成やシステム操作といった危険な権限は、**制作者 (Creator)** という特別なIDを持つ人間（あなた）のみに限定されています。たとえサーバー管理者であっても、制作者以外はこれらの機能を使えません。
*   **Loop Breaker**: 万が一AIが暴走してツールを連打しても、自動で検知して緊急停止する「自己防衛回路」を搭載しています。

---

## ⚙️ Architecture & Mechanism (仕組み)

ORAは3つの独立したモジュールが連携して動く **分散型アーキテクチャ** を採用しています。

```mermaid
graph TD
    User[👤 User] -->|Voice/Chat| Discord[🎮 Discord Gateway]
    
    subgraph "ORA Core System (Your PC)"
        Discord -->|Event| Body[🗣️ The BODY\n(Discord.py Client)]
        
        Body -->|See Image| Vision[👁️ Vision Module]
        Body -->|Hear Audio| Ears[👂 Whisper STT]
        
        Body -->|Think| Brain[🧠 The BRAIN\n(LM Studio / Local LLM)]
        Brain -->|Response| Body
        
        Body -->|Speak| Mouth[🔊 VoiceVox Engine]
        Body -->|Action| Guardian[🛡️ Guardian Sandbox]
        
        Guardian -->|Safe Exec| Apps[📂 Allowed Apps\n(Notepad/Chrome)]
        Guardian -.->|Block| Dangerous[❌ Dangerous Ops\n(Creator Only)]
    end
    
    Brain -->|Store Memory| DB[(🗄️ SQLite Database)]
```

### 1. The BRAIN (思考中枢)
*   **Engine**: LM Studio (OpenAI-compatible Server)
*   **Context Management**: 会話履歴を自動で要約・圧縮し、長期記憶として保持します。

### 2. The BODY (身体)
*   **Event-Driven**: Discordからのイベント（発言、入室、リアクション）を0.1秒単位で検知・反応します。
*   **Interactive UI**: ステータスマネージャが思考プロセスをリアルタイムでDiscord上に描画します。

### 3. The GUARDIAN (管理者)
*   **Scope Checking**: 全てのコマンド実行前にユーザーのIDと権限レベルを確認します。
*   **Creator Lockdown Mode**: デフォルトで最強のセキュリティ設定が有効になっており、重要なコマンドは制作者ID以外からは一切受け付けません。

---

## 🚀 Roadmap & Future (今後の展望)

ORAは現在も進化の途中です。Discordという「窓」を通して、Webやモバイルまで世界を広げようとしています。

### 🔐 Google OAuth Integration (実装予定)
*   **概要**: Googleアカウントによる安全なログイン。
*   **目的**: 家族や友人がORAを使う際、それぞれの「専用設定」や「専用の記憶」を持てるようにします。

### 📊 SQL Web Dashboard (実装予定)
*   **概要**: ブラウザで見れる管理画面。
*   **目的**: 「今日ORAと何話したっけ？」をカレンダー形式で見返したり、生成した画像のコレクションアルバムをWebで見れるようにします。

### 🖼️ Web Gallery & Chat (実装予定)
*   **概要**: Discord不要のWebインターフェース。
*   **目的**: スマホのブラウザから直接ORAに話しかけたり、外出先から家のPCのORAに指示を出せるようになります。

---

## 🛠️ Tech Stack (技術スタック)

エンジニア向けの技術情報です。

| Component | Technology | Role |
| :--- | :--- | :--- |
| **Language** | Python 3.11 | Core Logic |
| **Bot Framework** | discord.py 2.3+ | Discord API Wrapper |
| **LLM Server** | LM Studio / Ollama | Local Inference Server |
| **Vision** | Pillow / OpenCV / Tesseract | Image Processing & OCR |
| **Voice** | VoiceVox Engine | Neural TTS |
| **Database** | SQLite3 (aiobos) | Asynchronous Data Persistence |
| **Audio** | PyNaCl / Opus | Voice Encoding |
| **UI** | Discord Embeds & Views | Interactive Frontend |

---

*Created by YoneRai12 | Powered by ORA Architecture*
