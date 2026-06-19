#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const statusRoot = path.resolve(scriptDir, "..");

function usage() {
  console.log(`Usage:
  node status.yonerai.com/tools/build-status-feed.mjs [source.json] [output-feed.json]
  node tools/build-status-feed.mjs [source.json] [output-feed.json]

Default input:
  status-feed.source.example.json

Default output:
  status-feed.generated.json

Purpose:
  Build a complete yonerai.status.feed.v1 feed from a compact source JSON.
`);
}

function parseArgs(argv) {
  const options = { positionals: [] };
  for (const arg of argv) {
    if (arg === "--help" || arg === "-h") {
      options.help = true;
    } else {
      options.positionals.push(arg);
    }
  }
  return options;
}

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

const options = parseArgs(process.argv.slice(2));
if (options.help) {
  usage();
  process.exit(0);
}

const inputPath = resolveInput(options.positionals[0], "status-feed.source.example.json");
const outputPath = resolveOutput(options.positionals[1], "status-feed.generated.json");

const defaultLabels = {
  operational: { ja: "稼働中", en: "Operational" },
  degraded: { ja: "性能低下", en: "Degraded" },
  maintenance: { ja: "メンテナンス", en: "Maintenance" },
  partial_outage: { ja: "一部障害", en: "Partial outage" },
  major_outage: { ja: "重大障害", en: "Major outage" },
  not_started: { ja: "準備中", en: "Not started" },
  alpha_only: { ja: "alpha only", en: "Alpha only" },
  monitoring: { ja: "監視中", en: "Monitoring" },
  identified: { ja: "特定中", en: "Identified" },
  investigating: { ja: "調査中", en: "Investigating" },
  resolved: { ja: "解決済み", en: "Resolved" },
  completed: { ja: "完了", en: "Completed" },
};

const defaultSeverity = {
  operational: 1,
  degraded: 3,
  maintenance: 2,
  partial_outage: 4,
  major_outage: 5,
  not_started: 1,
  alpha_only: 1,
  monitoring: 2,
  identified: 1,
  investigating: 2,
  resolved: 0,
  completed: 0,
};

function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

function writeJson(file, value) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

function addDays(date, offset) {
  const next = new Date(`${date}T00:00:00.000Z`);
  next.setUTCDate(next.getUTCDate() + offset);
  return next.toISOString().slice(0, 10);
}

function dateLabel(date) {
  return {
    ja: date.replace(/^(\d{4})-(\d{2})-(\d{2})$/, "$1年$2月$3日"),
    en: date,
  };
}

function labelFor(source, state) {
  return source.states?.[state]?.label || defaultLabels[state] || { ja: state, en: state };
}

function colorFor(source, state, overrideColor) {
  return overrideColor || source.states?.[state]?.color || "#aeb6c2";
}

function stateSeverity(source, state) {
  if (Number.isFinite(Number(source.states?.[state]?.severity))) {
    return Number(source.states[state].severity);
  }
  return defaultSeverity[state] ?? 1;
}

function detailFor(value) {
  if (value == null) return undefined;
  if (
    isObject(value) &&
    (
      Object.prototype.hasOwnProperty.call(value, "title") ||
      Object.prototype.hasOwnProperty.call(value, "summary") ||
      Object.prototype.hasOwnProperty.call(value, "meta") ||
      Object.prototype.hasOwnProperty.call(value, "actions")
    )
  ) {
    return value;
  }
  return { summary: value };
}

function affectedCountLabel(count) {
  const safeCount = Number.isFinite(Number(count)) ? Number(count) : 1;
  return {
    ja: `${safeCount}件の影響コンポーネント`,
    en: `${safeCount} affected component${safeCount === 1 ? "" : "s"}`,
  };
}

function normalizeDays(source, component, range) {
  const overrides = isObject(component.days) ? component.days : {};
  const defaultState = component.default_state || "not_started";
  return Array.from({ length: range.days }, (_, index) => {
    const date = addDays(range.start, index);
    const override = isObject(overrides[date]) ? overrides[date] : {};
    const state = override.state || defaultState;
    const day = {
      index,
      date,
      date_label: override.date_label || dateLabel(date),
      state,
      label: override.label || labelFor(source, state),
      color: colorFor(source, state, override.color),
      message: override.message || component.default_message,
      detail: detailFor(override.detail),
      source: override.source || "status-feed-source",
    };
    if (override.incident_id) day.incident_id = override.incident_id;
    return day;
  });
}

function collectIncidentLinks(categories) {
  const links = new Map();
  categories.forEach((category) => {
    (category.children || []).forEach((component) => {
      (component.days || []).forEach((day) => {
        if (!day.incident_id) return;
        if (!links.has(day.incident_id)) links.set(day.incident_id, []);
        const incidentLinks = links.get(day.incident_id);
        const route = `${category.id}/${component.id}`;
        const existing = incidentLinks.find((link) => link.route === route);
        if (existing) {
          if (day.date && (!existing.date || day.date < existing.date)) {
            existing.date = day.date;
            existing.date_label = day.date_label;
          }
          if (day.date && (!existing.end_date || day.date > existing.end_date)) {
            existing.end_date = day.date;
            existing.end_date_label = day.date_label;
          }
          return;
        }
        incidentLinks.push({
          route,
          category_id: category.id,
          component_id: component.id,
          component_name: component.name,
          date: day.date,
          end_date: day.date,
          date_label: day.date_label,
          end_date_label: day.date_label,
          state: day.state,
          color: day.color,
        });
      });
    });
  });
  return links;
}

