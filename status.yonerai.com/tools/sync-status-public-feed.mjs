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

function usage() {
  console.log(`Usage:
  node status.yonerai.com/tools/sync-status-public-feed.mjs --input <input.json> [--public status-feed.json]
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
  --healthcheck <file>  template used for aws-metrics or yonerai-health inputs
  --public <file>       public feed output path, default status-feed.json
  --workdir <dir>       generated working dir, default generated/sync
  --no-promote          stop after generating feed; do not write public feed

This command validates inputs through the lower-level tools it calls.
`);
}

function parseArgs(argv) {
  const options = {
    input: null,
    healthcheck: null,
    publicFeed: "status-feed.json",
    workdir: "generated/sync",
    promote: true
  };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--help" || arg === "-h") options.help = true;
    else if (arg === "--input") options.input = argv[++index];
    else if (arg === "--healthcheck") options.healthcheck = argv[++index];
    else if (arg === "--public") options.publicFeed = argv[++index];
    else if (arg === "--workdir") options.workdir = argv[++index];
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

if (!options.input) {
  console.error("--input is required");
  usage();
  process.exit(1);
}

const inputPath = resolvePath(options.input, null, true);
const workdir = resolvePath(options.workdir, "generated/sync");
const pipelineDir = path.resolve(workdir, "pipeline");
const publicFeedPath = resolvePath(options.publicFeed, "status-feed.json");
const steps = [];
let ok = false;

try {
  fs.mkdirSync(workdir, { recursive: true });
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

  const pipelineStep = runStep("build-status-pipeline", [
    "tools/build-status-pipeline.mjs",
    toStatusRelative(pipelineInputPath),
    toStatusRelative(pipelineDir),
  ]);
  steps.push(pipelineStep);
  assertStep(pipelineStep);

  if (options.promote) {
    const promoteStep = runStep("promote-public-feed", [
      "tools/promote-status-public-feed.mjs",
      toStatusRelative(path.resolve(pipelineDir, "status-feed.generated.json")),
      toStatusRelative(publicFeedPath),
    ]);
    steps.push(promoteStep);
    assertStep(promoteStep);
  }

  ok = true;
  const reportPath = writeReport(workdir, {
    schema_version: "yonerai.status.sync.report.v1",
    generated_at: new Date().toISOString(),
    ok,
    input: toStatusRelative(inputPath),
    input_schema: schema,
    pipeline_input: toStatusRelative(pipelineInputPath),
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
    public_feed: toStatusRelative(publicFeedPath),
    promoted: false,
    error: String(error?.message || error),
    steps,
  });
  console.error(`Status public feed sync failed. Report: ${toStatusRelative(reportPath)}`);
  console.error(error.message);
  process.exit(1);
}
