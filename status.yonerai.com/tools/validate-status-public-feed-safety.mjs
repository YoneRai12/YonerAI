#!/usr/bin/env node

/*
 * Public safety scan for yonerai.status.feed.v1.
 *
 * Healthcheck inputs may contain private connection details, but final public
 * browser feeds must not contain secrets, bearer tokens, local/private
 * endpoints, or private runtime inventory strings.
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const statusRoot = path.resolve(scriptDir, "..");

const sensitiveKeyPattern = /(^|[_-])(token|secret|password|passwd|authorization|auth_header|api[_-]?key|access[_-]?key|private[_-]?key|credential|session|cookie|account[_-]?id|account[_-]?detail|arn|hostname|host[_-]?name|internal[_-]?host|worker[_-]?(identity|pc)|pc[_-]?identity|run[_-]?contents|conversation|prompt|output|audit[_-]?detail|runtime[_-]?inventory|private[_-]?runtime)([_-]|$)/i;
const sensitiveValuePatterns = [
  { name: "bearer-token", pattern: /\bBearer\s+[A-Za-z0-9._~+/-]+=*/i },
  { name: "aws-access-key", pattern: /\bAKIA[0-9A-Z]{16}\b/ },
  { name: "aws-arn", pattern: /\barn:aws:[A-Za-z0-9_:/.-]+\b/i },
  { name: "aws-secret-like", pattern: /\baws_secret_access_key\b/i },
  { name: "openai-key", pattern: /\bsk-[A-Za-z0-9_-]{20,}\b/ },
  { name: "jwt-like", pattern: /\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b/ },
  { name: "localhost-url", pattern: /\bhttps?:\/\/(?:localhost|127\.0\.0\.1|0\.0\.0\.0)(?::\d+)?\b/i },
  { name: "private-ip-url", pattern: /\bhttps?:\/\/(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3})(?::\d+)?\b/i },
  { name: "local-domain", pattern: /\bhttps?:\/\/[^/\s"]+\.local(?:[:/]|$)/i },
  { name: "file-url", pattern: /\bfile:\/\/[^\s"']+/i },
  { name: "windows-local-path", pattern: /\b[A-Z]:\\(?:Users|ProgramData|Windows|Temp|ORA|YonerAI)[^"'\n\r]*/i },
  { name: "unix-private-path", pattern: /(?:^|[\s"'])(?:\/home\/|\/root\/|\/var\/log\/|\/etc\/)[^\s"']*/i },
  { name: "internal-hostname", pattern: /\b(?:ip-\d+-\d+-\d+-\d+|[a-z0-9-]+\.(?:internal|corp|lan))(?:[.\s:/]|$)/i },
  { name: "private-runtime-word", pattern: /\b(private runtime inventory|break-glass|raw production inventory)\b/i }
];

function usage() {
  console.log(`Usage:
  node status.yonerai.com/tools/validate-status-public-feed-safety.mjs [feed.json...]
  node tools/validate-status-public-feed-safety.mjs [feed.json...]

Default feed:
  status-feed.example.json
`);
}

function parseArgs(argv) {
  const options = { files: [] };
  for (const arg of argv) {
    if (arg === "--help" || arg === "-h") options.help = true;
    else options.files.push(arg);
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

function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function scan(value, pathLabel, findings) {
  if (Array.isArray(value)) {
    value.forEach((item, index) => scan(item, `${pathLabel}[${index}]`, findings));
    return;
  }
  if (isObject(value)) {
    for (const [key, item] of Object.entries(value)) {
      const nextPath = `${pathLabel}.${key}`;
      if (sensitiveKeyPattern.test(key)) {
        findings.push({ path: nextPath, kind: "sensitive-key", detail: key });
      }
      scan(item, nextPath, findings);
    }
    return;
  }
  if (typeof value !== "string") return;
  for (const rule of sensitiveValuePatterns) {
    if (rule.pattern.test(value)) {
      findings.push({
        path: pathLabel,
        kind: rule.name,
        detail: value.length > 120 ? `${value.slice(0, 117)}...` : value
      });
    }
  }
}

function validateFile(file) {
  const input = JSON.parse(fs.readFileSync(file, "utf8"));
  const findings = [];
  if (!isObject(input)) {
    findings.push({ path: "$", kind: "shape", detail: "feed root must be an object" });
  } else if (input.schema_version !== "yonerai.status.feed.v1") {
    findings.push({
      path: "$.schema_version",
      kind: "schema",
      detail: `expected yonerai.status.feed.v1, got ${String(input.schema_version)}`
    });
  }
  scan(input, "$", findings);
  return findings;
}

const options = parseArgs(process.argv.slice(2));
if (options.help) {
  usage();
  process.exit(0);
}

const files = (options.files.length ? options.files : ["status-feed.example.json"]).map(resolveInput);
const allFindings = [];

for (const file of files) {
  try {
    const findings = validateFile(file);
    findings.forEach((finding) => allFindings.push({
      file: path.relative(statusRoot, file).replaceAll("\\", "/"),
      ...finding
    }));
  } catch (error) {
    allFindings.push({
      file: path.relative(statusRoot, file).replaceAll("\\", "/"),
      path: "$",
      kind: "read-error",
      detail: String(error?.message || error)
    });
  }
}

if (allFindings.length) {
  console.error("Status public feed safety validation failed.");
  for (const finding of allFindings) {
    console.error(`- ${finding.file} ${finding.path}: ${finding.kind} (${finding.detail})`);
  }
  process.exit(1);
}

console.log(`Status public feed safety validated: ${files.map((file) => path.relative(statusRoot, file).replaceAll("\\", "/")).join(", ")}`);
