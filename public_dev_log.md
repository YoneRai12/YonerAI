# 🛠️ ORA System Architecture & Changelog (Full)

> **Repository Status**: `Active` | **Core**: `Python 3.11+` | **Acceleration**: `CUDA 12.8 / RTX 5090`
> This document details the engineering journey of the ORA Ecosystem.

## 🧠 Core Intelligence & Logic
- [x] **Dual-Model Reasoning Pipeline**
    - [x] Implemented "Instruct -> Router -> Thinking" architecture.
    - [x] Engineered `route_eval` JSON schema for dynamic task delegation.
    - [x] **ResourceManager**: Created process supervisor for hot-swapping vLLM instances (7B Gaming vs 32B Reasoning).
    - [x] **Context Handover**: Preserved conversation context during model switching.
- [x] **Tool System Architecture (RAG)**
    - [x] **Dynamic Loading**: Implemented tag-based tool injection to reduce context window usage.
    - [x] **Categorization**: Grouped tools (Discord, Image, Video, Admin) for semantic router.
    - [x] **Safety Heuristics**: Added "Search Heuristic" to override LLM refusals for informational queries.
- [x] **Auto-Healing Engine ("The Immortal")**
    - [x] **Runtime Patching**: Hooked global `on_command_error` to catch unhandled exceptions.
    - [x] **Trace Analysis**: Automated stack trace analysis via LLM to generate `git apply` compatible patches.
    - [x] **Self-Routing**: Error reports routed to dedicated debug channels with diffs.

## 🎨 Creative Generation (ComfyUI / Flux.2)
- [x] **FLUX.2 Integration (RTX 5090)**
    - [x] **Architecture**: Migrated to `flux2_dev_fp8mixed` for 24GB VRAM optimization.
    - [x] **Tiled Decoding**: Implemented `VAEDecodeTiled` (512px / temporal:8) to solve VAE OOM crashes.
    - [x] **Custom Workflows**: Ported ComfyUI workflows (DualCLIPLoader, Weight Streaming).
    - [x] **Aspect Ratio Smart-Select**: Added 21:9 (Cinema), 16:9 (PC), 9:16 (Mobile) logic.
- [x] **Safety & Style**
    - [x] **Style Router**: LLM detects intent ("Make it sci-fi") and injects style prompts (e.g., "monochrome, cyberpunk").
    - [x] **Safety Gate**: Hardened negative prompts `(nsfw:2.0)` and keywords.
    - [x] **VRAM Guard**: Automated "LLM Unload -> Gen -> LLM Reload" cycle to prevent VRAM collision.

## 🔊 Voice & Sensory (Audio/Vision)
- [x] **Neural Voice Core**
    - [x] **Hybrid TTS**: Fallback chain `VOICEVOX (Local) -> EdgeTTS (Cloud) -> gTTS`.
    - [x] **Latency Optimization**: Tuned buffers for real-time response.
    - [x] **Cross-Channel**: Implemented "Sticky Voice" to read chat from any channel to VC.
- [x] **Music & Audio**
    - [x] **Yt-dlp Stream**: Implemented opus stream piping via `ffmpeg`.
    - [x] **Heuristic Playback**: Regex trigger for immediate URL playback (bypassing LLM thinking).
- [x] **Multimodal Vision**
    - [x] **True Vision**: Base64 image encoding passed directly to Qwen2.5-VL / Mistral.
    - [x] **OCR Pipeline**: Fallback integration for text extraction.
    - [x] **Hallucination Fix**: Enforced system prompt constraints to separate "Seeing" from "Imagining".

## 🛡️ Infrastructure & Hardening (Phase 13)
- [x] **Data Integrity**
    - [x] **Atomic Writes**: Implemented `tempfile + replace` strategy for `storage.py` (Zero corruption on crash).
    - [x] **Thread Safety**: Added `asyncio.Lock` wrappers for shared JSON states.
- [x] **Network Robustness**
    - [x] **Exponential Backoff**: Implemented retry logic for API handshakes.
    - [x] **Global Timeouts**: Hardened HTTP requests against hang-ups.
- [x] **DevOps**
    - [x] **Hot Reload**: Implemented extension reloader (`/reload`) for zero-downtime updates.
    - [x] **Logs**: Structured JSON logging with rotation (5MB cap).
    - [x] **WSL2**: Configured Ubuntu 22.04 env for vLLM native linux performance.

## 🎮 Game Interaction
- [x] **Minecraft Control**
    - [x] **Command Translation**: Ported Command Block logic to Python script.
    - [x] **Server Ops**: Remote Start/Stop/Status via Discord.
- [x] **Minigames**
    - [x] **Shiritori Engine**: Built custom word-chain logic with Japanese morphological analysis ("N" ending check).

## ⚙️ Privacy & Security Features
- [x] **Stealth Capabilities**
    - [x] **Anonymous /say**: Implemented ephemeral command masking for admin announcements.
    - [x] **Trace Cleaning**: Auto-deletion of command triggers.
- [x] **User Safety**
    - [x] **Input Sanitization**: Blocked shell injection vectors in system tools.
    - [x] **Permission Tiering**: Granular permission checks (Admin/Sub-Admin/User).

---
*Generated: 2025-12-19 | Total Commits: 500+ | System Version: 16.0*
