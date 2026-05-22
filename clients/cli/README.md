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
yonerai message --mode mock "hello"
yonerai run --mode mock "hello"
```

Without installing, run from `clients/cli`:

```bash
python -m yonerai_cli health
```

`yonerai demo`, `yonerai smoke`, `yonerai doctor`, `yonerai status`, and
`yonerai manifest verify` run locally and do not require a local Core API
process. `health`, `message`, and `run` run against a local Core API process.
The default origin is `http://127.0.0.1:8001`.

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

## Boundary

- The CLI only accepts loopback API origins.
- It does not call external providers directly.
- It does not store memory.
- It does not run shell commands.
- It does not deploy anything.
- Manifest verification is local-file validation only, not installation.
- If `ORA_CORE_API_TOKEN` is set, it is sent as `X-ORA-Core-Token` and is never printed.
