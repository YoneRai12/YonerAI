# ORA Project Contributing Guidelines

## 1. Task Management
*   **TASKS.md**: Contains only active and pending tasks.
*   **TASK_HISTORY.md**: Contains a complete history of all tasks (completed, abandoned, etc.).
    *   **Rule**: NEVER delete lines from `TASK_HISTORY.md`. Only append new history entries.
    *   **Paths**: Always use repository-relative paths (e.g., `src/cogs/ora.py`) in documentation.

## 2. Python Coding Style
*   **Type Hints**: Use built-in collection types for type hinting (Python 3.9+).
    *   Use `list[str]` instead of `typing.List[str]`.
    *   Use `dict[str, Any]` instead of `typing.Dict[str, Any]`.
*   **Imports**: Ensure all new modules can be imported successfully. Run `python scripts/test_imports.py` before committing.

## 3. Tool Development (Phase 6+)
*   All tools must be registered in `core/src/ora_core/mcp/registry.py`.
*   **VRAM Budget Management**:
    *   Tools requiring GPU must set `gpu_required=True`.
    *   **CRITICAL**: The Core API must run with **`worker=1`** (e.g., `uvicorn ... --workers 1`) to ensure the `asyncio.Semaphore` correctly manages the 25GB VRAM budget across all requests.
*   **Idempotency & Polling**:
    *   Tools must support `tool_call_id` and are scoped by `user_id`.
*   `ToolRunner` implements a polling mechanism (30s) for concurrent requests to the same tool call, preventing duplicate execution while ensuring consistent results.

## 4. Secrets & Local Configuration (MUST)
*   **Never commit `.env`** or any real credentials (Discord tokens, OpenAI keys, Cloudflare tunnel tokens, webhooks, OAuth secrets).
*   Use `.env.example` as the public template, and keep `.env` in `.gitignore` (already enforced).
*   If a secret is ever pasted into chat/issues or committed by mistake:
    1. rotate/revoke it immediately (treat it as compromised)
    2. remove it from git history if it reached the repository
*   Avoid printing secrets in logs. If you add new logs, redact values that look like tokens/keys.
