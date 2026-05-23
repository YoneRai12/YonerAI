from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "releases" / "manifest.schema.json"
EXAMPLE_PATH = ROOT / "releases" / "manifest.example.json"


def _load_manifest() -> dict[str, object]:
    return json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))


def _load_schema() -> dict[str, object]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _enum(schema: dict[str, object], *path: str) -> set[str]:
    current: object = schema
    for key in path:
        assert isinstance(current, dict)
        current = current[key]
    assert isinstance(current, list)
    return set(str(item) for item in current)


def _pattern(schema: dict[str, object], *path: str) -> re.Pattern[str]:
    current: object = schema
    for key in path:
        assert isinstance(current, dict)
        current = current[key]
    assert isinstance(current, str)
    return re.compile(current)


def _validate_manifest_contract(manifest: dict[str, object]) -> None:
    schema = _load_schema()
    required = set(schema["required"])
    missing = sorted(required - set(manifest))
    assert not missing, f"missing top-level fields: {missing}"

    assert manifest["schema_version"] == schema["properties"]["schema_version"]["const"]
    assert manifest["product"] == "YonerAI"
    assert manifest["channel"] in _enum(schema, "properties", "channel", "enum")
    assert _pattern(schema, "properties", "version", "pattern").match(str(manifest["version"]))
    assert isinstance(manifest["production_ready"], bool)

    release = manifest["release"]
    assert isinstance(release, dict)
    assert release["manifest_status"] in _enum(schema, "properties", "release", "properties", "manifest_status", "enum")
    assert _pattern(schema, "properties", "release", "properties", "tag", "pattern").match(str(release["tag"]))

    minimum = manifest["minimum_requirements"]
    assert isinstance(minimum, dict)
    assert isinstance(minimum["network_required"], bool)

    artifacts = manifest["artifacts"]
    assert isinstance(artifacts, list) and artifacts
    artifact_schema = schema["properties"]["artifacts"]["items"]
    assert isinstance(artifact_schema, dict)
    artifact_required = set(artifact_schema["required"])
    for artifact in artifacts:
        assert isinstance(artifact, dict)
        missing_artifact_fields = sorted(artifact_required - set(artifact))
        assert not missing_artifact_fields, f"missing artifact fields: {missing_artifact_fields}"
        assert artifact["kind"] in _enum(artifact_schema, "properties", "kind", "enum")
        assert artifact["target"] in _enum(artifact_schema, "properties", "target", "enum")
        assert artifact["os"] in _enum(artifact_schema, "properties", "os", "enum")
        assert artifact["arch"] in _enum(artifact_schema, "properties", "arch", "enum")
        assert _pattern(artifact_schema, "properties", "url", "pattern").match(str(artifact["url"]))
        assert _pattern(artifact_schema, "properties", "sha256", "pattern").match(str(artifact["sha256"]))
        assert isinstance(artifact["size_bytes"], int) and artifact["size_bytes"] > 0

        signature = artifact["signature"]
        assert isinstance(signature, dict)
        assert signature["status"] in _enum(artifact_schema, "properties", "signature", "properties", "status", "enum")
        if signature["status"] == "placeholder_non_production":
            assert manifest["production_ready"] is False
            assert signature["algorithm"] == "none"


def test_example_manifest_validates_against_schema_contract() -> None:
    _validate_manifest_contract(_load_manifest())


def test_semver_patterns_reject_malformed_numeric_identifiers() -> None:
    schema = _load_schema()
    version_pattern = _pattern(schema, "properties", "version", "pattern")
    tag_pattern = _pattern(schema, "properties", "release", "properties", "tag", "pattern")

    assert version_pattern.match("1.0.0-alpha.1")
    assert tag_pattern.match("v1.0.0-alpha.1")
    assert not version_pattern.match("01.2.3")
    assert not tag_pattern.match("v01.2.3")
    assert not version_pattern.match("1.0.0-alpha.01")
    assert not tag_pattern.match("v1.0.0-alpha.01")
    assert not version_pattern.match("1.0.0-alpha..1")
    assert not tag_pattern.match("v1.0.0-alpha..1")


def test_cli_manifest_validator_rejects_malformed_semver() -> None:
    import sys

    cli_src = ROOT / "clients" / "cli"
    if str(cli_src) not in sys.path:
        sys.path.insert(0, str(cli_src))
    from yonerai_cli.release_manifest import verify_manifest

    manifest = _load_manifest()
    manifest["version"] = "01.2.3"
    release = manifest["release"]
    assert isinstance(release, dict)
    release["tag"] = "v01.2.3"

    report = verify_manifest(manifest)

    assert report["contract_valid"] is False
    assert "version is invalid." in report["errors"]
    assert "release tag is invalid." in report["errors"]


def test_cli_manifest_validator_rejects_overlong_semver() -> None:
    import sys

    cli_src = ROOT / "clients" / "cli"
    if str(cli_src) not in sys.path:
        sys.path.insert(0, str(cli_src))
    from yonerai_cli.release_manifest import verify_manifest

    manifest = _load_manifest()
    overlong_version = "1.0.0-" + ("a" * 300)
    manifest["version"] = overlong_version
    release = manifest["release"]
    assert isinstance(release, dict)
    release["tag"] = f"v{overlong_version}"

    report = verify_manifest(manifest)

    assert report["contract_valid"] is False
    assert "version is invalid." in report["errors"]
    assert "release tag is invalid." in report["errors"]


