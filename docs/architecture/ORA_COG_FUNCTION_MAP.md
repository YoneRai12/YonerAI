# ORA Cog Function Map

This document is generated from `src/cogs/ora.py` using AST inspection. It does not import the Discord runtime.

## Summary

- Target: `src/cogs/ora.py`
- Source lines: `3088`
- Source SHA-256: `5b8e257139e28f7e43303bc0a458634f594d414e1ecae8f6222e2c8ba1a9ffff`
- Definitions mapped: `69`
- Risk counts: `{"high": 16, "low": 19, "medium": 34}`
- Side-effect counts: `{"discord": 44, "file": 8, "memory": 3, "network": 7, "provider_or_llm": 11, "system_or_process": 6, "tool_or_shell_policy": 4}`

## Top Responsibilities

- Discord command facade: slash commands, listeners, task loops, interaction replies.
- Runtime dependency wiring: managers, handlers, LLM clients, cost manager, watcher, storage.
- Permission and privacy policy: owner checks, privacy defaults, linked account state.
- System and desktop diagnostics: process list, status, desktop watcher, reload entrypoints.
- Provider and guardrail bridge: prompt handling, guardrail LLM call, model/client selection.
- Tool boundary surface: schema assembly, context filtering, tool handler integration.
- File and attachment handling: dataset upload, attachment/image processing, cache paths.
- Memory and points surface: memory clear, rank, points, conversation queue paths.
- Text cleanup and route/tool JSON recovery: legacy tags, route JSON stripping, tool-call recovery.
- Discord compatibility shims: mock interaction helpers and reaction handling.

## Extraction Candidates

- `ORACog._detect_spam` -> `src/cogs/ora_pure_helpers.py`
- `ORACog._is_input_spam` -> `src/cogs/ora_pure_helpers.py`
- `ORACog._extract_json_objects` -> `src/cogs/ora_pure_helpers.py`
- `ORACog._clean_content` -> `src/cogs/ora_pure_helpers.py`
- `ORACog._strip_route_json` -> `src/cogs/ora_pure_helpers.py`

## Internal Block Map

| Lines | Qualname | Responsibility | Side effects | Risk | Candidate | Target | Required tests |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1349-1362 | `ORACog._send_large_message.large_message_chunking` | Delegate Discord-bound chunk calculation to the extracted pure helper, then keep reply/send side effects inside ORACog. | none | low | no | `src/cogs/ora_message_format_helpers.py` | wrapper compatibility test |
| 1415-1415 | `ORACog._perform_guardrail_check.guardrail_response_interpretation` | Delegate guardrail model response interpretation to the extracted pure helper. | none | low | no | `src/cogs/ora_guardrail_helpers.py` | wrapper compatibility test |

## Definition Map

