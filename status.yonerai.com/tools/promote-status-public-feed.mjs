#!/usr/bin/env node

/*
 * Safely promote a generated yonerai.status.feed.v1 file to a public feed path.
 *
 * This is the final file boundary before static hosting / Cloudflare serving.
 * It validates schema and public safety, writes through a temporary file, and
 * keeps a timestamped backup of the previous public feed when it exists.
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const statusRoot = path.resolve(scriptDir, "..");

function usage() {
  console.log(`Usage:
  node status.yonerai.com/tools/promote-status-public-feed.mjs [source-feed.json] [public-feed.json]
  node tools/promote-status-public-feed.mjs [source-feed.json] [public-feed.json]

Default source:
  generated/status-feed.live.json

Default public feed:
  status-feed.json

Behavior:
  - validate-status-feed.mjs must pass
  - validate-status-public-feed-safety.mjs must pass
  - previous public feed is copied to generated/public-feed-backups/
  - public feed is replaced via temporary file + rename
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

function resolveInput(value, fallback) {
  const chosen = value || fallback;
  if (path.isAbsolute(chosen)) return chosen;
  const cwdPath = path.resolve(process.cwd(), chosen);
  const statusPath = path.resolve(statusRoot, chosen);
  if (fs.existsSync(cwdPath)) return cwdPath;
  if (fs.existsSync(statusPath)) return statusPath;
  return chosen.replaceAll("\\", "/").startsWith("status.yonerai.com/") ? cwdPath : statusPath;
}

function resolveOutput(value, fallback) {
  const chosen = value || fallback;
  if (path.isAbsolute(chosen)) return chosen;
  return chosen.replaceAll("\\", "/").startsWith("status.yonerai.com/")
    ? path.resolve(process.cwd(), chosen)
    : path.resolve(statusRoot, chosen);
}

function toStatusRelative(file) {
  return path.relative(statusRoot, file).replaceAll("\\", "/");
}

function runValidator(script, file, label) {
  const result = spawnSync(process.execPath, [script, toStatusRelative(file)], {
    cwd: statusRoot,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  });
  if (result.status !== 0) {
    throw new Error([
      `${label} validation failed`,
      (result.stdout || "").trim(),
      (result.stderr || "").trim(),
    ].filter(Boolean).join("\n"));
  }
}

function timestamp() {
  return new Date().toISOString().replace(/[:.]/g, "-");
}

function backupExisting(publicFeedPath) {
  if (!fs.existsSync(publicFeedPath)) return null;
  const backupDir = path.resolve(statusRoot, "generated/public-feed-backups");
  fs.mkdirSync(backupDir, { recursive: true });
  const backupName = `${path.basename(publicFeedPath)}.${timestamp()}.bak`;
  const backupPath = path.resolve(backupDir, backupName);
  fs.copyFileSync(publicFeedPath, backupPath);
  return backupPath;
}

function promote(sourceFeedPath, publicFeedPath) {
  if (!fs.existsSync(sourceFeedPath)) {
    throw new Error(`source feed does not exist: ${sourceFeedPath}`);
  }
  fs.mkdirSync(path.dirname(publicFeedPath), { recursive: true });
  runValidator("tools/validate-status-feed.mjs", sourceFeedPath, "feed schema");
  runValidator("tools/validate-status-public-feed-safety.mjs", sourceFeedPath, "public feed safety");

  const backupPath = backupExisting(publicFeedPath);
  const pendingPath = `${publicFeedPath}.pending-${process.pid}`;
  fs.copyFileSync(sourceFeedPath, pendingPath);
  fs.renameSync(pendingPath, publicFeedPath);
  return {
    source: sourceFeedPath,
    publicFeed: publicFeedPath,
    backup: backupPath,
  };
}

const options = parseArgs(process.argv.slice(2));
if (options.help) {
  usage();
  process.exit(0);
}

const sourceFeedPath = resolveInput(options.positionals[0], "generated/status-feed.live.json");
const publicFeedPath = resolveOutput(options.positionals[1], "status-feed.json");

try {
  const result = promote(sourceFeedPath, publicFeedPath);
  console.log(`Promoted public status feed: ${toStatusRelative(result.publicFeed)}`);
  console.log(`Source: ${toStatusRelative(result.source)}`);
  if (result.backup) console.log(`Backup: ${toStatusRelative(result.backup)}`);
} catch (error) {
  console.error("Failed to promote public status feed.");
  console.error(error.message);
  process.exit(1);
}
