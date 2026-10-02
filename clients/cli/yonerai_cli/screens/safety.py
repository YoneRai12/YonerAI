from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from yonerai_cli.config import build_config_report
from yonerai_cli.screens.labels import _approval_label, _selector


def format_safety_screen(lines: Iterable[str]) -> str:
    """Render safety screens from precomputed display lines."""

    return "\n".join(lines)


def _format_safety(config: dict[str, object], *, live: bool, lang: str) -> str:
    values = build_config_report(config, exists=True)["config"]
    if lang == "ja":
        network_selected = "provider" if live else "off"
        file_selected = str(values["file_access_mode"])
        tools_selected = str(values["tools_mode"])
        return format_safety_screen(
            (
                "安全設定",
                "",
                "ネットワーク（外部通信）",
                f"{_selector('off', network_selected)} オフ（初期値）",
                f"{_selector('provider', network_selected)} 提供元のみ許可（--liveで明示した時だけ）",
                f"{_selector('search', network_selected)} 検索を許可（未実装）",
                "",
                "ファイルアクセス（ファイル読み取り）",
                f"{_selector('workspace_only', file_selected)} ワークスペース内のみ",
                f"{_selector('disabled', file_selected)} 無効",
                f"{_selector('ask', file_selected)} 毎回確認（未実装）",
                "",
                "ツール（操作機能）",
                f"{_selector('dry_run', tools_selected)} ドライランのみ（計画だけ）",
                f"{_selector('diagnostics', tools_selected)} 安全診断のみ許可（限定）",
                f"{_selector('disabled', tools_selected)} 無効",
                "",
                f"承認（危険操作）: {_approval_label(values['approval_mode'], lang='ja')}",
                f"履歴記録（ローカル履歴）: {'オン（秘匿済み / ローカルのみ）' if values.get('ledger_enabled') else 'オフ'}",
                "シェル実行（PC操作）: 任意コマンドは無効",
                "クラウド候補: 非公開ファイルやローカルファイルは送りません",
                "ライブ提供元: 明示許可と provider 別 env opt-in が必要です",
                "",
            )
        )
    return format_safety_screen(
        (
            "Safety",
            f"  network: {'explicitly enabled' if values['network_enabled'] else 'off'}",
            f"  live provider: {'explicitly enabled' if live else 'off'}",
            f"  tools: {values['tools_mode']}",
            f"  file access: {values['file_access_mode']}",
            f"  approval: {values['approval_mode']}",
            f"  ledger: {'on' if values.get('ledger_enabled') else 'off'}",
            "  shell: arbitrary shell disabled",
            "  cloud: private/local files never sent to cloud candidates",
            "",
        )
    )
