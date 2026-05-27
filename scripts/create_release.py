import argparse
import fnmatch
import subprocess
import sys
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile, ZipInfo


REPRODUCIBLE_ARCHIVE_MTIME = "2000-01-01T00:00:00Z"
REPRODUCIBLE_ARCHIVE_DATETIME = (2000, 1, 1, 0, 0, 0)


def _read_product_name(repo_root: Path) -> str:
    # Single source of truth for branding of release artifacts.
    # Keep default "ORA" for older checkouts that don't have PRODUCT_NAME.
    p = repo_root / "PRODUCT_NAME"
    try:
        name = p.read_text(encoding="utf-8", errors="ignore").strip()
    except Exception:
        name = ""
    return name or "ORA"


def _git_bytes(repo_root: Path, args: list[str]) -> bytes:
    return subprocess.run(
        ["git", *args],
        check=True,
        cwd=str(repo_root),
        capture_output=True,
    ).stdout


def _export_ignore_patterns(repo_root: Path) -> tuple[str, ...]:
    attributes = repo_root / ".gitattributes"
    try:
        lines = attributes.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return ()
    patterns: list[str] = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2 or "export-ignore" not in parts[1:]:
            continue
        patterns.append(parts[0].lstrip("/"))
    return tuple(patterns)


def _is_export_ignored(path: str, patterns: tuple[str, ...]) -> bool:
    normalized = path.replace("\\", "/")
    for pattern in patterns:
        if fnmatch.fnmatchcase(normalized, pattern):
            return True
        if "/" not in pattern and fnmatch.fnmatchcase(Path(normalized).name, pattern):
            return True
    return False


def _head_blobs(repo_root: Path) -> list[tuple[str, str, str]]:
    raw = _git_bytes(repo_root, ["ls-tree", "-rz", "-r", "HEAD"])
    blobs: list[tuple[str, str, str]] = []
    for entry in raw.split(b"\0"):
        if not entry:
            continue
        metadata, raw_path = entry.split(b"\t", 1)
        mode, object_type, object_id = metadata.decode("ascii").split()
        if object_type != "blob":
            continue
        path = raw_path.decode("utf-8")
        blobs.append((mode, object_id, path))
    return blobs


def _write_deterministic_zip(repo_root: Path, output_path: Path) -> None:
    ignored = _export_ignore_patterns(repo_root)
    with ZipFile(output_path, "w", compression=ZIP_STORED) as archive:
        for mode, object_id, path in _head_blobs(repo_root):
            if _is_export_ignored(path, ignored):
                continue
            data = _git_bytes(repo_root, ["cat-file", "blob", object_id])
            info = ZipInfo(path, date_time=REPRODUCIBLE_ARCHIVE_DATETIME)
            info.compress_type = ZIP_STORED
            info.create_system = 3
            info.external_attr = (int(mode, 8) & 0o777) << 16
            archive.writestr(info, data)


def create_release_zip(version):
    repo_root = Path(__file__).parent.parent
    product = _read_product_name(repo_root)
    zip_name = f"{product}-{version}.zip"
    output_path = repo_root / zip_name
    
    print(f"Creating release archive for version {version}...")
    
    try:
        # Build from tracked HEAD blobs instead of `git archive` so the release
        # asset hash is stable across Windows, macOS, and Ubuntu git/zlib builds.
        _write_deterministic_zip(repo_root, output_path)
        print(f"Created: {output_path}")
        return output_path
    except subprocess.CalledProcessError as e:
        print(f"Failed to create archive: {e}")
        return None


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a YonerAI release archive.")
    parser.add_argument("version", nargs="?", help="Release version. Falls back to VERSION file when omitted.")
    parser.add_argument(
        "--sign-release",
        action="store_true",
        help="Generate signed release manifest + provenance + signature sidecars.",
    )
    parser.add_argument(
        "--signing-private-key-env",
        default="ORA_DISTRIBUTION_RELEASE_PRIVATE_KEY",
        help="Environment variable that holds the base64 Ed25519 private key.",
    )
    parser.add_argument(
        "--capability-manifest",
        default="config/distribution/distribution_node_capabilities.json",
        help="Capability manifest path to bind into the signed release metadata.",
    )
    parser.add_argument(
        "--expires-in-hours",
        type=int,
        default=24,
        help="Signed metadata TTL in hours.",
    )
    parser.add_argument(
        "--metadata-dir",
        default=None,
        help="Output directory for signed metadata. Defaults to artifacts/releases/<version>/",
    )
    return parser


def _create_signed_metadata(
    *,
    repo_root: Path,
    artifact_path: Path,
    version: str,
    capability_manifest: Path,
    private_key_env: str,
    expires_in_hours: int,
    metadata_dir: Path,
) -> None:
    sys.path.insert(0, str(repo_root / "core" / "src"))
    from ora_core.distribution.release import build_signed_release_bundle

    private_key = (Path(private_key_env).read_text(encoding="utf-8").strip() if Path(private_key_env).exists() else "")
    if not private_key:
        import os

        private_key = str(os.getenv(private_key_env, "")).strip()
    if not private_key:
        raise SystemExit(f"Missing signing key in env/file: {private_key_env}")
    if not capability_manifest.exists():
        raise SystemExit(f"Capability manifest not found: {capability_manifest}")

    product = _read_product_name(repo_root)
    outputs = build_signed_release_bundle(
        artifact_path=artifact_path,
        version=version,
        product=product,
        capability_manifest_path=capability_manifest,
        private_key_b64=private_key,
        out_dir=metadata_dir,
        expires_in_hours=expires_in_hours,
    )
    print("Signed release metadata created:")
    for name, path in outputs.items():
        print(f"  {name}: {path}")


if __name__ == "__main__":
    parser = _build_arg_parser()
    args = parser.parse_args()

    if not args.version:
        version_file = Path(__file__).parent.parent / "VERSION"
        if version_file.exists():
            version = version_file.read_text().strip()
        else:
            parser.print_help()
            sys.exit(1)
    else:
        version = args.version

    artifact_path = create_release_zip(version)
    if not artifact_path:
        sys.exit(1)

    if args.sign_release:
        repo_root = Path(__file__).parent.parent
        capability_manifest = repo_root / args.capability_manifest
        metadata_dir = (
            Path(args.metadata_dir)
            if args.metadata_dir
            else repo_root / "artifacts" / "releases" / version
        )
        _create_signed_metadata(
            repo_root=repo_root,
            artifact_path=artifact_path,
            version=version,
            capability_manifest=capability_manifest,
            private_key_env=args.signing_private_key_env,
            expires_in_hours=args.expires_in_hours,
            metadata_dir=metadata_dir,
        )

    sys.exit(0)
