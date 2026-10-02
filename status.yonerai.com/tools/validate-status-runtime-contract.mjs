#!/usr/bin/env node

/*
 * Static contract check for the YonerAI Status browser runtime API.
 *
 * This does not execute the browser UI. It verifies that the runtime adapter
 * still exposes the public globals, methods, events, and routes described by
 * status-runtime-api.contract.json.
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const statusRoot = path.resolve(scriptDir, "..");

function usage() {
  console.log(`Usage:
  node status.yonerai.com/tools/validate-status-runtime-contract.mjs [contract.json] [adapter.js]
  node tools/validate-status-runtime-contract.mjs [contract.json] [adapter.js]

Default contract:
  status-runtime-api.contract.json

Default adapter:
  mock-status-adapter.js
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

function methodName(signature) {
  return String(signature).split("(")[0].trim();
}

function normalizeGlobal(value) {
  return String(value).replace(/^window\./, "");
}

function fail(errors, message) {
  errors.push(message);
}

function requireText(source, needle, label, errors) {
  if (!source.includes(needle)) fail(errors, `${label}: missing ${needle}`);
}

function requireRegex(source, regex, label, errors) {
  if (!regex.test(source)) fail(errors, `${label}: missing ${regex}`);
}

const options = parseArgs(process.argv.slice(2));
if (options.help) {
  usage();
  process.exit(0);
}

const contractPath = resolveInput(options.positionals[0], "status-runtime-api.contract.json");
const adapterPath = resolveInput(options.positionals[1], "mock-status-adapter.js");

let contract;
let adapter;
try {
  contract = JSON.parse(fs.readFileSync(contractPath, "utf8"));
  adapter = fs.readFileSync(adapterPath, "utf8");
} catch (error) {
  console.error("Failed to read runtime contract inputs.");
  console.error(error.message);
  process.exit(1);
}

const errors = [];

if (contract.schema_version !== "yonerai.status.runtime-api.v1") {
  fail(errors, `schema_version: expected yonerai.status.runtime-api.v1, got ${String(contract.schema_version)}`);
}
if (contract.accepted_feed_schema !== "yonerai.status.feed.v1") {
  fail(errors, "accepted_feed_schema must be yonerai.status.feed.v1");
}

const runtimeGlobal = normalizeGlobal(contract.runtime_global || "");
if (!runtimeGlobal) {
  fail(errors, "runtime_global is required");
} else {
  requireText(adapter, `window.${runtimeGlobal}`, "runtime_global", errors);
}

for (const globalName of contract.compatibility_globals || []) {
  const normalized = normalizeGlobal(globalName);
  requireText(adapter, `window.${normalized}`, `compatibility_globals.${normalized}`, errors);
}

for (const signature of Object.keys(contract.public_methods || {})) {
  const name = methodName(signature);
  if (!name) {
    fail(errors, `public_methods has an empty method signature: ${signature}`);
    continue;
  }
  requireRegex(adapter, new RegExp(`\\b${name}\\b`), `public_methods.${name}`, errors);
}

for (const eventName of Object.keys(contract.browser_events || {})) {
  requireText(adapter, eventName, `browser_events.${eventName}`, errors);
}

for (const [routeName, route] of Object.entries(contract.route_contract || {})) {
  if (route.includes("__category__")) {
    requireText(adapter, "__category__", `route_contract.${routeName}`, errors);
  }
  if (route.startsWith("#incident-")) {
    requireText(adapter, "incident-", `route_contract.${routeName}`, errors);
  }
  if (route.startsWith("#status/")) {
    requireText(adapter, "#status/", `route_contract.${routeName}`, errors);
  }
}

if (!Array.isArray(contract.invariants) || !contract.invariants.length) {
  fail(errors, "invariants must be a non-empty array");
}

if (errors.length) {
  console.error(`Status runtime contract validation failed: ${contractPath}`);
  for (const error of errors) console.error(`- ${error}`);
  process.exit(1);
}

console.log(`Status runtime contract validated: ${contractPath}`);
console.log(`adapter=${path.relative(statusRoot, adapterPath).replaceAll("\\", "/")} methods=${Object.keys(contract.public_methods || {}).length} events=${Object.keys(contract.browser_events || {}).length}`);
