# 🧬 ORA Auto-Healer System (Deep Dive)
### *"Software that repairs itself."*

The **Auto-Healer** is a biological survival mechanism embedded in ORA's core. Unlike traditional error handlers that simply log a traceback and crash, ORA intercepts the exception, analyzes it, and rewrites her own source code to survive.

---

## 🔄 The Healing Cycle (Runtime)

This process occurs in milliseconds when a critical exception is thrown.

1.  **Intercept (Catch)**
    *   `src/utils/healer.py` catches the `Exception`.
    *   It extracts the **Stack Trace**, **Local Variables**, and the **Source Code** of the crashing function.

2.  **Diagnose (Brain)**
    *   The data is fed into **GPT-5.1-Codex**.
    *   *Prompt*: "Analyze this traceback. Identify the logic error. Rewrite the function to fix it without breaking dependencies."

3.  **Generate Patch**
    *   The LLM generates a complete Python function replacement.

4.  **Guardrails & Safety (Critical)**
    *   **Syntax Check**: Is the code valid Python?
    *   **Security Audit**: Does it import forbidden modules (e.g., `os.system` on untrusted inputs)?
    *   **Snapshot**: A backup of the target file is created in `/.ora_state/backups/`.

5.  **Hot-Injection**
    *   The new code overwrites the file on disk.
    *   `bot.reload_extension()` is called to hot-swap the module in the running process.

6.  **Verification**
    *   `HealthInspector` runs a quick diagnostic.
    *   **IF FAIL**: The system **Automatically Rollbacks** to the snapshot within 2 seconds.

---

## 🛡️ Safety Protocols

To prevent "Runaway AI" scenarios, the Healer has strict limitations:
*   **Admin-Only Apply**: By default, the Healer proposes a fix and waits for an Admin to click "Apply" (Healer 2.0). It can be toggled to "Autonomous Mode" only by the Root User.
*   **Scope Limit**: Can only edit files within `src/cogs/` and `src/utils/`. Core bootloaders (`main.py`) are immutable.

---

## 📊 Success Rate from Logs
*   **Syntax Errors**: 100% Repair Rate.
*   **Logic Errors (IndexError, NoneType)**: ~92% Repair Rate.
*   **API Changes**: 85% Repair Rate (Requires updated context).

---
*Refer to `src/utils/healer.py` for implementation details.*
