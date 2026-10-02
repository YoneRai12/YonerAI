#!/usr/bin/env node

/*
 * YonerAI Status pre-publish contract suite.
 *
 * This is a coordinator for the non-browser checks that protect the reusable
 * status page contract:
 *
 * - integration manifest
 * - runtime API contract
 * - UI/UX regression contract
 * - healthcheck input examples
 * - monitor/source/feed generation paths
 * - final public feed examples
 *
 * It intentionally does not launch a browser and does not replace visual QA.
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const statusRoot = path.resolve(scriptDir, "..");

function usage() {
  console.log(`Usage:
  node status.yonerai.com/tools/validate-status-contract-suite.mjs [--quick]
  node tools/validate-status-contract-suite.mjs [--quick]

Options:
  --quick   Skip alternate example files and only check the main happy path.

Outputs:
  generated/status-contract-suite-report.json

This suite does not start localhost or a browser.
`);
}

function parseArgs(argv) {
  const options = { quick: false };
  for (const arg of argv) {
    if (arg === "--help" || arg === "-h") options.help = true;
    else if (arg === "--quick") options.quick = true;
    else throw new Error(`unknown argument: ${arg}`);
  }
  return options;
}

function statusPath(relativePath) {
  return path.resolve(statusRoot, relativePath);
}

function exists(relativePath) {
  return fs.existsSync(statusPath(relativePath));
}

function runStep(name, args, options = {}) {
  const startedAt = new Date().toISOString();
  const result = spawnSync(process.execPath, args, {
    cwd: statusRoot,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  });
  return {
    name,
    required: options.required !== false,
    command: `node ${args.join(" ")}`,
    status: result.status,
    signal: result.signal,
    ok: result.status === 0,
    started_at: startedAt,
    finished_at: new Date().toISOString(),
    stdout: (result.stdout || "").trim(),
    stderr: (result.stderr || "").trim(),
    error: result.error ? String(result.error.message || result.error) : null,
  };
}

function skippedStep(name, reason) {
  return {
    name,
    required: false,
    command: "skip",
    status: 0,
    signal: null,
    ok: true,
    skipped: true,
    reason,
    started_at: new Date().toISOString(),
    finished_at: new Date().toISOString(),
    stdout: "",
    stderr: "",
    error: null,
  };
}

function writeReport(report) {
  const reportPath = statusPath("generated/status-contract-suite-report.json");
  fs.mkdirSync(path.dirname(reportPath), { recursive: true });
  fs.writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`, "utf8");
  return reportPath;
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

const steps = [];

steps.push(runStep("runtime-api-contract", ["tools/validate-status-runtime-contract.mjs"]));
steps.push(runStep("uiux-regression-contract", ["tools/validate-status-uiux-regression.mjs"]));
steps.push(runStep("integration-manifest", ["tools/validate-status-integration-manifest.mjs"]));
steps.push(runStep("status-snapshot-example", [
  "tools/validate-status-snapshot.mjs",
  "status-snapshot.example.json",
]));
steps.push(runStep("aws-metrics-example", [
  "tools/validate-status-aws-metrics.mjs",
  "status-aws-metrics.example.json",
]));
steps.push(runStep("yonerai-health-example", [
  "tools/validate-status-yonerai-health.mjs",
  "status-yonerai-health.example.json",
]));
steps.push(runStep("healthcheck-main-example", [
  "tools/validate-status-healthcheck.mjs",
  "status-healthcheck-input.example.json",
]));

if (!options.quick) {
  for (const file of [
    "status-healthcheck-input.yonerai-api-http.example.json",
    "status-healthcheck-input.aws-cloudwatch.example.json",
  ]) {
    if (exists(file)) {
      steps.push(runStep(`healthcheck-example-${file}`, [
        "tools/validate-status-healthcheck.mjs",
        file,
      ]));
    } else {
      steps.push(skippedStep(`healthcheck-example-${file}`, `${file} not found`));
    }
  }

  if (exists("status-healthcheck-input.aws-cloudwatch.example.json") && exists("status-aws-metrics.example.json")) {
    steps.push(runStep("fill-aws-metrics-example", [
      "tools/fill-status-aws-metrics.mjs",
      "status-healthcheck-input.aws-cloudwatch.example.json",
      "status-aws-metrics.example.json",
      "generated/contract-suite/status-healthcheck-input.aws-filled.json",
    ]));
    steps.push(runStep("pipeline-from-filled-aws-metrics", [
      "tools/build-status-pipeline.mjs",
      "generated/contract-suite/status-healthcheck-input.aws-filled.json",
      "generated/contract-suite/from-filled-aws",
    ]));
    steps.push(runStep("public-feed-safety-from-filled-aws", [
      "tools/validate-status-public-feed-safety.mjs",
      "generated/contract-suite/from-filled-aws/status-feed.generated.json",
    ]));
  } else {
    steps.push(skippedStep("fill-aws-metrics-example", "AWS healthcheck or metrics example not found"));
  }

  if (exists("status-healthcheck-input.yonerai-api-http.example.json") && exists("status-yonerai-health.example.json")) {
    steps.push(runStep("fill-yonerai-health-example", [
      "tools/fill-status-yonerai-health.mjs",
      "status-healthcheck-input.yonerai-api-http.example.json",
      "status-yonerai-health.example.json",
      "generated/contract-suite/status-healthcheck-input.yonerai-filled.json",
    ]));
    steps.push(runStep("pipeline-from-filled-yonerai-health", [
      "tools/build-status-pipeline.mjs",
      "generated/contract-suite/status-healthcheck-input.yonerai-filled.json",
      "generated/contract-suite/from-filled-yonerai",
    ]));
    steps.push(runStep("public-feed-safety-from-filled-yonerai", [
      "tools/validate-status-public-feed-safety.mjs",
      "generated/contract-suite/from-filled-yonerai/status-feed.generated.json",
    ]));
  } else {
    steps.push(skippedStep("fill-yonerai-health-example", "YonerAI healthcheck or health summary example not found"));
  }
}

steps.push(runStep("pipeline-from-healthcheck", [
  "tools/build-status-pipeline.mjs",
  "status-healthcheck-input.example.json",
  "generated/contract-suite/from-healthcheck",
]));
steps.push(runStep("public-feed-safety-from-healthcheck", [
  "tools/validate-status-public-feed-safety.mjs",
  "generated/contract-suite/from-healthcheck/status-feed.generated.json",
]));
steps.push(runStep("promote-public-feed-from-healthcheck", [
  "tools/promote-status-public-feed.mjs",
  "generated/contract-suite/from-healthcheck/status-feed.generated.json",
  "generated/contract-suite/promoted/status-feed.json",
]));
steps.push(runStep("sync-public-feed-from-healthcheck", [
  "tools/sync-status-public-feed.mjs",
  "--input",
  "status-healthcheck-input.example.json",
  "--public",
  "generated/contract-suite/synced/status-feed.json",
  "--workdir",
  "generated/contract-suite/sync",
]));
steps.push(runStep("build-public-package-from-synced-feed", [
  "tools/build-status-public-package.mjs",
  "--feed",
  "generated/contract-suite/synced/status-feed.json",
  "--out",
  "generated/contract-suite/public-package",
]));
steps.push(runStep("pipeline-from-status-snapshot", [
  "tools/build-status-pipeline.mjs",
  "status-snapshot.example.json",
  "generated/contract-suite/from-snapshot",
]));
steps.push(runStep("public-feed-safety-from-status-snapshot", [
  "tools/validate-status-public-feed-safety.mjs",
  "generated/contract-suite/from-snapshot/status-feed.generated.json",
]));
steps.push(runStep("sync-public-feed-from-status-snapshot", [
  "tools/sync-status-public-feed.mjs",
  "--input",
  "status-snapshot.example.json",
  "--public",
  "generated/contract-suite/synced-snapshot/status-feed.json",
  "--workdir",
  "generated/contract-suite/sync-snapshot",
]));

if (!options.quick) {
  for (const [name, input, output] of [
    ["pipeline-from-monitor", "status-monitor-results.example.json", "generated/contract-suite/from-monitor"],
    ["pipeline-from-source", "status-feed.source.example.json", "generated/contract-suite/from-source"],
  ]) {
    if (exists(input)) {
      steps.push(runStep(name, [
        "tools/build-status-pipeline.mjs",
        input,
        output,
      ]));
      steps.push(runStep(`${name}-public-feed-safety`, [
        "tools/validate-status-public-feed-safety.mjs",
        `${output}/status-feed.generated.json`,
      ]));
    } else {
      steps.push(skippedStep(name, `${input} not found`));
    }
  }

  for (const file of [
    "status-feed.example.json",
    "status-feed.scenarios.example.json",
  ]) {
    if (exists(file)) {
      steps.push(runStep(`feed-example-${file}`, [
        "tools/validate-status-feed.mjs",
        file,
      ]));
      steps.push(runStep(`feed-example-safety-${file}`, [
        "tools/validate-status-public-feed-safety.mjs",
        file,
      ]));
    } else {
      steps.push(skippedStep(`feed-example-${file}`, `${file} not found`));
    }
  }
}

const requiredFailed = steps.filter((step) => step.required && !step.ok);
const report = {
  schema_version: "yonerai.status.contract-suite.report.v1",
  generated_at: new Date().toISOString(),
  ok: requiredFailed.length === 0,
  quick: options.quick,
  status_root: statusRoot,
  steps,
};
const reportPath = writeReport(report);
const reportRelative = path.relative(statusRoot, reportPath).replaceAll("\\", "/");

if (!report.ok) {
  console.error(`Status contract suite failed. Report: ${reportRelative}`);
  for (const step of requiredFailed) {
    console.error(`- ${step.name}: ${step.stderr || step.error || "failed"}`);
  }
  process.exit(1);
}

console.log(`Status contract suite passed. Report: ${reportRelative}`);
