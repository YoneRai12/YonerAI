from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
import asyncio
from dataclasses import dataclass
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel


def _now() -> int:
    return int(time.time())


def _parse_bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _hash_code(code: str) -> str:
    # Store only hashes in Relay memory.
    return hashlib.sha256((code or "").strip().encode("utf-8", errors="ignore")).hexdigest()


def _safe_json_loads(raw: str) -> dict:
    try:
        obj = json.loads(raw)
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _limit_bytes(data: bytes, max_bytes: int) -> bytes:
    if len(data) <= max_bytes:
        return data
    return data[:max_bytes]


@dataclass
class PairOffer:
    node_id: str
    code_hash: str
    expires_at: int


@dataclass
class Session:
    token_hash: str
    node_id: str
    expires_at: int


class PairRequest(BaseModel):
    code: str


class PairResponse(BaseModel):
    ok: bool
    node_id: str
    token: str
    expires_at: int


class RelayState:
    """
    In-memory state (M2 MVP).
    - No message bodies are persisted.
    - No plaintext pairing codes / tokens are persisted (hash only).
    """

    def __init__(self) -> None:
        self.nodes: dict[str, NodeConn] = {}
        self.pair_offers: dict[str, PairOffer] = {}  # code_hash -> offer
        self.sessions: dict[str, Session] = {}  # token_hash -> session

    def prune(self) -> None:
        now = _now()
        # Pair offers
        for k in list(self.pair_offers.keys()):
            if self.pair_offers[k].expires_at <= now:
                del self.pair_offers[k]
        # Sessions
        for k in list(self.sessions.keys()):
            if self.sessions[k].expires_at <= now:
                del self.sessions[k]


@dataclass
class NodeConn:
    ws: WebSocket
    send_lock: asyncio.Lock
    pending: dict[str, asyncio.Future[dict]]