def test_cli_manifest_validator_accepts_example_contract() -> None:
    import sys

    cli_src = ROOT / "clients" / "cli"
    if str(cli_src) not in sys.path:
        sys.path.insert(0, str(cli_src))
    from yonerai_cli.release_manifest import load_manifest_file, verify_manifest

    report = verify_manifest(load_manifest_file(str(EXAMPLE_PATH)))

    assert report["contract_valid"] is True
    assert report["install_ready"] is False
    assert report["signature_state"] == "placeholder_non_production"


def test_release_artifact_filename_policy_accepts_example_archive() -> None:
    import sys

    cli_src = ROOT / "clients" / "cli"
    if str(cli_src) not in sys.path:
        sys.path.insert(0, str(cli_src))
    from yonerai_cli.release_manifest import expected_artifact_filename, verify_manifest

    manifest = _load_manifest()
    artifact = manifest["artifacts"][0]
    assert isinstance(artifact, dict)

    assert expected_artifact_filename(artifact, str(manifest["version"])) == "YonerAI-0.1.0-alpha.1.zip"
    assert verify_manifest(manifest)["contract_valid"] is True


def test_release_artifact_filename_policy_rejects_mutable_source_name() -> None:
    import sys

    cli_src = ROOT / "clients" / "cli"
    if str(cli_src) not in sys.path:
        sys.path.insert(0, str(cli_src))
    from yonerai_cli.release_manifest import verify_manifest

    manifest = _load_manifest()
    artifact = deepcopy(manifest["artifacts"][0])
    assert isinstance(artifact, dict)
    artifact["url"] = "https://github.com/YoneRai12/YonerAI/releases/download/v0.1.0-alpha.1/YonerAI-latest.zip"
    manifest["artifacts"] = [artifact]

    report = verify_manifest(manifest)

    assert report["contract_valid"] is False
    assert "artifact 0 filename must be YonerAI-0.1.0-alpha.1.zip." in report["errors"]


def test_release_artifact_filename_policy_accepts_manifest_asset_name() -> None:
    import sys

    cli_src = ROOT / "clients" / "cli"
    if str(cli_src) not in sys.path:
        sys.path.insert(0, str(cli_src))
    from yonerai_cli.release_manifest import verify_manifest

    manifest = _load_manifest()
    artifact = deepcopy(manifest["artifacts"][0])
    assert isinstance(artifact, dict)
    artifact.update(
        {
            "id": "yonerai-0.1.0-alpha.1-manifest",
            "kind": "manifest",
            "target": "universal-any",
            "os": "any",
            "arch": "universal",
            "url": "https://github.com/YoneRai12/YonerAI/releases/download/v0.1.0-alpha.1/YonerAI-0.1.0-alpha.1-manifest.json",
        }
    )
    manifest["artifacts"] = [artifact]

    report = verify_manifest(manifest)

    assert report["contract_valid"] is True
    assert report["install_ready"] is False
    assert report["signature_state"] == "placeholder_non_production"


def test_empty_artifact_list_is_rejected_by_cli_validator() -> None:
    import sys

    cli_src = ROOT / "clients" / "cli"
    if str(cli_src) not in sys.path:
        sys.path.insert(0, str(cli_src))
    from yonerai_cli.release_manifest import verify_manifest

    manifest = _load_manifest()
    manifest["artifacts"] = []

    report = verify_manifest(manifest)

    assert report["contract_valid"] is False
    assert "artifacts must be a non-empty array." in report["errors"]


def test_missing_sha256_is_rejected() -> None:
    manifest = _load_manifest()
    artifact = deepcopy(manifest["artifacts"][0])
    assert isinstance(artifact, dict)
    artifact.pop("sha256")
    manifest["artifacts"] = [artifact]

    try:
        _validate_manifest_contract(manifest)
    except AssertionError as exc:
        assert "missing artifact fields" in str(exc)
    else:
        raise AssertionError("missing sha256 was accepted")


def test_invalid_channel_is_rejected() -> None:
    manifest = _load_manifest()
    manifest["channel"] = "production"

    try:
        _validate_manifest_contract(manifest)
    except AssertionError:
        return
    raise AssertionError("invalid channel was accepted")


def test_invalid_artifact_target_is_rejected() -> None:
    manifest = _load_manifest()
    artifact = deepcopy(manifest["artifacts"][0])
    assert isinstance(artifact, dict)
    artifact["target"] = "oracle-prod"
    manifest["artifacts"] = [artifact]

    try:
        _validate_manifest_contract(manifest)
    except AssertionError:
        return
    raise AssertionError("invalid artifact target was accepted")


def test_placeholder_signature_requires_non_production_manifest() -> None:
    manifest = _load_manifest()
    manifest["production_ready"] = True

    try:
        _validate_manifest_contract(manifest)
    except AssertionError:
        return
    raise AssertionError("production manifest accepted placeholder signature")


def test_installer_foundation_adds_no_network_executing_script() -> None:
    docs = (ROOT / "docs" / "tasks" / "installer-distribution.md").read_text(encoding="utf-8")
    lower_docs = docs.lower()

    assert "install/windows.ps1" in docs
    assert "no `irm ... | iex`" in lower_docs
    assert "download-and-execute" in lower_docs
    assert not (ROOT / "install" / "windows.ps1").exists()
