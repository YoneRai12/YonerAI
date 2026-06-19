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

function redactLocalPaths(value) {
  return String(value || "")
    .replaceAll(tempDir, "<tmp>")
    .replaceAll(statusRoot, "<status-root>");
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

const feed = {
  schema_version: "yonerai.status.feed.v1",
  generated_at: "2026-01-01T00:00:00.000Z",
  locale_default: "ja",
  range: { days: 1, start: "2026-01-01", end: "2026-01-01" },
  meta: {
    accessToken: "redacted-value-a",
    refreshToken: "redacted-value-b",
    authToken: "redacted-value-c",
    secretAccessKey: "redacted-value-d",
    authorizationHeader: "redacted-value-e",
    setCookie: "redacted-value-f",
    sessionId: "redacted-value-g",
    api__key: "redacted-value-h",
    "api-_key": "redacted-value-i",
    "private key": "redacted-value-j"
  },
  states: [],
  categories: [],
  incidents: []
};

try {
  fs.writeFileSync(feedPath, `${JSON.stringify(feed, null, 2)}\n`);

  const result = spawnSync(process.execPath, [validator, feedPath], {
    cwd: statusRoot,
    encoding: "utf8"
  });

  if (result.status === 0) {
    assert.fail(
      [
        "camelCase and mixed-separator secret metadata must be rejected",
        `stdout: ${redactLocalPaths(result.stdout)}`,
        `stderr: ${redactLocalPaths(result.stderr)}`
      ].join("\n")
    );
  }

  for (const key of Object.keys(feed.meta)) {
    assert.match(result.stderr, new RegExp(`\\$\\.meta\\.${escapeRegExp(key)}: sensitive-key`));
  }
} finally {
  fs.rmSync(tempDir, { recursive: true, force: true });
}

console.log("Status public feed safety camelCase secret regression passed.");