function affectedComponentRefs(incidentLinks) {
  return incidentLinks.map((link) => ({
    category_id: link.category_id,
    component_id: link.component_id,
    name: link.component_name,
    state: link.state,
    date: link.date,
    end_date: link.end_date,
    date_label: link.date_label,
    end_date_label: link.end_date_label,
  }));
}

function enrichSegments(source, segments = []) {
  return segments.map((segment) => {
    if (!isObject(segment)) return segment;
    return {
      ...segment,
      color: colorFor(source, segment.state, segment.color),
    };
  });
}

function enrichIncident(source, incident, links) {
  if (!isObject(incident)) return incident;
  const incidentLinks = links.get(incident.id) || [];
  const firstLink = incidentLinks[0];
  const affected = isObject(incident.affected) ? { ...incident.affected } : {};
  if (firstLink) {
    const uniqueCategories = new Set(incidentLinks.map((link) => link.category_id));
    const firstDate = incidentLinks.reduce((value, link) => (!value || (link.date && link.date < value) ? link.date : value), firstLink.date);
    const lastDate = incidentLinks.reduce((value, link) => (!value || (link.end_date && link.end_date > value) ? link.end_date : value), firstLink.end_date || firstLink.date);
    const firstWindowLink = incidentLinks.find((link) => link.date === firstDate) || firstLink;
    const lastWindowLink = incidentLinks.find((link) => link.end_date === lastDate || link.date === lastDate) || firstLink;

    affected.category_id = affected.category_id || (uniqueCategories.size === 1 ? firstLink.category_id : undefined);
    affected.component_id = affected.component_id || (incidentLinks.length === 1 ? firstLink.component_id : undefined);
    affected.name = affected.name || (incidentLinks.length === 1 ? firstLink.component_name : affectedCountLabel(incidentLinks.length));
    affected.count = affected.count || affectedCountLabel(incidentLinks.length);
    if (!Array.isArray(affected.components) || affected.components.length === 0) {
      affected.components = affectedComponentRefs(incidentLinks);
    }
    affected.window = affected.window || {
      start_label: firstWindowLink.date_label || dateLabel(firstDate),
      end_label: lastWindowLink.end_date_label || lastWindowLink.date_label || dateLabel(lastDate),
    };
  }
  if (Array.isArray(affected.segments)) {
    affected.segments = enrichSegments(source, affected.segments);
  }
  if (!Object.keys(affected).length) {
    return { ...incident };
  }
  return { ...incident, affected };
}

function buildStates(source) {
  const sourceStates = source.states || {};
  const normalized = {};
  for (const [stateId, state] of Object.entries(sourceStates)) {
    if (!isObject(state)) continue;
    normalized[stateId] = {
      ...state,
      label: state.label || defaultLabels[stateId] || { ja: stateId, en: stateId },
      severity: Number.isFinite(Number(state.severity)) ? Number(state.severity) : (defaultSeverity[stateId] ?? 1),
    };
    if (typeof normalized[stateId].color !== "string") {
      normalized[stateId].color = "#aeb6c2";
    }
  }
  for (const [stateId, label] of Object.entries(defaultLabels)) {
    if (normalized[stateId]) continue;
    normalized[stateId] = {
      color: "#aeb6c2",
      label,
      severity: defaultSeverity[stateId] ?? 1,
    };
  }
  return normalized;
}

function buildFeed(source) {
  if (source.schema_version !== "yonerai.status.source.v1") {
    throw new Error(`unsupported source schema: ${source.schema_version}`);
  }
  const range = {
    start: source.range?.start,
    days: Number(source.range?.days || 90),
  };
  if (!/^\d{4}-\d{2}-\d{2}$/.test(range.start || "")) {
    throw new Error("source.range.start must use YYYY-MM-DD");
  }
  if (!Number.isInteger(range.days) || range.days < 1 || range.days > 120) {
    throw new Error("source.range.days must be an integer between 1 and 120");
  }

  const categories = (source.categories || []).map((category) => ({
    id: category.id,
    name: category.name,
    description: category.description,
    children: (category.children || category.components || []).map((component) => {
      const days = normalizeDays(source, component, range);
      return {
        id: component.id,
        name: component.name,
        fact: component.fact,
        monitoring: component.monitoring,
        claim: component.claim,
        state: component.state || days[days.length - 1]?.state || component.default_state || "not_started",
        days,
      };
    }),
  }));

  const incidentLinks = collectIncidentLinks(categories);

  return {
    schema_version: "yonerai.status.feed.v1",
    generated_at: source.generated_at || new Date().toISOString(),
    locale_default: source.locale_default || "ja",
    range: {
      days: range.days,
      start: range.start,
      end: addDays(range.start, range.days - 1),
    },
    meta: source.meta || {},
    contract_note: source.contract_note,
    states: buildStates(source),
    categories,
    incidents: Array.isArray(source.incidents) ? source.incidents.map((incident) => enrichIncident(source, incident, incidentLinks)) : [],
  };
}

try {
  const source = readJson(inputPath);
  const feed = buildFeed(source);
  writeJson(outputPath, feed);
  console.log(`Built status feed: ${outputPath}`);
} catch (error) {
  console.error(`Failed to build status feed from ${inputPath}`);
  console.error(error.message);
  process.exit(1);
}
