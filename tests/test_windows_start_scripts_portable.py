from pathlib import Path
import re


SCRIPTS = [
    Path("scripts/start_ora_system.bat"),
    Path("scripts/start_web_only.bat"),
]


def _script_text(path: Path) -> str:
    return path.read_text(encoding="ascii", errors="ignore")


def test_start_scripts_have_no_legacy_l_drive_dependency():
    for script in SCRIPTS:
        content = _script_text(script)
        assert "L:\\" not in content, f"{script} still contains legacy L: drive references"


def test_start_scripts_use_python_module_uvicorn():
    for script in SCRIPTS:
        content = _script_text(script).lower()
        assert "uvicorn.exe" not in content, f"{script} should not call uvicorn.exe directly"
        assert "-m uvicorn" in content, f"{script} should launch uvicorn via python -m"


def test_start_scripts_use_npm_cmd():
    npm_run_direct = re.compile(r"(?i)(?<![\w.])npm\s+run\b")
    for script in SCRIPTS:
        content = _script_text(script)
        assert not npm_run_direct.search(content), f"{script} should use npm.cmd run, not npm run"
        assert "npm.cmd run" in content.lower(), f"{script} should contain npm.cmd run"
