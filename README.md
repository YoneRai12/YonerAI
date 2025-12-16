# ORA Discord Bot - Ultimate Edition 🌌
### *The Next-Generation AI Orchestrator for RTX 5090*

<div align="center">

![ORA Banner](https://raw.githubusercontent.com/YoneRai12/ORA/main/docs/banner.png)

[![Discord](https://img.shields.io/badge/Discord-Join-7289DA?style=for-the-badge&logo=discord)](https://discord.gg/YoneRai12)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python)](https://www.python.org/)
[![Structure](https://img.shields.io/badge/Architecture-Hybrid%20MoE-FF0055?style=for-the-badge)](https://github.com/vllm-project/vllm)
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

### 🌟 Technical Highlights
- **🧠 Dual-Brain Architecture**: Automatically switches between a fast "Instruct Model" (Qwen3-VL-30B) for chat/vision and a deep "Reasoning Model" (Thinker) for math/logic.
- **👁️ True Vision (Multimodal)**: Can see video and images with human-level understanding (powered by Qwen & SAM 3).
- **🎨 Hollywood-Grade Art**: Generates 4K images using **FLUX.1-dev** (State of the Art) ensuring photo-realism.
- **🗣️ Human-Like Voice**: Listens to you in VC (Faster-Whisper) and speaks back (T5Gemma/VoiceVox).
- **🎮 Zero-Latency Gaming**: Automatically detects games (Apex/Valorant) and shrinks VRAM usage to save FPS.

---

## 💡 Practical Use Cases

| Scenario | How ORA Helps |
| :--- | :--- |
| **🤖 Gaming Companion** | "Hey ORA, look at my screen. Where is the enemy?" (Vision) |
| **🎨 Creative Studio** | "Generate a Youtube thumbnail for Minecraft, anime style." (Image Gen) |
| **📚 Homework Helper** | "Solve this calculus problem step-by-step." (Reasoning Model) |
| **🎙️ Vtuber / Stream** | Can act as a fully voiced co-host that reads chat and responds. |
| **🔍 Research** | "Search the web for RTX 5090 benchmarks and summarize." (Tools) |


## 🏗️ System Architecture (Logic Flow)

This system uses an **Automatic Semantic Router** to dynamically assign tasks to the most appropriate AI model.

```mermaid
graph TD
    User["User Input (Discord)"] --> Router{"Auto Router<br>(Context Analysis)"}

    %% Routing Logic
    Router -- "Chat / Logic" --> LLM["Qwen3-VL-30B-Instruct<br>(vLLM - Port 8001)"]
    Router -- "Image Upload" --> Vision["Qwen3-VL (Vision)<br>(Native Analysis)"]
    Router -- "Generate Image" --> ImageGen["Flux.1-dev<br>(ComfyUI - Port 8188)"]
    Router -- "Video/Object Search" --> SAM2["SAM 2 (Meta)<br>(Object Segmentation)"]
    
    %% Voice Path
    Router -- "Speak/TTS" --> VoiceRouter{"Voice Selector"}
    VoiceRouter -- "Standard" --> VV["VOICEVOX<br>(Port 50021)"]
    VoiceRouter -- "Human-like" --> T5["T5Gemma-TTS<br>(Resources Loaded)"]

    %% Future/Reserved
    Router -- "Video Gen?" --> VideoGen[Reserved / Future<br>(Port 8189)]

    %% Styling
    style Router fill:#f9f,stroke:#333,stroke-width:2px
    style LLM fill:#ccf,stroke:#333
    style ImageGen fill:#cfc,stroke:#333
```

### 🧩 Component Breakdown

| Feature | Model / Engine | Provider | Status |
| :--- | :--- | :--- | :--- |
| **LLM (Chat)** | `Qwen3-VL-30B-Instruct` | vLLM (Local) | 🟢 Active |
| **Vision (Eyes)** | `Qwen3-VL` (Native) | vLLM (Local) | 🟢 Active |
| **Image Gen** | `Flux.1-dev` (FP8) | ComfyUI | 🟢 Active |
| **Video Rec** | `SAM 2` (Segment Anything) | Meta (Facebook) | 🟡 Loaded |
| **TTS (Std)** | `VOICEVOX` | Docker / Local | 🟢 Active |
| **TTS (Real)** | `Aratako_T5Gemma-TTS` | Transformers | 🟡 On Demand |
| **Video Gen** | *(Planned / Reserved)* | *(TBD)* | ⚪ Future |

This architecture ensures high performance by loading heavy models (like Flux or SAM 2) only when needed, while the core LLM handles the orchestration.

---

## 💻 Installation & Usage

### One-Click Launch
1.  **Right-Click** on your Desktop -> **"Start ORA Bot"**.
2.  Wait 3 seconds. The system auto-initializes all 5 layers.

### Manual Modes
If launching via `start_vllm.bat`:
- **[1] Normal**: Full power (30B Model). Best for everything.
- **[2] Thinking**: Forces the Reasoning model.
- **[3] Gaming**: Low-VRAM mode (7B Model) for playing heavy games.

---

## ⚙️ Configuration & Customization

You can tweak ORA's behavior in `src/config.py` or `.env`.

### Environment Variables
| Variable | Description | Default |
| :--- | :--- | :--- |
| `ORA_DEV_GUILD_ID` | Server ID for Slash Commands (Global if empty) | None |
| `SD_API_URL` | URL for ComfyUI/SD Backend | `http://localhost:8188` |
| `LLM_API_URL` | URL for vLLM Backend | `http://localhost:8001/v1` |
| `VOICEVOX_URL` | URL for TTS Engine | `http://localhost:50021` |

### Specialized Models
ORA supports "Lazy Loading" for these heavy models (only loaded when used):
- **SAM 3 (Segment Anything)**: Place official repo in `L:\ai_models\github\sam3`.
- **T5Gemma TTS**: Place resources in `L:\ai_models\huggingface\Aratako_...`.

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

### 🗣️ Voice System
`/join` / `/leave`
-   Bot joins Voice Chat.
-   **Auto-Read**: Reads chat messages via TTS.
-   **Listen Mode**: (`/listen`) Talk to ORA directly. She hears you!

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
