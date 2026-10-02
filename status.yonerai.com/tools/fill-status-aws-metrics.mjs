#!/usr/bin/env node

/*
 * Fill aws_metric check values in yonerai.status.healthcheck.v1 input.
 *
 * This script does not call AWS and does not read credentials. It only maps a
 * metrics JSON file produced by AWS CLI, CloudWatch collectors, or internal
 * schedulers into the public-safe healthcheck input shape.
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const statusRoot = path.resolve(scriptDir, "..");

function usage() {
  console.log(`Usage:
  node status.yonerai.com/tools/fill-status-aws-metrics.mjs [healthcheck-input.json] [metrics.json] [healthcheck-output.json]
  node tools/fill-status-aws-metrics.mjs [healthcheck-input.json] [metrics.json] [healthcheck-output.json]

Default input:
  status-healthcheck-input.aws-cloudwatch.example.json

Default metrics:
  status-aws-metrics.example.json

Default output:
  generated/status-healthcheck-input.aws-filled.json

Accepted metrics JSON shapes:
  { "schema_version": "yonerai.status.aws-metrics.v1", "metrics": [{ "label": "lambda-errors", "value": 0 }] }
  { "metrics": { "lambda-errors": 0, "AWS/Lambda:Errors:Sum": 0 } }
  { "MetricDataResults": [{ "Id": "lambda_errors", "Label": "lambda-errors", "Values": [0], "Timestamps": ["..."] }] }
  { "Datapoints": [{ "Timestamp": "...", "Sum": 0 }] }
`);
}

function parseArgs(argv) {
  const options = { positionals: [] };
  for (const arg of argv) {
    if (arg === "--help" || arg === "-h") options.help = true;
    else options.positionals.push(arg);
  }
  return options;
}

function resolveInput(value, fallback) {
  const chosen = value || fallback;
  if (path.isAbsolute(chosen)) return chosen;
  const cwdPath = path.resolve(process.cwd(), chosen);
  const statusPath = path.resolve(statusRoot, chosen);
  if (fs.existsSync(cwdPath)) return cwdPath;
  if (fs.existsSync(statusPath)) return statusPath;
  return chosen.replaceAll("\\", "/").startsWith("status.yonerai.com/") ? cwdPath : statusPath;
}

function resolveOutput(value, fallback) {
  const chosen = value || fallback;
  if (path.isAbsolute(chosen)) return chosen;
  return chosen.replaceAll("\\", "/").startsWith("status.yonerai.com/")
    ? path.resolve(process.cwd(), chosen)
    : path.resolve(statusRoot, chosen);
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

function writeJson(file, value) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

function toStatusRelative(file) {
  return path.relative(statusRoot, file).replaceAll("\\", "/");
}

function runValidator(script, file, label) {
  const result = spawnSync(process.execPath, [script, toStatusRelative(file)], {
    cwd: statusRoot,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  });
  if (result.status !== 0) {
    throw new Error([
      `${label} validation failed`,
      (result.stdout || "").trim(),
      (result.stderr || "").trim(),
    ].filter(Boolean).join("\n"));
  }
}

function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function numberOrNull(value) {
  const next = Number(value);
  return Number.isFinite(next) ? next : null;
}

function normalizeMetricKey(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function latestValueFromTimestamped(values = [], timestamps = []) {
  if (!Array.isArray(values) || values.length === 0) return null;
  if (!Array.isArray(timestamps) || timestamps.length !== values.length) {
    return numberOrNull(values[0]);
  }
  let latestIndex = 0;
  let latestTime = Date.parse(timestamps[0]);
  timestamps.forEach((timestamp, index) => {
    const current = Date.parse(timestamp);
    if (Number.isFinite(current) && (!Number.isFinite(latestTime) || current > latestTime)) {
      latestTime = current;
      latestIndex = index;
    }
  });
  return numberOrNull(values[latestIndex]);
}

function addMetric(index, keys, value, meta = {}) {
  const numeric = numberOrNull(value);
  if (numeric == null) return;
  keys
    .filter(Boolean)
    .map(normalizeMetricKey)
    .filter(Boolean)
    .forEach((key) => {
      index.set(key, {
        value: numeric,
        meta,
      });
    });
}

function metricKeysForObject(metric) {
  const namespace = metric.namespace || metric.Namespace;
  const metricName = metric.metric_name || metric.metricName || metric.MetricName;
  const statistic = metric.statistic || metric.Statistic || metric.stat || metric.Stat;
  const label = metric.label || metric.Label || metric.id || metric.Id;
  return [
    label,
    metric.id,
    metric.Id,
    namespace && metricName && statistic ? `${namespace}:${metricName}:${statistic}` : null,
    namespace && metricName ? `${namespace}:${metricName}` : null,
    namespace && metricName && statistic ? `${namespace}/${metricName}/${statistic}` : null,
  ];
}

function buildMetricIndex(metricsInput) {
  const index = new Map();

  if (Array.isArray(metricsInput.metrics)) {
    metricsInput.metrics.forEach((metric) => {
      if (!isObject(metric)) return;
      addMetric(index, metricKeysForObject(metric), metric.value ?? metric.Value, {
        source: "metrics-array",
      });
    });
  } else if (isObject(metricsInput.metrics)) {
    Object.entries(metricsInput.metrics).forEach(([key, value]) => {
      addMetric(index, [key], value, { source: "metrics-map" });
    });
  }

  if (Array.isArray(metricsInput.MetricDataResults)) {
    metricsInput.MetricDataResults.forEach((result) => {
      if (!isObject(result)) return;
      const value = latestValueFromTimestamped(result.Values, result.Timestamps);
      addMetric(index, [result.Label, result.Id, result.Id?.replaceAll("_", "-")], value, {
        source: "aws-metric-data-results",
        status: result.StatusCode || null,
      });
    });
  }

  if (Array.isArray(metricsInput.Datapoints)) {
    const sorted = [...metricsInput.Datapoints].sort((left, right) => Date.parse(right.Timestamp) - Date.parse(left.Timestamp));
    const latest = sorted.find(isObject);
    if (latest) {
      for (const statistic of ["Sum", "Average", "Maximum", "Minimum", "SampleCount"]) {
        if (latest[statistic] != null) {
          addMetric(index, [statistic], latest[statistic], {
            source: "aws-datapoints",
            timestamp: latest.Timestamp || null,
          });
        }
      }
    }
  }

  return index;
}

function checkKeys(category, component, check) {
  const namespace = check.namespace;
  const metricName = check.metric_name;
  const statistic = check.statistic;
  return [
    check.label,
    `${category.id}/${component.id}/${check.label || ""}`,
    `${namespace}:${metricName}:${statistic}`,
    `${namespace}:${metricName}`,
    `${namespace}/${metricName}/${statistic}`,
    metricName,
  ];
}

function fillHealthcheck(input, metricIndex) {
  if (input.schema_version !== "yonerai.status.healthcheck.v1") {
    throw new Error(`unsupported healthcheck schema: ${input.schema_version}`);
  }

  let filled = 0;
  let missing = 0;
  const output = structuredClone(input);
  for (const category of output.categories || []) {
    for (const component of category.components || category.children || []) {
      for (const check of component.checks || []) {
        if (check?.type !== "aws_metric") continue;
        const match = checkKeys(category, component, check)
          .map(normalizeMetricKey)
          .map((key) => metricIndex.get(key))
          .find(Boolean);
        if (!match) {
          missing += 1;
          continue;
        }
        check.value = match.value;
        check.source = check.source || "aws-metric-fill";
        filled += 1;
      }
    }
  }
  output.generated_at = new Date().toISOString();
  output.aws_metric_fill = {
    generated_at: output.generated_at,
    filled,
    missing,
  };
  return output;
}

const options = parseArgs(process.argv.slice(2));
if (options.help) {
  usage();
  process.exit(0);
}

const healthcheckPath = resolveInput(options.positionals[0], "status-healthcheck-input.aws-cloudwatch.example.json");
const metricsPath = resolveInput(options.positionals[1], "status-aws-metrics.example.json");
const outputPath = resolveOutput(options.positionals[2], "generated/status-healthcheck-input.aws-filled.json");

try {
  runValidator("tools/validate-status-healthcheck.mjs", healthcheckPath, "healthcheck input");
  runValidator("tools/validate-status-aws-metrics.mjs", metricsPath, "AWS metrics input");
  const metricIndex = buildMetricIndex(readJson(metricsPath));
  const output = fillHealthcheck(readJson(healthcheckPath), metricIndex);
  writeJson(outputPath, output);
  console.log(`Filled AWS metric healthcheck input: ${outputPath}`);
  console.log(`filled=${output.aws_metric_fill.filled} missing=${output.aws_metric_fill.missing}`);
  if (output.aws_metric_fill.missing > 0) process.exitCode = 2;
} catch (error) {
  console.error("Failed to fill AWS metric healthcheck input.");
  console.error(error.message);
  process.exit(1);
}
