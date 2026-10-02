from __future__ import annotations

import importlib
import sys
from pathlib import Path

from fastapi.testclient import TestClient


def test_public_core_health_smoke(monkeypatch, tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    core_src = repo_root / "core" / "src"
    if str(core_src) not in sys.path:
        sys.path.insert(0, str(core_src))

    monkeypatch.setenv("ORA_ALLOW_MISSING_SECRETS", "1")
    monkeypatch.setenv("ORA_BOT_DB", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("ORA_DOTENV_PATH", str(tmp_path / "missing.env"))
    monkeypatch.delenv("ORA_CORE_API_TOKEN", raising=False)

    sys.modules.pop("ora_core.main", None)
    main_mod = importlib.import_module("ora_core.main")

    assert main_mod.ENV_PATH is None

    with TestClient(main_mod.app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["ok"] is True
