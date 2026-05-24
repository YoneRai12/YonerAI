# ORA Cog Function Map

This document is generated from `src/cogs/ora.py` using AST inspection. It does not import the Discord runtime.

## Summary

- Target: `src/cogs/ora.py`
- Source lines: `3277`
- Definitions mapped: `72`
- Risk counts: `{"high": 16, "low": 20, "medium": 36}`
- Side-effect counts: `{"discord": 46, "file": 8, "memory": 3, "network": 7, "provider_or_llm": 11, "system_or_process": 6, "tool_or_shell_policy": 4}`

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
| 84-86 | `_nonce` | Legacy helper or setup block. | none | low | no |  | static map coverage only |
| 92-119 | `_generate_tree` | Legacy helper with file boundary involvement. | file | high | no |  | workspace/temp-file allowlist test |
| 125-3268 | `ORACog` | ORA-specific commands such as login link and dataset management. | discord, provider_or_llm, memory, file, tool_or_shell_policy, network, system_or_process | high | no |  | discord-free static or mock interaction test; provider mocked or local-fixture execution test; workspace/temp-file allowlist test; deny-by-default tool boundary test; network-disabled fixture test; read-only diagnostic fixture test |
| 128-214 | `ORACog.__init__` | Initializes ORACog runtime dependencies and mutable state. | discord, provider_or_llm, memory, file, tool_or_shell_policy, network, system_or_process | high | no |  | discord-free static or mock interaction test; provider mocked or local-fixture execution test; workspace/temp-file allowlist test; deny-by-default tool boundary test; network-disabled fixture test; read-only diagnostic fixture test |
| 216-225 | `ORACog._load_soul` | Load the 'Soul' (Persona) prompt from data/soul.md. | file | high | no |  | workspace/temp-file allowlist test |
| 227-231 | `ORACog._get_tool_schemas` | Return tool definitions for the Unified Brain. | none | low | no |  | static map coverage only |
| 233-239 | `ORACog.set_status` | Helper to set bot status from callbacks. | discord | medium | no |  | discord-free static or mock interaction test |
| 241-247 | `ORACog._on_game_start` | Callback for GameWatcher when game starts. | discord | medium | no |  | discord-free static or mock interaction test |
| 249-252 | `ORACog._on_game_end` | Callback for GameWatcher when game ends. | discord | medium | no |  | discord-free static or mock interaction test |
| 255-340 | `ORACog.dashboard` | Get the link to this server's web dashboard. | discord, network, system_or_process | high | no |  | discord-free static or mock interaction test; network-disabled fixture test; read-only diagnostic fixture test |
| 342-353 | `ORACog.cog_load` | Called when the Cog is loaded. Performs Startup Sync. | none | low | no |  | static map coverage only |
| 355-380 | `ORACog._startup_sync` | Syncs OpenAI usage and updates local limiter state. | provider_or_llm, network | high | no |  | provider mocked or local-fixture execution test; network-disabled fixture test |
| 382-398 | `ORACog.cog_unload` | Legacy helper or setup block. | none | low | no |  | static map coverage only |
| 401-508 | `ORACog.check_unoptimized_users` | Periodically scan for unoptimized users and trigger optimization. | discord, file | high | no |  | discord-free static or mock interaction test; workspace/temp-file allowlist test |
| 510-518 | `ORACog._on_game_start` | Callback when game starts: Switch to Gaming Mode IMMEDIATELY. | none | low | no |  | static map coverage only |
| 520-525 | `ORACog._on_game_end` | Callback when game ends: Schedule switch to Normal Mode after 5 minutes. | none | low | no |  | static map coverage only |
| 527-537 | `ORACog._restore_normal_mode_delayed` | Wait 5 minutes then restore Normal Mode. | none | low | no |  | static map coverage only |
| 547-580 | `ORACog._check_permission` | Check if user has permission. Levels: - 'owner': Only the Bot Owner (Config Admin ID). - 'sub_admin': Owner OR Sub-Admins. - 'vc_admin': Owner OR Sub-Admins OR VC Admins. | none | low | no |  | static map coverage only |
| 583-598 | `ORACog.hourly_sync_loop` | Periodically sync OpenAI usage with official API. | discord, network | high | no |  | discord-free static or mock interaction test; network-disabled fixture test |
| 601-691 | `ORACog.desktop_loop` | Periodically check the desktop and report to Admin. | discord | medium | no |  | discord-free static or mock interaction test |
| 708-743 | `ORACog.system_reload` | Reloads an extension without restarting the bot. | discord, system_or_process | high | no |  | discord-free static or mock interaction test; read-only diagnostic fixture test |
| 753-759 | `ORACog.desktop_watch` | Toggle desktop watcher. | discord | medium | no |  | discord-free static or mock interaction test |
| 763-782 | `ORACog.system_info` | Show system info. | discord, system_or_process | high | no |  | discord-free static or mock interaction test; read-only diagnostic fixture test |
| 785-801 | `ORACog.system_process_list` | List top processes. | discord, system_or_process | high | no |  | discord-free static or mock interaction test; read-only diagnostic fixture test |
| 804-805 | `ORACog.before_desktop_loop` | Discord command/listener/task entrypoint. | none | medium | no |  | static map coverage only |
| 807-823 | `ORACog.login` | Discord command/listener/task entrypoint. | discord, network | high | no |  | discord-free static or mock interaction test; network-disabled fixture test |
| 825-828 | `ORACog._ephemeral_for` | Return True if the user's privacy setting is 'private'. | discord | medium | no |  | discord-free static or mock interaction test |
| 831-840 | `ORACog.whoami` | Discord command/listener/task entrypoint. | discord | medium | no |  | discord-free static or mock interaction test |
| 850-857 | `ORACog.ora_privacy` | Discord command/listener/task entrypoint. | discord | medium | no |  | discord-free static or mock interaction test |
| 867-872 | `ORACog.privacy_set_system` | Discord command/listener/task entrypoint. | discord | medium | no |  | discord-free static or mock interaction test |
| 874-900 | `ORACog.chat` | Legacy helper with discord, provider_or_llm boundary involvement. | discord, provider_or_llm | medium | no |  | discord-free static or mock interaction test; provider mocked or local-fixture execution test |
| 910-962 | `ORACog.dataset_add` | Discord command/listener/task entrypoint. | discord, file, network | high | no |  | discord-free static or mock interaction test; workspace/temp-file allowlist test; network-disabled fixture test |
| 965-974 | `ORACog.dataset_list` | Discord command/listener/task entrypoint. | discord | medium | no |  | discord-free static or mock interaction test |
| 981-1027 | `ORACog.summarize` | Summarize recent chat history. | discord, provider_or_llm | medium | no |  | discord-free static or mock interaction test; provider mocked or local-fixture execution test |
| 1041-1061 | `ORACog.status` | Discord command/listener/task entrypoint. | discord | medium | no |  | discord-free static or mock interaction test |
| 1069-1072 | `ORACog.memory_clear` | Discord command/listener/task entrypoint. | discord, memory | medium | no |  | discord-free static or mock interaction test |
| 1076-1124 | `ORACog.test_all` | Run a full system diagnostic check. | discord, provider_or_llm | medium | no |  | discord-free static or mock interaction test; provider mocked or local-fixture execution test |
| 1126-1143 | `ORACog._get_voice_channel_info` | Legacy helper with discord boundary involvement. | discord | medium | no |  | discord-free static or mock interaction test |
| 1150-1178 | `ORACog.process_message_queue` | Process queued messages after image generation completes. | discord | medium | no |  | discord-free static or mock interaction test |
| 1181-1212 | `ORACog.switch_brain` | Switch the AI Brain Mode. | discord | medium | no |  | discord-free static or mock interaction test |
| 1216-1274 | `ORACog.system_override` | Override System Limits (Roleplay). | discord | medium | no |  | discord-free static or mock interaction test |
| 1277-1335 | `ORACog.check_credits` | Check usage stats using CostManager with Sync. | discord, provider_or_llm | medium | no |  | discord-free static or mock interaction test; provider mocked or local-fixture execution test |
| 1337-1361 | `ORACog._send_large_message` | Splits and sends large messages to avoid 400 Bad Request. | discord | medium | no |  | discord-free static or mock interaction test |
| 1363-1381 | `ORACog._detect_spam` | Detects if text is repetitive spam using Compression Ratio. If text is long (>500 chars) and compresses extremely well (<10%), it's likely spam. | none | low | yes | `src/cogs/ora_pure_helpers.py` | characterization parity before wrapper extraction |
| 1383-1412 | `ORACog._is_input_spam` | Detects if input is spam/abuse (e.g. 'Repeat 10000 times', massive repetition). Returns True if spam. | none | low | yes | `src/cogs/ora_pure_helpers.py` | characterization parity before wrapper extraction |
| 1414-1475 | `ORACog._perform_guardrail_check` | [Layer 2 Security] AI Guardrail. Uses a cheap model (gpt-5-mini) to check for loop/spam/jailbreak instructions that regex missed. | provider_or_llm | medium | no |  | provider mocked or local-fixture execution test |
| 1477-1521 | `ORACog._extract_json_objects` | Extracts top-level JSON objects from text. | none | low | yes | `src/cogs/ora_pure_helpers.py` | characterization parity before wrapper extraction |
| 1523-1525 | `ORACog._clean_content` | Remove internal tags like <\|channel\|>... from the text. | none | low | yes | `src/cogs/ora_pure_helpers.py` | characterization parity before wrapper extraction |
| 1528-1818 | `ORACog.on_message` | Discord command/listener/task entrypoint. | discord, provider_or_llm, file, tool_or_shell_policy | high | no |  | discord-free static or mock interaction test; provider mocked or local-fixture execution test; workspace/temp-file allowlist test; deny-by-default tool boundary test |
| 1821-1847 | `ORACog._process_attachments` | Process a list of attachments (Text or Image) and update prompt/context. | discord, file | high | no |  | discord-free static or mock interaction test; workspace/temp-file allowlist test |
| 1849-1863 | `ORACog._process_embed_images` | Process images found in Embeds (Thumbnail or Image field). | discord | medium | no |  | discord-free static or mock interaction test |
| 1865-2974 | `ORACog._get_tool_schemas` | Returns the list of available tools, organized by Category. Includes 'tags' for RAG filtering. | none | low | no |  | static map coverage only |
| 2976-3058 | `ORACog.get_context_tools` | Public method to get tools filtered by client context. Prevents usage of Discord-only tools in Web UI, or Web tools in Discord. Also includes Dynamically Loaded Skills from SKILL.m | tool_or_shell_policy | high | no |  | deny-by-default tool boundary test |
| 3061-3070 | `ORACog.handle_prompt` | Process a user message and generate a response using the LLM (Delegated to ChatHandler). | discord, provider_or_llm | medium | no |  | discord-free static or mock interaction test; provider mocked or local-fixture execution test |
| 3072-3074 | `ORACog._legacy_handle_prompt` | Legacy helper or setup block. | none | low | no |  | static map coverage only |
| 3075-3088 | `ORACog.wait_for_llm` | Show a loading animation while waiting for LLM. | discord | medium | no |  | discord-free static or mock interaction test |
| 3090-3112 | `ORACog._create_mock_interaction` | Helper to create a mock interaction from context. | discord | medium | no |  | discord-free static or mock interaction test |
| 3092-3110 | `ORACog._create_mock_interaction.MockInteraction` | Legacy helper with discord boundary involvement. | discord | medium | no |  | discord-free static or mock interaction test |
| 3093-3098 | `ORACog._create_mock_interaction.MockInteraction.__init__` | Initializes ORACog runtime dependencies and mutable state. | discord | medium | no |  | discord-free static or mock interaction test |
| 3100-3105 | `ORACog._create_mock_interaction.MockInteraction.Response` | Legacy helper with discord boundary involvement. | discord | medium | no |  | discord-free static or mock interaction test |
| 3101-3101 | `ORACog._create_mock_interaction.MockInteraction.Response.__init__` | Initializes ORACog runtime dependencies and mutable state. | none | low | no |  | static map coverage only |
| 3102-3102 | `ORACog._create_mock_interaction.MockInteraction.Response.is_done` | Legacy helper or setup block. | none | low | no |  | static map coverage only |
| 3103-3104 | `ORACog._create_mock_interaction.MockInteraction.Response.send_message` | Legacy helper with discord boundary involvement. | discord | medium | no |  | discord-free static or mock interaction test |
| 3105-3105 | `ORACog._create_mock_interaction.MockInteraction.Response.defer` | Legacy helper or setup block. | none | low | no |  | static map coverage only |
| 3107-3110 | `ORACog._create_mock_interaction.MockInteraction.Followup` | Legacy helper with discord boundary involvement. | discord | medium | no |  | discord-free static or mock interaction test |
| 3108-3108 | `ORACog._create_mock_interaction.MockInteraction.Followup.__init__` | Initializes ORACog runtime dependencies and mutable state. | none | low | no |  | static map coverage only |
| 3109-3110 | `ORACog._create_mock_interaction.MockInteraction.Followup.send` | Legacy helper with discord boundary involvement. | discord | medium | no |  | discord-free static or mock interaction test |
| 3115-3183 | `ORACog.on_raw_reaction_add` | Handle flag reactions for translation. | discord, provider_or_llm | medium | no |  | discord-free static or mock interaction test; provider mocked or local-fixture execution test |
| 3186-3211 | `ORACog.rank` | Check your current points and rank. | discord | medium | no |  | discord-free static or mock interaction test |
| 3213-3224 | `ORACog.check_points` | AI tool to check user's current points. | discord | medium | no |  | discord-free static or mock interaction test |
| 3226-3268 | `ORACog._strip_route_json` | Removes the JSON block containing 'route_eval' by counting braces. | none | low | yes | `src/cogs/ora_pure_helpers.py` | characterization parity before wrapper extraction |
| 3271-3277 | `setup` | Legacy helper or setup block. | none | low | no |  | static map coverage only |

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

### `ORACog._get_tool_schemas`
- Callers: `ORACog.__init__`, `ORACog.get_context_tools`

### `ORACog.set_status`
- Callers: `ORACog._on_game_end`, `ORACog._on_game_start`

### `ORACog._on_game_start`
- Local callees: `ORACog.set_status`

### `ORACog._on_game_end`
- Local callees: `ORACog.set_status`

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
