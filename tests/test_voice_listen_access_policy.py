from types import SimpleNamespace

from src.utils.access_control import can_use_voice_listen


def test_voice_listen_policy_rejects_non_owner() -> None:
    bot = SimpleNamespace(config=SimpleNamespace(admin_user_id=12345))

    assert can_use_voice_listen(bot, 99999) is False


def test_voice_listen_policy_allows_owner() -> None:
    bot = SimpleNamespace(config=SimpleNamespace(admin_user_id=12345))

    assert can_use_voice_listen(bot, 12345) is True


def test_voice_listen_policy_denies_missing_identity() -> None:
    bot = SimpleNamespace(config=SimpleNamespace(admin_user_id=12345))

    assert can_use_voice_listen(bot, None) is False
