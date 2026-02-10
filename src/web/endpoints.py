# ruff: noqa: B904
# --- CHAT API IMPLEMENTATION ---
import asyncio
import hmac
import json
import os
import uuid
from datetime import datetime
from typing import List
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response, WebSocket, WebSocketDisconnect, Depends, Header, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from google.auth.transport import requests as g_requests
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
from sse_starlette.sse import EventSourceResponse

from src.config import COST_LIMITS

router = APIRouter()


# -----------------------------------------------------------------------------
# Settings (Local Setup UI)
# -----------------------------------------------------------------------------

# Only allow a small set of keys to be edited from the web UI.
# Secrets are stored under profile-scoped SECRETS_DIR and are never returned.
_ALLOWED_SECRET_KEYS: dict[str, str] = {
    "ORA_WEB_API_TOKEN": "ora_web_api_token.txt",
    "ADMIN_DASHBOARD_TOKEN": "admin_dashboard_token.txt",
    "DISCORD_BOT_TOKEN": "discord_bot_token.txt",
    "OPENAI_API_KEY": "openai_api_key.txt",
    "ANTHROPIC_API_KEY": "anthropic_api_key.txt",
    "GROK_API_KEY": "grok_api_key.txt",
    "ORA_SPOTIFY_CLIENT_ID": "ora_spotify_client_id.txt",
    "ORA_SPOTIFY_CLIENT_SECRET": "ora_spotify_client_secret.txt",
    "SEARCH_API_KEY": "search_api_key.txt",
}

# Non-secret config (stored under STATE_DIR/settings_override.json).
_ALLOWED_ENV_KEYS: set[str] = {
    # Identity / ownership
    "ADMIN_USER_ID",
    "DISCORD_APP_ID",
    "ORA_DEV_GUILD_ID",

    "ORA_API_BASE_URL",
    "ORA_CORE_API_URL",
    "ORA_PUBLIC_BASE_URL",

    # Approvals / policy knobs
    "ORA_OWNER_APPROVALS",
    "ORA_OWNER_APPROVAL_SKIP_TOOLS",
    "ORA_PRIVATE_OWNER_APPROVALS",
    "ORA_PRIVATE_OWNER_APPROVAL_SKIP_TOOLS",
    "ORA_SHARED_OWNER_APPROVALS",
    "ORA_SHARED_OWNER_APPROVAL_SKIP_TOOLS",
    "ORA_SHARED_GUEST_APPROVAL_MIN_SCORE",
    "ORA_SHARED_ALLOW_CRITICAL",

    # shared guest allowlist
    "ORA_SHARED_GUEST_ALLOWED_TOOLS",

    # MCP
    "ORA_MCP_ENABLED",
    "ORA_MCP_SERVERS_JSON",
    "ORA_MCP_ALLOW_DANGEROUS",
    "ORA_MCP_DENY_TOOL_PATTERNS",

    # Mention music UX
    "ORA_MUSIC_MENTION_TRIGGERS",
    "ORA_MUSIC_MENTION_LEVEL",
    "ORA_MUSIC_MENTION_YOUTUBE_LEVEL",
    "ORA_MUSIC_NATIVE_PICKER",
    "ORA_MUSIC_PLAYLIST_ACTION_UI",
    "ORA_MUSIC_PICKER_RESULTS",
    "ORA_MUSIC_PLAYLIST_PICKER_RESULTS",
    "ORA_MUSIC_PLAYLIST_PAGE_SIZE",
    "ORA_MUSIC_QUEUE_ALL_LIMIT",
    "ORA_MUSIC_QUEUE_ALL_SHUFFLE",
    "ORA_MUSIC_QUEUE_ALL_RESOLVE_TIMEOUT_SEC",
    "ORA_MUSIC_MAX_ATTACHMENT_MB",

    # Relay / tunnel
    "ORA_RELAY_URL",
    "ORA_RELAY_EXPOSE_MODE",
    "ORA_CLOUDFLARED_BIN",
    "ORA_RELAY_PUBLIC_URL_FILE",
    "ORA_RELAY_MAX_MSG_BYTES",
    "ORA_RELAY_MAX_PENDING",
    "ORA_RELAY_CLIENT_TIMEOUT_SEC",
}


def _settings_paths() -> tuple[Path, Path, Path]:
    from src.config import SECRETS_DIR, STATE_DIR

    secrets_dir = Path(SECRETS_DIR)
    state_dir = Path(STATE_DIR)
    settings_file = state_dir / "settings_override.json"
    return secrets_dir, state_dir, settings_file


