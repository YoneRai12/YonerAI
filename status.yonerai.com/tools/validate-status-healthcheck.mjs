#!/usr/bin/env node

/*
 * Lightweight runtime validator for yonerai.status.healthcheck.v1.
 *
 * The full contract is documented in status-healthcheck.schema.json. This
 * script intentionally has no external dependencies so bridges and schedulers
 * can reject malformed inputs before generating a public feed.
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const statusRoot = path.resolve(scriptDir, "..");

function usage() {
  console.log(`Usage:
  node status.yonerai.com/tools/validate-status-healthcheck.mjs [healthcheck-input.json]
  node tools/validate-status-healthcheck.mjs [healthcheck-input.json]

Default input:
  status-healthcheck-input.example.json
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

function isStatusPrefixed(value) {
  return value.replaceAll("\\", "/").startsWith("status.yonerai.com/");
}

function resolveInput(value, fallback) {
  const chosen = value || fallback;
  if (path.isAbsolute(chosen)) return chosen;
  const cwdPath = path.resolve(process.cwd(), chosen);
  const statusPath = path.resolve(statusRoot, chosen);
  if (fs.existsSync(cwdPath)) return cwdPath;
  if (fs.existsSync(statusPath)) return statusPath;
  return isStatusPrefixed(chosen) ? cwdPath : statusPath;
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function isNonEmptyString(value) {
  return typeof value === "string" && value.trim().length > 0;
}

function isDate(value) {
  return /^\d{4}-\d{2}-\d{2}$/.test(String(value || ""));
}

function isLocalized(value) {
  if (isNonEmptyString(value)) return true;
  if (Array.isArray(value)) return value.every((item) => typeof item === "string");
  if (!isObject(value)) return false;
  const entries = Object.entries(value);
  if (!entries.length) return false;
  return entries.every(([key, item]) => (
    isNonEmptyString(key) &&
    (
      typeof item === "string" ||
      (Array.isArray(item) && item.every((line) => typeof line === "string"))
    )
  ));
}

const mojibakeNeedles = [
  0x00e3,
  0x7e5d,
  0x7e3a,
  0x8b41,
  0x9aeb,
  0x9036,
  0x7e67,
  0x8b5b,
  0x8373,
  0x90b5,
  0x96b4,
  0x90e2,
  0xfffd,
].map((code) => String.fromCharCode(code));

function containsMojibakeText(value) {
  return mojibakeNeedles.some((needle) => value.includes(needle));
}

function hasMojibake(value) {
  return typeof value === "string" && containsMojibakeText(value);
}

function scanText(value, pathLabel, errors) {
  if (typeof value === "string") {
    if (hasMojibake(value)) errors.push(`${pathLabel}: possible mojibake text`);
    return;
  }
  if (Array.isArray(value)) {
    value.forEach((item, index) => scanText(item, `${pathLabel}[${index}]`, errors));
    return;
  }
  if (isObject(value)) {
    for (const [key, item] of Object.entries(value)) {
      scanText(item, `${pathLabel}.${key}`, errors);
    }
  }
}

function validateLocalized(value, pathLabel, errors, required = false) {
  if (value == null) {
    if (required) errors.push(`${pathLabel}: required`);
    return;
  }
  if (!isLocalized(value)) errors.push(`${pathLabel}: expected localized string, string array, or locale object`);
}

function validateStates(states, errors) {
  if (states == null) return;
  if (!isObject(states)) {
    errors.push("states: expected object");
    return;
  }
  for (const [stateId, state] of Object.entries(states)) {
    if (!isNonEmptyString(stateId)) errors.push("states: state id must be non-empty");
    if (!isObject(state)) {
      errors.push(`states.${stateId}: expected object`);
      continue;
    }
    if (state.color != null && !/^#[0-9a-fA-F]{6}$/.test(String(state.color))) {
      errors.push(`states.${stateId}.color: expected #RRGGBB`);
    }
    validateLocalized(state.label, `states.${stateId}.label`, errors);
    if (state.severity != null && !Number.isFinite(Number(state.severity))) {
      errors.push(`states.${stateId}.severity: expected number`);
    }
  }
}

function validateCheck(check, pathLabel, errors) {
  if (!isObject(check)) {
    errors.push(`${pathLabel}: expected object`);
    return;
  }
  const type = check.type || "static";
  if (!["static", "manual", "http", "aws_metric"].includes(type)) {
    errors.push(`${pathLabel}.type: unsupported check type ${type}`);
    return;
  }
  if (type === "http") {
    if (!isNonEmptyString(check.url)) errors.push(`${pathLabel}.url: required for http check`);
    if (check.timeout_ms != null && !Number.isFinite(Number(check.timeout_ms))) errors.push(`${pathLabel}.timeout_ms: expected number`);
    if (check.degraded_ms != null && !Number.isFinite(Number(check.degraded_ms))) errors.push(`${pathLabel}.degraded_ms: expected number`);
    if (check.headers != null && !isObject(check.headers)) errors.push(`${pathLabel}.headers: expected object`);
  }
  if (type === "aws_metric") {
    if (!isNonEmptyString(check.namespace)) errors.push(`${pathLabel}.namespace: required for aws_metric check`);
    if (!isNonEmptyString(check.metric_name)) errors.push(`${pathLabel}.metric_name: required for aws_metric check`);
    if (check.value != null && !Number.isFinite(Number(check.value))) errors.push(`${pathLabel}.value: expected number`);
  }
  if (check.state != null && !isNonEmptyString(check.state)) errors.push(`${pathLabel}.state: expected non-empty string`);
  validateLocalized(check.message, `${pathLabel}.message`, errors);
  validateLocalized(check.message_on_error, `${pathLabel}.message_on_error`, errors);
}

function validateComponent(component, pathLabel, errors) {
  if (!isObject(component)) {
    errors.push(`${pathLabel}: expected object`);
    return;
  }
  if (!isNonEmptyString(component.id)) errors.push(`${pathLabel}.id: required`);
  validateLocalized(component.name, `${pathLabel}.name`, errors, true);
  if (!isNonEmptyString(component.default_state)) errors.push(`${pathLabel}.default_state: required`);
  validateLocalized(component.fact, `${pathLabel}.fact`, errors);
  validateLocalized(component.monitoring, `${pathLabel}.monitoring`, errors);
  validateLocalized(component.claim, `${pathLabel}.claim`, errors);
  validateLocalized(component.default_message, `${pathLabel}.default_message`, errors);
  if (component.checks != null) {
    if (!Array.isArray(component.checks)) {
      errors.push(`${pathLabel}.checks: expected array`);
    } else {
      component.checks.forEach((check, index) => validateCheck(check, `${pathLabel}.checks[${index}]`, errors));
    }
  }
}

function validateCategory(category, pathLabel, errors) {
  if (!isObject(category)) {
    errors.push(`${pathLabel}: expected object`);
    return;
  }
  if (!isNonEmptyString(category.id)) errors.push(`${pathLabel}.id: required`);
  validateLocalized(category.name, `${pathLabel}.name`, errors, true);
  validateLocalized(category.description, `${pathLabel}.description`, errors);
  const components = category.components || category.children;
  if (!Array.isArray(components) || components.length === 0) {
    errors.push(`${pathLabel}.components: expected non-empty array`);
    return;
  }
  components.forEach((component, index) => validateComponent(component, `${pathLabel}.components[${index}]`, errors));
}

function validate(input) {
  const errors = [];
  if (!isObject(input)) {
    return ["input: expected object"];
  }
  if (input.schema_version !== "yonerai.status.healthcheck.v1") {
    errors.push(`schema_version: expected yonerai.status.healthcheck.v1`);
  }
  if (!isObject(input.range)) {
    errors.push("range: expected object");
  } else {
    if (!isDate(input.range.start)) errors.push("range.start: expected YYYY-MM-DD");
    if (!Number.isInteger(Number(input.range.days)) || Number(input.range.days) < 1 || Number(input.range.days) > 120) {
      errors.push("range.days: expected integer from 1 to 120");
    }
  }
  if (input.result_date != null && !isDate(input.result_date)) errors.push("result_date: expected YYYY-MM-DD");
  if (input.locale_default != null && !["ja", "en"].includes(input.locale_default)) errors.push("locale_default: expected ja or en");
  validateStates(input.states, errors);
  validateLocalized(input.contract_note, "contract_note", errors);
  if (!Array.isArray(input.categories) || input.categories.length === 0) {
    errors.push("categories: expected non-empty array");
  } else {
    input.categories.forEach((category, index) => validateCategory(category, `categories[${index}]`, errors));
  }
  scanText(input, "input", errors);
  return errors;
}

const options = parseArgs(process.argv.slice(2));
if (options.help) {
  usage();
  process.exit(0);
}

const inputPath = resolveInput(options.positionals[0], "status-healthcheck-input.example.json");

try {
  const errors = validate(readJson(inputPath));
  if (errors.length) {
    console.error(`Status healthcheck input validation failed: ${inputPath}`);
    for (const error of errors) console.error(`- ${error}`);
    process.exit(1);
  }
  console.log(`Status healthcheck input validated: ${inputPath}`);
} catch (error) {
  console.error(`Failed to validate status healthcheck input: ${inputPath}`);
  console.error(error.message);
  process.exit(1);
}
