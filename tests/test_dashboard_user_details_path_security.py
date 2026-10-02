import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import src.config as config
from src.web.app import app
from src.web.endpoints import (
    _dashboard_user_profile_dirs,
    _parse_dashboard_user_profile_id,
    _safe_dashboard_user_profile_path,
)


def _auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-token"}


def test_dashboard_user_details_reads_only_numeric_profile_ids(monkeypatch, tmp_path):
    memory_dir = tmp_path / "memory"
    users_dir = memory_dir / "users"
    users_dir.mkdir(parents=True)
    (users_dir / "123_456_public.json").write_text(
        json.dumps({"discord_user_id": "123", "guild_id": "456", "traits": ["public"]}),
        encoding="utf-8",
    )
    (users_dir / "123.json").write_text(json.dumps({"discord_user_id": "123"}), encoding="utf-8")

    monkeypatch.setattr(config, "MEMORY_DIR", str(memory_dir))
    monkeypatch.setenv("ORA_WEB_API_TOKEN", "test-token")

    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        response = client.get("/api/dashboard/users/123_456", headers=_auth_headers())

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["data"]["specific"]["guild_id"] == "456"
    assert body["data"]["general"]["discord_user_id"] == "123"


def test_dashboard_user_details_supports_memory_dir_that_points_to_users(monkeypatch, tmp_path):
    users_dir = tmp_path / "users"
    users_dir.mkdir()
    (users_dir / "321.json").write_text(json.dumps({"discord_user_id": "321"}), encoding="utf-8")

    monkeypatch.setattr(config, "MEMORY_DIR", str(users_dir))
    monkeypatch.setenv("ORA_WEB_API_TOKEN", "test-token")

    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        response = client.get("/api/dashboard/users/321", headers=_auth_headers())

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["data"]["general"]["discord_user_id"] == "321"


def test_dashboard_user_details_accepts_profile_suffix_from_user_list(monkeypatch, tmp_path):
    memory_dir = tmp_path / "memory"
    users_dir = memory_dir / "users"
    users_dir.mkdir(parents=True)
    (users_dir / "123_456_public.json").write_text(
        json.dumps({"discord_user_id": "123", "guild_id": "456", "source": "public"}),
        encoding="utf-8",
    )

    monkeypatch.setattr(config, "MEMORY_DIR", str(memory_dir))
    monkeypatch.setenv("ORA_WEB_API_TOKEN", "test-token")

    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        response = client.get("/api/dashboard/users/123_456_public", headers=_auth_headers())

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["data"]["specific"]["source"] == "public"


@pytest.mark.parametrize("user_id", ["abc", "123_abc", "123_456_789", "123_.."])
def test_dashboard_user_details_rejects_non_numeric_profile_ids(monkeypatch, tmp_path, user_id):
    memory_dir = tmp_path / "memory"
    (memory_dir / "users").mkdir(parents=True)

    monkeypatch.setattr(config, "MEMORY_DIR", str(memory_dir))
    monkeypatch.setenv("ORA_WEB_API_TOKEN", "test-token")

    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        response = client.get(f"/api/dashboard/users/{user_id}", headers=_auth_headers())

    assert response.status_code == 200
    assert response.json() == {"ok": False, "error": "Invalid user profile id"}


def test_safe_dashboard_user_profile_path_rejects_escape_attempts(tmp_path):
    users_dir = tmp_path / "memory" / "users"
    users_dir.mkdir(parents=True)

    safe_path = _safe_dashboard_user_profile_path(users_dir, "123.json")
    assert safe_path == users_dir.resolve() / "123.json"

    with pytest.raises(ValueError):
        _safe_dashboard_user_profile_path(users_dir, "../123.json")

    outside = tmp_path / "outside.json"
    with pytest.raises(ValueError):
        _safe_dashboard_user_profile_path(users_dir, str(outside))


def test_dashboard_user_profile_dirs_preserves_legacy_users_dir_input(tmp_path):
    memory_root = tmp_path / "memory"
    users_dir = tmp_path / "users"

    assert _dashboard_user_profile_dirs(memory_root) == [memory_root / "users", memory_root]
    assert _dashboard_user_profile_dirs(users_dir) == [users_dir]


def test_parse_dashboard_user_profile_id_accepts_safe_public_private_suffixes():
    assert _parse_dashboard_user_profile_id("123") == ("123", None)
    assert _parse_dashboard_user_profile_id("123_456") == ("123", "456")
    assert _parse_dashboard_user_profile_id("123_456_public") == ("123", "456")
    assert _parse_dashboard_user_profile_id("123_456_private") == ("123", "456")

    with pytest.raises(ValueError):
        _parse_dashboard_user_profile_id("123_456_public_extra")
