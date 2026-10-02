#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const statusRoot = path.resolve(scriptDir, "..");
const defaultStates = new Set([
  "operational",
  "degraded",
  "maintenance",
  "partial_outage",
  "major_outage",
  "not_started",
  "alpha_only",
]);
const allowedSchemas = new Set(["yonerai.status.monitor.v1", "yonerai.status.source.v1"]);
const errors = [];
const warnings = [];
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
const unsafeTextPatterns = [
  { pattern: /\uFFFD/, label: "replacement character" },
  { pattern: /\[object Object\]/, label: "[object Object]" },
  { pattern: /\bundefined\b/i, label: "undefined literal" },
  { pattern: /\bnull\b/i, label: "null literal" },
];

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

const file = resolveInput(process.argv[2], "status-monitor-results.example.json");

function fail(message) {
  errors.push(message);
}

function warn(message) {
  warnings.push(message);
}

function textSafety(value, label) {
  if (typeof value !== "string") return;
  if (hasMojibakeText(value)) {
    fail(`${label} appears to contain mojibake: ${value}`);
    return;
  }
  for (const item of unsafeTextPatterns) {
    if (item.pattern.test(value)) {
      fail(`${label} contains unsafe display text (${item.label}): ${value}`);
      return;
    }
  }
}

function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function nonEmptyString(value, label) {
  if (typeof value !== "string" || !value.trim()) fail(`${label} must be a non-empty string`);
  else textSafety(value, label);
}

function id(value, label, seen) {
  if (typeof value !== "string" || !/^[A-Za-z0-9._-]+$/.test(value)) {
    fail(`${label} must be a stable id using A-Z, a-z, 0-9, dot, underscore, or hyphen`);
    return;
  }
  if (value === "__category__") fail(`${label} uses reserved runtime id: __category__`);
  if (seen?.has(value)) fail(`${label} is duplicated: ${value}`);
  seen?.add(value);
}

function date(value, label) {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    fail(`${label} must use YYYY-MM-DD`);
  }
}

function dateValue(value) {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return NaN;
  return Date.parse(`${value}T00:00:00.000Z`);
}

function addDays(value, offset) {
  const next = new Date(`${value}T00:00:00.000Z`);
  next.setUTCDate(next.getUTCDate() + offset);
  return next.toISOString().slice(0, 10);
}

function inRange(value, range) {
  if (!range?.start || !Number.isInteger(range.days)) return true;
  const current = dateValue(value);
  const start = dateValue(range.start);
  const end = dateValue(addDays(range.start, range.days - 1));
  return Number.isFinite(current) && current >= start && current <= end;
}

function localized(value, label) {
  if (typeof value === "string" && value.trim()) {
    textSafety(value, label);
    return;
  }
  if (Array.isArray(value)) {
    if (!value.length) fail(`${label} must not be an empty localized array`);
    value.forEach((item, index) => localized(item, `${label}[${index}]`));
    return;
  }
  if (isObject(value)) {
    const keys = Object.keys(value);
    if (!keys.length) fail(`${label} must not be an empty localized object`);
    const localeKeys = keys.filter((key) => /^[a-z]{2}(-[A-Z]{2})?$/.test(key) || key === "ja" || key === "en");
    if (!localeKeys.length) fail(`${label} localized object must include locale keys such as ja or en`);
    localeKeys.forEach((key) => localized(value[key], `${label}.${key}`));
    return;
  }
  fail(`${label} must be a non-empty string, localized object, or localized array`);
}

function color(value, label) {
  if (value != null && !/^#[0-9a-fA-F]{6}$/.test(String(value))) {
    fail(`${label} must be #RRGGBB`);
  }
}

function detail(value, label) {
  if (value == null) return;
  if (isObject(value) && ("title" in value || "summary" in value || "meta" in value || "actions" in value)) {
    if (value.title != null) localized(value.title, `${label}.title`);
    if (value.summary != null) localized(value.summary, `${label}.summary`);
    return;
  }
  localized(value, label);
}

function state(value, label, knownStates) {
  if (typeof value !== "string" || !knownStates.has(value)) {
    fail(`${label} has unknown state: ${String(value)}`);
  }
}

function validateStates(input, knownStates) {
  if (!isObject(input.states)) return;
  for (const [stateId, definition] of Object.entries(input.states)) {
    id(stateId, `states.${stateId}`, null);
    knownStates.add(stateId);
    if (!isObject(definition)) {
      fail(`states.${stateId} must be an object`);
      continue;
    }
    color(definition.color, `states.${stateId}.color`);
    if (definition.label != null) localized(definition.label, `states.${stateId}.label`);
  }
}

