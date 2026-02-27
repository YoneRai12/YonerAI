from __future__ import annotations

import asyncio
import json
import logging
import os
import shlex
import subprocess
import sys
import threading
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

DEFAULT_PROTOCOL_VERSION = os.environ.get("ORA_MCP_PROTOCOL_VERSION", "2025-11-25")
DEFAULT_STDIO_FRAMING = os.environ.get("ORA_MCP_STDIO_FRAMING", "jsonl").strip().lower()
WIN32SYSLOADER_IMPORT_SENTINEL = "_win32sysloader"


def _redact_cmd(cmd: list[str]) -> str:
    # Best-effort redaction: never log full tokens/keys even if user passes them in command args.
    sensitive = ("key", "token", "secret", "password", "auth", "bearer")
    out: list[str] = []
    from src.utils.redaction import redact_text

    for part in cmd:
        low = part.lower()
        if any(s in low for s in sensitive):
            out.append("[REDACTED]")
        elif len(part) > 120:
            out.append(redact_text(part[:60] + "…" + part[-20:]))
        else:
            out.append(redact_text(part))
    return " ".join(out)


def _encode_frame(payload: dict, *, framing: str) -> bytes:
    """
    Encode one JSON-RPC message for stdio transports.

    - jsonl: newline-delimited JSON (used by the official MCP Python stdio transport)
    - lsp: LSP-style Content-Length headers (used by some JSON-RPC stdio servers)
    """
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if framing == "jsonl":
        return body + b"\n"
    header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
    return header + body


