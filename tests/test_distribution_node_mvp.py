from __future__ import annotations

import asyncio
import json
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

ROOT = Path(__file__).resolve().parents[1]
CORE_SRC = ROOT / "core" / "src"
if str(CORE_SRC) not in sys.path:
    sys.path.insert(0, str(CORE_SRC))

from ora_core.api.routes import messages as messages_route
from ora_core.api.dependencies.auth import get_current_user
from ora_core.database.models import Base
from ora_core.database.repo import Repository
from ora_core.database.session import get_db
from ora_core.distribution.capabilities import CapabilityManifest, CapabilityPolicy
from ora_core.distribution.files import normalize_tool_result_for_run
from ora_core.distribution.release import (
    ReleaseVerificationError,
    build_signed_release_bundle,
    generate_ed25519_keypair,
    verify_release_bundle,
)
from ora_core.distribution.runtime import DistributionRuntime, configure_current_runtime
from ora_core.engine.simple_worker import event_manager
from ora_core.main import create_app
from ora_core.mcp.runner import ToolRunner


async def _create_all(engine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def _build_distribution_env(monkeypatch, tmp_path: Path, *, version: str = "2026.4.10") -> dict[str, str]:
    capability_manifest = tmp_path / "distribution_node_capabilities.json"
    capability_manifest.write_text(
        json.dumps(
            {
                "schema_version": "yonerai-distribution-capabilities/v1",
                "profile": "distribution_node_mvp",
                "default_action": "deny",
                "capabilities": {
                    "run.submit_messages": True,
                    "run.read_events": True,
                    "run.submit_continuation_results": True,
                    "files.issue_download_ticket": True,
                    "files.download": True,
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    artifact_path = tmp_path / f"YonerAI-{version}.zip"
    artifact_path.write_bytes(b"distribution-node-mvp-artifact")

    private_key_b64, public_key_b64 = generate_ed25519_keypair()
    metadata_dir = tmp_path / "signed"
    signed = build_signed_release_bundle(
        artifact_path=artifact_path,
        version=version,
        product="YonerAI",
        capability_manifest_path=capability_manifest,
        private_key_b64=private_key_b64,
        out_dir=metadata_dir,
        expires_in_hours=24,
    )
    state_path = tmp_path / "distribution_state.json"

    env = {
        "ORA_DISTRIBUTION_NODE_ENABLE": "1",
        "ORA_DISTRIBUTION_CAPABILITY_MANIFEST": str(capability_manifest),
        "ORA_DISTRIBUTION_RELEASE_MANIFEST": str(signed["manifest_path"]),
        "ORA_DISTRIBUTION_RELEASE_PROVENANCE": str(signed["provenance_path"]),
        "ORA_DISTRIBUTION_RELEASE_SIGNATURE": str(signed["signature_path"]),
        "ORA_DISTRIBUTION_RELEASE_PUBLIC_KEY": public_key_b64,
        "ORA_DISTRIBUTION_RELEASE_ARTIFACT": str(artifact_path),
        "ORA_DISTRIBUTION_RELEASE_STATE": str(state_path),
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return env


def _auth_headers(
    provider: str,
    provider_id: str,
    *,
    display_name: str = "dist-user",
) -> dict[str, str]:
    return {
        "X-Test-Provider": provider,
        "X-Test-User-Id": provider_id,
        "X-Test-Display-Name": display_name,
    }


@pytest.fixture()
def distribution_app(monkeypatch, tmp_path: Path):
    env = _build_distribution_env(monkeypatch, tmp_path)
    db_path = tmp_path / "core_distribution.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    session_local = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    asyncio.run(_create_all(engine))

    app = create_app()

    async def override_get_db():
        async with session_local() as session:
            yield session

    async def override_get_current_user(request: Request):
        provider = request.headers.get("X-Test-Provider")
        provider_id = request.headers.get("X-Test-User-Id")
        if not provider or not provider_id:
            return None
        async with session_local() as session:
            repo = Repository(session)
            return await repo.get_or_create_user(
                provider=provider,
                provider_id=provider_id,
                display_name=request.headers.get("X-Test-Display-Name"),
            )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    yield {
        "app": app,
        "session_local": session_local,
        "env": env,
        "db_path": db_path,
    }

    asyncio.run(engine.dispose())
    configure_current_runtime(DistributionRuntime(enabled=False, capability_policy=CapabilityPolicy(enabled=False)))


def _default_message_payload(idempotency_key: str) -> dict:
    return {
        "conversation_id": None,
        "user_identity": {"provider": "web", "id": "dist-user-1", "display_name": "dist-user"},
        "content": "hello distribution node",
        "attachments": [],
        "idempotency_key": idempotency_key,
        "stream": True,
        "source": "web",
    }


def _read_sse_events(stream_response) -> list[dict]:
    events: list[dict] = []
    for line in stream_response.iter_lines():
        if not line:
            continue
        text = line.decode("utf-8") if isinstance(line, bytes) else str(line)
        if not text.startswith("data: "):
            continue
        events.append(json.loads(text[6:]))
    return events


def test_distribution_node_idempotency_replay_returns_same_run_id(distribution_app, monkeypatch) -> None:
    async def _fake_run_brain_task(*_args, **_kwargs):
        return None

    monkeypatch.setattr(messages_route, "run_brain_task", _fake_run_brain_task)

    payload = _default_message_payload("idem-dist-001")
    with TestClient(distribution_app["app"]) as client:
        first = client.post("/v1/messages", json=payload)
        second = client.post("/v1/messages", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["run_id"] == second.json()["run_id"]


def test_distribution_node_messages_auth_precedence_uses_authenticated_user_for_run_owner(
    distribution_app, monkeypatch
) -> None:
    async def _fake_run_brain_task(*_args, **_kwargs):
        return None

    monkeypatch.setattr(messages_route, "run_brain_task", _fake_run_brain_task)

    payload = _default_message_payload(f"auth-precedence-{uuid.uuid4().hex[:8]}")
    payload["user_identity"] = {
        "provider": "web",
        "id": "body-user-999",
        "display_name": "body-user",
    }
    
    async def _prepare_auth_user() -> str:
        async with distribution_app["session_local"]() as session:
            repo = Repository(session)
            auth_user = await repo.get_or_create_user("web", "auth-user-123", "auth-user")
            await session.commit()
            return auth_user.id

    auth_user_id = asyncio.run(_prepare_auth_user())

    auth_headers = _auth_headers("web", "auth-user-123", display_name="auth-user")

    with TestClient(distribution_app["app"]) as client:
        post = client.post("/v1/messages", json=payload, headers=auth_headers)

    run_id = post.json()["run_id"]

    async def _inspect() -> tuple[str | None, str]:
        async with distribution_app["session_local"]() as session:
            repo = Repository(session)
            run = await repo.get_run(run_id)
            body_user = await repo.get_or_create_user("web", "body-user-999", "body-user")
            return run.user_id, body_user.id

    run_user_id, body_user_id = asyncio.run(_inspect())

    assert post.status_code == 200
    assert run_user_id == auth_user_id
    assert run_user_id != body_user_id


def test_distribution_node_sse_ends_with_exactly_one_terminal_event(distribution_app, monkeypatch) -> None:
    async def _fake_run_brain_task(run_id: str, *_args, **_kwargs):
        await event_manager.emit(run_id, "progress", {"stage": "deliver", "pass": 1, "toc": []})
        await event_manager.emit(run_id, "final", {"output_text": "done"})
        await event_manager.emit(run_id, "final", {"output_text": "duplicate"})
        await event_manager.emit(run_id, "error", {"message": "ignored"})

    monkeypatch.setattr(messages_route, "run_brain_task", _fake_run_brain_task)

    payload = _default_message_payload(f"sse-{uuid.uuid4().hex[:8]}")
    with TestClient(distribution_app["app"]) as client:
        post = client.post("/v1/messages", json=payload)
        run_id = post.json()["run_id"]
        with client.stream(
            "GET",
            f"/v1/runs/{run_id}/events",
            headers=_auth_headers("web", "dist-user-1"),
        ) as stream:
            events = _read_sse_events(stream)

    terminal_events = [e for e in events if e.get("event") in {"final", "error"}]
    assert len(terminal_events) == 1
    assert terminal_events[0]["event"] == "final"
    assert events[-1]["event"] == "final"


def test_distribution_node_sse_unknown_event_does_not_block_terminal_event(
    distribution_app, monkeypatch
) -> None:
    async def _fake_run_brain_task(run_id: str, *_args, **_kwargs):
        await event_manager.emit(run_id, "future_extension_event", {"opaque": True})
        await event_manager.emit(run_id, "final", {"output_text": "done"})

    monkeypatch.setattr(messages_route, "run_brain_task", _fake_run_brain_task)

    payload = _default_message_payload(f"sse-unknown-{uuid.uuid4().hex[:8]}")
    with TestClient(distribution_app["app"]) as client:
        post = client.post("/v1/messages", json=payload)
        run_id = post.json()["run_id"]
        with client.stream(
            "GET",
            f"/v1/runs/{run_id}/events",
            headers=_auth_headers("web", "dist-user-1"),
        ) as stream:
            events = _read_sse_events(stream)

    terminal_events = [e for e in events if e.get("event") in {"final", "error"}]

    assert post.status_code == 200
    assert len(terminal_events) == 1
    assert terminal_events[0]["event"] == "final"
    assert events[-1]["event"] == "final"


def test_distribution_node_sse_reasoning_summary_public_safe_schema(
    distribution_app, monkeypatch
) -> None:
    async def _fake_run_brain_task(run_id: str, *_args, **_kwargs):
        await event_manager.emit(
            run_id,
            "reasoning_summary",
            {
                "summary": "safe summary",
                "details": {"safe_label": "not part of public schema"},
            },
        )
        await event_manager.emit(run_id, "final", {"output_text": "done"})

    monkeypatch.setattr(messages_route, "run_brain_task", _fake_run_brain_task)

    payload = _default_message_payload(f"sse-reasoning-schema-{uuid.uuid4().hex[:8]}")
    with TestClient(distribution_app["app"]) as client:
        post = client.post("/v1/messages", json=payload)
        run_id = post.json()["run_id"]
        with client.stream(
            "GET",
            f"/v1/runs/{run_id}/events",
            headers=_auth_headers("web", "dist-user-1"),
        ) as stream:
            events = _read_sse_events(stream)

    reasoning_events = [e for e in events if e.get("event") == "reasoning_summary"]

    assert post.status_code == 200
    assert len(reasoning_events) == 1
    assert reasoning_events[0] == {
        "event": "reasoning_summary",
        "data": {"summary": "safe summary"},
    }
    assert events[-1]["event"] == "final"


def test_event_manager_shapes_reasoning_summary_at_producer_boundary() -> None:
    async def _run() -> list[dict[str, Any]]:
        run_id = f"event-manager-reasoning-{uuid.uuid4().hex[:8]}"
        await event_manager.emit(
            run_id,
            "reasoning_summary",
            {
                "summary": "safe summary",
                "details": {"hidden": "drop"},
                "raw_prompt": "secret",
            },
        )
        await event_manager.emit(run_id, "final", {"output_text": "done"})
        events: list[dict[str, Any]] = []
        async for event in event_manager.listen(run_id):
            events.append(event)
        return events

    events = asyncio.run(_run())

    assert events[0] == {
        "event": "reasoning_summary",
        "data": {"summary": "safe summary"},
    }
    assert events[-1]["event"] == "final"


def test_event_manager_shapes_unusable_reasoning_summary_to_empty_payload() -> None:
    async def _run() -> list[dict[str, Any]]:
        run_id = f"event-manager-reasoning-empty-{uuid.uuid4().hex[:8]}"
        await event_manager.emit(
            run_id,
            "reasoning_summary",
            {
                "raw_chain_of_thought": "hidden reasoning",
                "hidden_routing_rationale": "internal route note",
            },
        )
        await event_manager.emit(run_id, "final", {"output_text": "done"})
        events: list[dict[str, Any]] = []
        async for event in event_manager.listen(run_id):
            events.append(event)
        return events

    events = asyncio.run(_run())

    assert events[0] == {"event": "reasoning_summary", "data": {}}
    assert events[-1]["event"] == "final"


def test_distribution_node_sse_meta_does_not_expose_forbidden_probe_fields(
    distribution_app, monkeypatch
) -> None:
    async def _fake_run_brain_task(run_id: str, *_args, **_kwargs):
        await event_manager.emit(
            run_id,
            "meta",
            {
                "state": "streaming",
                "raw_prompt": "secret prompt",
                "raw_chain_of_thought": "hidden reasoning",
                "operator_only_diagnostics": {"budget": 7},
                "private_admin_state": {"role": "owner"},
            },
        )
        await event_manager.emit(run_id, "final", {"output_text": "done"})

    monkeypatch.setattr(messages_route, "run_brain_task", _fake_run_brain_task)

    payload = _default_message_payload(f"sse-meta-{uuid.uuid4().hex[:8]}")
    with TestClient(distribution_app["app"]) as client:
        post = client.post("/v1/messages", json=payload)
        run_id = post.json()["run_id"]
        with client.stream(
            "GET",
            f"/v1/runs/{run_id}/events",
            headers=_auth_headers("web", "dist-user-1"),
        ) as stream:
            events = _read_sse_events(stream)

    meta_events = [e for e in events if e.get("event") == "meta"]
    meta_rendered = json.dumps(meta_events[0]["data"], ensure_ascii=False)

    assert post.status_code == 200
    assert len(meta_events) >= 1
    assert meta_events[0]["data"].get("state") == "streaming"
    assert "secret prompt" not in meta_rendered
    assert "hidden reasoning" not in meta_rendered
    assert "operator_only_diagnostics" not in meta_rendered
    assert "private_admin_state" not in meta_rendered
    assert events[-1]["event"] == "final"


def test_distribution_node_sse_reasoning_summary_strips_private_reasoning_fields(
    distribution_app, monkeypatch
) -> None:
    async def _fake_run_brain_task(run_id: str, *_args, **_kwargs):
        await event_manager.emit(
            run_id,
            "reasoning_summary",
            {
                "summary": "safe summary",
                "raw_chain_of_thought": "hidden reasoning",
                "raw_prompt": "secret prompt",
                "raw_prompts": ["secret prompt 2"],
                "hidden_route_rationale": "internal route reason",
                "hidden_routing_rationale": "internal routing note",
                "operator_only_diagnostics": {"budget": 7},
                "private_admin_state": {"role": "owner"},
                "details": {
                    "safe_label": "not part of public schema",
                    "raw_prompt": "nested secret prompt",
                    "raw_chain_of_thought": "nested hidden reasoning",
                },
            },
        )
        await event_manager.emit(run_id, "final", {"output_text": "done"})

    monkeypatch.setattr(messages_route, "run_brain_task", _fake_run_brain_task)

    payload = _default_message_payload(f"sse-reasoning-leak-{uuid.uuid4().hex[:8]}")
    with TestClient(distribution_app["app"]) as client:
        post = client.post("/v1/messages", json=payload)
        run_id = post.json()["run_id"]
        with client.stream(
            "GET",
            f"/v1/runs/{run_id}/events",
            headers=_auth_headers("web", "dist-user-1"),
        ) as stream:
            events = _read_sse_events(stream)

    reasoning_events = [e for e in events if e.get("event") == "reasoning_summary"]
    data = reasoning_events[0]["data"]
    reasoning_rendered = json.dumps(data, ensure_ascii=False)

    assert post.status_code == 200
    assert len(reasoning_events) == 1
    assert data == {"summary": "safe summary"}
    for forbidden in [
        "raw_chain_of_thought",
        "raw_prompt",
        "raw_prompts",
        "hidden_route_rationale",
        "hidden_routing_rationale",
        "operator_only_diagnostics",
        "private_admin_state",
        "hidden reasoning",
        "nested hidden reasoning",
        "secret prompt",
        "secret prompt 2",
        "nested secret prompt",
        "internal route reason",
        "internal routing note",
    ]:
        assert forbidden not in reasoning_rendered
    assert events[-1]["event"] == "final"


def test_distribution_node_results_accept_continuation_only(distribution_app) -> None:
    session_local = distribution_app["session_local"]

    async def _prepare() -> tuple[str, str]:
        async with session_local() as session:
            repo = Repository(session)
            user = await repo.get_or_create_user("web", "dist-user-2", "tester")
            conversation_id = await repo.resolve_conversation(user.id)
            _, run = await repo.create_user_message_and_run(
                conversation_id=conversation_id,
                user_id=user.id,
                content="continue",
                attachments=[],
                idempotency_key=f"tool-{uuid.uuid4().hex[:8]}",
            )
            await repo.get_or_create_tool_call("tc-dist-001", run.id, user.id, "echo_tool", {"text": "hi"})
            await event_manager.expect_tool_result(run.id, "tc-dist-001", "echo_tool")
            return run.id, user.id

    run_id, _user_id = asyncio.run(_prepare())

    with TestClient(distribution_app["app"]) as client:
        missing = client.post(
            f"/v1/runs/{run_id}/results",
            json={"tool": "echo_tool", "result": {"ok": True}},
            headers=_auth_headers("web", "dist-user-2", display_name="tester"),
        )
        accepted = client.post(
            f"/v1/runs/{run_id}/results",
            json={
                "tool": "echo_tool",
                "tool_call_id": "tc-dist-001",
                "result": {"ok": True},
            },
            headers=_auth_headers("web", "dist-user-2", display_name="tester"),
        )
        duplicate = client.post(
            f"/v1/runs/{run_id}/results",
            json={
                "tool": "echo_tool",
                "tool_call_id": "tc-dist-001",
                "result": {"ok": True},
            },
            headers=_auth_headers("web", "dist-user-2", display_name="tester"),
        )

    assert missing.status_code == 422
    assert accepted.status_code == 200
    assert accepted.json()["accepted"] is True
    assert accepted.json()["continuation_only"] is True
    assert duplicate.status_code == 200
    assert duplicate.json()["accepted"] is False
    assert duplicate.json()["duplicate"] is True

    asyncio.run(event_manager.emit(run_id, "final", {"output_text": "cleanup"}))


@pytest.mark.asyncio
async def test_distribution_node_files_are_refs_only_and_downloadable(distribution_app) -> None:
    session_local = distribution_app["session_local"]
    artifact_path = Path(distribution_app["db_path"]).parent / "artifact.txt"
    artifact_path.write_text("hello artifact", encoding="utf-8")

    async with session_local() as session:
        repo = Repository(session)
        user = await repo.get_or_create_user("web", "dist-user-files", "tester")
        normalized, artifact_ref, file_refs = await normalize_tool_result_for_run(
            repo,
            owner_user_id=user.id,
            run_id="run-files-001",
            tool_call_id="tc-files-001",
            result={
                "ok": True,
                "content": [{"type": "text", "text": "created file"}],
                "artifact_ref": str(artifact_path),
            },
        )

    assert artifact_ref and artifact_ref.startswith("fileref:")
    assert len(file_refs) == 1
    assert normalized["artifact_ref"] == artifact_ref
    assert str(artifact_path) not in json.dumps(normalized, ensure_ascii=False)

    with TestClient(distribution_app["app"]) as client:
        ticket = client.post(
            f"/v1/files/{file_refs[0]['file_id']}/download-url",
            json={},
            headers=_auth_headers("web", "dist-user-files", display_name="tester"),
        )
        download_url = ticket.json()["download_url"]
        download = client.get(download_url)

    assert ticket.status_code == 200
    assert download.status_code == 200
    assert download.text == "hello artifact"
    assert download.headers["cache-control"].startswith("no-store")


def test_distribution_node_release_verification_fails_closed(tmp_path: Path) -> None:
    capability_manifest = tmp_path / "capabilities.json"
    capability_manifest.write_text(
        json.dumps(
            {
                "schema_version": "yonerai-distribution-capabilities/v1",
                "profile": "distribution_node_mvp",
                "default_action": "deny",
                "capabilities": {"run.submit_messages": True},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    artifact_path = tmp_path / "artifact.zip"
    artifact_path.write_bytes(b"artifact-v1")
    private_key_b64, public_key_b64 = generate_ed25519_keypair()
    signed = build_signed_release_bundle(
        artifact_path=artifact_path,
        version="2026.4.10",
        product="YonerAI",
        capability_manifest_path=capability_manifest,
        private_key_b64=private_key_b64,
        out_dir=tmp_path / "signed",
        expires_in_hours=1,
    )

    ok = verify_release_bundle(
        manifest_path=signed["manifest_path"],
        provenance_path=signed["provenance_path"],
        signature_path=signed["signature_path"],
        public_key_b64=public_key_b64,
        capability_manifest_path=capability_manifest,
        artifact_path=artifact_path,
    )
    assert ok.manifest.version == "2026.4.10"

    artifact_path.write_bytes(b"artifact-v2")
    with pytest.raises(ReleaseVerificationError):
        verify_release_bundle(
            manifest_path=signed["manifest_path"],
            provenance_path=signed["provenance_path"],
            signature_path=signed["signature_path"],
            public_key_b64=public_key_b64,
            capability_manifest_path=capability_manifest,
            artifact_path=artifact_path,
        )

    artifact_path.write_bytes(b"artifact-v1")
    with pytest.raises(ReleaseVerificationError):
        verify_release_bundle(
            manifest_path=signed["manifest_path"],
            provenance_path=signed["provenance_path"],
            signature_path=signed["signature_path"],
            public_key_b64=public_key_b64,
            capability_manifest_path=capability_manifest,
            artifact_path=artifact_path,
            now=ok.manifest.expires_at,
        )

    with pytest.raises(ReleaseVerificationError):
        verify_release_bundle(
            manifest_path=signed["manifest_path"],
            provenance_path=signed["provenance_path"],
            signature_path=signed["signature_path"],
            public_key_b64=public_key_b64,
            capability_manifest_path=capability_manifest,
            artifact_path=artifact_path,
            trusted_version="2026.4.11",
        )


def test_distribution_node_rejects_non_deny_default_action(tmp_path: Path) -> None:
    capability_manifest = tmp_path / "capabilities.json"
    capability_manifest.write_text(
        json.dumps(
            {
                "schema_version": "yonerai-distribution-capabilities/v1",
                "profile": "distribution_node_mvp",
                "default_action": "allow",
                "capabilities": {"run.submit_messages": True},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    from ora_core.distribution.capabilities import CapabilityManifest

    with pytest.raises(RuntimeError):
        CapabilityManifest.from_path(capability_manifest)


def test_distribution_node_manifest_explicitly_denies_excluded_capabilities() -> None:
    manifest_path = ROOT / "config" / "distribution" / "distribution_node_capabilities.json"
    manifest = CapabilityManifest.from_path(manifest_path)

    assert manifest.default_action == "deny"
    assert manifest.capabilities["tools.arbitrary_shell"] is False
    assert manifest.capabilities["tools.arbitrary_sql"] is False
    assert manifest.capabilities["files.arbitrary_write"] is False
    assert manifest.capabilities["control_plane.high_risk"] is False


@pytest.mark.asyncio
async def test_distribution_node_rejects_undeclared_tool_capability(distribution_app, monkeypatch) -> None:
    emitted: list[dict] = []

    async def _fake_emit(run_id: str, event_type: str, data: dict):
        emitted.append({"run_id": run_id, "event": event_type, "data": data})

    monkeypatch.setattr(event_manager, "emit", _fake_emit)
    runner = ToolRunner(repo=SimpleNamespace())
    result = await runner.run_tool(
        tool_call_id="tc-undeclared",
        run_id="run-undeclared",
        user_id="dist-user-undeclared",
        tool_name="echo_tool",
        args={"text": "blocked"},
        client_type="web",
    )

    assert result["status"] == "failed"
    assert "declared capability" in str(result["error"])
    assert any(ev["event"] == "tool_error" for ev in emitted)


def test_distribution_node_rejects_unauthenticated_file_ticket(distribution_app) -> None:
    session_local = distribution_app["session_local"]

    async def _prepare() -> str:
        async with session_local() as session:
            repo = Repository(session)
            user = await repo.get_or_create_user("web", "dist-user-authz", "tester")
            file_record = await repo.create_distribution_file(
                owner_user_id=user.id,
                run_id=None,
                tool_call_id=None,
                storage_path=str(Path(distribution_app["db_path"]).parent / "authz.txt"),
                display_name="authz.txt",
                media_type="text/plain",
            )
            return file_record.id

    artifact_path = Path(distribution_app["db_path"]).parent / "authz.txt"
    artifact_path.write_text("authz", encoding="utf-8")
    file_id = asyncio.run(_prepare())

    with TestClient(distribution_app["app"]) as client:
        res = client.post(f"/v1/files/{file_id}/download-url", json={})

    assert res.status_code == 401


def test_distribution_node_rejects_unauthenticated_run_events(distribution_app, monkeypatch) -> None:
    async def _fake_run_brain_task(*_args, **_kwargs):
        return None

    monkeypatch.setattr(messages_route, "run_brain_task", _fake_run_brain_task)
    payload = _default_message_payload(f"sse-auth-{uuid.uuid4().hex[:8]}")

    with TestClient(distribution_app["app"]) as client:
        post = client.post("/v1/messages", json=payload)
        run_id = post.json()["run_id"]
        res = client.get(f"/v1/runs/{run_id}/events")

    assert res.status_code == 401


def test_distribution_node_rejects_unauthenticated_run_results(distribution_app) -> None:
    session_local = distribution_app["session_local"]

    async def _prepare() -> str:
        async with session_local() as session:
            repo = Repository(session)
            user = await repo.get_or_create_user("web", "dist-user-results-authz", "tester")
            conversation_id = await repo.resolve_conversation(user.id)
            _, run = await repo.create_user_message_and_run(
                conversation_id=conversation_id,
                user_id=user.id,
                content="continue",
                attachments=[],
                idempotency_key=f"tool-authz-{uuid.uuid4().hex[:8]}",
            )
            await repo.get_or_create_tool_call("tc-dist-authz-001", run.id, user.id, "echo_tool", {"text": "hi"})
            await event_manager.expect_tool_result(run.id, "tc-dist-authz-001", "echo_tool")
            return run.id

    run_id = asyncio.run(_prepare())

    with TestClient(distribution_app["app"]) as client:
        res = client.post(
            f"/v1/runs/{run_id}/results",
            json={
                "tool": "echo_tool",
                "tool_call_id": "tc-dist-authz-001",
                "result": {"ok": True},
            },
        )

    assert res.status_code == 401
