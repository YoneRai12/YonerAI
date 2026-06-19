#!/usr/bin/env node

/*
 * Convert internal monitor result JSON into yonerai.status.source.v1.
 *
 * This keeps monitor integrations independent from the browser runtime. The
 * browser only receives completed yonerai.status.feed.v1 after the source is
 * built and validated.
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const statusRoot = path.resolve(scriptDir, "..");

function isStatusPrefixed(value) {
  return value.replaceAll("\\", "/").startsWith("status.yonerai.com/");
}

function resolveInput(value, fallback) {
  const next = value || fallback;
  if (path.isAbsolute(next)) return next;
  const cwdPath = path.resolve(process.cwd(), next);
  const statusPath = path.resolve(statusRoot, next);
  if (fs.existsSync(cwdPath)) return cwdPath;
  if (fs.existsSync(statusPath)) return statusPath;
  return isStatusPrefixed(next) ? cwdPath : statusPath;
}

function resolveOutput(value, fallback) {
  const next = value || fallback;
  if (path.isAbsolute(next)) return next;
  return isStatusPrefixed(next) ? path.resolve(process.cwd(), next) : path.resolve(statusRoot, next);
}

const inputPath = resolveInput(process.argv[2], "status-monitor-results.example.json");
const outputPath = resolveOutput(process.argv[3], "status-feed.source.generated.json");

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

function writeJson(file, value) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

function resultMap(results = []) {
  return Object.fromEntries(results.map((result) => [
    result.date,
    {
      state: result.state,
      label: result.label,
      message: result.message,
      detail: result.detail,
      color: result.color,
      date_label: result.date_label,
      incident_id: result.incident_id,
      source: result.source || "internal-monitor",
    },
  ]));
}

function convertComponent(component) {
  return {
    id: component.id,
    name: component.name,
    fact: component.fact,
    monitoring: component.monitoring,
    claim: component.claim,
    state: component.state,
    default_state: component.default_state || "not_started",
    default_message: component.default_message,
    days: resultMap(component.results),
  };
}

function convert(input) {
  if (input.schema_version !== "yonerai.status.monitor.v1") {
    throw new Error(`unsupported monitor result schema: ${input.schema_version}`);
  }
  return {
    schema_version: "yonerai.status.source.v1",
    generated_at: input.generated_at || new Date().toISOString(),
    locale_default: input.locale_default || "ja",
    range: input.range,
    contract_note: input.contract_note,
    states: input.states || {},
    categories: (input.categories || []).map((category) => ({
      id: category.id,
      name: category.name,
      description: category.description,
      children: (category.children || category.components || []).map(convertComponent),
    })),
    incidents: Array.isArray(input.incidents) ? input.incidents : [],
  };
}

try {
  const source = convert(readJson(inputPath));
  writeJson(outputPath, source);
  console.log(`Built status source: ${outputPath}`);
} catch (error) {
  console.error(`Failed to build status source from monitor results: ${inputPath}`);
  console.error(error.message);
  process.exit(1);
}
