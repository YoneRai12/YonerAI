from __future__ import annotations

import json
import os
import re
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

import aiohttp
import discord


_GITHUB_HOSTS = {"github.com", "www.github.com"}


@dataclass(frozen=True)
class RepoRef:
    owner: str
    repo: str
    ref: Optional[str] = None


def _is_truthy(v: str | None) -> bool:
    return str(v or "").strip().lower() in {"1", "true", "yes", "on"}


def _parse_github_repo_url(url: str) -> RepoRef:
    raw = (url or "").strip()
    if not raw:
        raise ValueError("url is required")
    if raw.endswith(".git"):
        raw = raw[:-4]
    u = urlparse(raw)
    if u.scheme not in {"http", "https"}:
        raise ValueError("only http/https URLs are supported")
    if (u.netloc or "").lower() not in _GITHUB_HOSTS:
        raise ValueError("only github.com URLs are supported")

    parts = [p for p in (u.path or "").split("/") if p]
    if len(parts) < 2:
        raise ValueError("invalid GitHub repo URL")
    owner, repo = parts[0], parts[1]

    ref: Optional[str] = None
    # Support: https://github.com/{owner}/{repo}/tree/{ref}
    if len(parts) >= 4 and parts[2] == "tree":
        ref = parts[3]

    return RepoRef(owner=owner, repo=repo, ref=ref)