function validateRange(input) {
  if (!isObject(input.range)) {
    fail("range must be an object");
    return null;
  }
  date(input.range.start, "range.start");
  if (!Number.isInteger(input.range.days) || input.range.days < 1 || input.range.days > 120) {
    fail("range.days must be an integer between 1 and 120");
  }
  return input.range;
}

function validateAffected(incident, knownStates, componentRoutes, componentIds) {
  if (incident.affected == null) return;
  if (!isObject(incident.affected)) {
    fail(`incident ${incident.id}.affected must be an object when present`);
    return;
  }
  const affected = incident.affected;
  if (affected.name != null) localized(affected.name, `incident ${incident.id}.affected.name`);
  if (affected.count != null) localized(affected.count, `incident ${incident.id}.affected.count`);
  if (affected.category_id != null) id(affected.category_id, `incident ${incident.id}.affected.category_id`, null);
  if (affected.component_id != null) id(affected.component_id, `incident ${incident.id}.affected.component_id`, null);
  if (affected.category_id && affected.component_id) {
    const route = `${affected.category_id}/${affected.component_id}`;
    if (!componentRoutes.has(route)) fail(`incident ${incident.id}.affected references missing component route: ${route}`);
  } else if (affected.component_id != null) {
    if (!componentIds.has(affected.component_id)) fail(`incident ${incident.id}.affected references missing component_id: ${affected.component_id}`);
  } else {
    warn(`incident ${incident.id}.affected.component_id is recommended so the feed builder can keep affected UI linkable`);
  }
  if (affected.components != null) {
    if (!Array.isArray(affected.components)) {
      fail(`incident ${incident.id}.affected.components must be an array when present`);
    } else {
      affected.components.forEach((componentRef, componentRefIndex) => {
        if (!isObject(componentRef)) {
          fail(`incident ${incident.id}.affected.components[${componentRefIndex}] must be an object`);
          return;
        }
        id(componentRef.category_id, `incident ${incident.id}.affected.components[${componentRefIndex}].category_id`, null);
        id(componentRef.component_id, `incident ${incident.id}.affected.components[${componentRefIndex}].component_id`, null);
        const componentRoute = `${componentRef.category_id}/${componentRef.component_id}`;
        if (!componentRoutes.has(componentRoute)) {
          fail(`incident ${incident.id}.affected.components[${componentRefIndex}] references missing component route: ${componentRoute}`);
        }
        if (componentRef.name != null) localized(componentRef.name, `incident ${incident.id}.affected.components[${componentRefIndex}].name`);
        if (componentRef.state != null) state(componentRef.state, `incident ${incident.id}.affected.components[${componentRefIndex}].state`, knownStates);
        if (componentRef.date != null) date(componentRef.date, `incident ${incident.id}.affected.components[${componentRefIndex}].date`);
        if (componentRef.end_date != null) date(componentRef.end_date, `incident ${incident.id}.affected.components[${componentRefIndex}].end_date`);
        if (componentRef.date_label != null) localized(componentRef.date_label, `incident ${incident.id}.affected.components[${componentRefIndex}].date_label`);
        if (componentRef.end_date_label != null) localized(componentRef.end_date_label, `incident ${incident.id}.affected.components[${componentRefIndex}].end_date_label`);
      });
    }
  }
  if (affected.window != null) {
    if (!isObject(affected.window)) {
      fail(`incident ${incident.id}.affected.window must be an object when present`);
    } else {
      if (affected.window.start_label != null) localized(affected.window.start_label, `incident ${incident.id}.affected.window.start_label`);
      if (affected.window.end_label != null) localized(affected.window.end_label, `incident ${incident.id}.affected.window.end_label`);
    }
  }
  if (affected.segments != null && !Array.isArray(affected.segments)) {
    fail(`incident ${incident.id}.affected.segments must be an array when present`);
    return;
  }
  if (Array.isArray(affected.segments)) {
    const total = affected.segments.reduce((sum, segment) => sum + (isObject(segment) ? Number(segment.percent || 0) : 0), 0);
    if (Math.abs(total - 100) > 0.01) fail(`incident ${incident.id} affected segment percent total is ${total}, expected 100`);
    affected.segments.forEach((segment, segmentIndex) => {
      if (!isObject(segment)) {
        fail(`incident ${incident.id}.affected.segments[${segmentIndex}] must be an object`);
        return;
      }
      state(segment.state, `incident ${incident.id}.affected.segments[${segmentIndex}].state`, knownStates);
      if (typeof segment.percent !== "number" || segment.percent < 0 || segment.percent > 100) {
        fail(`incident ${incident.id}.affected.segments[${segmentIndex}].percent must be a number between 0 and 100`);
      }
      color(segment.color, `incident ${incident.id}.affected.segments[${segmentIndex}].color`);
      if (segment.tooltip != null) localized(segment.tooltip, `incident ${incident.id}.affected.segments[${segmentIndex}].tooltip`);
    });
  }
}

