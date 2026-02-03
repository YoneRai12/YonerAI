# ORA: AI Handover & Mac Migration Guide

> [!IMPORTANT]
> **New AI Developer**: Please read this file entirely before starting work. This project is a sophisticated Agentic AI system.

## 1. Project Identity
You are the lead developer for **ORA**, an autonomous agent Discord bot.
- **Core Philosophy**: "Agentic Mindset" — execute tools immediately instead of explaining.
- **Current Stack**: FastAPI (API), Discord.py (Bot), Cloud/Local LLM Hybrid.
- **Goal**: Transition from a simple bot to a fully autonomous AI platform.

## 2. Mac Migration Instructions
This project has been moved from Windows to Mac. The following steps are required:
1. **Unzip all modules**: `source_clean`, `memory`, `state`, and `logs`.
2. **Setup Environment**:
   - Create a new virtualenv.
   - Run `pip install -r requirements.txt`.
   - Install `brew install ffmpeg`.
3. **Update .env**:
   - Change `L:\...` paths to Mac absolute paths (e.g., `/Users/username/Documents/...`).
   - The persistent data is in the `memory`, `state`, and `logs` folders you just unzipped.

## 3. System Architecture
- `src/cogs/ora.py`: Main entry for bot operations.
- `src/utils/llm_client.py`: Unified interface for multiple LLM providers.
- `src/cogs/handlers/tool_selector.py`: RAG-based intent router with heuristic fallbacks.
- `src/web/endpoints.py`: FastAPI implementation for external API access and SSE streaming.

## 4. Current Task Status
- **Bug Fixed**: Tool classification for "Save" (download) intent is fixed and verified.
- **Next Step**: Enhance proactive features and improve RAG recall for long-term memory.

---
*Created by Antigravity (Assistant AI) for @YoneRai12*
