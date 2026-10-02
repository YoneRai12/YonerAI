from __future__ import annotations

import re
import threading
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from typing import Optional


PUBLIC_SESSION_MAX_ID_LENGTH = 120
PUBLIC_SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,119}$")
PUBLIC_SESSION_MAX_ENTRIES = 1024


class ConversationSessionError(ValueError):
    """Raised when public session metadata cannot be accepted safely."""


@dataclass(frozen=True)
class ConversationSessionState:
    session_id: str
    conversation_id: str
    turn_index: int
    history_count: int
    memory_persisted: bool = False


def normalize_public_session_id(session_id: Optional[str], conversation_id: str) -> str:
    raw_session_id = (session_id or "").strip()
    if not raw_session_id:
        raw_session_id = f"session-{uuid.uuid4().hex[:16]}"

    if len(raw_session_id) > PUBLIC_SESSION_MAX_ID_LENGTH or not PUBLIC_SESSION_ID_PATTERN.fullmatch(
        raw_session_id
    ):
        raise ConversationSessionError(
            "session_id must start with an ASCII letter or digit and may only contain letters, digits, dot, colon, underscore, or hyphen."
        )

    return raw_session_id


class PublicConversationSessionStore:
    """Small in-memory counter store for the public session scaffold.

    This intentionally stores metadata only. Message content is not persisted,
    and process restart clears all state.
    """

    def __init__(self, *, max_entries: int = PUBLIC_SESSION_MAX_ENTRIES) -> None:
        if max_entries < 1:
            raise ValueError("max_entries must be at least 1")
        self._max_entries = max_entries
        self._lock = threading.Lock()
        self._sessions: OrderedDict[str, ConversationSessionState] = OrderedDict()

    def record_turn(self, *, session_id: Optional[str], conversation_id: str) -> ConversationSessionState:
        normalized_session_id = normalize_public_session_id(session_id, conversation_id)
        with self._lock:
            existing = self._sessions.get(normalized_session_id)
            if existing and existing.conversation_id != conversation_id:
                raise ConversationSessionError(
                    "session_id is already associated with a different conversation_id in this process."
                )
            if existing:
                self._sessions.move_to_end(normalized_session_id)

            next_turn = 1 if existing is None else existing.turn_index + 1
            state = ConversationSessionState(
                session_id=normalized_session_id,
                conversation_id=conversation_id,
                turn_index=next_turn,
                history_count=next_turn,
                memory_persisted=False,
            )
            self._sessions[normalized_session_id] = state
            if len(self._sessions) > self._max_entries:
                self._sessions.popitem(last=False)
            return state

    def clear(self) -> None:
        with self._lock:
            self._sessions.clear()


_PUBLIC_CONVERSATION_SESSION_STORE = PublicConversationSessionStore()


def get_public_conversation_session_store() -> PublicConversationSessionStore:
    return _PUBLIC_CONVERSATION_SESSION_STORE


def reset_public_conversation_session_store() -> None:
    _PUBLIC_CONVERSATION_SESSION_STORE.clear()
