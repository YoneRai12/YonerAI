#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = path.resolve(import.meta.dirname, "..");
const files = {
  rootHtml: path.join(root, "index.html"),
  jaHtml: path.join(root, "jp", "index.html"),
  enHtml: path.join(root, "en", "index.html"),
  styles: path.join(root, "styles.css"),
  runtimeCss: path.join(root, "runtime-status.css"),
  adapter: path.join(root, "mock-status-adapter.js"),
  publicFeed: path.join(root, "status-feed.json"),
  mockFeed: path.join(root, "status-feed.mock.json"),
};

const results = [];

function read(file) {
  return fs.readFileSync(file, "utf8");
}

function pass(name, detail = "") {
  results.push({ ok: true, name, detail });
}

function fail(name, detail = "") {
  results.push({ ok: false, name, detail });
}

function expect(name, condition, detail = "") {
  if (condition) pass(name, detail);
  else fail(name, detail);
}

function assetVersion(html, asset) {
  const escaped = asset.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = html.match(new RegExp(`${escaped}\\?v=([^"'\\s>]+)`));
  return match?.[1] || null;
}

function adapterVersion(source) {
  return source.match(/const VERSION = "([^"]+)"/)?.[1] || null;
}

function parseJson(file) {
  try {
    return JSON.parse(read(file));
  } catch (error) {
    fail(`parse ${path.basename(file)}`, error.message);
    return null;
  }
}

function validateFeed(name, feed) {
  if (!feed) return;
  const schema = feed.schema_version || feed.schema || "";
  expect(`${name}: schema`, /^yonerai\.status\.feed\.v/.test(schema), schema || "missing");
  expect(`${name}: categories array`, Array.isArray(feed.categories) && feed.categories.length > 0, `${feed.categories?.length || 0}`);
  expect(`${name}: incidents array`, Array.isArray(feed.incidents), `${feed.incidents?.length || 0}`);

  const componentIds = new Set();
  let dayCount = 0;
  let badDays = 0;
  let clickableDays = 0;
  let missingIncidentRefs = 0;
  const incidentIds = new Set((feed.incidents || []).map((incident) => incident.id));

  for (const category of feed.categories || []) {
    expect(`${name}: category id ${category.id || "(missing)"}`, Boolean(category.id), "");
    expect(`${name}: category children ${category.id}`, Array.isArray(category.children), "");
    const categoryDays = category.days || [];
    const childrenHaveDays = (category.children || []).length > 0
      && (category.children || []).every((component) => Array.isArray(component.days) && component.days.length === 90);
    expect(
      `${name}: category days or aggregate source ${category.id}`,
      categoryDays.length === 90 || childrenHaveDays,
      `categoryDays=${categoryDays.length} childrenHaveDays=${childrenHaveDays}`,
    );
    for (const day of categoryDays) {
      dayCount += 1;
      if (!day.date || !day.state) badDays += 1;
      if (day.clickable) clickableDays += 1;
      if (day.incident_id && !incidentIds.has(day.incident_id)) missingIncidentRefs += 1;
    }
    for (const component of category.children || []) {
      expect(`${name}: component id ${component.id || "(missing)"}`, Boolean(component.id), "");
      expect(`${name}: unique component id ${component.id}`, !componentIds.has(component.id), component.id || "");
      componentIds.add(component.id);
      const componentDays = component.days || [];
      expect(`${name}: component days ${component.id}`, componentDays.length === 90, `days=${componentDays.length}`);
      for (const day of componentDays) {
        dayCount += 1;
        if (!day.date || !day.state) badDays += 1;
        if (day.clickable) clickableDays += 1;
        if (day.incident_id && !incidentIds.has(day.incident_id)) missingIncidentRefs += 1;
      }
    }
  }

  expect(`${name}: day records complete`, badDays === 0, `badDays=${badDays}`);
  expect(`${name}: incident references`, missingIncidentRefs === 0, `missingIncidentRefs=${missingIncidentRefs}`);
  pass(`${name}: day/clickable summary`, `days=${dayCount} clickable=${clickableDays}`);
}

const htmlDocs = {
  root: read(files.rootHtml),
  ja: read(files.jaHtml),
  en: read(files.enHtml),
};
const runtimeCss = read(files.runtimeCss);
const stylesCss = read(files.styles);
const adapter = read(files.adapter);
const currentAdapterVersion = adapterVersion(adapter);

const versions = Object.fromEntries(
  Object.entries(htmlDocs).map(([key, html]) => [
    key,
    {
      styles: assetVersion(html, "styles.css"),
      runtimeCss: assetVersion(html, "runtime-status.css"),
      adapter: assetVersion(html, "mock-status-adapter.js"),
    },
  ]),
);

