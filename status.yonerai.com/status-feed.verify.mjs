import fs from "node:fs";

const ROOT = new URL(".", import.meta.url);
const FEEDS = ["status-feed.json", "status-feed.mock.json", "status-feed.example.json"];
const REQUIRED_FILES = ["index.html", "styles.css", "mock-status-adapter.js"];
const REQUIRED_DOCS = ["STATUS_UIUX_BASELINE.md", "STATUS_RUNTIME_FEED.md", "STATUS_FEED_API.md", "STATUS_RUNTIME_CONTRACT.md"];
const REQUIRED_TEMPLATE_TOKENS = [
  'id="categoryTemplate"',
  'id="childTemplate"',
  'id="categoryList"',
  'id="barTooltip"',
  "category-summary",
  "category-bars",
  "children-content",
  "child-summary",
  "child-bars",
  "child-detail",
  "detail-card",
];
const REQUIRED_ADAPTER_TOKENS = [
  "window.YonerAIStatusRuntime",
  "__version",
  "validateFeed",
  "setFeed",
  "trySetFeed",
  "reload",
  "connectEvents",
  "disconnectEvents",
  "syncRoute",
  "clearInteractionState",
  "rerender",
  "getState",
  "getFeed",
  "yonerai-status:set-feed",
  "yonerai-status-feed:update",
  "#status/",
  "#incident/",
  "status-feed.mock.json",
  "status-feed.json",
  "bar.dataset.statusRuntime = \"feed\"",
  "target.dataset.statusRuntime = \"feed\"",
  "bar.dataset.mockStatus = status",
  "runtime.bars.set(route, bar)",
  "runtime.selectedTimer",
  "statusRuntimeSmoke",
];
const REQUIRED_BASELINE_TOKENS = [
  "http://127.0.0.1:5500/?mockStatus=1&cacheBust=20260601-feed-label-ja-check#incident-test-29-major_outage",
  "http://127.0.0.1:5500/ は UIUX 完成基準ではありません",
  "data-status-runtime=\"feed\"",
  "#incident-test-29-major_outage",
];
const REQUIRED_RUNTIME_DOC_TOKENS = [
  "yonerai.status.feed.v1",
  "children",
  "days",
  "state",
  "affected",
  "updates",
  "YonerAIStatusRuntime.setFeed",
  "YonerAIStatusRuntime.trySetFeed",
  "connectEvents",
  "tools/status-feed-bridge.example.mjs",
];
const REQUIRED_STATES = [
  "operational",
  "alpha_only",
  "not_started",
  "maintenance",
  "degraded",
  "partial_outage",
  "major_outage",
  "resolved",
  "monitoring",
  "identified",
  "investigating",
];
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

const problems = [];

function readText(file) {
  return fs.readFileSync(new URL(file, ROOT), "utf8");
}

function fail(file, message) {
  problems.push(`${file}: ${message}`);
}

function assert(file, condition, message) {
  if (!condition) fail(file, message);
}

function localized(value) {
  return typeof value === "string" || (value && typeof value === "object" && (value.ja || value.en));
}

function walkStrings(value, visitor, trail = []) {
  if (typeof value === "string") {
    visitor(value, trail);
    return;
  }
  if (Array.isArray(value)) {
    value.forEach((item, index) => walkStrings(item, visitor, trail.concat(index)));
    return;
  }
  if (value && typeof value === "object") {
    Object.entries(value).forEach(([key, item]) => walkStrings(item, visitor, trail.concat(key)));
  }
}

function normalizeStateId(value) {
  return String(value || "not_started").trim().toLowerCase();
}

function validateNoMojibake(file) {
  const text = readText(file);
  const lines = text.split(/\r?\n/);
  lines.forEach((line, index) => {
    if (hasMojibakeText(line)) fail(file, `mojibake-like text at line ${index + 1}: ${line.slice(0, 120)}`);
  });
}

