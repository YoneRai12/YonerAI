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

const feed = {
  schema_version: "yonerai.status.feed.v1",
  generated_at: "2026-01-01T00:00:00.000Z",
  locale_default: "ja",
  range: { days: 1, start: "2026-01-01", end: "2026-01-01" },
  meta: {
    accessToken: "redacted-access-token",
    refreshToken: "redacted-refresh-token",
    authToken: "redacted-auth-token",
    secretAccessKey: "redacted-secret-key",
    authorizationHeader: "redacted-authorization-header",
    setCookie: "redacted-cookie",
    sessionId: "redacted-session-id"
  },
  states: [],
  categories: [],
  incidents: []
};

fs.writeFileSync(feedPath, `${JSON.stringify(feed, null, 2)}\n`);

const result = spawnSync(process.execPath, [validator, feedPath], {
  cwd: statusRoot,
  encoding: "utf8"
});

assert.notEqual(result.status, 0, "camelCase secret metadata must be rejected");
for (const key of Object.keys(feed.meta)) {
  assert.match(result.stderr, new RegExp(`\\$\\.meta\\.${key}: sensitive-key`));
}

console.log("Status public feed safety camelCase secret regression passed.");
