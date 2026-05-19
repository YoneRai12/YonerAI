# YonerAI clients/web

`clients/web` is a temporary Web Chat MVP and smoke-demo surface for the public Core API message contract.

It is not the final YonerAI product UI, not a production Web product, and not a deployment target.

## What It Can Do

- Send a message to the local Core API through `POST /v1/public/messages`.
- Use `mock` / `offline` mode for deterministic credential-free smoke checks.
- Use `local` mode with `local_provider: "ollama"` when an Ollama-compatible local server is already running on loopback.
- Use `local` mode with `local_provider: "openai_compatible_local"` for loopback OpenAI-compatible local servers such as LM Studio, llama.cpp / llama-cpp-python server, text-generation-webui OpenAI API mode, or LocalAI.
- Display safe Core API errors without exposing stack traces, secrets, or local paths.

## What It Does Not Do

- It does not call external OpenAI, Anthropic, Gemini, Discord, SNS, or web-search providers.
- It does not accept arbitrary remote provider URLs from the browser.
- It does not implement Google login.
- It does not persist memory or conversation history.
- It does not complete the Discord gateway.
- It does not claim final Web UI or production readiness.

## Local Run

Start the Core API first from the repository root:

```powershell
$env:PYTHONPATH = "$PWD;$PWD\core\src"
$env:ORA_ALLOW_MISSING_SECRETS = "1"
python -m ora_core.main
```

Then start this temporary web client:

```powershell
cd clients\web
npm ci
npm run dev
```

Open `http://127.0.0.1:3000`.

The web client posts to `/api/public/messages`, and `next.config.ts` rewrites that local request to `http://127.0.0.1:8001/v1/public/messages` by default.

If port `8001` is already occupied by another local Core API during development, start the current Core API on another loopback port and set:

```powershell
$env:YONERAI_CORE_API_ORIGIN = "http://127.0.0.1:8011"
npm run dev
```

`YONERAI_CORE_API_ORIGIN` is loopback-only. Remote hosts, LAN hosts, embedded credentials, query strings, and fragments are rejected by the Next config.

## Local LLM Notes

For Ollama-compatible local mode, keep Ollama on a loopback address such as `http://127.0.0.1:11434`.

For OpenAI-compatible local mode, keep the local server on loopback, for example `http://127.0.0.1:1234/v1` for a common LM Studio setup. The Core API owns local base URL validation; this page intentionally does not expose an arbitrary provider URL input.

Model names are passed through to the local server. Availability and quality depend on the local runtime, not on this Web smoke surface.

## Checks

```powershell
npm ci
npm run lint
npm run build
npm audit --omit=dev
npm audit
```
