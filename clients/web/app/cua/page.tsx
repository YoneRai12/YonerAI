const cuaWebUrl = process.env.NEXT_PUBLIC_CUA_WEB_URL || "http://127.0.0.1:3100";
const cuaRunnerUrl = process.env.NEXT_PUBLIC_CUA_RUNNER_URL || "http://127.0.0.1:4100";
const cuaModel = process.env.NEXT_PUBLIC_CUA_DEFAULT_MODEL || "gpt-5.4";

const steps = [
  "Run the official OpenAI CUA sample as a separate sidecar service.",
  "Keep it on its own Node + pnpm + Playwright runtime.",
  "Point YonerAI at the sidecar instead of merging the sample into this web app.",
];

const requirements = [
  "Node.js 22.20.0",
  "pnpm 10.26.0",
  "Playwright Chromium install",
  "OPENAI_API_KEY configured in the sample app",
];

export default function CuaPage() {
  return (
    <main className="min-h-screen bg-[#121418] text-white">
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-8 px-6 py-12">
        <section className="rounded-3xl border border-cyan-400/20 bg-cyan-500/10 p-8 shadow-2xl shadow-cyan-950/20">
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.28em] text-cyan-200/80">
            OpenAI CUA Sidecar
          </p>
          <h1 className="text-4xl font-semibold tracking-tight text-white">
            GPT-5.4 browser operator, connected to YonerAI the safe way.
          </h1>
          <p className="mt-4 max-w-3xl text-sm leading-7 text-cyan-50/85">
            YonerAI already has its own Python backend and browser APIs. The official
            OpenAI CUA sample is best introduced as a separate sidecar app, then linked
            into YonerAI for operator workflows and experiments.
          </p>
          <div className="mt-6 flex flex-wrap gap-3 text-sm">
            <a
              href={cuaWebUrl}
              target="_blank"
              rel="noreferrer"
              className="rounded-full bg-white px-5 py-3 font-medium text-black transition hover:opacity-90"
            >
              Open CUA console
            </a>
            <a
              href={cuaRunnerUrl}
              target="_blank"
              rel="noreferrer"
              className="rounded-full border border-white/15 px-5 py-3 font-medium text-white transition hover:bg-white/5"
            >
              Open runner base URL
            </a>
            <a
              href="https://github.com/openai/openai-cua-sample-app"
              target="_blank"
              rel="noreferrer"
              className="rounded-full border border-cyan-300/25 px-5 py-3 font-medium text-cyan-100 transition hover:bg-cyan-400/10"
            >
              View official repo
            </a>
          </div>
        </section>

        <section className="grid gap-6 md:grid-cols-2">
          <article className="rounded-2xl border border-white/10 bg-white/5 p-6">
            <h2 className="text-lg font-semibold">Current sidecar target</h2>
            <dl className="mt-5 space-y-4 text-sm text-gray-300">
              <div>
                <dt className="text-xs uppercase tracking-[0.24em] text-gray-500">Demo web</dt>
                <dd className="mt-1 break-all text-white">{cuaWebUrl}</dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-[0.24em] text-gray-500">Runner</dt>
                <dd className="mt-1 break-all text-white">{cuaRunnerUrl}</dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-[0.24em] text-gray-500">Default model</dt>
                <dd className="mt-1 text-white">{cuaModel}</dd>
              </div>
            </dl>
          </article>

          <article className="rounded-2xl border border-white/10 bg-white/5 p-6">
            <h2 className="text-lg font-semibold">Sample requirements</h2>
            <ul className="mt-5 space-y-3 text-sm text-gray-300">
              {requirements.map((item) => (
                <li key={item} className="rounded-xl border border-white/8 bg-black/20 px-4 py-3">
                  {item}
                </li>
              ))}
            </ul>
          </article>
        </section>

        <section className="rounded-2xl border border-white/10 bg-[#171b22] p-6">
          <h2 className="text-lg font-semibold">Why not merge it directly?</h2>
          <div className="mt-5 grid gap-4 md:grid-cols-3">
            <div className="rounded-2xl border border-white/8 bg-black/20 p-4">
              <p className="text-xs uppercase tracking-[0.24em] text-gray-500">Runtime split</p>
              <p className="mt-2 text-sm leading-6 text-gray-300">
                The official sample expects a Node 22 + pnpm workspace, while YonerAI is already
                split across Python, FastAPI, Next.js, and Playwright helpers.
              </p>
            </div>
            <div className="rounded-2xl border border-white/8 bg-black/20 p-4">
              <p className="text-xs uppercase tracking-[0.24em] text-gray-500">Safer adoption</p>
              <p className="mt-2 text-sm leading-6 text-gray-300">
                Sidecar adoption keeps the sample reversible. If it fails or drifts, it does not
                break the public YonerAI runtime.
              </p>
            </div>
            <div className="rounded-2xl border border-white/8 bg-black/20 p-4">
              <p className="text-xs uppercase tracking-[0.24em] text-gray-500">Future path</p>
              <p className="mt-2 text-sm leading-6 text-gray-300">
                Once the runner proves useful, YonerAI can integrate replay links, auth, or task
                bridges without importing the whole sample monorepo.
              </p>
            </div>
          </div>
        </section>

        <section className="rounded-2xl border border-white/10 bg-white/[0.03] p-6">
          <h2 className="text-lg font-semibold">Recommended first steps</h2>
          <ol className="mt-5 space-y-3 text-sm text-gray-300">
            {steps.map((item, index) => (
              <li key={item} className="flex gap-4 rounded-xl border border-white/8 bg-black/20 px-4 py-3">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-cyan-400/15 text-cyan-200">
                  {index + 1}
                </span>
                <span className="leading-6">{item}</span>
              </li>
            ))}
          </ol>
          <p className="mt-5 text-sm leading-7 text-gray-400">
            See also: <code className="rounded bg-black/30 px-2 py-1 text-gray-200">docs/OPENAI_CUA_SIDECAR_ADOPTION.md</code>
          </p>
        </section>
      </div>
    </main>
  );
}
