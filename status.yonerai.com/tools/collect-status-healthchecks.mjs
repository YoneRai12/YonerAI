#!/usr/bin/env node

/*
 * Collect healthcheck-style inputs and write yonerai.status.monitor.v1.
 *
 * This is the reusable boundary between internal systems and the public status
 * feed pipeline. It can evaluate deterministic static checks, HTTP checks, and
 * already-collected AWS metric values without writing to DOM or browser files.
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const statusRoot = path.resolve(scriptDir, "..");

const severity = {
  operational: 0,
  not_started: 1,
  alpha_only: 1,
  maintenance: 2,
  degraded: 3,
  partial_outage: 4,
  major_outage: 5,
};

const defaultStateLabels = {
  operational: { ja: "稼働中", en: "Operational" },
  degraded: { ja: "性能低下", en: "Degraded" },
  maintenance: { ja: "メンテナンス", en: "Maintenance" },
  partial_outage: { ja: "一部障害", en: "Partial outage" },
  major_outage: { ja: "重大障害", en: "Major outage" },
  not_started: { ja: "準備中", en: "Not started" },
  alpha_only: { ja: "alpha only", en: "Alpha only" },
};

function resolveTemplate(value) {
  if (typeof value !== "string") return value;
  if (value === "__REPLACE_WITH_BEARER_TOKEN__") {
    const token = process.env.YONERAI_STATUS_TOKEN;
    if (token && token.trim()) {
      return `Bearer ${token.trim()}`;
    }
    return value;
  }
  if (value.startsWith("${") && value.endsWith("}") && value.length > 3) {
    const envName = value.slice(2, -1);
    const envValue = process.env[envName];
    if (envValue != null) return envValue;
  }
  return value;
}

function usage() {
  console.log(`Usage:
  node status.yonerai.com/tools/collect-status-healthchecks.mjs [healthcheck-input.json] [monitor-output.json]
  node tools/collect-status-healthchecks.mjs [healthcheck-input.json] [monitor-output.json]

Default input:
  status-healthcheck-input.example.json

Default output:
  generated/status-monitor-results.generated.json

Supported check types:
  static       deterministic state for fixtures or manual adapters
  http         same config can hit YonerAI API / health URLs
  aws_metric   already-collected AWS metric value with thresholds

The output is yonerai.status.monitor.v1 and should be passed to:
  tools/status-feed-bridge.example.mjs
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

function resolveOutput(value, fallback) {
  const chosen = value || fallback;
  if (path.isAbsolute(chosen)) return chosen;
  return isStatusPrefixed(chosen) ? path.resolve(process.cwd(), chosen) : path.resolve(statusRoot, chosen);
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

function writeJson(file, value) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

function todayUtc() {
  return new Date().toISOString().slice(0, 10);
}

function lastRangeDate(range) {
  if (!range?.start || !Number.isInteger(range.days)) return todayUtc();
  const date = new Date(`${range.start}T00:00:00.000Z`);
  date.setUTCDate(date.getUTCDate() + range.days - 1);
  return date.toISOString().slice(0, 10);
}

function localized(value, fallback) {
  if (value == null) return fallback;
  if (typeof value === "string") return { ja: value, en: value };
  return value;
}

function stateLabel(input, state) {
  return input.states?.[state]?.label || defaultStateLabels[state] || { ja: state, en: state };
}

function worseState(left, right) {
  return (severity[right] ?? 0) > (severity[left] ?? 0) ? right : left;
}

function compare(value, comparison, threshold) {
  const actual = Number(value);
  const limit = Number(threshold);
  if (!Number.isFinite(actual) || !Number.isFinite(limit)) return false;
  switch (comparison) {
    case "<": return actual < limit;
    case "<=": return actual <= limit;
    case ">": return actual > limit;
    case ">=": return actual >= limit;
    case "==": return actual === limit;
    case "!=": return actual !== limit;
    default: throw new Error(`unsupported comparison: ${comparison}`);
  }
}

function evaluateStatic(check) {
  return {
    state: check.state || "not_started",
    label: check.label || "static",
    message: localized(check.message, {
      ja: `static check: ${check.state || "not_started"}`,
      en: `static check: ${check.state || "not_started"}`,
    }),
    detail: check.detail,
    source: check.source || "static",
  };
}

async function evaluateHttp(check) {
  const started = Date.now();
  const timeoutMs = Number(check.timeout_ms || 5000);
  const min = Number(check.status_min ?? 200);
  const max = Number(check.status_max ?? 399);
  const degradedMs = Number(check.degraded_ms || 0);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const headers = {};
    if (check.headers && typeof check.headers === "object") {
      for (const [name, value] of Object.entries(check.headers)) {
        const resolved = resolveTemplate(value);
        if (typeof resolved === "string") headers[name] = resolved;
      }
    }
    const response = await fetch(resolveTemplate(check.url), {
      method: check.method || "GET",
      headers,
      signal: controller.signal,
    });
    const latencyMs = Date.now() - started;
    const ok = response.status >= min && response.status <= max;
    const slow = degradedMs > 0 && latencyMs > degradedMs;
    const state = ok ? (slow ? "degraded" : "operational") : (response.status >= 500 ? "major_outage" : "degraded");
    return {
      state,
      label: check.label || check.url,
      message: localized(check.message, {
        ja: `HTTP ${response.status}, ${latencyMs}ms`,
        en: `HTTP ${response.status}, ${latencyMs}ms`,
      }),
      detail: {
        summary: {
          ja: [`${check.url}`, `HTTP ${response.status}`, `${latencyMs}ms`],
          en: [`${check.url}`, `HTTP ${response.status}`, `${latencyMs}ms`],
        },
      },
      source: check.source || "http-healthcheck",
    };
  } catch (error) {
    return {
      state: "major_outage",
      label: check.label || check.url || "http",
      message: localized(check.message_on_error, {
        ja: `HTTP healthcheck failed: ${String(error?.message || error)}`,
        en: `HTTP healthcheck failed: ${String(error?.message || error)}`,
      }),
      detail: {
        summary: {
          ja: [String(check.url || "http"), String(error?.message || error)],
          en: [String(check.url || "http"), String(error?.message || error)],
        },
      },
      source: check.source || "http-healthcheck",
    };
  } finally {
    clearTimeout(timer);
  }
}

function evaluateAwsMetric(check) {
  const value = Number(check.value);
  let state = "operational";
  if (check.major_threshold != null && value >= Number(check.major_threshold)) {
    state = "major_outage";
  } else if (check.degraded_threshold != null && value >= Number(check.degraded_threshold)) {
    state = "degraded";
  } else if (!compare(value, check.comparison || "<=", check.threshold ?? 0)) {
    state = "degraded";
  }
  return {
    state,
    label: check.label || `${check.namespace || "AWS"}/${check.metric_name || "metric"}`,
    message: localized(check.message, {
      ja: `${check.namespace || "AWS"} ${check.metric_name || "metric"} = ${Number.isFinite(value) ? value : "unknown"}`,
      en: `${check.namespace || "AWS"} ${check.metric_name || "metric"} = ${Number.isFinite(value) ? value : "unknown"}`,
    }),
    detail: {
      summary: {
        ja: [
          `namespace: ${check.namespace || "AWS"}`,
          `metric: ${check.metric_name || "metric"}`,
          `value: ${Number.isFinite(value) ? value : "unknown"}`,
        ],
        en: [
          `namespace: ${check.namespace || "AWS"}`,
          `metric: ${check.metric_name || "metric"}`,
          `value: ${Number.isFinite(value) ? value : "unknown"}`,
        ],
      },
    },
    source: check.source || "aws-metric-input",
  };
}

async function evaluateCheck(check) {
  if (!check || typeof check !== "object") return evaluateStatic({ state: "not_started" });
  if (check.type === "http") return evaluateHttp(check);
  if (check.type === "aws_metric") return evaluateAwsMetric(check);
  if (check.type === "static" || check.type === "manual" || !check.type) return evaluateStatic(check);
  throw new Error(`unsupported check type: ${check.type}`);
}

async function evaluateComponent(input, component, date) {
  const checks = Array.isArray(component.checks) && component.checks.length
    ? component.checks
    : [{ type: "static", state: component.default_state || "not_started" }];
  const evaluated = [];
  let finalState = "operational";
  for (const check of checks) {
    const result = await evaluateCheck(check);
    evaluated.push(result);
    finalState = worseState(finalState, result.state);
  }
  const final = evaluated.find((result) => result.state === finalState) || evaluated[0];
  return {
    id: component.id,
    name: component.name,
    fact: component.fact,
    monitoring: component.monitoring,
    claim: component.claim,
    default_state: component.default_state || "not_started",
    default_message: component.default_message || {
      ja: "監視結果がない日は既定状態を表示します。",
      en: "Days without monitor results use the default state.",
    },
    results: [
      {
        date,
        state: finalState,
        label: stateLabel(input, finalState),
        message: final.message,
        detail: final.detail || {
          summary: {
            ja: evaluated.map((item) => `${item.label}: ${item.state}`),
            en: evaluated.map((item) => `${item.label}: ${item.state}`),
          },
        },
        source: final.source,
      },
    ],
  };
}

async function collect(input) {
  if (input.schema_version !== "yonerai.status.healthcheck.v1") {
    throw new Error(`unsupported healthcheck schema: ${input.schema_version}`);
  }
  const date = input.result_date || lastRangeDate(input.range);
  const categories = [];
  for (const category of input.categories || []) {
    const components = [];
    for (const component of category.components || category.children || []) {
      components.push(await evaluateComponent(input, component, date));
    }
    categories.push({
      id: category.id,
      name: category.name,
      description: category.description,
      components,
    });
  }
  return {
    schema_version: "yonerai.status.monitor.v1",
    generated_at: new Date().toISOString(),
    locale_default: input.locale_default || "ja",
    range: input.range,
    contract_note: input.contract_note,
    states: input.states || {},
    categories,
    incidents: Array.isArray(input.incidents) ? input.incidents : [],
  };
}

const options = parseArgs(process.argv.slice(2));
if (options.help) {
  usage();
  process.exit(0);
}

const inputPath = resolveInput(options.positionals[0], "status-healthcheck-input.example.json");
const outputPath = resolveOutput(options.positionals[1], "generated/status-monitor-results.generated.json");

try {
  const monitor = await collect(readJson(inputPath));
  writeJson(outputPath, monitor);
  console.log(`Collected status monitor results: ${outputPath}`);
} catch (error) {
  console.error(`Failed to collect status healthchecks: ${inputPath}`);
  console.error(error.message);
  process.exit(1);
}
