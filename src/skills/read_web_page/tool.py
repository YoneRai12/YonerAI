
import html as html_lib
import logging
import re
import urllib.parse

import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for script in soup(["script", "style", "noscript"]):
        script.decompose()
    text = soup.get_text(separator="\n")
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    return "\n".join(chunk for chunk in chunks if chunk)


def _truncate(text: str, limit: int = 6000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...(Content Truncated)..."


def _is_x_status(url: str) -> bool:
    try:
        u = urllib.parse.urlparse(url)
        host = (u.hostname or "").lower()
        if host not in {"x.com", "twitter.com", "www.x.com", "www.twitter.com"}:
            return False
        return "/status/" in (u.path or "")
    except Exception:
        return False


async def _fetch_x_oembed(session: aiohttp.ClientSession, url: str) -> tuple[bool, str]:
    """
    X/Twitter pages often block bots or require JS. oEmbed is the most reliable no-key path
    for extracting tweet text.
    """
    try:
        q = urllib.parse.urlencode({"url": url, "omit_script": "1", "dnt": "1"})
        oembed_url = f"https://publish.twitter.com/oembed?{q}"
        async with session.get(oembed_url) as resp:
            if resp.status != 200:
                return False, f"Error: oEmbed fetch failed (Status {resp.status})"
            data = await resp.json(content_type=None)

        author = (data.get("author_name") or "").strip()
        title = (data.get("title") or "").strip()
        html = (data.get("html") or "").strip()
        text = _html_to_text(html)
        text = html_lib.unescape(text)
        text = re.sub(r"\\n{3,}", "\n\n", text).strip()
        text = _truncate(text, 3000)
        header = f"### X oEmbed ({author})\n\n" if author else "### X oEmbed\n\n"
        if title and title not in text:
            header += f"Title: {title}\n\n"
        return True, header + text
    except Exception as e:
        return False, f"Access Error: oEmbed exception: {e}"


def _jina_reader_url(url: str) -> str | None:
    try:
        u = urllib.parse.urlparse(url)
        if u.scheme not in {"http", "https"}:
            return None
        q = f"?{u.query}" if u.query else ""
        return f"https://r.jina.ai/{u.scheme}://{u.netloc}{u.path}{q}"
    except Exception:
        return None


async def execute(args: dict, message=None) -> str:
    # Back-compat: some callers send {"input": "..."}.
    url = (args.get("url") or args.get("input") or args.get("link") or "").strip()
    if not url:
        return "Error: No URL provided."

    headers = {
        "User-Agent": _UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ja,en;q=0.9",
    }

    timeout = aiohttp.ClientTimeout(total=20, connect=5)
    try:
        logger.info(f"ReadPage: Reading {url}...")
        async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
            # 1) X/Twitter status -> try oEmbed first (most reliable without API key)
            if _is_x_status(url):
                ok, out = await _fetch_x_oembed(session, url)
                if ok:
                    return out

            # 2) Direct fetch
            try:
                async with session.get(url, allow_redirects=True) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        text = _truncate(_html_to_text(html))
                        return f"### Content of {url}\n\n{text}"
                    direct_err = f"Error: Failed to fetch page (Status {resp.status})"
            except Exception as e:
                direct_err = f"Access Error: {e}"

            # 3) Fallback: Jina reader
            jr = _jina_reader_url(url)
            if jr:
                try:
                    async with session.get(jr, allow_redirects=True) as resp:
                        if resp.status == 200:
                            body = await resp.text()
                            # Jina returns readable text; still sanitize a bit.
                            body = html_lib.unescape(body)
                            body = re.sub(r"\\n{3,}", "\n\n", body).strip()
                            body = _truncate(body)
                            return f"### Content of {url} (via reader)\n\n{body}"
                except Exception:
                    pass

        return direct_err

    except Exception as e:
        logger.error(f"ReadPage Error: {e}")
        return f"Access Error: {e}"
