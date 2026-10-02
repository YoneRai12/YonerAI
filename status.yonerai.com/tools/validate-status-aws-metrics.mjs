#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const statusRoot = path.resolve(scriptDir, "..");
const sensitiveKeyPattern = /(^|[_-])(token|secret|password|authorization|api[_-]?key|credential|cookie)([_-]|$)/i;

function usage() {
  console.log(`Usage:
  node status.yonerai.com/tools/validate-status-aws-metrics.mjs [metrics.json]
  node tools/validate-status-aws-metrics.mjs [metrics.json]

Default input:
  status-aws-metrics.example.json
`);
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

function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function scanKeys(value, label, errors) {
  if (Array.isArray(value)) {
    value.forEach((item, index) => scanKeys(item, `${label}[${index}]`, errors));
    return;
  }
  if (!isObject(value)) return;
  for (const [key, item] of Object.entries(value)) {
    if (sensitiveKeyPattern.test(key)) errors.push(`${label}.${key}: sensitive key is not allowed in metrics summary`);
    scanKeys(item, `${label}.${key}`, errors);
  }
}

function validate(input) {
  const errors = [];
  if (!isObject(input)) return ["input root must be an object"];
  if (input.schema_version != null && input.schema_version !== "yonerai.status.aws-metrics.v1") {
    errors.push(`schema_version must be yonerai.status.aws-metrics.v1 when present`);
  }
  const hasMetrics = input.metrics != null;
  const hasMetricDataResults = Array.isArray(input.MetricDataResults);
  const hasDatapoints = Array.isArray(input.Datapoints);
  if (!hasMetrics && !hasMetricDataResults && !hasDatapoints) {
    errors.push("one of metrics, MetricDataResults, or Datapoints is required");
  }
  if (Array.isArray(input.metrics)) {
    input.metrics.forEach((metric, index) => {
      if (!isObject(metric)) {
        errors.push(`metrics[${index}] must be an object`);
        return;
      }
      if (metric.value == null || !Number.isFinite(Number(metric.value))) errors.push(`metrics[${index}].value must be numeric`);
      if (!metric.label && !metric.metric_name && !metric.MetricName) errors.push(`metrics[${index}] should include label or metric_name`);
    });
  } else if (isObject(input.metrics)) {
    for (const [key, value] of Object.entries(input.metrics)) {
      if (!Number.isFinite(Number(value))) errors.push(`metrics.${key} must be numeric`);
    }
  } else if (input.metrics != null) {
    errors.push("metrics must be an array or object");
  }
  if (Array.isArray(input.MetricDataResults)) {
    input.MetricDataResults.forEach((result, index) => {
      if (!isObject(result)) errors.push(`MetricDataResults[${index}] must be an object`);
      if (result?.Values != null && !Array.isArray(result.Values)) errors.push(`MetricDataResults[${index}].Values must be an array`);
    });
  }
  if (Array.isArray(input.Datapoints)) {
    input.Datapoints.forEach((datapoint, index) => {
      if (!isObject(datapoint)) errors.push(`Datapoints[${index}] must be an object`);
    });
  }
  scanKeys(input, "$", errors);
  return errors;
}

const arg = process.argv[2];
if (arg === "--help" || arg === "-h") {
  usage();
  process.exit(0);
}

const file = resolveInput(arg, "status-aws-metrics.example.json");
try {
  const errors = validate(JSON.parse(fs.readFileSync(file, "utf8")));
  if (errors.length) {
    console.error(`Status AWS metrics validation failed: ${file}`);
    errors.forEach((error) => console.error(`- ${error}`));
    process.exit(1);
  }
  console.log(`Status AWS metrics validated: ${file}`);
} catch (error) {
  console.error(`Failed to validate Status AWS metrics: ${file}`);
  console.error(error.message);
  process.exit(1);
}
