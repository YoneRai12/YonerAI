#!/usr/bin/env node

/*
 * Static readiness audit for the active YonerAI Status goal.
 *
 * This does not prove visual/browser completion by itself. It records which
 * goal requirements have static artifacts, which have generated reports, and
 * which still require real browser/runtime evidence.
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const statusRoot = path.resolve(scriptDir, "..");

const requirements = [
  {
    id: "uiux-perfect-preserved",
    objective: "UIUX完璧版を壊さず維持する",
    staticEvidence: [
      "STATUS_UIUX_REGRESSION_CONTRACT.md",
      "status-uiux-regression.contract.json",
      "tools/validate-status-uiux-regression.mjs",
      "tools/status-runtime-browser-probe.js",
      "tools/run-status-browser-probe.mjs"
    ],
    runtimeEvidence: [
      "generated/status-browser-probe-report.json",
      "manual viewport confirmation for desktop/mobile/scaled"
    ],
    completionRule: "Static contract plus real browser probe/manual viewport checks must pass."
  },
  {
    id: "runtime-feed-api-stable",
    objective: "runtime feed APIを安定化する",
    staticEvidence: [
      "STATUS_RUNTIME_FEED_API.md",
      "status-runtime-api.contract.json",
      "tools/validate-status-runtime-contract.mjs"
    ],
    runtimeEvidence: [
      "browser runtime getState/getFeed evidence",
      "generated/status-browser-probe-report.json"
    ],
    completionRule: "Contract exists and browser runtime exposes documented globals/methods."
  },
  {
    id: "schema-example-docs-adapter-aligned",
    objective: "JSON schema / example / docs / adapterを一致させる",
    staticEvidence: [
      "status-healthcheck.schema.json",
      "status-monitor.schema.json",
      "status-source.schema.json",
      "status-feed.schema.json",
      "status-aws-metrics.schema.json",
      "status-yonerai-health.schema.json",
      "STATUS_JSON_TEMPLATES_FOR_INTEGRATION.md",
      "STATUS_INTEGRATION_MANIFEST.md",
      "tools/validate-status-contract-suite.mjs"
    ],
    runtimeEvidence: [
      "generated/status-contract-suite-report.json"
    ],
    completionRule: "Contract suite must pass and generated report must show ok=true."
  },
  {
    id: "feed-driven-no-dom-direct-write",
    objective: "直書き表示をfeed駆動に置き換える",
    staticEvidence: [
      "status-integration.manifest.json",
      "STATUS_OPERATIONS_RUNBOOK.md",
      "tools/sync-status-public-feed.mjs",
      "tools/promote-status-public-feed.mjs",
      "tools/build-status-public-package.mjs"
    ],
    runtimeEvidence: [
      "actual status-feed.json update evidence",
      "browser runtime feed update evidence"
    ],
    completionRule: "Operational update path must update UI through feed/runtime only."
  },
  {
    id: "aws-yonerai-healthcheck-bridge",
    objective: "AWS / YonerAI API / healthcheck からfeed化できるbridgeを作る",
    staticEvidence: [
      "tools/fill-status-aws-metrics.mjs",
      "tools/fill-status-yonerai-health.mjs",
      "tools/status-healthcheck-bridge.example.mjs",
      "tools/status-feed-bridge.example.mjs",
      "tools/build-status-pipeline.mjs",
      "status-aws-metrics.example.json",
      "status-yonerai-health.example.json"
    ],
    runtimeEvidence: [
      "generated pipeline reports for AWS/YonerAI/healthcheck examples",
      "generated status-feed.json from each path"
    ],
    completionRule: "Each input path must generate a validated and public-safe feed."
  },
  {
    id: "hover-touch-animation-selected-regression",
    objective: "hover / touch / animation / selected state の回帰を潰す",
    staticEvidence: [
      "status-uiux-regression.contract.json",
      "STATUS_UIUX_REGRESSION_CONTRACT.md",
      "tools/run-status-browser-probe.mjs"
    ],
    runtimeEvidence: [
      "desktop browser probe report",
      "mobile browser probe report",
      "scaled desktop browser probe report",
      "manual hover/touch/cascade/disclosure confirmation"
    ],
    completionRule: "Real browser evidence is required; static artifacts alone are insufficient."
  },
  {
    id: "public-safety-and-package-boundary",
    objective: "Cloudflare/static公開時にprivate/generated/internal情報を出さない",
    staticEvidence: [
      "tools/validate-status-public-feed-safety.mjs",
      "tools/build-status-public-package.mjs",
      "STATUS_PREPUBLISH_CHECKS.md",
      "STATUS_OPERATIONS_RUNBOOK.md"
    ],
    runtimeEvidence: [
      "generated public package manifest",
      "public feed safety report or passing command output"
    ],
    completionRule: "Public package must contain only public runtime files and a public-safe feed."
  }
];

function usage() {
  console.log(`Usage:
  node status.yonerai.com/tools/audit-status-goal-readiness.mjs [--out generated/status-goal-readiness-audit.json]
  node tools/audit-status-goal-readiness.mjs [--out generated/status-goal-readiness-audit.json]

This is a readiness audit, not a browser validation replacement.
`);
}

function resolveOutput(value) {
  if (path.isAbsolute(value)) return value;
  return value.replaceAll("\\", "/").startsWith("status.yonerai.com/")
    ? path.resolve(process.cwd(), value)
    : path.resolve(statusRoot, value);
}

function parseArgs(argv) {
  const options = {
    out: path.resolve(statusRoot, "generated/status-goal-readiness-audit.json")
  };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--help" || arg === "-h") options.help = true;
    else if (arg === "--out") options.out = resolveOutput(argv[++index]);
    else throw new Error(`unknown argument: ${arg}`);
  }
  return options;
}

function exists(relativePath) {
  return fs.existsSync(path.resolve(statusRoot, relativePath));
}

function readJsonIfExists(relativePath) {
  const file = path.resolve(statusRoot, relativePath);
  if (!fs.existsSync(file)) return null;
  try {
    return JSON.parse(fs.readFileSync(file, "utf8"));
  } catch {
    return null;
  }
}

function evidenceStatus(requirement) {
  const staticItems = requirement.staticEvidence.map((item) => ({
    path: item,
    exists: exists(item)
  }));
  const missingStatic = staticItems.filter((item) => !item.exists).map((item) => item.path);
  return {
    staticItems,
    missingStatic,
    staticReady: missingStatic.length === 0
  };
}

function generatedEvidence() {
  const contractSuite = readJsonIfExists("generated/status-contract-suite-report.json");
  const browserProbe = readJsonIfExists("generated/status-browser-probe-report.json");
  const publicPackageManifest = readJsonIfExists("generated/public-package/package-manifest.json");
  return {
    contractSuite: contractSuite ? {
      exists: true,
      ok: Boolean(contractSuite.ok),
      generated_at: contractSuite.generated_at || null
    } : { exists: false },
    browserProbe: browserProbe ? {
      exists: true,
      ok: Boolean(browserProbe.ok),
      generated_at: browserProbe.generated_at || null,
      viewport: browserProbe.viewport || null
    } : { exists: false },
    publicPackageManifest: publicPackageManifest ? {
      exists: true,
      files: publicPackageManifest.files || []
    } : { exists: false }
  };
}

function classify(requirement, evidence, generated) {
  if (!evidence.staticReady) return "incomplete-static-artifacts";
  if (requirement.id === "schema-example-docs-adapter-aligned" && generated.contractSuite.ok) return "runtime-evidence-present";
  if ((requirement.id === "uiux-perfect-preserved" || requirement.id === "hover-touch-animation-selected-regression") && generated.browserProbe.ok) {
    return "partial-browser-evidence-present";
  }
  if (requirement.id === "public-safety-and-package-boundary" && generated.publicPackageManifest.exists) return "package-evidence-present";
  if (requirement.runtimeEvidence.length > 0) return "needs-runtime-evidence";
  return "static-ready";
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

const generated = generatedEvidence();
const audited = requirements.map((requirement) => {
  const evidence = evidenceStatus(requirement);
  return {
    ...requirement,
    ...evidence,
    status: classify(requirement, evidence, generated)
  };
});

const completeStatuses = new Set(["runtime-evidence-present", "package-evidence-present"]);
const report = {
  schema_version: "yonerai.status.goal-readiness-audit.v1",
  generated_at: new Date().toISOString(),
  status_root: statusRoot,
  complete: audited.every((item) => completeStatuses.has(item.status)),
  generatedEvidence: generated,
  requirements: audited,
  note: "This audit is intentionally conservative. Browser/manual UI evidence is still required before marking the goal complete."
};

fs.mkdirSync(path.dirname(options.out), { recursive: true });
fs.writeFileSync(options.out, `${JSON.stringify(report, null, 2)}\n`, "utf8");

console.log(`Status goal readiness audit written: ${path.relative(statusRoot, options.out).replaceAll("\\", "/")}`);
console.log(`complete=${report.complete}`);
if (!report.complete) {
  const open = audited.filter((item) => !completeStatuses.has(item.status));
  console.log(`open_requirements=${open.length}`);
}
