#!/usr/bin/env node

/*
 * Local same-origin development server for YonerAI Status.
 *
 * It serves the static status page plus:
 * - GET /status-feed.json
 * - GET /status-feed/events
 *
 * No production secrets, private inventory, or live monitoring data belong here.
 */

import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const statusRoot = path.resolve(__dirname, "..");
const port = Number(process.env.PORT || process.argv[2] || 5500);
const feedFile = path.resolve(process.env.STATUS_FEED_FILE || path.join(statusRoot, "status-feed.mock.json"));
const clients = new Set();

const contentTypes = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".md": "text/markdown; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".webp": "image/webp",
  ".ico": "image/x-icon",
};

function readFeed() {
  return JSON.parse(fs.readFileSync(feedFile, "utf8"));
}

function sendJson(response, value, status = 200) {
  response.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store",
    "x-content-type-options": "nosniff",
  });
  response.end(JSON.stringify(value));
}

function sendSse(response, event, value) {
  response.write(`event: ${event}\n`);
  response.write(`data: ${JSON.stringify(value)}\n\n`);
}

function staticPath(urlPath) {
  const cleanPath = decodeURIComponent(urlPath.split("?")[0]);
  const normalized = cleanPath === "/" ? "/index.html" : cleanPath;
  const full = path.resolve(statusRoot, `.${normalized}`);
  if (!full.startsWith(statusRoot)) return null;
  return full;
}

function serveStatic(request, response) {
  const full = staticPath(new URL(request.url, `http://${request.headers.host}`).pathname);
  if (!full) return sendJson(response, { error: "invalid_path" }, 400);
  fs.readFile(full, (error, data) => {
    if (error) {
      sendJson(response, { error: "not_found" }, 404);
      return;
    }
    response.writeHead(200, {
      "content-type": contentTypes[path.extname(full).toLowerCase()] || "application/octet-stream",
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
    });
    response.end(data);
  });
}

function handleEvents(request, response) {
  response.writeHead(200, {
    "content-type": "text/event-stream; charset=utf-8",
    "cache-control": "no-store",
    "connection": "keep-alive",
    "x-content-type-options": "nosniff",
  });
  clients.add(response);

  try {
    sendSse(response, "status-feed", readFeed());
  } catch (error) {
    sendSse(response, "status-feed-error", { message: error.message });
  }

  const ping = setInterval(() => {
    sendSse(response, "ping", { at: new Date().toISOString() });
  }, 25000);

  request.on("close", () => {
    clearInterval(ping);
    clients.delete(response);
  });
}

function broadcastFeed() {
  let feed;
  try {
    feed = readFeed();
  } catch (error) {
    for (const client of clients) sendSse(client, "status-feed-error", { message: error.message });
    return;
  }
  for (const client of clients) sendSse(client, "status-feed", feed);
}

const server = http.createServer((request, response) => {
  const url = new URL(request.url, `http://${request.headers.host}`);
  if (request.method !== "GET") {
    sendJson(response, { error: "method_not_allowed" }, 405);
    return;
  }
  if (url.pathname === "/status-feed.json") {
    try {
      sendJson(response, readFeed());
    } catch (error) {
      sendJson(response, { error: "feed_read_failed", message: error.message }, 500);
    }
    return;
  }
  if (url.pathname === "/status-feed/events") {
    handleEvents(request, response);
    return;
  }
  serveStatic(request, response);
});

fs.watch(feedFile, { persistent: false }, () => {
  windowlessDebounce(broadcastFeed, 120);
});

let debounceTimer = 0;
function windowlessDebounce(fn, delay) {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(fn, delay);
}

server.listen(port, "127.0.0.1", () => {
  console.log(`YonerAI Status dev server: http://127.0.0.1:${port}/?mockStatus=1&liveStatus=1`);
  console.log(`Feed file: ${feedFile}`);
});
