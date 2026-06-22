#!/usr/bin/env node

/*
 * Convert AWS/Public YonerAI status snapshot v1 into the existing StatusWEB
 * source contract. The browser renderer still consumes only
 * yonerai.status.feed.v1.
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const statusRoot = path.resolve(scriptDir, "..");

const stateDefs = {
  operational: {
    severity: 0,
    color: "#25c39a",
    label: { ja: "稼働中", en: "Operational" },
  },
  degraded: {
    severity: 40,
    color: "#f6bd3f",
    label: { ja: "性能低下", en: "Degraded" },
  },
  disabled: {
    severity: 38,
    color: "#8f97a3",
    label: { ja: "\u7121\u52b9", en: "Disabled" },
  },
  partial_outage: {
    severity: 50,
    color: "#ff7a59",
    label: { ja: "一部障害", en: "Partial outage" },
  },
  major_outage: {
    severity: 60,
    color: "#ef5b4a",
    label: { ja: "重大障害", en: "Major outage" },
  },
  maintenance: {
    severity: 30,
    color: "#f97316",
    label: { ja: "メンテナンス", en: "Maintenance" },
  },
  offline: {
    severity: 65,
    color: "#ef5b4a",
    label: { ja: "オフライン", en: "Offline" },
  },
  unknown: {
    severity: 25,
    color: "#a9b0ba",
    label: { ja: "不明", en: "Unknown" },
  },
  investigating: {
    severity: 48,
    color: "#ff6b6b",
    label: { ja: "調査中", en: "Investigating" },
  },
  identified: {
    severity: 42,
    color: "#f6bd3f",
    label: { ja: "原因特定", en: "Identified" },
  },
  monitoring: {
    severity: 45,
    color: "#3a9dff",
    label: { ja: "監視中", en: "Monitoring" },
  },
  resolved: {
    severity: 0,
    color: "#25c39a",
    label: { ja: "解決済み", en: "Resolved" },
  },
};

const categoryCatalog = {
  "core-runtime": {
    order: 10,
    name: { ja: "Core runtime", en: "Core runtime" },
  },
  "identity-access": {
    order: 20,
    name: { ja: "Identity and access", en: "Identity and access" },
  },
  "provider-integrations": {
    order: 30,
    name: { ja: "Provider integrations", en: "Provider integrations" },
  },
  "public-surfaces": {
    order: 40,
    name: { ja: "Public surfaces", en: "Public surfaces" },
  },
  "governance-audit": {
    order: 50,
    name: { ja: "Governance and audit", en: "Governance and audit" },
  },
};

const componentCatalog = {
  api: { category: "core-runtime", name: { ja: "API", en: "API" } },
  auth: { category: "identity-access", name: { ja: "Auth", en: "Auth" } },
  provider_gateway: { category: "provider-integrations", name: { ja: "Provider gateway", en: "Provider gateway" } },
  official_execution_worker: { category: "core-runtime", name: { ja: "Official execution worker", en: "Official execution worker" } },
  run_queue: { category: "core-runtime", name: { ja: "Run queue", en: "Run queue" } },
  realtime_sync: { category: "core-runtime", name: { ja: "Realtime sync", en: "Realtime sync" } },
  web: { category: "public-surfaces", name: { ja: "Web", en: "Web" } },
  audit: { category: "governance-audit", name: { ja: "Audit", en: "Audit" } },
  discord: { category: "provider-integrations", name: { ja: "Discord", en: "Discord" } },
};

const availabilityLabel = {
  available: { ja: "利用可能", en: "Available" },
  limited: { ja: "制限あり", en: "Limited" },
  unavailable: { ja: "利用不可", en: "Unavailable" },
};

function usage() {
  console.log(`Usage:
  node status.yonerai.com/tools/build-status-source-from-snapshot.mjs [snapshot.json] [output-source.json]
  node tools/build-status-source-from-snapshot.mjs [snapshot.json] [output-source.json]

Default input:
  status-snapshot.example.json

Default output:
  generated/status-feed.source.from-snapshot.json
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

function resolveOutput(value, fallback) {
  const chosen = value || fallback;
  if (path.isAbsolute(chosen)) return chosen;
  return isStatusPrefixed(chosen) ? path.resolve(process.cwd(), chosen) : path.resolve(statusRoot, chosen);
}

function addDays(date, offset) {
  const next = new Date(`${date}T00:00:00.000Z`);
  next.setUTCDate(next.getUTCDate() + offset);
  return next.toISOString().slice(0, 10);
}

function dateFromTimestamp(value) {
  const parsed = new Date(value);
  if (!Number.isNaN(parsed.getTime())) return parsed.toISOString().slice(0, 10);
  return new Date().toISOString().slice(0, 10);
}

function rangeFromSnapshot(snapshot) {
  const days = 90;
  const end = dateFromTimestamp(snapshot.generated_at);
  return { start: addDays(end, 1 - days), days };
}

function local(value, fallback) {
  if (value == null) return fallback;
  if (typeof value === "string") return { ja: value, en: value };
  if (Array.isArray(value)) return { ja: value, en: value };
  return value;
}

function stateLabel(state) {
  return stateDefs[state]?.label || { ja: state, en: state };
}

function componentName(component) {
  return componentCatalog[component.id]?.name || { ja: component.id, en: component.id };
}

function categoryFor(component) {
  return componentCatalog[component.id]?.category || "public-surfaces";
}

function disclosure(snapshot) {
  return {
    ja: [
      "StatusSnapshot v1 から生成された公開safeなStatusWEB sourceです。",
      "これは staging/preview の状態表示であり、本番稼働、24時間運用、Live Discord restored、Google Login complete は主張しません。",
      "AWS/Private runtime の秘密情報、内部hostname、account detail、worker PC identity、run contents、provider prompt/output は表示しません。"
    ],
    en: [
      "Public-safe StatusWEB source generated from StatusSnapshot v1.",
      "This is a staging/preview status display and does not claim production, 24/7 operation, Live Discord restored, or Google Login complete.",
      "AWS/private runtime secrets, internal hostnames, account details, worker PC identity, run contents, and provider prompt/output are not displayed."
    ]
  };
}

function factFor(component) {
  return local(component.message, {
    ja: "AWS/Public YonerAI status snapshot から生成された公開safeな状態です。",
    en: "Public-safe state generated from the AWS/Public YonerAI status snapshot.",
  });
}

function monitoringFor(snapshot, component) {
  return {
    ja: `最終更新: ${component.updated_at || snapshot.generated_at}${component.stale ? " / stale" : ""}`,
    en: `Last updated: ${component.updated_at || snapshot.generated_at}${component.stale ? " / stale" : ""}`,
  };
}

function claimFor(component) {
  const availability = availabilityLabel[component.availability] || availabilityLabel.limited;
  return {
    ja: `${availability.ja} / stage: ${component.stage}. 本番運用や24時間運用は主張しません。`,
    en: `${availability.en} / stage: ${component.stage}. No production or 24/7 operation claim.`,
  };
}

function messageFor(component) {
  const base = local(component.message, stateLabel(component.health));
  if (!component.stale) return base;
  return {
    ja: Array.isArray(base.ja) ? [...base.ja, "このcomponentはstaleとして報告されています。"] : `${base.ja} / stale`,
    en: Array.isArray(base.en) ? [...base.en, "This component is reported stale."] : `${base.en} / stale`,
  };
}

function componentState(component) {
  if (component.id === "realtime_sync" && component.stage === "disabled") return "disabled";
  if (component.availability === "disabled") return "disabled";
  return component.health;
}

function componentToSource(snapshot, component) {
  const currentDate = dateFromTimestamp(snapshot.generated_at);
  const state = componentState(component);
  return {
    id: component.id,
    name: componentName(component),
    fact: factFor(component),
    monitoring: monitoringFor(snapshot, component),
    claim: claimFor(component),
    state,
    default_state: "unknown",
    default_message: {
      ja: "履歴データはまだありません。",
      en: "History data is not yet available.",
    },
    days: {
      [currentDate]: {
        state,
        message: messageFor(component),
        ...(component.incident_ref ? { incident_id: component.incident_ref } : {}),
        source: "status-snapshot-v1",
      },
    },
  };
}

function groupedCategories(snapshot) {
  const byCategory = new Map();
  (snapshot.components || []).forEach((component) => {
    const categoryId = categoryFor(component);
    if (!byCategory.has(categoryId)) byCategory.set(categoryId, []);
    byCategory.get(categoryId).push(componentToSource(snapshot, component));
  });
  return Array.from(byCategory.entries())
    .sort(([left], [right]) => (categoryCatalog[left]?.order || 999) - (categoryCatalog[right]?.order || 999))
    .map(([id, children]) => ({
      id,
      name: categoryCatalog[id]?.name || { ja: id, en: id },
      children,
    }));
}

function componentRouteIndex(categories) {
  const index = new Map();
  categories.forEach((category) => {
    category.children.forEach((component) => {
      index.set(component.id, { category, component });
    });
  });
  return index;
}

function incidentDate(incident, snapshot) {
  return dateFromTimestamp(incident.started_at || incident.resolved_at || snapshot.generated_at);
}

function affectedFor(snapshot, incident, categories) {
  const index = componentRouteIndex(categories);
  const refs = (incident.component_ids || [])
    .map((componentId) => {
      const found = index.get(componentId);
      if (!found) return null;
      const date = incidentDate(incident, snapshot);
      return {
        category_id: found.category.id,
        component_id: found.component.id,
        name: found.component.name,
        state: incident.impact,
        date,
        end_date: date,
      };
    })
    .filter(Boolean);
  const first = refs[0];
  return {
    category_id: refs.length === 1 ? first?.category_id : undefined,
    component_id: refs.length === 1 ? first?.component_id : undefined,
    components: refs,
    name: refs.length === 1 ? first?.name : {
      ja: `${refs.length}件の影響コンポーネント`,
      en: `${refs.length} affected components`,
    },
    count: {
      ja: `${refs.length || 1}件の影響コンポーネント`,
      en: `${refs.length || 1} affected component${refs.length === 1 ? "" : "s"}`,
    },
    segments: [
      {
        state: incident.impact || "unknown",
        percent: 100,
        tooltip: local(incident.title, stateLabel(incident.impact || "unknown")),
      },
    ],
  };
}

function incidentsToSource(snapshot, categories) {
  return (snapshot.incidents || []).map((incident) => {
    const affected = affectedFor(snapshot, incident, categories);
    return {
      id: incident.id,
      state: incident.impact,
      status: incident.status,
      date: incidentDate(incident, snapshot),
      ...(affected.category_id ? { category_id: affected.category_id } : {}),
      ...(affected.component_id ? { component_id: affected.component_id } : {}),
      title: local(incident.title, incident.id),
      meta: [
        stateLabel(incident.status || "monitoring"),
        stateLabel(incident.impact || "unknown"),
        { ja: `stage: ${snapshot.overall.stage}`, en: `stage: ${snapshot.overall.stage}` },
      ],
      summary: local(incident.summary, ""),
      footer: {
        ja: `${incidentDate(incident, snapshot)} ・ すべての更新を見る`,
        en: `${incidentDate(incident, snapshot)} ・ View all updates`,
      },
      affected,
      updates: (incident.updates || []).map((update) => ({
        status: update.status,
        label: local(update.label, stateLabel(update.status)),
        body: local(update.body, ""),
        utc: update.at,
        jst: update.at,
      })),
    };
  });
}

function buildSource(snapshot) {
  if (snapshot.schema_version !== "yonerai.status.v1") {
    throw new Error(`unsupported snapshot schema: ${snapshot.schema_version}`);
  }
  const range = rangeFromSnapshot(snapshot);
  const categories = groupedCategories(snapshot);
  return {
    schema_version: "yonerai.status.source.v1",
    generated_at: snapshot.generated_at,
    locale_default: "ja",
    range,
    meta: {
      source: "status-snapshot-v1",
      upstream_schema: snapshot.schema_version,
      snapshot_id: snapshot.snapshot_id,
      stale_after_seconds: snapshot.stale_after_seconds,
      overall_health: snapshot.overall.health,
      overall_availability: snapshot.overall.availability,
      overall_stage: snapshot.overall.stage,
    },
    contract_note: local(snapshot.overall.message, disclosure(snapshot)),
    states: stateDefs,
    categories,
    incidents: incidentsToSource(snapshot, categories),
  };
}

const args = process.argv.slice(2);
if (args.includes("--help") || args.includes("-h")) {
  usage();
  process.exit(0);
}

const inputPath = resolveInput(args[0], "status-snapshot.example.json");
const outputPath = resolveInput(args[1], "generated/status-feed.source.from-snapshot.json");

try {
  const snapshot = JSON.parse(fs.readFileSync(inputPath, "utf8"));
  const source = buildSource(snapshot);
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, `${JSON.stringify(source, null, 2)}\n`, "utf8");
  console.log(`Built status source from snapshot: ${outputPath}`);
} catch (error) {
  console.error(`Failed to build status source from snapshot: ${inputPath}`);
  console.error(error.message);
  process.exit(1);
}
