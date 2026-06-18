#!/usr/bin/env node
import { copyFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, isAbsolute, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const statusRoot = resolve(scriptDir, "..");

function usage() {
  console.log(`Usage:
  node status.yonerai.com/tools/build-status-pipeline.mjs [status-input.json] [output-dir] [--skip-validate]
  node tools/build-status-pipeline.mjs [status-input.json] [output-dir] [--skip-validate]

Default input:
  status-monitor-results.example.json

Supported input schemas:
  yonerai.status.v1
  yonerai.status.healthcheck.v1
  yonerai.status.monitor.v1
  yonerai.status.source.v1

Default output dir:
  generated

Outputs:
  generated/status-monitor-results.generated.json
  generated/status-feed.source.generated.json
  generated/status-feed.generated.json
  generated/status-feed.pipeline-report.json
`);
}

function parseArgs(argv) {
  const options = { validate: true, positionals: [] };
  for (const arg of argv) {
    if (arg === "--help" || arg === "-h") {
      options.help = true;
    } else if (arg === "--skip-validate" || arg === "--no-validate") {
      options.validate = false;
    } else {
      options.positionals.push(arg);
    }
  }
  return options;
}

function isStatusPrefixed(value) {
  return value.replaceAll("\\", "/").startsWith("status.yonerai.com/");
}

function toInputPath(value) {
  if (!value) return resolve(statusRoot, "status-monitor-results.example.json");
  if (isAbsolute(value)) return value;
  const cwdPath = resolve(process.cwd(), value);
  const statusPath = resolve(statusRoot, value);
  if (existsSync(cwdPath)) return cwdPath;
  if (existsSync(statusPath)) return statusPath;
  return isStatusPrefixed(value) ? cwdPath : statusPath;
}

function toOutputDir(value) {
  if (!value) return resolve(statusRoot, "generated");
  if (isAbsolute(value)) return value;
  return isStatusPrefixed(value) ? resolve(process.cwd(), value) : resolve(statusRoot, value);
}

function toStatusRelative(value) {
  return relative(statusRoot, value).replaceAll("\\", "/");
}

function runStep(name, args) {
  const startedAt = new Date().toISOString();
  const result = spawnSync(process.execPath, args, {
    cwd: statusRoot,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  });
  const finishedAt = new Date().toISOString();
  return {
    name,
    command: `node ${args.join(" ")}`,
    status: result.status,
    signal: result.signal,
    ok: result.status === 0,
    started_at: startedAt,
    finished_at: finishedAt,
    stdout: (result.stdout || "").trim(),
    stderr: (result.stderr || "").trim(),
    error: result.error ? String(result.error.message || result.error) : null,
  };
}

function runOperation(name, command, operation) {
  const startedAt = new Date().toISOString();
  try {
    operation();
    return {
      name,
      command,
      status: 0,
      signal: null,
      ok: true,
      started_at: startedAt,
      finished_at: new Date().toISOString(),
      stdout: "",
      stderr: "",
      error: null,
    };
  } catch (error) {
    return {
      name,
      command,
      status: 1,
      signal: null,
      ok: false,
      started_at: startedAt,
      finished_at: new Date().toISOString(),
      stdout: "",
      stderr: "",
      error: String(error?.message || error),
    };
  }
}

function inputSchema(file) {
  try {
    return JSON.parse(readFileSync(file, "utf8"))?.schema_version || "";
  } catch {
    return "";
  }
}

const options = parseArgs(process.argv.slice(2));
if (options.help) {
  usage();
  process.exit(0);
}

const inputPath = toInputPath(options.positionals[0]);
const outputDir = toOutputDir(options.positionals[1]);
const monitorOut = resolve(outputDir, "status-monitor-results.generated.json");
const sourceOut = resolve(outputDir, "status-feed.source.generated.json");
const feedOut = resolve(outputDir, "status-feed.generated.json");
const feedPendingOut = resolve(outputDir, "status-feed.generated.pending.json");
const reportOut = resolve(outputDir, "status-feed.pipeline-report.json");

mkdirSync(outputDir, { recursive: true });

const steps = [];
let ok = true;

if (!existsSync(inputPath)) {
  ok = false;
  steps.push({
    name: "input",
    ok: false,
    status: 1,
    command: "input exists",
    stdout: "",
    stderr: `Missing monitor result input: ${inputPath}`,
    error: null,
  });
} else {
  const schema = inputSchema(inputPath);
  let monitorInputPath = inputPath;
  let sourceInputPath = inputPath;

  if (schema === "yonerai.status.v1") {
    const validateSnapshot = runStep("validate-status-snapshot", [
      "tools/validate-status-snapshot.mjs",
      toStatusRelative(inputPath),
    ]);
    steps.push(validateSnapshot);
    ok = ok && validateSnapshot.ok;

    if (ok) {
      const snapshotToSource = runStep("snapshot-to-source", [
        "tools/build-status-source-from-snapshot.mjs",
        toStatusRelative(inputPath),
        toStatusRelative(sourceOut),
      ]);
      steps.push(snapshotToSource);
      ok = ok && snapshotToSource.ok;
      sourceInputPath = sourceOut;
    }
  } else if (schema === "yonerai.status.healthcheck.v1") {
    const validateHealthcheck = runStep("validate-healthcheck-input", [
      "tools/validate-status-healthcheck.mjs",
      toStatusRelative(inputPath),
    ]);
    steps.push(validateHealthcheck);
    ok = ok && validateHealthcheck.ok;

    if (ok) {
      const healthcheckToMonitor = runStep("healthcheck-to-monitor", [
        "tools/collect-status-healthchecks.mjs",
        toStatusRelative(inputPath),
        toStatusRelative(monitorOut),
      ]);
      steps.push(healthcheckToMonitor);
      ok = ok && healthcheckToMonitor.ok;
      monitorInputPath = monitorOut;
      sourceInputPath = sourceOut;
    }
  } else if (schema === "yonerai.status.monitor.v1") {
    monitorInputPath = inputPath;
    sourceInputPath = sourceOut;
  } else if (schema === "yonerai.status.source.v1") {
    sourceInputPath = inputPath;
  } else {
    ok = false;
    steps.push({
      name: "detect-input-schema",
      ok: false,
      status: 1,
      command: "read schema_version",
      stdout: "",
      stderr: `Unsupported status input schema: ${schema || "(missing)"}`,
      error: null,
    });
  }

  if (ok && schema !== "yonerai.status.source.v1" && schema !== "yonerai.status.v1") {
    const validateMonitor = runStep("validate-monitor-input", [
      "tools/validate-status-input.mjs",
      toStatusRelative(monitorInputPath),
    ]);
    steps.push(validateMonitor);
    ok = ok && validateMonitor.ok;

    if (ok) {
      const monitorToSource = runStep("monitor-to-source", [
        "tools/build-status-source-from-monitor.mjs",
        toStatusRelative(monitorInputPath),
        toStatusRelative(sourceOut),
      ]);
      steps.push(monitorToSource);
      ok = ok && monitorToSource.ok;
    }
  }

  if (ok) {
    const validateSource = runStep("validate-source-input", [
      "tools/validate-status-input.mjs",
      toStatusRelative(sourceInputPath),
    ]);
    steps.push(validateSource);
    ok = ok && validateSource.ok;
  }

  if (ok) {
    const sourceToFeed = runStep("source-to-feed", [
      "tools/build-status-feed.mjs",
      toStatusRelative(sourceInputPath),
      toStatusRelative(feedPendingOut),
    ]);
    steps.push(sourceToFeed);
    ok = ok && sourceToFeed.ok;
  }

  if (ok && options.validate) {
    const validateFeed = runStep("validate-feed", [
      "tools/validate-status-feed.mjs",
      toStatusRelative(feedPendingOut),
    ]);
    steps.push(validateFeed);
    ok = ok && validateFeed.ok;
  }

  if (ok && options.validate) {
    const validatePublicSafety = runStep("validate-public-feed-safety", [
      "tools/validate-status-public-feed-safety.mjs",
      toStatusRelative(feedPendingOut),
    ]);
    steps.push(validatePublicSafety);
    ok = ok && validatePublicSafety.ok;
  }

  if (ok) {
    const promoteFeed = runOperation(
      options.validate ? "promote-validated-feed" : "promote-unvalidated-feed",
      `copy ${toStatusRelative(feedPendingOut)} ${toStatusRelative(feedOut)}`,
      () => copyFileSync(feedPendingOut, feedOut),
    );
    steps.push(promoteFeed);
    ok = ok && promoteFeed.ok;
  }
}

const report = {
  schema_version: "yonerai.status.pipeline.report.v1",
  generated_at: new Date().toISOString(),
  ok,
  status_root: statusRoot,
  input: toStatusRelative(inputPath),
  input_schema: inputSchema(inputPath) || null,
  outputs: {
    monitor: toStatusRelative(monitorOut),
    source: toStatusRelative(sourceOut),
    feed: toStatusRelative(feedOut),
    pending_feed: toStatusRelative(feedPendingOut),
    report: toStatusRelative(reportOut),
  },
  validation: options.validate ? "enabled" : "skipped",
  feed_promotion: options.validate ? "validated-and-public-safe-only" : "unvalidated-debug",
  steps,
};

writeFileSync(reportOut, `${JSON.stringify(report, null, 2)}\n`, "utf8");

if (!ok) {
  console.error(`Status pipeline failed. Report: ${toStatusRelative(reportOut)}`);
  process.exit(1);
}

console.log(`Status pipeline complete. Feed: ${toStatusRelative(feedOut)}`);
console.log(`Report: ${toStatusRelative(reportOut)}`);
