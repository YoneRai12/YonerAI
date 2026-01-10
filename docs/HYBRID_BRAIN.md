# 🧠 Hybrid Brain Architecture (Deep Dive)
### *Fusion of Local Speed & Cloud Intelligence*

ORA operates on a **Tiered Logic System** managed by the **Omni-Router** (`src/config.py`). This ensures the lowest possible latency for chatting while providing "God-Mode" intelligence for coding.

---

## 🔄 The Omni-Router Logic

Every user message passes through a semantic classifier (`FunctionGemma` or `Mistral-Nemo`) to determine **intent** and **complexity**.

### 🏗️ Layer 1: Reflex (Local)
*   **Model**: **Qwen 2.5-VL 32B** (via vLLM)
*   **Latency**: < 300ms
*   **Cost**: $0.00
*   **Use Case**: Casual chat, simple questions, image recognition.
*   **Privacy**: **100% Local**. No data leaves your GPU.

### 🏗️ Layer 2: Logic (Cloud)
*   **Model**: **GPT-5.1-Codex / GPT-4o**
*   **Latency**: ~1.5s
*   **Cost**: Shared Pool (Free Tier) or User Key.
*   **Trigger**:
    *   Keywords: "Code", "Script", "Debug", "Fix", "Analyze".
    *   Complexity Score: > 50 (Calculated by token density/structure).

### 🏗️ Layer 3: Vision (Native)
*   **Model**: **Qwen 2.5-VL (Native)**
*   **Mechanism**: Directly reads the RGB buffer of your screen or uploaded images.
*   **Capability**: Can solve math problems, identify anime characters, or debug UI screenshots.

---

## 💰 Cost Management System
ORA includes a sophisticated `CostManager` to track usage across models.

*   **Shared Lane (Free)**: Access to a community pool of OpenAI tokens (2.5M/day).
*   **Personal Lane (BYOK)**: Use your own API Key (`OPENAI_API_KEY`) for unlimited speed.
*   **Gaming Mode**: When `valorant.exe` is detected, the Local Brain (32B) is unloaded, and a smaller 7B model is loaded to save VRAM.

---
*Refer to `src/config.py` and `src/utils/cost_manager.py` for implementation details.*
