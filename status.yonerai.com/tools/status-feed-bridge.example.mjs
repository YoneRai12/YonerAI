#!/usr/bin/env node

/*
 * Example status-input bridge for YonerAI Status.
 *
 * This script converts healthcheck, monitor, or source JSON into a validated
 * public browser feed and promotes it atomically to a feed file that the local
 * dev server or a hosting layer can serve.
 *
 * It intentionally does not know DOM, bars, route state, tooltip state, or
 * incident panel state. The browser runtime owns rendering.
 */

import { copyFileSync, existsSync, mkdirSync, renameSync, rmSync, writeFileSync } from "node:fs";
import { dirname, isAbsolute, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import fs from "node:fs";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const statusRoot = resolve(scriptDir, "..");

function usage() {
  console.log(`Usage:
  node status.yonerai.com/tools/status-feed-bridge.example.mjs [status-input.json] [public-feed.json] [--watch]
  node tools/status-feed-bridge.example.mjs [status-input.json] [public-feed.json] [--watch]

Environment:
  STATUS_MONITOR_FILE       status input JSON path
  STATUS_PUBLIC_FEED_FILE   output feed JSON path
  STATUS_PIPELINE_DIR       temporary pipeline output dir

Default status input:
  status-monitor-results.example.json

Default public feed output:
  generated/status-feed.live.json

This is an integration example. It keeps the last published feed if validation
or generation fails.
`);
}

function parseArgs(argv) {
  const options = { positionals: [], watch: false };
  for (const arg of argv) {
    if (arg === "--help" || arg === "-h") {
      options.help = true;
    } else if (arg === "--watch") {
      options.watch = true;
    } else {
      options.positionals.push(arg);
    }
  }
  return options;
}

function statusPath(value, fallback) {
  const chosen = value || fallback;
  if (isAbsolute(chosen)) return chosen;
  const cwdPath = resolve(process.cwd(), chosen);
  if (existsSync(cwdPath)) return cwdPath;
  if (chosen.replaceAll("\\", "/").startsWith("status.yonerai.com/")) return cwdPath;
  return resolve(statusRoot, chosen);
}

function toStatusRelative(value) {
  return relative(statusRoot, value).replaceAll("\\", "/");
}

function writeReport(reportPath, report) {
  mkdirSync(dirname(reportPath), { recursive: true });
  writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`, "utf8");
}

function runPipeline(inputPath, pipelineDir) {
  return spawnSync(process.execPath, [
    "tools/build-status-pipeline.mjs",
    toStatusRelative(inputPath),
    toStatusRelative(pipelineDir),
  ], {
    cwd: statusRoot,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  });
}

function promoteAtomically(sourcePath, publicFeedPath) {
  mkdirSync(dirname(publicFeedPath), { recursive: true });
  const pendingPath = `${publicFeedPath}.pending-${process.pid}`;
  copyFileSync(sourcePath, pendingPath);
  renameSync(pendingPath, publicFeedPath);
}

function bridgeOnce({ inputPath, publicFeedPath, pipelineDir, reportPath }) {
  const startedAt = new Date().toISOString();
  const result = runPipeline(inputPath, pipelineDir);
  const generatedFeed = resolve(pipelineDir, "status-feed.generated.json");
  const report = {
    schema_version: "yonerai.status.bridge.report.v1",
    generated_at: new Date().toISOString(),
    ok: false,
    input: toStatusRelative(inputPath),
    public_feed: toStatusRelative(publicFeedPath),
    pipeline_dir: toStatusRelative(pipelineDir),
    started_at: startedAt,
    finished_at: new Date().toISOString(),
    pipeline_status: result.status,
    stdout: (result.stdout || "").trim(),
    stderr: (result.stderr || "").trim(),
    error: result.error ? String(result.error.message || result.error) : null,
    promotion: "not-attempted",
  };

  if (result.status === 0 && existsSync(generatedFeed)) {
    try {
      promoteAtomically(generatedFeed, publicFeedPath);
      report.ok = true;
      report.promotion = "atomic-replace";
    } catch (error) {
      report.error = String(error?.message || error);
      report.promotion = "failed-keep-previous";
    }
  } else {
    report.promotion = "failed-keep-previous";
  }

  writeReport(reportPath, report);

  if (!report.ok) {
    console.error(`Status feed bridge failed. Previous feed was kept. Report: ${toStatusRelative(reportPath)}`);
    return false;
  }

  console.log(`Status feed published: ${toStatusRelative(publicFeedPath)}`);
  console.log(`Bridge report: ${toStatusRelative(reportPath)}`);
  return true;
}

function watchBridge(config) {
  let timer = 0;
  let running = false;
  const rebuild = () => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      if (running) return;
      running = true;
      try {
        bridgeOnce(config);
      } finally {
        running = false;
      }
    }, 150);
  };

  fs.watchFile(config.inputPath, { interval: 1000 }, rebuild);
  console.log(`Watching monitor input: ${toStatusRelative(config.inputPath)}`);
  console.log(`Publishing feed to: ${toStatusRelative(config.publicFeedPath)}`);
}

const options = parseArgs(process.argv.slice(2));
if (options.help) {
  usage();
  process.exit(0);
}

const inputPath = statusPath(
  options.positionals[0] || process.env.STATUS_MONITOR_FILE,
  "status-monitor-results.example.json",
);
const publicFeedPath = statusPath(
  options.positionals[1] || process.env.STATUS_PUBLIC_FEED_FILE,
  "generated/status-feed.live.json",
);
const pipelineDir = statusPath(
  process.env.STATUS_PIPELINE_DIR,
  "generated/bridge",
);
const reportPath = resolve(pipelineDir, "status-feed.bridge-report.json");

rmSync(resolve(pipelineDir, "status-feed.generated.pending.json"), { force: true });

const ok = bridgeOnce({ inputPath, publicFeedPath, pipelineDir, reportPath });
if (options.watch) {
  watchBridge({ inputPath, publicFeedPath, pipelineDir, reportPath });
} else if (!ok) {
  process.exit(1);
}
