# ORA Discord Bot - Ultimate Edition 🌌
### *The Next-Generation AI Orchestrator for RTX 5090*

<div align="center">

![ORA Banner](https://raw.githubusercontent.com/YoneRai12/ORA/main/docs/banner.png)

[![Discord](https://img.shields.io/badge/Discord-Join-7289DA?style=for-the-badge&logo=discord)](https://discord.gg/YoneRai12)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python)](https://www.python.org/)
[![Structure](https://img.shields.io/badge/Architecture-Hybrid%20MoE-FF0055?style=for-the-badge)](https://github.com/vllm-project/vllm)
[![GPU](https://img.shields.io/badge/GPU-RTX%205090%20Optimized-76B900?style=for-the-badge&logo=nvidia)](https://www.nvidia.com/)

</div>

---

## 🚀 Overview: Why ORA is Amazing

ORA is not just a chatbot. It is a **fully autonomous AI Operating System** running locally on your high-end hardware.
It integrates the world's most advanced open-source models into a seamless, unified experience inside Discord.

Unlike standard bots that just "reply", ORA **sees, hears, draws, thinks, and acts**.

### ✨ Highlights
- **🧠 Dual-Brain Architecture**: Automatically switches between a fast "Instruct Model" for chat and a deep "Reasoning Model" (Thinker) for math/logic.
- **👁️ True Vision (Multimodal)**: Can see video and images with human-level understanding (powered by Qwen & SAM 3).
- **🎨 Hollywood-Grade Art**: Generates 4K images using **FLUX.2** ensuring photo-realism and style adherence.
- **🗣️ Human-Like Voice**: Listens to you in VC (Faster-Whisper) and speaks back (T5Gemma/VoiceVox).
- **⚡ Zero-Latency Gaming**: Automatically detects when you play games (Valorant/Apex) and hot-swaps to a lightweight model to save FPS.

---

## 🧠 The "Dual Core" Intelligence System

ORA doesn't just use one model. It uses a sophisticated **Router** to decide *how* to answer you.

| Mode | Model Engine | Description |
| :--- | :--- | :--- |
| **Instruct Core** | `Qwen3-VL-30B-Instruct` | The daily driver. Handles chat, tools, vision, and general queries. Fast and witty. |
| **Thinking Core** | `Qwen3-VL-30B-Thinking` | The genius. Activated automatically for Math, Code, logic puzzles, or complex reasoning. It "thinks" before speaking. |

> **How it works:** If you ask "Hello", the Instruct Core replies. If you ask "Solve this integral", the Router detects complexity and wakes up the Thinking Core seamlessly.

---

## 🎨 Creative Studio (ComfyUI Integration)

ORA comes with a built-in **ComfyUI** backend, completely hidden behind a simple command.

- **Engine**: FLUX.2 (FP8 Quantized)
- **Features**:
    - **Smart Style**: "Draw a futuristic city" -> ORA automatically applies "Cyberpunk" styling.
    - **Safety Guard**: LLM-based filtering ensures no unsafe content is generated.
    - **High-Res Fix**: Native 4K upscaling support.

---

## 👁️ perception System (Vision & Audio)

ORA's senses are powered by specialized State-of-the-Art models:

### Visual (Eyes)
- **Qwen3-VL**: Understands memes, reads text in images, and analyzes scenes.
- **SAM 3 (Segment Anything Model)**: Can identify and cut out specific objects from video/images with pixel-perfect precision.

### Audio (Ears & Voice)
- **Hearing**: Uses `faster-whisper` (Large-v3) running on GPU for real-time transcription of Voice Chat.
- **Speaking**: Uses `T5Gemma-TTS` (Experimental) and `VoiceVox` for high-quality Japanese speech.

---

## 🛠️ Architecture: The 5-Layer Stack

ORA is built like a modern OS, optimized for the **NVIDIA RTX 5090 (32GB)**.

1.  **Launcher Layer** (`start_vllm.bat`):
    -   Orchestrates the entire boot process. Checks environment, sets modes, and handles crash recovery.
2.  **Resource Layer** (`ResourceManager`):
    -   The "Guard Dog". It monitors VRAM and kills/starts processes.
    -   Ensures you never run out of memory by enforcing **Exclusive Context** (Chat OR Image OR Game).
3.  **Inference Layer**:
    -   **vLLM Server**: High-throughput LLM serving.
    -   **ComfyUI Server**: Visual generation pipeline.
4.  **Application Layer**:
    -   **Discord Bot**: The main brain managing events and user interaction.
    -   **FastAPI**: Provides a Web Interface for integration.
5.  **Interface Layer**:
    -   **Discord**: Where you talk.
    -   **ORA UI**: A web dashboard for monitoring status.

---

## 💻 Installation & Usage

### 1. One-Click Start
No command line needed. Just run the **Launch Shortcut**:
```
[ Right-Click Desktop ] -> [ Start ORA Bot ]
```
Wait 3 seconds. The system will auto-initialize:
1.  **vLLM** starts (Blue Screen).
2.  **ComfyUI** starts (Background).
3.  **Bot** connects to Discord.

### 2. Modes
When launching manually, you can choose:
- **[1] Normal**: Full power (30B Model). Best for everything.
- **[2] Thinking**: Forces the Reasoning model.
- **[3] Gaming**: Low-VRAM mode (7B Model) for playing heavy games.

---

## 📜 Full Command List

| Command | Usage | Effect |
| :--- | :--- | :--- |
| **/join** | `/join` | ORA joins your VC and starts listening. |
| **/imagine** | `/imagine prompt: cat` | Generates a high-quality image. |
| **/analyze** | `/analyze [image]` | deeply analyzes the attached image. |
| **/search** | `/search query: weather` | Googles the internet for live info. |
| **/shiritori** | `/shiritori` | Challenges you to a word game. |
| **/system** | `/system status` | Shows VRAM / GPU usage and temperatures. |
| **/timer** | `/timer 3m` | Sets a timer. |

---

<div align="center">

**Developed by YoneRai12**
*Powered by the Bleeding Edge of AI*

</div>
