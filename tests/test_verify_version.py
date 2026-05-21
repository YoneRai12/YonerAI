from __future__ import annotations

from scripts import verify_version


def test_semantic_prerelease_is_supported() -> None:
    ok, message = verify_version.verify_version_value("0.1.0-alpha.1")

    assert ok is True
    assert message == "[OK] VERSION is valid SemVer: 0.1.0-alpha.1"


def test_digit_prefixed_alphanumeric_prerelease_is_supported() -> None:
    for value in ("1.0.0-1a", "1.0.0-1-rc"):
        ok, message = verify_version.verify_version_value(value)

        assert ok is True
        assert message == f"[OK] VERSION is valid SemVer: {value}"


def test_four_digit_semver_major_falls_back_to_semver() -> None:
    for value in ("2026.13.1", "2026.0.0-alpha"):
        ok, message = verify_version.verify_version_value(value)

        assert ok is True
        assert message == f"[OK] VERSION is valid SemVer: {value}"


def test_v_prefixed_tag_matches_unprefixed_version() -> None:
    ok, message = verify_version.verify_version_value("0.1.0-alpha.1", "v0.1.0-alpha.1")

    assert ok is True
    assert message == "[OK] VERSION matches tag: 0.1.0-alpha.1"


def test_version_file_value_must_not_include_v_prefix() -> None:
    ok, message = verify_version.verify_version_value("v0.1.0-alpha.1")

    assert ok is False
    assert "not a supported version string" in message


def test_invalid_versions_are_rejected() -> None:
    for value in (
        "0.1",
        "0.1.0-",
        "0.1.0-alpha..1",
        "0.1.0-01",
        "01.1.0",
    ):
        ok, _message = verify_version.verify_version_value(value)
        assert ok is False, value


def test_date_version_remains_supported_but_date_suffix_checkpoint_does_not() -> None:
    ok, message = verify_version.verify_version_value("2026.5.21")
    assert ok is True
    assert message == "[OK] VERSION is valid DateVer: 2026.5.21"

    suffix_ok, suffix_message = verify_version.verify_version_value("2026.5.21.5")
    assert suffix_ok is False
    assert "not a supported version string" in suffix_message


def test_tag_mismatch_is_rejected() -> None:
    ok, message = verify_version.verify_version_value("0.1.0-alpha.1", "v0.1.0-alpha.2")

    assert ok is False
    assert message == "[FAIL] VERSION mismatch. VERSION=0.1.0-alpha.1 tag=0.1.0-alpha.2"
