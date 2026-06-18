#!/usr/bin/env node

/*
 * Browser acceptance harness for the feed-driven YonerAI Status runtime.
 *
 * This script is intentionally not run automatically by the page. It is a
 * manual gate for proving that the reusable runtime still works after UI,
 * feed, or adapter changes.
 */

const target = process.argv[2] || "http://localhost:5500/?mockStatus=1";
const checks = [];

function check(name, expression) {
  checks.push({ name, expression });
}

check("runtime api exists", () => Boolean(window.YonerAIStatusRuntime));
check("runtime version is exposed", () => typeof window.YonerAIStatusRuntime?.__version === "string");
check("runtime live api exists", () => (
  typeof window.YonerAIStatusRuntime?.connectEvents === "function" &&
  typeof window.YonerAIStatusRuntime?.disconnectEvents === "function"
));
check("feed is loaded", () => Boolean(window.YonerAIStatusRuntime?.getFeed?.()));
check("feed schema is v1", () => window.YonerAIStatusRuntime?.getFeed?.()?.schema_version === "yonerai.status.feed.v1");
check("categories rendered from feed", () => document.querySelectorAll("#categoryList .category").length > 0);
check("components rendered from feed", () => document.querySelectorAll("#categoryList .child").length > 0);
check("feed bars rendered", () => document.querySelectorAll(".bar[data-status-runtime='feed']").length > 0);
check("no duplicate runtime status panel", () => document.querySelectorAll("#barDetailPanel").length <= 1);
check("no duplicate incident detail panel", () => document.querySelectorAll("#incidentDetailPanel").length <= 1);
check("selected bars are single-owner", () => document.querySelectorAll(".bar.is-selected").length <= 1);
check("runtime css is loaded", () => Array.from(document.styleSheets).some((sheet) => String(sheet.href || "").includes("runtime-status.css")));
check("mock feed badge exists in mock mode", () => Boolean(document.querySelector(".mock-feed-badge")));

