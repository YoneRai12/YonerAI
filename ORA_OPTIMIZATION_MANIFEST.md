# ORA User Optimization Manifest (v2.0)

This document defines the **immutable logic** for ORA's "User Optimization" (Memory Analysis) features.
Any future updates MUST adhere to this specification to prevent regression (Regression of Features or Regression of Spam).

---

## 1. The 3-Way Optimization Strategy

ORA employs a hybrid strategy to ensure users are analyzed deeply without spamming the Discord API.

### A. Real-Time Optimization (Immediate)
*   **Trigger**: User sends **5 new messages** during a session.
*   **Action**: 
    1. The 5 buffered messages are immediately dispatched to the `_analyze_wrapper` task.
    2. Buffer is cleared.
*   **Scope**: Immediate short-term memory analysis.
*   **API Usage**: **Zero**. Uses internal memory buffer entirely.
*   **Purpose**: "Instant Feedback" - The bot becomes smarter about the current conversation context instantly.

### B. Background Optimization (AutoScan)
*   **Trigger**: Periodic Loop (Default: 60 minutes).
*   **Method**: `MemoryCog.scan_history_task`.
*   **Logic**:
    1. Identifies "New" or "Pending" users who are currently Online.
    2. Checks **Local Logs** (`LocalLogReader`) for recent activity.
    3. **CRITICAL RULE**: Does **NOT** scan Discord API (`channel.history`).
*   **API Usage**: **Zero**. Strictly local.
*   **Purpose**: "Silent Catch-up" - Optimizes users who were active but missed the real-time trigger, using only what the bot has already seen/logged locally.
*   **Safety**: Impossible to cause Rate Limits (429) because it never requests history from Discord.

### C. Manual Optimization (Deep Scan)
*   **Trigger**: Slash Command `/optimize_user [target]`.
*   **Method**: `MemoryCog.analyze_user` -> `_find_user_history_targeted(allow_api=True)`.
*   **Logic**:
    1. First checks Local Logs.
    2. If insufficient, **Falls back to Discord API**.
    3. Scans Text Channels, Threads, and Voice Channels.
*   **Safety Measures**:
    *   **Pacing**: Sleeps **2.0 seconds** between API batches (50 msgs).
    *   **Backoff**: If `429 (Rate Limit)` is hit, sleeps **60 seconds** and aborts the specific channel scan.
*   **Purpose**: "Deep Recovery" - Forcing the bot to learn about a user it has no prior record of (e.g., old members).

---

## 2. Architecture & Queueing

### IPC Delegation (Worker Bot)
*   **Producer**: Main Bot identifies candidates for optimization.
*   **Queue File**: `L:\ORA_State\optimize_queue.json`
*   **Consumer**: Worker Bot (`worker_mode=True`) reads this file every 15-30 seconds.
*   **Logic**:
    *   Duplicate Prevention: Main Bot checks if User+Guild ID is already in queue before writing.
    *   Clear-on-Read: Worker Bot reads the file and immediately overwrites it with `[]` (empty) to prevent double-processing.

---

## 3. Log & Spam Prevention Rules

1. **Console Silence**:
   *   `discord.http` and `discord.gateway` loggers are set to `WARNING` level in `src/bot.py`.
   *   `SystemCog` filters out "We are being rate limited" messages from the Discord Debug Channel.

2. **No Ghost Scanning**:
   *   The bot will never proactively scan the API for users who are not interacting or explicitly targeted.

---

## 4. Recovery & Persistence

*   **Failed Analysis**: Users marked as "Error" or "Processing" for >2 hours are auto-reset to "Error" state on reboot to prevent "Stuck Yellow Status" on Dashboard.
*   **Atomic Saves**: All profile updates use `SimpleFileLock` and `.tmp` atomic writes to prevent JSON corruption.