function validateIncidents(input, knownStates, componentRoutes, componentIds) {
  const incidentIds = new Set();
  if (input.incidents == null) return incidentIds;
  if (!Array.isArray(input.incidents)) {
    fail("incidents must be an array when present");
    return incidentIds;
  }
  input.incidents.forEach((incident, incidentIndex) => {
    if (!isObject(incident)) {
      fail(`incidents[${incidentIndex}] must be an object`);
      return;
    }
    id(incident.id, `incidents[${incidentIndex}].id`, incidentIds);
    if (incident.state != null) state(incident.state, `incident ${incident.id}.state`, knownStates);
    if (incident.status != null) nonEmptyString(incident.status, `incident ${incident.id}.status`);
    if (incident.date != null) date(incident.date, `incident ${incident.id}.date`);
    localized(incident.title, `incident ${incident.id}.title`);
    if (incident.meta != null) localized(incident.meta, `incident ${incident.id}.meta`);
    if (incident.summary != null) localized(incident.summary, `incident ${incident.id}.summary`);
    if (incident.footer != null) localized(incident.footer, `incident ${incident.id}.footer`);
    if (incident.updates != null && !Array.isArray(incident.updates)) {
      fail(`incident ${incident.id}.updates must be an array when present`);
    }
    if (Array.isArray(incident.updates)) {
      incident.updates.forEach((update, updateIndex) => {
        if (!isObject(update)) {
          fail(`incident ${incident.id}.updates[${updateIndex}] must be an object`);
          return;
        }
        if (update.status != null) nonEmptyString(update.status, `incident ${incident.id}.updates[${updateIndex}].status`);
        if (update.label != null) localized(update.label, `incident ${incident.id}.updates[${updateIndex}].label`);
        if (update.body != null) localized(update.body, `incident ${incident.id}.updates[${updateIndex}].body`);
        if (update.utc != null) nonEmptyString(update.utc, `incident ${incident.id}.updates[${updateIndex}].utc`);
        if (update.jst != null) nonEmptyString(update.jst, `incident ${incident.id}.updates[${updateIndex}].jst`);
      });
    }
    validateAffected(incident, knownStates, componentRoutes, componentIds);
  });
  return incidentIds;
}

function validateComponent(component, label, schema, range, knownStates, referencedIncidents) {
  if (!isObject(component)) {
    fail(`${label} must be an object`);
    return;
  }
  id(component.id, `${label}.id`, null);
  localized(component.name, `${label}.name`);
  if (component.fact != null) localized(component.fact, `${label}.fact`);
  if (component.monitoring != null) localized(component.monitoring, `${label}.monitoring`);
  if (component.claim != null) localized(component.claim, `${label}.claim`);
  if (component.default_state == null) fail(`${label}.default_state is required`);
  else state(component.default_state, `${label}.default_state`, knownStates);
  if (component.state != null) state(component.state, `${label}.state`, knownStates);
  if (component.default_message != null) localized(component.default_message, `${label}.default_message`);

  if (schema === "yonerai.status.monitor.v1") {
    if (component.results == null) return;
    if (!Array.isArray(component.results)) {
      fail(`${label}.results must be an array when present`);
      return;
    }
    const resultDates = new Set();
    component.results.forEach((result, resultIndex) => {
      if (!isObject(result)) {
        fail(`${label}.results[${resultIndex}] must be an object`);
        return;
      }
      date(result.date, `${label}.results[${resultIndex}].date`);
      if (resultDates.has(result.date)) fail(`${label}.results[${resultIndex}].date is duplicated: ${result.date}`);
      resultDates.add(result.date);
      if (!inRange(result.date, range)) fail(`${label}.results[${resultIndex}].date is outside range`);
      state(result.state, `${label}.results[${resultIndex}].state`, knownStates);
      color(result.color, `${label}.results[${resultIndex}].color`);
      if (result.label != null) localized(result.label, `${label}.results[${resultIndex}].label`);
      if (result.message != null) localized(result.message, `${label}.results[${resultIndex}].message`);
      detail(result.detail, `${label}.results[${resultIndex}].detail`);
      if (result.incident_id) referencedIncidents.add(result.incident_id);
    });
    return;
  }

  if (component.days == null) return;
  if (!isObject(component.days)) {
    fail(`${label}.days must be an object keyed by YYYY-MM-DD when present`);
    return;
  }
  for (const [dayDate, override] of Object.entries(component.days)) {
    date(dayDate, `${label}.days key`);
    if (!inRange(dayDate, range)) fail(`${label}.days[${dayDate}] is outside range`);
    if (!isObject(override)) {
      fail(`${label}.days[${dayDate}] must be an object`);
      continue;
    }
    state(override.state, `${label}.days[${dayDate}].state`, knownStates);
    color(override.color, `${label}.days[${dayDate}].color`);
    if (override.label != null) localized(override.label, `${label}.days[${dayDate}].label`);
    if (override.message != null) localized(override.message, `${label}.days[${dayDate}].message`);
    detail(override.detail, `${label}.days[${dayDate}].detail`);
    if (override.incident_id) referencedIncidents.add(override.incident_id);
  }
}

