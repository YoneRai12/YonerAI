# NODE 3-Mode Profile Schema

目的: public の配布版 Node を 3 つの運用モードで切り替えるための設定スキーマを固定する。

この文書は docs-only の契約であり、まだ import rewrite や code move は行わない。

## Profile IDs

- `official-managed-lite`
- `official-hybrid-private`
- `full-private-self-host`

## Top-level keys

| key | type | required | description |
|---|---|---:|---|
| `mode_id` | string | yes | 上記 3 mode のいずれか |
| `enabled_skills` | array[string] | yes | mode で許可する skill IDs |
| `enabled_connectors` | array[string] | yes | `relay`, `mcp`, `local_web`, `official_sync`, `discord_gateway` など |
| `permissions` | table | yes | shell / fs / network / approvals などの capability gate |
| `official_service_dependency` | string | yes | `required`, `optional`, `none` |
| `verification_level` | string | yes | `official`, `hybrid`, `self_host`, `verified_node` など |
| `admin_surface` | string | yes | `private_only`, `local_only`, `mixed` |
| `local_web_enabled` | bool | yes | ローカル Web UI を起動するか |
| `system_shell_enabled` | bool | yes | shell/system tool を許可するか |
| `relay_dependency` | string | yes | `required`, `optional`, `none` |
| `capability_manifest` | string | yes | manifest file path or manifest id |
| `files_mode` | string | yes | `official_files`, `local_files`, `disabled` |
| `dev_surface` | table | no | dev mode gate, admin gate, footer visibility |
| `search_policy` | table | no | search-first, source ranking, provider preferences |
| `runtime_policy` | table | no | memory, background jobs, local db, update channel |

## Nested schema

### permissions

| key | type | description |
|---|---|---|
| `approvals_required_for` | array[string] | `medium`, `high`, `critical` など |
| `network_allow` | array[string] | connector names or domains |
| `filesystem_scope` | string | `app_sandbox`, `owner_workspace`, `full_local` |
| `shell_access` | string | `disabled`, `limited`, `owner_only` |
| `admin_actions` | string | `none`, `official_only`, `owner_only` |
| `extension_install` | string | `disabled`, `verified_only`, `owner_only` |

### dev_surface

| key | type | description |
|---|---|---|
| `requires_verified_admin` | bool | dev mode 表示に verified admin が必要か |
| `requires_env_gate` | bool | env gate も同時に必要か |
| `show_run_id_hash` | bool | footer に run_id_hash を出すか |
| `show_route_band` | bool | footer に route_band を出すか |
| `show_reason_code` | bool | footer に reason_code を出すか |

### search_policy

| key | type | description |
|---|---|---|
| `search_first_required` | bool | explicit search intent で最低 1 回検索するか |
| `noisy_source_demotion` | bool | reddit/quiz/support/search-engine を減点するか |
| `source_confidence_threshold` | number | primary source として扱う閾値 |
| `allow_web_detection` | bool | image pipeline で web detection を使うか |

### runtime_policy

| key | type | description |
|---|---|---|
| `memory_enabled` | bool | band0 でも memory pipeline を使うか |
| `local_db_enabled` | bool | sqlite/local store を使うか |
| `background_jobs_enabled` | bool | cleanup / sync / watch jobs を使うか |
| `update_channel` | string | `stable`, `beta`, `owner_pinned` |

## Mode semantics

### official-managed-lite

- official service 依存: 必須
- relay 依存: 必須
- local shell: 無効
- local web: 原則無効
- admin surface: private repo 側の official/admin surface のみ
- verification: official managed

