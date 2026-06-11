from __future__ import annotations

from yonerai_cli.config import ConfigError
from yonerai_cli.screens.labels import _safe


def _help(lang: str) -> str:
    if lang == "ja":
        return "\n".join(
            (
                "コマンド",
                "  /状態                 状態ヘッダーをもう一度表示する",
                "  /ホーム               状態ヘッダーをもう一度表示する",
                "  /コマンド             コマンドパレットを表示する",
                "  /入力                 入力欄と補完の使い方を見る",
                "  /設定                 設定を見る",
                "  /モード 計画|安全実行|レビュー|記憶",
                "  /計画                 読み取り専用の計画モードにする",
                "  /レビュー             レビュー優先モードにする",
                "  /権限                 承認と権限の状態を見る",
                "  /モデル               モデルとローカルLLMの設定を見る",
                "  /提供元               提供元（AI接続元）を見る",
                "  /安全                 安全境界を見る",
                "  /ポリシー             提供元・権限・更新・記憶の方針を見る",
                "  /進行                 実行前後の進行表示を見る",
                "  /タスク               現在/最近のタスク進行を見る",
                "  /エージェント         計画中の担当（計画担当・レビュー担当など）を見る",
                "  /コンテキスト         参照できる文脈と禁止境界を見る",
                "  /履歴                 実行履歴を見る",
                "  /表示 <実行ID>        1件の実行を見る",
                "  /ローカルLLM          PC内モデルの接続方法を見る",
                "  /ログイン             ステージングGoogleログイン案内を見る",
                "  /認証                 Google OAuthドライラン状態を見る",
                "  /セッション           CLIセッションを見る",
                "  /プロジェクト         現在のプロジェクトを見る",
                "  /API                  公式API接続状態を見る",
                "  /レート               APIレート制限を見る",
                "  /監査                 公開安全な監査メタデータを見る",
                "  /同期                 cloud/local同期境界を見る",
                "  /プライバシー         共有とプライバシー境界を見る",
                "  /自己進化             proposal-only自己進化キューを見る",
                "  /更新                 安定版/ベータ版の更新確認を選ぶ",
                "  /更新通知 オン|オフ   起動時の更新案内設定を変更",
                "  /言語 日本語|英語     表示言語を変更",
                "  /提供元選択 自動|モック|ローカル|OpenAI互換|Anthropic|Gemini",
                "  /承認 確認|拒否       危険操作の扱いを変更",
                "  /ファイル ワークスペース内のみ|無効",
                "  /履歴記録 オン|オフ   秘匿済みローカル履歴の記録を変更",
                "  /ライブ接続 オン|オフ 外部/ローカル実行の明示許可を変更",
                "  /ネットワーク オン|オフ 外部通信の明示許可を変更",
                "  /選択 <番号> <値>      設定画面の番号で変更",
                "  /終了                 終了",
                "",
            )
        )
    return "\n".join(
        (
            "Commands",
            "  /status          Show the Mission Control status header again",
            "  /home            Show the Mission Control status header again",
            "  /palette         Show command palette",
            "  /composer        Show input composer and completion help",
            "  /settings        Show settings",
            "  /mode plan|build|review|memory Change agent mode",
            "  /plan            Switch to read-only planning mode",
            "  /review          Switch to review mode",
            "  /permissions     Show approval and permission policy",
            "  /models          Show model and local LLM setup",
            "  /providers       Show provider status",
            "  /safety          Show safety boundaries",
            "  /policy          Show runtime policy state",
            "  /progress        Show progress panel",
            "  /tasks           Show current/recent task progress",
            "  /agents          Show planned agent/reviewer roles",
            "  /context         Show safe context references",
            "  /runs            Show run history",
            "  /show <run_id>   Show one run",
            "  /local-llm       Show local LLM loopback setup",
            "  /login           Show staging Google login guidance",
            "  /auth            Show Google OAuth dry-run status",
            "  /sessions        Show CLI sessions",
            "  /project         Show current project",
            "  /api             Show official API status",
            "  /rate-limit      Show API rate limit",
            "  /audit           Show sanitized audit metadata",
            "  /sync            Show cloud/local sync boundaries",
            "  /privacy         Show shared-traffic and private-content policy",
            "  /evolve          Show proposal-only self-evolution queue",
            "  /update          Check local manifest update status",
            "  /update-notice on|off Toggle startup update notice setting",
            "  /language ja|en  Change language",
            "  /provider auto|mock|local|openai-compatible|anthropic|gemini",
            "  /ledger on|off    Toggle redacted local ledger",
            "  /live on|off      Toggle explicit live/local execution permission",
            "  /network on|off   Toggle explicit network permission",
            "  /select <n> <value> Change a numbered setting",
            "  /quit            Exit",
            "",
        )
    )


def _non_tty_fallback(lang: str) -> str:
    if lang == "ja":
        return "\n".join(
            (
                "YonerAI Interactive CLI",
                "この入力はTTYではないため、対話画面は起動しません。",
                "対話で使う: yonerai",
                "明示して使う: yonerai chat",
                "スクリプトで使う: yonerai chat --script",
                "確認する: yonerai providers --pretty --lang ja",
                "",
            )
        )
    return "\n".join(
        (
            "YonerAI Interactive CLI",
            "stdin is not a TTY, so the interactive screen did not start.",
            "Interactive: yonerai chat",
            "Scripted: yonerai chat --script",
            "Check setup: yonerai providers --pretty --lang en",
            "",
        )
    )


def _unknown(lang: str) -> str:
    return "不明なコマンドです。/ヘルプ を見てください\n" if lang == "ja" else "Unknown command. Type /help\n"


def _bye(lang: str) -> str:
    return "終了しました\n" if lang == "ja" else "Goodbye\n"


def _config_error(lang: str, exc: ConfigError) -> str:
    message = _safe(str(exc) or "config error")
    if lang == "ja":
        return f"設定を保存できませんでした: {message}\n"
    return f"Could not save config: {message}\n"
