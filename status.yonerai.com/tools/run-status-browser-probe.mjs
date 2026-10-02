#!/usr/bin/env node

/*
 * Optional real-browser probe runner for YonerAI Status.
 *
 * This starts a static server when --url is omitted, opens the status page in
 * Chromium via Playwright, injects status-runtime-browser-probe.js, and writes
 * the probe report to generated/status-browser-probe-report.json.
 *
 * It is intentionally not part of the default static contract suite because
 * CI environments may not have Playwright or a browser installed.
 */

import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const statusRoot = path.resolve(scriptDir, "..");

const viewportPresets = {
  mobile: { width: 390, height: 844, isMobile: true, hasTouch: true },
  desktop: { width: 1440, height: 1000, isMobile: false, hasTouch: false },
  scaled: { width: 1920, height: 1600, isMobile: false, hasTouch: false }
};

function usage() {
  console.log(`Usage:
  node status.yonerai.com/tools/run-status-browser-probe.mjs [--url http://127.0.0.1:5500/] [--viewport mobile|desktop|scaled]
  node tools/run-status-browser-probe.mjs [--root generated/public-package] [--viewport mobile|desktop|scaled]

Options:
  --url <url>       Use an already running page.
  --root <dir>      Static root when --url is omitted. Default: status.yonerai.com root.
  --viewport <name> mobile, desktop, or scaled. Default: desktop.
  --headed          Run browser headed.
  --timeout <ms>    Runtime wait timeout. Default: 10000.
  --out <file>      Report output. Default: generated/status-browser-probe-report.json

Requires Playwright to be installed in the current Node environment.
`);
}

function parseArgs(argv) {
  const options = {
    url: null,
    root: statusRoot,
    viewport: "desktop",
    headed: false,
    timeout: 10000,
    out: path.resolve(statusRoot, "generated/status-browser-probe-report.json")
  };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--help" || arg === "-h") options.help = true;
    else if (arg === "--url") options.url = argv[++index];
    else if (arg === "--root") options.root = resolvePath(argv[++index]);
    else if (arg === "--viewport") options.viewport = argv[++index];
    else if (arg === "--headed") options.headed = true;
    else if (arg === "--timeout") options.timeout = Number(argv[++index]);
    else if (arg === "--out") options.out = resolvePath(argv[++index]);
    else throw new Error(`unknown argument: ${arg}`);
  }
  return options;
}

function resolvePath(value) {
  if (path.isAbsolute(value)) return value;
  const cwdPath = path.resolve(process.cwd(), value);
  if (fs.existsSync(cwdPath)) return cwdPath;
  return path.resolve(statusRoot, value);
}

function contentType(file) {
  if (file.endsWith(".html")) return "text/html; charset=utf-8";
  if (file.endsWith(".css")) return "text/css; charset=utf-8";
  if (file.endsWith(".js")) return "text/javascript; charset=utf-8";
  if (file.endsWith(".json")) return "application/json; charset=utf-8";
  if (file.endsWith(".svg")) return "image/svg+xml";
  return "application/octet-stream";
}

function safeJoin(root, urlPath) {
  const pathname = decodeURIComponent(new URL(urlPath, "http://local").pathname);
  const target = path.resolve(root, pathname === "/" ? "index.html" : pathname.slice(1));
  const relative = path.relative(root, target);
  if (relative.startsWith("..") || path.isAbsolute(relative)) return null;
  return target;
}

function startStaticServer(root) {
  const server = http.createServer((request, response) => {
    const target = safeJoin(root, request.url || "/");
    if (!target || !fs.existsSync(target) || fs.statSync(target).isDirectory()) {
      response.writeHead(404, { "content-type": "text/plain; charset=utf-8" });
      response.end("Not found");
      return;
    }
    response.writeHead(200, {
      "content-type": contentType(target),
      "cache-control": "no-store"
    });
    fs.createReadStream(target).pipe(response);
  });
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      resolve({
        server,
        url: `http://127.0.0.1:${address.port}/`
      });
    });
  });
}

async function loadPlaywright() {
  try {
    return await import("playwright");
  } catch (error) {
    throw new Error(`Playwright is required for browser probe runner: ${error.message}`);
  }
}

function writeReport(file, report) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, `${JSON.stringify(report, null, 2)}\n`, "utf8");
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

if (!viewportPresets[options.viewport]) {
  console.error(`unknown viewport preset: ${options.viewport}`);
  usage();
  process.exit(1);
}

let staticServer = null;
let browser = null;

try {
  const target = options.url ? { url: options.url } : await startStaticServer(options.root);
  staticServer = target.server || null;
  const { chromium } = await loadPlaywright();
  browser = await chromium.launch({ headless: !options.headed });
  const viewport = viewportPresets[options.viewport];
  const context = await browser.newContext({
    viewport: { width: viewport.width, height: viewport.height },
    isMobile: viewport.isMobile,
    hasTouch: viewport.hasTouch
  });
  const page = await context.newPage();
  await page.goto(target.url, { waitUntil: "domcontentloaded", timeout: options.timeout });
  await page.waitForFunction(() => window.YonerAIStatusRuntime || window.YonerAIStatus, null, { timeout: options.timeout });
  await page.addScriptTag({ url: pathToFileURL(path.resolve(statusRoot, "tools/status-runtime-browser-probe.js")).href });
  const report = await page.evaluate(() => window.YonerAIStatusProbe.run());
  report.viewport = options.viewport;
  report.probe_url = target.url;
  writeReport(options.out, report);
  console.log(`Status browser probe report: ${path.relative(statusRoot, options.out).replaceAll("\\", "/")}`);
  if (!report.ok) {
    console.error("Status browser probe failed.");
    console.error(JSON.stringify(report.failed, null, 2));
    process.exitCode = 1;
  }
} catch (error) {
  const report = {
    schema_version: "yonerai.status.browser-probe.report.v1",
    generated_at: new Date().toISOString(),
    ok: false,
    error: String(error?.message || error),
    viewport: options.viewport
  };
  writeReport(options.out, report);
  console.error(`Status browser probe runner failed. Report: ${path.relative(statusRoot, options.out).replaceAll("\\", "/")}`);
  console.error(error.message);
  process.exitCode = 1;
} finally {
  if (browser) await browser.close();
  if (staticServer) staticServer.close();
}
