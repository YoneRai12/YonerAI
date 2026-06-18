#!/usr/bin/env node

/*
 * Fill healthcheck components from a YonerAI health summary JSON.
 *
 * This script does not authenticate to YonerAI and does not call private APIs.
 * It only maps an already-collected, public-safe health summary into
 * yonerai.status.healthcheck.v1 static checks.
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const statusRoot = path.resolve(scriptDir, "..");

const stateAliases = {
  ok: "operational",
  healthy: "operational",
  up: "operational",
  online: "operational",
  operational: "operational",
  warn: "degraded",
  warning: "degraded",
  slow: "degraded",
  degraded: "degraded",
  maintenance: "maintenance",
  not_started: "not_started",
  preparing: "not_started",
  alpha_only: "alpha_only",
  alpha: "alpha_only",
  partial_outage: "partial_outage",
  partial: "partial_outage",
  down: "major_outage",
  outage: "major_outage",
  error: "major_outage",
  critical: "major_outage",
  major_outage: "major_outage"
};

function usage() {
  console.log(`Usage:
  node status.yonerai.com/tools/fill-status-yonerai-health.mjs [healthcheck-input.json] [yonerai-health.json] [healthcheck-output.json]
  node tools/fill-status-yonerai-health.mjs [healthcheck-input.json] [yonerai-health.json] [healthcheck-output.json]

Default input:
  status-healthcheck-input.yonerai-api-http.example.json

Default YonerAI health summary:
  status-yonerai-health.example.json

Default output:
  generated/status-healthcheck-input.yonerai-filled.json

Accepted health summary shape:
  {
    "schema_version": "yonerai.status.yonerai-health.v1",
    "components": [
      {
        "category_id": "core-api",
        "component_id": "yonerai-api",
        "state": "operational",
        "message": { "ja": "OK", "en": "OK" },
        "checked_at": "2026-06-18T00:00:00Z"
      }
    ]
  }
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

function normalizeState(value) {
  return stateAliases[String(value || "").trim().toLowerCase()] || "not_started";
}

function localize(value, fallback) {
  if (value == null) return fallback;
  if (typeof value === "string") return { ja: value, en: value };
  if (isObject(value)) return value;
  return fallback;
}

function routeKeys(categoryId, componentId) {
  return [
    `${categoryId}/${componentId}`,
    componentId
  ].map((value) => String(value || "").toLowerCase());
}

function buildHealthIndex(health) {
  const index = new Map();
  const add = (record) => {
    if (!isObject(record)) return;
    const categoryId = record.category_id || record.categoryId || record.category;
    const componentId = record.component_id || record.componentId || record.component || record.id;
    if (!componentId) return;
    routeKeys(categoryId, componentId).forEach((key) => {
      if (key && key !== "undefined") index.set(key, record);
    });
  };

  if (Array.isArray(health.components)) {
    health.components.forEach(add);
  }

  if (isObject(health.components)) {
    Object.entries(health.components).forEach(([key, record]) => {
      if (isObject(record)) add({ id: key, ...record });
    });
  }

  if (isObject(health.statuses)) {
    Object.entries(health.statuses).forEach(([key, record]) => {
      if (isObject(record)) {
        const [categoryId, componentId] = key.includes("/") ? key.split("/", 2) : [null, key];
        add({ category_id: categoryId, component_id: componentId, ...record });
      } else {
        const [categoryId, componentId] = key.includes("/") ? key.split("/", 2) : [null, key];
        add({ category_id: categoryId, component_id: componentId, state: record });
      }
    });
  }

  return index;
}

function detailFor(record) {
  const summary = [];
  if (record.checked_at || record.checkedAt) summary.push(`checked_at: ${record.checked_at || record.checkedAt}`);
  if (record.latency_ms != null || record.latencyMs != null) summary.push(`latency_ms: ${record.latency_ms ?? record.latencyMs}`);
  if (record.status_code != null || record.statusCode != null) summary.push(`status_code: ${record.status_code ?? record.statusCode}`);
  if (record.version) summary.push(`version: ${record.version}`);
  if (record.region) summary.push(`region: ${record.region}`);
  if (record.detail?.summary) return record.detail;
  return summary.length ? { summary: { ja: summary, en: summary } } : undefined;
}

function fillHealthcheck(input, health) {
  if (input.schema_version !== "yonerai.status.healthcheck.v1") {
    throw new Error(`unsupported healthcheck schema: ${input.schema_version}`);
  }

  const index = buildHealthIndex(health);
  const output = structuredClone(input);
  let filled = 0;
  let missing = 0;

  for (const category of output.categories || []) {
    for (const component of category.components || category.children || []) {
      const match = routeKeys(category.id, component.id)
        .map((key) => index.get(key))
        .find(Boolean);
      if (!match) {
        missing += 1;
        continue;
      }

      const state = normalizeState(match.state || match.status || match.health);
      const message = localize(match.message, {
        ja: `${component.name?.ja || component.id}: ${state}`,
        en: `${component.name?.en || component.id}: ${state}`
      });
      component.checks = [
        {
          type: "static",
          state,
          label: match.label || `yonerai-health-${component.id}`,
          message,
          detail: detailFor(match),
          source: match.source || "yonerai-health-fill"
        }
      ];
      filled += 1;
    }
  }

  if (Array.isArray(health.incidents) && health.incidents.length) {
    output.incidents = health.incidents;
  }

  output.generated_at = new Date().toISOString();
  output.yonerai_health_fill = {
    generated_at: output.generated_at,
    source_schema: health.schema_version || null,
    filled,
    missing
  };
  return output;
}

const options = parseArgs(process.argv.slice(2));
if (options.help) {
  usage();
  process.exit(0);
}

const healthcheckPath = resolveInput(options.positionals[0], "status-healthcheck-input.yonerai-api-http.example.json");
const healthPath = resolveInput(options.positionals[1], "status-yonerai-health.example.json");
const outputPath = resolveOutput(options.positionals[2], "generated/status-healthcheck-input.yonerai-filled.json");

try {
  runValidator("tools/validate-status-healthcheck.mjs", healthcheckPath, "healthcheck input");
  runValidator("tools/validate-status-yonerai-health.mjs", healthPath, "YonerAI health input");
  const output = fillHealthcheck(readJson(healthcheckPath), readJson(healthPath));
  writeJson(outputPath, output);
  console.log(`Filled YonerAI healthcheck input: ${outputPath}`);
  console.log(`filled=${output.yonerai_health_fill.filled} missing=${output.yonerai_health_fill.missing}`);
  if (output.yonerai_health_fill.missing > 0) process.exitCode = 2;
} catch (error) {
  console.error("Failed to fill YonerAI healthcheck input.");
  console.error(error.message);
  process.exit(1);
}
