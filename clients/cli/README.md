# YonerAI Local CLI Smoke

`clients/cli` is a temporary public MVP smoke CLI for the local YonerAI Core API.
It is not the final product CLI, not a native Japanese CLI, and not a deployment
or operations tool.

## Public Demo

From the repository root:

```bash
python -m pip install -r core/requirements.txt httpx
python -m pip install -e clients/cli
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

## What You Can Try In v0.1.0-alpha.2

v0.1.0-alpha.2 is a local public alpha slice. It is not a finished product, a
production installer, or a live Discord/Official Managed Cloud release.

Credential-free commands:

- `yonerai ask "summarize public docs" --provider mock --json`
- `yonerai ask "summarize this file" --file <path> --workspace <dir> --provider mock --json`
- `yonerai search mock "YonerAI alpha2" --json`
- `yonerai ops plan git-status --json`
- `yonerai memory add "local note" --store <local.jsonl> --confirm-local --json`
- `yonerai discord synthetic "hello" --json`
- `yonerai status --source fixture --json`
- `yonerai manifest verify releases/manifest.example.json --json`
- `yonerai install plan --manifest releases/manifest.example.json --json`

Mock `ask` returns a public-safe `run_id`. Workspace file summary reads only an
explicit file under an explicit workspace. Local memory writes only when a store
path and `--confirm-local` are provided.

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
yonerai ask "summarize public docs" --provider mock --json
yonerai ask "summarize this file" --file notes.txt --workspace . --provider mock --json
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

`yonerai demo`, `yonerai smoke`, `yonerai doctor`, `yonerai status`,
`yonerai manifest verify`, `yonerai plan`, mock `yonerai ask`, mock
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
- Workspace file summarization requires explicit `--file` and `--workspace`.
- Local memory requires explicit `--store` and `--confirm-local`; it is local-only and redacted.
- SafeShell is plan-only for a small diagnostic allowlist; it is not arbitrary shell execution.
- It does not deploy anything.
- Manifest verification is local-file validation only, not installation.
- If `ORA_CORE_API_TOKEN` is set, it is sent as `X-ORA-Core-Token` and is never printed.
