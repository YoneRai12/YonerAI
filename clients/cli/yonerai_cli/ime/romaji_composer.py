"""Romaji Composer state machine.

CLI-process-local input composition only. Not a global OS IME: no keyboard
hooks outside the YonerAI CLI process, no PATH/registry/service mutation.
Provider modes: deterministic (default, offline) | local_llm (loopback-only)
| cloud_opt_in (disabled by default, explicit opt-in required).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Callable

from yonerai_cli.ime import privacy
from yonerai_cli.ime.local_enhancer import EnhancerError, enhance_with_local_llm, is_loopback_endpoint
from yonerai_cli.ime.romaji_rules import convert_text


COMPOSER_SCHEMA_VERSION = "yonerai-romaji-composer/v0.1"
PROVIDER_MODES = ("deterministic", "local_llm", "cloud_opt_in")


@dataclass
class ComposerState:
    composer_enabled: bool = False
    raw_buffer: str = ""
    converted_candidate: str | None = None
    committed_text: str | None = None
    provider_mode: str = "deterministic"
    local_llm_endpoint: str = ""
    style_profile: str = ""
    user_dictionary: dict[str, str] = field(default_factory=dict)
    last_conversion_id: str | None = None
    cloud_opt_in_confirmed: bool = False
    audit: list[dict[str, object]] = field(default_factory=list)


class RomajiComposer:
    def __init__(self, *, transport: Callable | None = None) -> None:
        self.state = ComposerState()
        self._transport = transport
        self._undo_buffer: str | None = None

    @property
    def enabled(self) -> bool:
        return self.state.composer_enabled

    def enable(self) -> None:
        self.state.composer_enabled = True

    def disable(self) -> None:
        self.state.composer_enabled = False

    def append(self, text: str) -> str:
        if self.state.converted_candidate is not None:
            self.state.converted_candidate = None
            self._undo_buffer = None
        if self.state.raw_buffer:
            self.state.raw_buffer = f"{self.state.raw_buffer} {text}"
        else:
            self.state.raw_buffer = text
        return self.state.raw_buffer

    def clear(self) -> None:
        self.state.raw_buffer = ""
        self.state.converted_candidate = None
        self._undo_buffer = None

    def set_provider_mode(self, mode: str) -> None:
        if mode not in PROVIDER_MODES:
            raise ValueError(f"unknown provider_mode: {mode}")
        if mode == "cloud_opt_in" and not self.state.cloud_opt_in_confirmed:
            raise PermissionError("cloud conversion requires explicit opt-in confirmation.")
        self.state.provider_mode = mode

    def set_local_llm_endpoint(self, endpoint: str) -> None:
        if not is_loopback_endpoint(endpoint):
            raise ValueError("local llm endpoint must be loopback (localhost / 127.0.0.1 / ::1).")
        self.state.local_llm_endpoint = endpoint

    def confirm_cloud_opt_in(self) -> None:
        self.state.cloud_opt_in_confirmed = True

    def add_dictionary_entry(self, romaji: str, japanese: str) -> None:
        key = romaji.strip().lower()
        if not key or not japanese.strip():
            raise ValueError("dictionary entry needs both romaji and japanese.")
        self.state.user_dictionary[key] = japanese.strip()

    def set_style_profile(self, style: str) -> None:
        self.state.style_profile = style.strip()

    def convert(self) -> dict[str, object]:
        """Convert the current raw buffer into a Japanese candidate."""
        raw = self.state.raw_buffer
        if not raw.strip():
            return {"ok": False, "reason": "empty_buffer"}
        self._undo_buffer = raw
        route = "deterministic"
        notice = ""
        candidate = convert_text(raw, dictionary=self.state.user_dictionary)
        if self.state.provider_mode == "local_llm" and self.state.local_llm_endpoint:
            if privacy.contains_sensitive_markers(raw):
                notice = "local llm skipped: sensitive marker detected; deterministic result returned."
            else:
                try:
                    candidate = enhance_with_local_llm(
                        raw,
                        endpoint=self.state.local_llm_endpoint,
                        style_profile=self.state.style_profile,
                        dictionary=self.state.user_dictionary,
                        transport=self._transport,
                    )
                    route = "local_llm_loopback"
                except EnhancerError as exc:
                    notice = f"local llm fallback: {exc}"
        elif self.state.provider_mode == "cloud_opt_in":
            # Cloud enhancement is contract-only in this build: the gate exists,
            # but no external call is wired. Deterministic output is returned.
            notice = "cloud enhancer is contract-only in this build; deterministic result returned."
        conversion_id = uuid.uuid4().hex[:12]
        self.state.converted_candidate = candidate
        self.state.last_conversion_id = conversion_id
        self.state.audit.append(
            {
                "schema_version": COMPOSER_SCHEMA_VERSION,
                "conversion_id": conversion_id,
                "provider_mode": self.state.provider_mode,
                "route": route,
                **privacy.redacted_summary(raw, candidate),
            }
        )
        return {
            "ok": True,
            "conversion_id": conversion_id,
            "candidate": candidate,
            "route": route,
            "notice": notice,
        }

    def commit(self) -> str | None:
        """Commit the converted candidate as the actual input text."""
        if self.state.converted_candidate is None:
            return None
        committed = self.state.converted_candidate
        self.state.committed_text = committed
        self.state.raw_buffer = ""
        self.state.converted_candidate = None
        self._undo_buffer = None
        return committed

    def revert(self) -> str | None:
        """Undo conversion and restore the previous romaji buffer."""
        if self._undo_buffer is None:
            return None
        self.state.raw_buffer = self._undo_buffer
        self.state.converted_candidate = None
        self._undo_buffer = None
        return self.state.raw_buffer

    def status(self) -> dict[str, object]:
        return {
            "schema_version": COMPOSER_SCHEMA_VERSION,
            "composer_enabled": self.state.composer_enabled,
            "provider_mode": self.state.provider_mode,
            "local_llm_endpoint_set": bool(self.state.local_llm_endpoint),
            "style_profile": self.state.style_profile or "default",
            "dictionary_entries": len(self.state.user_dictionary),
            "buffer_chars": len(self.state.raw_buffer),
            "candidate_ready": self.state.converted_candidate is not None,
            "last_conversion_id": self.state.last_conversion_id,
            "cloud_opt_in_confirmed": self.state.cloud_opt_in_confirmed,
            "global_os_ime": False,
            "raw_text_in_status": False,
        }