def _read_exact_blocking(stream, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = stream.read(n - len(buf))
        if not chunk:
            break
        buf.extend(chunk)
    return bytes(buf)


def _read_mcp_message_blocking(stream, *, framing: str) -> Optional[dict]:
    """
    Read one MCP/JSON-RPC message from a blocking stdio stream.

    Supports:
    - jsonl: newline-delimited JSON (MCP Python stdio transport)
    - lsp: Content-Length framing (some JSON-RPC stdio servers)
    """
    while True:
        line = stream.readline()
        if not line:
            return None
        stripped = line.strip()
        if not stripped:
            continue

        # LSP-style framing: Content-Length + blank line + JSON body
        if framing == "lsp" or stripped.lower().startswith(b"content-length:"):
            if not stripped.lower().startswith(b"content-length:"):
                # Fall back to jsonl if we didn't actually receive headers.
                try:
                    return json.loads(stripped.decode("utf-8", errors="ignore"))
                except Exception:
                    continue

            header_lines = [line]
            while True:
                l2 = stream.readline()
                if not l2:
                    return None
                header_lines.append(l2)
                if l2 in (b"\r\n", b"\n"):
                    break

            length = None
            for raw in b"".join(header_lines).decode("utf-8", errors="ignore").splitlines():
                if raw.lower().startswith("content-length:"):
                    try:
                        length = int(raw.split(":", 1)[1].strip())
                    except Exception:
                        length = None
                    break
            if not length or length <= 0 or length > 50_000_000:
                continue
            body = _read_exact_blocking(stream, length)
            if not body:
                return None
            try:
                return json.loads(body.decode("utf-8", errors="ignore"))
            except Exception:
                continue

        # jsonl framing
        try:
            return json.loads(stripped.decode("utf-8", errors="ignore"))
        except Exception:
            continue


@dataclass(frozen=True)
class MCPTool:
    name: str
    description: str
    input_schema: Dict[str, Any]


class MCPStdioClient:
    """
    Minimal MCP client over stdio.

    This intentionally avoids any external MCP dependency so ORA remains portable.
    """

    def __init__(self, *, name: str, command: str, cwd: Optional[str] = None, env: Optional[Dict[str, str]] = None):
        self.name = name
        self.command_str = command
        cmd = shlex.split(command, posix=os.name != "nt")
        # On Windows, prefer the current interpreter for "python ..." commands so venv deps work.
        # Users can still force a specific interpreter by providing an absolute path.
        if os.name == "nt" and cmd and cmd[0].lower() in {"python", "python.exe"}:
            cmd[0] = sys.executable
        self.command = cmd
        self.cwd = cwd
        self.env = env or {}
        self.framing = DEFAULT_STDIO_FRAMING if DEFAULT_STDIO_FRAMING in ("jsonl", "lsp") else "jsonl"

        self._proc: Optional[subprocess.Popen[bytes]] = None
        self._stdout_thread: Optional[threading.Thread] = None
        self._stderr_thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._pending_lock = threading.Lock()
        self._write_lock = threading.Lock()
        self._pending: dict[int, asyncio.Future] = {}
        self._id = 1
        self._lock = asyncio.Lock()
        self._disabled = False
        self._disabled_reason: Optional[str] = None
        self._disable_lock = threading.Lock()

    async def start(self) -> None:
        if self._disabled:
            raise RuntimeError(f"MCP disabled server={self.name} reason_code={self._disabled_reason}")
        if self._proc and self._proc.poll() is None:
            return

        merged_env = os.environ.copy()
        merged_env.update({k: str(v) for k, v in (self.env or {}).items()})

        logger.info("MCP starting server=%s cmd=%s", self.name, _redact_cmd(self.command))
        self._loop = asyncio.get_running_loop()
        self._proc = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.cwd,
            env=merged_env,
        )
        assert self._proc.stdin and self._proc.stdout and self._proc.stderr

        self._stdout_thread = threading.Thread(target=self._stdout_loop, name=f"mcp-{self.name}-stdout", daemon=True)
        self._stderr_thread = threading.Thread(target=self._stderr_loop, name=f"mcp-{self.name}-stderr", daemon=True)
        self._stdout_thread.start()
        self._stderr_thread.start()
        # Best-effort initialization handshake (MCP uses an LSP-like initialize + initialized).
        # Some servers require this before tools/list will work; others ignore it.
        try:
            await self.request(
                "initialize",
                {
                    "protocolVersion": DEFAULT_PROTOCOL_VERSION,
                    "clientInfo": {"name": "ORA", "version": "mcp-0"},
                    "capabilities": {"tools": {}},
                },
                timeout=10,
            )
            await self.notify("notifications/initialized", None)
        except Exception:
            # Don't hard-fail for compatibility with older/non-standard servers.
            logger.debug("MCP initialize handshake failed server=%s", self.name, exc_info=True)
        if self._disabled:
            await self.close()
            raise RuntimeError(f"MCP disabled server={self.name} reason_code={self._disabled_reason}")

    def _disable_with_reason(self, reason_code: str) -> None:
        with self._disable_lock:
            if self._disabled:
                return
            self._disabled = True
            self._disabled_reason = reason_code
        logger.warning(
            "MCP[%s] disabled reason_code=%s action=no_restart",
            self.name,
            reason_code,
        )

    async def close(self) -> None:
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except Exception:
                pass
            try:
                await asyncio.wait_for(asyncio.to_thread(self._proc.wait), timeout=3)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
        self._proc = None
        self._stdout_thread = None
        self._stderr_thread = None
        self._loop = None

    def _resolve_pending(self, mid: int, msg: dict) -> None:
        with self._pending_lock:
            fut = self._pending.pop(mid, None)
        if fut and not fut.done():
            fut.set_result(msg)

    def _stdout_loop(self) -> None:
        assert self._proc and self._proc.stdout and self._loop
        while True:
            msg = _read_mcp_message_blocking(self._proc.stdout, framing=self.framing)
            if msg is None:
                return
            if not isinstance(msg, dict):
                continue
            if "id" in msg and (msg.get("result") is not None or msg.get("error") is not None):
                try:
                    mid = int(msg.get("id"))
                except Exception:
                    continue
                self._loop.call_soon_threadsafe(self._resolve_pending, mid, msg)

    def _stderr_loop(self) -> None:
        assert self._proc and self._proc.stderr
        from src.utils.redaction import redact_text

        while True:
            line = self._proc.stderr.readline()
            if not line:
                return
            txt = line.decode("utf-8", errors="ignore").rstrip()
            if txt:
                if WIN32SYSLOADER_IMPORT_SENTINEL in txt.lower():
                    self._disable_with_reason("mcp_import_error_win32sysloader")
                    try:
                        if self._proc and self._proc.poll() is None:
                            self._proc.terminate()
                    except Exception:
                        pass
                    return
                logger.warning("MCP[%s] stderr: %s", self.name, redact_text(txt))

    async def request(self, method: str, params: Optional[dict] = None, timeout: int = 60) -> dict:
        await self.start()
        assert self._proc and self._proc.stdin and self._loop

        async with self._lock:
            req_id = self._id
            self._id += 1

            fut: asyncio.Future = self._loop.create_future()
            with self._pending_lock:
                self._pending[req_id] = fut
            payload = {"jsonrpc": "2.0", "id": req_id, "method": method}
            if params is not None:
                payload["params"] = params
            data = _encode_frame(payload, framing=self.framing)

            def _write() -> None:
                assert self._proc and self._proc.stdin
                with self._write_lock:
                    self._proc.stdin.write(data)
                    self._proc.stdin.flush()

            await asyncio.to_thread(_write)

        try:
            msg = await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError as e:
            with self._pending_lock:
                self._pending.pop(req_id, None)
            raise TimeoutError(f"MCP timeout server={self.name} method={method}") from e

        if not isinstance(msg, dict):
            raise RuntimeError(f"MCP invalid response server={self.name}")
        if msg.get("error"):
            raise RuntimeError(f"MCP error server={self.name} method={method}: {msg.get('error')}")
        return msg.get("result") or {}

    async def notify(self, method: str, params: Optional[dict] = None) -> None:
        await self.start()
        assert self._proc and self._proc.stdin

        payload = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            payload["params"] = params

        data = _encode_frame(payload, framing=self.framing)

        def _write() -> None:
            assert self._proc and self._proc.stdin
            with self._write_lock:
                self._proc.stdin.write(data)
                self._proc.stdin.flush()

        await asyncio.to_thread(_write)

    async def list_tools(self) -> list[MCPTool]:
        # Spec/common: tools/list
        res = None
        last_err: Optional[Exception] = None
        for method in ("tools/list", "tools.list", "list_tools"):
            try:
                res = await self.request(method, {}, timeout=20)
                break
            except Exception as e:
                last_err = e
                if self._disabled:
                    break
                continue
        if res is None and last_err is not None:
            rc = None
            try:
                rc = self._proc.returncode if self._proc else None
            except Exception:
                rc = None
            logger.warning("MCP list_tools failed server=%s rc=%s err=%r", self.name, rc, last_err)
        if not isinstance(res, dict):
            return []
        tools = res.get("tools") or res.get("result") or res.get("data") or []
        out: list[MCPTool] = []
        if isinstance(tools, list):
            for t in tools:
                if not isinstance(t, dict):
                    continue
                name = str(t.get("name") or "").strip()
                if not name:
                    continue
                desc = str(t.get("description") or "").strip()
                schema = t.get("inputSchema") or t.get("input_schema") or t.get("parameters") or {}
                if not isinstance(schema, dict):
                    schema = {}
                out.append(MCPTool(name=name, description=desc, input_schema=schema))
        return out

    async def call_tool(self, tool_name: str, arguments: Optional[dict] = None, timeout: int = 180) -> dict:
        args = arguments if isinstance(arguments, dict) else {}
        # Spec/common: tools/call
        res = None
        last_err: Optional[Exception] = None
        for method in ("tools/call", "tools.call", "call_tool"):
            try:
                res = await self.request(method, {"name": tool_name, "arguments": args}, timeout=timeout)
                break
            except Exception as e:
                last_err = e
                if self._disabled:
                    break
                continue
        if res is None and last_err is not None:
            rc = None
            try:
                rc = self._proc.returncode if self._proc else None
            except Exception:
                rc = None
            logger.warning("MCP call_tool failed server=%s tool=%s rc=%s err=%r", self.name, tool_name, rc, last_err)
        if not isinstance(res, dict):
            return {"ok": False, "error": "invalid_response", "raw": res}
        return res
