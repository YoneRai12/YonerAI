#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const statusRoot = path.resolve(scriptDir, "..");
const allowedStates = new Set([
  "ok",
  "healthy",
  "up",
  "online",
  "operational",
  "warn",
  "warning",
  "slow",
  "degraded",
  "maintenance",
  "not_started",
  "preparing",
  "alpha_only",
  "alpha",
  "partial_outage",
  "partial",
  "down",
  "outage",
  "error",
  "critical",
  "major_outage"
]);
const sensitiveKeyPattern = /(^|[_-])(token|secret|password|authorization|api[_-]?key|credential|cookie)([_-]|$)/i;

function usage() {
  console.log(`Usage:
  node status.yonerai.com/tools/validate-status-yonerai-health.mjs [health-summary.json]
  node tools/validate-status-yonerai-health.mjs [health-summary.json]

Default input:
  status-yonerai-health.example.json
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

function isLocalized(value) {
  if (value == null) return true;
  if (typeof value === "string") return true;
  if (!isObject(value)) return false;
  return Object.values(value).every((item) => typeof item === "string" || (Array.isArray(item) && item.every((line) => typeof line === "string")));
}

function scanKeys(value, label, errors) {
  if (Array.isArray(value)) {
    value.forEach((item, index) => scanKeys(item, `${label}[${index}]`, errors));
    return;
  }
  if (!isObject(value)) return;
  for (const [key, item] of Object.entries(value)) {
    if (sensitiveKeyPattern.test(key)) errors.push(`${label}.${key}: sensitive key is not allowed in health summary`);
    scanKeys(item, `${label}.${key}`, errors);
  }
}

function stateOf(record) {
  return String(record.state || record.status || record.health || "").trim().toLowerCase();
}

function validateRecord(record, label, errors) {
  if (!isObject(record)) {
    errors.push(`${label} must be an object`);
    return;
  }
  const componentId = record.component_id || record.componentId || record.component || record.id;
  if (!componentId) errors.push(`${label}.component_id is required`);
  const state = stateOf(record);
  if (!state) errors.push(`${label}.state is required`);
  else if (!allowedStates.has(state)) errors.push(`${label}.state has unsupported value: ${state}`);
  if (!isLocalized(record.message)) errors.push(`${label}.message must be a localized string`);
  if (record.latency_ms != null && !Number.isFinite(Number(record.latency_ms))) errors.push(`${label}.latency_ms must be numeric`);
  if (record.status_code != null && !Number.isFinite(Number(record.status_code))) errors.push(`${label}.status_code must be numeric`);
}

function validate(input) {
  const errors = [];
  if (!isObject(input)) return ["input root must be an object"];
  if (input.schema_version !== "yonerai.status.yonerai-health.v1") {
    errors.push("schema_version must be yonerai.status.yonerai-health.v1");
  }
  if (Array.isArray(input.components)) {
    input.components.forEach((record, index) => validateRecord(record, `components[${index}]`, errors));
  } else if (isObject(input.components)) {
    Object.entries(input.components).forEach(([key, record]) => validateRecord({ id: key, ...record }, `components.${key}`, errors));
  } else if (input.components != null) {
    errors.push("components must be an array or object");
  }
  if (isObject(input.statuses)) {
    Object.entries(input.statuses).forEach(([key, value]) => {
      if (isObject(value)) validateRecord({ id: key, ...value }, `statuses.${key}`, errors);
      else if (!allowedStates.has(String(value).toLowerCase())) errors.push(`statuses.${key} has unsupported state: ${value}`);
    });
  }
  if (!input.components && !input.statuses) errors.push("components or statuses is required");
  if (input.incidents != null && !Array.isArray(input.incidents)) errors.push("incidents must be an array when present");
  scanKeys(input, "$", errors);
  return errors;
}

const arg = process.argv[2];
if (arg === "--help" || arg === "-h") {
  usage();
  process.exit(0);
}

const file = resolveInput(arg, "status-yonerai-health.example.json");
try {
  const errors = validate(JSON.parse(fs.readFileSync(file, "utf8")));
  if (errors.length) {
    console.error(`Status YonerAI health validation failed: ${file}`);
    errors.forEach((error) => console.error(`- ${error}`));
    process.exit(1);
  }
  console.log(`Status YonerAI health validated: ${file}`);
} catch (error) {
  console.error(`Failed to validate Status YonerAI health: ${file}`);
  console.error(error.message);
  process.exit(1);
}
