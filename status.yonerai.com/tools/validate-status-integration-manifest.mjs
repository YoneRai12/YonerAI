#!/usr/bin/env node

/*
 * Validate the YonerAI Status integration manifest.
 *
 * This keeps the repo-level integration map honest: files referenced by the
 * manifest must exist, schema versions must stay stable, and public/private
 * file boundaries must remain explicit.
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const statusRoot = path.resolve(scriptDir, "..");

function usage() {
  console.log(`Usage:
  node status.yonerai.com/tools/validate-status-integration-manifest.mjs [manifest.json]
  node tools/validate-status-integration-manifest.mjs [manifest.json]

Default manifest:
  status-integration.manifest.json
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

function existsRelative(relativePath) {
  return fs.existsSync(path.resolve(statusRoot, relativePath));
}

function fail(errors, message) {
  errors.push(message);
}

function requireFile(errors, label, relativePath) {
  if (typeof relativePath !== "string" || !relativePath.trim()) {
    fail(errors, `${label}: missing file path`);
    return;
  }
  if (relativePath.includes("*")) return;
  if (!existsRelative(relativePath)) fail(errors, `${label}: missing ${relativePath}`);
}

const options = parseArgs(process.argv.slice(2));
if (options.help) {
  usage();
  process.exit(0);
}

const manifestPath = resolveInput(options.positionals[0], "status-integration.manifest.json");

let manifest;
try {
  manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
} catch (error) {
  console.error(`Failed to read status integration manifest: ${manifestPath}`);
  console.error(error.message);
  process.exit(1);
}

const errors = [];

if (manifest.schema_version !== "yonerai.status.integration-manifest.v1") {
  fail(errors, `schema_version: expected yonerai.status.integration-manifest.v1, got ${String(manifest.schema_version)}`);
}
if (manifest.product !== "YonerAI Status") fail(errors, "product must be YonerAI Status");
if (manifest.public_origin !== "https://status.yonerai.com") fail(errors, "public_origin must be https://status.yonerai.com");

for (const [key, value] of Object.entries(manifest.public_runtime || {})) {
  requireFile(errors, `public_runtime.${key}`, value);
}

for (const [key, value] of Object.entries(manifest.schemas || {})) {
  requireFile(errors, `schemas.${key}.schema`, value.schema);
  if (typeof value.version !== "string" || !value.version.startsWith("yonerai.status.")) {
    fail(errors, `schemas.${key}.version: expected yonerai.status.*`);
  }
}

for (const [key, value] of Object.entries(manifest.pipelines || {})) {
  requireFile(errors, `pipelines.${key}.script`, value.script);
}

for (const [key, value] of Object.entries(manifest.validation || {})) {
  requireFile(errors, `validation.${key}`, value);
}

for (const requiredArray of [
  "source_of_truth_order",
  "public_files_allowed",
  "public_files_forbidden",
  "uiux_invariants",
  "claim_rules"
]) {
  if (!Array.isArray(manifest[requiredArray]) || manifest[requiredArray].length === 0) {
    fail(errors, `${requiredArray}: expected non-empty array`);
  }
}

if (manifest.runtime_update_contract?.only_runtime_feed_schema !== "yonerai.status.feed.v1") {
  fail(errors, "runtime_update_contract.only_runtime_feed_schema must be yonerai.status.feed.v1");
}

if (errors.length) {
  console.error(`Status integration manifest validation failed: ${manifestPath}`);
  for (const error of errors) console.error(`- ${error}`);
  process.exit(1);
}

console.log(`Status integration manifest validated: ${manifestPath}`);
console.log(`schemas=${Object.keys(manifest.schemas || {}).length} pipelines=${Object.keys(manifest.pipelines || {}).length} validations=${Object.keys(manifest.validation || {}).length}`);
