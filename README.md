# ORA Ecosystem (ORALLM Pro) | ⚡ Universal AI Interface

![ORA Banner](https://img.shields.io/badge/ORA-Universal_AI-7d5bf6?style=for-the-badge&logo=openai)
![Status](https://img.shields.io/badge/Status-Operational-brightgreen?style=for-the-badge&logo=discord)
![Python](https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge&logo=python)
![Architecture](https://img.shields.io/badge/Architecture-Event--Driven-orange?style=for-the-badge)

> **"Your PC, Your Data, Your AI."**
> ORAは、クラウドAIの制約からあなたを解放する、完全ローカル指向の次世代AIアシスタントです。

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
*   ゲーム画面を見せてアドバイスを求めたり、イラストの感想を言い合うことも可能です。

### 3. 🔊 感情を持つ声 (Neural Voice)
ただの機械音声ではありません。**VoiceVox** エンジンと連携し、感情豊かに喋ります。
まるで隣にいるかのようなレスポンス速度で、あなたのDiscord通話に参加し、読み上げや雑談を行います。

### 4. 🛡️ 鉄壁の守り (The Guardian)
「AIにPCを乗っ取られるのでは？」という心配は無用です。
ORAは **Sandbox (砂場)** アーキテクチャを採用しており、許可されたアプリ（メモ帳、電卓、ブラウザ等）以外には指一本触れることができません。
さらに、重要な操作には **管理者権限 (Owner Permission)** が必須となる二重ロックシステムを搭載しています。

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
        Guardian -.->|Block| Dangerous[❌ Dangerous Ops\n(System/Delete)]
    end
    
    Brain -->|Store Memory| DB[(🗄️ SQLite Database)]
```

### 1. The BRAIN (思考中枢)
*   **Engine**: LM Studio (OpenAI-compatible Server)
*   **Context Management**: 会話履歴を自動で要約・圧縮し、長期記憶として保持します。これにより「さっきの話だけど」が通じます。
*   **Fallback**: 画像認識ができないモデル（Mistral等）を使用している場合、自動でGoogle Cloud Vision APIやOCRエンジンに切り替える「自動判断機能」を持っています。

### 2. The BODY (身体)
*   **Event-Driven**: Discordからのイベント（発言、入室、リアクション）を0.1秒単位で検知・反応します。
*   **Voice Pipeline**: 音声を「受信(Whisper)」→「思考(LLM)」→「発話(VoiceVox)」のパイプラインで処理し、リアルタイムに近い対話を実現しています。

### 3. The GUARDIAN (管理者)
*   **Scope Checking**: 全てのコマンド実行前にユーザーのIDと権限レベルを確認します。
*   **Whitelist Execution**: 事前にコード内で定義された `ALLOWED_APPS` リストにあるプログラムしか起動できません。これにより、AIハルシネーションによる誤操作を物理的に防いでいます。

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

---

*Created by YoneRai12 | Powered by ORA Architecture*
