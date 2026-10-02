/*
 * Browser-side YonerAI Status runtime probe.
 *
 * Usage in a loaded status page:
 *   window.YonerAIStatusProbe.run()
 *
 * Or load this file in local/dev and call:
 *   const report = window.YonerAIStatusProbe.run({ log: true });
 *
 * This script does not mutate feed data, DOM state, selected bars, tooltip
 * state, or runtime routes. It only reads runtime diagnostics and DOM counts.
 */
(function installYonerAIStatusProbe(global) {
  "use strict";

  function all(selector) {
    return Array.from(global.document.querySelectorAll(selector));
  }

  function one(selector) {
    return global.document.querySelector(selector);
  }

  function isVisible(node) {
    if (!node || node.hidden) return false;
    const style = global.getComputedStyle(node);
    return style.display !== "none" && style.visibility !== "hidden" && style.opacity !== "0";
  }

  function runtime() {
    return global.YonerAIStatusRuntime || global.YonerAIStatus || null;
  }

  function safeCall(fn, fallback) {
    try {
      return typeof fn === "function" ? fn() : fallback;
    } catch (error) {
      return { error: String(error && error.message ? error.message : error) };
    }
  }

  function routeFromHash() {
    return String(global.location.hash || "").replace(/^#/, "");
  }

  function selectedRoutes() {
    return all(".bar.is-selected").map((bar) => bar.dataset.route || "");
  }

  function feedBarCounts(feed) {
    var componentBars = 0;
    var categoryOverviewBars = 0;
    var categories = Array.isArray(feed && feed.categories) ? feed.categories : [];
    categories.forEach(function countCategory(category) {
      var children = Array.isArray(category.children) ? category.children : [];
      children.forEach(function countChild(child) {
        componentBars += Array.isArray(child.days) ? child.days.length : 0;
      });
      var firstChild = children.find(function hasDays(child) {
        return Array.isArray(child.days);
      });
      categoryOverviewBars += firstChild ? firstChild.days.length : 0;
    });
    return {
      componentBars: componentBars,
      categoryOverviewBars: categoryOverviewBars,
      expectedWithCategoryOverview: componentBars + categoryOverviewBars
    };
  }

  function addCheck(checks, name, ok, detail, severity) {
    checks.push({
      name: name,
      ok: Boolean(ok),
      severity: severity || "blocker",
      detail: detail || null
    });
  }

  function run(options) {
    var opts = options || {};
    var rt = runtime();
    var state = safeCall(function getRuntimeState() {
      return rt && rt.getState ? rt.getState() : null;
    }, null);
    var feed = safeCall(function getRuntimeFeed() {
      return rt && rt.getFeed ? rt.getFeed() : null;
    }, null);
    var tooltip = one("#barTooltip");
    var tooltipStyle = tooltip ? global.getComputedStyle(tooltip) : null;
    var selected = all(".bar.is-selected");
    var hovered = all(".bar.is-hovered");
    var statusPanels = all("#barDetailPanel");
    var incidentPanels = all("#incidentDetailPanel");
    var visibleStatusPanels = statusPanels.filter(isVisible);
    var visibleIncidentPanels = incidentPanels.filter(isVisible);
    var overflow = global.document.documentElement.scrollWidth > global.document.documentElement.clientWidth + 2;
    var routes = selectedRoutes();
    var feedCounts = feedBarCounts(feed);
    var renderedBars = all(".bar").length;
    var hash = routeFromHash();
    var checks = [];

    addCheck(checks, "runtime-present", Boolean(rt), "window.YonerAIStatusRuntime or window.YonerAIStatus is available");
    addCheck(checks, "tooltip-singleton", all("#barTooltip").length === 1, { count: all("#barTooltip").length });
    addCheck(checks, "tooltip-pointer-safe", !tooltipStyle || tooltipStyle.pointerEvents === "none", {
      pointerEvents: tooltipStyle ? tooltipStyle.pointerEvents : null
    }, "major");
    addCheck(checks, "selected-singleton", selected.length <= 1, { count: selected.length });
    addCheck(checks, "bar-detail-panel-singleton", statusPanels.length <= 1, { count: statusPanels.length });
    addCheck(checks, "incident-panel-singleton", incidentPanels.length <= 1, { count: incidentPanels.length });
    addCheck(checks, "panel-mode-exclusive", !(visibleStatusPanels.length && visibleIncidentPanels.length), {
      visibleStatusPanels: visibleStatusPanels.length,
      visibleIncidentPanels: visibleIncidentPanels.length
    });
    addCheck(checks, "viewport-no-horizontal-overflow", !overflow, {
      scrollWidth: global.document.documentElement.scrollWidth,
      clientWidth: global.document.documentElement.clientWidth
    }, "major");
    addCheck(checks, "runtime-state-selected-count-compatible", !state || state.error || state.selectedCount == null || state.selectedCount === selected.length, {
      runtimeSelectedCount: state && state.selectedCount,
      domSelectedCount: selected.length
    }, "major");
    addCheck(checks, "runtime-panel-count-compatible", !state || state.error || (
      (state.statusPanels == null || state.statusPanels === statusPanels.length) &&
      (state.incidentPanels == null || state.incidentPanels === incidentPanels.length)
    ), {
      runtimeStatusPanels: state && state.statusPanels,
      domStatusPanels: statusPanels.length,
      runtimeIncidentPanels: state && state.incidentPanels,
      domIncidentPanels: incidentPanels.length
    }, "major");
    addCheck(checks, "selected-route-non-empty", selected.length === 0 || routes.every(Boolean), { routes: routes }, "major");
    addCheck(checks, "selected-route-matches-runtime", selected.length === 0 || !state || !state.selectedRoute || routes.includes(state.selectedRoute), {
      routes: routes,
      runtimeSelectedRoute: state && state.selectedRoute,
      hash: hash
    }, "major");
    addCheck(checks, "rendered-bars-at-least-component-days", !feed || feed.error || renderedBars >= feedCounts.componentBars, {
      renderedBars: renderedBars,
      componentBars: feedCounts.componentBars,
      expectedWithCategoryOverview: feedCounts.expectedWithCategoryOverview
    }, "major");

    var failed = checks.filter(function failedCheck(check) {
      return !check.ok;
    });
    var report = {
      schema_version: "yonerai.status.browser-probe.report.v1",
      generated_at: new Date().toISOString(),
      ok: failed.length === 0,
      url: global.location.href,
      hash: hash,
      runtimeState: state,
      counts: {
        bars: renderedBars,
        selected: selected.length,
        hovered: hovered.length,
        tooltips: all("#barTooltip").length,
        statusPanels: statusPanels.length,
        incidentPanels: incidentPanels.length,
        visibleStatusPanels: visibleStatusPanels.length,
        visibleIncidentPanels: visibleIncidentPanels.length
      },
      feedCounts: feedCounts,
      checks: checks,
      failed: failed
    };

    if (opts.log) {
      var logger = report.ok ? console.log : console.error;
      logger.call(console, "YonerAI Status browser probe", report);
    }
    return report;
  }

  global.YonerAIStatusProbe = {
    run: run
  };
})(window);