function validateUiContract() {
  for (const file of REQUIRED_FILES) {
    assert(file, fs.existsSync(new URL(file, ROOT)), "required status page file is missing");
  }
  for (const file of REQUIRED_DOCS) {
    assert(file, fs.existsSync(new URL(file, ROOT)), "required status documentation file is missing");
    validateNoMojibake(file);
  }
  const index = readText("index.html");
  const adapter = readText("mock-status-adapter.js");
  const baseline = readText("STATUS_UIUX_BASELINE.md");
  const runtimeDoc = readText("STATUS_RUNTIME_FEED.md");
  for (const token of REQUIRED_TEMPLATE_TOKENS) {
    assert("index.html", index.includes(token), `required template token missing: ${token}`);
  }
  for (const token of REQUIRED_ADAPTER_TOKENS) {
    assert("mock-status-adapter.js", adapter.includes(token), `required runtime token missing: ${token}`);
  }
  for (const token of REQUIRED_BASELINE_TOKENS) {
    assert("STATUS_UIUX_BASELINE.md", baseline.includes(token), `required UIUX baseline token missing: ${token}`);
  }
  for (const token of REQUIRED_RUNTIME_DOC_TOKENS) {
    assert("STATUS_RUNTIME_FEED.md", runtimeDoc.includes(token), `required runtime-feed doc token missing: ${token}`);
  }
}

function validateDay(file, states, day, prefix) {
  assert(file, day && typeof day === "object" && !Array.isArray(day), `${prefix} must be an object`);
  assert(file, /^\d{4}-\d{2}-\d{2}$/.test(String(day.date || "")), `${prefix}.date must be YYYY-MM-DD`);
  assert(file, states.has(normalizeStateId(day.state || day.status)), `${prefix}.state is unknown`);
}

