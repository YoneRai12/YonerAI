from __future__ import annotations


from src.utils.access_control import filter_tool_schemas_for_user, is_tool_allowed


class _Cfg:
    def __init__(self, *, admin_user_id: int, profile: str = "private", sub_admin_ids=None):
        self.admin_user_id = admin_user_id
        self.profile = profile
        self.sub_admin_ids = set(sub_admin_ids or [])


class _Bot:
    def __init__(self, cfg: _Cfg):
        self.config = cfg


def test_public_tools_allow_everyday_features_for_non_owner() -> None:
    bot = _Bot(_Cfg(admin_user_id=999, profile="private"))
    user_id = 123

    for tool in [
        "music_play",
        "music_control",
        "music_queue",
        "music_stop",
        "tts_speak",
        "join_voice_channel",
        "leave_voice_channel",
        "web_search_api",
        "read_web_page",
    ]:
        assert is_tool_allowed(bot, user_id, tool) is True

    # Dangerous tools should stay locked down by default.
    assert is_tool_allowed(bot, user_id, "web_download") is False
    assert is_tool_allowed(bot, user_id, "system_control") is False


def test_shared_profile_falls_back_to_public_allowlist_when_explicit_not_set(monkeypatch) -> None:
    monkeypatch.delenv("ORA_SHARED_GUEST_ALLOWED_TOOLS", raising=False)
    monkeypatch.delenv("ORA_PUBLIC_TOOLS", raising=False)

    bot = _Bot(_Cfg(admin_user_id=999, profile="shared"))
    user_id = 123
    assert is_tool_allowed(bot, user_id, "music_play") is True
    assert is_tool_allowed(bot, user_id, "web_download") is False


def test_filter_tool_schemas_for_user_filters_to_allowlist() -> None:
    bot = _Bot(_Cfg(admin_user_id=999, profile="private"))
    user_id = 123
    tools = [
        {"name": "music_play"},
        {"name": "web_search_api"},
        {"name": "web_download"},
    ]
    filtered = filter_tool_schemas_for_user(bot=bot, user_id=user_id, tools=tools)
    names = {t["name"] for t in filtered}
    assert "music_play" in names
    assert "web_search_api" in names
    assert "web_download" not in names

