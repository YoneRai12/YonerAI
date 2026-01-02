# ORA Discord Bot - Ultimate Edition 🌌
### *The Next-Generation AI Orchestrator for RTX 5090*

<div align="center">

![ORA Banner](https://raw.githubusercontent.com/YoneRai12/ORA/main/docs/banner.png)

[![Discord](https://img.shields.io/badge/Discord-Join-7289DA?style=for-the-badge&logo=discord)](https://discord.gg/YoneRai12)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python)](https://www.python.org/)
[![Structure](https://img.shields.io/badge/Architecture-Dual%20Brain-FF0055?style=for-the-badge)](https://github.com/vllm-project/vllm)
[![GPU](https://img.shields.io/badge/GPU-RTX%205090%20Optimized-76B900?style=for-the-badge&logo=nvidia)](https://www.nvidia.com/)

<div align="center">

[![English](https://img.shields.io/badge/Language-English-blue?style=for-the-badge)](README.md)
[![Japanese](https://img.shields.io/badge/言語-日本語-red?style=for-the-badge)](README_JP.md)

</div>

</div>

---

## 🚀 Overview

ORA is a **fully autonomous AI Operating System** running locally on your hardware. It integrates the world's most advanced open-source models into a seamless, unified experience inside Discord.

### ✨ Why ORA? (Key Benefits)
- **💰 Zero Monthly Fees**: Unlike ChatGPT Plus ($20/mo) or Midjourney ($10/mo), ORA runs **100% locally**. You own the AI.
- **🔒 Complete Privacy**: No data leaves your PC. Your chats, images, and voice are processed on your RTX 5090.
- **⚡ High Performance**: Optimized for RTX 5090 (32GB VRAM), ensuring maximum speed and quality.

### � Universal Brain (v3.0)

**A Hybrid System merging "Cloud Intelligence" with "Local Privacy".**

### 🧠 Two Operation Modes
- **Smart Mode (Recommended)**:
  - Active only upon **User Consent**.
  - Leverages **GPT-5 Series** (OpenAI) and **Gemini 2.0** (Google) for complex code generation and advanced vision.
  - **Shared Traffic (Free)**: 250k ~ 2.5M tokens/day available via OpenAI Shared Lane.
- **Private Mode (Default)**:
  - Active if consent is denied or ignored.
  - **100% Local**. No data leaves your machine.
  - Maximizes your **RTX 5090** capability locally.

### �🌟 Technical Highlights
- **🧠 Dual-Architecture (Brain + Voice)**: 
    - **Main Brain**: `Ministral-3-14B` via **vLLM** (Logic, Tools, Vision).
    - **Voice Engine**: `T5Gemma-TTS` via **Services** (Voice Cloning, Speech).
- **🗣️ Doppelganger Mode**: Can clone and speak with YOUR voice (Zero-Shot Cloning).
- **👁️ True Vision (Native)**: Can see video and images directly through the Main Brain.
- **🎨 Hollywood-Grade Art**: Generates 4K images using **FLUX.2** (State of the Art).
- **🎮 Zero-Latency Gaming**: Automatically detects games (Apex/Valorant) and shrinks VRAM usage to save FPS.

---

## 🆕 Update v3.9 (2025/12/26)

### 📊 Dashboard Refresh (ORA System Refresh)
Implemented a new dashboard UI for at-a-glance system status.
- **Active Processing**: Real-time **Cyan** highlighting for the user currently being processed (Top-Left).
- **Token Tracking**: Accurate token usage tracking for all models including `GPT-5.1`.
- **Privacy Safe Mode**: Hides personal information for screenshots.

![Dashboard v3.9](docs/dashboard_v3.9.png)

### 🧠 GPT-5.1 Codex Mini Support
Added routing support for OpenAI's latest model, `gpt-5.1-codex-mini`.
- Automatically uses the new `v1/responses` endpoint instead of the traditional `v1/chat/completions`.
- Dramatically improves accuracy for complex reasoning tasks and coding.

---

## 💡 Practical Use Cases

| Scenario | How ORA Helps |
| :--- | :--- |
| **🤖 Gaming Companion** | "Hey ORA, look at my screen. Where is the enemy?" (Vision) |
| **🎨 Creative Studio** | "Generate a Youtube thumbnail for Minecraft, anime style." (Image Gen) |
| **👯 Doppelganger** | "Clone my voice from this audio file." (Voice Cloning) |
| **📚 Homework Helper** | "Solve this calculus problem step-by-step." (Reasoning Model) |
| **🎙️ Vtuber / Stream** | Can act as a fully voiced co-host that reads chat and responds. |
| **🔍 Research** | "Search the web for RTX 5090 benchmarks and summarize." (Tools) |

---

## 🏗️ System Architecture (Logic Flow)

This system uses an **Automatic Semantic Router** to dynamically assign tasks to the most appropriate AI model.

```mermaid
%%{init: { 'theme': 'dark' }}%%
graph TD
    User["User Input (Discord)"] --> Consent{"User Consent<br>(Smart Mode?)"}
    
    %% Privacy Decision
    Consent -- "Yes" --> SmartRouter{"Smart Router<br>(Difficulty/Cost)"}
    Consent -- "No" --> LocalRouter{"Local Router<br>(Fully Local)"}

    %% Smart Path
    SmartRouter -- "High Intel / Vision" --> CloudAPI["☁️ Cloud APIs<br>(GPT-5 / Gemini 2.0)"]
    SmartRouter -- "Standard / Low Cost" --> LocalRouter

    %% Local Path
    LocalRouter -- "Chat / Logic / Vision" --> LLM["Mistral 14B / Qwen<br>(vLLM - Port 8001)"]
    LocalRouter -- "Generate Image" --> ImageGen["Flux.1-dev<br>(ComfyUI - Port 8188)"]
    LocalRouter -- "Video/Object Search" --> SAM2["SAM 2 (Meta)<br>(Object Segmentation)"]
    
    %% Voice Path (Dual Engine)
    LocalRouter -- "Speak/TTS" --> VoiceRouter{"Voice Selector"}
    VoiceRouter -- "Standard" --> VV["VOICEVOX<br>(Port 50021)"]
    VoiceRouter -- "Clone/Real" --> VoiceSvc["Voice Engine<br>(T5Gemma Aratako - Port 8002)"]
    
    VoiceSvc -- "Doppelganger" --> Cloning["Voice Registration<br>(User Embeddings)"]

    %% Output
    CloudAPI --> Output["Response (Embed/Text)"]
    LLM --> Output["Response (Embed/Text)"]

    %% Styling for better dark mode readability
    style Consent fill:#ffbd00,stroke:#333,stroke-width:2px,color:#000
    style SmartRouter fill:#ff1493,stroke:#ffffff,stroke-width:2px,color:#ffffff
    style CloudAPI fill:#00ffff,stroke:#333,stroke-width:2px,color:#000
    style LocalRouter fill:#1e90ff,stroke:#ffffff,stroke-width:1px,color:#ffffff
    style LLM fill:#1e90ff,stroke:#ffffff,stroke-width:1px,color:#ffffff
    style ImageGen fill:#32cd32,stroke:#ffffff,stroke-width:1px,color:#ffffff
    style SAM2 fill:#ff4500,stroke:#ffffff,stroke-width:1px,color:#ffffff
    style VoiceRouter fill:#da70d6,stroke:#ffffff,stroke-width:1px,color:#ffffff
    style VV fill:#ffd700,stroke:#ffffff,stroke-width:1px,color:#000000
    style VoiceSvc fill:#dda0dd,stroke:#ffffff,stroke-width:1px,color:#000000
    style Cloning fill:#dda0dd,stroke:#ffffff,stroke-width:1px,color:#000000
```

### 🧩 Component Breakdown

| Feature | Model / Engine | Provider | Status |
| :--- | :--- | :--- | :--- |
| **LLM (Brain)** | `Ministral-3-14B` | vLLM (Local) | 🟢 Active |
| **Vision (Eyes)** | `Qwen3-VL` (Native) | vLLM (Local) | 🟢 Active |
| **Image Gen** | `Flux.1-dev` (FP8) | ComfyUI | 🟢 Active |
| **Video Rec** | `SAM 2` (Segment Anything) | Meta (Facebook) | 🟡 Loaded |
| **TTS (Std)** | `VOICEVOX` | Docker / Local | 🟢 Active |
| **TTS (Real)** | `Aratako_T5Gemma-TTS` | Transformers | 🟢 Active (Port 8002) |

This architecture ensures high performance by loading heavy models (like Flux or SAM 2) only when needed, while the core LLM handles the orchestration.

---

## 💻 Installation & Usage

### 1. Model Setup (First Time)
Run the downloader to fetch the Voice Engine weights (~10GB):
```powershell
python download_triad_models.py
```

### 2. Launching ORA
1.  **Start Services**: Double-click `start_services.bat`.
    -   Launches **Voice Engine** (T5Gemma) on Port 8002.
2.  **Start Launcher**: Right-Click Desktop -> **"Start ORA Bot"**.
    -   Launches **vLLM** (Brain) and **ComfyUI** (Image).

### Manual Modes
If launching via `start_vllm.bat`:
- **[1] Normal**: Full power (Mistral/Qwen 30B).
- **[2] Thinking**: Forces Reasoning model.
- **[3] Gaming**: Low-VRAM mode (7B Model).

---

## ⚙️ Configuration & Customization

You can tweak ORA's behavior in `src/config.py` or `.env`.

### Environment Variables
| Variable | Description | Default |
| :--- | :--- | :--- |
| `ORA_DEV_GUILD_ID` | Server ID for Slash Commands (Global if empty) | None |
| `SD_API_URL` | URL for ComfyUI/SD Backend | `http://localhost:8188` |
| `LLM_API_URL` | URL for vLLM Backend | `http://localhost:8001/v1` |
| `VOICE_ENGINE_URL` | URL for T5Gemma TTS | `http://localhost:8002` |

---

## 📚 Detailed Command List

### 🎨 Image Generation
`/imagine [prompt] [style] [resolution]`
-   **Prompt**: "A cyberpunk city at night".
-   **Style**: "Anime", "Photo", "Oil Painting" (Auto-detected if omitted).
-   **Resolution**: FHD, 4K, Ultrawide.
> **Note**: ORA uses FLUX.2, which follows prompts *exactly*.

### 👁️ Vision Analysis
`/analyze [image/video]`
-   Upload a file and ask "What is happening here?".
-   Use "Solve this" for math homework.
-   Use "Who is this?" for character recognition.

### 🗣️ Voice & Cloning
`/join` / `/leave`
-   **Auto-Read**: Reads chat messages via TTS.
-   `/doppelganger [audio]`: **Registers your voice.** ORA will start speaking with YOUR voice.
-   `/listen`: Talk to ORA directly. She hears you!

### 🔧 Tools & Utilities
-   `/search`: Google Search.
-   `/timer`: Set alarms.
-   `/system`: VRAM/Temp monitor.
-   `/shiritori`: Play games.

---

## ❓ Troubleshooting

### "System Swapping / Laggy"
-   **Cause**: vLLM default VRAM reservation (90%) leaves no room for Windows.
-   **Fix**: Launcher sets `gpu-memory-utilization` to 0.60 (60%), fixing this. Restart the bot.

### "Bot starts but vLLM stops"
-   **Cause**: Port conflict. Bot tries to start its own vLLM.
-   **Fix**: Fixed in `ResourceManager` (Startup Adoption). Restart the bot.

### "Image Generation Failed"
-   **Cause**: ComfyUI not running.
-   **Fix**: Use the "Start ORA Bot" launcher (it starts Comfy automatically).

---

<div align="center">

**Developed by YoneRai12**
*Powered by the Bleeding Edge of AI*

</div>

---

# 🧠 RTX 5090 AI Training System

This repository now includes a specialized module for fine-tuning ORA's brain (`Mistral-3-14B-Instruct`) natively on Windows using the RTX 5090.

## 🎯 Phase 18: Tool Mastery (LoRA Curriculum)
We are fine-tuning the model to master specific Discord operations without prompting:
1.  **Identity**: Recall "I am ORA, created by YoneRai12."
2.  **Tool Use**: Precisely outputting JSON for `generate_image`, `web_search`, `doppelganger`.
3.  **Moderation**: Precision use of `ban_user`, `kick_user`.

## ⚙️ Technical Specs (Blackwell Optimized)
-   **Model**: `mistralai/Ministral-3-14B-Instruct-2512`
-   **Method**: QLoRA (4-bit NF4 Quantization)
-   **Precision**: BFloat16 (Native Mixed Precision for RTX 5090)
-   **Stack**: Pure PyTorch Nightly (CUDA 12.8) + BitsAndBytes Windows

## 🚀 How to Train
1.  **Generate Data**:
    ```powershell
    python src/training/prepare_tool_data.py
    ```
    *(Generates 1,000 synthetic `User -> Thought -> Tool` samples)*

2.  **Start Training**:
    ```powershell
    cd RTX5090-DebugSystem-main
    start_training.bat
    ```
    ```
    *(Auto-monitors VRAM and Loss convergence)*

---

## 🚀 The Commander's Intel (Phase 21 Upgrade)
*December 2025 Update: The Final Piece*

ORA is currently evolving to encompass the **9 Pillars of Singularity**:

1.  **🧠 Reflex Brain**: **Nemotron 3 Nano** (381 tokens/s) for instant conversational reflexes.
2.  **👁️ God's View**: Real-time Desktop Monitoring via `mss` + Vision API.
3.  **🎨 Photoshop Core**: Image Layer Decomposition (`/layer`) via **Qwen-Image-Layered**.
4.  **💠 3D Alchemy**: Generating Minecraft items from images via **TRELLIS.2**.
5.  **⚡ FunctionGemma**: Dedicated 270M Router for ultra-low latency tool selection.
6.  **🌐 Research Agent**: **BU-30B** Browser Agent for autonomous web navigation.
7.  **🎭 Infinite Personas**: ELYZA-style LoRA switching (Maid, Engineer, Commander).
8.  **💅 Premium UI**: **Google Sans Flex** integration for a state-of-the-art dashboard.
9.  **🏡 Jarvis Control**: Voice-to-IoT control for total room automation.

---

## 🆕 Upgrade v4.0 (2025/12/30) - The Mac Expansion

### 🍎 ORA Mac Migration Support
FULL Support for **Apple Silicon (M1/M2/M3/M4)**.
- **Unified Logic**: Run ORA's Brain on your Windows/Mac.
- **Remote Dev Ready**: Includes `MIGRATION_GUIDE.md` for seamless VS Code Remote SSH setups.
- **One-Click Setup**: Dedicated `Double_Click_To_Start.command` for Mac users.

### 📐 Automatic Math Rendering
Native LaTeX/TeX support for beautiful mathematical expressions.
- **Auto-Detect**: ORA automatically recognizes math in responses.
- **Visual Rendering**: Converts complex equations (integral, matrix, etc.) into transparent PNGs instantly.
- **Universal**: Works on both Local Brain and Cloud Models (OpenAI/Gemini).

### 🐛 Critical Fixes
- **Duplicate Reply Fix**: Solved the "Double Message" bug where ORA would reply twice.
- **Model Stability**: Fixed `gpt-5.1` / `o1` API parameter compatibility.
- **Dependency Fix**: Resolved `matplotlib` and `re` module errors.


### 📜 Verification Logs (Recent)
*   **2025-12-21**: [Fix] Music "Search & Play" Logic (Polished `yt-dlp` query handling).
*   **2025-12-21**: [New] Layer Decomposition Service (Port 8003).
*   **2025-12-21**: [New] UI Font Upgrade (Google Sans Flex).
*   **2025-12-20**: [Opt] **L: Drive Liberation** (Cleared 800GB+ Backup).

---

<div align="center">

**Developed by YoneRai12**
*The Future is Local.*

</div>
