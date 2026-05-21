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

## Boundary

- The CLI only accepts loopback API origins.
- It does not call external providers directly.
- It does not store memory.
- It does not run shell commands.
- It does not deploy anything.
- If `ORA_CORE_API_TOKEN` is set, it is sent as `X-ORA-Core-Token` and is never printed.
