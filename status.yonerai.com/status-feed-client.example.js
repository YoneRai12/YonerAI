(() => {
  if (window.YonerAIStatusFeedClient?.__version === "20260601-feed-client-example") return;

  const VERSION = "20260601-feed-client-example";
  const SET_FEED_EVENT = "yonerai-status:set-feed";
  const APPLIED_EVENT = "yonerai-status-feed-applied";
  const READY_EVENT = "yonerai-status-runtime-ready";

  function runtime() {
    return window.YonerAIStatusRuntime || null;
  }

  function normalizeOptions(options = {}, fallbackSource = "client") {
    return {
      ...options,
      source: options.source || fallbackSource,
    };
  }

  function sameOrigin(url) {
    const parsed = new URL(url, window.location.href);
    if (parsed.origin !== window.location.origin) {
      throw new Error("YonerAI Status feed client only accepts same-origin URLs");
    }
    return parsed.href;
  }

  function dispatch(feed, options = {}) {
    const finalOptions = normalizeOptions(options, "client-dispatch");
    document.dispatchEvent(new CustomEvent(SET_FEED_EVENT, {
      detail: {
        feed,
        options: finalOptions,
        source: finalOptions.source,
      },
    }));
    return {
      ok: null,
      pending: true,
      state: runtime()?.getState?.() || null,
    };
  }

  function apply(feed, options = {}) {
    const finalOptions = normalizeOptions(options, "client-apply");
    const api = runtime();
    if (api?.trySetFeed) return api.trySetFeed(feed, finalOptions);
    if (api?.setFeed) {
      try {
        const applied = api.setFeed(feed, finalOptions);
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
    return dispatch(feed, finalOptions);
  }

  async function load(url = "/status-feed.json", options = {}) {
    const href = sameOrigin(url);
    const finalOptions = normalizeOptions(options, "client-load");
    const api = runtime();
    if (api?.reload) {
      try {
        const applied = await api.reload(href, finalOptions);
        return { ok: true, feed: applied, state: api.getState?.() || null };
      } catch (error) {
        return {
          ok: false,
          error: {
            name: error?.name || "FeedLoadError",
            message: error?.message || String(error),
          },
          state: api.getState?.() || null,
        };
      }
    }
    const response = await fetch(href, { cache: "no-store" });
    if (!response.ok) {
      return {
        ok: false,
        error: {
          name: "FeedLoadError",
          message: `failed to load status feed: ${response.status}`,
        },
        state: runtime()?.getState?.() || null,
      };
    }
    return apply(await response.json(), finalOptions);
  }

  function waitForRuntime(timeoutMs = 5000) {
    if (runtime()) return Promise.resolve(runtime());
    return new Promise((resolve, reject) => {
      let timer = 0;
      let poller = 0;
      const cleanup = () => {
        window.clearTimeout(timer);
        window.clearTimeout(poller);
        document.removeEventListener(READY_EVENT, onReady);
      };
      const resolveIfReady = () => {
        const api = runtime();
        if (!api) return false;
        cleanup();
        resolve(api);
        return true;
      };
      const onReady = () => {
        resolveIfReady();
      };
      const poll = () => {
        if (resolveIfReady()) return;
        poller = window.setTimeout(poll, 50);
      };
      timer = window.setTimeout(() => {
        cleanup();
        reject(new Error("YonerAIStatusRuntime was not available before timeout"));
      }, timeoutMs);
      document.addEventListener(READY_EVENT, onReady);
      poll();
    });
  }

  async function applyWhenReady(feed, options = {}, timeoutMs = 5000) {
    await waitForRuntime(timeoutMs);
    return apply(feed, normalizeOptions(options, "client-ready-apply"));
  }

  async function loadWhenReady(url = "/status-feed.json", options = {}, timeoutMs = 5000) {
    await waitForRuntime(timeoutMs);
    return load(url, normalizeOptions(options, "client-ready-load"));
  }

  window.YonerAIStatusFeedClient = {
    __version: VERSION,
    eventName: SET_FEED_EVENT,
    appliedEventName: APPLIED_EVENT,
    readyEventName: READY_EVENT,
    apply,
    applyWhenReady,
    dispatch,
    load,
    loadWhenReady,
    waitForRuntime,
  };
})();