async def _github_default_branch(session: aiohttp.ClientSession, rr: RepoRef) -> Optional[str]:
    api_url = f"https://api.github.com/repos/{rr.owner}/{rr.repo}"
    headers = {"User-Agent": "ORA-Sandbox"}
    try:
        async with session.get(api_url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            b = data.get("default_branch")
            return str(b) if b else None
    except Exception:
        return None


async def _download_to_file(
    session: aiohttp.ClientSession,
    url: str,
    *,
    dest_dir: Path,
    max_bytes: int,
) -> Path:
    headers = {"User-Agent": "ORA-Sandbox"}
    timeout = aiohttp.ClientTimeout(total=120)
    async with session.get(url, headers=headers, timeout=timeout) as resp:
        if resp.status != 200:
            raise RuntimeError(f"download_failed:status={resp.status}")

        fd, tmp_path = tempfile.mkstemp(prefix="ora_sandbox_", suffix=".zip", dir=str(dest_dir))
        os.close(fd)
        out = Path(tmp_path)
        total = 0
        try:
            with out.open("wb") as f:
                async for chunk in resp.content.iter_chunked(1024 * 128):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > max_bytes:
                        raise RuntimeError("download_failed:zip_too_large")
                    f.write(chunk)
            return out
        except Exception:
            try:
                out.unlink(missing_ok=True)  # py311+
            except Exception:
                pass
            raise


def _safe_extract_zip(zip_path: Path, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_root = dest_dir.resolve()

    with zipfile.ZipFile(zip_path) as zf:
        members = zf.infolist()
        if not members:
            raise RuntimeError("zip_empty")

        # Extract with traversal protection.
        for m in members:
            # zipfile uses forward slashes.
            name = m.filename
            if not name or name.endswith("/"):
                continue
            target = (dest_dir / name).resolve()
            if not str(target).startswith(str(dest_root) + os.sep):
                raise RuntimeError("zip_path_traversal_detected")
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(m, "r") as src, target.open("wb") as dst:
                dst.write(src.read())

    # GitHub zip normally has a single top-level dir.
    children = [p for p in dest_dir.iterdir() if p.is_dir()]
    if len(children) == 1:
        return children[0]
    return dest_dir


def _summarize_repo(root: Path, *, max_files: int = 25000) -> Dict[str, Any]:
    ignore_dirs = {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "dist",
        "build",
        "__pycache__",
        ".next",
        ".turbo",
        ".pytest_cache",
    }
    lang_by_ext = {
        ".py": "Python",
        ".js": "JavaScript",
        ".ts": "TypeScript",
        ".tsx": "TypeScript",
        ".jsx": "JavaScript",
        ".json": "JSON",
        ".yml": "YAML",
        ".yaml": "YAML",
        ".md": "Markdown",
        ".toml": "TOML",
        ".rs": "Rust",
        ".go": "Go",
        ".java": "Java",
        ".kt": "Kotlin",
        ".cs": "CSharp",
        ".cpp": "CPP",
        ".c": "C",
        ".h": "C",
        ".sh": "Shell",
        ".ps1": "PowerShell",
        ".bat": "Batch",
        ".sql": "SQL",
        ".html": "HTML",
        ".css": "CSS",
    }

    total_files = 0
    total_bytes = 0
    ext_counts: Dict[str, int] = {}
    lang_counts: Dict[str, int] = {}
    notable: Dict[str, bool] = {}
    suspicious_hits: Dict[str, int] = {}

    # Cheap "static" suspicious strings scan (no execution).
    suspicious_patterns = {
        "os.system": re.compile(r"\bos\.system\s*\("),
        "subprocess": re.compile(r"\bsubprocess\.(Popen|run|call)\b"),
        "eval/exec": re.compile(r"\b(eval|exec)\s*\("),
        "curl/wget": re.compile(r"\b(curl|wget)\b"),
        "powershell": re.compile(r"\bpowershell\b", re.IGNORECASE),
        "certutil": re.compile(r"\bcertutil\b", re.IGNORECASE),
        "rm -rf": re.compile(r"\brm\s+-rf\b"),
    }

    for p in root.rglob("*"):
        if total_files >= max_files:
            break
        if p.is_dir():
            # Skip ignored dirs by name.
            if p.name in ignore_dirs:
                # Prune by not recursing further: rglob can't prune easily; we just continue.
                continue
            continue
        # Skip files in ignored dirs (best-effort).
        if any(part in ignore_dirs for part in p.parts):
            continue

        total_files += 1
        try:
            size = p.stat().st_size
        except Exception:
            size = 0
        total_bytes += int(size or 0)

        ext = p.suffix.lower()
        ext_counts[ext] = ext_counts.get(ext, 0) + 1
        lang = lang_by_ext.get(ext)
        if lang:
            lang_counts[lang] = lang_counts.get(lang, 0) + 1

        name_low = p.name.lower()
        if name_low in {"requirements.txt", "pyproject.toml", "package.json", "pnpm-lock.yaml", "yarn.lock", "poetry.lock"}:
            notable[name_low] = True
        if name_low in {"dockerfile", "compose.yaml", "docker-compose.yml"}:
            notable[name_low] = True
        if name_low.endswith(".env") or name_low == ".env":
            notable[".env_present"] = True

        # Lightweight suspicious scan on small-ish text files
        if size and size <= 1_000_000:
            try:
                chunk = p.read_bytes()[:200_000]
                try:
                    text = chunk.decode("utf-8", errors="ignore")
                except Exception:
                    text = ""
                if text:
                    for label, pat in suspicious_patterns.items():
                        if pat.search(text):
                            suspicious_hits[label] = suspicious_hits.get(label, 0) + 1
            except Exception:
                pass

    # Sort top extensions/languages for display
    top_ext = sorted(ext_counts.items(), key=lambda kv: kv[1], reverse=True)[:12]
    top_lang = sorted(lang_counts.items(), key=lambda kv: kv[1], reverse=True)[:10]

    return {
        "total_files": total_files,
        "total_bytes": total_bytes,
        "top_extensions": top_ext,
        "top_languages": top_lang,
        "notable_files": sorted([k for k, v in notable.items() if v]),
        "suspicious_hits": dict(sorted(suspicious_hits.items(), key=lambda kv: kv[1], reverse=True)),
    }


def _fmt_bytes(n: int) -> str:
    n = int(n or 0)
    for unit in ["B", "KB", "MB", "GB"]:
        if n < 1024 or unit == "GB":
            return f"{n:.1f}{unit}" if unit != "B" else f"{n}{unit}"
        n /= 1024
    return f"{n:.1f}GB"


def _render_summary(title: str, rr: RepoRef, summary: Dict[str, Any]) -> str:
    lines = []
    lines.append(f"**{title}** `{rr.owner}/{rr.repo}`" + (f" (ref: `{rr.ref}`)" if rr.ref else ""))
    lines.append(f"- files: {summary.get('total_files')} | size: {_fmt_bytes(int(summary.get('total_bytes') or 0))}")
    tl = summary.get("top_languages") or []
    if tl:
        langs = ", ".join([f"{k}({v})" for k, v in tl[:6]])
        lines.append(f"- langs: {langs}")
    nf = summary.get("notable_files") or []
    if nf:
        lines.append(f"- notable: {', '.join(nf[:10])}")
    sh = summary.get("suspicious_hits") or {}
    if sh:
        hits = ", ".join([f"{k}({v})" for k, v in list(sh.items())[:6]])
        lines.append(f"- suspicious: {hits}")
    return "\n".join(lines)


async def download_repo(args: dict, message: discord.Message, status_manager, bot=None) -> Dict[str, Any]:
    """
    Safe-by-default: download GitHub repo ZIP into ORA temp sandbox and perform static inspection only.
    No code execution.
    """
    from src.config import Config, TEMP_DIR

    url = (args or {}).get("url") or (args or {}).get("repo_url")
    if not url:
        return {"result": "❌ url is required (GitHub repo URL)."}

    ref = (args or {}).get("ref")
    max_zip_bytes = int((args or {}).get("max_zip_bytes") or os.getenv("ORA_SANDBOX_MAX_ZIP_BYTES") or 50 * 1024 * 1024)
    keep = _is_truthy((args or {}).get("keep"))

    cfg = Config.load()
    base = Path(TEMP_DIR) / "sandboxes"
    base.mkdir(parents=True, exist_ok=True)
    sandbox_id = f"sbx_{int(time.time())}_{os.urandom(4).hex()}"
    sbx_dir = base / sandbox_id
    sbx_dir.mkdir(parents=True, exist_ok=True)

    try:
        rr = _parse_github_repo_url(str(url))
        if ref:
            rr = RepoRef(owner=rr.owner, repo=rr.repo, ref=str(ref))
    except Exception as e:
        return {"result": f"❌ invalid GitHub URL: {e}"}

    if status_manager:
        await status_manager.next_step("Sandbox: resolving repo ref...")

    session: aiohttp.ClientSession
    if bot is not None and hasattr(bot, "session") and isinstance(getattr(bot, "session"), aiohttp.ClientSession):
        session = bot.session
    else:
        session = aiohttp.ClientSession()

    created_own_session = session is not getattr(bot, "session", None)
    zip_path: Optional[Path] = None
    extracted_root: Optional[Path] = None
    try:
        branch = rr.ref
        if not branch:
            branch = await _github_default_branch(session, rr) or "main"

        candidate_urls = []
        if rr.ref:
            candidate_urls.append(f"https://codeload.github.com/{rr.owner}/{rr.repo}/zip/refs/heads/{rr.ref}")
            candidate_urls.append(f"https://codeload.github.com/{rr.owner}/{rr.repo}/zip/{rr.ref}")
        else:
            candidate_urls.append(f"https://codeload.github.com/{rr.owner}/{rr.repo}/zip/refs/heads/{branch}")
            if branch not in {"main", "master"}:
                candidate_urls.append(f"https://codeload.github.com/{rr.owner}/{rr.repo}/zip/refs/heads/main")
                candidate_urls.append(f"https://codeload.github.com/{rr.owner}/{rr.repo}/zip/refs/heads/master")

        last_err: Optional[Exception] = None
        if status_manager:
            await status_manager.next_step("Sandbox: downloading ZIP...")
        for u in candidate_urls:
            try:
                zip_path = await _download_to_file(session, u, dest_dir=sbx_dir, max_bytes=max_zip_bytes)
                break
            except Exception as e:
                last_err = e
                continue
        if not zip_path:
            raise RuntimeError(f"download_failed:{type(last_err).__name__ if last_err else 'unknown'}")

        if status_manager:
            await status_manager.next_step("Sandbox: extracting ZIP (safe)...")
        extracted_root = _safe_extract_zip(zip_path, sbx_dir / "repo")

        if status_manager:
            await status_manager.next_step("Sandbox: static scan...")
        summary = _summarize_repo(extracted_root)

        meta = {
            "sandbox_id": sandbox_id,
            "profile": getattr(cfg, "profile", None),
            "source_url": str(url),
            "owner": rr.owner,
            "repo": rr.repo,
            "ref": rr.ref,
            "downloaded_at": int(time.time()),
        }
        try:
            (sbx_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=True, indent=2), encoding="utf-8")
        except Exception:
            pass

        text = _render_summary("Sandbox Downloaded", rr, summary)
        text += "\n- note: static inspection only (no execution)."
        text += f"\n- sandbox_id: `{sandbox_id}`"

        return {
            "result": text,
            "sandbox_id": sandbox_id,
            "repo": {"owner": rr.owner, "name": rr.repo, "ref": rr.ref},
            "summary": summary,
            "sandbox_uri": f"sandbox://{sandbox_id}/",
        }
    except Exception as e:
        return {"result": f"❌ sandbox_download_failed: {type(e).__name__}: {e}"}
    finally:
        if created_own_session:
            try:
                await session.close()
            except Exception:
                pass
        if not keep:
            # Keep only extracted results? For now: keep everything by default unless keep=0.
            pass


async def compare_repos(args: dict, message: discord.Message, status_manager, bot=None) -> Dict[str, Any]:
    """
    Download 2 GitHub repos into sandboxes and compare high-level structure.
    Safe: no execution.
    """
    url_a = (args or {}).get("url_a") or (args or {}).get("a") or (args or {}).get("repo_a")
    url_b = (args or {}).get("url_b") or (args or {}).get("b") or (args or {}).get("repo_b")
    urls = (args or {}).get("urls")
    if (not url_a or not url_b) and isinstance(urls, list) and len(urls) >= 2:
        url_a, url_b = urls[0], urls[1]
    if not url_a or not url_b:
        return {"result": "❌ need url_a and url_b (or urls=[a,b])."}

    a = await download_repo({"url": url_a, "keep": True}, message, status_manager, bot=bot)
    b = await download_repo({"url": url_b, "keep": True}, message, status_manager, bot=bot)

    if not isinstance(a, dict) or not isinstance(b, dict):
        return {"result": "❌ compare failed: download step returned non-dict."}
    if "summary" not in a or "summary" not in b:
        return {"result": f"❌ compare failed:\nA: {a.get('result')}\nB: {b.get('result')}"}

    sa = a["summary"]
    sb = b["summary"]

    def _as_map(top_list):
        out = {}
        for k, v in (top_list or []):
            out[str(k)] = int(v)
        return out

    la = _as_map(sa.get("top_languages"))
    lb = _as_map(sb.get("top_languages"))
    all_langs = sorted(set(la) | set(lb))

    diff_lines = []
    diff_lines.append("**Sandbox Repo Compare (static)**")
    diff_lines.append(f"- A: {a.get('sandbox_uri')} {a.get('repo')}")
    diff_lines.append(f"- B: {b.get('sandbox_uri')} {b.get('repo')}")
    diff_lines.append("")
    diff_lines.append(f"- files: A={sa.get('total_files')} vs B={sb.get('total_files')}")
    diff_lines.append(f"- size:  A={_fmt_bytes(int(sa.get('total_bytes') or 0))} vs B={_fmt_bytes(int(sb.get('total_bytes') or 0))}")
    if all_langs:
        diff_lines.append("- langs (counts): " + ", ".join([f"{k}:A{la.get(k,0)}/B{lb.get(k,0)}" for k in all_langs[:10]]))
    return {
        "result": "\n".join(diff_lines),
        "a": a,
        "b": b,
    }
