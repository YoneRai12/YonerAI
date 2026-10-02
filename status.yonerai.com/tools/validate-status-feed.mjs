#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";

const allowedSchemas = new Set(["yonerai.status.feed.v1"]);
const defaultStates = new Set([
  "operational",
  "degraded",
  "maintenance",
  "partial_outage",
  "major_outage",
  "not_started",
  "alpha_only",
]);

const file = process.argv[2] || path.join("status.yonerai.com", "status-feed.mock.json");
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

function id(value, label, seen) {
  if (typeof value !== "string" || !/^[A-Za-z0-9._-]+$/.test(value)) {
    fail(`${label} must be a stable id using A-Z, a-z, 0-9, dot, underscore, or hyphen`);
    return;
  }
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

function state(value, label, knownStates) {
  if (typeof value !== "string" || !knownStates.has(value)) {
    fail(`${label} has unknown state: ${String(value)}`);
  }
}

function color(value, label) {
  if (value != null && !/^#[0-9a-fA-F]{6}$/.test(String(value))) {
    fail(`${label} must be #RRGGBB`);
  }
}

let feed;
try {
  feed = JSON.parse(fs.readFileSync(file, "utf8"));
} catch (error) {
  console.error(`Failed to read feed: ${file}`);
  console.error(error.message);
  process.exit(1);
}

if (!isObject(feed)) fail("feed root must be an object");
if (!allowedSchemas.has(feed.schema_version)) fail(`schema_version must be yonerai.status.feed.v1, got ${String(feed.schema_version)}`);
if (typeof feed.generated_at !== "string" || !feed.generated_at.trim()) fail("generated_at must be a non-empty string");

const range = feed.range;
let expectedDayCount = null;
if (range != null) {
  if (!isObject(range)) {
    fail("range must be an object when present");
  } else {
    if (!Number.isInteger(range.days) || range.days < 1 || range.days > 120) {
      fail("range.days must be an integer between 1 and 120");
    } else {
      expectedDayCount = range.days;
    }
    if (range.start != null) date(range.start, "range.start");
    if (range.end != null) date(range.end, "range.end");
    if (range.start && range.end && Number.isInteger(range.days)) {
      const expectedEnd = addDays(range.start, range.days - 1);
      if (range.end !== expectedEnd) fail(`range.end must equal ${expectedEnd} for range.start and range.days`);
    }
  }
}

const knownStates = new Set(defaultStates);
if (isObject(feed.states)) {
  for (const [stateId, definition] of Object.entries(feed.states)) {
    id(stateId, `states.${stateId}`, null);
    knownStates.add(stateId);
    if (!isObject(definition)) fail(`states.${stateId} must be an object`);
    if (definition?.label != null) localized(definition.label, `states.${stateId}.label`);
    if (definition?.color != null && !/^#[0-9a-fA-F]{6}$/.test(definition.color)) {
      fail(`states.${stateId}.color must be #RRGGBB`);
    }
  }
}

const incidentIds = new Set();
const referencedIncidents = new Set();
const categoryIds = new Set();
const componentIds = new Set();
const componentRoutes = new Set();

if (!Array.isArray(feed.categories) || feed.categories.length === 0) {
  fail("categories must be a non-empty array");
} else {
  feed.categories.forEach((category, categoryIndex) => {
    if (!isObject(category)) {
      fail(`categories[${categoryIndex}] must be an object`);
      return;
    }
    id(category.id, `categories[${categoryIndex}].id`, categoryIds);
    localized(category.name, `categories[${categoryIndex}].name`);

    const children = category.children || category.components;
    if (!Array.isArray(children) || children.length === 0) {
      fail(`category ${category.id || categoryIndex} must have non-empty children`);
      return;
    }

    let categoryDateSignature = null;
    children.forEach((component, componentIndex) => {
      if (!isObject(component)) {
        fail(`category ${category.id} child[${componentIndex}] must be an object`);
        return;
      }
      id(component.id, `component id in category ${category.id}`, componentIds);
      if (component.id === "__category__") fail("__category__ is reserved for runtime category overview routes");
      componentRoutes.add(`${category.id}/${component.id}`);
      localized(component.name, `component ${component.id}.name`);
      if (component.fact != null) localized(component.fact, `component ${component.id}.fact`);
      if (component.monitoring != null) localized(component.monitoring, `component ${component.id}.monitoring`);
      if (component.claim != null) localized(component.claim, `component ${component.id}.claim`);
      if (component.state != null) state(component.state, `component ${component.id}.state`, knownStates);
      if (!Array.isArray(component.days) || component.days.length === 0) {
        fail(`component ${component.id} must have non-empty days`);
        return;
      }
      if (expectedDayCount != null && component.days.length !== expectedDayCount) {
        fail(`component ${component.id} days length must equal range.days (${expectedDayCount})`);
      }
      const dateSignature = component.days.map((day) => isObject(day) ? day.date : "").join("|");
      if (categoryDateSignature == null) categoryDateSignature = dateSignature;
      else if (dateSignature !== categoryDateSignature) {
        fail(`category ${category.id} children must share the same ordered day dates for aggregate status bars`);
      }
      let previousDateValue = null;
      component.days.forEach((day, dayIndex) => {
        if (!isObject(day)) {
          fail(`component ${component.id}.days[${dayIndex}] must be an object`);
          return;
        }
        if (day.index != null && day.index !== dayIndex) {
          fail(`component ${component.id}.days[${dayIndex}].index must equal ${dayIndex}`);
        }
        date(day.date, `component ${component.id}.days[${dayIndex}].date`);
        if (range?.start && day.date !== addDays(range.start, dayIndex)) {
          fail(`component ${component.id}.days[${dayIndex}].date must equal ${addDays(range.start, dayIndex)} from range.start`);
        }
        const currentDateValue = dateValue(day.date);
        if (previousDateValue != null && Number.isFinite(currentDateValue) && currentDateValue <= previousDateValue) {
          fail(`component ${component.id}.days[${dayIndex}].date must be strictly increasing`);
        }
        previousDateValue = currentDateValue;
        state(day.state, `component ${component.id}.days[${dayIndex}].state`, knownStates);
        color(day.color, `component ${component.id}.days[${dayIndex}].color`);
        if (day.label != null) localized(day.label, `component ${component.id}.days[${dayIndex}].label`);
        if (day.message != null) localized(day.message, `component ${component.id}.days[${dayIndex}].message`);
        if (day.detail != null) {
          if (!isObject(day.detail)) fail(`component ${component.id}.days[${dayIndex}].detail must be an object when present`);
          if (day.detail?.summary != null) localized(day.detail.summary, `component ${component.id}.days[${dayIndex}].detail.summary`);
        }
        if (day.incident_id) referencedIncidents.add(day.incident_id);
      });
    });
  });
}

if (Array.isArray(feed.incidents)) {
  feed.incidents.forEach((incident, incidentIndex) => {
    if (!isObject(incident)) {
      fail(`incidents[${incidentIndex}] must be an object`);
      return;
    }
    id(incident.id, `incidents[${incidentIndex}].id`, incidentIds);
    if (incident.state != null) state(incident.state, `incident ${incident.id}.state`, knownStates);
    if (incident.status != null) nonEmptyString(incident.status, `incident ${incident.id}.status`);
    localized(incident.title, `incident ${incident.id}.title`);
    if (incident.date != null) date(incident.date, `incident ${incident.id}.date`);
    if (incident.meta != null) {
      if (!Array.isArray(incident.meta)) {
        fail(`incident ${incident.id}.meta must be an array when present`);
      } else {
        incident.meta.forEach((item, itemIndex) => localized(item, `incident ${incident.id}.meta[${itemIndex}]`));
      }
    }
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
        if (update.status != null && typeof update.status !== "string") fail(`incident ${incident.id}.updates[${updateIndex}].status must be a string`);
        if (update.label != null) localized(update.label, `incident ${incident.id}.updates[${updateIndex}].label`);
        if (update.body != null) localized(update.body, `incident ${incident.id}.updates[${updateIndex}].body`);
        if (update.utc != null) nonEmptyString(update.utc, `incident ${incident.id}.updates[${updateIndex}].utc`);
        if (update.jst != null) nonEmptyString(update.jst, `incident ${incident.id}.updates[${updateIndex}].jst`);
      });
    }
    if (incident.affected != null) {
      if (!isObject(incident.affected)) {
        fail(`incident ${incident.id}.affected must be an object when present`);
      } else {
        if (incident.affected.name != null) localized(incident.affected.name, `incident ${incident.id}.affected.name`);
        if (incident.affected.count != null) localized(incident.affected.count, `incident ${incident.id}.affected.count`);
        if (incident.affected.category_id != null) id(incident.affected.category_id, `incident ${incident.id}.affected.category_id`, null);
        if (incident.affected.component_id != null) id(incident.affected.component_id, `incident ${incident.id}.affected.component_id`, null);
        if (incident.affected.category_id && incident.affected.component_id) {
          const route = `${incident.affected.category_id}/${incident.affected.component_id}`;
          if (!componentRoutes.has(route)) fail(`incident ${incident.id}.affected references missing component route: ${route}`);
        } else if (incident.affected.component_id != null) {
          if (!componentIds.has(incident.affected.component_id)) fail(`incident ${incident.id}.affected references missing component_id: ${incident.affected.component_id}`);
        } else {
          warn(`incident ${incident.id}.affected.component_id is recommended so affected UI can link to an exact component`);
        }
        if (incident.affected.components != null) {
          if (!Array.isArray(incident.affected.components)) {
            fail(`incident ${incident.id}.affected.components must be an array when present`);
          } else {
            incident.affected.components.forEach((componentRef, componentRefIndex) => {
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
        if (incident.affected.window != null) {
          if (!isObject(incident.affected.window)) {
            fail(`incident ${incident.id}.affected.window must be an object when present`);
          } else {
            if (incident.affected.window.start_label != null) localized(incident.affected.window.start_label, `incident ${incident.id}.affected.window.start_label`);
            if (incident.affected.window.end_label != null) localized(incident.affected.window.end_label, `incident ${incident.id}.affected.window.end_label`);
          }
        }
      }
    }
    if (incident.affected?.segments && Array.isArray(incident.affected.segments)) {
      const total = incident.affected.segments.reduce((sum, segment) => sum + (isObject(segment) ? Number(segment.percent || 0) : 0), 0);
      if (Math.abs(total - 100) > 0.01) fail(`incident ${incident.id} affected segment percent total is ${total}, expected 100`);
      incident.affected.segments.forEach((segment, segmentIndex) => {
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
  });
} else {
  fail("incidents must be an array, even when it is empty");
}

for (const incidentId of referencedIncidents) {
  if (!incidentIds.has(incidentId)) fail(`day references missing incident_id: ${incidentId}`);
}

if (errors.length) {
  console.error(`Status feed validation failed: ${file}`);
  errors.forEach((message) => console.error(`- ${message}`));
  if (warnings.length) {
    console.error("Warnings:");
    warnings.forEach((message) => console.error(`- ${message}`));
  }
  process.exit(1);
}

console.log(`Status feed validation passed: ${file}`);
console.log(`categories=${feed.categories?.length || 0} components=${componentIds.size} incidents=${incidentIds.size} states=${knownStates.size}`);
if (warnings.length) {
  console.log("Warnings:");
  warnings.forEach((message) => console.log(`- ${message}`));
}
