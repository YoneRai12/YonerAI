# 🛰️ Satellite Architecture (Deep Dive)
### *24/7 Uptime. Zero Noise.*

Running an RTX 5090 24/7 is expensive and hot. The **Satellite System** solves this by offloading the "Listening" phase to a low-power device.

---

## 🏗️ The Topology

### 🌎 Main Node (The Beast)
*   **Specs**: Windows 11, RTX 5090, i9-14900K.
*   **Role**: Heavy Compute (LLM Inference, Image Gen, Training).
*   **State**: **Sleeping (S3)** by default.

### 🛰️ Satellite Node (The Scout)
*   **Specs**: MacBook Air (M1/M2) or N100 Mini PC.
*   **Role**: Discord Gateway connection, Text Chat, Music Playback.
*   **Power**: < 10W.

---

## ⚡ The Wake Protocol

1.  **Trigger**: User sends a request requiring Heavy Compute (e.g., `/imagine`, `/code`).
2.  **Detection**: Satellite analyzes intent via specific keywords.
3.  **Signal**: Satellite sends a **Magic Packet (WoL)** to the Main Node's MAC Address.
4.  **Handover**:
    *   Main Node wakes up (Boot time: ~15s).
    *   Satellite forwards the request context to Main Node via local API (`/v1/internal/handover`).
    *   Main Node processes the request and replies directly to Discord.
5.  **Sleep**: After 30 minutes of idle time, Main Node auto-suspends.

---

## 🎮 Remote Control Features
Commands available from the Satellite to control the Main Node:
*   `/system wake`: Force Wake-on-LAN.
*   `/system sleep`: Force Sleep (S3).
*   `/system reboot`: Emergency Reboot (if Main Node freezes).
*   `/screen stream`: Stream Main Node's desktop to Discord (via `mss`).

---
*Refer to `src/utils/desktop_watcher.py` (Main) and `satellite/` (Sub) for implementation.*