async function main() {
  let chromium;
  try {
    ({ chromium } = await import("playwright"));
  } catch {
    console.error("Playwright is required for this harness.");
    console.error("Install or run in an environment where the Browser/Playwright runtime is available.");
    process.exit(2);
  }

  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 960 } });
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });

  try {
    await page.goto(target, { waitUntil: "networkidle" });
    await page.waitForFunction(() => Boolean(window.YonerAIStatusRuntime?.getFeed?.()), null, { timeout: 5000 });

    const results = await page.evaluate((serializedChecks) => {
      const restored = serializedChecks.map(({ name, source }) => ({ name, fn: Function(`return (${source})`)() }));
      return restored.map(({ name, fn }) => {
        try {
          return { name, ok: Boolean(fn()) };
        } catch (error) {
          return { name, ok: false, error: error.message };
        }
      });
    }, checks.map(({ name, expression }) => ({ name, source: expression.toString() })));

    const failed = results.filter((result) => !result.ok);
    if (errors.length || failed.length) {
      console.error(`Status runtime acceptance failed: ${target}`);
      failed.forEach((result) => console.error(`- ${result.name}${result.error ? `: ${result.error}` : ""}`));
      errors.forEach((error) => console.error(`- console/page error: ${error}`));
      process.exitCode = 1;
      return;
    }

    await page.evaluate(() => {
      const feed = window.YonerAIStatusRuntime.getFeed();
      const category = feed.categories.find((item) => item.id === "status-bar-test") || feed.categories[0];
      const component = category.children[0];
      const day = component.days.find((item) => item.incident_id) || component.days[component.days.length - 1];
      window.location.hash = `status/${category.id}/${component.id}/${day.date}/${day.state}`;
    });
    await page.waitForSelector("#barDetailPanel.is-visible", { timeout: 5000 });

    const statusRouteOk = await page.evaluate(() => ({
      selected: document.querySelectorAll(".bar.is-selected").length,
      panels: document.querySelectorAll("#barDetailPanel").length,
      route: document.documentElement.dataset.statusRoute,
    }));
    if (statusRouteOk.selected !== 1 || statusRouteOk.panels !== 1 || statusRouteOk.route !== "status") {
      console.error("Status route acceptance failed");
      console.error(JSON.stringify(statusRouteOk, null, 2));
      process.exitCode = 1;
      return;
    }

    const feedReplacementApiOk = await page.evaluate(() => new Promise((resolve) => {
      const runtime = window.YonerAIStatusRuntime;
      const original = JSON.parse(JSON.stringify(runtime.getFeed()));
      const repeated = JSON.parse(JSON.stringify(original));
      repeated.generated_at = "acceptance-repeat-feed";

      const firstReturn = runtime.setFeed(repeated, { animate: false, source: "acceptance-repeat-1" });
      const secondReturn = runtime.setFeed(repeated, { animate: false, source: "acceptance-repeat-2" });

      const beforeInvalidGeneratedAt = runtime.getFeed()?.generated_at;
      document.dispatchEvent(new CustomEvent("yonerai-status:set-feed", {
        detail: { schema_version: "yonerai.status.feed.v1", categories: "invalid" },
      }));
      const afterInvalidGeneratedAt = runtime.getFeed()?.generated_at;

      const eventFeed = JSON.parse(JSON.stringify(runtime.getFeed()));
      eventFeed.generated_at = "acceptance-event-feed";
      document.addEventListener("yonerai-status-feed-applied", (event) => {
        window.setTimeout(() => {
          resolve({
            firstReturnGeneratedAt: firstReturn?.generated_at,
            secondReturnGeneratedAt: secondReturn?.generated_at,
            beforeInvalidGeneratedAt,
            afterInvalidGeneratedAt,
            eventSource: event.detail?.source,
            finalGeneratedAt: runtime.getFeed()?.generated_at,
            eventError: document.documentElement.dataset.statusFeedEventError || "",
            feedError: document.documentElement.dataset.statusFeedError || "",
            categoryCount: document.querySelectorAll("#categoryList .category").length,
            selected: document.querySelectorAll(".bar.is-selected").length,
            runtimePanels: document.querySelectorAll("#barDetailPanel").length,
            incidentPanels: document.querySelectorAll("#incidentDetailPanel").length,
          });
        }, 50);
      }, { once: true });
      document.dispatchEvent(new CustomEvent("yonerai-status:set-feed", {
        detail: {
          feed: eventFeed,
          options: { animate: false },
          source: "acceptance-event-feed",
        },
      }));
    }));

    if (
      feedReplacementApiOk.firstReturnGeneratedAt !== "acceptance-repeat-feed" ||
      feedReplacementApiOk.secondReturnGeneratedAt !== "acceptance-repeat-feed" ||
      feedReplacementApiOk.beforeInvalidGeneratedAt !== "acceptance-repeat-feed" ||
      feedReplacementApiOk.afterInvalidGeneratedAt !== "acceptance-repeat-feed" ||
      feedReplacementApiOk.eventSource !== "acceptance-event-feed" ||
      feedReplacementApiOk.finalGeneratedAt !== "acceptance-event-feed" ||
      feedReplacementApiOk.eventError ||
      feedReplacementApiOk.feedError ||
      feedReplacementApiOk.categoryCount < 1 ||
      feedReplacementApiOk.selected > 1 ||
      feedReplacementApiOk.runtimePanels > 1 ||
      feedReplacementApiOk.incidentPanels > 1
    ) {
      console.error("Feed replacement API acceptance failed");
      console.error(JSON.stringify(feedReplacementApiOk, null, 2));
      process.exitCode = 1;
      return;
    }

    const reloadFailClosedOk = await page.evaluate(async () => {
      const runtime = window.YonerAIStatusRuntime;
      const beforeGeneratedAt = runtime.getFeed()?.generated_at;
      const beforeCategories = document.querySelectorAll("#categoryList .category").length;
      const beforeBars = document.querySelectorAll(".bar[data-status-runtime='feed']").length;
      const originalFetch = window.fetch;
      let rejected = false;

      window.fetch = () => Promise.resolve(new Response(JSON.stringify({
        schema_version: "yonerai.status.feed.v1",
        categories: "invalid",
      }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }));

      try {
        await runtime.reload("/acceptance-invalid-feed.json", { animate: false, source: "acceptance-invalid-reload" });
      } catch {
        rejected = true;
      } finally {
        window.fetch = originalFetch;
      }

      return {
        rejected,
        beforeGeneratedAt,
        afterGeneratedAt: runtime.getFeed()?.generated_at,
        feedError: document.documentElement.dataset.statusFeedError || "",
        categories: document.querySelectorAll("#categoryList .category").length,
        bars: document.querySelectorAll(".bar[data-status-runtime='feed']").length,
        beforeCategories,
        beforeBars,
        runtimePanels: document.querySelectorAll("#barDetailPanel").length,
        incidentPanels: document.querySelectorAll("#incidentDetailPanel").length,
      };
    });

    if (
      !reloadFailClosedOk.rejected ||
      reloadFailClosedOk.beforeGeneratedAt !== reloadFailClosedOk.afterGeneratedAt ||
      reloadFailClosedOk.feedError !== "reload-failed" ||
      reloadFailClosedOk.categories !== reloadFailClosedOk.beforeCategories ||
      reloadFailClosedOk.bars !== reloadFailClosedOk.beforeBars ||
      reloadFailClosedOk.runtimePanels > 1 ||
      reloadFailClosedOk.incidentPanels > 1
    ) {
      console.error("Reload fail-closed acceptance failed");
      console.error(JSON.stringify(reloadFailClosedOk, null, 2));
      process.exitCode = 1;
      return;
    }

    const sseFailClosedOk = await page.evaluate(() => new Promise((resolve) => {
      const runtime = window.YonerAIStatusRuntime;
      const beforeGeneratedAt = runtime.getFeed()?.generated_at;
      const originalEventSource = window.EventSource;
      const listeners = {};

      function MockEventSource(href) {
        this.href = href;
      }
      MockEventSource.prototype.addEventListener = function addEventListener(type, listener) {
        listeners[type] = listener;
      };
      MockEventSource.prototype.close = function close() {};

      window.EventSource = MockEventSource;
      runtime.connectEvents("/acceptance-status-feed-events");
      listeners.open?.({});
      listeners["status-feed"]?.({ data: "{not-json" });
      const afterInvalidGeneratedAt = runtime.getFeed()?.generated_at;
      const invalidError = document.documentElement.dataset.statusFeedEventError || "";

      const nextFeed = JSON.parse(JSON.stringify(runtime.getFeed()));
      nextFeed.generated_at = "acceptance-sse-feed";
      document.addEventListener("yonerai-status-feed-applied", (event) => {
        window.setTimeout(() => {
          runtime.disconnectEvents();
          window.EventSource = originalEventSource;
          resolve({
            beforeGeneratedAt,
            afterInvalidGeneratedAt,
            invalidError,
            source: event.detail?.source,
            finalGeneratedAt: runtime.getFeed()?.generated_at,
            finalEventError: document.documentElement.dataset.statusFeedEventError || "",
            liveState: document.documentElement.dataset.statusLive || "",
            categories: document.querySelectorAll("#categoryList .category").length,
            selected: document.querySelectorAll(".bar.is-selected").length,
            runtimePanels: document.querySelectorAll("#barDetailPanel").length,
            incidentPanels: document.querySelectorAll("#incidentDetailPanel").length,
          });
        }, 50);
      }, { once: true });
      listeners["status-feed"]?.({ data: JSON.stringify(nextFeed) });
    }));

    if (
      sseFailClosedOk.beforeGeneratedAt !== sseFailClosedOk.afterInvalidGeneratedAt ||
      sseFailClosedOk.invalidError !== "parse" ||
      sseFailClosedOk.source !== "events" ||
      sseFailClosedOk.finalGeneratedAt !== "acceptance-sse-feed" ||
      sseFailClosedOk.finalEventError ||
      sseFailClosedOk.liveState ||
      sseFailClosedOk.categories < 1 ||
      sseFailClosedOk.selected > 1 ||
      sseFailClosedOk.runtimePanels > 1 ||
      sseFailClosedOk.incidentPanels > 1
    ) {
      console.error("SSE fail-closed acceptance failed");
      console.error(JSON.stringify(sseFailClosedOk, null, 2));
      process.exitCode = 1;
      return;
    }

    const canonicalRouteOk = await page.evaluate(() => new Promise((resolve) => {
      const runtime = window.YonerAIStatusRuntime;
      const feed = JSON.parse(JSON.stringify(runtime.getFeed()));
      const category = feed.categories.find((item) => item.id === "status-bar-test") || feed.categories[0];
      const component = category.children[0];
      const day = component.days[5];
      day.state = "maintenance";
      day.color = "#fb923c";
      runtime.setFeed(feed, { animate: false, source: "acceptance-canonical-route" });
      window.location.hash = `status/${category.id}/${component.id}/${day.date}/operational`;
      runtime.syncRoute();
      window.setTimeout(() => {
        const categoryBar = document.querySelector(`.category-bars[data-category-id="${CSS.escape(category.id)}"] .bar[data-date="${CSS.escape(day.date)}"]`);
        const selected = document.querySelector(".bar.is-selected");
        resolve({
          hash: window.location.hash,
          route: document.documentElement.dataset.statusRoute,
          selectedCount: document.querySelectorAll(".bar.is-selected").length,
          selectedState: selected?.dataset.state || "",
          categoryBarColor: categoryBar ? getComputedStyle(categoryBar).getPropertyValue("--bar-color").trim() : "",
        });
      }, 120);
    }));

    if (
      !canonicalRouteOk.hash.endsWith("/maintenance") ||
      canonicalRouteOk.route !== "status" ||
      canonicalRouteOk.selectedCount !== 1 ||
      canonicalRouteOk.selectedState !== "maintenance" ||
      canonicalRouteOk.categoryBarColor.toLowerCase() !== "#fb923c"
    ) {
      console.error("Canonical status route acceptance failed");
      console.error(JSON.stringify(canonicalRouteOk, null, 2));
      process.exitCode = 1;
      return;
    }

    const liveUpdateOk = await page.evaluate(() => new Promise((resolve) => {
      const runtime = window.YonerAIStatusRuntime;
      const base = JSON.parse(JSON.stringify(runtime.getFeed()));
      base.generated_at = "acceptance-live-update";
      base.categories[0].children[0].days[0].state = "degraded";
      base.categories[0].children[0].days[0].color = "#ffbf2f";
      base.categories[0].children[0].days[0].message = {
        ja: "acceptance live update",
        en: "acceptance live update",
      };

      document.addEventListener("yonerai-status-feed-applied", (event) => {
        window.setTimeout(() => {
          resolve({
            source: event.detail?.source,
            generatedAt: runtime.getFeed()?.generated_at,
            pendingCascade: document.querySelectorAll(".is-cascade-pending,.is-runtime-cascade,.is-cascading").length,
            selected: document.querySelectorAll(".bar.is-selected").length,
            panels: document.querySelectorAll("#barDetailPanel,#incidentDetailPanel").length,
          });
        }, 50);
      }, { once: true });

      runtime.setFeed(base, { animate: false, source: "acceptance-live-update" });
    }));

    if (
      liveUpdateOk.source !== "acceptance-live-update" ||
      liveUpdateOk.generatedAt !== "acceptance-live-update" ||
      liveUpdateOk.pendingCascade !== 0 ||
      liveUpdateOk.selected > 1 ||
      liveUpdateOk.panels > 1
    ) {
      console.error("Live update render-mode acceptance failed");
      console.error(JSON.stringify(liveUpdateOk, null, 2));
      process.exitCode = 1;
      return;
    }

    const presentationContractOk = await page.evaluate(() => new Promise((resolve) => {
      const runtime = window.YonerAIStatusRuntime;
      const feed = JSON.parse(JSON.stringify(runtime.getFeed()));
      const category = feed.categories[0];
      const component = category.children[0];
      const day = component.days[0];
      day.state = "degraded";
      day.color = "#ffbf2f";
      day.message = {
        ja: "acceptance presentation message",
        en: "acceptance presentation message",
      };
      day.detail = {
        summary: {
          ja: [
            "acceptance detail paragraph one",
            "acceptance detail paragraph two",
          ],
          en: [
            "acceptance detail paragraph one",
            "acceptance detail paragraph two",
          ],
        },
      };
      runtime.setFeed(feed, { animate: false, source: "acceptance-presentation" });
      window.location.hash = `status/${category.id}/${component.id}/${day.date}/${day.state}`;
      window.setTimeout(() => {
        const panel = document.querySelector("#barDetailPanel");
        const bar = document.querySelector(`.bar.is-selected[data-date="${CSS.escape(day.date)}"]`);
        resolve({
          panelExists: Boolean(panel),
          panelAccent: panel ? getComputedStyle(panel).getPropertyValue("--panel-accent").trim() : "",
          barColor: bar ? getComputedStyle(bar).getPropertyValue("--bar-color").trim() : "",
          text: panel?.textContent || "",
        });
      }, 120);
    }));

    if (
      !presentationContractOk.panelExists ||
      presentationContractOk.panelAccent.toLowerCase() !== "#ffbf2f" ||
      presentationContractOk.barColor.toLowerCase() !== "#ffbf2f" ||
      !presentationContractOk.text.includes("acceptance detail paragraph one") ||
      !presentationContractOk.text.includes("acceptance detail paragraph two")
    ) {
      console.error("Feed-driven presentation acceptance failed");
      console.error(JSON.stringify(presentationContractOk, null, 2));
      process.exitCode = 1;
      return;
    }

    await page.evaluate(() => {
      const feed = window.YonerAIStatusRuntime.getFeed();
      const incident = feed.incidents[0];
      window.location.hash = `incident/${incident.id}`;
    });
    await page.waitForSelector("#incidentDetailPanel.is-visible", { timeout: 5000 });

    const incidentRouteOk = await page.evaluate(() => ({
      incidentPanels: document.querySelectorAll("#incidentDetailPanel").length,
      updates: document.querySelectorAll("#updatesTimeline .timeline-item").length,
      affectedSegments: document.querySelectorAll(".affected-segment").length,
      staleSelected: document.querySelectorAll(".bar.is-selected").length,
      route: document.documentElement.dataset.statusRoute,
    }));
    if (
      incidentRouteOk.incidentPanels !== 1 ||
      incidentRouteOk.updates < 1 ||
      incidentRouteOk.affectedSegments < 1 ||
      incidentRouteOk.staleSelected !== 0 ||
      incidentRouteOk.route !== "incident"
    ) {
      console.error("Incident route acceptance failed");
      console.error(JSON.stringify(incidentRouteOk, null, 2));
      process.exitCode = 1;
      return;
    }

    console.log(`Status runtime acceptance passed: ${target}`);
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