def create_app() -> FastAPI:
    app = FastAPI(title="ORA Relay (M2 MVP)", version="0.1.0")
    st = RelayState()

    max_msg_bytes = int((os.getenv("ORA_RELAY_MAX_MSG_BYTES") or "1048576").strip() or "1048576")
    max_http_body_bytes = int((os.getenv("ORA_RELAY_MAX_HTTP_BODY_BYTES") or "262144").strip() or "262144")
    session_ttl_sec = int((os.getenv("ORA_RELAY_SESSION_TTL_SEC") or "3600").strip() or "3600")
    pair_ttl_sec = int((os.getenv("ORA_RELAY_PAIR_TTL_SEC") or "120").strip() or "120")
    max_pending = int((os.getenv("ORA_RELAY_MAX_PENDING") or "64").strip() or "64")
    client_timeout_sec = float((os.getenv("ORA_RELAY_CLIENT_TIMEOUT_SEC") or "35").strip() or "35")

    enforce_https_origin = _parse_bool_env("ORA_RELAY_ENFORCE_ORIGIN", False)

    @app.get("/health")
    async def health() -> dict:
        st.prune()
        return {"ok": True, "nodes": len(st.nodes), "pairs": len(st.pair_offers), "sessions": len(st.sessions)}

    @app.post("/api/pair", response_model=PairResponse)
    async def api_pair(req: PairRequest) -> PairResponse:
        st.prune()
        code = (req.code or "").strip()
        if not code:
            raise HTTPException(status_code=400, detail="code required")
        offer = st.pair_offers.get(_hash_code(code))
        if not offer or offer.expires_at <= _now():
            raise HTTPException(status_code=403, detail="invalid or expired code")
        if offer.node_id not in st.nodes:
            raise HTTPException(status_code=503, detail="node not connected")

        token = secrets.token_urlsafe(32)
        token_hash = _hash_code(token)
        expires_at = _now() + max(60, min(24 * 3600, int(session_ttl_sec)))
        st.sessions[token_hash] = Session(token_hash=token_hash, node_id=offer.node_id, expires_at=expires_at)
        # One-time code: invalidate after use.
        try:
            del st.pair_offers[_hash_code(code)]
        except Exception:
            pass
        return PairResponse(ok=True, node_id=offer.node_id, token=token, expires_at=expires_at)

    async def _require_session(ws: WebSocket) -> Session:
        st.prune()
        token = (ws.query_params.get("token") or "").strip()
        if not token:
            # Allow passing via header too (e.g., browser).
            token = (ws.headers.get("authorization") or "").strip()
            if token.lower().startswith("bearer "):
                token = token.split(None, 1)[1].strip()
        if not token:
            await ws.close(code=4403)
            raise RuntimeError("missing token")
        sess = st.sessions.get(_hash_code(token))
        if not sess or sess.expires_at <= _now():
            await ws.close(code=4403)
            raise RuntimeError("invalid token")
        return sess

    @app.websocket("/ws/node")
    async def ws_node(ws: WebSocket, node_id: str) -> None:
        if not node_id:
            await ws.close(code=4400)
            return
        await ws.accept()
        conn = NodeConn(ws=ws, send_lock=asyncio.Lock(), pending={})
        st.nodes[node_id] = conn

        # Node must immediately send a "pair_offer" message to be pairable.
        try:
            while True:
                raw = await ws.receive_text()
                if raw is None:
                    break
                if len(raw.encode("utf-8", errors="ignore")) > max_msg_bytes:
                    await ws.send_text(json.dumps({"type": "error", "error": "message_too_large"}))
                    continue
                msg = _safe_json_loads(raw)
                mtype = str(msg.get("type") or "")

                if mtype == "pair_offer":
                    # payload: {"code": "..."} (plaintext only in-flight)
                    code = str(msg.get("code") or "").strip()
                    if not code:
                        await ws.send_text(json.dumps({"type": "pair_offer_ack", "ok": False, "error": "code_required"}))
                        continue
                    expires_at = _now() + max(30, min(600, int(pair_ttl_sec)))
                    offer = PairOffer(node_id=node_id, code_hash=_hash_code(code), expires_at=expires_at)
                    st.pair_offers[offer.code_hash] = offer
                    await ws.send_text(json.dumps({"type": "pair_offer_ack", "ok": True, "expires_at": expires_at}))
                    continue

                if mtype == "http_response":
                    req_id = str(msg.get("id") or "")
                    fut = conn.pending.pop(req_id, None)
                    if fut and (not fut.done()):
                        fut.set_result(msg)
                    continue

                if mtype == "pong":
                    continue

                # Unknown messages ignored to keep relay minimal.
                await ws.send_text(json.dumps({"type": "error", "error": "unknown_message_type"}))

        except WebSocketDisconnect:
            pass
        finally:
            # Fail any pending requests for this node.
            try:
                for _id, fut in list(conn.pending.items()):
                    if not fut.done():
                        fut.set_result({"type": "http_response", "id": _id, "error": "node_disconnected"})
                conn.pending.clear()
            except Exception:
                pass
            # Drop pair offers for this node (avoid stale pairing surface).
            try:
                for k, offer in list(st.pair_offers.items()):
                    if offer.node_id == node_id:
                        del st.pair_offers[k]
            except Exception:
                pass
            if st.nodes.get(node_id) is conn:
                del st.nodes[node_id]
            st.prune()

    @app.websocket("/ws/client")
    async def ws_client(ws: WebSocket) -> None:
        # Basic Origin enforcement toggle (for public deployments).
        if enforce_https_origin:
            origin = (ws.headers.get("origin") or "").strip().lower()
            if origin and (not origin.startswith("https://")):
                await ws.close(code=4403)
                return

        await ws.accept()
        try:
            sess = await _require_session(ws)
        except Exception:
            return

        node_id = sess.node_id
        try:
            while True:
                raw = await ws.receive_text()
                if raw is None:
                    break
                if len(raw.encode("utf-8", errors="ignore")) > max_msg_bytes:
                    await ws.send_text(json.dumps({"type": "error", "error": "message_too_large"}))
                    continue
                msg = _safe_json_loads(raw)
                mtype = str(msg.get("type") or "")
                req_id = str(msg.get("id") or "")

                if mtype == "ping":
                    await ws.send_text(json.dumps({"type": "pong", "ts": _now()}))
                    continue

                if mtype != "http_proxy":
                    await ws.send_text(json.dumps({"type": "error", "id": req_id, "error": "unknown_message_type"}))
                    continue

                node = st.nodes.get(node_id)
                if not node:
                    await ws.send_text(json.dumps({"type": "http_response", "id": req_id, "error": "node_not_connected"}))
                    continue

                # Forward to node. Do not log payload. Apply size limits.
                payload = dict(msg)
                if not req_id:
                    req_id = secrets.token_hex(8)
                    payload["id"] = req_id

                # Prevent id collisions (also protects node.pending from overwrite).
                if req_id in node.pending:
                    await ws.send_text(json.dumps({"type": "http_response", "id": req_id, "error": "id_in_use"}))
                    continue

                # Basic DoS guard: cap in-flight requests per node.
                if len(node.pending) >= max_pending:
                    await ws.send_text(json.dumps({"type": "http_response", "id": req_id, "error": "too_many_pending"}))
                    continue

                # Cap the body if present.
                body_b64 = payload.get("body_b64")
                if isinstance(body_b64, str) and body_b64:
                    try:
                        b = base64.b64decode(body_b64.encode("utf-8"), validate=False)
                        b = _limit_bytes(b, max_http_body_bytes)
                        payload["body_b64"] = base64.b64encode(b).decode("ascii")
                    except Exception:
                        payload["body_b64"] = ""

                loop = asyncio.get_running_loop()
                fut: asyncio.Future[dict] = loop.create_future()
                node.pending[req_id] = fut
                try:
                    async with node.send_lock:
                        await node.ws.send_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
                except Exception:
                    node.pending.pop(req_id, None)
                    await ws.send_text(json.dumps({"type": "http_response", "id": req_id, "error": "node_send_failed"}))
                    continue

                # Wait for response for this id (node supports mux; ws_client stays sequential for now).
                try:
                    resp = await asyncio.wait_for(fut, timeout=float(client_timeout_sec))
                except Exception:
                    node.pending.pop(req_id, None)
                    await ws.send_text(json.dumps({"type": "http_response", "id": req_id, "error": "timeout"}))
                    continue

                # Ensure pending is cleaned up even if Node responded but we failed to send to client.
                node.pending.pop(req_id, None)
                await ws.send_text(json.dumps(resp, ensure_ascii=False, separators=(",", ":")))

        except WebSocketDisconnect:
            pass
        finally:
            st.prune()

    return app


app = create_app()