| Lines | Qualname | Responsibility | Side effects | Risk | Candidate | Target | Required tests |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 91-93 | `_nonce` | Legacy helper or setup block. | none | low | no |  | static map coverage only |
| 99-126 | `_generate_tree` | Legacy helper with file boundary involvement. | file | high | no |  | workspace/temp-file allowlist test |
| 132-3079 | `ORACog` | ORA-specific commands such as login link and dataset management. | discord, provider_or_llm, memory, file, tool_or_shell_policy, network, system_or_process | high | no |  | discord-free static or mock interaction test; provider mocked or local-fixture execution test; workspace/temp-file allowlist test; deny-by-default tool boundary test; network-disabled fixture test; read-only diagnostic fixture test |
| 135-221 | `ORACog.__init__` | Initializes ORACog runtime dependencies and mutable state. | discord, provider_or_llm, memory, file, tool_or_shell_policy, network, system_or_process | high | no |  | discord-free static or mock interaction test; provider mocked or local-fixture execution test; workspace/temp-file allowlist test; deny-by-default tool boundary test; network-disabled fixture test; read-only diagnostic fixture test |
| 223-232 | `ORACog._load_soul` | Load the 'Soul' (Persona) prompt from data/soul.md. | file | high | no |  | workspace/temp-file allowlist test |
| 240-246 | `ORACog.set_status` | Helper to set bot status from callbacks. | discord | medium | no |  | discord-free static or mock interaction test |
| 262-347 | `ORACog.dashboard` | Get the link to this server's web dashboard. | discord, network, system_or_process | high | no |  | discord-free static or mock interaction test; network-disabled fixture test; read-only diagnostic fixture test |
| 349-360 | `ORACog.cog_load` | Called when the Cog is loaded. Performs Startup Sync. | none | low | no |  | static map coverage only |
| 362-387 | `ORACog._startup_sync` | Syncs OpenAI usage and updates local limiter state. | provider_or_llm, network | high | no |  | provider mocked or local-fixture execution test; network-disabled fixture test |
| 389-405 | `ORACog.cog_unload` | Legacy helper or setup block. | none | low | no |  | static map coverage only |
| 408-515 | `ORACog.check_unoptimized_users` | Periodically scan for unoptimized users and trigger optimization. | discord, file | high | no |  | discord-free static or mock interaction test; workspace/temp-file allowlist test |
| 517-525 | `ORACog._on_game_start` | Callback when game starts: Switch to Gaming Mode IMMEDIATELY. | none | low | no |  | static map coverage only |
| 527-532 | `ORACog._on_game_end` | Callback when game ends: Schedule switch to Normal Mode after 5 minutes. | none | low | no |  | static map coverage only |
| 534-544 | `ORACog._restore_normal_mode_delayed` | Wait 5 minutes then restore Normal Mode. | none | low | no |  | static map coverage only |
| 554-587 | `ORACog._check_permission` | Check if user has permission. Levels: - 'owner': Only the Bot Owner (Config Admin ID). - 'sub_admin': Owner OR Sub-Admins. - 'vc_admin': Owner OR Sub-Admins OR VC Admins. | none | low | no |  | static map coverage only |
| 590-605 | `ORACog.hourly_sync_loop` | Periodically sync OpenAI usage with official API. | discord, network | high | no |  | discord-free static or mock interaction test; network-disabled fixture test |
| 608-698 | `ORACog.desktop_loop` | Periodically check the desktop and report to Admin. | discord | medium | no |  | discord-free static or mock interaction test |
| 715-750 | `ORACog.system_reload` | Reloads an extension without restarting the bot. | discord, system_or_process | high | no |  | discord-free static or mock interaction test; read-only diagnostic fixture test |
| 760-766 | `ORACog.desktop_watch` | Toggle desktop watcher. | discord | medium | no |  | discord-free static or mock interaction test |
| 770-789 | `ORACog.system_info` | Show system info. | discord, system_or_process | high | no |  | discord-free static or mock interaction test; read-only diagnostic fixture test |
| 792-808 | `ORACog.system_process_list` | List top processes. | discord, system_or_process | high | no |  | discord-free static or mock interaction test; read-only diagnostic fixture test |
| 811-812 | `ORACog.before_desktop_loop` | Discord command/listener/task entrypoint. | none | medium | no |  | static map coverage only |
| 814-830 | `ORACog.login` | Discord command/listener/task entrypoint. | discord, network | high | no |  | discord-free static or mock interaction test; network-disabled fixture test |
| 832-835 | `ORACog._ephemeral_for` | Return True if the user's privacy setting is 'private'. | discord | medium | no |  | discord-free static or mock interaction test |
| 838-847 | `ORACog.whoami` | Discord command/listener/task entrypoint. | discord | medium | no |  | discord-free static or mock interaction test |
| 857-864 | `ORACog.ora_privacy` | Discord command/listener/task entrypoint. | discord | medium | no |  | discord-free static or mock interaction test |
| 874-879 | `ORACog.privacy_set_system` | Discord command/listener/task entrypoint. | discord | medium | no |  | discord-free static or mock interaction test |
| 881-907 | `ORACog.chat` | Legacy helper with discord, provider_or_llm boundary involvement. | discord, provider_or_llm | medium | no |  | discord-free static or mock interaction test; provider mocked or local-fixture execution test |
| 917-969 | `ORACog.dataset_add` | Discord command/listener/task entrypoint. | discord, file, network | high | no |  | discord-free static or mock interaction test; workspace/temp-file allowlist test; network-disabled fixture test |
| 972-981 | `ORACog.dataset_list` | Discord command/listener/task entrypoint. | discord | medium | no |  | discord-free static or mock interaction test |
| 988-1034 | `ORACog.summarize` | Summarize recent chat history. | discord, provider_or_llm | medium | no |  | discord-free static or mock interaction test; provider mocked or local-fixture execution test |
| 1048-1068 | `ORACog.status` | Discord command/listener/task entrypoint. | discord | medium | no |  | discord-free static or mock interaction test |
| 1076-1079 | `ORACog.memory_clear` | Discord command/listener/task entrypoint. | discord, memory | medium | no |  | discord-free static or mock interaction test |
| 1083-1131 | `ORACog.test_all` | Run a full system diagnostic check. | discord, provider_or_llm | medium | no |  | discord-free static or mock interaction test; provider mocked or local-fixture execution test |
| 1133-1150 | `ORACog._get_voice_channel_info` | Legacy helper with discord boundary involvement. | discord | medium | no |  | discord-free static or mock interaction test |
| 1157-1185 | `ORACog.process_message_queue` | Process queued messages after image generation completes. | discord | medium | no |  | discord-free static or mock interaction test |
| 1188-1219 | `ORACog.switch_brain` | Switch the AI Brain Mode. | discord | medium | no |  | discord-free static or mock interaction test |
| 1223-1281 | `ORACog.system_override` | Override System Limits (Roleplay). | discord | medium | no |  | discord-free static or mock interaction test |
| 1284-1342 | `ORACog.check_credits` | Check usage stats using CostManager with Sync. | discord, provider_or_llm | medium | no |  | discord-free static or mock interaction test; provider mocked or local-fixture execution test |
| 1344-1364 | `ORACog._send_large_message` | Splits and sends large messages to avoid 400 Bad Request. | discord | medium | no |  | discord-free static or mock interaction test |
| 1366-1368 | `ORACog._detect_spam` | Compatibility wrapper for the extracted ORA spam detector. | none | low | yes | `src/cogs/ora_pure_helpers.py` | characterization parity before wrapper extraction |
| 1370-1372 | `ORACog._is_input_spam` | Compatibility wrapper for the extracted ORA input spam detector. | none | low | yes | `src/cogs/ora_pure_helpers.py` | characterization parity before wrapper extraction |
| 1374-1421 | `ORACog._perform_guardrail_check` | [Layer 2 Security] AI Guardrail. Uses a cheap model (gpt-5-mini) to check for loop/spam/jailbreak instructions that regex missed. | provider_or_llm | medium | no |  | provider mocked or local-fixture execution test |
| 1423-1425 | `ORACog._extract_json_objects` | Compatibility wrapper for the extracted ORA JSON recovery helper. | none | low | yes | `src/cogs/ora_pure_helpers.py` | characterization parity before wrapper extraction |
| 1427-1429 | `ORACog._clean_content` | Remove internal tags like <\|channel\|>... from the text. | none | low | yes | `src/cogs/ora_pure_helpers.py` | characterization parity before wrapper extraction |
| 1432-1722 | `ORACog.on_message` | Discord command/listener/task entrypoint. | discord, provider_or_llm, file, tool_or_shell_policy | high | no |  | discord-free static or mock interaction test; provider mocked or local-fixture execution test; workspace/temp-file allowlist test; deny-by-default tool boundary test |
| 1725-1751 | `ORACog._process_attachments` | Process a list of attachments (Text or Image) and update prompt/context. | discord, file | high | no |  | discord-free static or mock interaction test; workspace/temp-file allowlist test |
| 1753-1767 | `ORACog._process_embed_images` | Process images found in Embeds (Thumbnail or Image field). | discord | medium | no |  | discord-free static or mock interaction test |
| 1769-2878 | `ORACog._get_tool_schemas` | Returns the list of available tools, organized by Category. Includes 'tags' for RAG filtering. | none | low | no |  | static map coverage only |
| 2880-2909 | `ORACog.get_context_tools` | Public method to get tools filtered by client context. Prevents usage of Discord-only tools in Web UI, or Web tools in Discord. Also includes Dynamically Loaded Skills from SKILL.m | tool_or_shell_policy | high | no |  | deny-by-default tool boundary test |
| 2912-2921 | `ORACog.handle_prompt` | Process a user message and generate a response using the LLM (Delegated to ChatHandler). | discord, provider_or_llm | medium | no |  | discord-free static or mock interaction test; provider mocked or local-fixture execution test |
| 2923-2925 | `ORACog._legacy_handle_prompt` | Legacy helper or setup block. | none | low | no |  | static map coverage only |
| 2926-2939 | `ORACog.wait_for_llm` | Show a loading animation while waiting for LLM. | discord | medium | no |  | discord-free static or mock interaction test |
| 2941-2963 | `ORACog._create_mock_interaction` | Helper to create a mock interaction from context. | discord | medium | no |  | discord-free static or mock interaction test |
| 2943-2961 | `ORACog._create_mock_interaction.MockInteraction` | Legacy helper with discord boundary involvement. | discord | medium | no |  | discord-free static or mock interaction test |
| 2944-2949 | `ORACog._create_mock_interaction.MockInteraction.__init__` | Initializes ORACog runtime dependencies and mutable state. | discord | medium | no |  | discord-free static or mock interaction test |
| 2951-2956 | `ORACog._create_mock_interaction.MockInteraction.Response` | Legacy helper with discord boundary involvement. | discord | medium | no |  | discord-free static or mock interaction test |
| 2952-2952 | `ORACog._create_mock_interaction.MockInteraction.Response.__init__` | Initializes ORACog runtime dependencies and mutable state. | none | low | no |  | static map coverage only |
| 2953-2953 | `ORACog._create_mock_interaction.MockInteraction.Response.is_done` | Legacy helper or setup block. | none | low | no |  | static map coverage only |
| 2954-2955 | `ORACog._create_mock_interaction.MockInteraction.Response.send_message` | Legacy helper with discord boundary involvement. | discord | medium | no |  | discord-free static or mock interaction test |
| 2956-2956 | `ORACog._create_mock_interaction.MockInteraction.Response.defer` | Legacy helper or setup block. | none | low | no |  | static map coverage only |
| 2958-2961 | `ORACog._create_mock_interaction.MockInteraction.Followup` | Legacy helper with discord boundary involvement. | discord | medium | no |  | discord-free static or mock interaction test |
| 2959-2959 | `ORACog._create_mock_interaction.MockInteraction.Followup.__init__` | Initializes ORACog runtime dependencies and mutable state. | none | low | no |  | static map coverage only |
| 2960-2961 | `ORACog._create_mock_interaction.MockInteraction.Followup.send` | Legacy helper with discord boundary involvement. | discord | medium | no |  | discord-free static or mock interaction test |
| 2966-3034 | `ORACog.on_raw_reaction_add` | Handle flag reactions for translation. | discord, provider_or_llm | medium | no |  | discord-free static or mock interaction test; provider mocked or local-fixture execution test |
| 3037-3062 | `ORACog.rank` | Check your current points and rank. | discord | medium | no |  | discord-free static or mock interaction test |
| 3064-3075 | `ORACog.check_points` | AI tool to check user's current points. | discord | medium | no |  | discord-free static or mock interaction test |
| 3077-3079 | `ORACog._strip_route_json` | Compatibility wrapper for the extracted ORA route JSON stripper. | none | low | yes | `src/cogs/ora_pure_helpers.py` | characterization parity before wrapper extraction |
| 3082-3088 | `setup` | Legacy helper or setup block. | none | low | no |  | static map coverage only |

