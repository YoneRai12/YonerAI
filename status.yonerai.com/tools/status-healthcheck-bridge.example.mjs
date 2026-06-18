#!/usr/bin/env node

/*
 * Example healthcheck bridge for YonerAI Status.
 *
 * This is the direct integration path for YonerAI API, AWS metric inputs, and
 * static/manual checks:
 *
 *   healthcheck input -> monitor result -> source -> feed -> atomic publish
 *
 * The browser runtime still consumes only yonerai.status.feed.v1. This script
 * does not touch DOM state, selected bars, tooltip state, or animation state.
 */

import fs from "node:fs";
import { dirname, isAbsolute, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const statusRoot = resolve(scriptDir, "..");

function usage() {
  console.log(`Usage:
  node status.yonerai.com/tools/status-healthcheck-bridge.example.mjs [healthcheck-input.json] [public-feed.json] [--watch]
  node tools/status-healthcheck-bridge.example.mjs [healthcheck-input.json] [public-feed.json] [--watch]

Environment:
  STATUS_HEALTHCHECK_FILE   healthcheck input JSON path
  STATUS_PUBLIC_FEED_FILE   output feed JSON path
  STATUS_PIPELINE_DIR       temporary pipeline output dir

Default healthcheck input:
  status-healthcheck-input.example.json

Default public feed output:
  generated/status-feed.live.json

This wrapper is intended for scheduler/CI/local daemon use. Failed generations
do not promote a broken feed.
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
  if (fs.existsSync(cwdPath)) return cwdPath;
  if (chosen.replaceAll("\\", "/").startsWith("status.yonerai.com/")) return cwdPath;
  return resolve(statusRoot, chosen);
}

function runNode(args, env = {}) {
  return spawnSync(process.execPath, args, {
    cwd: statusRoot,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
    env: {
      ...process.env,
      ...env,
    },
  });
}

function runOnce(config) {
  fs.mkdirSync(config.pipelineDir, { recursive: true });
  const monitorPath = resolve(config.pipelineDir, "status-monitor-results.generated.json");

  const validation = runNode([
    "tools/validate-status-healthcheck.mjs",
    config.healthcheckPath,
  ]);
  if (validation.status !== 0) {
    console.error("Status healthcheck input validation failed. Public feed was not changed.");
    if (validation.stdout.trim()) console.error(validation.stdout.trim());
    if (validation.stderr.trim()) console.error(validation.stderr.trim());
    return false;
  }

  const collect = runNode([
    "tools/collect-status-healthchecks.mjs",
    config.healthcheckPath,
    monitorPath,
  ]);
  if (collect.status !== 0) {
    console.error("Status healthcheck collection failed. Public feed was not changed.");
    if (collect.stdout.trim()) console.error(collect.stdout.trim());
    if (collect.stderr.trim()) console.error(collect.stderr.trim());
    return false;
  }

  const bridge = runNode([
    "tools/status-feed-bridge.example.mjs",
    monitorPath,
    config.publicFeedPath,
  ], {
    STATUS_PIPELINE_DIR: resolve(config.pipelineDir, "feed"),
  });
  if (bridge.status !== 0) {
    console.error("Status feed bridge failed. Public feed was not changed.");
    if (bridge.stdout.trim()) console.error(bridge.stdout.trim());
    if (bridge.stderr.trim()) console.error(bridge.stderr.trim());
    return false;
  }

  if (validation.stdout.trim()) console.log(validation.stdout.trim());
  if (collect.stdout.trim()) console.log(collect.stdout.trim());
  if (bridge.stdout.trim()) console.log(bridge.stdout.trim());
  return true;
}

function watch(config) {
  let timer = 0;
  let running = false;
  const rebuild = () => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      if (running) return;
      running = true;
      try {
        runOnce(config);
      } finally {
        running = false;
      }
    }, 150);
  };

  fs.watchFile(config.healthcheckPath, { interval: 1000 }, rebuild);
  console.log(`Watching healthcheck input: ${config.healthcheckPath}`);
  console.log(`Publishing feed to: ${config.publicFeedPath}`);
}

const options = parseArgs(process.argv.slice(2));
if (options.help) {
  usage();
  process.exit(0);
}

const healthcheckPath = statusPath(
  options.positionals[0] || process.env.STATUS_HEALTHCHECK_FILE,
  "status-healthcheck-input.example.json",
);
const publicFeedPath = statusPath(
  options.positionals[1] || process.env.STATUS_PUBLIC_FEED_FILE,
  "generated/status-feed.live.json",
);
const pipelineDir = statusPath(
  process.env.STATUS_PIPELINE_DIR,
  "generated/healthcheck-bridge",
);

const ok = runOnce({ healthcheckPath, publicFeedPath, pipelineDir });
if (options.watch) {
  watch({ healthcheckPath, publicFeedPath, pipelineDir });
} else if (!ok) {
  process.exit(1);
}
