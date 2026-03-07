from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib
import math
import re
from typing import Iterable


_VECTOR_DIMENSIONS = 256
_LOW_CONFIDENCE_THRESHOLD = 0.28
_MIN_MARGIN = 0.015

_INTENT_PROTOTYPES: dict[str, tuple[str, ...]] = {
    "generic_image_overview": (
        "この画像を説明して。まず何の画面か、次に主要な領域、最後に細部を説明して。",
        "このスクリーンショットに何が映っているか、全体構造から順に説明して。",
        "What is shown in this screenshot? Describe the full screen first, then the main focus.",
    ),
    "focused_image_question": (
        "CPUのところだけ説明して。",
        "この部分だけ詳しく見て。",
        "Focus only on one area or field in the image.",
    ),
    "image_followup": (
        "続き。さっきの画像についてさらに説明して。",
        "この画像をもっと詳しく見て。",
        "Keep talking about the previous image without asking to resend it.",
    ),
    "save_export_intent": (
        "この結果をPDFで保存して。",
        "ダウンロードしたい。",
        "Export this result as a file and let me save it.",
    ),
}

_ASCII_TOKEN_RE = re.compile(r"[a-z0-9_./:-]{2,}", re.IGNORECASE)
_JAPANESE_CHUNK_RE = re.compile(r"[ぁ-んァ-ヶ一-龯ー]{2,}")


@dataclass(frozen=True)
class SemanticIntentResult:
    scores: dict[str, float]
    top_intent: str
    top_score: float
    margin: float
    low_confidence: bool
    generic_image_overview: bool
    focused_image_question: bool
    image_followup: bool
    save_export_intent: bool


def has_explicit_export_constraint(text: str) -> bool:
    normalized = _normalize_text(text)
    if not normalized:
        return False

    verb_markers = (
        "save",
        "download",
        "export",
        "保存",
        "ダウンロード",
        "書き出し",
        "エクスポート",
    )
    format_markers = (
        "pdf",
        "png",
        "jpg",
        "jpeg",
        "webp",
        "mp3",
        "mp4",
        "wav",
        "zip",
        "csv",
        "xlsx",
        "docx",
    )
    return any(marker in normalized for marker in verb_markers) or any(
        marker in normalized for marker in format_markers
    )


def classify_semantic_intent(
    text: str,
    *,
    has_current_image: bool = False,
    has_prior_image: bool = False,
    has_client_history: bool = False,
    has_explicit_export_constraint: bool = False,
) -> SemanticIntentResult:
    followup_reference = _has_followup_reference(text)
    scores = _base_similarity_scores(text)
    adjusted = dict(scores)

    if has_current_image:
        adjusted["generic_image_overview"] += 0.12
        adjusted["focused_image_question"] += 0.12
        adjusted["image_followup"] -= 0.02
    if has_prior_image and not has_current_image:
        adjusted["image_followup"] += 0.24
    if has_client_history and not has_current_image:
        adjusted["image_followup"] += 0.08
    if followup_reference and not has_current_image:
        adjusted["image_followup"] += 0.12
    if has_explicit_export_constraint:
        adjusted["save_export_intent"] += 0.18

    ranked = sorted(adjusted.items(), key=lambda item: item[1], reverse=True)
    top_intent, top_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0
    margin = top_score - second_score
    low_confidence = top_score < _LOW_CONFIDENCE_THRESHOLD or margin < _MIN_MARGIN

    generic_overview = (
        adjusted["generic_image_overview"] >= 0.30
        and adjusted["generic_image_overview"] >= adjusted["focused_image_question"]
        and not low_confidence
    )
    focused_question = (
        adjusted["focused_image_question"] >= 0.30
        and adjusted["focused_image_question"] > adjusted["generic_image_overview"] + 0.01
        and not low_confidence
    )
    image_followup = (
        has_prior_image
        and not has_current_image
        and top_intent == "image_followup"
        and (has_client_history or followup_reference)
        and adjusted["image_followup"] >= 0.28
        and (not low_confidence or has_client_history)
    )
    save_export = (
        adjusted["save_export_intent"] >= 0.36
        and not low_confidence
    )

    if low_confidence:
        generic_overview = False
        focused_question = False
        image_followup = False
        save_export = False

    return SemanticIntentResult(
        scores=adjusted,
        top_intent=top_intent,
        top_score=top_score,
        margin=margin,
        low_confidence=low_confidence,
        generic_image_overview=generic_overview,
        focused_image_question=focused_question,
        image_followup=image_followup,
        save_export_intent=save_export,
    )


def _base_similarity_scores(text: str) -> dict[str, float]:
    vec = _embed_text(text)
    scores: dict[str, float] = {}
    for intent_name, proto_vecs in _prototype_vectors().items():
        similarities = [_cosine_similarity(vec, proto_vec) for proto_vec in proto_vecs]
        scores[intent_name] = max(similarities) if similarities else 0.0
    return scores


@lru_cache(maxsize=1)
def _prototype_vectors() -> dict[str, tuple[tuple[float, ...], ...]]:
    return {
        intent_name: tuple(_embed_text(proto) for proto in prototypes)
        for intent_name, prototypes in _INTENT_PROTOTYPES.items()
    }


def _embed_text(text: str) -> tuple[float, ...]:
    vec = [0.0] * _VECTOR_DIMENSIONS
    for token in _iter_semantic_tokens(text):
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        bucket = int.from_bytes(digest[:4], "big") % _VECTOR_DIMENSIONS
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vec[bucket] += sign

    norm = math.sqrt(sum(value * value for value in vec))
    if norm <= 0:
        return tuple(0.0 for _ in vec)
    return tuple(value / norm for value in vec)


def _cosine_similarity(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _iter_semantic_tokens(text: str) -> Iterable[str]:
    normalized = _normalize_text(text)
    if not normalized:
        return ()

    tokens: list[str] = []
    for match in _ASCII_TOKEN_RE.finditer(normalized):
        token = match.group(0)
        tokens.append(token)
        tokens.extend(_ngrams(token, min_n=3, max_n=4))

    for match in _JAPANESE_CHUNK_RE.finditer(normalized):
        token = match.group(0)
        tokens.append(token)
        tokens.extend(_ngrams(token, min_n=2, max_n=3))

    if not tokens:
        tokens.append(normalized)
    return tokens


def _normalize_text(text: str) -> str:
    normalized = str(text or "").strip().lower()
    normalized = re.sub(r"<@!?\d+>", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def _has_followup_reference(text: str) -> bool:
    normalized = _normalize_text(text)
    if not normalized:
        return False

    markers = (
        "続き",
        "この画像",
        "この画面",
        "このスクリーンショット",
        "これ",
        "ここ",
        "しっかり見て",
        "詳しく見て",
        "continue",
        "follow up",
        "more",
    )
    return any(marker in normalized for marker in markers)


def _ngrams(token: str, *, min_n: int, max_n: int) -> list[str]:
    out: list[str] = []
    for n in range(min_n, max_n + 1):
        if len(token) < n:
            continue
        out.extend(token[idx : idx + n] for idx in range(0, len(token) - n + 1))
    return out
