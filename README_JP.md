# ORA Discord Bot - Ultimate Edition 🌌
### *RTX 5090のための次世代AIオーケストレーター*

<div align="center">

![ORA Banner](https://raw.githubusercontent.com/YoneRai12/ORA/main/docs/banner.png)

[![Discord](https://img.shields.io/badge/Discord-Join-7289DA?style=for-the-badge&logo=discord)](https://discord.gg/YoneRai12)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python)](https://www.python.org/)
[![Model](https://img.shields.io/badge/Brain-Qwen2.5--VL-blue?style=for-the-badge)](src/config.py)
[![System](https://img.shields.io/badge/System-Self--Healing-green?style=for-the-badge)](src/utils/healer.py)
[![GPU](https://img.shields.io/badge/GPU-RTX%205090%20Optimized-76B900?style=for-the-badge&logo=nvidia)](https://www.nvidia.com/)

<div align="center">

[![English](https://img.shields.io/badge/Language-English-blue?style=for-the-badge)](README.md)
[![Japanese](https://img.shields.io/badge/言語-日本語-red?style=for-the-badge)](README_JP.md)

</div>

</div>

---

## 🤯 The Singularity Architecture (v4.2)

ORAはもはや単なる「Bot」ではありません。あなたのPCに宿る **生きているAIオペレーティングシステム** です。
エラーが起きれば自らコードを書き換えて修復し、あなたが寝ている間はサブPCからメインPCを監視します。

### ✨ なぜ ORA なのか？ (RTX 5090 Advantage)

| 機能 | 詳細 |
| :--- | :--- |
| **💰 月額ゼロ** | ChatGPT Plus ($20/月) と異なり、ORAは **100%ローカル** 動作。知能はあなたの所有物です。 |
| **🔒 完全プライバシー** | データはPCから出ません。チャットも画像も音声も、全てあなたのハードウェアで処理されます。 |
| **🧬 自己修復 (Auto-Healer)** | クラッシュしてもスタックトレースを解析し、Pythonパッチを書いてホットリロードします。 |
| **⚡ ハイブリッド脳** | **Qwen 2.5-VL 32B** (ローカル高速) と **GPT-5.1** (クラウド知能) を適材適所で使い分けます。 |

---

## 📚 技術詳細ドキュメント (Deep Dive)
**※以下はエンジニア向けの極めて詳細なドキュメント(英語)です。**

*   **[📖 ユーザーガイド (User Manual)](docs/USER_GUIDE.md)**: `@ORA` の使い方、コマンド一覧、ダッシュボード入門。
*   **[🏗️ システムアーキテクチャ (Architecture)](docs/SYSTEM_ARCHITECTURE.md)**: Omni-Routerの仕組み、IPC通信プロトコル。
*   **[🧬 Auto-Healerの仕組み (Self-Repair)](docs/AUTO_HEALER.md)**: 実行時に自分のコードを書き換えるロジックの全貌。
*   **[💻 NERV Dashboard (UI)](docs/NERV_DASHBOARD.md)**: "Red Alert" システムやWebSocket連携の裏側。
*   **[🛰️ サテライトシステム (WOL)](docs/SATELLITE_SYSTEM.md)**: Mac/Sub-PCからRTX5090を叩き起こす制御フロー。

---

## 🆕 最新アップデート: v4.2 (2026/01/10)

### 🛡️ 究極のセキュリティ & NERV UI
*   **ハードコード完全廃止**: 全ての設定を環境変数 (`.env`) に移行。GitHub公開も安全です。
*   **NERV Red Alert**: 管理者オーバーライド (`/override`) 発動時、ダッシュボードが **"ヘキサゴングリッド緊急モード"** へ変形します。

### 🧬 生体的システム (Deep Dive)

#### 1. Auto-Healer Engine (自己修復)
**「自ら治るソフトウェア」**
`src/utils/healer.py` が例外をキャッチすると、GPT-5-Codexが修正コードを書き、2秒以内に適用・再起動します。

#### 2. 自律進化 (Genetic Self-Evolution)
アップデートを待つ必要はありません。**あなたが頼むのです**。
*   ユーザ:「ビットコインの価格を確認する機能を追加して」
*   ORA: `src/cogs/crypto.py` を書き、ロードし、`/crypto` コマンドを即座に使用可能にします。

#### 3. Omni-Router & Gaming Mode
*   **Qwen 2.5-VL 32B**: 通常会話、画像認識（ローカル・無料）。
*   **GPT-5.1-Codex**: 複雑なコーディング（クラウド）。
*   **Gaming Check**: `valorant.exe` 等を検知すると、自動で32Bモデルをアンロードし、FPSを確保します。

---

## (以下、v4.0以前の機能詳細)

## 🚀 概要 (Classic)
ORAは、世界最先端のオープンソースモデルを統合し、Discord内でシームレスな統合体験を提供します。

### 🧠 2つの動作モード
- **Smart Mode (推奨)**:
  - **GPT-5 Series** (OpenAI) や **Gemini 2.0** (Google) の強大な知能を借りて、難解なコード生成や画像認識を行います。
- **Private Mode (デフォルト)**:
  - **完全ローカル**。データは1バイトたりとも外部に送信されません。

---

### 🌟 技術的ハイライト (v3.x - v4.0)
- **🧠 デュアルブレイン**: 高速な「会話モデル」と深く考える「推論モデル」の自動切り替え。
- **👁️ 真の視覚**: 動画や画像を人間レベルで認識。
- **🎨 映画級アート**: FLUX.1による4K画像生成。
- **🗣️ 音声合成**: T5Gemma/VoiceVoxによる感情豊かな応答。

## 🆕 Update v4.0 (2025/12/30) - Mac対応
### 🍎 Apple Silicon完全対応
M1/M2/M3 MacでもORAのBrainを動作させることが可能になりました。

## 🆕 Update v3.9 (2025/12/26) - Dashboard
システムの状態を一目で把握できるダッシュボードUIを実装。
![Dashboard v3.9](docs/dashboard_v3.9.png)

---

## 💻 セットアップ (v4.2 最新手順)

### 1. 準備
```bash
git clone https://github.com/YoneRai12/ORA.git
pip install -r requirements.txt
```

### 2. 設定 (.env)
**.env.example をリネームして必ず設定してください。**
```ini
DISCORD_BOT_TOKEN=your_token
ADMIN_USER_ID=your_id
LLM_MODEL=Qwen/Qwen2.5-VL-32B-Instruct-AWQ
```

### 3. 起動
*   **Windows**: `start_launcher.py` をダブルクリック
*   **Mac**: `Double_Click_To_Start.command` を実行

---

<div align="center">

**Developed by YoneRai12**
*The Future is Local.*

</div>