## Interface Map

| Lines | Qualname | Inputs | Outputs | Callers | Local callees |
| --- | --- | --- | --- | --- | --- |
| 91-93 | `_nonce` | length: int | return value; annotation: str | `ORACog`, `ORACog.login` | none |
| 99-126 | `_generate_tree` | dir_path: Path, max_depth: int, current_depth: int | return value; annotation: str | `_generate_tree` | `_generate_tree` |
| 132-3079 | `ORACog` | base:commands.Cog | class instance | `setup` | `_nonce` |
| 135-221 | `ORACog.__init__` | self, bot: commands.Bot, store: Store, llm: LLMClient, search_client: SearchClient, public_base_url: Optional[str], ora_api_base_url: Optional[str], privacy_default: str | return value; annotation: None | none | `ORACog._get_tool_schemas`, `ORACog._load_soul` |
| 223-232 | `ORACog._load_soul` | self | return value; annotation: str | `ORACog.__init__` | none |
| 240-246 | `ORACog.set_status` | self, text: str, status_type: discord.Status | async coroutine | none | none |
| 262-347 | `ORACog.dashboard` | self, interaction: discord.Interaction | async coroutine | none | none |
| 349-360 | `ORACog.cog_load` | self | async coroutine | none | `ORACog._startup_sync` |
| 362-387 | `ORACog._startup_sync` | self | async coroutine | `ORACog.cog_load` | none |
| 389-405 | `ORACog.cog_unload` | self | return value | none | none |
| 408-515 | `ORACog.check_unoptimized_users` | self | async coroutine | none | none |
| 517-525 | `ORACog._on_game_start` | self | return value | none | none |
| 527-532 | `ORACog._on_game_end` | self | return value | none | `ORACog._restore_normal_mode_delayed` |
| 534-544 | `ORACog._restore_normal_mode_delayed` | self | async coroutine | `ORACog._on_game_end` | none |
| 554-587 | `ORACog._check_permission` | self, user_id: int, level: str | async coroutine; annotation: bool | `ORACog.status`, `ORACog.switch_brain`, `ORACog.system_override`, `ORACog.system_reload` | none |
| 590-605 | `ORACog.hourly_sync_loop` | self | async coroutine | none | none |
| 608-698 | `ORACog.desktop_loop` | self | async coroutine | none | none |
| 715-750 | `ORACog.system_reload` | self, interaction: discord.Interaction, extension: str | async coroutine | none | `ORACog._check_permission` |
| 760-766 | `ORACog.desktop_watch` | self, interaction: discord.Interaction, mode: str | async coroutine | none | none |
| 770-789 | `ORACog.system_info` | self, interaction: discord.Interaction | async coroutine; annotation: None | none | none |
| 792-808 | `ORACog.system_process_list` | self, interaction: discord.Interaction | async coroutine; annotation: None | none | none |
| 811-812 | `ORACog.before_desktop_loop` | self | async coroutine | none | none |
| 814-830 | `ORACog.login` | self, interaction: discord.Interaction, ephemeral: bool | async coroutine; annotation: None | none | `_nonce` |
| 832-835 | `ORACog._ephemeral_for` | self, user: discord.User \| discord.Member | async coroutine; annotation: bool | `ORACog.chat`, `ORACog.dataset_add`, `ORACog.dataset_list`, `ORACog.summarize` | none |
| 838-847 | `ORACog.whoami` | self, interaction: discord.Interaction | async coroutine; annotation: None | none | none |
| 857-864 | `ORACog.ora_privacy` | self, interaction: discord.Interaction, mode: Optional[app_commands.Choice[str]] | async coroutine; annotation: None | none | none |
| 874-879 | `ORACog.privacy_set_system` | self, interaction: discord.Interaction, mode: app_commands.Choice[str] | async coroutine; annotation: None | none | none |
| 881-907 | `ORACog.chat` | self, interaction: discord.Interaction, prompt: str | async coroutine; annotation: None | none | `ORACog._ephemeral_for` |
| 917-969 | `ORACog.dataset_add` | self, interaction: discord.Interaction, file: discord.Attachment, name: Optional[str] | async coroutine; annotation: None | none | `ORACog._ephemeral_for` |
| 972-981 | `ORACog.dataset_list` | self, interaction: discord.Interaction | async coroutine; annotation: None | none | `ORACog._ephemeral_for` |
| 988-1034 | `ORACog.summarize` | self, interaction: discord.Interaction, limit: int | async coroutine; annotation: None | none | `ORACog._ephemeral_for` |
| 1048-1068 | `ORACog.status` | self, interaction: discord.Interaction | async coroutine | none | `ORACog._check_permission` |
| 1076-1079 | `ORACog.memory_clear` | self, interaction: discord.Interaction | async coroutine; annotation: None | none | none |
| 1083-1131 | `ORACog.test_all` | self, interaction: discord.Interaction, ephemeral: bool | async coroutine; annotation: None | none | none |
| 1133-1150 | `ORACog._get_voice_channel_info` | self, guild: discord.Guild, channel_name: Optional[str], user: Optional[discord.Member] | async coroutine; annotation: str | none | none |
| 1157-1185 | `ORACog.process_message_queue` | self | async coroutine | none | `ORACog.handle_prompt` |
| 1188-1219 | `ORACog.switch_brain` | self, interaction: discord.Interaction, mode: str | async coroutine | none | `ORACog._check_permission` |
| 1223-1281 | `ORACog.system_override` | self, interaction: discord.Interaction, mode: str, auth_code: str | async coroutine | none | `ORACog._check_permission` |
| 1284-1342 | `ORACog.check_credits` | self, interaction: discord.Interaction | async coroutine | none | none |
| 1344-1364 | `ORACog._send_large_message` | self, message: discord.Message, content: str, header: str, files: list | async coroutine | none | none |
| 1366-1368 | `ORACog._detect_spam` | self, text: str | return value; annotation: bool | none | none |
| 1370-1372 | `ORACog._is_input_spam` | self, text: str | return value; annotation: bool | none | none |
| 1374-1421 | `ORACog._perform_guardrail_check` | self, prompt: str, user_id: int | async coroutine; annotation: dict | none | none |
| 1423-1425 | `ORACog._extract_json_objects` | self, text: str | return value; annotation: list[str] | none | none |
| 1427-1429 | `ORACog._clean_content` | self, text: str | return value; annotation: str | none | none |
| 1432-1722 | `ORACog.on_message` | self, message: discord.Message | async coroutine; annotation: None | none | `ORACog._create_mock_interaction`, `ORACog._process_attachments`, `ORACog._process_embed_images` |
| 1725-1751 | `ORACog._process_attachments` | self, attachments: List[discord.Attachment], prompt: str, context_message: discord.Message, is_reference: bool | async coroutine; annotation: str | `ORACog.on_message` | none |
| 1753-1767 | `ORACog._process_embed_images` | self, embeds: List[discord.Embed], prompt: str, context_message: discord.Message, is_reference: bool | async coroutine; annotation: str | `ORACog.on_message` | none |
| 1769-2878 | `ORACog._get_tool_schemas` | self | return value; annotation: list[dict] | `ORACog.__init__`, `ORACog.get_context_tools` | none |
| 2880-2909 | `ORACog.get_context_tools` | self, client_type: str, user_id: int \| None | return value; annotation: list[dict] | none | `ORACog._get_tool_schemas` |
| 2912-2921 | `ORACog.handle_prompt` | self, message: discord.Message, prompt: str, existing_status_msg: Optional[discord.Message], is_voice: bool, force_dm: bool | async coroutine; annotation: None | `ORACog.process_message_queue` | none |
| 2923-2925 | `ORACog._legacy_handle_prompt` | self, message, prompt, existing_status_msg, is_voice, force_dm | async coroutine | none | none |
| 2926-2939 | `ORACog.wait_for_llm` | self, message: discord.Message | async coroutine; annotation: None | none | none |
| 2941-2963 | `ORACog._create_mock_interaction` | self, ctx | return value | `ORACog.on_message` | none |
| 2943-2961 | `ORACog._create_mock_interaction.MockInteraction` | none | class instance | none | none |
| 2944-2949 | `ORACog._create_mock_interaction.MockInteraction.__init__` | self, ctx | return value | none | `ORACog._create_mock_interaction.MockInteraction.Followup`, `ORACog._create_mock_interaction.MockInteraction.Response` |
| 2951-2956 | `ORACog._create_mock_interaction.MockInteraction.Response` | none | class instance | `ORACog._create_mock_interaction.MockInteraction.__init__` | none |
| 2952-2952 | `ORACog._create_mock_interaction.MockInteraction.Response.__init__` | self, ctx | return value | none | none |
| 2953-2953 | `ORACog._create_mock_interaction.MockInteraction.Response.is_done` | self | return value | none | none |
| 2954-2955 | `ORACog._create_mock_interaction.MockInteraction.Response.send_message` | self, embed, ephemeral | async coroutine | none | none |
| 2956-2956 | `ORACog._create_mock_interaction.MockInteraction.Response.defer` | self | async coroutine | none | none |
| 2958-2961 | `ORACog._create_mock_interaction.MockInteraction.Followup` | none | class instance | `ORACog._create_mock_interaction.MockInteraction.__init__` | none |
| 2959-2959 | `ORACog._create_mock_interaction.MockInteraction.Followup.__init__` | self, ctx | return value | none | none |
| 2960-2961 | `ORACog._create_mock_interaction.MockInteraction.Followup.send` | self, embed, ephemeral | async coroutine | none | none |
| 2966-3034 | `ORACog.on_raw_reaction_add` | self, payload: discord.RawReactionActionEvent | async coroutine | none | none |
| 3037-3062 | `ORACog.rank` | self, interaction: discord.Interaction | async coroutine | none | none |
| 3064-3075 | `ORACog.check_points` | self, ctx: commands.Context | async coroutine; annotation: None | none | none |
| 3077-3079 | `ORACog._strip_route_json` | self, content: str | return value; annotation: str | none | none |
| 3082-3088 | `setup` | bot | async coroutine | none | `ORACog` |

