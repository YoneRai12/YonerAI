from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ.setdefault("ORA_BOT_DB", "test_ora_web_install.db")

from src.web.app import app


ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = ROOT / "src" / "web" / "static"


def test_install_page_is_plain_command_text_and_points_to_github_release_assets():
    with TestClient(app) as client:
        response = client.get("/install")

    assert response.status_code == 200
    assert response.headers.get("content-type", "").startswith("text/plain")
    assert "https://github.com/YoneRai12/YonerAI/releases/latest/download/install.ps1" in response.text
    assert "<!doctype" not in response.text.lower()
    assert "<html" not in response.text.lower()
    assert "<style" not in response.text.lower()
    assert "class=" not in response.text.lower()
    assert "https://yonerai.com/install.ps1" not in response.text
    assert "https://yonerai.com/releases/latest/download" not in response.text
    assert "127.0.0.1" not in response.text
    assert "file://" not in response.text.lower()
    assert "C:\\" not in response.text
    assert "/Users/" not in response.text


def test_yonerai_com_does_not_serve_local_installer_artifact_paths():
    blocked_paths = [
        "/install.ps1",
        "/install.ps1.sha256",
        "/YonerAI-0.6.2.zip",
        "/manifest.v0.6.2.json",
        "/static/install.ps1",
        "/static/install.ps1.sha256",
        "/static/YonerAI-0.6.2.zip",
        "/static/manifest.v0.6.2.json",
    ]

    with TestClient(app) as client:
        for path in blocked_paths:
            response = client.get(path)
            assert response.status_code == 404, path
            assert "param(" not in response.text.lower(), path


def test_static_site_tree_contains_no_local_install_artifacts():
    forbidden: list[Path] = []
    for path in STATIC_ROOT.rglob("*"):
        if not path.is_file():
            continue
        name = path.name.lower()
        if name.endswith((".ps1", ".zip", ".sha256")):
            forbidden.append(path)
        elif name.startswith("manifest") and name.endswith(".json"):
            forbidden.append(path)

    assert forbidden == []


def teardown_module():
    try:
        if os.path.exists("test_ora_web_install.db"):
            os.remove("test_ora_web_install.db")
    except Exception:
        pass
