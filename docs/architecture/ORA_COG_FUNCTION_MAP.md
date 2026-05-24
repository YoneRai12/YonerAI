# ORA Cog Function Map

This document is generated from `src/cogs/ora.py` using AST inspection. It does not import the Discord runtime.

## Summary

- Target: `src/cogs/ora.py`
- Source lines: `3104`
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

## Definition Map

| Lines | Qualname | Responsibility | Side effects | Risk | Candidate | Target | Required tests |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 89-91 | `_nonce` | Legacy helper or setup block. | none | low | no |  | static map coverage only |
| 97-124 | `_generate_tree` | Legacy helper with file boundary involvement. | file | high | no |  | workspace/temp-file allowlist test |
| 130-3095 | `ORACog` | ORA-specific commands such as login link and dataset management. | discord, provider_or_llm, memory, file, tool_or_shell_policy, network, system_or_process | high | no |  | discord-free static or mock interaction test; provider mocked or local-fixture execution test; workspace/temp-file allowlist test; deny-by-default tool boundary test; network-disabled fixture test; read-only diagnostic fixture test |
| 133-219 | `ORACog.__init__` | Initializes ORACog runtime dependencies and mutable state. | discord, provider_or_llm, memory, file, tool_or_shell_policy, network, system_or_process | high | no |  | discord-free static or mock interaction test; provider mocked or local-fixture execution test; workspace/temp-file allowlist test; deny-by-default tool boundary test; network-disabled fixture test; read-only diagnostic fixture test |
| 221-230 | `ORACog._load_soul` | Load the 'Soul' (Persona) prompt from data/soul.md. | file | high | no |  | workspace/temp-file allowlist test |
| 238-244 | `ORACog.set_status` | Helper to set bot status from callbacks. | discord | medium | no |  | discord-free static or mock interaction test |
| 260-345 | `ORACog.dashboard` | Get the link to this server's web dashboard. | discord, network, system_or_process | high | no |  | discord-free static or mock interaction test; network-disabled fixture test; read-only diagnostic fixture test |
| 347-358 | `ORACog.cog_load` | Called when the Cog is loaded. Performs Startup Sync. | none | low | no |  | static map coverage only |
| 360-385 | `ORACog._startup_sync` | Syncs OpenAI usage and updates local limiter state. | provider_or_llm, network | high | no |  | provider mocked or local-fixture execution test; network-disabled fixture test |
| 387-403 | `ORACog.cog_unload` | Legacy helper or setup block. | none | low | no |  | static map coverage only |
| 406-513 | `ORACog.check_unoptimized_users` | Periodically scan for unoptimized users and trigger optimization. | discord, file | high | no |  | discord-free static or mock interaction test; workspace/temp-file allowlist test |
| 515-523 | `ORACog._on_game_start` | Callback when game starts: Switch to Gaming Mode IMMEDIATELY. | none | low | no |  | static map coverage only |
| 525-530 | `ORACog._on_game_end` | Callback when game ends: Schedule switch to Normal Mode after 5 minutes. | none | low | no |  | static map coverage only |
| 532-542 | `ORACog._restore_normal_mode_delayed` | Wait 5 minutes then restore Normal Mode. | none | low | no |  | static map coverage only |
| 552-585 | `ORACog._check_permission` | Check if user has permission. Levels: - 'owner': Only the Bot Owner (Config Admin ID). - 'sub_admin': Owner OR Sub-Admins. - 'vc_admin': Owner OR Sub-Admins OR VC Admins. | none | low | no |  | static map coverage only |
| 588-603 | `ORACog.hourly_sync_loop` | Periodically sync OpenAI usage with official API. | discord, network | high | no |  | discord-free static or mock interaction test; network-disabled fixture test |
| 606-696 | `ORACog.desktop_loop` | Periodically check the desktop and report to Admin. | discord | medium | no |  | discord-free static or mock interaction test |
| 713-748 | `ORACog.system_reload` | Reloads an extension without restarting the bot. | discord, system_or_process | high | no |  | discord-free static or mock interaction test; read-only diagnostic fixture test |
| 758-764 | `ORACog.desktop_watch` | Toggle desktop watcher. | discord | medium | no |  | discord-free static or mock interaction test |
| 768-787 | `ORACog.system_info` | Show system info. | discord, system_or_process | high | no |  | discord-free static or mock interaction test; read-only diagnostic fixture test |
| 790-806 | `ORACog.system_process_list` | List top processes. | discord, system_or_process | high | no |  | discord-free static or mock interaction test; read-only diagnostic fixture test |
| 809-810 | `ORACog.before_desktop_loop` | Discord command/listener/task entrypoint. | none | medium | no |  | static map coverage only |
| 812-828 | `ORACog.login` | Discord command/listener/task entrypoint. | discord, network | high | no |  | discord-free static or mock interaction test; network-disabled fixture test |
| 830-833 | `ORACog._ephemeral_for` | Return True if the user's privacy setting is 'private'. | discord | medium | no |  | discord-free static or mock interaction test |
| 836-845 | `ORACog.whoami` | Discord command/listener/task entrypoint. | discord | medium | no |  | discord-free static or mock interaction test |
| 855-862 | `ORACog.ora_privacy` | Discord command/listener/task entrypoint. | discord | medium | no |  | discord-free static or mock interaction test |
| 872-877 | `ORACog.privacy_set_system` | Discord command/listener/task entrypoint. | discord | medium | no |  | discord-free static or mock interaction test |
| 879-905 | `ORACog.chat` | Legacy helper with discord, provider_or_llm boundary involvement. | discord, provider_or_llm | medium | no |  | discord-free static or mock interaction test; provider mocked or local-fixture execution test |
| 915-967 | `ORACog.dataset_add` | Discord command/listener/task entrypoint. | discord, file, network | high | no |  | discord-free static or mock interaction test; workspace/temp-file allowlist test; network-disabled fixture test |
| 970-979 | `ORACog.dataset_list` | Discord command/listener/task entrypoint. | discord | medium | no |  | discord-free static or mock interaction test |
| 986-1032 | `ORACog.summarize` | Summarize recent chat history. | discord, provider_or_llm | medium | no |  | discord-free static or mock interaction test; provider mocked or local-fixture execution test |
| 1046-1066 | `ORACog.status` | Discord command/listener/task entrypoint. | discord | medium | no |  | discord-free static or mock interaction test |
| 1074-1077 | `ORACog.memory_clear` | Discord command/listener/task entrypoint. | discord, memory | medium | no |  | discord-free static or mock interaction test |
| 1081-1129 | `ORACog.test_all` | Run a full system diagnostic check. | discord, provider_or_llm | medium | no |  | discord-free static or mock interaction test; provider mocked or local-fixture execution test |
| 1131-1148 | `ORACog._get_voice_channel_info` | Legacy helper with discord boundary involvement. | discord | medium | no |  | discord-free static or mock interaction test |
| 1155-1183 | `ORACog.process_message_queue` | Process queued messages after image generation completes. | discord | medium | no |  | discord-free static or mock interaction test |
| 1186-1217 | `ORACog.switch_brain` | Switch the AI Brain Mode. | discord | medium | no |  | discord-free static or mock interaction test |
| 1221-1279 | `ORACog.system_override` | Override System Limits (Roleplay). | discord | medium | no |  | discord-free static or mock interaction test |
| 1282-1340 | `ORACog.check_credits` | Check usage stats using CostManager with Sync. | discord, provider_or_llm | medium | no |  | discord-free static or mock interaction test; provider mocked or local-fixture execution test |
| 1342-1366 | `ORACog._send_large_message` | Splits and sends large messages to avoid 400 Bad Request. | discord | medium | no |  | discord-free static or mock interaction test |
| 1368-1370 | `ORACog._detect_spam` | Compatibility wrapper for the extracted ORA spam detector. | none | low | yes | `src/cogs/ora_pure_helpers.py` | characterization parity before wrapper extraction |
| 1372-1374 | `ORACog._is_input_spam` | Compatibility wrapper for the extracted ORA input spam detector. | none | low | yes | `src/cogs/ora_pure_helpers.py` | characterization parity before wrapper extraction |
| 1376-1437 | `ORACog._perform_guardrail_check` | [Layer 2 Security] AI Guardrail. Uses a cheap model (gpt-5-mini) to check for loop/spam/jailbreak instructions that regex missed. | provider_or_llm | medium | no |  | provider mocked or local-fixture execution test |
| 1439-1441 | `ORACog._extract_json_objects` | Compatibility wrapper for the extracted ORA JSON recovery helper. | none | low | yes | `src/cogs/ora_pure_helpers.py` | characterization parity before wrapper extraction |
| 1443-1445 | `ORACog._clean_content` | Remove internal tags like <\|channel\|>... from the text. | none | low | yes | `src/cogs/ora_pure_helpers.py` | characterization parity before wrapper extraction |
| 1448-1738 | `ORACog.on_message` | Discord command/listener/task entrypoint. | discord, provider_or_llm, file, tool_or_shell_policy | high | no |  | discord-free static or mock interaction test; provider mocked or local-fixture execution test; workspace/temp-file allowlist test; deny-by-default tool boundary test |
| 1741-1767 | `ORACog._process_attachments` | Process a list of attachments (Text or Image) and update prompt/context. | discord, file | high | no |  | discord-free static or mock interaction test; workspace/temp-file allowlist test |
| 1769-1783 | `ORACog._process_embed_images` | Process images found in Embeds (Thumbnail or Image field). | discord | medium | no |  | discord-free static or mock interaction test |
| 1785-2894 | `ORACog._get_tool_schemas` | Returns the list of available tools, organized by Category. Includes 'tags' for RAG filtering. | none | low | no |  | static map coverage only |
| 2896-2925 | `ORACog.get_context_tools` | Public method to get tools filtered by client context. Prevents usage of Discord-only tools in Web UI, or Web tools in Discord. Also includes Dynamically Loaded Skills from SKILL.m | tool_or_shell_policy | high | no |  | deny-by-default tool boundary test |
| 2928-2937 | `ORACog.handle_prompt` | Process a user message and generate a response using the LLM (Delegated to ChatHandler). | discord, provider_or_llm | medium | no |  | discord-free static or mock interaction test; provider mocked or local-fixture execution test |
| 2939-2941 | `ORACog._legacy_handle_prompt` | Legacy helper or setup block. | none | low | no |  | static map coverage only |
| 2942-2955 | `ORACog.wait_for_llm` | Show a loading animation while waiting for LLM. | discord | medium | no |  | discord-free static or mock interaction test |
| 2957-2979 | `ORACog._create_mock_interaction` | Helper to create a mock interaction from context. | discord | medium | no |  | discord-free static or mock interaction test |
| 2959-2977 | `ORACog._create_mock_interaction.MockInteraction` | Legacy helper with discord boundary involvement. | discord | medium | no |  | discord-free static or mock interaction test |
| 2960-2965 | `ORACog._create_mock_interaction.MockInteraction.__init__` | Initializes ORACog runtime dependencies and mutable state. | discord | medium | no |  | discord-free static or mock interaction test |
| 2967-2972 | `ORACog._create_mock_interaction.MockInteraction.Response` | Legacy helper with discord boundary involvement. | discord | medium | no |  | discord-free static or mock interaction test |
| 2968-2968 | `ORACog._create_mock_interaction.MockInteraction.Response.__init__` | Initializes ORACog runtime dependencies and mutable state. | none | low | no |  | static map coverage only |
| 2969-2969 | `ORACog._create_mock_interaction.MockInteraction.Response.is_done` | Legacy helper or setup block. | none | low | no |  | static map coverage only |
| 2970-2971 | `ORACog._create_mock_interaction.MockInteraction.Response.send_message` | Legacy helper with discord boundary involvement. | discord | medium | no |  | discord-free static or mock interaction test |
| 2972-2972 | `ORACog._create_mock_interaction.MockInteraction.Response.defer` | Legacy helper or setup block. | none | low | no |  | static map coverage only |
| 2974-2977 | `ORACog._create_mock_interaction.MockInteraction.Followup` | Legacy helper with discord boundary involvement. | discord | medium | no |  | discord-free static or mock interaction test |
| 2975-2975 | `ORACog._create_mock_interaction.MockInteraction.Followup.__init__` | Initializes ORACog runtime dependencies and mutable state. | none | low | no |  | static map coverage only |
| 2976-2977 | `ORACog._create_mock_interaction.MockInteraction.Followup.send` | Legacy helper with discord boundary involvement. | discord | medium | no |  | discord-free static or mock interaction test |
| 2982-3050 | `ORACog.on_raw_reaction_add` | Handle flag reactions for translation. | discord, provider_or_llm | medium | no |  | discord-free static or mock interaction test; provider mocked or local-fixture execution test |
| 3053-3078 | `ORACog.rank` | Check your current points and rank. | discord | medium | no |  | discord-free static or mock interaction test |
| 3080-3091 | `ORACog.check_points` | AI tool to check user's current points. | discord | medium | no |  | discord-free static or mock interaction test |
| 3093-3095 | `ORACog._strip_route_json` | Compatibility wrapper for the extracted ORA route JSON stripper. | none | low | yes | `src/cogs/ora_pure_helpers.py` | characterization parity before wrapper extraction |
| 3098-3104 | `setup` | Legacy helper or setup block. | none | low | no |  | static map coverage only |

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

### `ORACog._perform_guardrail_check`
- Local callees: `ORACog._extract_json_objects`

### `ORACog._extract_json_objects`
- Callers: `ORACog._perform_guardrail_check`

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
