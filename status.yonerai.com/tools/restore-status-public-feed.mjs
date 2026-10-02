#!/usr/bin/env node

/*
 * Restore a public YonerAI Status feed from a validated backup.
 *
 * The backup must pass the same public feed checks as normal promotion before
 * it replaces the current public feed. This is intended as the feed-only
 * rollback path after a bad generated feed promotion.
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const statusRoot = path.resolve(scriptDir, "..");

function usage() {
  console.log(`Usage:
  node status.yonerai.com/tools/restore-status-public-feed.mjs [backup-feed.json] [public-feed.json]
  node tools/restore-status-public-feed.mjs [backup-feed.json] [public-feed.json]

Default backup:
  latest file under generated/public-feed-backups/

Default public feed:
  status-feed.json

Behavior:
  - backup feed must pass validate-status-feed.mjs
  - backup feed must pass validate-status-public-feed-safety.mjs
  - current public feed is copied to generated/public-feed-backups/ before restore
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

function resolveInput(value) {
  if (value) {
    if (path.isAbsolute(value)) return value;
    const cwdPath = path.resolve(process.cwd(), value);
    const statusPath = path.resolve(statusRoot, value);
    if (fs.existsSync(cwdPath)) return cwdPath;
    if (fs.existsSync(statusPath)) return statusPath;
    return value.replaceAll("\\", "/").startsWith("status.yonerai.com/") ? cwdPath : statusPath;
  }
  const backupDir = path.resolve(statusRoot, "generated/public-feed-backups");
  if (!fs.existsSync(backupDir)) throw new Error(`backup directory does not exist: ${backupDir}`);
  const backups = fs.readdirSync(backupDir)
    .filter((name) => name.endsWith(".bak"))
    .map((name) => path.resolve(backupDir, name))
    .sort((left, right) => fs.statSync(right).mtimeMs - fs.statSync(left).mtimeMs);
  if (!backups.length) throw new Error(`no public feed backups found in ${backupDir}`);
  return backups[0];
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
  const backupName = `${path.basename(publicFeedPath)}.pre-restore-${timestamp()}.bak`;
  const backupPath = path.resolve(backupDir, backupName);
  fs.copyFileSync(publicFeedPath, backupPath);
  return backupPath;
}

function restore(backupFeedPath, publicFeedPath) {
  if (!fs.existsSync(backupFeedPath)) {
    throw new Error(`backup feed does not exist: ${backupFeedPath}`);
  }
  fs.mkdirSync(path.dirname(publicFeedPath), { recursive: true });
  runValidator("tools/validate-status-feed.mjs", backupFeedPath, "backup feed schema");
  runValidator("tools/validate-status-public-feed-safety.mjs", backupFeedPath, "backup public feed safety");

  const currentBackupPath = backupExisting(publicFeedPath);
  const pendingPath = `${publicFeedPath}.restore-pending-${process.pid}`;
  fs.copyFileSync(backupFeedPath, pendingPath);
  fs.renameSync(pendingPath, publicFeedPath);
  return {
    backupFeed: backupFeedPath,
    publicFeed: publicFeedPath,
    currentBackup: currentBackupPath,
  };
}

const options = parseArgs(process.argv.slice(2));
if (options.help) {
  usage();
  process.exit(0);
}

try {
  const backupFeedPath = resolveInput(options.positionals[0]);
  const publicFeedPath = resolveOutput(options.positionals[1], "status-feed.json");
  const result = restore(backupFeedPath, publicFeedPath);
  console.log(`Restored public status feed: ${toStatusRelative(result.publicFeed)}`);
  console.log(`Backup source: ${toStatusRelative(result.backupFeed)}`);
  if (result.currentBackup) console.log(`Previous current feed backup: ${toStatusRelative(result.currentBackup)}`);
} catch (error) {
  console.error("Failed to restore public status feed.");
  console.error(error.message);
  process.exit(1);
}
