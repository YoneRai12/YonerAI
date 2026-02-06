# ORA System Changelog

## 🆕 v5.1.1 (2026/02/06) - CI Fix + Memory/Download Robustness
### ✅ CI Fix (No Secrets Needed)
* GitHub Actions smoke test now sets a dummy `DISCORD_BOT_TOKEN` so tests don’t fail on missing secrets.

### 🧠 Memory Safety
* Ensures `memory/users/` is created at startup.
* Prevents **channel memory** files (`memory/channels/<channel_id>.json`) from being misinterpreted as **user** files during cloud-sync.

### 🎥 Download + 📸 Screenshot Hardening
* `web_download` no longer crashes on older deployments where `download_video_smart()` doesn’t accept `split_strategy`.
* `web_screenshot` embed title is now short/stable (`ORA Screenshot`) to avoid Discord’s 256-char title hard limit.

## 🆕 v5.1.0 (2026/02/06) - Diagram Clarity + Release Alignment
### 📈 Readable Architecture Diagrams
Reworked README diagrams for practical readability:
* Switched core flow to **sequence diagrams** (request -> routing -> dispatch -> tool loop -> final response).
* Replaced dense runtime graph with a simpler layer model:
  * Platform -> Client Process -> Core Process -> Tool Executors.

### ✅ CI Confidence Pass
Validated the same checks used by GitHub workflows:
* `ruff check .`
* `mypy src/ --ignore-missing-imports`
* `python -m compileall src/`
* `pytest tests/test_smoke.py`
* Core checks (`core_test.yml` equivalent) also verified locally.

### 🏷️ Version Bump
* Updated `VERSION` to `5.1.0`.
* README header updated to `v5.1-Singularity`.

## 🆕 v5.0.0 (2026/02/06) - Core Loop Alignment & Reproducible Release
### 🧭 Architecture/Flow Documentation Sync
Updated `README.md` and `README_JP.md` to match the current implementation:
* **Hub/Spoke Runtime Flow**: `ChatHandler` -> `ToolSelector/RAG` -> `ORA Core` -> dispatch -> local tool execution -> `/v1/runs/{id}/results`.
* Added Mermaid diagrams for both **End-to-End Request Path** and **Runtime Architecture**.

### ✅ CI & Reproducibility Hardening
* Added explicit local verification steps matching CI (`ruff`, `mypy`, `compileall`, `pytest smoke`).
* Added version verification script: `scripts/verify_version.py`.
* Updated release workflow to enforce:
  * tag `vX.Y.Z` and `VERSION` file consistency
  * deterministic release archive generation based on verified version.

### 🔐 Secret Safety
* Re-validated token/API-key handling pattern:
  * credentials loaded from `.env`/environment variables
  * no new hardcoded secrets introduced by this update.

## 🆕 v4.2 Update (2026/01/10) - Security Hardening & NERV UI
### 🛡️ Ultimate Security Architecture
Completed the transition to a fully environment-variable driven configuration.
*   **Zero Hardcoded Secrets**: All Admin IDs, Channel IDs, and Tokens are now strictly loaded from `.env`.
*   **Safe-Guard**: Codebase is now completely safe for public GitHub hosting/forking.

### 🚨 NERV-Style Admin Override (Visual Upgrade)
*   **Red Alert Mode**: When Admin Override is active, the Dashboard background shifts to a dynamic "Hex-Grid Red Alert" state.
*   **System Telemetry**: Added "Core System Connection" and "Root Injection" sequences to the override animation.

### 🐛 Healer & System Optimization
*   **Refactored Logic**: `healer.py` and `system.py` permission checks are now dynamic, allowing for seamless transfers between Main and Sub-PCs.

---

## 🆕 v4.1 (2026/01/05) - Agentic Stability & Self-Evolution
### 🤖 High-End Model Restoration (Codex stabilization)
Stabilized agentic capabilities for the Shared Traffic series.
*   **gpt-5.1-codex Support**: Correctly routes to the `/responses` endpoint and handles "Tool Call" parsing (flattening & mapping).
*   **Auto-Parameter Filtering**: Automatically removes incompatible parameters like temperature for O1 and Codex models.

### 🧠 Enhanced Context Awareness
*   **Channel History Fallback**: ORA now automatically fetches the last 15 messages from the channel if no direct reply is found. No more "forgetting" the previous context!

### 🛠️ Self-Evolution & Reliability
*   **Healer 2.0**: Interactive UI to apply or dismiss AI-suggested code fixes safely.
*   **Log Forwarder**: Real-time log streaming to a dedicated Discord channel for remote monitoring.
*   **Pre-flight Health Checks**: Integrated `health_inspector` to verify system integrity before applying changes.

---

## 🆕 v4.0 (2025/12/30) - The Mac Expansion
### 🍎 ORA Mac Migration Support
**FULL Support for Apple Silicon (M1/M2/M3/M4).**
*   **Unified Logic**: Run ORA's Brain on your Windows/Mac.
*   **Remote Dev Ready**: Includes `MIGRATION_GUIDE.md` for seamless VS Code Remote SSH setups.
*   **One-Click Setup**: Dedicated `Double_Click_To_Start.command` for Mac users.

### 📐 Automatic Math Rendering
Native LaTeX/TeX support for beautiful mathematical expressions.
*   **Auto-Detect**: ORA automatically recognizes math in responses.
*   **Visual Rendering**: Converts complex equations (integral, matrix, etc.) into transparent PNGs instantly.

---

## 🆕 v3.9 (2025/12/26) - Dashboard Refresh
Implemented a new dashboard UI for at-a-glance system status.
*   **Active Processing**: Real-time Cyan highlighting for the user currently being processed (Top-Left).
*   **Token Tracking**: Accurate token usage tracking for all models including GPT-5.1.
*   **Privacy Safe Mode**: Hides personal information for screenshots.
