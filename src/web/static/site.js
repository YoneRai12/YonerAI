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
    document.querySelectorAll("[data-card-href]").forEach((card) => {
      const href = card.getAttribute("data-card-href") || "";
      if (!href) {
        return;
      }
      card.setAttribute("tabindex", "0");
      card.setAttribute("role", "link");
      const openCard = () => {
        if (/^https?:\/\//i.test(href)) {
          window.open(href, "_blank", "noopener,noreferrer");
          return;
        }
        window.location.assign(href);
      };
      card.addEventListener("click", openCard);
      card.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          openCard();
        }
      });
    });
  }

  function finishPreload() {
    document.body.classList.remove("preload");
  }

  window.YonerAIWeb = {
    resolveApiBase,
    resolveChatHref,
    resolveGoogleStartHref,
  };

  if (document.readyState === "loading") {
    document.addEventListener(
      "DOMContentLoaded",
      () => {
        wireLinks();
        finishPreload();
      },
      { once: true }
    );
  } else {
    wireLinks();
    finishPreload();
  }
})();
