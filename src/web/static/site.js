(() => {
  "use strict";

  function stripTrailingSlash(value) {
    return String(value || "").replace(/\/+$/, "");
  }

  function hostName() {
    return String(window.location.hostname || "").toLowerCase();
  }

  function resolveApiBase() {
    const host = hostName();
    if (host === "yonerai.com" || host === "www.yonerai.com") {
      return "https://api.yonerai.com";
    }
    return stripTrailingSlash(window.location.origin || "");
  }

  function resolveChatHref() {
    const apiBase = resolveApiBase();
    if (stripTrailingSlash(apiBase) === stripTrailingSlash(window.location.origin || "")) {
      return "/jp/chat";
    }
    return `${apiBase}/jp/chat`;
  }

  function resolveGoogleStartHref(returnTo) {
    const apiBase = resolveApiBase();
    return `${apiBase}/api/auth/google/start?returnTo=${encodeURIComponent(returnTo || "/jp/chat")}`;
  }

  function wireLinks() {
    document.querySelectorAll("[data-chat-cta]").forEach((link) => {
      link.setAttribute("href", resolveChatHref());
    });
    document.querySelectorAll("[data-google-login]").forEach((link) => {
      const nextPath = link.getAttribute("data-return-to") || "/jp/chat";
      link.setAttribute("href", resolveGoogleStartHref(nextPath));
    });
  }

  window.YonerAIWeb = {
    resolveApiBase,
    resolveChatHref,
    resolveGoogleStartHref,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", wireLinks, { once: true });
  } else {
    wireLinks();
  }
})();
