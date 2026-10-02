#!/usr/bin/env node

/*
 * Static UI/UX regression contract check for YonerAI Status.
 *
 * This does not replace browser QA. It catches obvious drift between the
 * UI/UX regression contract, runtime adapter diagnostics, and public assets
 * before a feed/runtime change reaches visual review.
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const statusRoot = path.resolve(scriptDir, "..");

function usage() {
  console.log(`Usage:
  node status.yonerai.com/tools/validate-status-uiux-regression.mjs [contract.json] [adapter.js] [styles.css] [index.html]
  node tools/validate-status-uiux-regression.mjs [contract.json] [adapter.js] [styles.css] [index.html]

Defaults:
  status-uiux-regression.contract.json
  mock-status-adapter.js
  styles.css
  index.html
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

function readOptional(file) {
  return fs.existsSync(file) ? fs.readFileSync(file, "utf8") : "";
}

function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function pushError(errors, message) {
  errors.push(message);
}

function pushWarning(warnings, message) {
  warnings.push(message);
}

function requireText(source, needle, label, errors) {
  if (!source.includes(needle)) pushError(errors, `${label}: missing ${needle}`);
}

function requireAnyText(source, needles, label, errors) {
  if (!needles.some((needle) => source.includes(needle))) {
    pushError(errors, `${label}: missing one of ${needles.join(", ")}`);
  }
}

function warnMissing(source, needle, label, warnings) {
  if (source && !source.includes(needle)) pushWarning(warnings, `${label}: did not find ${needle}`);
}

const options = parseArgs(process.argv.slice(2));
if (options.help) {
  usage();
  process.exit(0);
}

const contractPath = resolveInput(options.positionals[0], "status-uiux-regression.contract.json");
const adapterPath = resolveInput(options.positionals[1], "mock-status-adapter.js");
const cssPath = resolveInput(options.positionals[2], "styles.css");
const indexPath = resolveInput(options.positionals[3], "index.html");

let contract;
let adapter;
try {
  contract = JSON.parse(fs.readFileSync(contractPath, "utf8"));
  adapter = fs.readFileSync(adapterPath, "utf8");
} catch (error) {
  console.error("Failed to read UI/UX regression inputs.");
  console.error(error.message);
  process.exit(1);
}

const css = readOptional(cssPath);
const index = readOptional(indexPath);
const errors = [];
const warnings = [];

if (contract.schema_version !== "yonerai.status.uiux-regression.v1") {
  pushError(errors, `schema_version: expected yonerai.status.uiux-regression.v1, got ${String(contract.schema_version)}`);
}

if (!Array.isArray(contract.scope) || contract.scope.length === 0) {
  pushError(errors, "scope must be a non-empty array");
}

if (!isObject(contract.runtime_prerequisites)) {
  pushError(errors, "runtime_prerequisites must be an object");
} else {
  requireText(adapter, "window.YonerAIStatusRuntime", "runtime_prerequisites.required_global", errors);
  for (const method of contract.runtime_prerequisites.required_methods || []) {
    requireAnyText(adapter, [`${method},`, `${method}:`, `function ${method}`], `runtime_prerequisites.required_methods.${method}`, errors);
  }
  if (contract.runtime_prerequisites.required_feed_schema !== "yonerai.status.feed.v1") {
    pushError(errors, "runtime_prerequisites.required_feed_schema must be yonerai.status.feed.v1");
  }
}

const requiredSelectors = [
  "tooltip",
  "bar_detail_panel",
  "incident_detail_panel",
  "bar",
  "selected_bar",
  "category",
  "child",
  "theme_toggle"
];

if (!isObject(contract.selectors)) {
  pushError(errors, "selectors must be an object");
} else {
  for (const key of requiredSelectors) {
    if (typeof contract.selectors[key] !== "string" || !contract.selectors[key].trim()) {
      pushError(errors, `selectors.${key}: required`);
    }
  }
}

const requiredInvariants = [
  "tooltip_singleton",
  "tooltip_not_pointer_target",
  "selected_bar_singleton",
  "selected_bar_route_match",
  "detail_panel_singleton",
  "feed_update_clears_invalid_selection",
  "bar_cascade_single_pass",
  "bar_cascade_left_to_right",
  "disclosure_layout_animates_open_and_close",
  "dark_mode_surface_coverage",
  "mobile_range_header_no_wrap_glitch"
];

if (!isObject(contract.invariants)) {
  pushError(errors, "invariants must be an object");
} else {
  for (const invariant of requiredInvariants) {
    if (!isObject(contract.invariants[invariant])) {
      pushError(errors, `invariants.${invariant}: required`);
      continue;
    }
    if (!contract.invariants[invariant].severity) pushError(errors, `invariants.${invariant}.severity: required`);
    if (!contract.invariants[invariant].rule) pushError(errors, `invariants.${invariant}.rule: required`);
  }
}

for (const diagnostic of ["selectedCount", "statusPanels", "incidentPanels", "bars", "error", "selectedRoute"]) {
  requireText(adapter, diagnostic, `runtime getState diagnostic ${diagnostic}`, errors);
}

for (const selectorNeedle of ["#barTooltip", "#barDetailPanel", "#incidentDetailPanel", ".bar", ".is-selected"]) {
  requireText(adapter, selectorNeedle, `adapter selector ${selectorNeedle}`, errors);
}

requireText(adapter, "pointerdown", "touch/pointer handling", errors);
requireAnyText(adapter, ["mousemove", "pointermove"], "hover smooth movement", errors);
requireText(adapter, "hashchange", "route sync", errors);
requireText(adapter, "clearInteractionState", "interaction cleanup", errors);

if (!css) {
  pushWarning(warnings, `styles file not found: ${cssPath}`);
} else {
  warnMissing(css, "#barTooltip", "css tooltip selector", warnings);
  warnMissing(css, "pointer-events: none", "css tooltip pointer safety", warnings);
  warnMissing(css, ".bar.is-selected", "css selected bar selector", warnings);
  warnMissing(css, "prefers-reduced-motion", "css reduced motion support", warnings);
  warnMissing(css, "data-theme", "css theme variable coverage", warnings);
}

if (!index) {
  pushWarning(warnings, `index file not found: ${indexPath}`);
} else {
  warnMissing(index, "barTooltip", "index tooltip singleton", warnings);
  warnMissing(index, "themeToggle", "index theme toggle", warnings);
  warnMissing(index, "mock-status-adapter.js", "index runtime adapter script", warnings);
}

if (!Array.isArray(contract.manual_viewports) || contract.manual_viewports.length < 3) {
  pushError(errors, "manual_viewports must include mobile, desktop, and scaled desktop coverage");
}

if (!isObject(contract.runtime_probe_expectations)) {
  pushError(errors, "runtime_probe_expectations must be an object");
}

if (errors.length) {
  console.error(`Status UI/UX regression contract validation failed: ${contractPath}`);
  for (const error of errors) console.error(`- ${error}`);
  if (warnings.length) {
    console.error("Warnings:");
    for (const warning of warnings) console.error(`- ${warning}`);
  }
  process.exit(1);
}

console.log(`Status UI/UX regression contract validated: ${contractPath}`);
console.log(`adapter=${path.relative(statusRoot, adapterPath).replaceAll("\\", "/")} invariants=${Object.keys(contract.invariants || {}).length} viewports=${contract.manual_viewports?.length || 0}`);
if (warnings.length) {
  console.log("Warnings:");
  for (const warning of warnings) console.log(`- ${warning}`);
}
