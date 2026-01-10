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

## 🛠️ Slash Command Reference

### 🎨 Creative Tools
| Command | Description |
| :--- | :--- |
| `/imagine [prompt] [style]` | Generate 4K Art via Flux.1 (e.g., `/imagine a cyberpunk city anime_style`). |
| `/analyze [image]` | Deep analyze an image or video file. |
| `/layer [image]` | Decompose an image into PSD layers (Photoshop Core). |

### 🗣️ Voice & Audio
| Command | Description |
| :--- | :--- |
| `/join` | ORA joins your voice channel and reads chat (TTS). |
| `/listen` | ORA starts listening to your voice input (Voice Control). |
| `/doppelganger [audio]` | Clones YOUR voice from a sample file. ORA will speak as YOU. |

### 🔧 Utilities & System
| Command | Description |
| :--- | :--- |
| `/search [query]` | Real-time web search (Google/DuckDuckGo). |
| `/code [request]` | Forces the Coding Brain (GPT-5) for a specific request. |
| `/system health` | Show VRAM usage, temp, and load. |
| `/override` | **Admin Only**. Triggers NERV Red Alert mode for system recovery. |

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
