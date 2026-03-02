import logging
import sqlite3
import time

from fastapi.testclient import TestClient

from src.config import resolve_bot_db_path
from src.web.app import app


def _auth_headers(user_id: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer t",
        "x-ora-user-id": user_id,
    }


def test_files_owner_check_and_nostore_headers(monkeypatch):
    monkeypatch.setenv("ORA_WEB_API_TOKEN", "t")

    with TestClient(app) as client:
        create_resp = client.post(
            "/v1/files",
            headers=_auth_headers("owner1"),
            files={"file": ("hello.txt", b"hello world", "text/plain")},
        )
        assert create_resp.status_code == 200
        file_id = create_resp.json()["file_id"]

        download_resp = client.get(f"/v1/files/{file_id}/download", headers=_auth_headers("owner1"))
        assert download_resp.status_code == 200
        assert "no-store" in (download_resp.headers.get("Cache-Control") or "")
        assert "attachment" in (download_resp.headers.get("Content-Disposition") or "").lower()

        forbidden_resp = client.get(f"/v1/files/{file_id}/download", headers=_auth_headers("other-user"))
        assert forbidden_resp.status_code == 403


def test_files_expiry(monkeypatch):
    monkeypatch.setenv("ORA_WEB_API_TOKEN", "t")

    with TestClient(app) as client:
        create_resp = client.post(
            "/v1/files",
            headers=_auth_headers("expiry-user"),
            files={
                "file": ("exp.txt", b"expiring payload", "text/plain"),
                "expires_in_sec": (None, "1"),
            },
        )
        assert create_resp.status_code == 200
        file_id = create_resp.json()["file_id"]

        time.sleep(2)
        expired_resp = client.get(f"/v1/files/{file_id}/download", headers=_auth_headers("expiry-user"))
        assert expired_resp.status_code == 404


def test_share_token_is_hashed_and_not_logged(monkeypatch, caplog):
    monkeypatch.setenv("ORA_WEB_API_TOKEN", "t")
    monkeypatch.setenv("ORA_FILES_SHARE_ENABLED", "1")
    caplog.set_level(logging.INFO, logger="src.web.routers.files")

    with TestClient(app) as client:
        create_resp = client.post(
            "/v1/files",
            headers=_auth_headers("share-user"),
            files={"file": ("share.txt", b"share payload", "text/plain")},
        )
        assert create_resp.status_code == 200
        file_id = create_resp.json()["file_id"]

        share_resp = client.post(f"/v1/files/{file_id}/share", headers=_auth_headers("share-user"), json={})
        assert share_resp.status_code == 200
        share_token = share_resp.json()["share_token"]
        assert isinstance(share_token, str) and len(share_token) > 10

        shared_download = client.get(f"/s/{share_token}")
        assert shared_download.status_code == 200
        assert "no-store" in (shared_download.headers.get("Cache-Control") or "")

    assert share_token not in caplog.text

    conn = sqlite3.connect(resolve_bot_db_path())
    try:
        row = conn.execute(
            "SELECT token_hash FROM file_share_tokens WHERE file_id=? ORDER BY created_at DESC LIMIT 1",
            (file_id,),
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    token_hash = str(row[0])
    assert token_hash != share_token
    assert len(token_hash) == 64