## Call Graph Notes

### `_nonce`
- Callers: `ORACog`, `ORACog.login`

### `_generate_tree`
- Callers: `_generate_tree`
- Local callees: `_generate_tree`

### `ORACog`
- Callers: `setup`
- Local callees: `_nonce`

### `ORACog.__init__`
- Local callees: `ORACog._get_tool_schemas`, `ORACog._load_soul`

### `ORACog._load_soul`
- Callers: `ORACog.__init__`

### `ORACog.cog_load`
- Local callees: `ORACog._startup_sync`

### `ORACog._startup_sync`
- Callers: `ORACog.cog_load`

### `ORACog._on_game_end`
- Local callees: `ORACog._restore_normal_mode_delayed`

### `ORACog._restore_normal_mode_delayed`
- Callers: `ORACog._on_game_end`

### `ORACog._check_permission`
- Callers: `ORACog.status`, `ORACog.switch_brain`, `ORACog.system_override`, `ORACog.system_reload`

### `ORACog.system_reload`
- Local callees: `ORACog._check_permission`

### `ORACog.login`
- Local callees: `_nonce`

### `ORACog._ephemeral_for`
- Callers: `ORACog.chat`, `ORACog.dataset_add`, `ORACog.dataset_list`, `ORACog.summarize`

### `ORACog.chat`
- Local callees: `ORACog._ephemeral_for`

