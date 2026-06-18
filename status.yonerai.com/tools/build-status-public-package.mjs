#!/usr/bin/env node

/*
 * Build a public-only package for status.yonerai.com hosting.
 *
 * This copies only browser/runtime-safe files into an output directory. It is
 * intended for Cloudflare Pages/static hosting handoff, not for internal
 * pipeline storage. Healthcheck inputs, monitor/source inputs, reports,
 * backups, tokens, and private generated files are intentionally excluded.
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const statusRoot = path.resolve(scriptDir, "..");

const requiredRuntimeFiles = [
  "index.html",
  "jp/index.html",
  "en/index.html",
  "styles.css",
  "runtime-status.css",
  "mock-status-adapter.js"
];

const optionalPublicFiles = [
  "status-runtime-api.contract.json",
  "status-uiux-regression.contract.json"
];

function usage() {
  console.log(`Usage:
  node status.yonerai.com/tools/build-status-public-package.mjs [--feed status-feed.json] [--out generated/public-package]
  node tools/build-status-public-package.mjs [--feed status-feed.json] [--out generated/public-package]

Options:
  --feed <file>  final public feed to copy as status-feed.json
  --out <dir>    output package directory

Behavior:
  - validates feed schema
  - validates public feed safety
  - copies only public runtime files
  - writes package-manifest.json
`);
}

function parseArgs(argv) {
  const options = {
    feed: "status-feed.json",
    out: "generated/public-package"
  };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--help" || arg === "-h") options.help = true;
    else if (arg === "--feed") options.feed = argv[++index];
    else if (arg === "--out") options.out = argv[++index];
    else throw new Error(`unknown argument: ${arg}`);
  }
  return options;
}

function resolveInput(value) {
  if (path.isAbsolute(value)) return value;
  const cwdPath = path.resolve(process.cwd(), value);
  const statusPath = path.resolve(statusRoot, value);
  if (fs.existsSync(cwdPath)) return cwdPath;
  if (fs.existsSync(statusPath)) return statusPath;
  return value.replaceAll("\\", "/").startsWith("status.yonerai.com/") ? cwdPath : statusPath;
}

function resolveOutput(value) {
  if (path.isAbsolute(value)) return value;
  return value.replaceAll("\\", "/").startsWith("status.yonerai.com/")
    ? path.resolve(process.cwd(), value)
    : path.resolve(statusRoot, value);
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

function copyFile(source, destination) {
  if (!fs.existsSync(source)) throw new Error(`required public file does not exist: ${source}`);
  fs.mkdirSync(path.dirname(destination), { recursive: true });
  fs.copyFileSync(source, destination);
}

function cleanOutputDir(outDir) {
  const resolved = path.resolve(outDir);
  const relative = path.relative(statusRoot, resolved).replaceAll("\\", "/");
  if (!relative || relative.startsWith("..") || path.isAbsolute(relative) || !relative.startsWith("generated/")) {
    throw new Error(`output directory must stay inside status generated/ directory: ${outDir}`);
  }
  fs.rmSync(resolved, { recursive: true, force: true });
  fs.mkdirSync(resolved, { recursive: true });
}

function buildPackage(feedPath, outDir) {
  if (!fs.existsSync(feedPath)) throw new Error(`feed file does not exist: ${feedPath}`);
  runValidator("tools/validate-status-feed.mjs", feedPath, "feed schema");
  runValidator("tools/validate-status-public-feed-safety.mjs", feedPath, "public feed safety");

  cleanOutputDir(outDir);
  const copied = [];

  for (const file of requiredRuntimeFiles) {
    const source = path.resolve(statusRoot, file);
    const destination = path.resolve(outDir, file);
    copyFile(source, destination);
    copied.push(file);
  }

  copyFile(feedPath, path.resolve(outDir, "status-feed.json"));
  copied.push("status-feed.json");

  for (const file of optionalPublicFiles) {
    const source = path.resolve(statusRoot, file);
    if (!fs.existsSync(source)) continue;
    const destination = path.resolve(outDir, file);
    copyFile(source, destination);
    copied.push(file);
  }

  const manifest = {
    schema_version: "yonerai.status.public-package-manifest.v1",
    generated_at: new Date().toISOString(),
    source_root: statusRoot,
    feed_source: toStatusRelative(feedPath),
    files: copied,
    excluded_by_design: [
      "status-healthcheck-input*.json",
      "status-monitor-results*.json",
      "status-feed.source*.json",
      "status-aws-metrics*.json",
      "status-yonerai-health*.json",
      "generated/**/status-feed.pipeline-report.json",
      "generated/public-feed-backups/**",
      "tools/**"
    ]
  };
  fs.writeFileSync(path.resolve(outDir, "package-manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
  copied.push("package-manifest.json");
  return { outDir, copied };
}

let options;
try {
  options = parseArgs(process.argv.slice(2));
} catch (error) {
  console.error(error.message);
  usage();
  process.exit(1);
}

if (options.help) {
  usage();
  process.exit(0);
}

try {
  const feedPath = resolveInput(options.feed);
  const outDir = resolveOutput(options.out);
  const result = buildPackage(feedPath, outDir);
  console.log(`Built public status package: ${toStatusRelative(result.outDir)}`);
  console.log(`files=${result.copied.length}`);
} catch (error) {
  console.error("Failed to build public status package.");
  console.error(error.message);
  process.exit(1);
}