const adapterVersions = Object.values(versions).map((entry) => entry.adapter);
expect(
  "html adapter cache versions match runtime",
  adapterVersions.every((version) => version === currentAdapterVersion),
  JSON.stringify({ currentAdapterVersion, versions }),
);
expect("root stylesheet cache version is present", Boolean(versions.root.styles), JSON.stringify(versions.root));
expect("html pages include no-store meta", Object.values(htmlDocs).every((html) => html.includes('http-equiv="Cache-Control"') && html.includes('http-equiv="Pragma"')), "");
expect("html pages include runtime retry guard", Object.values(htmlDocs).every((html) => html.includes("runtime-retry-empty")), "");
expect("runtime adapter declares version", Boolean(currentAdapterVersion), currentAdapterVersion || "missing");
const runtimeApiBlock = adapter.match(/window\.YonerAIStatusRuntime\s*=\s*\{([\s\S]*?)\n\s*\};/);
const expectedRuntimeApiKeys = [
  "applyFeed",
  "setFeed",
  "trySetFeed",
  "reload",
  "refresh",
  "connectEvents",
  "disconnectEvents",
  "validateFeed",
  "syncRoute",
  "clearInteractionState",
  "rerender",
  "getState",
  "getFeed",
  "destroy",
];
const missingRuntimeApiKeys = runtimeApiBlock
  ? expectedRuntimeApiKeys.filter((key) => !new RegExp(`\\b${key}\\s*[:},]`).test(runtimeApiBlock[1]))
  : expectedRuntimeApiKeys;
expect(
  "runtime adapter exports public feed API",
  Boolean(runtimeApiBlock) && missingRuntimeApiKeys.length === 0,
  runtimeApiBlock ? missingRuntimeApiKeys.join(", ") : "runtime object missing",
);
expect("runtime adapter exposes legacy aliases", ["window.YonerAIStatus =", "yoneraiStatusSetFeed", "yoneraiStatusTrySetFeed", "yoneraiStatusGetFeed"].every((token) => adapter.includes(token)), "");
expect("runtime adapter handles feed update events", ["yonerai-status-feed:update", "yonerai-status:set-feed", "yonerai-status-feed:refresh"].every((token) => adapter.includes(token)), "");
expect("runtime adapter destroys old instance", adapter.includes("window.YonerAIStatusRuntime?.destroy") && adapter.includes("window.YonerAIStatusRuntime.destroy()"), "");
expect(
  "runtime adapter selects real feed by default",
  /function feedUrl\(\)[\s\S]*params\.get\("mockStatus"\) === "1"[\s\S]*localPreviewHost[\s\S]*status-feed\.mock\.json[\s\S]*status-feed\.json/.test(adapter),
  "",
);
expect("runtime adapter clears incident panel on status route", /function showStatusRoute[\s\S]*removeIncidentPanel\(\);[\s\S]*dataset\.statusRouteType = "status"/.test(adapter), "");
expect("runtime css owns overlap hard fix", runtimeCss.includes("20260601-uiux-overlap-hard-fix"), "");
expect("runtime css hides closed disclosure hit targets", /children\[aria-hidden="true"\][\s\S]*display:\s*none\s*!important/.test(runtimeCss), "");
expect("runtime css keeps open disclosure in flow", /category\.is-open > \.children[\s\S]*display:\s*block\s*!important/.test(runtimeCss), "");
expect("runtime css owns base bar transform", runtimeCss.includes("20260601-public-feed-label-fix") && /:not\(\.is-selected\)[\s\S]*transform:\s*none\s*!important/.test(runtimeCss), "");
expect("runtime css keeps tooltip position JS-owned", /tooltip\.runtime-tooltip,[\s\S]*tooltip\.runtime-tooltip\.is-visible[\s\S]*opacity 80ms ease,[\s\S]*visibility/.test(runtimeCss), "");
expect("root css keeps touch rows vertical-scroll safe", /\.bars,\s*\.category-bars,\s*\.child-bars\s*\{[\s\S]*touch-action:\s*pan-y/.test(stylesCss), "");

validateFeed("public feed", parseJson(files.publicFeed));
validateFeed("mock feed", parseJson(files.mockFeed));

const failures = results.filter((result) => !result.ok);
for (const result of results) {
  const mark = result.ok ? "PASS" : "FAIL";
  console.log(`${mark} ${result.name}${result.detail ? ` :: ${result.detail}` : ""}`);
}

if (failures.length) {
  console.error(`status-uiux-smoke failed: ${failures.length} failure(s)`);
  process.exit(1);
}

console.log("status-uiux-smoke passed");
