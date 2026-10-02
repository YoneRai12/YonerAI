/*
 * Example production bootstrap for YonerAI Status runtime.
 *
 * This file is intentionally not loaded by index.html by default.
 * Copy this pattern into the hosting layer when a real same-origin feed source
 * exists. The runtime renderer stays in mock-status-adapter.js.
 */

(() => {
  const config = {
    feedUrl: "/status-feed.json",
    eventStreamUrl: "/status-feed/events",
    refreshMs: 30_000,
    enablePolling: true,
    enableEventSource: true,
  };

  let timer = 0;
  let eventSource = null;
  let lastAppliedAt = 0;

  function runtime() {
    if (!window.YonerAIStatusRuntime) {
      throw new Error("YonerAIStatusRuntime is not ready");
    }
    return window.YonerAIStatusRuntime;
  }

  function sameOrigin(url) {
    const parsed = new URL(url, window.location.href);
    if (parsed.origin !== window.location.origin) {
      throw new Error(`status feed URL must be same-origin: ${parsed.href}`);
    }
    return parsed.href;
  }

  async function loadOnce() {
    const result = await applyRemoteFeed(config.feedUrl, "bootstrap-polling");
    if (!result.ok) throw new Error(result.error?.message || "status feed rejected");
    return result;
  }

  function applyFeed(feed, source = "bootstrap-direct") {
    const api = runtime();
    if (api.trySetFeed) {
      const result = api.trySetFeed(feed, {
        animate: false,
        source,
      });
      if (result.ok) lastAppliedAt = Date.now();
      return result;
    }
    try {
      const applied = api.setFeed(feed, {
        animate: false,
        source,
      });
      lastAppliedAt = Date.now();
      return { ok: true, feed: applied, state: api.getState?.() || null };
    } catch (error) {
      return {
        ok: false,
        error: {
          name: error?.name || "Error",
          message: error?.message || String(error),
        },
        state: api.getState?.() || null,
      };
    }
  }

  async function applyRemoteFeed(url, source) {
    const response = await fetch(sameOrigin(url), { cache: "no-store" });
    if (!response.ok) {
      return {
        ok: false,
        error: {
          name: "FeedLoadError",
          message: `failed to load status feed: ${response.status}`,
        },
        state: window.YonerAIStatusRuntime?.getState?.() || null,
      };
    }
    return applyFeed(await response.json(), source);
  }

  function schedulePolling() {
    window.clearTimeout(timer);
    if (!config.enablePolling) return;
    timer = window.setTimeout(async () => {
      try {
        await loadOnce();
      } catch (error) {
        console.warn("status feed refresh failed", error);
      } finally {
        schedulePolling();
      }
    }, config.refreshMs);
  }

  function connectEventSource() {
    if (!config.enableEventSource || !window.EventSource) return;
    if (eventSource) eventSource.close();
    eventSource = new EventSource(sameOrigin(config.eventStreamUrl));

    eventSource.addEventListener("status-feed", (event) => {
      try {
        const result = applyFeed(JSON.parse(event.data), "bootstrap-sse");
        if (!result.ok) console.warn("status feed event was rejected", result.error);
      } catch (error) {
        console.warn("status feed event was rejected", error);
      }
    });

    eventSource.addEventListener("ping", () => {
      lastAppliedAt = Date.now();
    });

    eventSource.addEventListener("error", () => {
      eventSource?.close();
      eventSource = null;
      window.setTimeout(connectEventSource, 5000);
    });
  }

  function exposeStatusHook() {
    window.YonerAIStatusLive = {
      reload: loadOnce,
      applyFeed,
      reconnect: connectEventSource,
      getState: () => ({
        feedUrl: config.feedUrl,
        eventStreamUrl: config.eventStreamUrl,
        enablePolling: config.enablePolling,
        enableEventSource: config.enableEventSource,
        eventSourceState: eventSource?.readyState ?? null,
        lastAppliedAt,
        runtime: window.YonerAIStatusRuntime?.getState?.() || null,
      }),
    };
  }

  window.addEventListener("DOMContentLoaded", async () => {
    // Do not bind yonerai-status:set-feed here.
    // mock-status-adapter.js already owns that event, and a second listener
    // would apply the same feed twice.
    exposeStatusHook();
    try {
      await loadOnce();
    } catch (error) {
      console.warn("initial status feed load failed", error);
    }
    connectEventSource();
    schedulePolling();
  });
})();