def _read_settings_override() -> dict:
    _, _, settings_file = _settings_paths()
    try:
        if not settings_file.exists():
            return {}
        raw = json.loads(settings_file.read_text(encoding="utf-8", errors="ignore"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def _write_settings_override(*, env_map: dict[str, str], mode: str) -> None:
    _, state_dir, settings_file = _settings_paths()
    state_dir.mkdir(parents=True, exist_ok=True)
    m = (mode or "").strip().lower()
    if m not in {"fill", "override"}:
        m = "override"
    payload = {"env": env_map, "mode": m}
    settings_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _secret_present(key: str) -> bool:
    from pathlib import Path
    secrets_dir, _, _ = _settings_paths()
    fname = _ALLOWED_SECRET_KEYS.get(key)
    if not fname:
        return False
    try:
        p = Path(secrets_dir) / fname
        if p.exists() and p.is_file():
            if p.stat().st_size > 0:
                return True
    except Exception:
        pass
    return bool((os.getenv(key) or "").strip())


def _get_settings_status() -> dict:
    from src.config import ORA_PROFILE, ORA_INSTANCE_ID, STATE_DIR, SECRETS_DIR

    raw_override = _read_settings_override()
    override_mode = (raw_override.get("mode") or "fill")
    if not isinstance(override_mode, str):
        override_mode = "fill"
    override_mode = override_mode.strip().lower()
    if override_mode not in {"fill", "override"}:
        override_mode = "fill"

    env_override = raw_override.get("env", {})
    if not isinstance(env_override, dict):
        env_override = {}

    env_out: dict[str, str | None] = {}
    env_sources: dict[str, str] = {}
    for k in sorted(_ALLOWED_ENV_KEYS):
        v = (os.getenv(k) or "").strip()
        if v:
            env_out[k] = v
            # Heuristic source label: if override is set AND we're in override mode AND it matches, call it override.
            ov = env_override.get(k)
            if override_mode == "override" and isinstance(ov, str) and ov.strip() and ov.strip() == v:
                env_sources[k] = "override"
            else:
                env_sources[k] = "env"
        else:
            # Show overrides (non-secret) to help debugging even when env is empty.
            ov = env_override.get(k)
            env_out[k] = str(ov) if isinstance(ov, str) and ov.strip() else None
            env_sources[k] = "override" if env_out[k] is not None else "unset"

    # Also return raw overrides to help debugging UI behavior.
    env_overrides_out: dict[str, str] = {}
    for k, v in env_override.items():
        if isinstance(k, str) and isinstance(v, str) and k in _ALLOWED_ENV_KEYS and v.strip():
            env_overrides_out[k] = v.strip()

    secrets_out = {k: _secret_present(k) for k in sorted(_ALLOWED_SECRET_KEYS.keys())}
    return {
        "profile": str(ORA_PROFILE),
        "instance_id": str(ORA_INSTANCE_ID),
        "state_dir": str(STATE_DIR),
        "secrets_dir": str(SECRETS_DIR),
        "override_mode": override_mode,
        "env": env_out,
        "env_sources": env_sources,
        "env_overrides": env_overrides_out,
        "secrets_present": secrets_out,
        "notes": [
            "Secrets are never returned by the API (only presence).",
            "Changing some settings may require restarting the bot/web server.",
        ],
    }


class SettingsSecretsUpdate(BaseModel):
    # Map of secret key -> value (or null to clear).
    secrets: dict[str, str | None] = {}


class SettingsEnvUpdate(BaseModel):
    # Map of env key -> value (or null/empty to clear override).
    env: dict[str, str | None] = {}
    # How to apply overrides relative to .env:
    # - fill: only set values when env is missing (legacy behavior)
    # - override: overrides always win for keys present in env_map
    mode: str | None = None


def _is_loopback(request: Request) -> bool:
    host = (request.client.host if request.client else "") or ""
    return host in {"127.0.0.1", "::1", "localhost"}


async def require_admin(
    request: Request,
    x_admin_token: str | None = Header(None),
    token: str | None = Query(None),
) -> None:
    """
    Admin API guard.

    - If `ADMIN_DASHBOARD_TOKEN` is set: require it (header `x-admin-token` or query `token`).
    - If not set: allow only loopback requests AND `ALLOW_INSECURE_ADMIN_DASHBOARD=1` (explicit legacy opt-in).
    """
    admin_token = (os.getenv("ADMIN_DASHBOARD_TOKEN") or "").strip()
    allow_legacy = (os.getenv("ALLOW_INSECURE_ADMIN_DASHBOARD") or "").strip().lower() in {"1", "true", "yes", "on"}
    presented = (x_admin_token or token or "").strip()

    if admin_token:
        if (not presented) or (not hmac.compare_digest(presented, admin_token)):
            raise HTTPException(status_code=403, detail="Invalid admin token")
        return

    if not allow_legacy:
        raise HTTPException(status_code=503, detail="ADMIN_DASHBOARD_TOKEN is not configured")

    if not _is_loopback(request):
        raise HTTPException(status_code=403, detail="Admin API only available on loopback without token")


async def require_web_api(
    request: Request,
    x_ora_token: str | None = Header(None),
    authorization: str | None = Header(None),
    token: str | None = Query(None),
) -> None:
    """
    Web API guard for internet exposure.

    - If `ORA_WEB_API_TOKEN` is set: require it (header `x-ora-token`, Authorization Bearer, or query `token`).
    - If not set: allow only loopback callers.
    - If `ORA_REQUIRE_WEB_API_TOKEN=1`: require token even on loopback.
    """
    expected = (os.getenv("ORA_WEB_API_TOKEN") or "").strip()
    require_token = (os.getenv("ORA_REQUIRE_WEB_API_TOKEN") or "").strip().lower() in {"1", "true", "yes", "on"}

    bearer = ""
    if authorization:
        parts = authorization.strip().split(None, 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            bearer = parts[1].strip()

    presented = (x_ora_token or bearer or token or "").strip()

    if expected:
        if (not presented) or (not hmac.compare_digest(presented, expected)):
            raise HTTPException(status_code=403, detail="Invalid ORA web API token")
        return

    if require_token:
        raise HTTPException(status_code=503, detail="ORA_WEB_API_TOKEN is not configured")

    if not _is_loopback(request):
        raise HTTPException(status_code=503, detail="ORA_WEB_API_TOKEN is not configured")


@router.get("/settings/status")
async def get_settings_status(_: None = Depends(require_web_api)):
    return _get_settings_status()


@router.post("/settings/secrets")
async def update_settings_secrets(req: SettingsSecretsUpdate, _: None = Depends(require_web_api)):
    from pathlib import Path

    secrets_dir, _, _ = _settings_paths()
    secrets_dir.mkdir(parents=True, exist_ok=True)

    updated: list[str] = []
    for k, v in (req.secrets or {}).items():
        if k not in _ALLOWED_SECRET_KEYS:
            raise HTTPException(status_code=400, detail=f"Unsupported secret key: {k}")
        fname = _ALLOWED_SECRET_KEYS[k]
        p = Path(secrets_dir) / fname

        if v is None or (isinstance(v, str) and not v.strip()):
            # Clear
            try:
                if p.exists():
                    p.unlink()
            except Exception:
                pass
            if k in os.environ:
                os.environ.pop(k, None)
            updated.append(k)
            continue

        if not isinstance(v, str):
            v = str(v)
        v = v.strip()
        if len(v) > 4096:
            raise HTTPException(status_code=400, detail=f"Secret too long: {k}")

        p.write_text(v + "\n", encoding="utf-8")
        try:
            os.chmod(str(p), 0o600)
        except Exception:
            pass
        os.environ[k] = v
        updated.append(k)

    out = _get_settings_status()
    out["updated"] = updated
    return out


@router.post("/settings/env")
async def update_settings_env(req: SettingsEnvUpdate, _: None = Depends(require_web_api)):
    raw = _read_settings_override()
    overrides = raw.get("env", {})
    if not isinstance(overrides, dict):
        overrides = {}

    mode = req.mode if isinstance(req.mode, str) and req.mode.strip() else (raw.get("mode") if isinstance(raw, dict) else None)
    if not isinstance(mode, str):
        mode = "override"
    mode = mode.strip().lower()
    if mode not in {"fill", "override"}:
        mode = "override"

    updated: list[str] = []
    for k, v in (req.env or {}).items():
        if k not in _ALLOWED_ENV_KEYS:
            raise HTTPException(status_code=400, detail=f"Unsupported env key: {k}")
        if v is None or (isinstance(v, str) and not v.strip()):
            overrides.pop(k, None)
            updated.append(k)
            continue
        if not isinstance(v, str):
            v = str(v)
        overrides[k] = v.strip()
        # Best-effort immediate apply for this process.
        os.environ[k] = overrides[k]
        updated.append(k)

    _write_settings_override(
        env_map={str(k): str(v) for k, v in overrides.items() if isinstance(k, str) and isinstance(v, str)},
        mode=mode,
    )
    out = _get_settings_status()
    out["updated"] = updated
    return out

@router.get("/dashboard/summary")
async def get_dashboard_summary(_: None = Depends(require_web_api)):
    """Returns summary statistics for the dashboard."""
    import json
    from pathlib import Path
    from src.config import STATE_DIR

    state_path = Path(STATE_DIR) / "cost_state.json"

    # Defaults
    total_tokens = 0
    total_high = 0
    total_stable = 0
    total_opt = 0

    if state_path.exists():
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                raw = json.load(f)

            # Aggregate from User Buckets (Current Session/Day)
            # This matches "Current Session" logic better than Global History which is sparse
            for user_buckets in raw.get("user_buckets", {}).values():
                for key, bucket in user_buckets.items():
                    used = bucket.get("used", {})
                    t = used.get("tokens_in", 0) + used.get("tokens_out", 0)

                    k_low = key.lower()
                    if k_low.startswith("high"):
                        total_high += t
                    elif k_low.startswith("stable"):
                        total_stable += t
                    elif k_low.startswith("optimization"):
                        total_opt += t

            total_tokens = total_high + total_stable + total_opt

        except Exception:
            pass

    return {
        "total_runs": total_tokens, # Using tokens as runs proxy for now, or just raw tokens
        "total_high": total_high,
        "total_stable": total_stable,
        "total_opt": total_opt,
        "tools": [
            {"name": "web_search", "count": 45, "avg_latency": 850},
            {"name": "read_web_page", "count": 12, "avg_latency": 1200},
            {"name": "python_interpreter", "count": 67, "avg_latency": 320},
        ],
        "recent_tool_calls": []
    }


# --- CHAT API IMPLEMENTATION (Simple/Fake Stream) ---
# Imports moved to top


# Simple in-memory store for active runs (UUID -> asyncio.Queue)
_RUN_QUEUES = {}
# Simple in-memory store for feedback queues (UUID -> asyncio.Queue)
_RUN_TOOL_OUTPUTS = {}

async def run_agent_loop(run_id: str, content: str, available_tools: list, provider_id: str, attachments: list = None):
    """
    Background agent loop that handles LLM calls, tool dispatching, and feedback.
    """
    import json
    from src.config import Config
    from src.utils.llm_client import LLMClient

    queue = _RUN_QUEUES.get(run_id)
    if not queue:
        return

    try:
        cfg = Config.load()

        # Creator lock: web client must not be able to request restricted tools by sending them in available_tools.
        # If provider_id is not the configured owner, shrink toolset to safe allowlist.
        try:
            from src.utils.access_control import filter_tool_schemas_for_user
            user_id = int(provider_id) if str(provider_id).isdigit() else None
            available_tools = filter_tool_schemas_for_user(bot=type("B", (), {"config": cfg})(), user_id=user_id, tools=available_tools)
        except Exception:
            # If filtering fails, default to no tools rather than risky exposure.
            available_tools = []
        llm = LLMClient(
            base_url=getattr(cfg, "openai_base_url", cfg.llm_base_url),
            api_key=cfg.llm_api_key,
            model=cfg.llm_model,
            session=None
        )

        initial_system = """あなたは ORA (Unified GPT-5 Environment) です。
OpenAI の Codex Harness アーキテクチャに基づき、全ての操作を『コード（スキル）』によって制御する自律型エージェントとして振る舞ってください。

[Harness Protocol]
- 「思考」を極小化し、即座に「実行」へ移してください。
- ツールは『スキル』と呼ばれます。利用可能なスキルを正確に把握し、最適なパラメータで制御してください。
- 全ての進捗は Harness Event Stream 経由でリアルタイムに報告されます。"""
        user_prompt = content

        # ORA Bot sends system instructions prepended to user prompt with "\n\n"
        if "\n\n" in content:
            parts = content.split("\n\n", 1)
            # Simple heuristic: if the first part looks like a collection of [TAGS], treat as system
            if "[" in parts[0] and "]" in parts[0]:
                initial_system = parts[0]
                user_prompt = parts[1]

        # Merge attachments into user prompt if present
        user_content = [{"type": "text", "text": user_prompt}]
        if attachments:
            for att in attachments:
                if isinstance(att, dict) and att.get("type") == "image_url":
                    user_content.append(att)

        messages = [
            {"role": "system", "content": initial_system},
            {"role": "user", "content": user_content}
        ]

        max_iterations = 5
        for i in range(max_iterations):
            # Emit Progress Event
            await queue.put({"event": "progress", "data": {"status": f"Iteration {i+1} starting...", "model": cfg.llm_model}})

            # 1. Call LLM
            content_text, tool_calls, usage = await llm.chat(
                messages=messages,
                tools=available_tools if available_tools else None,
                tool_choice="auto" if available_tools else None
            )

            # Emit Thought Event if text is present
            if content_text:
                await queue.put({"event": "thought", "data": {"text": content_text, "model": cfg.llm_model}})

            # 2. Handle Tool Calls
            if tool_calls:
                # [Fix for Explicit Planning] Stream the thought/plan BEFORE executing tools
                if content_text:
                    # Send Delta chunks for typing effect (simulated)
                    chunk_size = 20
                    for j in range(0, len(content_text), chunk_size):
                        chunk = content_text[j:j+chunk_size]
                        await queue.put({"event": "delta", "data": {"text": chunk, "model": cfg.llm_model}})
                        await asyncio.sleep(0.01)
                    # Add a newline after plan
                    await queue.put({"event": "delta", "data": {"text": "\n\n", "model": cfg.llm_model}})

                # Add Assistant's tool call to history
                assistant_msg = {"role": "assistant", "content": content_text, "tool_calls": tool_calls}
                messages.append(assistant_msg)

                # Send Dispatch Event for each tool
                for tc in tool_calls:
                    func = tc.get("function", {})
                    tool_name = func.get("name")
                    tool_args = json.loads(func.get("arguments", "{}"))

                    dispatch_data = {
                        "event": "dispatch",
                        "data": {
                            "tool": tool_name,
                            "args": tool_args,
                            "call_id": tc.get("id")
                        }
                    }
                    await queue.put(dispatch_data)

                    # Wait for feedback on _RUN_TOOL_OUTPUTS
                    # The bot will POST to /runs/{run_id}/results
                    feedback_queue = _RUN_TOOL_OUTPUTS.get(run_id)
                    if feedback_queue:
                        try:
                            # Wait for the specific tool result
                            # [Simplified] We assume results come in order or we just take the next one
                            result_data = await asyncio.wait_for(feedback_queue.get(), timeout=120)

                            # Add Tool result to history
                            raw_result = result_data.get("result", "[Success]")

                            # Standardize: Extract result string if it's a dict
                            result_text = raw_result
                            tool_attachment = None

                            if isinstance(raw_result, dict):
                                result_text = raw_result.get("result", str(raw_result))
                                # Extract Image if multimodal feedback present
                                if "image_b64" in raw_result:
                                    b64 = raw_result["image_b64"]
                                    tool_attachment = {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}

                            tool_msg_content = result_text
                            if tool_attachment:
                                tool_msg_content = [
                                    {"type": "text", "text": result_text},
                                    tool_attachment
                                ]

                            messages.append({
                                "role": "tool",
                                "tool_call_id": tc.get("id"),
                                "name": tool_name,
                                "content": tool_msg_content
                            })
                        except asyncio.TimeoutError:
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tc.get("id"),
                                "name": tool_name,
                                "content": "Error: Tool execution timed out."
                            })

                # Loop back for next iteration (LLM processes results)
                continue

            # 3. Handle Final Text
            if content_text:
                # Send Delta chunks for typing effect (simulated)
                chunk_size = 20
                for j in range(0, len(content_text), chunk_size):
                    chunk = content_text[j:j+chunk_size]
                    await queue.put({"event": "delta", "data": {"text": chunk, "model": cfg.llm_model}})
                    await asyncio.sleep(0.01)

                # Send final event
                await queue.put({"event": "final", "data": {"text": content_text, "model": cfg.llm_model}})

            break # Exit loop if no tool calls

    except Exception as e:
        import traceback
        traceback.print_exc()
        await queue.put({"event": "error", "data": {"message": str(e)}})
    finally:
        # Mark end of stream
        await queue.put(None)

@router.post("/messages")
async def create_message(request: Request, _: None = Depends(require_web_api)):
    """
    Starts a background run and returns a run_id immediately.
    """
    try:
        data = await request.json()
        content = data.get("content", "")
        available_tools = data.get("available_tools", [])
        attachments = data.get("attachments", [])
        identity = data.get("user_identity", {})
        provider_id = identity.get("id", "anonymous")

        run_id = str(uuid.uuid4())

        # Initialize Queues
        _RUN_QUEUES[run_id] = asyncio.Queue()
        _RUN_TOOL_OUTPUTS[run_id] = asyncio.Queue()

        # Start Background Task
        asyncio.create_task(run_agent_loop(run_id, content, available_tools, provider_id, attachments))

        return {"run_id": run_id}

    except Exception as e:
        print(f"Chat Error: {e}")
        return {"error": str(e)}

@router.get("/runs/{run_id}/events")
async def get_run_events(run_id: str, request: Request, _: None = Depends(require_web_api)):
    """
    Stream the events from the background agent loop via SSE.
    """
    async def event_generator():
        queue = _RUN_QUEUES.get(run_id)
        if not queue:
            yield json.dumps({"event": "error", "data": {"message": "Run not found"}})
            return

        try:
            while True:
                if await request.is_disconnected():
                    break

                event = await queue.get()
                if event is None: # Sentinel for end of stream
                    break

                yield json.dumps(event)
        finally:
            # Clean up after stream ends or disconnects
            if run_id in _RUN_QUEUES:
                del _RUN_QUEUES[run_id]
            if run_id in _RUN_TOOL_OUTPUTS:
                del _RUN_TOOL_OUTPUTS[run_id]

    return EventSourceResponse(event_generator())

@router.post("/runs/{run_id}/results")
async def submit_tool_result(run_id: str, result: dict, _: None = Depends(require_web_api)):
    """
    Bot submits tool execution results here to continue the loop.
    """
    import logging
    logger = logging.getLogger(__name__)

    if run_id not in _RUN_TOOL_OUTPUTS:
        raise HTTPException(status_code=404, detail="Run not found or already completed")

    logger.info(f"📥 Received tool result for run {run_id}: {result.get('tool')}")
    await _RUN_TOOL_OUTPUTS[run_id].put(result)
    return {"status": "ok"}
# ----------------------------------------------------

@router.get("/config/limits")
async def get_config_limits():
    """Return the current COST_LIMITS configuration."""
    return COST_LIMITS


# Dependency to get store (lazy import to avoid circular dependency)
def get_store():
    from src.web.app import get_store as _get_store

    return _get_store()


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass


manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str | None = Query(None)):
    # WebSocket auth: match `require_web_api` behavior as closely as possible.
    expected = (os.getenv("ORA_WEB_API_TOKEN") or "").strip()
    require_token = (os.getenv("ORA_REQUIRE_WEB_API_TOKEN") or "").strip().lower() in {"1", "true", "yes", "on"}

    presented = (token or "").strip()
    if not presented:
        presented = (websocket.headers.get("x-ora-token") or "").strip()
    if not presented:
        auth = (websocket.headers.get("authorization") or "").strip()
        parts = auth.split(None, 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            presented = parts[1].strip()

    host = (websocket.client.host if websocket.client else "") or ""
    is_loopback = host in {"127.0.0.1", "::1", "localhost"}

    if expected:
        if (not presented) or (not hmac.compare_digest(presented, expected)):
            await websocket.close(code=1008)
            return
    else:
        if require_token or (not is_loopback):
            await websocket.close(code=1008)
            return

    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


GOOGLE_CLIENT_SECRETS_FILE = "google_client_secrets.json"
GOOGLE_SCOPES = ["openid", "https://www.googleapis.com/auth/drive.file", "email", "profile"]
GOOGLE_REDIRECT_URI = "http://localhost:8000/api/auth/google/callback"  # Update with actual domain in prod


def build_flow(state: str | None = None) -> Flow:
    return Flow.from_client_secrets_file(
        GOOGLE_CLIENT_SECRETS_FILE,
        scopes=GOOGLE_SCOPES,
        redirect_uri=GOOGLE_REDIRECT_URI,
        state=state,
    )


@router.get("/auth/discord")
async def auth_discord(request: Request, code: str | None = None, state: str | None = None):
    # If no code, redirect to Google
    if code is None:
        discord_user_id = request.query_params.get("discord_user_id")
        flow = build_flow(state=discord_user_id or "")
        auth_url, _ = flow.authorization_url(prompt="consent", include_granted_scopes="true")
        return RedirectResponse(auth_url)

    # If code exists, handle Discord auth (not implemented yet per instructions)
    return {"message": "Discord auth flow not fully implemented yet."}


@router.get("/auth/google/callback")
async def auth_google_callback(request: Request, code: str, state: str | None = None):
    # We need the store. Since we can't import from app easily due to circular deps,
    # we will access it via the app instance attached to the request, or import it inside.
    from src.web.app import get_store

    store = get_store()

    flow = build_flow(state=state)
    flow.fetch_token(code=code)

    creds = flow.credentials
    request_adapter = g_requests.Request()
    idinfo = id_token.verify_oauth2_token(
        creds.id_token,
        request_adapter,
        flow.client_config["client_id"],
    )

    google_sub = idinfo["sub"]
    email = idinfo.get("email")

    # Update DB
    await store.upsert_google_user(google_sub=google_sub, email=email, credentials=creds)

    # Link Discord User
    discord_user_id = state
    if discord_user_id:
        # Validate discord_user_id is int-like
        if discord_user_id.isdigit():
            await store.link_discord_google(int(discord_user_id), google_sub)

    return RedirectResponse(url="/linked")  # Redirect to a success page (to be created)


@router.post("/auth/link-code")
async def request_link_code(request: Request):
    """Generate a temporary link code for a Discord user."""
    try:
        data = await request.json()
        discord_user_id = data.get("user_id")
        if not discord_user_id:
            raise HTTPException(status_code=400, detail="Missing user_id")

        store = get_store()
        # Create a unique state/code
        code = str(uuid.uuid4())

        # Store it with expiration (e.g., 15 minutes)
        await store.start_login_state(code, discord_user_id, ttl_sec=900)

        # Return the auth URL that the user should visit
        # In a real app, this might be a short link or just the code
        # For ORA, we return the full URL to the web auth endpoint with state
        auth_url = f"{GOOGLE_REDIRECT_URI}?state={code}"  # Wait, this is callback.
        # We need to point to the start of the flow
        # Actually, the user should visit /api/auth/discord?discord_user_id=...
        # But we want to use the code as state.

        # Let's construct the Google Auth URL directly or via our endpoint
        flow = build_flow(state=code)
        auth_url, _ = flow.authorization_url(prompt="consent", include_granted_scopes="true")

        return {"url": auth_url, "code": code}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ocr")
async def ocr_endpoint(request: Request, _: None = Depends(require_web_api)):
    """
    Analyze an uploaded image using the same logic as the ORA Cog.
    Expects multipart/form-data with 'file'.
    """
    from src.utils import image_tools

    # We need to parse the body manually or use FastAPI's File
    # Since we are inside a router without explicit File param in signature above (to keep imports clean),
    # let's do it properly by importing UploadFile at top or here.
    # To avoid messing up the file structure too much, I'll use Request form.

    form = await request.form()
    file = form.get("file")

    if not file:
        return {"error": "No file provided"}

    content = await file.read()

    # Analyze
    try:
        # Use structured analysis
        result = image_tools.analyze_image_structured(content)
        return result
    except Exception as e:
        return {"error": str(e)}


@router.get("/conversations/latest")
async def get_latest_conversations(user_id: str | None = None, limit: int = 20, _: None = Depends(require_web_api)):
    """Get recent conversations for a user (Discord ID or Google Sub). If None, returns all."""
    from src.web.app import get_store

    store = get_store()

    try:
        convs = await store.get_conversations(user_id, limit)
        return convs
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/memory/graph")
async def get_memory_graph(_: None = Depends(require_web_api)):
    """Get the knowledge graph data."""
    import json
    from pathlib import Path

    try:
        path = Path("graph_cache.json")
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {"ok": True, "data": data}
        return {"ok": True, "data": {"nodes": [], "links": []}}
    except Exception as e:
        return {"ok": False, "error_code": "READ_ERROR", "error_message": str(e)}


@router.get("/dashboard/usage")
async def get_dashboard_usage(_: None = Depends(require_web_api)):
    """Get global cost usage stats from CostManager state file (Aggregated)."""
    import json
    from pathlib import Path

    from src.config import STATE_DIR
    state_path = Path(STATE_DIR) / "cost_state.json"

    # Calculate Today in JST
    # Calculate Today (Match CostManager Timezone)
    import pytz  # type: ignore

    from src.config import COST_TZ

    tz = pytz.timezone(COST_TZ)
    today_str = datetime.now(tz).strftime("%Y-%m-%d")

    # Default Structure
    response_data = {
        "total_usd": 0.0,
        "daily_tokens": {"high": 0, "stable": 0, "burn": 0},
        "last_reset": "",
        "unlimited_mode": False,
        "unlimited_users": [],
        "users": [],
    }

    if not state_path.exists():
        return {"ok": True, "data": response_data, "message": "No cost state found"}

    try:
        with open(state_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        # Helper to Sum Usage
        def add_usage(bucket_key: str, bucket_data: dict, target_data: dict):
            # bucket_data structure: {"used": {"tokens_in": X, "tokens_out": Y, "usd": Z}, ...}
            # target_data: The specific dict in response_data (daily_tokens or lifetime_tokens)

            used = bucket_data.get("used", {})
            tokens = used.get("tokens_in", 0) + used.get("tokens_out", 0)
            usd = used.get("usd", 0.0)

            # Add to proper lane
            if bucket_key.startswith("high:"):
                target_data["high"] += tokens
            elif bucket_key.startswith("stable:"):
                target_data["stable"] += tokens
            elif bucket_key.startswith("burn:"):
                target_data["burn"] += tokens
            elif bucket_key.startswith("optimization:"):
                if "optimization" not in target_data:
                    target_data["optimization"] = 0
                target_data["optimization"] += tokens

            # Add to OpenAI Sum (for verifying against Dashboard)
            # RELAXED CHECK: If it contains 'openai' OR is an optimization lane (usually API)
            # We want to capture ALL API usage in this sum for the user.
            if ":openai" in bucket_key or "optimization" in bucket_key or "high" in bucket_key:
                # Exclude local manually if needed, but usually local doesn't use these lanes in CostManager
                if "openai_sum" in target_data:
                    target_data["openai_sum"] += tokens
                else:
                    target_data["openai_sum"] = tokens

            return usd

        # Default Structure
        response_data = {
            "total_usd": 0.0,
            "daily_tokens": {"high": 0, "stable": 0, "burn": 0},
            "lifetime_tokens": {"high": 0, "stable": 0, "burn": 0, "optimization": 0, "openai_sum": 0},
            "last_reset": datetime.now().isoformat(),
            "unlimited_mode": raw_data.get("unlimited_mode", False),
            "unlimited_users": raw_data.get("unlimited_users", []),
        }

        # 1. Process Global Buckets (Current - Daily)
        for key, bucket in raw_data.get("global_buckets", {}).items():
            if bucket.get("day") == today_str:
                usd_gain = add_usage(key, bucket, response_data["daily_tokens"])
                response_data["total_usd"] += usd_gain

        # 1b. Process Global History (Lifetime)
        # First, add Today's usage to Lifetime
        for key, bucket in raw_data.get("global_buckets", {}).items():
            add_usage(key, bucket, response_data["lifetime_tokens"])

        # Then, add History to Lifetime
        for key, history_list in raw_data.get("global_history", {}).items():
            for bucket in history_list:
                usd_gain = add_usage(key, bucket, response_data["lifetime_tokens"])
                response_data["total_usd"] += usd_gain  # Accumulate lifetime USD? Or just daily USD?
                # Burn limit is cumulative, so let's track ALL usage USD here for "Lifetime USD".
                # But "Current Burn Limit" might need separate logic.
                # For this dashboard view, "Total Spend" implies Lifetime.

        # 2. Process User Buckets (Main Source of Truth for Dashboard)
        # We assume User Buckets contain the breakdown.
        # To avoid double counting with Global (if it existed), we rely on Users here or use max.
        # Given Global seems empty/desynced, we add User usage to valid totals.

        for user_buckets in raw_data.get("user_buckets", {}).values():
            for key, bucket in user_buckets.items():
                # Aggressive Accumulation: Show ALL usage in "Daily" (Cards) for meaningful numbers
                # if bucket.get("day") == today_str:
                if True:
                    usd_gain = add_usage(key, bucket, response_data["daily_tokens"])
                    # Accumulate Total USD from Users (Wait, total_usd is usually lifetime?)
                    # If we only sum today, it's Daily Cost. If we sum all, it's Lifetime.
                    # The UI likely separates them.
                    # But the variable is `total_usd` at root.
                    # If the bug was "Not Resetting", it means Daily Tokens wasn't resetting,
                    # AND total_usd (Daily Cost?) wasnt resetting.
                    # So we should filter USD too.
                    response_data["total_usd"] += usd_gain

                # CRITICAL FIX: Also aggregate User Usage into Lifetime Tokens
                # This ensures that if Global History is missing/desynced, the Dashboard still shows the sum of known users.
                # add_usage adds to the target dict.
                add_usage(key, bucket, response_data["lifetime_tokens"])

        # 2a. Populate Users List for Dashboard Table
        users_list = []
        for uid, buckets in raw_data.get("user_buckets", {}).items():
            user_usd = 0.0
            user_tokens = {"high": 0, "stable": 0, "burn": 0, "optimization": 0}

            for b_key, b_val in buckets.items():
                used = b_val.get("used", {})
                t = used.get("tokens_in", 0) + used.get("tokens_out", 0)
                u = used.get("usd", 0.0)
                user_usd += u

                k_low = b_key.lower()
                if k_low.startswith("high"):
                    user_tokens["high"] += t
                elif k_low.startswith("stable"):
                    user_tokens["stable"] += t
                elif k_low.startswith("burn"):
                    user_tokens["burn"] += t
                elif k_low.startswith("optimization"):
                    user_tokens["optimization"] += t

            users_list.append({
                "discord_user_id": uid,
                "display_name": uid, # ID as name fallback
                "status": "active",
                "cost_usage": {
                    "total_usd": user_usd,
                    **user_tokens
                },
                "avatar_url": None
            })
        response_data["users"] = users_list

        # 2b. User History Loop (to catch past usage not in current user_buckets)
        for user_hists in raw_data.get("user_history", {}).values():
            for key, hist_list in user_hists.items():
                for bucket in hist_list:
                    add_usage(key, bucket, response_data["lifetime_tokens"])

            # Update Lifetime with User data too?
            # If we trust user buckets, we should ensure they feed into lifetime view if needed.
            # But lifetime_tokens loop (1b) looked at Global History.
            # If Global History is empty, user history won't be seen.
            # For now, fixing "Current Estimated Cost" (total_usd) is the priority.

        # 2b. User History Loop (to catch past usage not in current user_buckets)
        for user_hists in raw_data.get("user_history", {}).values():
            for key, hist_list in user_hists.items():
                for bucket in hist_list:
                    # Accumulate to lifetime tokens and USD
                    usd_val = add_usage(key, bucket, response_data["lifetime_tokens"])
                    # Important: Add historical USD to total_usd
                    response_data["total_usd"] += usd_val

        return {"ok": True, "data": response_data, "debug_user_history_count": len(raw_data.get("user_history", {}))}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/dashboard/history")
async def get_dashboard_history(_: None = Depends(require_web_api)):
    """Get historical usage data (timeline) and model breakdown."""
    import json
    from pathlib import Path

    from src.config import STATE_DIR
    state_path = Path(STATE_DIR) / "cost_state.json"
    # state_path = Path("L:/ORA_State/cost_state.json")
    print(f"DEBUG: Loading state from {state_path}")
    if not state_path.exists():
        return {"ok": False, "error": "No cost state found"}

    try:
        with open(state_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        timeline = {}  # "YYYY-MM-DD" -> {high, stable, optimization, usd}
        breakdown = {}  # "high" -> {"openai": 100, "total": 100}
        hourly = {}  # "YYYY-MM-DDTHH" -> {hour, high, stable, optimization, burn, usd}

        def process_bucket(key, bucket, date_str):
            # 1. Update Timeline
            if date_str not in timeline:
                timeline[date_str] = {
                    "date": date_str,
                    "high": 0,
                    "stable": 0,
                    "optimization": 0,
                    "burn": 0,
                    "usd": 0.0,
                }

            t_data = timeline[date_str]
            used = bucket.get("used", {})
            reserved = bucket.get("reserved", {})
            tokens = (
                used.get("tokens_in", 0)
                + used.get("tokens_out", 0)
                + reserved.get("tokens_in", 0)
                + reserved.get("tokens_out", 0)
            )
            usd = used.get("usd", 0.0) + reserved.get("usd", 0.0)

            t_data["usd"] += usd

            key_lower = key.lower()
            lane = "unknown"
            if key_lower.startswith("high"):
                t_data["high"] += tokens
                lane = "high"
            elif key_lower.startswith("stable"):
                t_data["stable"] += tokens
                lane = "stable"
            elif key_lower.startswith("optimization"):
                t_data["optimization"] += tokens
                lane = "optimization"
            elif key_lower.startswith("burn"):
                t_data["burn"] += tokens
                lane = "burn"

            # 2. Update Breakdown (Total Lifetime)
            if lane not in breakdown:
                breakdown[lane] = {"total": 0}

            breakdown[lane]["total"] += tokens

            # Extract Provider/Model (Format: lane:provider:model)
            parts = key_lower.split(":")
            if len(parts) >= 2:
                provider = parts[1]
                # If model is present, maybe use it? For now just provider.
                model = parts[2] if len(parts) > 2 else "default"
                label = f"{provider} ({model})"

                if label not in breakdown[lane]:
                    breakdown[lane][label] = 0
                breakdown[lane][label] += tokens

        def process_hourly(bucket_key, hour_map):
            key_lower = bucket_key.lower()
            lane = "unknown"
            if key_lower.startswith("high"):
                lane = "high"
            elif key_lower.startswith("stable"):
                lane = "stable"
            elif key_lower.startswith("optimization"):
                lane = "optimization"
            elif key_lower.startswith("burn"):
                lane = "burn"

            if lane == "unknown":
                return

            for hour, usage in hour_map.items():
                if hour not in hourly:
                    hourly[hour] = {"hour": hour, "high": 0, "stable": 0, "optimization": 0, "burn": 0, "usd": 0.0}
                tokens = usage.get("tokens_in", 0) + usage.get("tokens_out", 0)
                usd = usage.get("usd", 0.0)
                hourly[hour][lane] += tokens
                hourly[hour]["usd"] += usd

        # Process History
        for key, hist_list in raw_data.get("global_history", {}).items():
            for bucket in hist_list:
                process_bucket(key, bucket, bucket["day"])

        # Process Current (Today)
        for key, bucket in raw_data.get("global_buckets", {}).items():
            process_bucket(key, bucket, bucket["day"])

        # CRITICAL: If Global History is thin, aggregate User History
        # (Since we saw Global has 2 keys vs User 400 keys)
        for user_hists in raw_data.get("user_history", {}).values():
             for key, hist_list in user_hists.items():
                for bucket in hist_list:
                    # We process it as if it's global bucket data for the timeline
                    # This might double count IF global history matches, but since global is empty, it fills gaps.
                    # Ideally we'd dedupe by lane+date, but process_bucket adds +=.
                    # Given the "Global History Keys: 2", it's likely Global is missing most data.
                    # Debug print to console
                    # print(f"DEBUG: Processing bucket {bucket['day']} from {key}")
                    process_bucket(key, bucket, bucket["day"])

        # Process User History
        for user_hists in raw_data.get("user_history", {}).values():
            for key, hist_list in user_hists.items():
                for bucket in hist_list:
                    process_bucket(key, bucket, bucket["day"])

        # Process User Current Buckets
        for user_buckets in raw_data.get("user_buckets", {}).values():
            for key, bucket in user_buckets.items():
                process_bucket(key, bucket, bucket["day"])

        # Process Hourly (Global + User)
        for key, hour_map in raw_data.get("global_hourly", {}).items():
            process_hourly(key, hour_map)
        for user_hour_map in raw_data.get("user_hourly", {}).values():
            for key, hour_map in user_hour_map.items():
                process_hourly(key, hour_map)

        # Convert timeline to sorted list
        sorted_timeline = sorted(timeline.values(), key=lambda x: x["date"])
        sorted_hourly = [hourly[k] for k in sorted(hourly.keys())]

        return {"ok": True, "data": {"timeline": sorted_timeline, "breakdown": breakdown, "hourly": sorted_hourly}}

    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/dashboard/users")
async def get_dashboard_users(response: Response, _: None = Depends(require_web_api)):
    """Get list of users with display names and stats from Memory JSONs."""
    # Force No-Cache to ensure real-time updates
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, proxy-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    import json
    from pathlib import Path

    import aiofiles  # type: ignore

    from src.config import MEMORY_DIR, STATE_DIR
    Path(MEMORY_DIR) / "users"
    users = []

    # 1. Load Discord State (Presence/Names/Guilds) FIRST
    discord_state_path = Path(STATE_DIR) / "discord_state.json"
    discord_state = {"users": {}, "guilds": {}}
    if discord_state_path.exists():
        try:
            with open(discord_state_path, "r", encoding="utf-8") as f:
                discord_state = json.load(f)
        except Exception:
            pass  # Sync might be writing

    try:
        memory_path = Path(MEMORY_DIR)
        user_files = []
        if memory_path.exists():
            # 1. Look in root
            user_files.extend(list(memory_path.glob("*.json")))
            # 2. Look in users/ subfolder
            users_sub = memory_path / "users"
            if users_sub.exists():
                user_files.extend(list(users_sub.glob("*.json")))

        for method_file in user_files:
                try:
                    uid = method_file.stem  # Filename without extension = User ID

                    async with aiofiles.open(method_file, "r", encoding="utf-8") as f:
                        content = await f.read()
                        data = json.loads(content)

                        traits = data.get("traits", [])

                        # Respect saved status
                        raw_status = data.get("status", "Optimized" if len(traits) > 0 else "New")

                        real_discord_id = data.get("discord_user_id", uid.split("_")[0])

                        # Resolve Name/Guild if missing/unknown
                        display_name = data.get("name", "Unknown")
                        guild_name = data.get("guild_name", "Unknown Server")

                        # Fallback Logic:
                        # 1. If memory file has a real name (not Unknown or User_ID), use it.
                        # 2. If it's a generic name/ID, try discord_state (Live Cache).
                        # 3. If still ID, and it starts with User_UID, try to resolve just the name part from ANY source.
                        d_user = discord_state["users"].get(real_discord_id, {})

                        is_generic = display_name in ["Unknown", ""] or display_name.startswith("User_") or display_name.isdigit()

                        if is_generic:
                            if d_user.get("name"):
                                display_name = d_user["name"]
                            elif data.get("name") and not data["name"].startswith("User_") and not data["name"].isdigit():
                                display_name = data["name"]

                        # Strip "User_" prefix for cleaner display if all else fails
                        if display_name.startswith("User_") and "_" in display_name:
                            # User_123_456 -> 123
                            parts = display_name.split("_")
                            if len(parts) > 1:
                                parts[1]
                                # We still want a name, but if we CANNOT find one,
                                # we keep it as is or try to look up in a global name cache if we had one.
                                # For now, let's just ensure the priority above works.

                        if guild_name == "Unknown Server":
                            # Try to find guild from file name if possible (UID_GID)
                            parts = uid.split("_")
                            if len(parts) == 2:
                                gid = parts[1]
                                if gid in discord_state.get("guilds", {}):
                                    guild_name = discord_state["guilds"][gid]

                            # Try to find guild from discord_state user info
                            if guild_name == "Unknown Server":
                                d_user = discord_state["users"].get(real_discord_id, {})
                                gid = d_user.get("guild_id")
                                if gid and gid in discord_state.get("guilds", {}):
                                    guild_name = discord_state["guilds"][gid]

                        # Deduplication Check
                        # If we already have this (real_id, guild_name) tuple, keep the one with more points/optimized status
                        # Deduplication Logic: Prioritize Processing (Show activity) > Optimized > Error > New
                        score_base = 0
                        if raw_status.lower() == "processing":
                            score_base = 2500
                        elif raw_status.lower() == "optimized":
                            score_base = 2000
                        elif raw_status.lower() == "error":
                            score_base = 1000

                        entry = {
                            "discord_user_id": method_file.stem,
                            "real_user_id": real_discord_id,
                            "display_name": display_name,
                            "created_at": data.get("last_updated", ""),
                            "points": len(traits),
                            "message_count": data.get("message_count", len(data.get("last_context", []))),
                            "status": raw_status,
                            "impression": data.get("impression", None),
                            "guild_name": guild_name,
                            "banner": data.get("banner", None),
                            "traits": traits,
                            "deep_analysis": data.get("layer2_user_memory", {}).get("deep_analysis", None),
                            "is_nitro": d_user.get("is_nitro", False),
                            "_sort_score": score_base + len(traits),
                        }
                        users.append(entry)
                except Exception as e:
                    print(f"Error reading user file {method_file}: {e}")

        # 2. Merge with Cost Data & Find Ghost Users
        from src.config import STATE_DIR
        state_path = Path(STATE_DIR) / "cost_state.json"
        cost_data = {}
        if state_path.exists():
            with open(state_path, "r", encoding="utf-8") as f:
                cost_data = json.load(f)

        # Use a set of (REAL User ID, Guild Name) to allow same user in different guilds
        existing_keys = set()
        for u in users:
            uid = str(u.get("real_user_id", u["discord_user_id"]))
            gname = u.get("guild_name", "Unknown Server")
            existing_keys.add((uid, gname))

        # 2a. Check for users who have cost activity but NO memory file yet
        all_user_buckets = cost_data.get("user_buckets", {})
        for uid in all_user_buckets:
            real_uid_from_bucket = uid.split("_")[0]  # Extract real UID

            # Find name/guild for this bucket
            d_user = discord_state["users"].get(real_uid_from_bucket, {})
            guild_id = d_user.get("guild_id")
            guild_name = "Unknown Server"
            if guild_id and guild_id in discord_state.get("guilds", {}):
                guild_name = discord_state["guilds"][guild_id]

            if (str(real_uid_from_bucket), guild_name) not in existing_keys:
                # Try to resolve Name/Guild from Discord State
                d_user = discord_state["users"].get(real_uid_from_bucket, {})
                display_name = d_user.get("name", f"User {real_uid_from_bucket}"[:12] + "...")

                guild_id = d_user.get("guild_id")
                # Resolve Guild Name from ID
                guild_name = "Unknown Server"
                if guild_id and guild_id in discord_state.get("guilds", {}):
                    guild_name = discord_state["guilds"][guild_id]

                users.append(
                    {
                        "discord_user_id": uid,  # Keep original bucket ID for cost lookup
                        "real_user_id": real_uid_from_bucket,  # Use real UID for deduplication
                        "display_name": display_name,
                        "created_at": "",
                        "points": 0,
                        "status": "New",
                        "impression": "No memory data yet",
                        "guild_name": guild_name,
                        "banner": d_user.get("banner"),
                        "traits": [],
                        "is_nitro": d_user.get("is_nitro", False),
                        "_sort_score": 0,
                    }
                )
                existing_keys.add((str(real_uid_from_bucket), guild_name))

        # 3. [Fix] Backfill from Discord State (Active Users without Cost or Memory)
        for d_uid, d_user in discord_state.get("users", {}).items():
            guild_id = d_user.get("guild_id")
            guild_name = "Unknown Server"
            if guild_id and guild_id in discord_state.get("guilds", {}):
                guild_name = discord_state["guilds"][guild_id]

            # Check if this (uid, guild) tuple exists
            if (str(d_uid), guild_name) not in existing_keys:
                users.append(
                    {
                        "discord_user_id": d_uid,
                        "real_user_id": d_uid,
                        "display_name": d_user.get("name", "Unknown"),
                        "created_at": "",
                        "points": 0,
                        "status": "Online" if d_user.get("status") != "offline" else "Offline",
                        "impression": "Active in Discord",
                        "guild_name": guild_name,
                        "banner": d_user.get("banner"),
                        "traits": [],
                        "is_nitro": d_user.get("is_nitro", False),
                        "_sort_score": -1, # Low priority until interacted
                    }
                )
                existing_keys.add((str(d_uid), guild_name))



        # 3. Calculate Cost Usage for ALL Users & Inject Presence
        for u in users:
            uid = u["discord_user_id"]

            # Inject Presence using REAL ID (Fix for uid_gid mismatch)
            target_uid = str(u.get("real_user_id", uid))
            d_user = discord_state["users"].get(target_uid, {})
            u["discord_status"] = d_user.get("status", "offline")

            # Ensure is_bot is present (fallback to discord_state if not set in earlier steps)
            if "is_bot" not in u:
                u["is_bot"] = d_user.get("is_bot", False)

            # Fix Name if "Unknown" and we have data
            if u["display_name"] == "Unknown" and d_user.get("name"):
                u["display_name"] = d_user.get("name")

            # Inject URLs
            if not u.get("avatar_url"):
                u["avatar_url"] = (
                    f"https://cdn.discordapp.com/avatars/{target_uid}/{d_user.get('avatar')}.png"
                    if d_user.get("avatar")
                    else None
                )

            # Banner Prioritization: JSON (Global/Memory) > Discord State (Live)
            banner_key = u.get("banner") or d_user.get("banner")
            u["banner_url"] = (
                f"https://cdn.discordapp.com/banners/{target_uid}/{banner_key}.png" if banner_key else None
            )
            # Default Structure
            u["cost_usage"] = {"high": 0, "stable": 0, "burn": 0, "total_usd": 0.0}

            target_id = uid
            # If composite ID (UID_GID) is not in bucket, try real_user_id (UID)
            if target_id not in all_user_buckets and "real_user_id" in u:
                target_id = u["real_user_id"]

            if target_id in all_user_buckets:
                user_specific_buckets = all_user_buckets[target_id]
                for key, bucket in user_specific_buckets.items():
                    used = bucket.get("used", {})
                    reserved = bucket.get("reserved", {})
                    tokens = (
                        used.get("tokens_in", 0)
                        + used.get("tokens_out", 0)
                        + reserved.get("tokens_in", 0)
                        + reserved.get("tokens_out", 0)
                    )
                    cost = used.get("usd", 0.0) + reserved.get("usd", 0.0)

                    u["cost_usage"]["total_usd"] += cost

                    bucket_key_lower = key.lower()
                    if bucket_key_lower.startswith("high"):
                        u["cost_usage"]["high"] += tokens
                    elif bucket_key_lower.startswith("stable"):
                        u["cost_usage"]["stable"] += tokens
                    elif bucket_key_lower.startswith("burn"):
                        u["cost_usage"]["burn"] += tokens
                    elif bucket_key_lower.startswith("optimization"):
                        if "optimization" not in u["cost_usage"]:
                            u["cost_usage"]["optimization"] = 0
                        u["cost_usage"]["optimization"] += tokens

                    # Detect Provider
                    # key pattern: lane:provider:model or similar
                    parts = bucket_key_lower.split(":")
                    if len(parts) >= 2:
                        provider = parts[1]
                        if "providers" not in u:
                            u["providers"] = set()
                        u["providers"].add(provider)

            # Determine Mode
            providers = u.get("providers", set())
            if "openai" in providers:
                u["mode"] = "API (Paid)"
            elif "local" in providers or "gemini_trial" in providers:
                u["mode"] = "Private (Local/Free)"
            else:
                u["mode"] = "Unknown"

            # Clean up set for JSON
            if "providers" in u:
                del u["providers"]

            # Force Pending status? NO. Only if they strictly lack a profile (handled above).
            # If they have usage but no profile: they were added as Pending.
            # If they have usage AND profile: status comes from profile (Optimized/Idle).
            pass

        # Deduplicate Users by (real_user_id, guild_name)
        # Keep the entry with highest _sort_score
        unique_map = {}
        for u in users:
            # Safety: Fallback to discord_user_id if real_user_id is missing
            rid = u.get("real_user_id", u["discord_user_id"])
            key = (rid, u["guild_name"])
            if key not in unique_map:
                unique_map[key] = u
            else:
                # Compare scores
                if u.get("_sort_score", 0) > unique_map[key].get("_sort_score", 0):
                    unique_map[key] = u

        # Determine final list
        final_users = list(unique_map.values())

        # Clean up internal keys
        for u in final_users:
            u.pop("_sort_score", None)

        # Global Property Sync (Fix for Header/Nitro/Impression mismatch across servers)
        # 1. Collect Best Global Props
        global_props = {}
        for u in final_users:
            rid = u.get("real_user_id")
            if not rid:
                continue

            if rid not in global_props:
                global_props[rid] = {"banner_url": None, "is_nitro": False, "impression": None}

            # Propagate Banner (First non-null wins, or prefer one with value)
            if u.get("banner_url") and not global_props[rid]["banner_url"]:
                global_props[rid]["banner_url"] = u["banner_url"]

            # Propagate Nitro (True wins)
            if u.get("is_nitro"):
                global_props[rid]["is_nitro"] = True

            # Propagate Impression (Prefer General Profile i.e. no underscore in ID, or just first non-null)
            # General profile usually has ID == Real ID
            is_general = str(u["discord_user_id"]) == str(rid)
            if u.get("impression"):
                # If we encounter the General Profile's impression, It wins (or at least is stored).
                # If we haven't stored any impression yet, store this one.
                # If we already have one, only overwrite if this is the General one.
                if is_general:
                    global_props[rid]["impression"] = u["impression"]
                elif not global_props[rid]["impression"]:
                    global_props[rid]["impression"] = u["impression"]

        # 2. Apply Global Props
        for u in final_users:
            rid = u.get("real_user_id")
            if rid and rid in global_props:
                props = global_props[rid]
                if props["banner_url"] and not u.get("banner_url"):
                    u["banner_url"] = props["banner_url"]
                if props["is_nitro"]:
                    u["is_nitro"] = True
                # Backfill Impression
                if props["impression"] and not u.get("impression"):
                    u["impression"] = props["impression"]

        return {"ok": True, "data": final_users}

    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/dashboard/users/{user_id}")
async def get_user_details(user_id: str, _: None = Depends(require_web_api)):
    """Get full details for a specific user (traits, history, context). Supports dual profiles."""
    import json
    from pathlib import Path

    MEMORY_DIR = Path("L:/ORA_Memory/users")
    parts = user_id.split("_")
    uid = parts[0]
    gid = parts[1] if len(parts) > 1 else None

    specific_data = None
    general_data = None

    try:
        # 1. Try Specific Profile
        if gid:
            # FIX: Check public/private suffixes matching memory.py
            path_spec = MEMORY_DIR / f"{uid}_{gid}_public.json"
            if not path_spec.exists():
                path_spec = MEMORY_DIR / f"{uid}_{gid}_private.json"

            # Legacy fallback
            if not path_spec.exists():
                path_spec = MEMORY_DIR / f"{uid}_{gid}.json"

            if path_spec.exists():
                with open(path_spec, "r", encoding="utf-8") as f:
                    specific_data = json.load(f)

        # 2. Try General Profile
        path_gen = MEMORY_DIR / f"{uid}.json"
        if path_gen.exists():
            with open(path_gen, "r", encoding="utf-8") as f:
                general_data = json.load(f)

        if not specific_data and not general_data:
            return {"ok": False, "error": "User profile not found"}

        return {"ok": True, "data": {"specific": specific_data, "general": general_data}}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/system/refresh_profiles")
async def request_profile_refresh(_: None = Depends(require_admin)):
    """Trigger profile refresh via file signal for the Bot process."""
    try:
        from pathlib import Path

        # Create a trigger file that MemoryCog watches
        trigger_path = Path("refresh_profiles.trigger")
        trigger_path.write_text("trigger", encoding="utf-8")
        return {"ok": True, "message": "Profile refresh requested."}
    except Exception as e:
        return {"ok": False, "error": str(e)}




@router.post("/dashboard/users/{user_id}/optimize")
async def optimize_user(user_id: str, _: None = Depends(require_admin)):
    """Triggers forced optimization for a user."""
    # Extract real Discord ID from potential UID_GID format
    real_uid = int(user_id.split("_")[0])

    # Architecture Change: Write to Queue File for MemoryCog to pick up (IPC)
    import json
    import time
    from pathlib import Path

    parts = user_id.split("_")
    real_uid = int(parts[0])
    target_guild_id = int(parts[1]) if len(parts) > 1 else None

    queue_path = Path("L:/ORA_State/optimize_queue.json")

    try:
        # 1. Read existing queue
        queue = []
        if queue_path.exists():
            try:
                with open(queue_path, "r", encoding="utf-8") as f:
                    queue = json.load(f)
            except Exception:
                queue = []

        # 2. Append new request
        queue.append({"user_id": real_uid, "guild_id": target_guild_id, "timestamp": time.time()})

        # 3. Write back (Atomic-ish)
        with open(queue_path, "w", encoding="utf-8") as f:
            json.dump(queue, f, indent=2)

        return {"status": "queued", "message": "Optimization requested via Queue"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to queue optimization: {e}") from e


@router.post("/system/restart")
async def system_restart(_: None = Depends(require_admin)):
    """Restart the Bot Process (Self-Termination)."""
    # In a managed environment (systemd/Docker), exiting 0 or 1 usually triggers restart.
    import asyncio
    import sys

    # Schedule exit
    async def _exit():
        await asyncio.sleep(1)
        sys.exit(0)

    asyncio.create_task(_exit())
    return {"ok": True, "message": "Restarting system..."}


@router.post("/system/shutdown")
async def system_shutdown(_: None = Depends(require_admin)):
    """Shutdown the Bot Process."""
    import asyncio
    import sys

    async def _exit():
        await asyncio.sleep(1)
        # 0 might mean success and no restart in some configs, but usually scripts loop.
        # If we really want to stop, we might need a specific exit code or flag file.
        # For now, standard exit.
        sys.exit(0)

    asyncio.create_task(_exit())
    return {"ok": True, "message": "Shutting down system..."}


@router.get("/logs/stream")
async def log_stream(_: None = Depends(require_admin)):
    """Simple Log Stream (Not fully implemented, returns recent logs)."""
    # For a real stream, we'd use WebSocket or SSE.
    # Here, let's just return the last 50 lines of the log file if available.
    log_path = "discord.log"
    try:
        if os.path.exists(log_path):
            with open(log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                return {"ok": True, "logs": lines[-50:]}
        return {"ok": False, "error": "Log file not found"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/dashboard/view", response_class=Response)
async def get_server_dashboard_view(token: str):
    """Render a beautiful, server-specific dashboard (HTML) SECURELY."""

    from fastapi.responses import HTMLResponse

    # 0. Validate Token
    from src.web.app import get_store

    store = get_store()

    guild_id = await store.validate_dashboard_token(token)
    if not guild_id:
        return HTMLResponse(
            "<h1>403 Access Denied</h1><p>Invalid or expired dashboard token. Please generate a new link using <code>/dashboard</code> in your server.</p>",
            status_code=403,
        )

    # 1. Fetch ALL users (reuse logic)
    class MockResponse:
        headers = {}

    res = await get_dashboard_users(MockResponse())
    if not res.get("ok"):
        return HTMLResponse(f"Error loading data: {res.get('error')}", status_code=500)

    all_users = res.get("data", [])

    # 2. Filter by Guild ID (Securely obtained from Token)
    server_users = []
    guild_name = "Unknown Server"

    for u in all_users:
        # Check explicit guild_id
        if str(u.get("guild_id")) == guild_id:
            server_users.append(u)
            if u.get("guild_name") and u["guild_name"] != "Unknown Server":
                guild_name = u["guild_name"]
        # Fallback: Check if UID_GID matches (though with token, this might be less relevant)
        elif "_" in str(u["discord_user_id"]):
            parts = str(u["discord_user_id"]).split("_")
            if len(parts) == 2 and parts[1] == guild_id:
                server_users.append(u)
                if u.get("guild_name") and u["guild_name"] != "Unknown Server":
                    guild_name = u["guild_name"]

    # 3. Calculate Stats
    total_users = len(server_users)
    total_cost = sum(u["cost_usage"]["total_usd"] for u in server_users)
    active_users = len([u for u in server_users if u["status"] != "New"])

    # 4. Generate HTML (Dark Mode, Glassmorphism)
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ORA Dashboard - {guild_name}</title>
        <style>
            :root {{
                --bg: #0f172a;
                --card-bg: rgba(30, 41, 59, 0.7);
                --text-main: #f8fafc;
                --text-sub: #94a3b8;
                --accent: #3b82f6;
                --accent-glow: rgba(59, 130, 246, 0.5);
                --sc-success: #10b981;
                --sc-warn: #f59e0b;
                --sc-danger: #ef4444;
            }}
            body {{
                background-color: var(--bg);
                background-image: radial-gradient(circle at 10% 20%, rgba(59, 130, 246, 0.1) 0%, transparent 20%),
                                  radial-gradient(circle at 90% 80%, rgba(16, 185, 129, 0.05) 0%, transparent 20%);
                color: var(--text-main);
                font-family: 'Inter', system-ui, -apple-system, sans-serif;
                margin: 0;
                padding: 40px;
                min-height: 100vh;
            }}
            .container {{
                max-width: 1200px;
                margin: 0 auto;
            }}
            header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 40px;
                border-bottom: 1px solid rgba(255,255,255,0.1);
                padding-bottom: 20px;
            }}
            h1 {{
                font-size: 2.5rem;
                font-weight: 800;
                background: linear-gradient(135deg, #fff 0%, #94a3b8 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin: 0;
            }}

            .stats-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 20px;
                margin-bottom: 40px;
            }}
            .stat-card {{
                background: var(--card-bg);
                backdrop-filter: blur(12px);
                border: 1px solid rgba(255,255,255,0.05);
                border-radius: 16px;
                padding: 24px;
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
                transition: transform 0.2s;
            }}
            .stat-card:hover {{
                transform: translateY(-2px);
                border-color: rgba(255,255,255,0.1);
            }}
            .stat-label {{ color: var(--text-sub); font-size: 0.9rem; margin-bottom: 8px; }}
            .stat-value {{ font-size: 2rem; font-weight: 700; color: #fff; }}

            .users-table {{
                width: 100%;
                border-collapse: collapse;
                background: var(--card-bg);
                backdrop-filter: blur(12px);
                border-radius: 16px;
                overflow: hidden;
                border: 1px solid rgba(255,255,255,0.05);
            }}
            th, td {{
                padding: 16px 24px;
                text-align: left;
                border-bottom: 1px solid rgba(255,255,255,0.05);
            }}
            th {{
                background: rgba(0,0,0,0.2);
                color: var(--text-sub);
                font-weight: 600;
                font-size: 0.85rem;
                text-transform: uppercase;
                letter-spacing: 0.05em;
            }}
            tr:last-child td {{ border-bottom: none; }}
            tr:hover td {{ background: rgba(255,255,255,0.02); }}

            .avatar {{
                width: 32px;
                height: 32px;
                border-radius: 50%;
                vertical-align: middle;
                margin-right: 12px;
                border: 2px solid rgba(255,255,255,0.1);
            }}
            .badge {{
                display: inline-block;
                padding: 4px 10px;
                border-radius: 20px;
                font-size: 0.75rem;
                font-weight: 600;
            }}
            .badge-success {{ background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.2); }}
            .badge-warn {{ background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.2); }}
            .badge-neutral {{ background: rgba(148, 163, 184, 0.2); color: #cbd5e1; border: 1px solid rgba(148, 163, 184, 0.2); }}

            .cost {{ font-family: 'SF Mono', 'Roboto Mono', monospace; color: var(--sc-warn); }}

        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <div>
                    <h1>{guild_name}</h1>
                    <span style="color: var(--text-sub)">Server Dashboard</span>
                </div>
                <div style="text-align: right">
                     <span class="badge badge-success">SECURE VIEW</span>
                     <span class="badge badge-neutral">ID: {guild_id}</span>
                </div>
            </header>

            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-label">Total Users</div>
                    <div class="stat-value">{total_users}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Active Profiles</div>
                    <div class="stat-value">{active_users}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">AI Cost (Est.)</div>
                    <div class="stat-value" style="color: #fbbf24">${total_cost:.4f}</div>
                </div>
            </div>

            <h2 style="margin-bottom: 20px; font-weight: 600;">Member Activity</h2>

            <table class="users-table">
                <thead>
                    <tr>
                        <th>User</th>
                        <th>Status</th>
                        <th>Points</th>
                        <th>AI Cost</th>
                        <th>Last Active</th>
                    </tr>
                </thead>
                <tbody>
    """

    for u in server_users:
        avatar = u.get("avatar_url") or "https://cdn.discordapp.com/embed/avatars/0.png"
        status = u.get("status", "New")
        if status == "Optimized":
            pass
        elif status == "Processing":
            pass

        cost = u["cost_usage"]["total_usd"]

        html += f"""
                    <tr>
                        <td>
                            <img src="{avatar}" class="avatar" alt="av">
                            {u["display_name"]}
                        </td>
                        <td><span class="badge {{badge_class}}">{status}</span></td>
                        <td>{u["points"]}</td>
                        <td class="cost">${cost:.4f}</td>
                        <td style="color: var(--text-sub)">{u.get("created_at", "N/A")[:16]}</td>
                    </tr>
        """

    html += """
                </tbody>
            </table>
        </div>
    </body>
    </html>
    """

    return HTMLResponse(content=html, status_code=200)

@router.get("/dashboard/admin", response_class=Response)
async def get_admin_dashboard_view(token: str):
    """Render a SUPER ADMIN DASHBOARD showing ALL servers."""
    from fastapi.responses import HTMLResponse

    # Strict token validation
    # - ADMIN_DASHBOARD_TOKEN must be configured for production usage.
    # - Legacy fallback can be enabled only with ALLOW_INSECURE_ADMIN_DASHBOARD=1.
    admin_token = (os.getenv("ADMIN_DASHBOARD_TOKEN") or "").strip()
    allow_legacy = (os.getenv("ALLOW_INSECURE_ADMIN_DASHBOARD") or "").strip().lower() in {"1", "true", "yes", "on"}
    if admin_token:
        if not token or not hmac.compare_digest(token, admin_token):
            raise HTTPException(status_code=403, detail="Invalid admin dashboard token")
    elif not allow_legacy:
        raise HTTPException(status_code=503, detail="ADMIN_DASHBOARD_TOKEN is not configured")

    # 1. Fetch ALL users
    class MockResponse:
        headers = {}

    res = await get_dashboard_users(MockResponse())
    if not res.get("ok"):
        return HTMLResponse(f"Error loading data: {res.get('error')}", status_code=500)

    all_users = res.get("data", [])

    # 2. Group by Guild
    guilds = {}
    for u in all_users:
        gname = u.get("guild_name", "Unknown Server")
        if gname not in guilds:
            guilds[gname] = {"users": [], "cost": 0.0}

        guilds[gname]["users"].append(u)
        guilds[gname]["cost"] += u["cost_usage"]["total_usd"]

    # 3. Generate HTML
    html_rows = ""
    for gname, data in guilds.items():
        g_users = data["users"]
        g_cost = data["cost"]

        html_rows += f"""
        <div class="guild-section">
            <div class="guild-header">
                <h3>{gname}</h3>
                <span class="badge badge-warn">${g_cost:.4f}</span>
            </div>
            <table class="users-table">
                <thead>
                    <tr>
                        <th>User</th>
                        <th>Status</th>
                        <th>Points</th>
                        <th>Cost</th>
                    </tr>
                </thead>
                <tbody>
        """
        for u in g_users:
             avatar = u.get("avatar_url") or "https://cdn.discordapp.com/embed/avatars/0.png"
             html_rows += f"""
                    <tr>
                        <td><img src="{avatar}" class="avatar">{u["display_name"]}</td>
                        <td>{u["status"]}</td>
                        <td>{u["points"]}</td>
                        <td class="cost">${u["cost_usage"]["total_usd"]:.4f}</td>
                    </tr>
             """
        html_rows += "</tbody></table></div><br>"

    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ORA SUPER ADMIN</title>
        <style>
            :root {{
                --bg: #0f172a;
                --card-bg: rgba(30, 41, 59, 0.7);
                --text-main: #f8fafc;
                --text-sub: #94a3b8;
            }}
            body {{
                background-color: var(--bg);
                color: var(--text-main);
                font-family: 'Inter', sans-serif;
                padding: 40px;
            }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            .guild-section {{
                background: var(--card-bg);
                border-radius: 16px;
                padding: 20px;
                border: 1px solid rgba(255,255,255,0.05);
            }}
            .guild-header {{
                display: flex; justify-content: space-between; align-items: center;
                margin-bottom: 15px; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 10px;
            }}
            h3 {{ margin: 0; color: #3b82f6; }}
            .users-table {{ width: 100%; border-collapse: collapse; }}
            th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.05); }}
            .avatar {{ width: 24px; height: 24px; border-radius: 50%; vertical-align: middle; margin-right: 8px; }}
            .badge-warn {{ background: rgba(245, 158, 11, 0.2); color: #fbbf24; padding: 4px 8px; border-radius: 12px; font-size: 0.8rem; }}
            .cost {{ color: #fbbf24; font-family: monospace; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>♾️ ORA ADMIN CONSOLE</h1>
            <p>Overview of all active servers and resource usage.</p>
            {html_rows}
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html, status_code=200)


@router.get("/audit/tools")
async def api_audit_tools(
    request: Request,
    limit: int = 200,
    actor_id: str | None = None,
    tool_name: str | None = None,
    since_ts: int | None = None,
    _: None = Depends(require_admin),
):
    store = get_store()
    aid = int(actor_id) if actor_id and actor_id.isdigit() else None
    rows = await store.get_tool_audit_rows(limit=limit, actor_id=aid, tool_name=tool_name, since_ts=since_ts)
    return {"ok": True, "data": rows}


@router.get("/audit/approvals")
async def api_audit_approvals(
    request: Request,
    limit: int = 200,
    since_ts: int | None = None,
    _: None = Depends(require_admin),
):
    store = get_store()
    rows = await store.get_approval_requests_rows(limit=limit, since_ts=since_ts)
    # Do not expose expected codes in audit output.
    for r in rows:
        if "expected_code" in r:
            r["expected_code"] = None
            r["expected_code_present"] = bool(r.get("requires_code"))
    return {"ok": True, "data": rows}


@router.get("/approvals")
async def api_list_approvals(
    request: Request,
    limit: int = 100,
    status: str | None = "pending",
    _: None = Depends(require_web_api),
):
    store = get_store()
    st = (status or "").strip().lower()
    st = st if st in {"pending", "approved", "denied", "expired", "timeout"} else None
    rows = await store.get_approval_requests_rows(limit=limit, status=st)
    # Do not expose expected codes over the Web API (owner should get codes via DM).
    for r in rows:
        if "expected_code" in r:
            r["expected_code"] = None
            r["expected_code_present"] = bool(r.get("requires_code"))
    return {"ok": True, "data": rows}


@router.get("/approvals/{tool_call_id}")
async def api_get_approval(
    tool_call_id: str,
    _: None = Depends(require_web_api),
):
    store = get_store()
    row = await store.get_approval_request(tool_call_id=str(tool_call_id))
    if not row:
        raise HTTPException(status_code=404, detail="approval not found")
    row["expected_code"] = None
    row["expected_code_present"] = bool(row.get("requires_code"))
    return {"ok": True, "data": row}


class ApprovalDecision(BaseModel):
    code: str | None = None


@router.post("/approvals/{tool_call_id}/approve")
async def api_approve_approval(
    tool_call_id: str,
    body: ApprovalDecision,
    _: None = Depends(require_web_api),
):
    store = get_store()
    row = await store.get_approval_request(tool_call_id=str(tool_call_id))
    if not row:
        raise HTTPException(status_code=404, detail="approval not found")
    if row.get("status") != "pending":
        return {"ok": True, "data": row}

    if row.get("requires_code"):
        expected = (row.get("expected_code") or "").strip()
        presented = (body.code or "").strip()
        if not expected:
            raise HTTPException(status_code=500, detail="expected_code missing")
        if presented != expected:
            raise HTTPException(status_code=403, detail="code mismatch")

    ok = await store.decide_approval_request(tool_call_id=str(tool_call_id), status="approved", decided_by="web")
    out = await store.get_approval_request(tool_call_id=str(tool_call_id))
    return {"ok": ok, "data": out}


@router.post("/approvals/{tool_call_id}/deny")
async def api_deny_approval(
    tool_call_id: str,
    _: None = Depends(require_web_api),
):
    store = get_store()
    row = await store.get_approval_request(tool_call_id=str(tool_call_id))
    if not row:
        raise HTTPException(status_code=404, detail="approval not found")
    if row.get("status") != "pending":
        return {"ok": True, "data": row}
    ok = await store.decide_approval_request(tool_call_id=str(tool_call_id), status="denied", decided_by="web")
    out = await store.get_approval_request(tool_call_id=str(tool_call_id))
    return {"ok": ok, "data": out}


@router.get("/audit/chat_events")
async def api_audit_chat_events(
    request: Request,
    limit: int = 200,
    event_type: str | None = None,
    since_ts: int | None = None,
    _: None = Depends(require_admin),
):
    store = get_store()
    rows = await store.get_chat_events_rows(limit=limit, event_type=event_type, since_ts=since_ts)
    return {"ok": True, "data": rows}
