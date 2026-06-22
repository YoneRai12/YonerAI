#!/usr/bin/env node

/*
 * High-level YonerAI Status feed synchronizer.
 *
 * This is the operational wrapper for:
 *
 *   external input -> optional fill -> pipeline -> public feed promotion
 *
 * It never writes DOM and never edits UI/CSS. The browser still consumes only
 * yonerai.status.feed.v1 through the runtime adapter.
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const statusRoot = path.resolve(scriptDir, "..");

const defaultHealthcheckBySchema = {
  "yonerai.status.aws-metrics.v1": "status-healthcheck-input.aws-cloudwatch.example.json",
  "yonerai.status.yonerai-health.v1": "status-healthcheck-input.yonerai-api-http.example.json"
};

const allowedSnapshotHosts = new Set(["api-staging.yonerai.com"]);
const maxSnapshotBytes = 1_000_000;

function usage() {
  console.log(`Usage:
  node status.yonerai.com/tools/sync-status-public-feed.mjs --input <input.json> [--public status-feed.json]
  node status.yonerai.com/tools/sync-status-public-feed.mjs --input-url <https://.../v1/status> [--public status-feed.json]
  node tools/sync-status-public-feed.mjs --input <input.json> [--healthcheck template.json] [--public status-feed.json]

Accepted input schemas:
  yonerai.status.v1
  yonerai.status.healthcheck.v1
  yonerai.status.monitor.v1
  yonerai.status.source.v1
  yonerai.status.aws-metrics.v1
  yonerai.status.yonerai-health.v1

Options:
  --input <file>        required input JSON
  --input-url <url>     fetch a public-safe yonerai.status.v1 snapshot
  --healthcheck <file>  template used for aws-metrics or yonerai-health inputs
  --public <file>       public feed output path, default status-feed.json
  --workdir <dir>       generated working dir, default generated/sync
  --etag-file <file>    upstream ETag cache, default <workdir>/status-upstream.etag
  --last-known-good <file>
                        validated feed fallback, default <workdir>/status-feed.last-known-good.json
  --refresh-ms <ms>     browser same-origin refresh interval, default 15000
  --no-promote          stop after generating feed; do not write public feed

This command validates inputs through the lower-level tools it calls.
`);
}

function parseArgs(argv) {
  const options = {
    input: null,
    inputUrl: null,
    healthcheck: null,
    publicFeed: "status-feed.json",
    workdir: "generated/sync",
    etagFile: null,
    lastKnownGood: null,
    refreshMs: 15000,
    promote: true
  };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--help" || arg === "-h") options.help = true;
    else if (arg === "--input") options.input = argv[++index];
    else if (arg === "--input-url") options.inputUrl = argv[++index];
    else if (arg === "--healthcheck") options.healthcheck = argv[++index];
    else if (arg === "--public") options.publicFeed = argv[++index];
    else if (arg === "--workdir") options.workdir = argv[++index];
    else if (arg === "--etag-file") options.etagFile = argv[++index];
    else if (arg === "--last-known-good") options.lastKnownGood = argv[++index];
    else if (arg === "--refresh-ms") options.refreshMs = Number(argv[++index]);
    else if (arg === "--no-promote") options.promote = false;
    else throw new Error(`unknown argument: ${arg}`);
  }
  return options;
}

function resolvePath(value, fallback, mustExist = false) {
  const chosen = value || fallback;
  if (!chosen) return null;
  if (path.isAbsolute(chosen)) return chosen;
  const cwdPath = path.resolve(process.cwd(), chosen);
  const statusPath = path.resolve(statusRoot, chosen);
  if (mustExist && fs.existsSync(cwdPath)) return cwdPath;
  if (mustExist && fs.existsSync(statusPath)) return statusPath;
  if (chosen.replaceAll("\\", "/").startsWith("status.yonerai.com/")) return cwdPath;
  return statusPath;
}

function toStatusRelative(file) {
  return path.relative(statusRoot, file).replaceAll("\\", "/");
}

function readSchema(file) {
  return JSON.parse(fs.readFileSync(file, "utf8"))?.schema_version || "";
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

function writeJson(file, value) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

function atomicCopyFile(source, target) {
  fs.mkdirSync(path.dirname(target), { recursive: true });
  const pending = `${target}.pending-${process.pid}-${Date.now()}`;
  try {
    fs.copyFileSync(source, pending);
    fs.renameSync(pending, target);
  } finally {
    fs.rmSync(pending, { force: true });
  }
}

function runStep(name, args) {
  const startedAt = new Date().toISOString();
  const result = spawnSync(process.execPath, args, {
    cwd: statusRoot,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  });
  return {
    name,
    command: `node ${args.join(" ")}`,
    ok: result.status === 0,
    status: result.status,
    signal: result.signal,
    started_at: startedAt,
    finished_at: new Date().toISOString(),
    stdout: (result.stdout || "").trim(),
    stderr: (result.stderr || "").trim(),
    error: result.error ? String(result.error.message || result.error) : null,
  };
}

function writeReport(workdir, report) {
  const reportPath = path.resolve(workdir, "status-sync-report.json");
  fs.mkdirSync(path.dirname(reportPath), { recursive: true });
  fs.writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`, "utf8");
  return reportPath;
}

function assertStep(step) {
  if (!step.ok) {
    throw new Error(`${step.name} failed\n${step.stderr || step.stdout || step.error || "no output"}`);
  }
}

function assertRefreshMs(value) {
  if (!Number.isInteger(value) || value < 5000 || value > 300000) {
    throw new Error("--refresh-ms must be an integer from 5000 to 300000");
  }
}

function assertPublicSnapshotUrl(value) {
  const url = new URL(value);
  if (url.protocol !== "https:") {
    throw new Error("--input-url must be https");
  }
  if (!allowedSnapshotHosts.has(url.hostname.toLowerCase())) {
    throw new Error("--input-url host is not approved for public status ingestion");
  }
  if (url.username || url.password) {
    throw new Error("--input-url must not include credentials");
  }
  for (const key of url.searchParams.keys()) {
    if (/(token|secret|key|code|session|account|email)/i.test(key)) {
      throw new Error("--input-url must not include credential-like query parameters");
    }
  }
  return url;
}

function publicText(value) {
  if (typeof value === "string") return value;
  if (value && typeof value === "object") {
    return {
      ...(typeof value.ja === "string" ? { ja: value.ja } : {}),
      ...(typeof value.en === "string" ? { en: value.en } : {}),
    };
  }
  return "";
}

function normalizeComponents(value) {
  if (Array.isArray(value)) return value;
  if (value && typeof value === "object") return Object.values(value);
  return [];
}

function projectSnapshotComponent(component) {
  return {
    id: String(component?.id || ""),
    health: String(component?.health || "unknown"),
    availability: String(component?.availability || "limited"),
    stage: String(component?.stage || "staging"),
    message: publicText(component?.message),
    updated_at: typeof component?.updated_at === "string" ? component.updated_at : null,
    stale: Boolean(component?.stale),
    incident_ref: component?.incident_ref == null ? null : String(component.incident_ref),
  };
}

function projectStatusSnapshot(raw) {
  const snapshot = raw?.public_status?.schema_version === "yonerai.status.v1" ? raw.public_status : raw;
  const projected = {
    schema_version: "yonerai.status.v1",
    snapshot_id: String(snapshot?.snapshot_id || ""),
    generated_at: String(snapshot?.generated_at || ""),
    stale_after_seconds: Number(snapshot?.stale_after_seconds || 0),
    overall: {
      health: String(snapshot?.overall?.health || "unknown"),
      availability: String(snapshot?.overall?.availability || "limited"),
      stage: String(snapshot?.overall?.stage || "staging"),
      message: publicText(snapshot?.overall?.message),
    },
    components: normalizeComponents(snapshot?.components).map(projectSnapshotComponent),
  };
  return projected;
}

function oversizedSnapshotError() {
  const error = new Error("upstream status endpoint returned an oversized snapshot");
  error.publicCode = "upstream_invalid";
  return error;
}

async function readBoundedResponseText(response) {
  const contentLength = response.headers.get("content-length");
  if (contentLength && Number.parseInt(contentLength, 10) > maxSnapshotBytes) {
    throw oversizedSnapshotError();
  }

  if (!response.body?.getReader) {
    const text = await response.text();
    if (Buffer.byteLength(text, "utf8") > maxSnapshotBytes) throw oversizedSnapshotError();
    return text;
  }

  const reader = response.body.getReader();
  const chunks = [];
  let total = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    total += value.byteLength;
    if (total > maxSnapshotBytes) {
      try {
        await reader.cancel();
      } catch {
        // ignore cancellation errors; the public error class is enough.
      }
      throw oversizedSnapshotError();
    }
    chunks.push(value);
  }

  const bytes = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return new TextDecoder().decode(bytes);
}

async function fetchSnapshotFromUrl(url, workdir, etagFile) {
  const headers = { Accept: "application/json" };
  if (etagFile && fs.existsSync(etagFile)) {
    const previousEtag = fs.readFileSync(etagFile, "utf8").trim();
    if (previousEtag) headers["If-None-Match"] = previousEtag;
  }

  const response = await fetch(url, { headers, redirect: "manual", signal: AbortSignal.timeout(10000) });
  if (response.status === 304) {
    return { notModified: true, status: 304, etag: response.headers.get("etag") || null };
  }
  if (response.status >= 300 && response.status < 400) {
    const error = new Error("upstream status endpoint redirected unexpectedly");
    error.publicCode = "upstream_unavailable";
    throw error;
  }
  if (!response.ok) {
    const error = new Error("upstream status endpoint unavailable");
    error.publicCode = "upstream_unavailable";
    throw error;
  }

  const text = await readBoundedResponseText(response);

  let snapshot;
  try {
    snapshot = JSON.parse(text);
  } catch {
    const error = new Error("upstream status endpoint returned invalid JSON");
    error.publicCode = "upstream_invalid";
    throw error;
  }

  if (snapshot?.schema_version !== "yonerai.status.v1") {
    const error = new Error("upstream status endpoint returned an unsupported schema");
    error.publicCode = "upstream_invalid_schema";
    throw error;
  }

  const projected = projectStatusSnapshot(snapshot);
  const snapshotPath = path.resolve(workdir, "status-snapshot.live.json");
  writeJson(snapshotPath, projected);

  const etag = response.headers.get("etag");
  return { inputPath: snapshotPath, status: response.status, etag: etag || null };
}

function persistAcceptedEtag(etagFile, etag) {
  if (!etagFile || !etag) return;
  fs.mkdirSync(path.dirname(etagFile), { recursive: true });
  fs.writeFileSync(etagFile, `${etag}\n`, "utf8");
}

function decorateLiveFeed(feed, options, liveStatus) {
  const meta = {
    ...(feed.meta || {}),
    source: feed.meta?.source || "status-snapshot-v1",
    live_monitoring: true,
    refresh_ms: options.refreshMs,
    live_ingestion: {
      enabled: true,
      status: liveStatus,
      mode: "public-safe-status-snapshot",
      same_origin_browser_feed: true,
      browser_calls_upstream: false,
      refreshed_at: new Date().toISOString(),
    },
  };
  return { ...feed, meta };
}

function markDayStale(day, degradedState) {
  const next = { ...day, stale: true };
  if (next.state === "operational" || next.status === "operational") {
    next.state = "degraded";
    if (Object.hasOwn(next, "status")) next.status = "degraded";
    next.color = degradedState?.color || "#d89614";
    next.label = degradedState?.label || { ja: "性能低下", en: "Degraded" };
    next.message = {
      ja: "最新ステータス取得が失敗したため、この日の稼働中表示を stale/degraded として扱います。",
      en: "Latest status fetch failed, so this operational day is treated as stale/degraded.",
    };
  }
  return next;
}

function markChildStale(child, degradedState) {
  const next = { ...child, stale: true };
  if (next.state === "operational") next.state = "degraded";
  next.days = Array.isArray(next.days) ? next.days.map((day) => markDayStale(day, degradedState)) : [];
  next.fact = {
    ja: "最新ステータス取得が失敗したため、最後に検証済みのステータスを stale/degraded として表示しています。",
    en: "Latest status fetch failed, so the last validated status is shown as stale/degraded.",
  };
  return next;
}

function decorateFallbackFeed(feed, options) {
  const next = decorateLiveFeed(feed, options, "stale");
  const degradedState = next.states?.degraded || null;
  next.meta = {
    ...next.meta,
    stale: true,
    live_ingestion: {
      ...next.meta.live_ingestion,
      stale: true,
      fallback: "last_known_good",
      fallback_reason: "upstream_unavailable_or_invalid",
    },
    note: {
      ja: "最新ステータス取得に失敗したため、最後に検証済みのステータスを表示しています。履歴データの補完は行っていません。",
      en: "Latest status fetch failed, so the last validated status is displayed. History data is not backfilled.",
    },
  };
  next.categories = Array.isArray(next.categories)
    ? next.categories.map((category) => ({
        ...category,
        stale: true,
        state: category.state === "operational" ? "degraded" : category.state,
        children: Array.isArray(category.children) ? category.children.map((child) => markChildStale(child, degradedState)) : [],
      }))
    : [];
  return next;
}

function validateFeedFile(file, steps) {
  const validateStep = runStep("validate-status-feed", [
    "tools/validate-status-feed.mjs",
    toStatusRelative(file),
  ]);
  steps.push(validateStep);
  assertStep(validateStep);

  const safetyStep = runStep("validate-public-feed-safety", [
    "tools/validate-status-public-feed-safety.mjs",
    toStatusRelative(file),
  ]);
  steps.push(safetyStep);
  assertStep(safetyStep);
}

function writeFallbackFeed(lastKnownGoodPath, publicFeedPath, options, steps) {
  if (!lastKnownGoodPath || !fs.existsSync(lastKnownGoodPath)) {
    const error = new Error("upstream status fetch failed and no last-known-good feed exists");
    error.publicCode = "no_last_known_good";
    throw error;
  }
  const fallbackPath = path.resolve(path.dirname(lastKnownGoodPath), "status-feed.fallback.pending.json");
  writeJson(fallbackPath, decorateFallbackFeed(readJson(lastKnownGoodPath), options));
  validateFeedFile(fallbackPath, steps);
  if (options.promote) {
    atomicCopyFile(fallbackPath, publicFeedPath);
  }
  return fallbackPath;
}

function writeNotModifiedFeed(lastKnownGoodPath, publicFeedPath, options, steps) {
  if (!lastKnownGoodPath || !fs.existsSync(lastKnownGoodPath)) {
    const error = new Error("upstream status snapshot was not modified and no last-known-good feed exists");
    error.publicCode = "no_last_known_good";
    throw error;
  }
  const notModifiedPath = path.resolve(path.dirname(lastKnownGoodPath), "status-feed.not-modified.pending.json");
  writeJson(notModifiedPath, decorateLiveFeed(readJson(lastKnownGoodPath), options, "not_modified"));
  validateFeedFile(notModifiedPath, steps);
  if (options.promote) {
    atomicCopyFile(notModifiedPath, publicFeedPath);
  }
  return notModifiedPath;
}

let options;
try {
  options = parseArgs(process.argv.slice(2));
} catch (error) {
  console.error(error.message);
  usage();
  process.exit(1);
}

if (options.help) {
  usage();
  process.exit(0);
}

if ((options.input && options.inputUrl) || (!options.input && !options.inputUrl)) {
  console.error("exactly one of --input or --input-url is required");
  usage();
  process.exit(1);
}

assertRefreshMs(options.refreshMs);

let inputPath = options.input ? resolvePath(options.input, null, true) : null;
const workdir = resolvePath(options.workdir, "generated/sync");
const pipelineDir = path.resolve(workdir, "pipeline");
const publicFeedPath = resolvePath(options.publicFeed, "status-feed.json");
const etagFile = resolvePath(options.etagFile, path.join(toStatusRelative(workdir), "status-upstream.etag"));
const lastKnownGoodPath = resolvePath(
  options.lastKnownGood,
  path.join(toStatusRelative(workdir), "status-feed.last-known-good.json"),
);
const steps = [];
let ok = false;
let acceptedEtag = null;
let validatedInputUrl = null;
try {
  validatedInputUrl = options.inputUrl ? assertPublicSnapshotUrl(options.inputUrl) : null;
} catch (error) {
  console.error(error.message);
  process.exit(1);
}
const upstream = {
  input_url: validatedInputUrl ? validatedInputUrl.origin + validatedInputUrl.pathname : null,
  fetched: false,
  not_modified: false,
  fallback_used: false,
};

try {
  fs.mkdirSync(workdir, { recursive: true });
  if (validatedInputUrl) {
    const url = validatedInputUrl;
    try {
      const fetched = await fetchSnapshotFromUrl(url, workdir, etagFile);
      upstream.fetched = true;
      upstream.not_modified = Boolean(fetched.notModified);
      if (fetched.notModified) {
        const notModifiedFeed = writeNotModifiedFeed(lastKnownGoodPath, publicFeedPath, options, steps);
        ok = true;
        const reportPath = writeReport(workdir, {
          schema_version: "yonerai.status.sync.report.v1",
          generated_at: new Date().toISOString(),
          ok,
          input: null,
          input_schema: null,
          upstream,
          public_feed: options.promote ? toStatusRelative(publicFeedPath) : null,
          not_modified_feed: toStatusRelative(notModifiedFeed),
          promoted: options.promote,
          steps,
        });
        console.log(`Status public feed sync complete from last-known-good. Report: ${toStatusRelative(reportPath)}`);
        process.exit(0);
      }
      inputPath = fetched.inputPath;
      acceptedEtag = fetched.etag || null;
    } catch (error) {
      const fallbackFeed = writeFallbackFeed(lastKnownGoodPath, publicFeedPath, options, steps);
      upstream.fallback_used = true;
      ok = true;
      const reportPath = writeReport(workdir, {
        schema_version: "yonerai.status.sync.report.v1",
        generated_at: new Date().toISOString(),
        ok,
        input: null,
        input_schema: null,
        upstream: { ...upstream, error: error.publicCode || "upstream_unavailable" },
        public_feed: options.promote ? toStatusRelative(publicFeedPath) : null,
        fallback_feed: toStatusRelative(fallbackFeed),
        promoted: options.promote,
        steps,
      });
      console.log(`Status public feed sync complete from last-known-good. Report: ${toStatusRelative(reportPath)}`);
      process.exit(0);
    }
  }

  const schema = readSchema(inputPath);
  let pipelineInputPath = inputPath;

  if (schema === "yonerai.status.aws-metrics.v1") {
    const template = resolvePath(options.healthcheck, defaultHealthcheckBySchema[schema], true);
    pipelineInputPath = path.resolve(workdir, "status-healthcheck-input.aws-filled.json");
    const step = runStep("fill-aws-metrics", [
      "tools/fill-status-aws-metrics.mjs",
      toStatusRelative(template),
      toStatusRelative(inputPath),
      toStatusRelative(pipelineInputPath),
    ]);
    steps.push(step);
    assertStep(step);
  } else if (schema === "yonerai.status.yonerai-health.v1") {
    const template = resolvePath(options.healthcheck, defaultHealthcheckBySchema[schema], true);
    pipelineInputPath = path.resolve(workdir, "status-healthcheck-input.yonerai-filled.json");
    const step = runStep("fill-yonerai-health", [
      "tools/fill-status-yonerai-health.mjs",
      toStatusRelative(template),
      toStatusRelative(inputPath),
      toStatusRelative(pipelineInputPath),
    ]);
    steps.push(step);
    assertStep(step);
  } else if (![
    "yonerai.status.v1",
    "yonerai.status.healthcheck.v1",
    "yonerai.status.monitor.v1",
    "yonerai.status.source.v1"
  ].includes(schema)) {
    throw new Error(`unsupported input schema: ${schema || "(missing)"}`);
  }

  try {
    const pipelineStep = runStep("build-status-pipeline", [
      "tools/build-status-pipeline.mjs",
      toStatusRelative(pipelineInputPath),
      toStatusRelative(pipelineDir),
    ]);
    steps.push(pipelineStep);
    assertStep(pipelineStep);

    const generatedFeedPath = path.resolve(pipelineDir, "status-feed.generated.json");
    if (options.inputUrl) {
      writeJson(generatedFeedPath, decorateLiveFeed(readJson(generatedFeedPath), options, "live"));
    }
    validateFeedFile(generatedFeedPath, steps);
    if (options.inputUrl) {
      atomicCopyFile(generatedFeedPath, lastKnownGoodPath);
      persistAcceptedEtag(etagFile, acceptedEtag);
    }

    if (options.promote) {
      const promoteStep = runStep("promote-public-feed", [
        "tools/promote-status-public-feed.mjs",
        toStatusRelative(generatedFeedPath),
        toStatusRelative(publicFeedPath),
      ]);
      steps.push(promoteStep);
      assertStep(promoteStep);
    }
  } catch (error) {
    if (!options.inputUrl) throw error;
    const fallbackFeed = writeFallbackFeed(lastKnownGoodPath, publicFeedPath, options, steps);
    upstream.fallback_used = true;
    ok = true;
    const reportPath = writeReport(workdir, {
      schema_version: "yonerai.status.sync.report.v1",
      generated_at: new Date().toISOString(),
      ok,
      input: inputPath ? toStatusRelative(inputPath) : null,
      input_schema: schema,
      upstream: { ...upstream, error: "pipeline_invalid" },
      pipeline_input: toStatusRelative(pipelineInputPath),
      public_feed: options.promote ? toStatusRelative(publicFeedPath) : null,
      fallback_feed: toStatusRelative(fallbackFeed),
      promoted: options.promote,
      steps,
    });
    console.log(`Status public feed sync complete from last-known-good. Report: ${toStatusRelative(reportPath)}`);
    process.exit(0);
  }

  ok = true;
  const reportPath = writeReport(workdir, {
    schema_version: "yonerai.status.sync.report.v1",
    generated_at: new Date().toISOString(),
    ok,
    input: toStatusRelative(inputPath),
    input_schema: schema,
    upstream,
    pipeline_input: toStatusRelative(pipelineInputPath),
    last_known_good: options.inputUrl ? toStatusRelative(lastKnownGoodPath) : null,
    public_feed: options.promote ? toStatusRelative(publicFeedPath) : null,
    promoted: options.promote,
    steps,
  });
  console.log(`Status public feed sync complete. Report: ${toStatusRelative(reportPath)}`);
  if (options.promote) console.log(`Public feed: ${toStatusRelative(publicFeedPath)}`);
} catch (error) {
  const reportPath = writeReport(workdir, {
    schema_version: "yonerai.status.sync.report.v1",
    generated_at: new Date().toISOString(),
    ok,
    input: inputPath ? toStatusRelative(inputPath) : null,
    upstream,
    public_feed: toStatusRelative(publicFeedPath),
    promoted: false,
    error: error?.publicCode || String(error?.message || error),
    steps,
  });
  console.error(`Status public feed sync failed. Report: ${toStatusRelative(reportPath)}`);
  console.error(error.message);
  process.exit(1);
}
