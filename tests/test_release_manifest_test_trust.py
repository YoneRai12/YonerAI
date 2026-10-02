from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CLI_SRC = ROOT / "clients" / "cli"
SIGNED_MANIFEST = ROOT / "releases" / "manifest.test-signed.json"
TEST_TRUST_FIXTURE = ROOT / "releases" / "test-trust.fixture.json"


def _prepare_paths() -> None:
    text = str(CLI_SRC)
    if text not in sys.path:
        sys.path.insert(0, text)


def _signed_manifest() -> dict[str, Any]:
    return json.loads(SIGNED_MANIFEST.read_text(encoding="utf-8"))


def _test_trust_fixture() -> dict[str, Any]:
    return json.loads(TEST_TRUST_FIXTURE.read_text(encoding="utf-8"))


def _write_json(tmp_path: Path, name: str, payload: dict[str, Any]) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_signed_manifest_verifies_with_non_production_test_trust_fixture() -> None:
    _prepare_paths()
    from yonerai_cli.release_manifest import load_manifest_file, load_test_trust_fixture, verify_manifest

    report = verify_manifest(
        load_manifest_file(str(SIGNED_MANIFEST)),
        test_trust_fixture=load_test_trust_fixture(str(TEST_TRUST_FIXTURE)),
    )

    assert report["contract_valid"] is True
    assert report["install_ready"] is False
    assert report["signature_state"] == "signed"
    assert report["signature_verified"] is True
    assert report["test_signature_verified"] is True
    assert report["production_signature_verified"] is False
    assert report["test_trust_fixture_used"] is True
    assert report["production_trust_material"] is False
    assert report["non_production_reason"] == "test_trust_fixture_not_production"
    assert report["signature_checks"] == [
        {
            "artifact_id": "yonerai-0.1.0-alpha.test.1-source-archive",
            "status": "verified",
            "key_id": "test-non-production-ed25519-2026-05-23",
            "algorithm": "ed25519",
            "trust_source": "non-production-test-fixture",
            "production_trust": False,
            "reason": None,
        }
    ]


def test_cli_manifest_verify_test_trust_json_is_network_free(monkeypatch, capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    def fail_urlopen(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("manifest test trust verification must not open network")

    monkeypatch.setattr(cli.urllib.request, "urlopen", fail_urlopen)

    assert cli.main(
        [
            "manifest",
            "verify",
            "releases/manifest.test-signed.json",
            "--test-trust-fixture",
            "releases/test-trust.fixture.json",
            "--json",
        ]
    ) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["signature_verified"] is True
    assert output["test_signature_verified"] is True
    assert output["production_signature_verified"] is False
    assert output["test_trust_fixture_used"] is True
    assert output["production_trust_material"] is False
    assert output["network_required"] is False


def test_cli_manifest_verify_test_trust_pretty_is_readable(capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    assert cli.main(
        [
            "manifest",
            "verify",
            "releases/manifest.test-signed.json",
            "--test-trust-fixture",
            "releases/test-trust.fixture.json",
            "--pretty",
            "--color",
            "never",
        ]
    ) == 0

    output = capsys.readouterr().out
    assert "YonerAI manifest verification" in output
    assert "test_trust_fixture_used" in output
    assert "production_trust_material: false" in output
    assert "Signature checks" in output
    assert "verified" in output
    assert "\033[" not in output


def test_cli_manifest_verify_test_trust_ja_pretty_keeps_signature_details(capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    assert cli.main(
        [
            "manifest",
            "verify",
            "releases/manifest.test-signed.json",
            "--test-trust-fixture",
            "releases/test-trust.fixture.json",
            "--pretty",
            "--lang",
            "ja",
            "--color",
            "never",
        ]
    ) == 0

    output = capsys.readouterr().out
    assert "YonerAI \u30de\u30cb\u30d5\u30a7\u30b9\u30c8\u691c\u8a3c" in output
    assert "\u5951\u7d04" in output
    assert "\u30bb\u30ad\u30e5\u30ea\u30c6\u30a3" in output
    assert not any(marker in output for marker in ("\ufffd", "\u7e5d", "\u87fe", "\u8b8c", "\u87f9"))
    assert "test_trust_fixture_used" in output
    assert "production_trust_material" in output
    assert "Signature checks" in output
    assert "verified" in output


def test_signed_manifest_without_test_trust_fixture_is_not_verified(capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    assert cli.main(["manifest", "verify", "releases/manifest.test-signed.json", "--json"]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["signature_state"] == "signed"
    assert output["signature_verified"] is False
    assert output["test_trust_fixture_used"] is False
    assert output["signature_checks"][0]["status"] == "skipped"
    assert output["signature_checks"][0]["trust_source"] is None
    assert output["signature_checks"][0]["reason"] == "test_trust_fixture_required"
    assert output["non_production_reason"] == "signature_not_verified"


def test_require_signed_rejects_unverified_signed_manifest(capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    exit_code = cli.main(["manifest", "verify", "releases/manifest.test-signed.json", "--require-signed", "--json"])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert output["contract_valid"] is False
    assert "manifest signature is not verified." in output["errors"]


def test_test_trust_fixture_rejects_production_trust_material(tmp_path, capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    fixture = _test_trust_fixture()
    fixture["production_trust"] = True
    fixture_path = _write_json(tmp_path, "production-trust.fixture.json", fixture)

    exit_code = cli.main(
        [
            "manifest",
            "verify",
            "releases/manifest.test-signed.json",
            "--test-trust-fixture",
            str(fixture_path),
            "--json",
        ]
    )

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert "test trust fixture must not contain production trust." in output["errors"]
    assert str(tmp_path) not in json.dumps(output)


def test_test_trust_fixture_rejects_remote_fixture_without_fetch(monkeypatch, capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    def fail_urlopen(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("remote test trust fixture must not be fetched")

    monkeypatch.setattr(cli.urllib.request, "urlopen", fail_urlopen)

    exit_code = cli.main(
        [
            "manifest",
            "verify",
            "releases/manifest.test-signed.json",
            "--test-trust-fixture",
            "https://example.invalid/test-trust.fixture.json",
            "--json",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "remote URLs are not fetched" in captured.err


def test_test_trust_fixture_rejects_unc_fixture_without_fetch(monkeypatch, capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    def fail_urlopen(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("UNC test trust fixture must not be fetched")

    monkeypatch.setattr(cli.urllib.request, "urlopen", fail_urlopen)

    exit_code = cli.main(
        [
            "manifest",
            "verify",
            "releases/manifest.test-signed.json",
            "--test-trust-fixture",
            "\\\\server\\share\\test-trust.fixture.json",
            "--json",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "remote paths are not fetched" in captured.err


def test_test_trust_verification_fails_closed_on_tampered_signed_manifest(tmp_path, capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    manifest = _signed_manifest()
    manifest["artifacts"][0]["size_bytes"] = 2
    manifest_path = _write_json(tmp_path, "tampered-manifest.json", manifest)

    exit_code = cli.main(
        [
            "manifest",
            "verify",
            str(manifest_path),
            "--test-trust-fixture",
            "releases/test-trust.fixture.json",
            "--json",
        ]
    )

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert output["signature_verified"] is False
    assert output["signature_checks"][0]["status"] == "failed"
    assert output["signature_checks"][0]["reason"] == "signature_invalid"
    assert str(tmp_path) not in json.dumps(output)
