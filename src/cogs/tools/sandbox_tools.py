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
_GITHUB_API = "api.github.com"


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


async def _github_repo_metadata(session: aiohttp.ClientSession, rr: RepoRef) -> Dict[str, Any]:
    api_url = f"https://api.github.com/repos/{rr.owner}/{rr.repo}"
    headers = {"User-Agent": "ORA-Sandbox"}
    try:
        async with session.get(api_url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                return {"ok": False, "status": resp.status}
            data = await resp.json()
            # Keep a minimal subset to reduce PII/log risk.
            return {
                "ok": True,
                "status": resp.status,
                "full_name": data.get("full_name"),
                "description": data.get("description"),
                "default_branch": data.get("default_branch"),
                "stargazers_count": data.get("stargazers_count"),
                "forks_count": data.get("forks_count"),
                "open_issues_count": data.get("open_issues_count"),
                "archived": data.get("archived"),
                "license": (data.get("license") or {}).get("spdx_id") if isinstance(data.get("license"), dict) else None,
                "pushed_at": data.get("pushed_at"),
                "updated_at": data.get("updated_at"),
                "language": data.get("language"),
                "size_kb": data.get("size"),
            }
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}:{e}"}


async def _github_root_listing(session: aiohttp.ClientSession, rr: RepoRef, *, ref: str, max_entries: int) -> Dict[str, Any]:
    # Contents API: non-recursive listing of repo root.
    api_url = f"https://api.github.com/repos/{rr.owner}/{rr.repo}/contents/"
    headers = {"User-Agent": "ORA-Sandbox"}
    params = {"ref": ref} if ref else None
    try:
        async with session.get(api_url, headers=headers, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                return {"ok": False, "status": resp.status, "items": []}
            data = await resp.json()
            items = []
            if isinstance(data, list):
                for it in data[: max(0, int(max_entries or 0))]:
                    if not isinstance(it, dict):
                        continue
                    items.append(
                        {
                            "type": it.get("type"),
                            "name": it.get("name"),
                            "path": it.get("path"),
                            "size": it.get("size"),
                        }
                    )
            return {"ok": True, "status": resp.status, "items": items}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}:{e}", "items": []}


async def _github_readme(session: aiohttp.ClientSession, rr: RepoRef, *, ref: str, max_bytes: int) -> Dict[str, Any]:
    api_url = f"https://api.github.com/repos/{rr.owner}/{rr.repo}/readme"
    headers = {"User-Agent": "ORA-Sandbox"}
    params = {"ref": ref} if ref else None
    try:
        async with session.get(api_url, headers=headers, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                return {"ok": False, "status": resp.status, "text": ""}
            data = await resp.json()
            if not isinstance(data, dict):
                return {"ok": False, "status": resp.status, "text": ""}
            enc = (data.get("encoding") or "").lower()
            content = data.get("content")
            if enc != "base64" or not isinstance(content, str):
                return {"ok": False, "status": resp.status, "text": ""}
            import base64

            raw = base64.b64decode(content.encode("ascii"), validate=False)
            raw = raw[: max(0, int(max_bytes or 0))]
            try:
                text = raw.decode("utf-8", errors="ignore")
            except Exception:
                text = ""
            return {"ok": True, "status": resp.status, "text": text}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}:{e}", "text": ""}


