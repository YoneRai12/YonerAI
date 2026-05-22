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
yonerai doctor --json
yonerai manifest verify releases/manifest.example.json
yonerai manifest verify releases/manifest.example.json --json
yonerai message --mode mock "hello"
yonerai run --mode mock "hello"
```

Without installing, run from `clients/cli`:

```bash
python -m yonerai_cli health
```

`yonerai demo` and `yonerai smoke` run in-process and do not require a local Core
API process. The other commands run against a local Core API process. The default
origin is `http://127.0.0.1:8001`.

`yonerai doctor` is an offline, non-mutating diagnostic command. It checks the
Python version, CLI import, demo command availability, credential-free demo
boundary, and the local release manifest example. It does not run the demo,
modify PATH, install packages, download remote code, or connect to live services.
If `ORA_CORE_API_TOKEN` is present, doctor reports only `present_redacted`.

`yonerai manifest verify <path>` validates a local release manifest file. Remote
manifest URLs are rejected, no artifact is downloaded, and no installer is run.
The example manifest is contract-valid but not install-ready because it still
uses a non-production signature placeholder. Optional
`--artifact ARTIFACT_ID=LOCAL_FILE` mappings verify local SHA256 and size only;
output reports artifact ids, not local file paths.

## Boundary

- The CLI only accepts loopback API origins.
- It does not call external providers directly.
- It does not store memory.
- It does not run shell commands.
- It does not deploy anything.
- Manifest verification is local-file validation only, not installation.
- If `ORA_CORE_API_TOKEN` is set, it is sent as `X-ORA-Core-Token` and is never printed.
