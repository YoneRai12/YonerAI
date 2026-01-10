# 💻 NERV-Style Neural Dashboard (Deep Dive)
### *Visualizing the Ghost in the Machine*

The Dashboard is not just a UI; it is a **Real-Time Telemetry Surface** connected directly to ORA's brain via WebSockets. It is built with **Next.js**, **TailwindCSS**, and **Framer Motion**.

---

## 🚨 The "Red Alert" Protocol
When the **Admin Override** (`/override`) command is issued in Discord, the dashboard reacts globally.

1.  **State Sync**: The backend broadcasts `{"status": "OVERRIDE", "level": "CRITICAL"}`.
2.  **Visual Shift**:
    *   The calm blue/cyan theme instantly shifts to **Aggressive Red**.
    *   A **Hexagon Grid Overlay** slides across the background (Evangelion Style).
    *   **"WARNING: ROOT ACCESS GRANTED"** flashes in the header.
3.  **Core Audio**: Sound effects (Sirens) play on the host machine via Windows Core Audio API.

---

## 📡 Live Telemetry Features

### 1. Thought Stream
You can see the raw "Thought Chain" of the AI as it processes a request.
*   *Blue Text*: User Input.
*   *Green Text*: Local Brain thinking.
*   *Purple Text*: Cloud Brain (GPT-5) coding.
*   *Yellow Text*: Tool Execution (Search, Image Gen).

### 2. System Vitals
*   **GPU VRAM**: Real-time graph of RTX 5090 memory usage.
*   **Token Rate**: Speed of generation (Tokens/sec).
*   **Cost**: Estimated API cost for the current session.

---

## 🛠️ Tech Stack
*   **Frontend**: React 19, Next.js 15 (App Router).
*   **Styling**: TailwindCSS, CSS Modules (for Scanlines/CRT effects).
*   **Comms**: Socket.IO-Client.
*   **Host**: Node.js sidecar process managed by `PM2`.

---
*Refer to `ora-ui/app/dashboard/page.tsx` for source code.*
