# YonerAI Local CLI Smoke

`clients/cli` is the YonerAI CLI Local Runtime surface. It is the main
public-safe command surface for provider readiness, auto routing, local-dev
execution, diagnostics, and release/install dry-run planning. It is not a
deployment tool and not a live Discord/Official Managed Cloud runtime.

License: YonerAI code is source-available under PolyForm Noncommercial License
1.0.0. Documentation/assets are CC BY-NC-ND 4.0 unless stated otherwise, and
the YonerAI brand is All Rights Reserved. This is not an OSI open-source
package and commercial use requires a separate license.

## Install and start YonerAI

This is the CLI Local Runtime path, not full YonerAI cloud production. The
latest stable is `v0.7.0`. Stable is the default channel; alpha requires an
explicit `-Channel alpha` flag.

### Quick install

```powershell
irm https://install.yonerai.com | iex
```

Quick install runs a static Cloudflare wrapper from `install.yonerai.com`. The
wrapper downloads `install.ps1` and `install.ps1.sha256` from the currently
embedded trusted stable release tag, checks the sidecar against the embedded
SHA256, and runs the bootstrap only after the downloaded script hash matches. It
does not call the GitHub API from the user's terminal, fetch ZIPs, manifests, or
sidecar hashes from `yonerai.com`, mutate PATH by default, request admin rights,
edit the registry, install a service, store provider keys, or enable live
providers.

Do not pipe `releases/latest/download/install.ps1` directly into
`Invoke-Expression`; the short command goes through the trust-mapped wrapper.

### Verified install

Use this when you want to verify `install.ps1` before execution:

```powershell
$ErrorActionPreference = "Stop"
$base = "https://github.com/YoneRai12/YonerAI/releases/download/v0.7.0"
$expected = "3db7cdace412d2c2978c74d77e2a2fce664bee4e6ee710f79b2349c0e89f3874"
$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("yonerai-bootstrap-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tmp | Out-Null
try {
  $script = Join-Path $tmp "install.ps1"
  $sidecar = Join-Path $tmp "install.ps1.sha256"
  irm "$base/install.ps1" -OutFile $script
  irm "$base/install.ps1.sha256" -OutFile $sidecar
  $sidecarExpected = ((Get-Content -LiteralPath $sidecar -Raw) -split '\s+')[0].ToLowerInvariant()
  if ($sidecarExpected -notmatch "^[a-f0-9]{64}$") { throw "install.ps1 sidecar SHA256 is invalid" }
  if ($sidecarExpected -ne $expected) { throw "install.ps1 sidecar does not match trusted digest" }
  $actual = (Get-FileHash -LiteralPath $script -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($actual -ne $expected) { throw "install.ps1 hash mismatch" }
  $scriptText = Get-Content -LiteralPath $script -Raw
  if ($scriptText -notmatch "Invoke-VerifiedLocalBootstrap" -or $scriptText -match "install.ps1 is still plan-only") {
    throw "install.ps1 is not an executable bootstrap. Refusing to launch."
  }
  & (Get-Process -Id $PID).Path -NoProfile -ExecutionPolicy Bypass -File $script -Execute -Launch
} finally {
  if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Recurse -Force }
}
```

### If you downloaded the GitHub Release ZIP

Download `YonerAI-0.7.0.zip` from the
[v0.7.0 release](https://github.com/YoneRai12/YonerAI/releases/tag/v0.7.0),
extract it, then run PowerShell inside the extracted folder. The extracted
folder name can vary; change the `cd` command to match the folder you see.

```powershell
cd "$HOME\Downloads\YonerAI-0.7.0"
python --version
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -r core/requirements.txt httpx
python -m pip install -e clients/cli
yonerai
```

If the extracted archive or checkout contains `install-local.ps1`, you can use
the plan-first local bootstrap helper:

```powershell
.\install-local.ps1
.\install-local.ps1 -Execute -Launch
```

The first command prints the plan only. The second command explicitly creates
or reuses `.venv`, installs the local CLI package, and launches YonerAI. It does
not mutate PATH, run a remote script, request admin rights, install a service,
or enable live providers.

`install.ps1` is the GitHub Release bootstrap. Without `-Execute`, it prints
the plan and performs no install:

```powershell
.\install.ps1
```

Use Python 3.11 or newer. If `python --version` does not work, install Python
first or use the launcher command that exists on your machine.

After `yonerai` opens, choose `日本語` or `English`, then type a normal
message. Settings are available with `/設定` or `/settings`; safety is
`/安全`; history is `/履歴`; exit is `/終了` or `/quit`.

If `yonerai` is not found, activate the virtual environment again:
`.\.venv\Scripts\Activate.ps1`. This path does not mutate PATH permanently,
does not run `irm ... | iex`, does not download or execute a remote installer,
and does not enable live providers by default.

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

When `prompt_toolkit` and Rich are available, the interactive shell shows
completion candidates and colored panels. If not, it falls back to plain text.
In Japanese mode, type `/` to see Japanese-first candidates; Tab and arrow-key
selection are available in compatible terminals.

Readable Japanese aliases are accepted for the main TUI actions, including
`/設定`, `/モデル`, `/提供元`, `/安全`, `/履歴`, `/タスク`, `/認証`,
`/プライバシー`, `/自己進化`, `/更新`, `/更新通知`, and `/終了`. Legacy
aliases remain accepted for compatibility. The interactive shell is still a
local terminal surface: it does not enable live providers, arbitrary shell/tool
execution, production cloud, Google login, or live Discord.

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
yonerai manifest verify manifest.v0.7.0.json --pretty
yonerai install plan --manifest manifest.v0.7.0.json --pretty
yonerai update check --manifest manifest.v0.7.0.json --pretty
yonerai update plan --manifest manifest.v0.7.0.json --pretty
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
- `/models`
- `/providers`
- `/safety`
- `/tasks`
- `/agents`
- `/runs`
- `/show <run_id>`
- `/local-llm`
- `/auth`
- `/privacy`
- `/update`
- `/update-notice on|off`
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

Japanese mode shows Japanese command labels such as `/設定`, `/モデル`, `/提供元`,
`/安全`, `/履歴`, `/タスク`, `/エージェント`, `/認証`, `/同期`, `/プライバシー`, `/更新`, and `/終了`. English aliases remain
accepted for compatibility, but they are not the primary Japanese UI.

`yonerai update` shows stable/alpha choices first. `yonerai update stable` and
`yonerai update alpha` read local VERSION and local release manifests, then
report whether a newer manifest target exists. They do not download, install,
mutate PATH, execute remote code, force update, auto-apply updates, or require
admin rights.

`yonerai sync status --pretty --lang ja` shows the public account-sync
contract. Cloud conversation sync down requires a linked account and
user-selected cloud conversation. Local private conversation sync up is
disabled by default and requires explicit approval plus audit reason. The public
repo command is fixture/contract only; it does not contact Official Cloud or
production Oracle.

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
yonerai auth status --pretty --lang ja
yonerai auth google login --dry-run --pretty --lang ja
yonerai sync status --pretty --lang ja
yonerai sync preview --direction cloud-to-local --json
yonerai sync approve --dry-run --direction local-to-cloud --json
yonerai privacy status --pretty --lang ja
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

`yonerai auth google login --dry-run` is a contract preview only. It checks the
loopback-only PKCE/state requirements and never starts live OAuth, opens a
browser, prints tokens, or stores refresh tokens. `yonerai privacy status`
shows OpenAI shared traffic as disabled by default and confirms private/local
file/memory/local-node content is excluded from any future shared-traffic lane.

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
