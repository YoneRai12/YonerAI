from typing import Dict, Any, List

# Central Registry for Tool Metada (Schema + Implementation Path)
# This file MUST NOT import heavy libraries (torch, numpy, etc.)

TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {
    # --- WEB SKILLS ---
    "web_navigate": {
        "impl": "src.cogs.tools.web_tools:navigate",
        "tags": ["browser", "web"],
        "capability": "navigation",
        "version": "2.1.0",
        "schema": {
            "name": "web_navigate",
            "description": "ブラウザを指定したURLに移動させます。基本的なWeb閲覧の開始点です。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "移動先のURL。"}
                },
                "required": ["url"]
            }
        }
    },
    "web_screenshot": {
        "impl": "src.cogs.tools.web_tools:screenshot",
        "tags": ["browser", "screenshot", "image"],
        "capability": "vision_capture",
        "version": "3.5.0",
        "schema": {
            "name": "web_screenshot",
            "description": "ブラウザを撮影します。4K撮影対応。撮影内容は即座に視覚コンテキストとしてフィードバックされます。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "移動先のURL（省略可）。"},
                    "resolution": {"type": "string", "enum": ["SD", "HD", "FHD", "2K", "4K", "8K"], "description": "解像度。4K以上を推奨。"},
                    "dark_mode": {"type": "boolean", "description": "ダークモード有効化。"},
                    "mobile": {"type": "boolean", "description": "モバイル端末エミュレーション。"},
                    "width": {"type": "integer", "description": "カスタム幅。"},
                    "height": {"type": "integer", "description": "カスタム高さ。"},
                    "delay": {"type": "integer", "description": "撮影待機。"},
                    "full_page": {"type": "boolean", "description": "ページ全体。"}
                }
            }
        }
    },
    "web_download": {
        "impl": "src.cogs.tools.web_tools:download",
        "tags": ["browser", "download", "save", "video", "image"],
        "capability": "media_retrieval",
        "version": "1.8.2",
        "schema": {
            "name": "web_download",
            "description": "YouTube等のWebサイトから動画や音声をダウンロードして保存します。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "対象URL。"},
                    "format": {"type": "string", "enum": ["video", "audio"], "description": "保存形式。"},
                    "start_time": {"type": "integer", "description": "開始位置。"}
                },
                "required": ["url"]
            }
        }
    },
    "web_record_screen": {
        "impl": "src.cogs.tools.web_tools:record_screen",
        "tags": ["browser", "record", "video"],
        "capability": "dynamic_capture",
        "version": "1.0.4",
        "schema": {
            "name": "web_record_screen",
            "description": "ブラウザの操作画面を動画として録画します。",
            "parameters": {
                "type": "object",
                "properties": {
                    "duration": {"type": "integer", "description": "録画時間（秒単位）。"}
                },
                "required": ["duration"]
            }
        }
    },

    # --- VOICE / MUSIC SKILLS ---
    "music_play": {
        "impl": "src.cogs.tools.music_tools:play",
        "tags": ["voice", "music", "vc"],
        "capability": "audio_broadcast",
        "version": "2.4.0",
        "schema": {
            "name": "music_play",
            "description": "ボイスチャンネルで音楽を再生します。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "楽曲の検索ワードまたはURL。"}
                },
                "required": ["query"]
            }
        }
    },
    "join_voice_channel": {
        "impl": "src.cogs.tools.music_tools:join",
        "tags": ["voice", "vc", "join"],
        "capability": "session_entry",
        "version": "1.2.0",
        "schema": {
            "name": "join_voice_channel",
            "description": "ユーザーのボイスチャンネルに参加します。",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    "leave_voice_channel": {
        "impl": "src.cogs.tools.music_tools:leave",
        "tags": ["voice", "vc", "leave"],
        "capability": "session_exit",
        "version": "1.2.0",
        "schema": {
            "name": "leave_voice_channel",
            "description": "ボイスチャンネルから切断します。",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    "tts_speak": {
        "impl": "src.cogs.tools.music_tools:speak",
        "tags": ["voice", "tts", "speak"],
        "capability": "speech_synthesis",
        "version": "3.1.0",
        "schema": {
            "name": "tts_speak",
            "description": "指定したテキストをボイスチャンネルで読み上げます。",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "読み上げる内容。"}
                },
                "required": ["text"]
            }
        }
    },

    # --- MEDIA GEN SKILLS ---
    "dall-e_gen": {
        "impl": "src.cogs.tools.media_tools:generate_image",
        "tags": ["image", "generate", "create"],
        "capability": "generative_art",
        "version": "4.0.0",
        "schema": {
            "name": "dall-e_gen",
            "description": "指示に基づいてAI画像を生成します。",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "画像の記述語。"}
                },
                "required": ["prompt"]
            }
        }
    },

    # --- SYSTEM SKILLS ---
    "system_info": {
        "impl": "src.cogs.tools.system_tools:info",
        "tags": ["system", "info", "memory"],
        "capability": "diagnostic",
        "version": "2.0.0",
        "schema": {
            "name": "system_info",
            "description": "ボットのシステムステータスとメモリ情報を取得します。",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    "check_privilege": {
        "impl": "src.cogs.tools.system_tools:check_privilege",
        "tags": ["system", "auth"],
        "capability": "security",
        "version": "1.5.0",
        "schema": {
             "name": "check_privilege",
             "description": "ユーザーの権限レベルを確認します。",
             "parameters": {"type": "object", "properties": {}}
        }
    },
    "router_health": {
        "impl": "src.cogs.tools.system_tools:router_health",
        "tags": ["system", "health", "monitor", "router"],
        "capability": "infrastructure_monitor",
        "version": "1.1.0",
        "schema": {
            "name": "router_health",
            "description": "ルーターのリアルタイムヘルス指標（レイテンシ、キャッシュ安定性等）を表示します。",
            "parameters": {"type": "object", "properties": {}}
        }
    },

    # --- SEARCH / CODEBASE SKILLS ---
    "code_grep": {
        "impl": "src.cogs.tools.search_tools:code_grep",
        "tags": ["search", "code", "grep"],
        "capability": "content_indexing",
        "version": "1.0.0",
        "schema": {
            "name": "code_grep",
            "description": "コードベース内を文字列検索（grep）します。特定の機能や変数がどこで使われているか探すのに最適です。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "検索キーワード。"},
                    "path": {"type": "string", "description": "検索対象ディレクトリ（デフォルト: '.'）。"},
                    "ignore_case": {"type": "boolean", "description": "大文字小文字を区別しない。"}
                },
                "required": ["query"]
            }
        }
    },
    "code_find": {
        "impl": "src.cogs.tools.search_tools:code_find",
        "tags": ["search", "code", "find"],
        "capability": "file_lookup",
        "version": "1.0.0",
        "schema": {
            "name": "code_find",
            "description": "ファイル名や拡張子を指定してファイルを検索します。特定のファイルを探す際に使用します。",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "ファイル名のパターン（正規表現）。"},
                    "path": {"type": "string", "description": "検索対象ディレクトリ（デフォルト: '.'）。"}
                },
                "required": ["pattern"]
            }
        }
    },
    "code_read": {
        "impl": "src.cogs.tools.search_tools:code_read",
        "tags": ["read", "code", "file"],
        "capability": "file_reading",
        "version": "1.0.0",
        "schema": {
            "name": "code_read",
            "description": "ファイルの内容を読み込みます。行指定も可能です。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "ファイルパス。"},
                    "start": {"type": "integer", "description": "開始行（1開始）。"},
                    "end": {"type": "integer", "description": "終了行。"}
                },
                "required": ["path"]
            }
        }
    },
    "code_tree": {
        "impl": "src.cogs.tools.search_tools:code_tree",
        "tags": ["search", "code", "tree"],
        "capability": "hierarchy_mapping",
        "version": "1.0.0",
        "schema": {
            "name": "code_tree",
            "description": "ディレクトリ構造をツリー形式で表示し、プロジェクトの全体像を把握します。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "ルートディレクトリ。"},
                    "depth": {"type": "integer", "description": "深さ（デフォルト: 2）。"}
                }
            }
        }
    }
    ,
    # --- SCHEDULER (OWNER ONLY) ---
    "schedule_task": {
        "impl": "src.cogs.tools.scheduler_tools:schedule_task",
        "tags": ["scheduler", "automation", "owner"],
        "capability": "scheduler_admin",
        "version": "0.1.0",
        "schema": {
            "name": "schedule_task",
            "description": "（オーナー専用）定期タスクを作成します。安全のためLLMのみで実行され、ツール呼び出しは行いません。",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "実行する指示文。"},
                    "interval_sec": {"type": "integer", "description": "実行間隔（秒）。30以上。"},
                    "channel_id": {"type": "integer", "description": "投稿先チャンネルID（省略時: 現在のチャンネル）。"},
                    "model": {"type": "string", "description": "Coreへ渡すllm_preference（省略可）。"},
                    "enabled": {"type": "boolean", "description": "有効/無効（デフォルトtrue）。"}
                },
                "required": ["prompt", "interval_sec"]
            }
        }
    },
    "list_scheduled_tasks": {
        "impl": "src.cogs.tools.scheduler_tools:list_scheduled_tasks",
        "tags": ["scheduler", "automation", "owner"],
        "capability": "scheduler_admin",
        "version": "0.1.0",
        "schema": {
            "name": "list_scheduled_tasks",
            "description": "（オーナー専用）定期タスク一覧を表示します。",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    "delete_scheduled_task": {
        "impl": "src.cogs.tools.scheduler_tools:delete_scheduled_task",
        "tags": ["scheduler", "automation", "owner"],
        "capability": "scheduler_admin",
        "version": "0.1.0",
        "schema": {
            "name": "delete_scheduled_task",
            "description": "（オーナー専用）定期タスクを削除します。",
            "parameters": {
                "type": "object",
                "properties": {"task_id": {"type": "integer", "description": "タスクID (#)"}},
                "required": ["task_id"]
            }
        }
    },
    "toggle_scheduled_task": {
        "impl": "src.cogs.tools.scheduler_tools:toggle_scheduled_task",
        "tags": ["scheduler", "automation", "owner"],
        "capability": "scheduler_admin",
        "version": "0.1.0",
        "schema": {
            "name": "toggle_scheduled_task",
            "description": "（オーナー専用）定期タスクの有効/無効を切り替えます。",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer", "description": "タスクID (#)"},
                    "enabled": {"type": "boolean", "description": "trueで有効、falseで無効"}
                },
                "required": ["task_id", "enabled"]
            }
        }
    },
}

def get_tool_schemas() -> List[Dict[str, Any]]:
    """Returns a list of tool definitions (JSON schemas) for the LLM."""
    schemas = []
    for key, data in TOOL_REGISTRY.items():
        # Inject tags into the schema for the Router to see?
        # Actually Router looks at tool['tags'] in our custom logic.
        # We should return a dict that includes 'tags' alongside the schema wrapper.

        # Structure matching available_tools in ToolSelector:
        # { "name": "...", "tags": [], ... (schema fields) }

        s = data["schema"].copy()
        s["tags"] = data["tags"]
        schemas.append(s)
    return schemas

def get_tool_impl(tool_name: str) -> str:
    """Returns the implementation path for a tool."""
    return TOOL_REGISTRY.get(tool_name, {}).get("impl")