function validateCategories(input, range, knownStates, referencedIncidents) {
  const componentRoutes = new Set();
  const componentIds = new Set();
  if (!Array.isArray(input.categories) || input.categories.length === 0) {
    fail("categories must be a non-empty array");
    return { componentRoutes, componentIds };
  }
  const categoryIds = new Set();
  input.categories.forEach((category, categoryIndex) => {
    if (!isObject(category)) {
      fail(`categories[${categoryIndex}] must be an object`);
      return;
    }
    id(category.id, `categories[${categoryIndex}].id`, categoryIds);
    localized(category.name, `categories[${categoryIndex}].name`);
    if (category.description != null) localized(category.description, `categories[${categoryIndex}].description`);
    const hasChildren = Array.isArray(category.children);
    const hasComponents = Array.isArray(category.components);
    if (hasChildren === hasComponents) {
      fail(`category ${category.id || categoryIndex} must have exactly one of children or components`);
      return;
    }
    const children = hasChildren ? category.children : category.components;
    if (!children.length) {
      fail(`category ${category.id || categoryIndex} must have at least one component`);
      return;
    }
    const categoryComponentIds = new Set();
    children.forEach((component, componentIndex) => {
      if (component?.id != null) {
        id(component.id, `category ${category.id}.component[${componentIndex}].id`, categoryComponentIds);
        componentIds.add(component.id);
        componentRoutes.add(`${category.id}/${component.id}`);
      }
      validateComponent(component, `category ${category.id}.component[${componentIndex}]`, input.schema_version, range, knownStates, referencedIncidents);
    });
  });
  return { componentRoutes, componentIds };
}

let input;
try {
  input = JSON.parse(fs.readFileSync(file, "utf8"));
} catch (error) {
  console.error(`Failed to read status input: ${file}`);
  console.error(error.message);
  process.exit(1);
}

if (!isObject(input)) fail("input root must be an object");
if (!allowedSchemas.has(input.schema_version)) fail(`schema_version must be one of ${Array.from(allowedSchemas).join(", ")}`);
if (input.generated_at != null && typeof input.generated_at !== "string") fail("generated_at must be a string when present");

const knownStates = new Set(defaultStates);
validateStates(input, knownStates);
const range = validateRange(input);
const referencedIncidents = new Set();
const categoryIndex = range ? validateCategories(input, range, knownStates, referencedIncidents) : { componentRoutes: new Set(), componentIds: new Set() };
const incidentIds = validateIncidents(input, knownStates, categoryIndex.componentRoutes, categoryIndex.componentIds);

for (const incidentId of referencedIncidents) {
  if (!incidentIds.has(incidentId)) fail(`status input references missing incident_id: ${incidentId}`);
}

if (errors.length) {
  console.error(`Status input validation failed: ${file}`);
  errors.forEach((message) => console.error(`- ${message}`));
  if (warnings.length) {
    console.error("Warnings:");
    warnings.forEach((message) => console.error(`- ${message}`));
  }
  process.exit(1);
}

console.log(`Status input validation passed: ${file}`);
console.log(`schema=${input.schema_version} categories=${input.categories?.length || 0} states=${knownStates.size} incidents=${incidentIds.size}`);
if (warnings.length) {
  console.log("Warnings:");
  warnings.forEach((message) => console.log(`- ${message}`));
}
