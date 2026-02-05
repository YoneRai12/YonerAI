import html
import os
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from src.utils.temp_downloads import (
    cleanup_expired_downloads,
    get_download_file_path,
    get_download_manifest,
)

router = APIRouter(tags=["downloads"])


def _seconds_left(expires_at: int) -> int:
    return max(0, int(expires_at) - int(time.time()))


@router.get("/api/download/{token}/meta")
async def get_download_meta(token: str):
    cleanup_expired_downloads()
    manifest = get_download_manifest(token)
    if not manifest:
        raise HTTPException(status_code=404, detail="Download not found or expired.")

    return {
        "ok": True,
        "token": token,
        "download_name": manifest.get("download_name", "download.bin"),
        "size_bytes": int(manifest.get("size_bytes", 0)),
        "source_url": manifest.get("source_url", ""),
        "metadata": manifest.get("metadata", {}),
        "expires_at": int(manifest.get("expires_at", 0)),
        "seconds_left": _seconds_left(int(manifest.get("expires_at", 0))),
    }


@router.get("/download/{token}", response_class=HTMLResponse)
async def download_page(token: str):
    cleanup_expired_downloads()
    manifest = get_download_manifest(token)
    if not manifest:
        raise HTTPException(status_code=404, detail="Download not found or expired.")

    name = html.escape(str(manifest.get("download_name", "download.bin")))
    source_url = html.escape(str(manifest.get("source_url", "")))
    size_bytes = int(manifest.get("size_bytes", 0))
    size_mb = f"{size_bytes / (1024 * 1024):.1f}MB"
    seconds_left = _seconds_left(int(manifest.get("expires_at", 0)))

    source_line = (
        f'<p><strong>Source:</strong> <a href="{source_url}" target="_blank" rel="noreferrer">{source_url}</a></p>'
        if source_url
        else ""
    )

    html_body = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>ORA Temporary Download</title>
  <style>
    body {{
      margin: 0;
      font-family: "Segoe UI", sans-serif;
      background: #0f1218;
      color: #eef2ff;
      padding: 20px;
    }}
    .card {{
      max-width: 720px;
      margin: 0 auto;
      border: 1px solid #283245;
      background: #171d29;
      border-radius: 12px;
      padding: 20px;
    }}
    a.btn {{
      display: inline-block;
      margin-top: 12px;
      background: #2f6df6;
      color: #fff;
      text-decoration: none;
      padding: 10px 14px;
      border-radius: 8px;
      font-weight: 600;
    }}
    .muted {{
      color: #a9b6ce;
      font-size: 13px;
    }}
  </style>
</head>
<body>
  <div class="card">
    <h2>Temporary Download</h2>
    <p><strong>File:</strong> {name}</p>
    <p><strong>Size:</strong> {size_mb}</p>
    <p><strong>Expires in:</strong> {seconds_left} sec</p>
    {source_line}
    <a class="btn" href="/download/{token}/file">Download File</a>
    <p class="muted">This file is automatically deleted after 30 minutes.</p>
  </div>
</body>
</html>"""
    return HTMLResponse(content=html_body)


@router.get("/download/{token}/file")
async def download_file(token: str):
    cleanup_expired_downloads()
    manifest = get_download_manifest(token)
    if not manifest:
        raise HTTPException(status_code=404, detail="Download not found or expired.")

    fpath = get_download_file_path(token)
    if not fpath or not os.path.exists(fpath):
        raise HTTPException(status_code=404, detail="Download file missing.")

    name = str(manifest.get("download_name", "download.bin"))
    return FileResponse(
        fpath,
        filename=name,
        media_type="application/octet-stream",
    )
