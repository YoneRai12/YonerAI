# OpenAI CUA Sidecar Adoption

This document explains how to adopt the official `openai/openai-cua-sample-app`
alongside YonerAI without forcing it into the existing Python and Next.js
runtime layout.

## Why sidecar first

The official sample is a separate monorepo built around:

- `apps/demo-web`: Next.js operator console
- `apps/runner`: Fastify runner
- `packages/*`: shared runner/runtime contracts
- Playwright + Responses API browser workflows

YonerAI already has:

- Python / FastAPI web API
- existing browser router at `src/web/routers/browser.py`
- Next.js web client at `clients/web`
- another UI surface at `ora-ui`

Directly merging the sample into the current repo would create avoidable
conflicts:

- `pnpm` workspace vs current `npm` layout
- Node `22.20.0` expectation vs current project setup
- sample Fastify runner vs existing FastAPI backend
- sample Next.js app vs existing `clients/web` and `ora-ui`

Because of that, the recommended first step is:

1. run the OpenAI sample as a separate sidecar app
2. link to it from YonerAI
3. decide later whether to replace or absorb parts of the current browser stack

## Recommended local ports

Do not reuse the sample defaults as-is because YonerAI already uses common web
ports.

- CUA demo web: `http://127.0.0.1:3100`
- CUA runner: `http://127.0.0.1:4100`

## YonerAI web env

Add these variables to `clients/web/.env.local` when you want the link page to
point at a running sidecar:

```env
NEXT_PUBLIC_CUA_WEB_URL=http://127.0.0.1:3100
NEXT_PUBLIC_CUA_RUNNER_URL=http://127.0.0.1:4100
NEXT_PUBLIC_CUA_DEFAULT_MODEL=gpt-5.4
```

## Suggested adoption flow

1. Clone the official sample outside this repo.
2. Run it as its own service using Node 22, pnpm, and Playwright.
3. Point YonerAI's `/cua` page at the sidecar URLs above.
4. Evaluate whether the sample should remain:
   - a power-user console
   - an internal operator tool
   - a replacement for part of the current browser panel

## What to integrate later

If the sidecar works well, the next realistic integrations are:

- single sign-on / shared auth in front of the demo web
- artifact and replay links from YonerAI into the CUA runner
- mapping YonerAI browser tasks into sample runner scenarios
- extracting only the runner concepts, not the full sample UI

## What not to do yet

- do not copy the whole sample into `clients/web`
- do not replace the existing FastAPI backend with the sample runner
- do not mix the sample package manager into the current repo root

Keep the first adoption reversible.
