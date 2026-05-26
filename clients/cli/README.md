# YonerAI Local CLI Smoke

`clients/cli` is the YonerAI CLI Local Runtime surface. It is the main
public-safe command surface for provider readiness, auto routing, local-dev
execution, diagnostics, and release/install dry-run planning. It is not a
deployment tool and not a live Discord/Official Managed Cloud runtime.

## Install and start YonerAI

From the repository root, install the local CLI runtime into a virtual
environment. This is not the production installer path and does not download or
execute remote installer scripts.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -r core/requirements.txt httpx
python -m pip install -e clients/cli
yonerai
```

`yonerai` starts the interactive CLI when stdin is a TTY. `yonerai chat` starts
the same screen explicitly, and `yonerai ask --auto` remains the scriptable
runtime path.

This screen is the YonerAI Mission Control CLI. It shows provider, route, local
node, ledger, safety mode, run_id, task progress, and the deterministic
reviewer/subagent plan. It does not start uncontrolled agents or turn on live
providers by default.

## Public Demo

From the repository root:

```bash
python -m pip install -r core/requirements.txt httpx
python -m pip install -e clients/cli
yonerai
yonerai chat
yonerai config show --pretty --lang ja
yonerai start --guided --lang ja
yonerai providers --pretty --lang ja
yonerai ask "hello" --auto --pretty --lang ja
yonerai chat --script --lang ja
yonerai demo --pretty
yonerai demo --json
```

`yonerai quickstart` is an alias for `yonerai demo`. The demo is deterministic,
runs in-process, and does not require a running Core API process, credentials,
Oracle, live Discord, a provider API key, persistent memory, Google login, or
deployment.

`yonerai demo --json` emits the stable `yonerai-public-demo/v1` contract with
`schema_version: "1.0"`. `yonerai demo --pretty` prints the same sections in a
readable release-check format.

It shows the public self-host local surface, Hybrid Local Node contract/dev
simulator, Managed Cloud as external contract-only, route preview, enrolled
Local Node trust/session simulation, the managed download guard, and
proposal-only self-evolution.

## Interactive CLI

`yonerai` and `yonerai chat` start the interactive terminal app when stdin is a
TTY. It is Japanese-first, uses the same `ask --auto` runtime path as the
command CLI, and exposes settings through slash commands:

- `/settings`
- `/providers`
- `/safety`
- `/tasks`
- `/agents`
- `/runs`
- `/show <run_id>`
- `/local-llm`
- `/language ja|en`
- `/provider auto|mock|local|openai-compatible|anthropic|gemini`
- `/ledger on|off`
- `/live on|off`
- `/network on|off`
- `/select <n> <value>`
- `/quit`

First interactive launch asks for Japanese or English and stores only local
non-secret preferences. Non-TTY execution prints fallback instructions instead
of hanging. `yonerai chat --script` intentionally reads lines from stdin for
tests or scripted demos.

Japanese mode shows Japanese command labels such as `/設定`, `/タスク`,
`/ローカルLLM`, `/ライブ接続`, and `/ネットワーク`. English aliases remain
accepted for compatibility, but they are not the primary Japanese UI.

The interactive CLI does not add production Oracle, Official Managed Cloud,
live Discord, arbitrary shell/file/tool execution, or default live provider
calls. External providers still require explicit `--live` and provider-specific
environment opt-in. Local LLM remains loopback-only.

## What You Can Try In v0.2.0-alpha.1 And Later

The current CLI local runtime is a local public runtime slice. It is not a
finished full product, a production installer, or a live Discord/Official
Managed Cloud release.

Credential-free commands:

- `yonerai`
- `yonerai chat`
- `yonerai config show --pretty --lang ja`
- `yonerai start --guided --lang ja`
- `yonerai providers --pretty --lang ja`
- `yonerai ask "hello" --auto --pretty --lang ja`
- `yonerai ask "summarize public docs" --provider mock --json`
- `yonerai hybrid run --pretty`
- `yonerai hybrid run --json`
- `yonerai ask "use this selected file" --file <path> --workspace <dir> --provider mock --json`
- `yonerai search mock "YonerAI alpha2" --json`
- `yonerai ops plan git-status --json`
- `yonerai memory add "local note" --store <local.jsonl> --confirm-local --json`
- `yonerai discord synthetic "hello" --json`
- `yonerai status --source fixture --json`
- `yonerai manifest verify releases/manifest.example.json --json`
- `yonerai install plan --manifest releases/manifest.example.json --json`

`yonerai start --guided` explains the first-run path and checks only loopback
local LLM metadata endpoints. It does not send a prompt to a model. It prints a
mock-first path, Local LLM next steps when loopback is detected, a workspace
file guard sample, a redacted ledger sample, and limitations. Mock `ask`
returns a public-safe `run_id`. Workspace file support is a Workspace File
Access Guard: it reads only an explicit UTF-8 text file under an explicit
workspace. Local memory writes only when a store path and `--confirm-local` are
provided.

`yonerai providers --pretty --lang ja` is the provider readiness view. It
reports mock, local LLM, OpenAI-compatible, Anthropic, and Gemini setup without
printing keys or making provider calls. External providers require explicit
`--live` plus provider-specific environment opt-in. Local LLM remains
loopback-only.

`yonerai ask "hello" --auto --pretty --lang ja` is the non-engineer CLI path. It
shows difficulty, privacy, selected route, selected provider, ledger status,
and non-actions. `yonerai runs list/show --pretty --lang ja` reads an explicit
local ledger path or `YONERAI_RUN_LEDGER_PATH` and does not upload run history.

`yonerai hybrid run` is the first local-dev Hybrid execution slice. It runs
route preview, a verified test Local Node session, in-memory relay transport,
mock provider execution, redacted ledger events, and an Oracle stub
request/result envelope in one report. It does not contact production Oracle,
Official Managed Cloud, live Discord, public tunnels, or external providers by
default.

Not included: production readiness, live Discord restoration, live web search by
default, arbitrary shell execution, arbitrary file access, installer-ready
distribution, npm/winget packages, production signing/trust material, Google
login, production DB behavior, complete persistent memory, or a claim that
`src/cogs/ora.py` is solved.

## Install For Local Testing

```bash
python -m pip install -e clients/cli
```

After installation, the local command is:

```bash
yonerai demo --pretty
yonerai start --guided --lang ja
yonerai start --guided --json
yonerai providers --pretty --lang ja
yonerai providers --json
yonerai health
yonerai smoke --pretty
yonerai doctor
yonerai doctor --pretty
yonerai doctor --pretty --lang ja
yonerai doctor --json
yonerai status --pretty
yonerai status --pretty --lang ja
yonerai manifest verify releases/manifest.example.json
yonerai manifest verify releases/manifest.example.json --pretty
yonerai manifest verify releases/manifest.example.json --pretty --lang ja
yonerai manifest verify releases/manifest.example.json --json
yonerai plan "summarize public docs" --json
yonerai ask "hello" --auto --pretty --lang ja
yonerai ask "hard public reasoning over public API docs" --auto --json
yonerai ask "summarize public docs" --provider mock --json
yonerai hybrid run --pretty
yonerai hybrid run --json
yonerai ask "use this selected file" --file notes.txt --workspace . --provider mock --json
yonerai ask "hello" --provider mock --json --ledger .yonerai-runs.jsonl
yonerai runs list --ledger .yonerai-runs.jsonl --pretty --lang ja
yonerai runs show <run_id> --ledger .yonerai-runs.jsonl --pretty --lang ja
yonerai search mock "YonerAI alpha2" --json
yonerai ops plan git-status --json
yonerai memory add "local note" --store .yonerai-memory.jsonl --confirm-local --json
yonerai discord synthetic "hello" --json
yonerai status --source fixture --json
yonerai install plan --manifest releases/manifest.example.json --json
yonerai install plan-windows --json
yonerai message --mode mock "hello"
yonerai run --mode mock "hello"
```

Without installing, run from `clients/cli`:

```bash
python -m yonerai_cli health
```

`yonerai start`, `yonerai demo`, `yonerai smoke`, `yonerai doctor`, `yonerai status`,
`yonerai manifest verify`, `yonerai plan`, mock `yonerai ask`,
`yonerai hybrid run`, mock
`yonerai search`, `yonerai ops plan`, `yonerai discord synthetic`, and
`yonerai install plan` run locally and do not require a local Core API process.
`yonerai install plan-windows` remains a Windows-specific dry-run alias.
`health`, `message`, and `run` run against a local Core API process. The
default origin is `http://127.0.0.1:8001`.

