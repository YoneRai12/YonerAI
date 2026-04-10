import logging
import asyncio
import time
import os
import json
import re
import traceback
from typing import Any
from datetime import datetime
from urllib.parse import urlparse
from sqlalchemy.ext.asyncio import AsyncSession

from ora_core.api.schemas.messages import DownloadLink, EffectiveRoute, MessageRequest
from ora_core.database.repo import Repository, RunStatus
from ora_core.brain.context import ContextBuilder
from ora_core.brain.memory import memory_store
from ora_core.models.model_registry import get_model_registry
# from ora_core.engine.omni_engine import remote_engine # To be implemented/connected
from ora_core.engine.simple_worker import event_manager # For event streaming
from src.utils.cost_manager import CostManager, Usage
from src.utils.intent_semantics import classify_semantic_intent, has_explicit_export_constraint

try:
    from src.utils.agent_trace import trace_event
except Exception:  # pragma: no cover - fallback for constrained test/runtime envs
    def trace_event(*_args: Any, **_kwargs: Any) -> None:
        return None

logger = logging.getLogger(__name__)

class MainProcess:
    """
    The Central Brain Loop.
    Coordinates: Input -> Context -> Engine -> Output -> Memory Update.
    """
    
    def __init__(self, run_id: str, conversation_id: str, request: MessageRequest, db_session: AsyncSession):
        self.run_id = run_id
        self.conversation_id = conversation_id
        self.request = request
        self.db = db_session
        self.repo = Repository(db_session)
        self.cost_manager = CostManager()

    _ROUTE_DEFAULTS: dict[str, dict[str, int]] = {
        "INSTANT": {"max_turns": 2, "max_tool_calls": 0, "time_budget_seconds": 25},
        "TASK": {"max_turns": 5, "max_tool_calls": 5, "time_budget_seconds": 120},
        "AGENT_LOOP": {"max_turns": 8, "max_tool_calls": 10, "time_budget_seconds": 300},
    }
    _PROFILE_SEARCH_DOMAINS = {
        "github.com",
        "x.com",
        "twitter.com",
        "instagram.com",
        "youtube.com",
        "youtube.co.jp",
        "tiktok.com",
        "linkedin.com",
        "lit.link",
        "note.com",
        "github.io",
        "qiita.com",
        "zenn.dev",
        "pixiv.net",
        "nicovideo.jp",
        "niconico.com",
    }
    _NOISY_SEARCH_DOMAINS = {
        "reddit.com",
        "funtivia.com",
        "quizur.com",
        "microsoft.com",
        "google.com",
        "bing.com",
        "eroguide.dk",
    }
    _NOISY_SEARCH_KEYWORDS = (
        "quiz",
        "forum",
        "subreddit",
        "microsoft support",
        "google search",
        "general guide",
        "dictionary",
        "wiki",
    )

    @staticmethod
    def _clamp_int(value: Any, default: int, *, lo: int, hi: int) -> int:
        try:
            v = int(value)
        except Exception:
            v = int(default)
        return max(lo, min(hi, v))

    @staticmethod
    def _clamp_float(value: Any, default: float, *, lo: float = 0.0, hi: float = 1.0) -> float:
        try:
            v = float(value)
        except Exception:
            v = float(default)
        return max(lo, min(hi, v))

    @staticmethod
    def _dedup_reason_codes(raw: Any) -> list[str]:
        out: list[str] = []
        if not isinstance(raw, list):
            return out
        for x in raw:
            rc = str(x or "").strip()
            if rc and rc not in out:
                out.append(rc)
        return out

    @staticmethod
    def _risk_level_from_score(score: float) -> str:
        s = max(0.0, min(1.0, float(score)))
        if s >= 0.9:
            return "CRITICAL"
        if s >= 0.6:
            return "HIGH"
        if s >= 0.3:
            return "MEDIUM"
        return "LOW"

    @staticmethod
    def _mode_from_difficulty(score: float) -> str:
        d = max(0.0, min(1.0, float(score)))
        if d <= 0.3:
            return "INSTANT"
        if d <= 0.6:
            return "TASK"
        return "AGENT_LOOP"

    @staticmethod
    def _band_from_route_score(score: float) -> str:
        s = max(0.0, min(1.0, float(score)))
        if s <= 0.3:
            return "instant"
        if s <= 0.6:
            return "task"
        return "agent"

    @staticmethod
    def _tier_from_route_band(route_band: str) -> str:
        return {
            "instant": "instant",
            "task": "balanced",
            "agent": "pro",
        }.get(str(route_band or "").strip().lower(), "balanced")

    @staticmethod
    def _truthy_env(name: str, default: bool = False) -> bool:
        raw = os.getenv(name)
        if raw is None:
            return default
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _safe_user_message_for_error(error_code: str) -> str:
        code = str(error_code or "").strip() or "core_error"
        return f"Gateway failed: {code}"

    def _budget_stop_user_message(self, *, effective_route: dict[str, Any], reason_code: str) -> str:
        base = "[System] Request stopped by Core safety limits."
        if not self._route_debug_enabled():
            return base

        route_band = str(effective_route.get("route_band") or "").strip().lower() or "task"
        reason = str(reason_code or "").strip() or "router_budget_exceeded"
        return (
            f"[System] Route budget reached ({reason}). "
            f"Request stopped by Core safety limits. route_band={route_band}"
        )

    @staticmethod
    def _normalize_search_text(text: str) -> str:
        lowered = str(text or "").strip().lower()
        lowered = re.sub(r"<@!?\d+>", " ", lowered)
        lowered = lowered.replace("@yonerai", " ")
        lowered = re.sub(r"\s+", " ", lowered)
        return lowered.strip()

    def _search_query_hint(self, effective_route: dict[str, Any]) -> str:
        hint = str(effective_route.get("search_query_hint") or "").strip()
        if hint:
            return hint
        content = str(getattr(self.request, "content", "") or "").strip()
        if not content:
            return ""
        return content.splitlines()[-1].strip()

    def _clarification_allowed_before_search(self, query: str) -> bool:
        normalized = self._normalize_search_text(query)
        if not normalized:
            return True

        if any(marker in normalized for marker in ("この画像", "画像のurl", "このurl", "このリンク", "このページ")):
            has_attachment = bool(getattr(self.request, "attachments", None))
            has_url = bool(re.search(r"https?://", query or ""))
            if not has_attachment and not has_url:
                return True

        if any(marker in normalized for marker in ("非公開", "private", "住所", "電話番号", "連絡先", "本名", "学校", "家族")):
            return True

        stripped = normalized
        for token in (
            "について",
            "を",
            "で",
            "要約して",
            "要約",
            "まとめて",
            "まとめ",
            "比較して",
            "比較しながら",
            "検索して",
            "検索",
            "調べて",
            "調査して",
            "公開情報",
            "web 全体で",
            "web全体で",
            "主要sns",
            "活動内容",
            "出典url",
            "sources",
            "source",
        ):
            stripped = stripped.replace(token, " ")
        stripped = re.sub(r"[^0-9a-zA-Zぁ-んァ-ヶ一-龯_@.\-\s]", " ", stripped)
        stripped = re.sub(r"\s+", " ", stripped).strip()
        return len(stripped) < 2

    def _missing_referenced_input(self, query: str) -> bool:
        normalized = self._normalize_search_text(query)
        if not normalized:
            return False
        refers_to_missing_input = any(
            marker in normalized
            for marker in (
                "\u3053\u306e\u753b\u50cf",
                "\u3053\u306eurl",
                "\u753b\u50cf\u306eurl",
                "\u3053\u306e\u30ea\u30f3\u30af",
                "\u3053\u306e\u52d5\u753b",
                "\u3053\u306e\u97f3\u58f0",
                "\u3053\u306e\u30d5\u30a1\u30a4\u30eb",
                "this image",
                "this url",
                "this link",
                "this video",
                "this audio",
                "this file",
            )
        )
        if not refers_to_missing_input:
            return False
        has_attachment = bool(getattr(self.request, "attachments", None))
        has_url = bool(re.search(r"https?://", query or ""))
        return not has_attachment and not has_url

    @staticmethod
    def _has_contradictory_export_constraints(query: str) -> bool:
        normalized = str(query or "").strip().lower()
        if not normalized:
            return False

        wants_pdf = "pdf" in normalized
        wants_image = any(
            marker in normalized
            for marker in ("png", "jpg", "jpeg", "webp", "\u753b\u50cf\u306e\u307e\u307e", "\u753b\u50cf\u3067")
        )
        wants_video = any(marker in normalized for marker in ("mp4", "\u52d5\u753b\u306e\u307e\u307e", "\u52d5\u753b\u3067"))
        wants_audio = any(marker in normalized for marker in ("mp3", "wav", "\u97f3\u58f0\u3060\u3051", "\u97f3\u58f0\u3067"))

        if wants_pdf and (wants_image or wants_video or wants_audio):
            return True
        if wants_image and wants_video:
            return True
        if wants_video and wants_audio:
            return True
        return False

    def _clarification_allowed_before_save_export(self, query: str, *, explicit_save_intent: bool) -> bool:
        if self._missing_referenced_input(query):
            return True
        if explicit_save_intent and self._has_contradictory_export_constraints(query):
            return True
        return False

    @staticmethod
    def _next_actions_for_search(query: str) -> list[str]:
        query = str(query or "").strip()
        return [
            "検索語の表記ゆれを変えて再検索する",
            "対象プラットフォームを指定して再検索する",
            f"対象のURLやスクリーンショットを提示してもらう ({query[:60]})" if query else "対象のURLやスクリーンショットを提示してもらう",
        ]

    def _search_target_text(self, query: str) -> str:
        stripped = self._normalize_search_text(query)
        for token in (
            "について",
            "を",
            "で",
            "要約して",
            "要約",
            "まとめて",
            "まとめ",
            "比較して",
            "比較しながら",
            "検索して",
            "検索",
            "調べて",
            "調査して",
            "公開情報",
            "web 全体で",
            "web全体で",
            "主要sns",
            "活動内容",
            "出典url",
            "sources",
            "source",
        ):
            stripped = stripped.replace(token, " ")
        stripped = re.sub(r"[^0-9a-zA-Zぁ-んァ-ヶ一-龯_@.\-\s]", " ", stripped)
        return re.sub(r"\s+", " ", stripped).strip()

    @staticmethod
    def _search_candidate_tokens(normalized_query: str) -> list[str]:
        tokens = [
            token.strip("@")
            for token in re.split(r"\s+", normalized_query)
            if len(token.strip("@")) >= 3 and token not in {"検索して", "要約して", "公開情報", "主要sns"}
        ]
        if not tokens and normalized_query:
            fallback = normalized_query.strip("@")
            if fallback:
                tokens = [fallback]
        return tokens

    @staticmethod
    def _source_domain(url: str) -> str:
        try:
            domain = urlparse(str(url or "").strip()).netloc.lower()
        except Exception:
            return ""
        if domain.startswith("www."):
            domain = domain[4:]
        return domain

    def _is_profile_lookup_search(self, normalized_query: str, candidate_tokens: list[str]) -> bool:
        if not normalized_query or not candidate_tokens:
            return False
        return len(candidate_tokens) == 1

    @staticmethod
    def _contains_exact_token(text: str, token: str) -> bool:
        if not text or not token:
            return False
        pattern = rf"(?<![0-9a-zA-Z_]){re.escape(token)}(?![0-9a-zA-Z_])"
        return re.search(pattern, text, flags=re.IGNORECASE) is not None

    def _score_search_source(
        self,
        *,
        candidate_tokens: list[str],
        source: dict[str, Any],
        profile_lookup: bool,
    ) -> tuple[int, bool]:
        title = str(source.get("title") or "").strip()
        snippet = str(source.get("snippet") or "").strip()
        url = str(source.get("url") or "").strip()
        hay = self._normalize_search_text(" ".join([title, snippet, url]))
        domain = self._source_domain(url)

        score = 0
        exact_match = False

        for token in candidate_tokens:
            if token in hay:
                score += 2
            if self._contains_exact_token(hay, token):
                score += 3
                exact_match = True
            if url and (f"/{token.lower()}" in url.lower() or f"@{token.lower()}" in url.lower()):
                score += 2
                exact_match = True

        if domain in self._PROFILE_SEARCH_DOMAINS:
            score += 2
        if profile_lookup and domain in self._NOISY_SEARCH_DOMAINS:
            score -= 5
        elif domain in self._NOISY_SEARCH_DOMAINS:
            score -= 3

        lowered = " ".join([title.lower(), snippet.lower(), url.lower()])
        if any(keyword in lowered for keyword in self._NOISY_SEARCH_KEYWORDS):
            score -= 3 if profile_lookup else 2

        if profile_lookup and exact_match and domain in self._PROFILE_SEARCH_DOMAINS:
            score += 3
        if profile_lookup and not exact_match and domain not in self._PROFILE_SEARCH_DOMAINS:
            score -= 1

        return score, exact_match

    def _rank_search_sources(self, *, query: str, sources: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str], float]:
        normalized_query = self._search_target_text(query)
        candidate_tokens = self._search_candidate_tokens(normalized_query)
        profile_lookup = self._is_profile_lookup_search(normalized_query, candidate_tokens)

        scored: list[tuple[int, int, bool, dict[str, Any]]] = []
        for index, source in enumerate(sources):
            score, exact_match = self._score_search_source(
                candidate_tokens=candidate_tokens,
                source=source,
                profile_lookup=profile_lookup,
            )
            scored.append((score, index, exact_match, source))

        scored.sort(key=lambda item: (item[0], item[2], -item[1]), reverse=True)

        positive = [source for score, _, _, source in scored if score > 0]
        ranked_sources = positive[:5] if positive else []

        top_score = scored[0][0] if scored else 0
        top_exact = scored[0][2] if scored else False
        matched_entities: list[str] = []
        confidence = 0.0

        if sources:
            if profile_lookup:
                if top_score >= 7 and top_exact:
                    matched_entities = [query.strip()]
                    confidence = 0.85
                elif top_score >= 5 and ranked_sources:
                    matched_entities = [query.strip()]
                    confidence = 0.65
                else:
                    confidence = 0.2
            else:
                if top_score >= 5:
                    matched_entities = [query.strip()]
                    confidence = 0.75
                elif ranked_sources:
                    confidence = 0.45
                else:
                    confidence = 0.25

        return ranked_sources, matched_entities, confidence

    def _build_search_result_contract(self, *, query: str, sources: list[dict[str, Any]]) -> dict[str, Any]:
        ranked_sources, matched_entities, confidence = self._rank_search_sources(query=query, sources=sources)

        searched_sources = [
            {
                "title": str(source.get("title") or "").strip(),
                "url": str(source.get("url") or "").strip(),
                "snippet": str(source.get("snippet") or "").strip(),
            }
            for source in ranked_sources[:5]
        ]

        return {
            "searched_sources": searched_sources,
            "matched_entities": matched_entities,
            "confidence": confidence,
            "next_actions": self._next_actions_for_search(query),
        }

    @staticmethod
    def _format_search_content_atoms(sources: list[dict[str, Any]]) -> list[dict[str, str]]:
        return [
            {
                "type": "text",
                "text": f"[{index}] {str(source.get('title') or '無題').strip()}\nURL: {str(source.get('url') or '').strip()}\nSnippet: {str(source.get('snippet') or '').strip()}\n",
            }
            for index, source in enumerate(sources[:5], start=1)
        ]

    def _normalize_search_tool_payload(self, *, query: str, tool_payload: Any) -> tuple[Any, dict[str, Any]]:
        sources = self._extract_search_sources(tool_payload)
        contract = self._build_search_result_contract(query=query, sources=sources)
        normalized_sources = list(contract.get("searched_sources") or [])

        if not isinstance(tool_payload, dict):
            return tool_payload, contract

        normalized_payload = dict(tool_payload)
        structured = tool_payload.get("structuredContent")
        if isinstance(structured, dict):
            normalized_payload["structuredContent"] = dict(structured)
            normalized_payload["structuredContent"]["sources"] = normalized_sources
        elif "structuredContent" in normalized_payload:
            normalized_payload["structuredContent"] = {"sources": normalized_sources}

        if "sources" in normalized_payload:
            normalized_payload["sources"] = normalized_sources

        if "content" in normalized_payload:
            normalized_payload["content"] = self._format_search_content_atoms(normalized_sources)

        return normalized_payload, contract

    @staticmethod
    def _extract_search_sources(tool_payload: Any) -> list[dict[str, Any]]:
        if not isinstance(tool_payload, dict):
            return []
        structured = tool_payload.get("structuredContent")
        if isinstance(structured, dict) and isinstance(structured.get("sources"), list):
            return [s for s in structured.get("sources") if isinstance(s, dict)]
        if isinstance(tool_payload.get("sources"), list):
            return [s for s in tool_payload.get("sources") if isinstance(s, dict)]
        return []

    @staticmethod
    def _looks_like_clarification_only_response(text: str) -> bool:
        normalized = str(text or "").strip()
        if not normalized:
            return True
        question_markers = (
            "確認",
            "よろしいですか",
            "教えてください",
            "選んでください",
            "どの範囲",
            "どちら",
            "何を",
            "?",
            "？",
        )
        source_markers = ("http://", "https://", "出典", "source", "sources")
        has_question = any(marker in normalized for marker in question_markers)
        has_sources = any(marker in normalized.lower() for marker in source_markers)
        return has_question and not has_sources

    @staticmethod
    def _looks_like_save_export_clarification_only_response(text: str) -> bool:
        normalized = str(text or "").strip().lower()
        if not normalized:
            return False
        question_markers = (
            "\u3069\u306e\u5f62\u5f0f",
            "\u4fdd\u5b58\u3057\u305f\u3044\u5f62\u5f0f",
            "\u4f55\u3092\u30c0\u30a6\u30f3\u30ed\u30fc\u30c9",
            "\u4f55\u3092\u4fdd\u5b58",
            "what format",
            "which format",
            "what do you want to download",
            "?",
            "\uff1f",
        )
        format_markers = (
            "\u4fdd\u5b58",
            "\u30c0\u30a6\u30f3\u30ed\u30fc\u30c9",
            "\u5f62\u5f0f",
            "\u30d5\u30a1\u30a4\u30eb\u540d",
            "download",
            "save",
            "export",
            "format",
            "pdf",
            "png",
            "mp4",
            "mp3",
        )
        has_question = any(marker in normalized for marker in question_markers)
        has_format = any(marker in normalized for marker in format_markers)
        return has_question and has_format

    def _format_search_no_match_response(self, *, query: str, contract: dict[str, Any]) -> str:
        next_actions = contract.get("next_actions") or []
        options = "\n".join(f"- {item}" for item in next_actions[:3])
        query_label = query.strip() or "指定の対象"
        return (
            f"検索を実行しましたが、{query_label} に関する公開情報の中に自信を持って一致すると言える結果は見つかりませんでした。\n"
            f"次にできること:\n{options}"
        )

    def _format_search_summary_fallback(self, *, query: str, contract: dict[str, Any]) -> str:
        sources = contract.get("searched_sources") or []
        top_lines: list[str] = []
        for idx, source in enumerate(sources[:3], start=1):
            title = str(source.get("title") or "無題").strip()
            url = str(source.get("url") or "").strip()
            snippet = str(source.get("snippet") or "").strip()
            line = f"{idx}. {title}"
            if url:
                line += f" - {url}"
            if snippet:
                line += f"\n   {snippet[:140]}"
            top_lines.append(line)
        details = "\n".join(top_lines) if top_lines else "- 検索結果の詳細は取得済みです"
        return (
            f"{query.strip() or '指定の対象'} について検索を実行しました。公開情報の要点は次のとおりです。\n"
            f"{details}"
        )

    @staticmethod
    def _dedupe_downloads(downloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        unique: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        for item in downloads:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            unique.append(item)
        return unique[:5]

    def _coerce_download_link(
        self,
        *,
        url: Any,
        label: Any = None,
        file_id: Any = None,
    ) -> dict[str, Any] | None:
        url_text = str(url or "").strip()
        if not url_text:
            return None
        label_text = str(label or "ダウンロード").strip() or "ダウンロード"
        file_id_text = str(file_id or "").strip() or None
        try:
            return DownloadLink(
                url=url_text,
                label=label_text,
                file_id=file_id_text,
            ).model_dump(exclude_none=True)
        except Exception:
            return None

    def _extract_downloads_from_tool_payload(
        self,
        *,
        tool_payload: Any,
        artifact_ref: Any = None,
    ) -> list[dict[str, Any]]:
        downloads: list[dict[str, Any]] = []

        def _append_candidate(*, url: Any, label: Any = None, file_id: Any = None) -> None:
            item = self._coerce_download_link(url=url, label=label, file_id=file_id)
            if item:
                downloads.append(item)

        def _consume_mapping(mapping: dict[str, Any]) -> None:
            if not isinstance(mapping, dict):
                return
            _append_candidate(
                url=(
                    mapping.get("url")
                    or mapping.get("download_url")
                    or mapping.get("download_page_url")
                    or mapping.get("href")
                ),
                label=(
                    mapping.get("label")
                    or mapping.get("name")
                    or mapping.get("filename")
                    or mapping.get("download_name")
                ),
                file_id=mapping.get("file_id"),
            )

        def _consume_list(raw: Any) -> None:
            if not isinstance(raw, list):
                return
            for item in raw:
                if isinstance(item, dict):
                    _consume_mapping(item)

        if isinstance(tool_payload, dict):
            _consume_list(tool_payload.get("downloads"))
            _consume_list(tool_payload.get("files"))
            _consume_list(tool_payload.get("attachments"))

            structured = tool_payload.get("structuredContent")
            if isinstance(structured, dict):
                _consume_list(structured.get("downloads"))
                _consume_list(structured.get("files"))
                _consume_list(structured.get("attachments"))

            for meta_key in ("video_meta", "image_meta", "file_meta"):
                meta = tool_payload.get(meta_key)
                if isinstance(meta, dict):
                    _append_candidate(
                        url=meta.get("download_page_url") or meta.get("download_url") or meta.get("url"),
                        label=meta.get("filename") or meta.get("download_name") or meta_key,
                        file_id=meta.get("file_id"),
                    )

            _append_candidate(
                url=tool_payload.get("download_page_url") or tool_payload.get("download_url"),
                label=tool_payload.get("filename") or tool_payload.get("download_name"),
                file_id=tool_payload.get("file_id"),
            )

        if isinstance(artifact_ref, str) and artifact_ref.strip().lower().startswith(("http://", "https://")):
            _append_candidate(url=artifact_ref, label="ダウンロード")

        return self._dedupe_downloads(downloads)

    async def _force_search_attempt(
        self,
        *,
        runner: Any,
        run_id: str,
        user_id: str,
        client_type: str,
        query: str,
        request_meta: dict[str, Any] | None,
        effective_route: dict[str, Any],
        pass_index: int,
        tool_call_suffix: str,
    ) -> tuple[str, dict[str, Any], dict[str, Any]]:
        forced_tool_call_id = f"forced-search-{run_id}-{pass_index}-{tool_call_suffix}"
        result = await runner.run_tool(
            forced_tool_call_id,
            run_id,
            user_id,
            "google_search",
            {"query": query},
            client_type,
            request_meta=request_meta,
            effective_route=effective_route,
        )
        tool_payload = result.get("result") if isinstance(result, dict) and result.get("result") is not None else result.get("error")
        tool_payload, contract = self._normalize_search_tool_payload(query=query, tool_payload=tool_payload)
        return forced_tool_call_id, tool_payload, contract

    @staticmethod
    def _is_model_not_found_error(exc: Exception) -> bool:
        msg = str(exc or "").lower()
        markers = (
            "model_not_found",
            "model not found",
            "unknown model",
            "no such model",
            "not a valid model",
            "invalid model",
        )
        return any(m in msg for m in markers)

    @staticmethod
    def _is_provider_unavailable_error(exc: Exception) -> bool:
        msg = str(exc or "").lower()
        markers = (
            "timeout",
            "timed out",
            "rate limit",
            "429",
            "503",
            "temporarily unavailable",
            "connection",
        )
        return any(m in msg for m in markers)

    async def _emit_progress_event(self, *, stage: str, pass_index: int, toc: list[str] | None = None) -> None:
        await event_manager.emit(
            self.run_id,
            "progress",
            {
                "stage": str(stage),
                "pass": int(pass_index),
                "toc": list(toc or []),
            },
        )

    def _route_debug_enabled(self) -> bool:
        raw = str(os.getenv("ORA_ROUTE_DEBUG", "") or "").strip().lower()
        env_enabled = raw in {"1", "true", "yes", "on"}
        if not env_enabled:
            return False
        return self._is_admin_verified()

    def _is_admin_verified(self) -> bool:
        try:
            req_meta = getattr(self.request, "request_meta", None)
            return bool(getattr(req_meta, "admin_verified", False))
        except Exception:
            return False

    @staticmethod
    def _append_reason_code(effective_route: dict[str, Any], reason_code: str) -> None:
        rc = str(reason_code or "").strip()
        if not rc:
            return
        reason_codes = effective_route.get("reason_codes")
        if not isinstance(reason_codes, list):
            reason_codes = []
            effective_route["reason_codes"] = reason_codes
        if rc not in reason_codes:
            reason_codes.append(rc)

    async def _persist_effective_route(self, effective_route: dict[str, Any]) -> None:
        try:
            from src.utils.link_attribution import record_run_effective_route

            await record_run_effective_route(run_id=self.run_id, effective_route=effective_route)
        except Exception:
            pass

    @staticmethod
    def _band2_pass_count(effective_route: dict[str, Any]) -> int:
        route_band = str((effective_route or {}).get("route_band") or "").strip().lower()
        return 2 if route_band == "agent" else 1

    @staticmethod
    def _band2_pass_timeout_sec() -> int | None:
        raw = str(os.getenv("ORA_BAND2_PASS_TIMEOUT_SEC", "") or "").strip()
        if not raw:
            return None
        try:
            timeout = int(raw)
        except Exception:
            return None
        return timeout if timeout > 0 else None

    async def _emit_progress(self, stage: str, pass_index: int, toc: list[str] | None = None) -> None:
        safe_stage = str(stage or "").strip().lower() or "progress"
        safe_toc = [str(item).strip() for item in (toc or []) if str(item).strip()][:3]
        await event_manager.emit(
            self.run_id,
            "progress",
            {
                "stage": safe_stage,
                "pass": int(pass_index),
                "toc": safe_toc,
            },
        )

    async def _generate_with_registry(
        self,
        *,
        omni_engine: Any,
        messages: list[dict[str, Any]],
        client_type: str,
        tool_schemas: list[dict[str, Any]] | None,
        route_band: str,
        pass_index: int,
        llm_pref: str | None,
    ) -> Any:
        strict = self._truthy_env("MODEL_REGISTRY_STRICT", True)
        registry = get_model_registry(strict=strict)
        tier = registry.tier_for_route_band(route_band)
        candidates = registry.resolve_candidates(route_band=route_band, tier=tier)

        last_exc: Exception | None = None
        selected_payload: dict[str, Any] | None = None

        for idx, candidate in enumerate(candidates):
            provider = candidate.provider
            model_id = candidate.model_id
            selected_payload = {
                "run_id": self.run_id,
                "route_band": route_band,
                "tier": tier,
                "pass": pass_index,
                "provider": provider,
                "model_id": model_id,
                "candidate_index": idx,
            }
            logger.info("router.model.selected", extra={"route_event": selected_payload})

            try:
                response = await omni_engine.generate(
                    messages,
                    client_type,
                    stream=False,
                    preference=model_id,
                    tool_schemas=tool_schemas,
                )
                logger.info(
                    "router.model.fallback",
                    extra={
                        "route_event": {
                            **selected_payload,
                            "used": bool(idx > 0),
                            "reason": "none" if idx == 0 else "provider_unavailable",
                        }
                    },
                )
                return response
            except Exception as exc:
                last_exc = exc
                reason = "provider_error"
                if self._is_model_not_found_error(exc):
                    reason = "model_not_found"
                    registry.disable_runtime(provider, model_id)
                elif self._is_provider_unavailable_error(exc):
                    reason = "provider_unavailable"

                logger.warning(
                    "router.model.fallback",
                    extra={
                        "route_event": {
                            **selected_payload,
                            "used": True,
                            "reason": reason,
                            "error": str(exc)[:240],
                        }
                    },
                )
                continue

        # Strict mode: always fall back to stable_fallback as last safe option.
        stable = registry.stable_fallback
        stable_payload = {
            "run_id": self.run_id,
            "route_band": route_band,
            "tier": tier,
            "pass": pass_index,
            "provider": stable.provider,
            "model_id": stable.model_id,
            "candidate_index": "stable_fallback",
        }
        logger.info("router.model.selected", extra={"route_event": stable_payload})
        try:
            response = await omni_engine.generate(
                messages,
                client_type,
                stream=False,
                preference=stable.model_id,
                tool_schemas=tool_schemas,
            )
            logger.info(
                "router.model.fallback",
                extra={
                    "route_event": {
                        **stable_payload,
                        "used": True,
                        "reason": "stable_fallback",
                    }
                },
            )
            return response
        except Exception as exc:
            logger.warning(
                "router.model.fallback",
                extra={
                    "route_event": {
                        **stable_payload,
                        "used": True,
                        "reason": "stable_fallback_failed",
                        "error": str(exc)[:240],
                    }
                },
            )
            if last_exc:
                raise last_exc
            raise exc

    def _resolve_effective_route(self, selected_tool_schemas: list[dict[str, Any]]) -> dict[str, Any]:
        hint: dict[str, Any] = {}
        raw_hint = getattr(self.request, "route_hint", None)
        if raw_hint is not None:
            if hasattr(raw_hint, "model_dump"):
                try:
                    dumped = raw_hint.model_dump()
                    if isinstance(dumped, dict):
                        hint = dumped
                except Exception:
                    hint = {}
            elif isinstance(raw_hint, dict):
                hint = raw_hint

        difficulty_score = self._clamp_float(hint.get("difficulty_score"), 0.5)
        complexity_score = self._clamp_float(hint.get("complexity_score"), difficulty_score)
        action_score = self._clamp_float(hint.get("action_score"), difficulty_score)
        security_risk_score = self._clamp_float(hint.get("security_risk_score"), 0.0)
        function_category = str(hint.get("function_category") or "chat").strip().lower() or "chat"
        explicit_search_intent = bool(hint.get("explicit_search_intent"))
        reason_codes = self._dedup_reason_codes(hint.get("reason_codes"))
        explicit_save_intent = bool(hint.get("explicit_save_intent"))
        if not explicit_save_intent:
            semantic_intent = classify_semantic_intent(
                str(getattr(self.request, "content", "") or ""),
                has_current_image=any(
                    str(getattr(att, "type", None) or (att.get("type") if isinstance(att, dict) else "")).strip()
                    in {"image_url", "image_base64"}
                    for att in (getattr(self.request, "attachments", None) or [])
                ),
                has_prior_image=False,
                has_client_history=bool(getattr(self.request, "client_history", None)),
                has_explicit_export_constraint=has_explicit_export_constraint(
                    str(getattr(self.request, "content", "") or "")
                ),
            )
            explicit_save_intent = bool(semantic_intent.save_export_intent)
            if explicit_save_intent:
                reason_codes = self._dedup_reason_codes(list(reason_codes) + ["semantic_save_intent_detected"])
        search_query_hint = str(hint.get("search_query_hint") or "").strip()[:500]
        route_score_hint = hint.get("route_score")
        if route_score_hint is None:
            route_score = (complexity_score * 0.45) + (security_risk_score * 0.35) + (action_score * 0.20)
        else:
            route_score = self._clamp_float(route_score_hint, difficulty_score)

        budget_hint = hint.get("budget")
        budget_dict = budget_hint if isinstance(budget_hint, dict) else {}

        def _build_budget(route_defaults: dict[str, int]) -> dict[str, int]:
            return {
                "max_turns": self._clamp_int(budget_dict.get("max_turns"), route_defaults["max_turns"], lo=1, hi=20),
                "max_tool_calls": self._clamp_int(
                    budget_dict.get("max_tool_calls"),
                    route_defaults["max_tool_calls"],
                    lo=0,
                    hi=20,
                ),
                "time_budget_seconds": self._clamp_int(
                    budget_dict.get("time_budget_seconds"),
                    route_defaults["time_budget_seconds"],
                    lo=10,
                    hi=1800,
                ),
            }

        floor_applied = False
        if function_category == "vision" and route_score < 0.35:
            route_score = 0.35
            floor_applied = True
            if "router_vision_floor_applied" not in reason_codes:
                reason_codes.append("router_vision_floor_applied")

        mode_hint = str(hint.get("mode") or "").strip().upper()
        if mode_hint in self._ROUTE_DEFAULTS and not floor_applied:
            mode = mode_hint
        else:
            mode = self._mode_from_difficulty(route_score)
        defaults = dict(self._ROUTE_DEFAULTS.get(mode, self._ROUTE_DEFAULTS["TASK"]))
        budget = _build_budget(defaults)
        security_risk_level = str(hint.get("security_risk_level") or "").strip().upper()
        if not security_risk_level:
            security_risk_level = self._risk_level_from_score(security_risk_score)

        high_risk = security_risk_score >= 0.6 or security_risk_level in {"HIGH", "CRITICAL"}
        if mode in {"INSTANT", "AGENT_LOOP"} and high_risk:
            mode = "TASK"
            defaults = dict(self._ROUTE_DEFAULTS["TASK"])
            budget = _build_budget(defaults)
            if "router_mode_forced_safe" not in reason_codes:
                reason_codes.append("router_mode_forced_safe")

        if selected_tool_schemas and mode == "INSTANT":
            mode = "TASK"
            defaults = dict(self._ROUTE_DEFAULTS["TASK"])
            budget = _build_budget(defaults)
            if "router_mode_forced_tools" not in reason_codes:
                reason_codes.append("router_mode_forced_tools")

        if not selected_tool_schemas and not explicit_search_intent:
            budget["max_tool_calls"] = 0
        elif mode == "INSTANT":
            # Keep band0 ("instant") fail-safe and cheap.
            clamped_tools = min(int(budget.get("max_tool_calls", 0) or 0), 1)
            budget["max_tool_calls"] = max(clamped_tools, 0)
            # Keep band0 ("instant") fail-safe and cheap even when hints request larger budgets.
            clamped_turns = min(int(budget.get("max_turns", 2)), int(self._ROUTE_DEFAULTS["INSTANT"]["max_turns"]))
            clamped_time = min(
                int(budget.get("time_budget_seconds", 25)),
                int(self._ROUTE_DEFAULTS["INSTANT"]["time_budget_seconds"]),
            )
            if clamped_turns != int(budget.get("max_turns", clamped_turns)) or clamped_time != int(
                budget.get("time_budget_seconds", clamped_time)
            ):
                if "router_budget_band0_clamped" not in reason_codes:
                    reason_codes.append("router_budget_band0_clamped")
            budget["max_turns"] = clamped_turns
            budget["time_budget_seconds"] = clamped_time
        elif int(budget.get("max_tool_calls", 0) or 0) <= 0:
            # Respect router-provided budget for band1+ paths; only guard against invalid zero.
            budget["max_tool_calls"] = 1

        route_band = self._band_from_route_score(route_score)
        model_tier = self._tier_from_route_band(route_band)

        effective = EffectiveRoute(
            mode=mode,  # type: ignore[arg-type]
            route_band=route_band,  # type: ignore[arg-type]
            model_tier=model_tier,  # type: ignore[arg-type]
            function_category=function_category,
            explicit_search_intent=explicit_search_intent,
            explicit_save_intent=explicit_save_intent,
            search_query_hint=search_query_hint or None,
            route_score=round(route_score, 2),
            difficulty_score=round(difficulty_score, 2),
            complexity_score=round(complexity_score, 2),
            action_score=round(action_score, 2),
            security_risk_score=round(security_risk_score, 2),
            security_risk_level=security_risk_level,
            budget=budget,
            reason_codes=reason_codes,
            source_hint_present=bool(hint),
        )
        route = effective.model_dump()
        route_meta = {
            "risk_score": round(security_risk_score, 2),
            "difficulty_score": round(difficulty_score, 2),
            "intent_kind": function_category,
            "selected_tools": len(selected_tool_schemas),
            "memory_used": True,  # ContextBuilder is executed unconditionally before route execution.
        }
        route_debug_meta = {
            **route_meta,
            "route_band": route.get("route_band"),
            "model_tier": route.get("model_tier"),
            # Placeholders for future model-family routing visibility.
            "model_family_primary": str(getattr(self.request, "llm_preference", "") or "auto"),
            "model_family_fallback": "auto-fallback",
        }
        logger.info(
            "Core route decision",
            extra={
                "route_event": {
                    "run_id": self.run_id,
                    "mode": route.get("mode"),
                    "route_band": route.get("route_band"),
                    "route_score": route.get("route_score"),
                    "reason_codes": route.get("reason_codes", []),
                    "meta": route_meta,
                }
            },
        )
        if self._route_debug_enabled():
            route["route_debug"] = route_debug_meta
        else:
            route.pop("route_debug", None)
        return route

    async def run(self):
        """Execute the cognitive cycle."""
        effective_route: dict[str, Any] = {}
        budget_stop_reason: str | None = None
        run_started_at = time.monotonic()

        try:
            await self.repo.update_run_status(self.run_id, RunStatus.in_progress)

            user = await self.repo.get_or_create_user(
                self.request.user_identity.provider,
                self.request.user_identity.id,
                self.request.user_identity.display_name,
            )
            verified_admin = self._is_admin_verified()
            if self.request.client_context is not None:
                try:
                    self.request.client_context.is_admin = verified_admin
                except Exception:
                    pass

            context_messages = await ContextBuilder.build_context(self.request, user.id, self.conversation_id, self.repo)

            try:
                from pathlib import Path

                repo_root = Path(__file__).resolve().parents[4]
                soul_path = repo_root / "memory" / "soul.md"
                if soul_path.exists():
                    with open(soul_path, "r", encoding="utf-8") as f:
                        soul_content = f.read().strip()
                    if soul_content:
                        context_messages.insert(0, {"role": "system", "content": f"[SYSTEM IDENTITY]\n{soul_content}"})
            except Exception as e:
                logger.warning(f"Core Soul Injection Failed: {e}")

            client_type = getattr(self.request, "source", "web")
            selected_tool_schemas = self._resolve_selected_tools_for_core(client_type)
            if client_type == "discord" and selected_tool_schemas:
                self._register_missing_discord_proxy_tools(selected_tool_schemas)

            effective_route = self._resolve_effective_route(selected_tool_schemas)
            route_band = str(effective_route.get("route_band") or "task")
            model_tier = str(effective_route.get("model_tier") or self._tier_from_route_band(route_band))
            if effective_route.get("mode") == "INSTANT":
                selected_tool_schemas = []
            await self._persist_effective_route(effective_route)
            await event_manager.emit(self.run_id, "meta", {"effective_route": effective_route})

            if self._truthy_env("MODEL_REGISTRY_VERIFY_ON_STARTUP", False):
                get_model_registry(strict=self._truthy_env("MODEL_REGISTRY_STRICT", True))

            from ora_core.engine.omni_engine import omni_engine
            from ora_core.mcp.runner import ToolRunner

            runner = ToolRunner(self.repo)
            llm_pref = getattr(self.request, "llm_preference", None)
            route_budget = effective_route.get("budget") if isinstance(effective_route, dict) else {}
            if not isinstance(route_budget, dict):
                route_budget = {}
            max_turns = self._clamp_int(route_budget.get("max_turns"), 5, lo=1, hi=20)
            max_tool_calls = self._clamp_int(route_budget.get("max_tool_calls"), 0, lo=0, hi=20)
            time_budget_seconds = self._clamp_int(route_budget.get("time_budget_seconds"), 120, lo=10, hi=1800)
            pass_timeout_seconds = self._clamp_int(
                os.getenv("ORA_BAND2_PASS_TIMEOUT_SEC"),
                min(time_budget_seconds, 90),
                lo=10,
                hi=600,
            )

            def _tool_content(tool_data: Any) -> str:
                if isinstance(tool_data, str):
                    return tool_data
                if tool_data is None:
                    return ""
                try:
                    return json.dumps(tool_data, ensure_ascii=False)
                except Exception:
                    return str(tool_data)

            async def _run_generation_pass(pass_index: int, pass_label: str) -> tuple[str, str | None]:
                nonlocal budget_stop_reason
                started_at = time.monotonic()
                tool_calls_used = 0
                pass_final_text = ""
                last_content = ""
                search_attempt_made = False
                search_result_contract: dict[str, Any] | None = None
                pass_downloads: list[dict[str, Any]] = []
                explicit_search_intent = bool(effective_route.get("explicit_search_intent"))
                explicit_save_intent = bool(effective_route.get("explicit_save_intent"))
                search_query_hint = self._search_query_hint(effective_route)
                request_query = str(getattr(self.request, "content", "") or "").strip()
                save_clarification_allowed = self._clarification_allowed_before_save_export(
                    request_query,
                    explicit_save_intent=explicit_save_intent,
                )
                request_meta = self.request.request_meta.model_dump() if self.request.request_meta else None
                if explicit_save_intent and not save_clarification_allowed:
                    context_messages.append(
                        {
                            "role": "system",
                            "content": (
                                "[OUTPUT POLICY]\n"
                                "The user explicitly requested save/export/download. "
                                "If format is unspecified, choose the source-native/default format and proceed. "
                                "Only ask for clarification if required input is missing or constraints conflict."
                            ),
                        }
                    )
                elif not explicit_save_intent:
                    context_messages.append(
                        {
                            "role": "system",
                            "content": (
                                "[OUTPUT POLICY]\n"
                                "Unless the user explicitly requested save/export/download, "
                                "treat the request as a normal answer/action request. "
                                "Do not ask about save/export format."
                            ),
                        }
                    )

                for turn in range(max_turns):
                    if (time.monotonic() - started_at) >= float(time_budget_seconds):
                        budget_stop_reason = "router_budget_time_exceeded"
                        self._append_reason_code(effective_route, budget_stop_reason)
                        break

                    await self._emit_progress_event(
                        stage="search" if selected_tool_schemas else "compose",
                        pass_index=pass_index,
                    )
                    logger.info(
                        f"Run {self.run_id} Pass {pass_label} Turn {turn+1}: Generating response (Tier: {model_tier}, Pref: {llm_pref})..."
                    )
                    try:
                        generate_coro = self._generate_with_registry(
                            omni_engine=omni_engine,
                            messages=context_messages,
                            client_type=client_type,
                            tool_schemas=selected_tool_schemas,
                            route_band=str(effective_route.get("route_band") or route_band or "task"),
                            pass_index=pass_index,
                            llm_pref=llm_pref,
                        )
                        if pass_timeout_sec is not None:
                            response = await asyncio.wait_for(generate_coro, timeout=float(pass_timeout_sec))
                        else:
                            response = await generate_coro

                        usage_info = getattr(response, "usage", None)
                        if usage_info:
                            try:
                                exec_model = getattr(response, "model", "unknown")
                                lane = "optimization"
                                provider = "local"
                                low_model = str(exec_model).lower()
                                if any(k in low_model for k in ["gpt-", "o1", "o3", "o4"]):
                                    lane = "stable" if ("mini" in low_model or "instant" in low_model) else "high"
                                    provider = "openai"
                                elif "gemini" in low_model:
                                    lane = "burn"
                                    provider = "google"
                                elif "claude" in low_model:
                                    lane = "high"
                                    provider = "anthropic"

                                target_uid = self.request.user_identity.id
                                u_obj = Usage(tokens_in=usage_info.prompt_tokens, tokens_out=usage_info.completion_tokens)
                                self.cost_manager.add_cost(lane, provider, target_uid, u_obj)
                            except Exception as e:
                                logger.error(f"Failed to track cost: {e}")

                        message = response.choices[0].message
                        content = message.content or ""
                        last_content = content
                        tool_calls = message.tool_calls

                        if (
                            self._looks_like_save_export_clarification_only_response(content)
                            and not self._missing_referenced_input(request_query)
                        ):
                            if not explicit_save_intent and turn < (max_turns - 1):
                                self._append_reason_code(effective_route, "router_default_output_mode_applied")
                                context_messages.append(
                                    {
                                        "role": "system",
                                        "content": (
                                            "[OUTPUT POLICY]\n"
                                            "The user did not request save/export/download. "
                                            "Answer normally without asking about file format or download format."
                                        ),
                                    }
                                )
                                continue
                            if explicit_save_intent and not save_clarification_allowed and turn < (max_turns - 1):
                                self._append_reason_code(effective_route, "router_save_default_format_applied")
                                context_messages.append(
                                    {
                                        "role": "system",
                                        "content": (
                                            "[OUTPUT POLICY]\n"
                                            "Proceed with the default/source-native export format. "
                                            "Do not ask for format unless the request is contradictory."
                                        ),
                                    }
                                )
                                continue

                        if not tool_calls:
                            if (
                                explicit_search_intent
                                and not search_attempt_made
                                and not self._clarification_allowed_before_search(search_query_hint)
                            ):
                                if tool_calls_used >= max_tool_calls:
                                    budget_stop_reason = "router_budget_tool_exceeded"
                                    self._append_reason_code(effective_route, budget_stop_reason)
                                    pass_final_text = self._budget_stop_user_message(
                                        effective_route=effective_route,
                                        reason_code=budget_stop_reason,
                                    )
                                    context_messages.append({"role": "assistant", "content": pass_final_text})
                                    break

                                forced_tool_call_id, tool_payload, search_result_contract = await self._force_search_attempt(
                                    runner=runner,
                                    run_id=self.run_id,
                                    user_id=user.id,
                                    client_type=client_type,
                                    request_meta=request_meta,
                                    effective_route=effective_route,
                                    query=search_query_hint,
                                    pass_index=pass_index,
                                    tool_call_suffix=f"{turn + 1}",
                                )
                                search_attempt_made = True
                                tool_calls_used += 1
                                pass_downloads = self._dedupe_downloads(
                                    pass_downloads + self._extract_downloads_from_tool_payload(tool_payload=tool_payload)
                                )
                                context_messages.append(
                                    {
                                        "role": "tool",
                                        "tool_call_id": forced_tool_call_id,
                                        "name": "google_search",
                                        "content": _tool_content(tool_payload),
                                    }
                                )
                                if float(search_result_contract.get("confidence", 0.0) or 0.0) < 0.5:
                                    pass_final_text = self._format_search_no_match_response(
                                        query=search_query_hint,
                                        contract=search_result_contract,
                                    )
                                    context_messages.append({"role": "assistant", "content": pass_final_text})
                                    break

                                context_messages.append(
                                    {
                                        "role": "system",
                                        "content": (
                                            "[SEARCH-FIRST POLICY]\n"
                                            "A real public search pass has already been executed. "
                                            "Do not ask a clarification-only question. "
                                            "Summarize the searched results with concrete sources. "
                                            "If the match is weak, say that you searched but no confident match was found and list next actions."
                                        ),
                                    }
                                )
                                continue

                            if search_attempt_made and search_result_contract and self._looks_like_clarification_only_response(content):
                                confidence = float(search_result_contract.get("confidence", 0.0) or 0.0)
                                if confidence >= 0.5:
                                    pass_final_text = self._format_search_summary_fallback(
                                        query=search_query_hint,
                                        contract=search_result_contract,
                                    )
                                else:
                                    pass_final_text = self._format_search_no_match_response(
                                        query=search_query_hint,
                                        contract=search_result_contract,
                                    )
                            else:
                                pass_final_text = content
                            context_messages.append({"role": "assistant", "content": pass_final_text})
                            break
                    except asyncio.TimeoutError:
                        self._append_reason_code(effective_route, "core_timeout")
                        await self.repo.update_run_status(self.run_id, RunStatus.failed)
                        await self._persist_effective_route(effective_route)
                        await event_manager.emit(
                            self.run_id,
                            "error",
                            {
                                "error_code": "core_timeout",
                                "user_safe_message": self._safe_user_message_for_error("core_timeout"),
                            },
                        )
                        return
                    context_messages.append(message)
                    for tc in tool_calls:
                        if (time.monotonic() - started_at) >= float(time_budget_seconds):
                            budget_stop_reason = "router_budget_time_exceeded"
                            self._append_reason_code(effective_route, budget_stop_reason)
                            break
                        if tool_calls_used >= max_tool_calls:
                            budget_stop_reason = "router_budget_tool_exceeded"
                            self._append_reason_code(effective_route, budget_stop_reason)
                            break

                        tc_id = tc.id
                        t_name = tc.function.name
                        try:
                            t_args = json.loads(tc.function.arguments or "{}")
                        except json.JSONDecodeError as e:
                            logger.warning(
                                f"Tool {t_name} (ID: {tc_id}): Invalid JSON arguments: {e}. args={tc.function.arguments!r}"
                            )
                            context_messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tc_id,
                                    "name": t_name,
                                    "content": _tool_content({"ok": False, "error": f"Invalid arguments JSON: {str(e)}"}),
                                }
                            )
                            continue
                        except Exception as e:
                            logger.warning(
                                f"Tool {t_name} (ID: {tc_id}): Failed to parse arguments. err={e} args={tc.function.arguments!r}"
                            )
                            context_messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tc_id,
                                    "name": t_name,
                                    "content": _tool_content({"ok": False, "error": f"Failed to parse arguments: {str(e)}"}),
                                }
                            )
                            continue

                        result = await runner.run_tool(
                            tc_id,
                            self.run_id,
                            user.id,
                            t_name,
                            t_args,
                            client_type,
                            request_meta=request_meta,
                            effective_route=effective_route,
                        )

                        if isinstance(result, dict):
                            tool_data = result.get("result") if result.get("result") is not None else result.get("error")
                        else:
                            tool_data = result
                        if t_name == "google_search":
                            tool_data, search_result_contract = self._normalize_search_tool_payload(
                                query=str(t_args.get("query") or search_query_hint or ""),
                                tool_payload=tool_data,
                            )
                        dispatched_externally = (
                            client_type == "discord"
                            and isinstance(result, dict)
                            and isinstance(result.get("result"), dict)
                            and "client_action" in result.get("result", {})
                        )
                        if dispatched_externally:
                            submitted = None
                            await self._emit_progress("deliver", pass_index, [f"tool:{t_name}"])
                            try:
                                submitted = await event_manager.wait_for_tool_result(self.run_id, tc_id, timeout_sec=180)
                                tool_data = submitted.get("result", "[Success]")
                            except asyncio.TimeoutError:
                                tool_data = {
                                    "ok": False,
                                    "error": {
                                        "code": "CLIENT_RESULT_TIMEOUT",
                                        "message": f"Timed out waiting for client result: {t_name}",
                                    },
                                }
                            except asyncio.CancelledError:
                                tool_data = {
                                    "ok": False,
                                    "error": {
                                        "code": "CLIENT_RESULT_CANCELLED",
                                        "message": f"Client result wait cancelled: {t_name}",
                                    },
                                }

                        artifact_ref = result.get("artifact_ref") if isinstance(result, dict) else None
                        if dispatched_externally and isinstance(submitted, dict):
                            artifact_ref = submitted.get("artifact_ref") or artifact_ref
                        pass_downloads = self._dedupe_downloads(
                            pass_downloads
                            + self._extract_downloads_from_tool_payload(
                                tool_payload=tool_data,
                                artifact_ref=artifact_ref,
                            )
                        )

                        context_messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tc_id,
                                "name": t_name,
                                "content": _tool_content(tool_data),
                            }
                        )
                        if self._extract_search_sources(tool_data):
                            search_attempt_made = True
                            search_result_contract = self._build_search_result_contract(
                                query=search_query_hint or str(t_args.get("query") or ""),
                                sources=self._extract_search_sources(tool_data),
                            )
                        tool_calls_used += 1
                    if budget_stop_reason:
                        break
                else:
                    budget_stop_reason = "router_budget_turn_exceeded"
                    self._append_reason_code(effective_route, budget_stop_reason)
                    pass_final_text = last_content.strip() or self._budget_stop_user_message(
                        effective_route=effective_route,
                        reason_code=budget_stop_reason,
                    )

                if budget_stop_reason and not pass_final_text.strip():
                    pass_final_text = last_content.strip() or self._budget_stop_user_message(
                        effective_route=effective_route,
                        reason_code=budget_stop_reason,
                    )
                return pass_final_text, budget_stop_reason, pass_downloads

            plan_toc = ["draft", "critique_patch", "deliver"] if route_band == "agent" else ["draft", "deliver"]
            await self._emit_progress_event(stage="plan", pass_index=1, toc=plan_toc)
            await self._emit_progress_event(stage="memory", pass_index=1)

            if route_band == "agent":
                try:
                    final_response_text, budget_stop_reason, final_downloads = await asyncio.wait_for(
                        _run_generation_pass(pass_index=1, pass_label="draft"),
                        timeout=float(pass_timeout_seconds),
                    )
                except asyncio.TimeoutError:
                    await self.repo.update_run_status(self.run_id, RunStatus.failed)
                    await self._persist_effective_route(effective_route)
                    await event_manager.emit(
                        self.run_id,
                        "error",
                        {
                            "error_code": "core_timeout",
                            "user_safe_message": self._safe_user_message_for_error("core_timeout"),
                        },
                    )
                    trace_event(
                        "core.run.metrics",
                        run_id=self.run_id,
                        route_band=route_band,
                        model_tier=model_tier,
                        total_ms=int((time.monotonic() - run_started_at) * 1000),
                        budget_stop=False,
                        status="failed",
                        error_code="core_timeout",
                    )
                    return
            else:
                final_response_text, budget_stop_reason, final_downloads = await _run_generation_pass(pass_index=1, pass_label="draft")

            if route_band == "agent":
                await self._emit_progress_event(stage="compose", pass_index=2, toc=["critique_patch"])
                critique_prompt = (
                    "You are in critique_patch pass. Improve clarity and correctness while preserving intent. "
                    "Return only the final revised answer text."
                )
                critique_messages = list(context_messages)
                critique_messages.append({"role": "assistant", "content": final_response_text})
                critique_messages.append({"role": "system", "content": critique_prompt})

                try:
                    critique_response = await asyncio.wait_for(
                        self._generate_with_registry(
                            omni_engine=omni_engine,
                            messages=critique_messages,
                            client_type=client_type,
                            tool_schemas=None,
                            route_band=route_band,
                            pass_index=2,
                            llm_pref=llm_pref,
                        ),
                        timeout=float(pass_timeout_seconds),
                    )
                except asyncio.TimeoutError:
                    await self.repo.update_run_status(self.run_id, RunStatus.failed)
                    await self._persist_effective_route(effective_route)
                    await event_manager.emit(
                        self.run_id,
                        "error",
                        {
                            "error_code": "core_timeout",
                            "user_safe_message": self._safe_user_message_for_error("core_timeout"),
                        },
                    )
                    trace_event(
                        "core.run.metrics",
                        run_id=self.run_id,
                        route_band=route_band,
                        model_tier=model_tier,
                        total_ms=int((time.monotonic() - run_started_at) * 1000),
                        budget_stop=bool(budget_stop_reason),
                        status="failed",
                        error_code="core_timeout",
                    )
                    return

                try:
                    revised = str(critique_response.choices[0].message.content or "").strip()
                except Exception:
                    revised = ""
                if revised:
                    final_response_text = revised

            await self._emit_progress_event(stage="deliver", pass_index=2 if route_band == "agent" else 1)

            await self.repo.create_assistant_message(self.conversation_id, final_response_text)
            try:
                await self._update_memory_on_completion(user.id, self.request.content, final_response_text)
            except Exception as e:
                logger.error(f"Memory update failed (non-fatal): {e}\n{traceback.format_exc()}")

            await self._persist_effective_route(effective_route)
            final_payload: dict[str, Any] = {"output_text": final_response_text}
            if final_downloads:
                final_payload["downloads"] = self._dedupe_downloads(final_downloads)
            await event_manager.emit(self.run_id, "final", final_payload)
            await self.repo.update_run_status(self.run_id, RunStatus.completed)
            trace_event(
                "core.run.metrics",
                run_id=self.run_id,
                route_band=route_band,
                model_tier=model_tier,
                total_ms=int((time.monotonic() - run_started_at) * 1000),
                budget_stop=bool(budget_stop_reason),
                status="completed",
            )

        except Exception as e:
            logger.error(f"MainProcess Error: {e}", exc_info=True)
            await self.repo.update_run_status(self.run_id, RunStatus.failed)
            await self._persist_effective_route(effective_route)
            await event_manager.emit(
                self.run_id,
                "error",
                {
                    "error_code": "core_runtime_error",
                    "user_safe_message": self._safe_user_message_for_error("core_runtime_error"),
                },
            )
            trace_event(
                "core.run.metrics",
                run_id=self.run_id,
                route_band=str(effective_route.get("route_band") or "task"),
                model_tier=str(effective_route.get("model_tier") or "balanced"),
                total_ms=int((time.monotonic() - run_started_at) * 1000),
                budget_stop=bool(budget_stop_reason),
                status="failed",
                error_code="core_runtime_error",
            )

    def _resolve_selected_tools_for_core(self, client_type: str) -> list[dict[str, Any]]:
        """
        Resolve client-selected tool schemas to an executable subset for Core.
        - Keeps only tools registered in Core and allowed for the current client_type.
        - Preserves router-selected order to keep behavior stable.
        """
        from ora_core.mcp.registry import tool_registry

        requested = getattr(self.request, "available_tools", None) or []
        if not requested:
            return []

        allowed_defs = {t.name: t for t in tool_registry.list_tools_for_client(client_type)}
        resolved: list[dict[str, Any]] = []
        seen: set[str] = set()

        for tool in requested:
            if not isinstance(tool, dict):
                continue
            name = tool.get("name")
            if not isinstance(name, str) or name in seen:
                continue
            if name in allowed_defs:
                definition = allowed_defs[name]
                params = tool.get("parameters") if isinstance(tool.get("parameters"), dict) else definition.parameters
                desc = tool.get("description") if isinstance(tool.get("description"), str) else definition.description
                resolved.append({"name": name, "description": desc, "parameters": params})
            elif client_type == "discord":
                # For Discord, allow client-selected tools to be auto-proxied to Bot ToolHandler.
                params = tool.get("parameters") if isinstance(tool.get("parameters"), dict) else {"type": "object", "properties": {}}
                desc = (
                    tool.get("description")
                    if isinstance(tool.get("description"), str)
                    else f"Dispatch '{name}' to Discord client tool handler."
                )
                resolved.append({"name": name, "description": desc, "parameters": params})
            seen.add(name)

        return resolved

    def _register_missing_discord_proxy_tools(self, selected_tools: list[dict[str, Any]]) -> None:
        """
        Register missing Discord tools as lightweight proxy tools so Core can dispatch
        router-selected client capabilities without hardcoding every tool in Core.
        """
        import re

        from ora_core.mcp.registry import ToolDefinition, tool_registry

        async def dynamic_discord_proxy(args: dict, context: dict) -> dict[str, Any]:
            return {
                "ok": True,
                "content": [{"type": "text", "text": "Dispatching action to Discord client..."}],
                "client_action": args,
            }

        valid_name = re.compile(r"^[a-zA-Z0-9_\\-]{1,64}$")
        for tool in selected_tools:
            name = tool.get("name")
            if not isinstance(name, str) or not valid_name.match(name):
                continue
            if tool_registry.get_definition(name):
                continue
            params = tool.get("parameters") if isinstance(tool.get("parameters"), dict) else {"type": "object", "properties": {}}
            desc = tool.get("description") if isinstance(tool.get("description"), str) else f"Discord proxy for {name}"
            tool_registry.register_tool(
                ToolDefinition(
                    name=name,
                    description=desc,
                    parameters=params,
                    allowed_clients=["discord"],
                ),
                dynamic_discord_proxy,
            )

    async def _update_memory_on_completion(self, user_id: str, user_text: str, assistant_text: str):
        """Append to Raw Logs (L4) and trigger background summarization (L3)."""
        # Keep the memory file ID consistent with ContextBuilder (guild-scoped for Discord).
        target_memory_id = user_id
        if self.request.user_identity.provider == "discord":
            guild_id = None
            try:
                if self.request.client_context and getattr(self.request.client_context, "guild_id", None):
                    guild_id = self.request.client_context.guild_id
            except Exception:
                guild_id = None
            if guild_id:
                target_memory_id = f"{self.request.user_identity.id}_{guild_id}_public"
            else:
                target_memory_id = self.request.user_identity.id

        profile = await memory_store.get_or_create_profile(
            target_memory_id,
            default_name=self.request.user_identity.display_name or "User",
        )

        # L4: Raw Logs
        if "layer4_raw_logs" not in profile:
            profile["layer4_raw_logs"] = []

        profile["layer4_raw_logs"].append(
            {
                "timestamp": datetime.now().isoformat(),
                "user": user_text,
                "assistant": assistant_text,
            }
        )
        profile["last_updated"] = datetime.now().isoformat()

        # Atomic Save
        await memory_store.save_user_profile(target_memory_id, profile)
