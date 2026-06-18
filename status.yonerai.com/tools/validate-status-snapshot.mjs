#!/usr/bin/env node

/*
 * Validate public-safe YonerAI status snapshot input before StatusWEB converts
 * it into yonerai.status.source.v1 / yonerai.status.feed.v1.
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const statusRoot = path.resolve(scriptDir, "..");

const healthStates = new Set([
  "operational",
  "degraded",
  "partial_outage",
  "major_outage",
  "maintenance",
  "offline",
  "unknown",
]);
const availabilityStates = new Set(["available", "limited", "unavailable"]);
const stages = new Set(["preview", "staging", "production", "disabled"]);
const incidentStatuses = new Set(["investigating", "identified", "monitoring", "resolved", "maintenance"]);
const componentIds = new Set([
  "api",
  "auth",
  "provider_gateway",
  "official_execution_worker",
  "run_queue",
  "realtime_sync",
  "web",
  "audit",
  "discord",
]);

const errors = [];
const warnings = [];
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

function hasMojibakeText(value) {
  return mojibakeNeedles.some((needle) => value.includes(needle));
}
const unsafeTextPatterns = [
  { pattern: /\uFFFD/, label: "replacement character" },
  { pattern: /\[object Object\]/, label: "[object Object]" },
  { pattern: /\bundefined\b/i, label: "undefined literal" },
  { pattern: /\bnull\b/i, label: "null literal" },
];
const sensitiveKeyPattern = /(^|[_-])(token|secret|password|passwd|authorization|auth_header|api[_-]?key|access[_-]?key|private[_-]?key|credential|session|cookie|account[_-]?id|worker[_-]?identity)([_-]|$)/i;
const sensitiveValuePatterns = [
  { name: "bearer-token", pattern: /\bBearer\s+[A-Za-z0-9._~+/-]+=*/i },
  { name: "aws-access-key", pattern: /\bAKIA[0-9A-Z]{16}\b/ },
  { name: "openai-key", pattern: /\bsk-[A-Za-z0-9_-]{20,}\b/ },
  { name: "jwt-like", pattern: /\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b/ },
  { name: "arn", pattern: /\barn:aws:[A-Za-z0-9:/_-]+\b/i },
  { name: "email", pattern: /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/i },
  { name: "local-path", pattern: /\b[A-Z]:\\[^\n\r"]+/i },
  { name: "localhost-url", pattern: /\bhttps?:\/\/(?:localhost|127\.0\.0\.1|0\.0\.0\.0)(?::\d+)?\b/i },
  { name: "private-ip-url", pattern: /\bhttps?:\/\/(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3})(?::\d+)?\b/i },
  { name: "local-domain", pattern: /\bhttps?:\/\/[^/\s"]+\.local(?:[:/]|$)/i },
  { name: "private-runtime-word", pattern: /\b(private runtime inventory|break-glass|raw production inventory|internal hostname|worker identity|conversation metadata|provider prompt|provider output|run contents)\b/i },
];

function usage() {
  console.log(`Usage:
  node status.yonerai.com/tools/validate-status-snapshot.mjs [snapshot.json]
  node tools/validate-status-snapshot.mjs [snapshot.json]

Default input:
  status-snapshot.example.json
`);
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

function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function fail(message) {
  errors.push(message);
}

function warn(message) {
  warnings.push(message);
}

function textSafety(value, label) {
  if (typeof value !== "string") return;
  if (hasMojibakeText(value)) {
    fail(`${label} appears to contain mojibake: ${value}`);
    return;
  }
  for (const item of unsafeTextPatterns) {
    if (item.pattern.test(value)) {
      fail(`${label} contains unsafe display text (${item.label}): ${value}`);
      return;
    }
  }
}

function scanPublicSafety(value, label) {
  if (Array.isArray(value)) {
    value.forEach((item, index) => scanPublicSafety(item, `${label}[${index}]`));
    return;
  }
  if (isObject(value)) {
    for (const [key, item] of Object.entries(value)) {
      const next = `${label}.${key}`;
      if (sensitiveKeyPattern.test(key)) warn(`${next} uses sensitive-looking metadata key ignored by StatusWEB: ${key}`);
      scanPublicSafety(item, next);
    }
    return;
  }
  if (typeof value !== "string") return;
  for (const rule of sensitiveValuePatterns) {
    if (rule.pattern.test(value)) fail(`${label} contains forbidden public value ${rule.name}: ${value}`);
  }
}

function id(value, label, seen) {
  if (typeof value !== "string" || !/^[A-Za-z0-9._:-]+$/.test(value)) {
    fail(`${label} must be a stable public id`);
    return;
  }
  if (seen?.has(value)) fail(`${label} is duplicated: ${value}`);
  seen?.add(value);
}

function localized(value, label) {
  if (typeof value === "string" && value.trim()) {
    textSafety(value, label);
    return;
  }
  if (Array.isArray(value)) {
    if (!value.length) fail(`${label} must not be an empty localized array`);
    value.forEach((item, index) => localized(item, `${label}[${index}]`));
    return;
  }
  if (isObject(value)) {
    const keys = Object.keys(value);
    if (!keys.length) fail(`${label} must not be an empty localized object`);
    const localeKeys = keys.filter((key) => /^[a-z]{2}(-[A-Z]{2})?$/.test(key) || key === "ja" || key === "en");
    if (!localeKeys.length) fail(`${label} localized object must include locale keys such as ja or en`);
    localeKeys.forEach((key) => localized(value[key], `${label}.${key}`));
    return;
  }
  fail(`${label} must be a non-empty string, localized object, or localized array`);
}

function enumValue(value, allowed, label) {
  if (typeof value !== "string" || !allowed.has(value)) {
    fail(`${label} has unsupported value: ${String(value)}`);
  }
}

function validateOverall(overall) {
  if (!isObject(overall)) {
    fail("overall must be an object");
    return;
  }
  enumValue(overall.health, healthStates, "overall.health");
  enumValue(overall.availability, availabilityStates, "overall.availability");
  enumValue(overall.stage, stages, "overall.stage");
  localized(overall.message, "overall.message");
}

function validateComponent(component, index, componentSeen, incidentRefs) {
  const label = `components[${index}]`;
  if (!isObject(component)) {
    fail(`${label} must be an object`);
    return;
  }
  enumValue(component.id, componentIds, `${label}.id`);
  if (component.id != null) {
    if (componentSeen.has(component.id)) fail(`${label}.id is duplicated: ${component.id}`);
    componentSeen.add(component.id);
  }
  enumValue(component.health, healthStates, `${label}.health`);
  enumValue(component.availability, availabilityStates, `${label}.availability`);
  enumValue(component.stage, stages, `${label}.stage`);
  localized(component.message, `${label}.message`);
  if (typeof component.updated_at !== "string" || !component.updated_at.trim()) fail(`${label}.updated_at must be a non-empty string`);
  if (typeof component.stale !== "boolean") fail(`${label}.stale must be boolean`);
  if (component.incident_ref !== null) {
    id(component.incident_ref, `${label}.incident_ref`, null);
    incidentRefs.add(component.incident_ref);
  }
}

function validateIncident(incident, index, incidentSeen, componentSeen) {
  const label = `incidents[${index}]`;
  if (!isObject(incident)) {
    fail(`${label} must be an object`);
    return;
  }
  id(incident.id, `${label}.id`, incidentSeen);
  enumValue(incident.status, incidentStatuses, `${label}.status`);
  enumValue(incident.impact, healthStates, `${label}.impact`);
  if (incident.started_at != null && typeof incident.started_at !== "string") fail(`${label}.started_at must be a string`);
  if (incident.resolved_at != null && typeof incident.resolved_at !== "string") fail(`${label}.resolved_at must be a string`);
  localized(incident.title, `${label}.title`);
  localized(incident.summary, `${label}.summary`);
  if (incident.component_ids != null) {
    if (!Array.isArray(incident.component_ids) || !incident.component_ids.length) {
      fail(`${label}.component_ids must be a non-empty array when present`);
    } else {
      incident.component_ids.forEach((componentId, componentIndex) => {
        enumValue(componentId, componentIds, `${label}.component_ids[${componentIndex}]`);
        if (!componentSeen.has(componentId)) warn(`${label}.component_ids[${componentIndex}] is not present in components: ${componentId}`);
      });
    }
  }
  if (!Array.isArray(incident.updates) || !incident.updates.length) {
    fail(`${label}.updates must be a non-empty array`);
    return;
  }
  incident.updates.forEach((update, updateIndex) => {
    if (!isObject(update)) {
      fail(`${label}.updates[${updateIndex}] must be an object`);
      return;
    }
    enumValue(update.status, incidentStatuses, `${label}.updates[${updateIndex}].status`);
    if (typeof update.at !== "string" || !update.at.trim()) fail(`${label}.updates[${updateIndex}].at must be a non-empty string`);
    if (update.label != null) localized(update.label, `${label}.updates[${updateIndex}].label`);
    localized(update.body, `${label}.updates[${updateIndex}].body`);
  });
}

const args = process.argv.slice(2);
if (args.includes("--help") || args.includes("-h")) {
  usage();
  process.exit(0);
}

const file = resolveInput(args[0], "status-snapshot.example.json");
let snapshot;
try {
  snapshot = JSON.parse(fs.readFileSync(file, "utf8"));
} catch (error) {
  console.error(`Failed to read status snapshot: ${file}`);
  console.error(error.message);
  process.exit(1);
}

if (!isObject(snapshot)) fail("snapshot root must be an object");
if (snapshot.schema_version !== "yonerai.status.v1") {
  fail(`schema_version must be yonerai.status.v1, got ${String(snapshot.schema_version)}`);
}
id(snapshot.snapshot_id, "snapshot_id", null);
if (typeof snapshot.generated_at !== "string" || !snapshot.generated_at.trim()) fail("generated_at must be a non-empty string");
if (!Number.isInteger(snapshot.stale_after_seconds) || snapshot.stale_after_seconds < 30) {
  fail("stale_after_seconds must be an integer >= 30");
}
validateOverall(snapshot.overall);

const incidentRefs = new Set();
const componentSeen = new Set();
if (!Array.isArray(snapshot.components) || !snapshot.components.length) {
  fail("components must be a non-empty array");
} else {
  snapshot.components.forEach((component, index) => validateComponent(component, index, componentSeen, incidentRefs));
}

const incidentSeen = new Set();
if (snapshot.incidents != null) {
  if (!Array.isArray(snapshot.incidents)) {
    fail("incidents must be an array when present");
  } else {
    snapshot.incidents.forEach((incident, index) => validateIncident(incident, index, incidentSeen, componentSeen));
  }
}

for (const incidentRef of incidentRefs) {
  if (!incidentSeen.has(incidentRef)) warn(`component references incident_ref without public incident details: ${incidentRef}`);
}

scanPublicSafety(snapshot, "$");

if (errors.length) {
  console.error(`Status snapshot validation failed: ${file}`);
  errors.forEach((message) => console.error(`- ${message}`));
  if (warnings.length) {
    console.error("Warnings:");
    warnings.forEach((message) => console.error(`- ${message}`));
  }
  process.exit(1);
}

console.log(`Status snapshot validation passed: ${file}`);
console.log(`components=${componentSeen.size} incidents=${incidentSeen.size} stage=${snapshot.overall?.stage} health=${snapshot.overall?.health}`);
if (warnings.length) {
  console.log("Warnings:");
  warnings.forEach((message) => console.log(`- ${message}`));
}
