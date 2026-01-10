# 📘 ORA User Manual & Command Guide
### *Mastering the AI Operating System*

This guide details how to interact with ORA, from your first `@mention` to advanced system control.

---

## 🚀 First Encounter (Onboarding)
When you first invite ORA to your server or DM her:

1.  **The Awakening**: ORA detects a new user and initiates the **"Bonding Protocol"**.
2.  **Privacy Selection**: You will be presented with a UI to choose your privacy level:
    *   **Private Mode (Default)**: 100% Local processing. Secure.
    *   **Smart Mode**: Allows Cloud Processing (GPT-5) for complex coding tasks.
3.  **Voice Calibration**: If you use voice features, ORA will ask to calibrate to your microphone for optimal listening.

---

## 💬 Chat Capabilities (`@ORA`)
You don't need slash commands for everything. Just talk.

*   **Standard Chat**: "Hello ORA, how are you?" -> Instant local reply (Qwen 2.5).
*   **Vision**: Paste an image and ask "What is this?" -> Active Vision Analysis.
*   **Coding**: "Write a Python script to scrape a website." -> Route to GPT-5-Codex automatically.
*   **Reasoning**: "Why is the sky blue? Explain in physics terms." -> Deep Thinking Mode.

---

## 🛠️ Slash Command Reference (Cheatsheet)

### 🎨 Creative Tools
| Command | Usage Example | Result |
| :--- | :--- | :--- |
| `/imagine` | `/imagine a futuristic tokyo` | Generates a 4K Image (Flux.1) |
| `/analyze` | `/analyze (attach image)` | Analyzes the image content |
| `/layer` | `/layer (attach image)` | Splits image into PSD layers |

### 🗣️ Voice & Audio
| Command | Usage Example | Result |
| :--- | :--- | :--- |
| `/join` | `/join` | ORA joins VC and reads chat |
| `/listen` | `/listen` | Switch to Voice Control Mode |
| `/doppelganger` | `/doppelganger (attach audio)` | Clones your voice instantly |

### 🔧 Utilities & System
| Command | Usage Example | Result |
| :--- | :--- | :--- |
| `/search` | `/search RTX 5090 release date` | Real-time Google Search |
| `/code` | `/code python script for...` | Force GPT-5 Coding Mode |
| `/system health` | `/system health` | Show GPU VRAM/Temp |
| `/override` | `/override` | **Admin Only**. Emergency Mode |

---

## 💻 The NERV Dashboard (Web UI)
Access the dashboard at `http://localhost:3000` (or your tailored URL).

### Key Modules:
1.  **Thought Stream**: Watch the AI thinking in real-time (Green = Local, Purple = Cloud).
2.  **Cost Monitor**: Tracks your free Shared Lane usage vs. Personal API usage.
3.  **Memory Inspector**: View what ORA "remembers" about you in her Vector DB.
4.  **Gaming Control**: One-click "Optimize" button to kill background processes.

---

## 🧬 Self-Evolution Request
Want a feature that doesn't exist?
*   **Command**: `/dev_request [feature]`
*   **Example**: `/dev_request Add a command to check Bitcoin price.`
*   **Result**: ORA will write the code, test it, and deploy `/crypto` within seconds.
