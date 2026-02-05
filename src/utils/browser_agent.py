from __future__ import annotations

# mypy: ignore-errors
from dataclasses import dataclass
from collections import deque
import contextlib
import logging
import typing
from typing import Any, Literal, Optional
import uuid
import asyncio
import re
import os

import playwright

from playwright.async_api import (
    Browser,
    BrowserContext,
    Frame,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)

BrowserMode = Literal["launch", "cdp"]
RefMode = Literal["aria", "role", "css"]

log = logging.getLogger(__name__)

INTERACTIVE_ROLES: set[str] = {
    "button",
    "checkbox",
    "combobox",
    "link",
    "listbox",
    "menuitem",
    "menuitemcheckbox",
    "menuitemradio",
    "option",
    "radio",
    "searchbox",
    "slider",
    "spinbutton",
    "switch",
    "tab",
    "textbox",
}

ARIA_REF_LINE_RE = re.compile(
    r'^\s*-\s*(?P<role>[\w-]+)(?:\s+"(?P<name>[^"]*)")?.*?\[ref=(?P<ref>e\d+)\]',
    re.IGNORECASE,
)

MAX_REF_ENTRIES = 200
MIN_BBOX_ENTRIES = 5
MAX_SELECTOR_CHARS = 200

CSS_PATH_SCRIPT = """
el => {
  const escape =
    window.CSS && window.CSS.escape
      ? window.CSS.escape
      : (value) => value.replace(/([\\s#.:>+~\\[\\](),=])/g, "\\\\$1");
  if (!(el instanceof Element)) return "";
  const path = [];
  let element = el;
  while (element && element.nodeType === Node.ELEMENT_NODE) {
    let selector = element.nodeName.toLowerCase();
    if (element.id) {
      selector += "#" + escape(element.id);
      path.unshift(selector);
      break;
    }
    let sibling = element;
    let nth = 1;
    while ((sibling = sibling.previousElementSibling)) {
      if (sibling.nodeName.toLowerCase() === selector) nth += 1;
    }
    if (nth > 1) {
      selector += `:nth-of-type(${nth})`;
    }
    path.unshift(selector);
    element = element.parentElement;

  }
  return path.join(" > ");
}
"""


@dataclass
class RefEntry:
    ref: str
    role: str | None
    name: str | None
    nth: int | None
    mode: RefMode
    selector: str | None
    bbox: dict[str, float] | None
    frame_name: str | None
    frame_url: str | None

    def to_dict(self) -> dict[str, Any]:
        selector = self.selector
        if selector:
            selector = selector[:MAX_SELECTOR_CHARS]
        return {
            "ref": self.ref,
            "role": self.role,
            "name": self.name,
            "nth": self.nth,
            "mode": self.mode,
            "selector": selector,
            "bbox": self.bbox,
            "frame_name": self.frame_name,
            "frame_url": self.frame_url,
        }


@dataclass
class BrowserObservation:
    url: str
    title: str
    aria: str
    ref_generation: int
    ref_snapshot: str
    refs: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "aria": self.aria,
            "ref_generation": self.ref_generation,
            "ref_snapshot": self.ref_snapshot,
            "refs": self.refs,
        }


