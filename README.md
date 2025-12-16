# ORA Discord Bot (Ultimate Edition)

<div align="center">

![ORA Banner](https://raw.githubusercontent.com/YoneRai12/ORA/main/docs/banner.png)

**"The AI Assistant that feels alive."**

[![Discord](https://img.shields.io/badge/Discord-Join-7289DA?style=for-the-badge&logo=discord)](https://discord.gg/YoneRai12)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python)](https://www.python.org/)
[![vLLM](https://img.shields.io/badge/AI-vLLM-FF6F00?style=for-the-badge)](https://github.com/vllm-project/vllm)
[![ComfyUI](https://img.shields.io/badge/Art-ComfyUI-blue?style=for-the-badge)](https://github.com/comfyanonymous/ComfyUI)

</div>

## 🌌 What is ORA?

ORA is not just a chatbot. It is a **fully integrated AI Orchestrator** designed for high-end local hardware (RTX 5090).
It combines a massive 30B Vision-Language Model with a specialized Reasoning Model, Image Generation Engine, and real-time Voice capabilities into a single Discord interface.

Unlike other bots, ORA **thinking** before speaking when necessary, providing mathematical precision alongside casual conversation.

---

## 🔥 Key Features

### 🧠 Dual-Core Intelligence (Hybrid Reasoning)
ORA uses a **Router System** to dynamically switch between two brains based on your question:
- **Instruct Core (Qwen3-VL-30B)**: For chat, coding, tools, and vision. (Fast)
- **Thinking Core (Reasoning)**: For math, complex logic, and deep problem solving. (Deep)

### 🎨 Hyper-Realistic Image Generation
Built-in **ComfyUI Integration** driving **FLUX.2 (FP8)**.
- **Auto-Style**: Detects "Anime", "Photo", "Art" automatically.
- **Smart Safety**: Strict filtering for safe environments.
- **Upscaling**: 4K resolution support.

### 👁️ True Multimodal Vision
ORA can **see** what you post. Drop an image and ask "What is this?", or "Solve this math problem".
- Powered by **Qwen2.5-VL-32B** (or Qwen3).
- **SAM 3 Integration**: Can segment and identify specific objects in videos/images.

### 🗣️ Natural Voice & Hearing
- **T5Gemma-TTS**: Experimental high-quality speech synthesis.
- **Hearing**: Join VC (`/join`) and ORA listens to you using **Faster-Whisper**. You can talk naturally without typing.

### 🎮 Gaming Mode
Running a heavy game? ORA automatically detects it and hot-swaps to a **Low-Resource 7B Model** to preserve your FPS.

---

## 🚀 Getting Started

### Prerequisites
- **NVIDIA GPU** with 24GB+ VRAM (RTX 3090/4090/5090 recommended).
- **Windows 10/11** with WSL2 (Ubuntu 22.04).
- **Python 3.10+**.

### One-Click Launch
We have simplified everything into a single launcher.

1.  **Right-Click** on your Desktop.
2.  Select **"Start ORA Bot"**.
3.  Wait 3 seconds.
    -   The system will auto-start **vLLM**, **ComfyUI**, **Web API**, and **The Bot**.

### Manual Launch
Run `start_vllm.bat` in the project root.

---

## 🛠️ Commands

| Command | Description |
| :--- | :--- |
| `/join` | Joins your Voice Channel. |
| `/leave` | Leaves Voice Channel. |
| `/listen` | Toggles voice listening mode (Talk to ORA). |
| `/imagine` | Generate an image (or just ask "Draw a cat"). |
| `/analyze` | Analyze an image/video attachment. |
| `/search` | Search Google for real-time info. |
| `/shiritori` | Play a word chain game. |
| `/help` | Show full command list. |

---

## 📂 Architecture

ORA operates on a 5-Layer stack:

1.  **Launcher Layer**: `start_vllm.bat` (Window Management & Environment).
2.  **Resource Layer**: `ResourceManager` (Manages GPU allocation, killing/adopting processes).
3.  **Inference Layer**: `vLLM` (Text/Vision) & `ComfyUI` (Image).
4.  **Application Layer**: `ORA Bot` (Discord.py) & `FastAPI` (Web Interface).
5.  **Interface Layer**: Discord Client & `ora-ui` (Web Dashboard).

---

## 👤 Credits

**Project Lead**: YoneRai12
**Core Engine**: vLLM Team
**Image Engine**: ComfyAnonymous
**Base Models**: Qwen Team, Facebook Research (SAM 3), Aratako (T5Gemma)

<div align="center">
<i>"Intelligence is not just answering; it's understanding."</i>
</div>
