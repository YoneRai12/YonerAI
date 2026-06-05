from __future__ import annotations

from typing import Iterable


def format_context_screen(*, lang: str) -> str:
    lines = _context_lines_ja() if lang == "ja" else _context_lines_en()
    return "\n".join(lines)


def _context_lines_ja() -> Iterable[str]:
    return (
        "コンテキスト",
        "  YonerAI が参照してよい文脈を確認します。ここでは本文の自動読み込みはしません。",
        "",
        "使える参照",
        "  @planner <内容>      計画担当の安全なプレビュー",
        "  @reviewer <内容>     レビュー担当の安全なプレビュー",
        "  @researcher <内容>   調査担当の安全なプレビュー",
        "  @implementer <内容>  実装担当の安全なプレビュー（実行なし）",
        "  @tester <内容>       テスト担当の安全なプレビュー（実行なし）",
        "  /記憶 list           ローカル記憶のIDと秘匿済み要約を確認",
        "  /履歴                run_idと秘匿済みタスク要約を確認",
        "  /表示 <run_id>       秘匿済みの実行要約だけ表示",
        "  /入力                入力欄と補完候補の使い方を確認",
        "  /進行                実行前後の進行表示を確認",
        "",
        "まだ自動投入しないもの",
        "  @file は未実装です。ファイル本文を勝手に読みません。",
        "  ローカル絶対パス、秘密情報、private memory、local node内容はcloud候補へ渡しません。",
        "  外部URLや内部endpointを文脈として自動取得しません。",
        "",
        "次に使うコマンド",
        "  /計画 <内容>",
        "  /レビュー <内容>",
        "  /記憶 list",
        "  /権限",
        "",
    )


def _context_lines_en() -> Iterable[str]:
    return (
        "Context",
        "  Review which references YonerAI may use. This screen does not auto-load raw content.",
        "",
        "Supported references",
        "  @planner <text>      Public-safe planner preview",
        "  @reviewer <text>     Public-safe reviewer preview",
        "  @researcher <text>   Public-safe researcher preview",
        "  @implementer <text>  Public-safe implementer preview, no execution",
        "  @tester <text>       Public-safe tester preview, no execution",
        "  /memory list         Inspect local memory IDs and redacted summaries",
        "  /runs                Inspect run IDs and redacted task summaries",
        "  /show <run_id>       Show redacted run summary",
        "  /composer            Inspect input composer and completion help",
        "  /progress            Inspect execution progress display",
        "",
        "Not auto-loaded yet",
        "  @file is not implemented. File bodies are not read automatically.",
        "  Local absolute paths, secrets, private memory, and local node content are not sent to cloud candidates.",
        "  External URLs and internal endpoints are not fetched as context automatically.",
        "",
        "Next commands",
        "  /plan <text>",
        "  /review <text>",
        "  /memory list",
        "  /permissions",
        "",
    )