def _fallback_enabled() -> bool:
    # Keep this on by default; it only does GitHub API reads and never executes code.
    return _is_truthy(os.getenv("ORA_SANDBOX_FALLBACK_ON_DOWNLOAD_FAIL", "1"))


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
        # Optional fallback: if ZIP download fails, fall back to GitHub API read-only inspection.
        # This keeps things useful while still avoiding code execution.
        if _fallback_enabled():
            try:
                if status_manager:
                    await status_manager.next_step("Sandbox: download failed, falling back to GitHub API (read-only)...")

                branch = rr.ref or await _github_default_branch(session, rr) or "main"
                max_root = int(os.getenv("ORA_SANDBOX_FALLBACK_ROOT_MAX_ENTRIES") or "200")
                max_readme = int(os.getenv("ORA_SANDBOX_FALLBACK_README_MAX_BYTES") or "200000")

                meta = await _github_repo_metadata(session, rr)
                root = await _github_root_listing(session, rr, ref=branch, max_entries=max_root)
                readme = await _github_readme(session, rr, ref=branch, max_bytes=max_readme)

                fallback = {
                    "mode": "github_api_read_only",
                    "download_error": f"{type(e).__name__}: {e}",
                    "ref_used": branch,
                    "repo_meta": meta,
                    "root_listing": root,
                    "readme": {"ok": readme.get("ok"), "status": readme.get("status"), "chars": len(readme.get('text') or '')},
                }
                try:
                    (sbx_dir / "fallback.json").write_text(json.dumps(fallback, ensure_ascii=True, indent=2), encoding="utf-8")
                    if isinstance(readme.get("text"), str) and readme["text"]:
                        (sbx_dir / "README_fallback.txt").write_text(readme["text"][:max_readme], encoding="utf-8", errors="ignore")
                except Exception:
                    pass

                lines = []
                lines.append("**Sandbox Fallback (GitHub API, read-only)**")
                lines.append(f"- repo: `{rr.owner}/{rr.repo}`" + (f" (ref: `{rr.ref}`)" if rr.ref else ""))
                lines.append(f"- reason: download failed -> fallback")
                lines.append(f"- error: `{type(e).__name__}`")
                if isinstance(meta, dict) and meta.get("ok"):
                    lines.append(f"- stars: {meta.get('stargazers_count')} | forks: {meta.get('forks_count')} | lang: {meta.get('language')}")
                    if meta.get("default_branch"):
                        lines.append(f"- default_branch: `{meta.get('default_branch')}` | using: `{branch}`")
                if isinstance(root, dict) and root.get("ok"):
                    items = root.get("items") or []
                    if items:
                        shown = ", ".join([str(it.get("name")) for it in items[:30] if isinstance(it, dict) and it.get("name")])
                        if shown:
                            lines.append(f"- root: {shown}" + (" ..." if len(items) > 30 else ""))
                if isinstance(readme, dict) and readme.get("ok") and readme.get("text"):
                    snippet = (readme["text"] or "").strip().splitlines()
                    snippet = snippet[:40]
                    if snippet:
                        lines.append("")
                        lines.append("```text")
                        lines.extend(snippet)
                        lines.append("```")

                lines.append("")
                lines.append("- note: fallback is read-only via GitHub API; no repo ZIP was downloaded; no code executed.")
                lines.append(f"- sandbox_id: `{sandbox_id}`")
                return {
                    "result": "\n".join(lines),
                    "sandbox_id": sandbox_id,
                    "repo": {"owner": rr.owner, "name": rr.repo, "ref": rr.ref},
                    "fallback_used": True,
                    "fallback": fallback,
                    "sandbox_uri": f"sandbox://{sandbox_id}/",
                }
            except Exception:
                # If fallback also fails, return original error (safe).
                pass
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
    # If at least one side fell back to read-only inspection, still produce a best-effort compare.
    if "summary" not in a or "summary" not in b:
        if a.get("fallback_used") or b.get("fallback_used"):
            lines = []
            lines.append("**Sandbox Repo Compare (best-effort)**")
            lines.append(f"- A: {a.get('repo')} | fallback={bool(a.get('fallback_used'))}")
            lines.append(f"- B: {b.get('repo')} | fallback={bool(b.get('fallback_used'))}")
            lines.append("")
            lines.append("- note: one side failed full ZIP download; used GitHub API read-only fallback.")
            lines.append("")
            lines.append("A:")
            lines.append(str(a.get("result") or "").strip()[:2000])
            lines.append("")
            lines.append("B:")
            lines.append(str(b.get("result") or "").strip()[:2000])
            return {"result": "\n".join(lines), "a": a, "b": b, "partial": True}
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