class BrowserAgent:
    """Async browser controller for LLM-driven actions."""

    def __init__(
        self,
        *,
        default_timeout_ms: int = 15_000,
        max_aria_chars: int = 10_000,
        max_action_history: int = 20,
    ) -> None:
        self.default_timeout_ms = default_timeout_ms
        self.max_aria_chars = max_aria_chars
        self.max_action_history = max_action_history

        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._pages: dict[str, Page] = {}
        self._page_ids: dict[Page, str] = {}
        self._active_tab_id: str | None = None
        self._owns_browser = False
        self._owns_context = False
        self._tab_actions: dict[str, deque[dict[str, Any]]] = {}
        self._refs_by_tab: dict[str, dict[str, RefEntry]] = {}
        self._ref_generation_by_tab: dict[str, int] = {}
        self._aria_snapshot_ref_supported: bool | None = None

    @property
    def page(self) -> Page:
        if self._page is None:
            raise RuntimeError("BrowserAgent has not started yet.")
        return self._page

    def is_started(self) -> bool:
        return self._playwright is not None and self._page is not None

    def needs_restart(self) -> bool:
        return self._playwright is not None and self._page is None

    @staticmethod
    def _empty_observation() -> BrowserObservation:
        return BrowserObservation(
            url="",
            title="",
            aria="",
            ref_generation=0,
            ref_snapshot="",
            refs=[],
        )

    def _register_page(self, page: Page, *, set_active: bool = True) -> str:
        existing = self._page_ids.get(page)
        if existing:
            if set_active:
                self._active_tab_id = existing
                self._page = page
            return existing
        tab_id = uuid.uuid4().hex[:8]
        self._pages[tab_id] = page
        self._page_ids[page] = tab_id
        self._tab_actions[tab_id] = deque(maxlen=self.max_action_history)
        self._refs_by_tab[tab_id] = {}
        self._ref_generation_by_tab[tab_id] = 0

        def _on_close() -> None:
            self._pages.pop(tab_id, None)
            self._page_ids.pop(page, None)
            self._tab_actions.pop(tab_id, None)
            self._refs_by_tab.pop(tab_id, None)
            self._ref_generation_by_tab.pop(tab_id, None)
            if self._active_tab_id == tab_id:
                fallback = next(iter(self._pages.keys()), None)
                self._active_tab_id = fallback
                self._page = self._pages.get(fallback) if fallback else None

        page.on("close", _on_close)

        if set_active or self._active_tab_id is None:
            self._active_tab_id = tab_id
            self._page = page
        return tab_id

    async def start(
        self,
        *,
        mode: BrowserMode = "launch",
        headless: bool = True,
        cdp_url: str | None = None,
        viewport: dict[str, int] | None = None,
        user_agent: str | None = None,
        user_data_dir: str | None = None,
        record_video_dir: str | None = None,
        record_video_size: dict[str, int] | None = None,
    ) -> None:
        if self._playwright is not None:
            if self._page is not None:
                return
            await self.close()

        try:
            await self._start_browser(
                mode=mode,
                headless=headless,
                cdp_url=cdp_url,
                viewport=viewport,
                user_agent=user_agent,
                user_data_dir=user_data_dir,
                record_video_dir=record_video_dir,
                record_video_size=record_video_size,
            )
        except Exception:
            await self.close()
            raise

    async def _start_browser(
        self,
        *,
        mode: BrowserMode,
        headless: bool,
        cdp_url: str | None,
        viewport: dict[str, int] | None,
        user_agent: str | None,
        user_data_dir: str | None,
        record_video_dir: str | None,
        record_video_size: dict[str, int] | None,
    ) -> None:
        self._playwright = await async_playwright().start()
        log.info("Playwright version: %s", getattr(playwright, "__version__", "unknown"))

        # Load proxy config in a browser-only safe way.
        # Do not hard-fail if full bot config (e.g., DISCORD_BOT_TOKEN) is missing.
        proxy_settings = None
        browser_proxy = (os.getenv("BROWSER_PROXY") or "").strip()
        if not browser_proxy:
            try:
                from src.config import Config
                cfg = Config.load()
                browser_proxy = (getattr(cfg, "browser_proxy", None) or "").strip()
            except Exception as cfg_err:
                log.warning("BrowserAgent: Config.load() unavailable; continuing without proxy. (%s)", cfg_err)
        if browser_proxy:
            log.info(f"Using Browser Proxy: {browser_proxy}")
            proxy_settings = {"server": browser_proxy}

        # --- PARANOID SECURITY ARGS ---
        # 1. Disable WebRTC IP Leak (Critical for VPN users)
        # 2. Disable Geolocation features
        # 3. Anti-Fingerprinting (Hide Automation)
        PARANOID_ARGS = [
            "--force-webrtc-ip-handling-policy=disable_non_proxied_udp", # Kills WebRTC leaks
            "--disable-webrtc", # Try to disable entirely if possible (generic)
            "--denying-new-preferences",
            "--disable-blink-features=AutomationControlled", # Hide "navigator.webdriver"
            "--no-first-run",
            "--no-service-autorun",
            "--password-store=basic",
            "--use-mock-keychain",
            "--disable-features=IsolateOrigins,site-per-process,GeoLocation", # Disable Geo
        ]

        if mode == "launch":
            if user_data_dir:
                self._context = await self._playwright.chromium.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    headless=headless,
                    viewport=viewport,
                    user_agent=user_agent,
                    record_video_dir=record_video_dir,
                    record_video_size=record_video_size,
                    proxy=proxy_settings,
                    args=PARANOID_ARGS, # Security Injection
                    permissions=[], # Block everything by default
                    geolocation=None, # Force no geo
                )

                self._browser = self._context.browser
                self._owns_browser = True
                self._owns_context = True
            else:
                self._browser = await self._playwright.chromium.launch(
                    headless=headless,
                    proxy=proxy_settings,
                    args=PARANOID_ARGS # Security Injection
                )
                self._context = await self._browser.new_context(
                    viewport=viewport,
                    user_agent=user_agent,
                    record_video_dir=record_video_dir,
                    record_video_size=record_video_size,
                    permissions=[], # Block everything
                    geolocation=None,
                )
                self._owns_browser = True
                self._owns_context = True
        else:
            if not cdp_url:
                raise ValueError("cdp_url is required for mode='cdp'.")
            self._browser = await self._playwright.chromium.connect_over_cdp(cdp_url)
            if self._browser.contexts:
                self._context = self._browser.contexts[0]
                self._owns_context = False
            else:
                self._context = await self._browser.new_context(
                    viewport=viewport,
                    user_agent=user_agent,
                    record_video_dir=record_video_dir,
                    record_video_size=record_video_size,
                )
                self._owns_context = True

        self._context.set_default_timeout(self.default_timeout_ms)
        self._context.on("page", lambda page: self._register_page(page, set_active=False))
        if self._context.pages:
            for page in self._context.pages:
                self._register_page(page, set_active=False)
            self._active_tab_id = next(reversed(self._pages.keys()), None)
            if self._active_tab_id:
                self._page = self._pages[self._active_tab_id]
        else:
            page = await self._context.new_page()
            self._register_page(page, set_active=True)

    async def close(self) -> None:
        if self._context is not None and self._owns_context:
            try:
                await self._context.close()
            except Exception:
                pass
        if self._browser is not None and self._owns_browser:
            # Only close browsers we launched; CDP-attached browsers are external.
            try:
                await self._browser.close()
            except Exception:
                pass
        if self._playwright is not None:
            try:
                await self._playwright.stop()
            except Exception:
                pass

        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._pages = {}
        self._page_ids = {}
        self._active_tab_id = None
        self._tab_actions = {}
        self._refs_by_tab = {}
        self._ref_generation_by_tab = {}
        self._aria_snapshot_ref_supported = None
        self._owns_browser = False
        self._owns_context = False

    async def observe(self) -> BrowserObservation:
        page = self._page
        if page is None:
            return self._empty_observation()
        return await self._observe_page(page)

    async def _observe_page(self, page: Page, retry_count: int = 3) -> BrowserObservation:
        for attempt in range(retry_count):
            try:
                return await self._observe_page_inner(page)
            except Exception as e:
                msg = str(e)
                # Check for specific Playwright errors related to navigation/context destruction
                if (
                    "Execution context was destroyed" in msg
                    or "Target closed" in msg
                    or "Navigating" in msg
                ):
                    if attempt < retry_count - 1:
                        log.warning(
                            "Recoverable error during observation (attempt %d/%d): %s. Retrying...",
                            attempt + 1,
                            retry_count,
                            msg,
                        )
                        await asyncio.sleep(0.5 * (attempt + 1))
                        continue
                # log.exception("Failed to observe page after retries.") # Reduced verbosity
                return self._empty_observation()
        return self._empty_observation()

    async def _observe_page_inner(self, page: Page) -> BrowserObservation:
        title = await page.title()

        aria = ""
        aria_ref_snapshot: str | None = None
        try:
            locator = page.locator("body")
            if hasattr(locator, "aria_snapshot"):
                if self._aria_snapshot_ref_supported is not False:
                    try:
                        aria_ref_snapshot = await locator.aria_snapshot(ref=True)
                        self._aria_snapshot_ref_supported = True
                    except TypeError:
                        if self._aria_snapshot_ref_supported is None:
                            log.debug(
                                "aria_snapshot(ref=True) unsupported; using non-ref snapshot fallback."
                            )
                        self._aria_snapshot_ref_supported = False
                        aria_ref_snapshot = None
                if aria_ref_snapshot:
                    aria = aria_ref_snapshot
                else:
                    aria = await locator.aria_snapshot()
            else:
                raise AttributeError("aria_snapshot not available")
        except Exception:
            try:
                snapshot = await page.accessibility.snapshot()
                aria = str(snapshot)
            except Exception:
                aria = ""

        if len(aria) > self.max_aria_chars:
            aria = aria[: self.max_aria_chars] + "\n...[truncated]"

        tab_id = self._page_ids.get(page)
        ref_generation = 0
        ref_snapshot = ""
        refs: list[dict[str, Any]] = []
        if tab_id:
            ref_generation = self._ref_generation_by_tab.get(tab_id, 0) + 1
            entries = await self._build_ref_entries(page, aria_ref_snapshot)
            self._refs_by_tab[tab_id] = {entry.ref: entry for entry in entries}
            self._ref_generation_by_tab[tab_id] = ref_generation
            ref_snapshot = self._format_ref_snapshot(entries)
            refs = [entry.to_dict() for entry in entries]

        return BrowserObservation(
            url=page.url,
            title=title,
            aria=aria,
            ref_generation=ref_generation,
            ref_snapshot=ref_snapshot,
            refs=refs,
        )

    async def _build_ref_entries(
        self,
        page: Page,
        aria_ref_snapshot: str | None,
    ) -> list[RefEntry]:
        entries: list[RefEntry] = []
        if aria_ref_snapshot:
            entries = await self._refs_from_aria_snapshot(page, aria_ref_snapshot)
        bbox_count = sum(1 for entry in entries if entry.bbox)
        if not entries or bbox_count < MIN_BBOX_ENTRIES:
            fallback_entries = await self._refs_from_clickable_targets(
                page,
                ref_prefix="c",
                max_items=MAX_REF_ENTRIES,
            )
            entries = self._merge_ref_entries(entries, fallback_entries)
        return self._apply_nth_to_duplicates(entries[:MAX_REF_ENTRIES])

    async def _refs_from_aria_snapshot(
        self,
        page: Page,
        aria_ref_snapshot: str,
    ) -> list[RefEntry]:
        entries: list[RefEntry] = []
        for line in aria_ref_snapshot.splitlines():
            match = ARIA_REF_LINE_RE.search(line)
            if not match:
                continue
            role = match.group("role").lower()
            name = match.group("name") or None
            ref = match.group("ref")
            if role.lower() not in INTERACTIVE_ROLES:
                continue
            locator = page.locator(f"aria-ref={ref}")
            selector = None
            bbox = None
            try:
                handle = await locator.element_handle()
            except Exception:
                handle = None
            if handle is not None:
                with contextlib.suppress(Exception):
                    selector = await handle.evaluate(CSS_PATH_SCRIPT)
                with contextlib.suppress(Exception):
                    bbox = await handle.bounding_box()
            entries.append(
                RefEntry(
                    ref=ref,
                    role=role,
                    name=name,
                    nth=None,
                    mode="aria",
                    selector=selector or None,
                    bbox=bbox,
                    frame_name=None,
                    frame_url=page.url or None,
                )
            )
        return entries

    async def _refs_from_clickable_targets(
        self,
        page: Page,
        *,
        ref_prefix: str,
        max_items: int,
    ) -> list[RefEntry]:
        selector = (
            "a, button, input, textarea, select, [role=button], [role=link], "
            "[role=tab], [role=menuitem], [role=checkbox], [role=radio], "
            "[role=combobox], [role=listbox], [role=menuitemcheckbox], [role=menuitemradio], "
            "[role=option], [role=searchbox], [role=slider], [role=spinbutton], [role=switch]"
        )
        entries: list[RefEntry] = []
        ref_index = 1
        max_scan = max_items * 2

        # Safe viewport access
        try:
            viewport = page.viewport_size or {}
        except:
            viewport = {}

        viewport_w = viewport.get("width")
        viewport_h = viewport.get("height")

        # Scan frames as well
        frames = []
        try:
            frames = page.frames
        except:
            frames = []

        for frame in frames:
            try:
                handles = await frame.query_selector_all(selector)
            except Exception:
                continue
            for handle in handles:
                if len(entries) >= max_scan:
                    break
                try:
                    box = await handle.bounding_box()
                except Exception:
                    continue
                if not box:
                    continue
                if box.get("width", 0) < 2 or box.get("height", 0) < 2:
                    continue
                if viewport_w and viewport_h:
                    if (
                        box.get("x", 0) > viewport_w
                        or box.get("y", 0) > viewport_h
                        or (box.get("x", 0) + box.get("width", 0)) < 0
                        or (box.get("y", 0) + box.get("height", 0)) < 0
                    ):
                        continue
                role_attr = None
                try:
                    role_attr = await handle.get_attribute("role")
                except Exception:
                    role_attr = None
                try:
                    tag_name = await handle.evaluate("el => el.tagName.toLowerCase()")
                except Exception:
                    tag_name = ""
                try:
                    input_type = await handle.get_attribute("type")
                except Exception:
                    input_type = None
                role = self._infer_role(role_attr, tag_name, input_type)
                name = await self._infer_accessible_name(handle, tag_name)
                selector_path = None
                with contextlib.suppress(Exception):
                    selector_path = await handle.evaluate(CSS_PATH_SCRIPT)
                ref = f"{ref_prefix}{ref_index}"
                ref_index += 1
                mode: RefMode = "css"
                if role and name:
                    mode = "role"
                entries.append(
                    RefEntry(
                        ref=ref,
                        role=role,
                        name=name,
                        nth=None,
                        mode=mode,
                        selector=selector_path,
                        bbox={
                            "x": float(box.get("x", 0)),
                            "y": float(box.get("y", 0)),
                            "width": float(box.get("width", 0)),
                            "height": float(box.get("height", 0)),
                        },
                        frame_name=frame.name or None,
                        frame_url=frame.url or None,
                    )
                )
            if len(entries) >= max_scan:
                break
        entries.sort(
            key=lambda entry: (
                (entry.bbox or {}).get("width", 0) * (entry.bbox or {}).get("height", 0)
            ),
            reverse=True,
        )
        return entries[:max_items]

    @staticmethod
    def _merge_ref_entries(
        base_entries: list[RefEntry],
        fallback_entries: list[RefEntry],
    ) -> list[RefEntry]:
        merged = list(base_entries)
        selector_to_index: dict[str, int] = {}
        for idx, entry in enumerate(merged):
            if entry.selector:
                selector_to_index[entry.selector] = idx
        for entry in fallback_entries:
            if entry.selector and entry.selector in selector_to_index:
                existing = merged[selector_to_index[entry.selector]]
                if existing.bbox is None and entry.bbox is not None:
                    existing.bbox = entry.bbox
                if existing.frame_name is None and entry.frame_name:
                    existing.frame_name = entry.frame_name
                if existing.frame_url is None and entry.frame_url:
                    existing.frame_url = entry.frame_url
                continue
            merged.append(entry)
        return merged

    @staticmethod
    def _infer_role(role_attr: str | None, tag_name: str, input_type: str | None) -> str | None:
        if role_attr:
            return role_attr.lower()
        if tag_name == "a":
            return "link"
        if tag_name == "button":
            return "button"
        if tag_name == "textarea":
            return "textbox"
        if tag_name == "select":
            return "combobox"
        if tag_name == "input":
            input_kind = (input_type or "").lower()
            if input_kind in {"checkbox"}:
                return "checkbox"
            if input_kind in {"radio"}:
                return "radio"
            if input_kind in {"range"}:
                return "slider"
            if input_kind in {"search"}:
                return "searchbox"
            return "textbox"
        return None

    @staticmethod
    async def _infer_accessible_name(handle: Any, tag_name: str) -> str | None:
        for attr in ("aria-label", "alt", "title", "placeholder", "value", "name"):
            try:
                value = await handle.get_attribute(attr)
            except Exception:
                value = None
            if value:
                return value
        if tag_name in {"a", "button", "option"}:
            with contextlib.suppress(Exception):
                text = await handle.inner_text()
                if text:
                    return text
        return None

    @staticmethod
    def _apply_nth_to_duplicates(entries: list[RefEntry]) -> list[RefEntry]:
        counts: dict[tuple[str | None, str | None], int] = {}
        for entry in entries:
            if not entry.role or not entry.name:
                continue
            key = (entry.role, entry.name)
            counts[key] = counts.get(key, 0) + 1
        nth_tracker: dict[tuple[str | None, str | None], int] = {}
        for entry in entries:
            if not entry.role or not entry.name:
                continue
            key = (entry.role, entry.name)
            if counts.get(key, 0) > 1:
                entry.nth = nth_tracker.get(key, 0)
                nth_tracker[key] = entry.nth + 1
        return entries

    @staticmethod
    def _format_ref_snapshot(entries: list[RefEntry]) -> str:
        lines = []
        for entry in entries:
            role = entry.role or "element"
            name = f' "{entry.name}"' if entry.name else ""
            nth = f" (nth={entry.nth})" if entry.nth is not None else ""
            lines.append(f"- {role}{name} [ref={entry.ref}]{nth}")
        return "\n".join(lines)

    def _get_ref_entry(self, tab_id: str | None, ref: str) -> RefEntry | None:
        if not tab_id:
            return None
        refs = self._refs_by_tab.get(tab_id)
        if refs is None:
            return None
        return refs.get(ref)

    def _ref_generation_matches(self, tab_id: str | None, ref_generation: int) -> bool:
        if not tab_id:
            return False
        return self._ref_generation_by_tab.get(tab_id, 0) == ref_generation

    def _resolve_ref_frame(self, page: Page, entry: RefEntry) -> Page | Frame:
        if entry.frame_url and entry.frame_url == page.url:
            return page
        if entry.frame_name:
            frame = page.frame(name=entry.frame_name)
            if frame:
                return frame
        if entry.frame_url:
            frame = page.frame(url=entry.frame_url)
            if frame:
                return frame
        return page

    async def _resolve_ref_locator(self, page: Page, entry: RefEntry) -> Any:
        target = self._resolve_ref_frame(page, entry)
        candidates = []
        if entry.mode == "aria":
            candidates.append(target.locator(f"aria-ref={entry.ref}"))
        if entry.mode == "role" and entry.role and entry.name:
            candidates.append(target.get_by_role(entry.role, name=entry.name))
        if entry.mode == "css" and entry.selector:
            candidates.append(target.locator(entry.selector))
        if entry.mode == "aria" and entry.role and entry.name:
            candidates.append(target.get_by_role(entry.role, name=entry.name))
        if entry.mode == "aria" and entry.selector:
            candidates.append(target.locator(entry.selector))
        if entry.mode == "role" and entry.selector:
            candidates.append(target.locator(entry.selector))
        for locator in candidates:
            if entry.nth is not None:
                locator = locator.nth(entry.nth)
            try:
                handle = await locator.element_handle()
            except Exception:
                continue
            if handle is not None:
                return locator
        raise ValueError("ref_not_resolvable")

    async def _list_tabs(self) -> list[dict[str, Any]]:
        tabs = []
        for tab_id, page in self._pages.items():
            title = ""
            with contextlib.suppress(Exception):
                title = await page.title()
            tabs.append(
                {
                    "tab_id": tab_id,
                    "url": page.url,
                    "title": title,
                    "active": tab_id == self._active_tab_id,
                }
            )
        return tabs

    def _record_action(self, tab_id: str | None, action_type: str, details: dict[str, Any]) -> None:
        if not tab_id:
            return
        history = self._tab_actions.get(tab_id)
        if history is None:
            return
        history.append({"type": action_type, "details": details})

    @staticmethod
    def _truncate_detail(value: Any, limit: int = 120) -> str:
        text = str(value or "")
        text = " ".join(text.split())
        if len(text) <= limit:
            return text
        return text[: max(0, limit - 1)] + "…"

    async def act(self, action: dict[str, Any]) -> dict[str, Any]:
        page = self._page
        if page is None:
            return {
                "ok": False,
                "error": "browser_not_started",
                "observation": self._empty_observation().to_dict(),
            }
        action_type = str(action.get("type") or "")
        active_tab_id = self._active_tab_id

        try:
            if action_type == "goto":
                await page.goto(str(action["url"]))
                self._record_action(
                    active_tab_id,
                    action_type,
                    {"url": self._truncate_detail(action.get("url"))},
                )
                with contextlib.suppress(Exception):
                    await page.wait_for_load_state("load", timeout=2000)
            elif action_type == "click":
                locator = page.locator(str(action["selector"]))
                with contextlib.suppress(Exception):
                    await locator.scroll_into_view_if_needed(timeout=5_000)
                try:
                    await locator.click(timeout=self.default_timeout_ms)
                except Exception:
                    await locator.click(timeout=self.default_timeout_ms, force=True)
                self._record_action(
                    active_tab_id,
                    action_type,
                    {"selector": self._truncate_detail(action.get("selector"))},
                )
                with contextlib.suppress(Exception):
                    # Give a brief moment for any click-triggered navigation to start
                    await page.wait_for_timeout(500)
                    await page.wait_for_load_state("load", timeout=2000)
            elif action_type == "scroll":
                delta_x_raw = action.get("delta_x", 0)
                delta_y_raw = action.get("delta_y", 800)
                after_ms_raw = action.get("after_ms", 150)
                delta_x = float(0 if delta_x_raw is None else delta_x_raw)
                delta_y = float(800 if delta_y_raw is None else delta_y_raw)
                after_ms = int(150 if after_ms_raw is None else after_ms_raw)
                await page.mouse.wheel(delta_x, delta_y)
                if after_ms > 0:
                    await page.wait_for_timeout(after_ms)
                self._record_action(
                    active_tab_id,
                    action_type,
                    {"delta_x": delta_x, "delta_y": delta_y, "after_ms": after_ms},
                )
            elif action_type == "click_role":
                role = str(action["role"])
                name = action.get("name")
                locator = page.get_by_role(role, name=str(name) if name else None)
                with contextlib.suppress(Exception):
                    await locator.scroll_into_view_if_needed(timeout=5_000)
                try:
                    await locator.click(timeout=self.default_timeout_ms)
                except Exception:
                    await locator.click(timeout=self.default_timeout_ms, force=True)
                self._record_action(
                    active_tab_id,
                    action_type,
                    {"role": role, "name": self._truncate_detail(name)},
                )
                with contextlib.suppress(Exception):
                    await page.wait_for_timeout(500)
                    await page.wait_for_load_state("load", timeout=2000)
            elif action_type == "click_xy":
                x = float(action.get("x", 0))
                y = float(action.get("y", 0))
                button = str(action.get("button") or "left")
                clicks_raw = action.get("clicks", 1)
                clicks = int(1 if clicks_raw is None else clicks_raw)
                await page.mouse.click(x=x, y=y, button=button, click_count=clicks)
                self._record_action(
                    active_tab_id,
                    action_type,
                    {"x": x, "y": y, "button": button, "clicks": clicks},
                )
            elif action_type == "click_ref":
                ref = str(action.get("ref") or "")
                ref_generation_raw = action.get("ref_generation")
                ref_generation = int(ref_generation_raw) if ref_generation_raw is not None else -1
                if not self._ref_generation_matches(active_tab_id, ref_generation):
                    return {
                        "ok": False,
                        "error": "ref_generation_mismatch",
                        "observation": (await self.observe()).to_dict(),
                    }
                entry = self._get_ref_entry(active_tab_id, ref)
                if entry is None:
                    return {
                        "ok": False,
                        "error": "unknown_ref",
                        "observation": (await self.observe()).to_dict(),
                    }
                locator = await self._resolve_ref_locator(page, entry)
                with contextlib.suppress(Exception):
                    await locator.scroll_into_view_if_needed(timeout=5_000)
                try:
                    await locator.click(timeout=self.default_timeout_ms)
                except Exception:
                    await locator.click(timeout=self.default_timeout_ms, force=True)
                self._record_action(
                    active_tab_id,
                    action_type,
                    {"ref": ref, "generation": ref_generation},
                )
            elif action_type == "new_tab":
                url = action.get("url")
                focus = action.get("focus", True)
                new_page = await self._context.new_page()
                tab_id = self._register_page(new_page, set_active=bool(focus))
                if isinstance(url, str) and url:
                    await new_page.goto(url)
                    self._record_action(
                        tab_id,
                        action_type,
                        {"url": self._truncate_detail(url)},
                    )
                return {
                    "ok": True,
                    "tab_id": tab_id,
                    "observation": (await self.observe()).to_dict(),
                }
            elif action_type == "switch_tab":
                tab_id = str(action.get("tab_id") or "")
                target = self._pages.get(tab_id)
                if target is None:
                    return {
                        "ok": False,
                        "error": "unknown_tab",
                        "observation": (await self.observe()).to_dict(),
                    }
                self._active_tab_id = tab_id
                self._page = target
                self._record_action(tab_id, action_type, {"tab_id": tab_id})
            elif action_type == "close_tab":
                tab_id = str(action.get("tab_id") or "")
                target = self._pages.get(tab_id)
                if target is None:
                    return {
                        "ok": False,
                        "error": "unknown_tab",
                        "observation": (await self.observe()).to_dict(),
                    }
                await target.close()
                self._record_action(active_tab_id, action_type, {"tab_id": tab_id})
            elif action_type == "list_tabs":
                return {
                    "ok": True,
                    "tabs": await self._list_tabs(),
                    "observation": (await self.observe()).to_dict(),
                }
            elif action_type == "observe_tabs":
                include_aria = bool(action.get("include_aria", False))
                max_tabs_raw = action.get("max_tabs")
                max_tabs = int(max_tabs_raw) if max_tabs_raw is not None else None
                tabs = []
                for tab_id, tab_page in list(self._pages.items()):
                    if max_tabs is not None and len(tabs) >= max_tabs:
                        break
                    title = ""
                    with contextlib.suppress(Exception):
                        title = await tab_page.title()
                    aria = ""
                    if include_aria:
                        with contextlib.suppress(Exception):
                            aria = (await self._observe_page(tab_page)).aria
                    tabs.append(
                        {
                            "tab_id": tab_id,
                            "url": tab_page.url,
                            "title": title,
                            "active": tab_id == self._active_tab_id,
                            "aria": aria,
                            "last_actions": list(self._tab_actions.get(tab_id, [])),
                        }
                    )
                return {
                    "ok": True,
                    "tabs": tabs,
                    "observation": (await self.observe()).to_dict(),
                }
            elif action_type == "fill":
                await page.locator(str(action["selector"])).fill(str(action.get("text", "")))
                self._record_action(
                    active_tab_id,
                    action_type,
                    {
                        "selector": self._truncate_detail(action.get("selector")),
                        "text": self._truncate_detail(action.get("text")),
                    },
                )
            elif action_type == "fill_role":
                role = str(action["role"])
                name = action.get("name")
                await page.get_by_role(role, name=str(name) if name else None).fill(
                    str(action.get("text", ""))
                )
                self._record_action(
                    active_tab_id,
                    action_type,
                    {
                        "role": role,
                        "name": self._truncate_detail(name),
                        "text": self._truncate_detail(action.get("text")),
                    },
                )
            elif action_type == "fill_ref":
                ref = str(action.get("ref") or "")
                ref_generation_raw = action.get("ref_generation")
                ref_generation = int(ref_generation_raw) if ref_generation_raw is not None else -1
                if not self._ref_generation_matches(active_tab_id, ref_generation):
                    return {
                        "ok": False,
                        "error": "ref_generation_mismatch",
                        "observation": (await self.observe()).to_dict(),
                    }
                entry = self._get_ref_entry(active_tab_id, ref)
                if entry is None:
                    return {
                        "ok": False,
                        "error": "unknown_ref",
                        "observation": (await self.observe()).to_dict(),
                    }
                locator = await self._resolve_ref_locator(page, entry)
                text = str(action.get("text", ""))
                try:
                    await locator.fill(text)
                except Exception:
                    fallback = locator.locator("input, textarea, [contenteditable=true]").first
                    await fallback.fill(text)
                self._record_action(
                    active_tab_id,
                    action_type,
                    {"ref": ref, "generation": ref_generation, "text": self._truncate_detail(text)},
                )
            elif action_type == "type":
                text = str(action.get("text", ""))
                await page.keyboard.type(text)
                self._record_action(
                    active_tab_id,
                    action_type,
                    {"text": self._truncate_detail(text)},
                )
            elif action_type == "press":
                await page.keyboard.press(str(action["key"]))
                self._record_action(
                    active_tab_id,
                    action_type,
                    {"key": self._truncate_detail(action.get("key"))},
                )
            elif action_type == "wait_for_load":
                await page.wait_for_load_state(str(action.get("state", "load")))
                self._record_action(
                    active_tab_id,
                    action_type,
                    {"state": self._truncate_detail(action.get("state", "load"))},
                )
            elif action_type == "hover_ref":
                ref = str(action.get("ref") or "")
                ref_generation_raw = action.get("ref_generation")
                ref_generation = int(ref_generation_raw) if ref_generation_raw is not None else -1
                if not self._ref_generation_matches(active_tab_id, ref_generation):
                    return {
                        "ok": False,
                        "error": "ref_generation_mismatch",
                        "observation": (await self.observe()).to_dict(),
                    }
                entry = self._get_ref_entry(active_tab_id, ref)
                if entry is None:
                    return {
                        "ok": False,
                        "error": "unknown_ref",
                        "observation": (await self.observe()).to_dict(),
                    }
                locator = await self._resolve_ref_locator(page, entry)
                with contextlib.suppress(Exception):
                    await locator.scroll_into_view_if_needed(timeout=5_000)
                await locator.hover()
                self._record_action(
                    active_tab_id,
                    action_type,
                    {"ref": ref, "generation": ref_generation},
                )
            elif action_type in {"scroll_ref", "scroll_into_view_ref"}:
                ref = str(action.get("ref") or "")
                ref_generation_raw = action.get("ref_generation")
                ref_generation = int(ref_generation_raw) if ref_generation_raw is not None else -1
                if not self._ref_generation_matches(active_tab_id, ref_generation):
                    return {
                        "ok": False,
                        "error": "ref_generation_mismatch",
                        "observation": (await self.observe()).to_dict(),
                    }
                entry = self._get_ref_entry(active_tab_id, ref)
                if entry is None:
                    return {
                        "ok": False,
                        "error": "unknown_ref",
                        "observation": (await self.observe()).to_dict(),
                    }
                locator = await self._resolve_ref_locator(page, entry)
                await locator.scroll_into_view_if_needed(timeout=5_000)
                self._record_action(
                    active_tab_id,
                    action_type,
                    {"ref": ref, "generation": ref_generation},
                )
            elif action_type == "observe":
                pass
            else:
                return {
                    "ok": False,
                    "error": f"unknown action type: {action_type}",
                    "observation": (await self.observe()).to_dict(),
                }

            return {"ok": True, "observation": (await self.observe()).to_dict()}
        except PlaywrightTimeoutError as exc:
            return {
                "ok": False,
                "error": f"timeout: {exc}",
                "observation": (await self.observe()).to_dict(),
            }
        except Exception as exc:
            return {
                "ok": False,
                "error": f"error: {type(exc).__name__}: {exc}",
                "observation": (await self.observe()).to_dict(),
            }