function validateFeed(file) {
  let feed;
  try {
    feed = JSON.parse(readText(file));
  } catch (error) {
    fail(file, `invalid JSON: ${error.message}`);
    return;
  }

  walkStrings(feed, (text, trail) => {
    if (hasMojibakeText(text)) fail(file, `mojibake-like text at ${trail.join(".")}: ${text.slice(0, 80)}`);
  });

  assert(file, feed && typeof feed === "object" && !Array.isArray(feed), "feed root must be an object");
  assert(file, feed.schema_version === "yonerai.status.feed.v1", "schema_version must be yonerai.status.feed.v1");
  assert(file, feed.generated_at, "generated_at is required");
  assert(file, feed.range && typeof feed.range === "object", "range object is required");
  assert(file, /^\d{4}-\d{2}-\d{2}$/.test(String(feed.range?.start || "")), "range.start must be YYYY-MM-DD");
  assert(file, /^\d{4}-\d{2}-\d{2}$/.test(String(feed.range?.end || "")), "range.end must be YYYY-MM-DD");
  assert(file, Number.isInteger(Number(feed.range?.days)) && Number(feed.range.days) > 0, "range.days must be a positive integer");
  assert(file, Array.isArray(feed.categories), "categories must be an array");
  assert(file, Array.isArray(feed.incidents || []), "incidents must be an array when present");

  const states = new Set(REQUIRED_STATES);
  for (const [stateId, state] of Object.entries(feed.states || {})) {
    const id = normalizeStateId(stateId);
    states.add(id);
    assert(file, state && typeof state === "object" && !Array.isArray(state), `states.${stateId} must be an object`);
    assert(file, Number.isFinite(Number(state?.severity)), `states.${stateId}.severity must be numeric`);
    assert(file, /^#[0-9a-f]{6}$/i.test(String(state?.color || "")), `states.${stateId}.color must be #rrggbb`);
    assert(file, localized(state?.label || state?.labels), `states.${stateId}.label must be localized`);
  }
  for (const stateId of REQUIRED_STATES) {
    assert(file, states.has(stateId), `required state is missing: ${stateId}`);
  }

  const categories = new Set();
  const componentsByCategory = new Map();
  const expectedDays = Number(feed.range.days);
  for (const [categoryIndex, category] of (feed.categories || []).entries()) {
    const prefix = `categories[${categoryIndex}]`;
    assert(file, category && typeof category === "object" && !Array.isArray(category), `${prefix} must be an object`);
    assert(file, category.id, `${prefix}.id is required`);
    assert(file, !categories.has(String(category.id)), `${prefix}.id duplicates ${category.id}`);
    categories.add(String(category.id));
    assert(file, localized(category.name || category.id), `${prefix}.name must be localized`);
    assert(file, states.has(normalizeStateId(category.state || category.default_state || category.default_status || "not_started")), `${prefix}.state is unknown`);

    const children = category.children || category.components || [];
    assert(file, Array.isArray(children), `${prefix}.children must be an array`);
    assert(file, children.length > 0, `${prefix}.children must not be empty`);
    const componentIds = new Set();
    for (const [componentIndex, component] of children.entries()) {
      const componentPrefix = `${prefix}.children[${componentIndex}]`;
      assert(file, component && typeof component === "object" && !Array.isArray(component), `${componentPrefix} must be an object`);
      assert(file, component.id, `${componentPrefix}.id is required`);
      assert(file, !componentIds.has(String(component.id)), `${componentPrefix}.id duplicates ${component.id}`);
      componentIds.add(String(component.id));
      assert(file, localized(component.name || component.id), `${componentPrefix}.name must be localized`);
      assert(file, states.has(normalizeStateId(component.state || component.default_state || component.default_status || category.state || "not_started")), `${componentPrefix}.state is unknown`);
      assert(file, Array.isArray(component.days), `${componentPrefix}.days must be an array`);
      assert(file, component.days.length === expectedDays, `${componentPrefix}.days must have ${expectedDays} entries`);
      component.days.forEach((day, dayIndex) => validateDay(file, states, day, `${componentPrefix}.days[${dayIndex}]`));
    }
    componentsByCategory.set(String(category.id), componentIds);
  }

  const incidentIds = new Set();
  for (const [incidentIndex, incident] of (feed.incidents || []).entries()) {
    const prefix = `incidents[${incidentIndex}]`;
    assert(file, incident && typeof incident === "object" && !Array.isArray(incident), `${prefix} must be an object`);
    assert(file, incident.id, `${prefix}.id is required`);
    assert(file, !incidentIds.has(String(incident.id)), `${prefix}.id duplicates ${incident.id}`);
    incidentIds.add(String(incident.id));
    assert(file, localized(incident.title || incident.id), `${prefix}.title must be localized`);
    assert(file, states.has(normalizeStateId(incident.state || "resolved")), `${prefix}.state is unknown`);
    assert(file, states.has(normalizeStateId(incident.impact || incident.state || "resolved")), `${prefix}.impact is unknown`);
    if (incident.date) assert(file, /^\d{4}-\d{2}-\d{2}$/.test(String(incident.date)), `${prefix}.date must be YYYY-MM-DD`);
    if (incident.category_id) assert(file, categories.has(String(incident.category_id)), `${prefix}.category_id references unknown category`);
    if (incident.category_id && incident.component_id) {
      const componentIds = componentsByCategory.get(String(incident.category_id)) || new Set();
      assert(file, componentIds.has(String(incident.component_id)), `${prefix}.component_id references unknown component`);
    }
    const affectedItems = Array.isArray(incident.affected) ? incident.affected : incident.affected ? [incident.affected] : [];
    for (const [affectedIndex, item] of affectedItems.entries()) {
      const affectedPrefix = `${prefix}.affected[${affectedIndex}]`;
      assert(file, Array.isArray(item.segments || []), `${affectedPrefix}.segments must be an array when present`);
      const total = (item.segments || []).reduce((sum, segment) => sum + Number(segment.percent ?? segment.width ?? 0), 0);
      if ((item.segments || []).length) assert(file, Math.abs(total - 100) < 0.01, `${affectedPrefix}.segments percent total must be 100`);
      for (const [segmentIndex, segment] of (item.segments || []).entries()) {
        assert(file, states.has(normalizeStateId(segment.state || segment.status)), `${affectedPrefix}.segments[${segmentIndex}].state is unknown`);
        assert(file, Number(segment.percent ?? segment.width) > 0, `${affectedPrefix}.segments[${segmentIndex}].percent must be positive`);
      }
    }
    assert(file, Array.isArray(incident.updates || []), `${prefix}.updates must be an array when present`);
    for (const [updateIndex, update] of (incident.updates || []).entries()) {
      const updatePrefix = `${prefix}.updates[${updateIndex}]`;
      assert(file, states.has(normalizeStateId(update.state || update.status || "resolved")), `${updatePrefix}.state is unknown`);
      assert(file, localized(update.title || update.label || update.state || update.status), `${updatePrefix}.title must be localized`);
    }
  }
}

validateUiContract();
FEEDS.forEach(validateFeed);

if (problems.length) {
  console.error(problems.join("\n"));
  process.exit(1);
}

console.log(`YonerAI status feed contract OK (${FEEDS.join(", ")})`);