`yonerai doctor` is an offline, non-mutating diagnostic command. It checks the
Python version, CLI import, demo command availability, credential-free demo
boundary, local release manifest example, redaction utility self-check, and MCP
deny-policy self-check. It does not run the demo, modify PATH, install packages,
download remote code, or connect to live services. If `ORA_CORE_API_TOKEN` is
present, doctor reports only `present_redacted`.

`yonerai status` reuses the same offline diagnostics and prints a shorter public
demo / installer-readiness summary. `--lang ja` is available for `doctor`,
`status`, and `manifest verify` pretty output. JSON output remains English-keyed
for stable tests and automation. Pretty commands also accept
`--color auto|never|always`; JSON output never includes terminal color codes.

`yonerai start --guided` is the recommended first command for non-engineers. It
guides the user from demo to doctor, local LLM metadata check, first safe ask,
workspace file guard sample, and opt-in ledger sample. If a loopback Ollama or
LM Studio style endpoint is detected, it explains the explicit
`ORA_LOCAL_LLM_ENABLED=1` and `--live` requirement before local provider
execution. If no local model server is found, it recommends the mock provider
path that works immediately. The guided command itself does not create sample
files, read files, write ledger files, install packages, mutate PATH, or start
model servers.

`yonerai manifest verify <path>` validates a local release manifest file. Remote
manifest URLs are rejected, no artifact is downloaded, and no installer is run.
The example manifest is contract-valid but not install-ready because it still
uses a non-production signature placeholder. Optional
`--artifact ARTIFACT_ID=LOCAL_FILE` mappings verify local SHA256 and size only;
output reports artifact ids, not local file paths. Pretty output reports
contract validity, install readiness, artifact count, SHA256/signature status,
and that no network/download/install action was performed.

`yonerai install plan --manifest releases/manifest.example.json` reads a local
manifest, validates the same contract, prints planned installer steps and
rollback placeholders, and explicitly reports non-actions: no download, no
execution, no PATH mutation, no package install, no registry modification, no
service install, and no remote script execution. It does not install anything.

## Boundary

- The CLI only accepts loopback API origins.
- External provider execution requires explicit provider selection, `--live`, and provider-specific env opt-in; default CLI/demo/tests do not call live providers.
- Local LLM execution is loopback-only.
- Workspace File Access Guard requires explicit `--file` and `--workspace`; it is not folder crawling, PDF/image parsing, arbitrary file access, or automatic file summarization.
- Local memory requires explicit `--store` and `--confirm-local`; it is local-only and redacted.
- SafeShell is plan-only for a small diagnostic allowlist; it is not arbitrary shell execution.
- It does not deploy anything.
- Manifest verification is local-file validation only, not installation.
- If `ORA_CORE_API_TOKEN` is set, it is sent as `X-ORA-Core-Token` and is never printed.