### `ORACog.dataset_add`
- Local callees: `ORACog._ephemeral_for`

### `ORACog.dataset_list`
- Local callees: `ORACog._ephemeral_for`

### `ORACog.summarize`
- Local callees: `ORACog._ephemeral_for`

### `ORACog.status`
- Local callees: `ORACog._check_permission`

### `ORACog.process_message_queue`
- Local callees: `ORACog.handle_prompt`

### `ORACog.switch_brain`
- Local callees: `ORACog._check_permission`

### `ORACog.system_override`
- Local callees: `ORACog._check_permission`

### `ORACog.on_message`
- Local callees: `ORACog._create_mock_interaction`, `ORACog._process_attachments`, `ORACog._process_embed_images`

### `ORACog._process_attachments`
- Callers: `ORACog.on_message`

### `ORACog._process_embed_images`
- Callers: `ORACog.on_message`

### `ORACog._get_tool_schemas`
- Callers: `ORACog.__init__`, `ORACog.get_context_tools`

### `ORACog.get_context_tools`
- Local callees: `ORACog._get_tool_schemas`

### `ORACog.handle_prompt`
- Callers: `ORACog.process_message_queue`

### `ORACog._create_mock_interaction`
- Callers: `ORACog.on_message`

### `ORACog._create_mock_interaction.MockInteraction.__init__`
- Local callees: `ORACog._create_mock_interaction.MockInteraction.Followup`, `ORACog._create_mock_interaction.MockInteraction.Response`

### `ORACog._create_mock_interaction.MockInteraction.Response`
- Callers: `ORACog._create_mock_interaction.MockInteraction.__init__`

### `ORACog._create_mock_interaction.MockInteraction.Followup`
- Callers: `ORACog._create_mock_interaction.MockInteraction.__init__`

### `setup`
- Local callees: `ORACog`
