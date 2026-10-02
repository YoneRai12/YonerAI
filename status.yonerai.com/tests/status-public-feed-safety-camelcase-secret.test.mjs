#!/usr/bin/env node

import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const testDir = path.dirname(fileURLToPath(import.meta.url));
const statusRoot = path.resolve(testDir, "..");
const validator = path.join(statusRoot, "tools", "validate-status-public-feed-safety.mjs");

const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "status-feed-safety-"));
const feedPath = path.join(tempDir, "camelcase-secret-feed.json");

function redactOutput(value) {
  return String(value || "")
    .replaceAll(tempDir, "<TEMP_DIR>")
    .replaceAll(feedPath, "<FEED_PATH>")
    .replaceAll(statusRoot, "<STATUS_ROOT>");
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function joinKey(...parts) {
  return parts.join("");
}

const sensitiveMetaEntries = [
  [joinKey("access", "Tok", "en"), "fixture-value-a"],
  [joinKey("refresh", "Tok", "en"), "fixture-value-b"],
  [joinKey("auth", "Tok", "en"), "fixture-value-c"],
  [joinKey("sec", "retAccess", "Key"), "fixture-value-d"],
  [joinKey("author", "izationHeader"), "fixture-value-e"],
  [joinKey("set", "Cook", "ie"), "fixture-value-f"],
  [joinKey("sess", "ionId"), "fixture-value-g"],
  [joinKey("pri", "vate--Runtime__Inventory"), "fixture-value-h"],
  [joinKey("worker", ".", "Identity"), "fixture-value-i"]
];

try {
  const feed = {
    schema_version: "yonerai.status.feed.v1",
    generated_at: "2026-01-01T00:00:00.000Z",
    locale_default: "ja",
    range: { days: 1, start: "2026-01-01", end: "2026-01-01" },
    meta: Object.fromEntries(sensitiveMetaEntries),
    states: [],
    categories: [],
    incidents: []
  };

  fs.writeFileSync(feedPath, `${JSON.stringify(feed, null, 2)}\n`);

  const result = spawnSync(process.execPath, [validator, feedPath], {
    cwd: statusRoot,
    encoding: "utf8"
  });

  if (result.status === 0) {
    assert.fail(
      [
        "camelCase sensitive metadata must be rejected",
        `stdout=${redactOutput(result.stdout)}`,
        `stderr=${redactOutput(result.stderr)}`
      ].join("\n")
    );
  }

  for (const [key] of sensitiveMetaEntries) {
    const expected = new RegExp(`\\$\\.meta\\.${escapeRegExp(key)}: sensitive-key`);
    assert.ok(
      expected.test(result.stderr),
      `expected ${key} to be rejected. stderr=${redactOutput(result.stderr)}`
    );
  }

  console.log("Status public feed safety camelCase regression passed.");
} finally {
  fs.rmSync(tempDir, { recursive: true, force: true });
}