```toml
mode_id = "official-managed-lite"
enabled_skills = ["read_web_page", "weather"]
enabled_connectors = ["relay", "official_sync", "files"]
official_service_dependency = "required"
verification_level = "official"
admin_surface = "private_only"
local_web_enabled = false
system_shell_enabled = false
relay_dependency = "required"
capability_manifest = "manifests/managed-lite.toml"
files_mode = "official_files"

[permissions]
approvals_required_for = ["medium", "high", "critical"]
network_allow = ["relay", "official_files"]
filesystem_scope = "app_sandbox"
shell_access = "disabled"
admin_actions = "official_only"
extension_install = "disabled"

[dev_surface]
requires_verified_admin = true
requires_env_gate = true
show_run_id_hash = true
show_route_band = true
show_reason_code = true

[search_policy]
search_first_required = true
noisy_source_demotion = true
source_confidence_threshold = 0.7
allow_web_detection = false

[runtime_policy]
memory_enabled = true
local_db_enabled = true
background_jobs_enabled = false
update_channel = "stable"
```

### official-hybrid-private

- official service 依存: 任意
- relay 依存: 任意だが推奨
- local web: 有効
- local shell: 制限付き
- admin surface: owner local + official assist surface の混在
- verification: hybrid

```toml
mode_id = "official-hybrid-private"
enabled_skills = ["read_web_page", "weather", "read_chat_history", "image_crop_upscale"]
enabled_connectors = ["relay", "local_web", "mcp", "files"]
official_service_dependency = "optional"
verification_level = "hybrid"
admin_surface = "mixed"
local_web_enabled = true
system_shell_enabled = false
relay_dependency = "optional"
capability_manifest = "manifests/hybrid-private.toml"
files_mode = "official_files"

[permissions]
approvals_required_for = ["medium", "high", "critical"]
network_allow = ["relay", "official_files", "mcp"]
filesystem_scope = "owner_workspace"
shell_access = "disabled"
admin_actions = "owner_only"
extension_install = "verified_only"

[dev_surface]
requires_verified_admin = true
requires_env_gate = true
show_run_id_hash = true
show_route_band = true
show_reason_code = true

[search_policy]
search_first_required = true
noisy_source_demotion = true
source_confidence_threshold = 0.65
allow_web_detection = true

[runtime_policy]
memory_enabled = true
local_db_enabled = true
background_jobs_enabled = true
update_channel = "stable"
```

### full-private-self-host

- official service 依存: なし
- relay 依存: なし
- local web: 有効
- local shell: owner-only
- admin surface: local only
- verification: self-host / optionally verified-node

```toml
mode_id = "full-private-self-host"
enabled_skills = ["read_web_page", "weather", "read_chat_history", "system_control", "image_crop_upscale"]
enabled_connectors = ["local_web", "mcp", "files"]
official_service_dependency = "none"
verification_level = "self_host"
admin_surface = "local_only"
local_web_enabled = true
system_shell_enabled = true
relay_dependency = "none"
capability_manifest = "manifests/full-private-self-host.toml"
files_mode = "local_files"

[permissions]
approvals_required_for = ["high", "critical"]
network_allow = ["mcp", "files"]
filesystem_scope = "owner_workspace"
shell_access = "owner_only"
admin_actions = "owner_only"
extension_install = "owner_only"

[dev_surface]
requires_verified_admin = false
requires_env_gate = true
show_run_id_hash = true
show_route_band = true
show_reason_code = true

[search_policy]
search_first_required = true
noisy_source_demotion = true
source_confidence_threshold = 0.6
allow_web_detection = true

[runtime_policy]
memory_enabled = true
local_db_enabled = true
background_jobs_enabled = true
update_channel = "owner_pinned"
```

## Validation rules

1. `mode_id` は 3 値固定。
2. `official_service_dependency = "required"` の場合、`relay_dependency` は `required` または `optional` でなければならない。
3. `system_shell_enabled = true` の場合、`permissions.shell_access` は `owner_only` でなければならない。
4. `admin_surface = "private_only"` の場合、public repo 側の admin endpoint を runtime dependency にしてはならない。
5. `files_mode = "official_files"` の場合、cross-repo access は files contract 経由のみ許可される。
6. dev footer に内部メタを出すのは `requires_env_gate=true` かつ mode の admin 条件を満たす場合のみ。
