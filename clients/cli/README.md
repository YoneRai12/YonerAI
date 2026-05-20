# YonerAI Local CLI Smoke

`clients/cli` is a temporary public MVP smoke CLI for the local YonerAI Core API.
It is not the final product CLI, not a native Japanese CLI, and not a deployment
or operations tool.

## Install For Local Testing

```bash
python -m pip install -e clients/cli
```

After installation, the local command is:

```bash
yonerai health
yonerai message --mode mock "hello"
yonerai run --mode mock "hello"
```

Without installing, run from `clients/cli`:

```bash
python -m yonerai_cli health
```

Run these commands against a local Core API process. The default origin is
`http://127.0.0.1:8001`.

## Boundary

- The CLI only accepts loopback API origins.
- It does not call external providers directly.
- It does not store memory.
- It does not run shell commands.
- It does not deploy anything.
- If `ORA_CORE_API_TOKEN` is set, it is sent as `X-ORA-Core-Token` and is never printed.
