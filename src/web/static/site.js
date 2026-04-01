(() => {
  "use strict";
  const COOKIE_CONSENT_KEY = "yonerai_cookie_consent_v1";
  const COOKIE_LANG_KEY = "yonerai_lang";
  const COOKIE_TTL_SEC = 31536000;
  const TOPBAR_HINT_KEY = "yonerai_topbar_scroll_hint_seen_v1";
  const COOKIE_COPY = {
    en: {
      title: "Cookie preferences",
      body: "YonerAI uses an essential session cookie (yonerai_session) for sign-in, and one optional cookie (yonerai_lang) to remember language across visits.",
      accept: "Allow optional cookie",
      essential: "Essential only",
    },
    ja: {
      title: "Cookie設定",
      body: "YonerAI はログインのために必須Cookie (yonerai_session) を使用し、言語設定を保持するために任意Cookie (yonerai_lang) を使用します。",
      accept: "任意Cookieを許可",
      essential: "必須のみ",
    },
  };

  function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) {
      return parts.pop().split(";").shift() || "";
    }
    return "";
  }

  function setCookie(name, value, maxAgeSec) {
    document.cookie = `${name}=${encodeURIComponent(value)}; path=/; max-age=${maxAgeSec}; SameSite=Lax`;
  }

  function clearCookie(name) {
    document.cookie = `${name}=; path=/; max-age=0; SameSite=Lax`;
  }

  function normalizeLang(v) {
    const s = String(v || "").toLowerCase();
    return s.startsWith("ja") ? "ja" : "en";
  }

  function langFromPath() {
    const p = (window.location.pathname || "/").toLowerCase();
    if (p === "/jp" || p.startsWith("/jp/")) {
      return "ja";
    }
    if (p === "/en" || p.startsWith("/en/")) {
      return "en";
    }
    return "";
  }

  function localePrefix(lang) {
    return normalizeLang(lang) === "ja" ? "/jp" : "/en";
  }

  function resolveChatHostBase() {
    const host = String(window.location.hostname || "").toLowerCase();
    const proto = String(window.location.protocol || "https:");
    if (host === "yonerai.com" || host === "www.yonerai.com") {
      return `${proto}//api.yonerai.com`;
    }
    return `${proto}//${window.location.host}`;
  }

  function resolveLocalizedChatHref(lang) {
    return `${resolveChatHostBase()}${localePrefix(lang)}/chat`;
  }

  function resolveLocalizedLoginHref(lang) {
    const chatHref = resolveLocalizedChatHref(lang);
    const chatUrl = new URL(chatHref, window.location.origin);
    return `${resolveChatHostBase()}/auth/login?returnTo=${encodeURIComponent(chatUrl.pathname)}`;
  }

  function stripLocalePrefix(path) {
    const p = path || "/";
    if (p === "/jp" || p.startsWith("/jp/")) {
      const rest = p.slice(3);
      return rest ? rest : "/";
    }
    if (p === "/en" || p.startsWith("/en/")) {
      const rest = p.slice(3);
      return rest ? rest : "/";
    }
    return p;
  }

  function localizedPath(lang) {
    const base = stripLocalePrefix(window.location.pathname || "/");
    const prefix = localePrefix(lang);
    const normalizedBase = base.startsWith("/") ? base : `/${base}`;
    const targetPath = normalizedBase === "/" ? prefix : `${prefix}${normalizedBase}`;
    return `${targetPath}${window.location.search || ""}${window.location.hash || ""}`;
  }

  function detectLang() {
    const params = new URLSearchParams(window.location.search);
    const forced = params.get("lang");
    if (forced) {
      return normalizeLang(forced);
    }

    const fromPath = langFromPath();
    if (fromPath) {
      return normalizeLang(fromPath);
    }

    const fromCookie = getCookie(COOKIE_LANG_KEY);
    if (fromCookie) {
      return normalizeLang(fromCookie);
    }

    const langs = Array.isArray(navigator.languages) && navigator.languages.length
      ? navigator.languages
      : [navigator.language || "en"];
    return langs.some((x) => String(x).toLowerCase().startsWith("ja")) ? "ja" : "en";
  }

  function getConsentState() {
    const v = getCookie(COOKIE_CONSENT_KEY);
    return v === "accepted" || v === "essential" ? v : "";
  }

  function canStoreOptionalCookies() {
    return getConsentState() === "accepted";
  }

  function setLangCookie(lang) {
    if (!canStoreOptionalCookies()) {
      return;
    }
    setCookie(COOKIE_LANG_KEY, normalizeLang(lang), COOKIE_TTL_SEC);
  }

  function updateCookieConsentText(lang) {
    const root = document.getElementById("oa-cookie-consent");
    if (!root) {
      return;
    }
    const copy = COOKIE_COPY[normalizeLang(lang)];
    const title = root.querySelector("[data-cookie-title]");
    const body = root.querySelector("[data-cookie-body]");
    const accept = root.querySelector("[data-cookie-accept]");
    const essential = root.querySelector("[data-cookie-essential]");
    if (title) title.textContent = copy.title;
    if (body) body.textContent = copy.body;
    if (accept) accept.textContent = copy.accept;
    if (essential) essential.textContent = copy.essential;
  }

  function hideCookieConsent() {
    const root = document.getElementById("oa-cookie-consent");
    if (!root) {
      return;
    }
    root.classList.add("is-hide");
    window.setTimeout(() => {
      root.remove();
    }, 220);
  }

  function showCookieConsent(lang) {
    if (getConsentState()) {
      return;
    }
    if (document.getElementById("oa-cookie-consent")) {
      updateCookieConsentText(lang);
      return;
    }

    const wrap = document.createElement("section");
    wrap.id = "oa-cookie-consent";
    wrap.className = "oa-cookie-consent";
    wrap.setAttribute("role", "dialog");
    wrap.setAttribute("aria-live", "polite");
    wrap.setAttribute("aria-modal", "false");
    wrap.innerHTML = `
      <div class="oa-cookie-card">
        <h2 data-cookie-title></h2>
        <p data-cookie-body></p>
        <div class="oa-cookie-actions">
          <button type="button" class="oa-cookie-btn is-ghost" data-cookie-essential></button>
          <button type="button" class="oa-cookie-btn is-primary" data-cookie-accept></button>
        </div>
      </div>
    `;
    document.body.appendChild(wrap);
    updateCookieConsentText(lang);

    const acceptBtn = wrap.querySelector("[data-cookie-accept]");
    const essentialBtn = wrap.querySelector("[data-cookie-essential]");
    if (acceptBtn) {
      acceptBtn.addEventListener("click", () => {
        const activeLang = normalizeLang(document.documentElement.lang || lang || "en");
        setCookie(COOKIE_CONSENT_KEY, "accepted", COOKIE_TTL_SEC);
        setCookie(COOKIE_LANG_KEY, activeLang, COOKIE_TTL_SEC);
        hideCookieConsent();
      });
    }

    if (essentialBtn) {
      essentialBtn.addEventListener("click", () => {
        setCookie(COOKIE_CONSENT_KEY, "essential", COOKIE_TTL_SEC);
        clearCookie(COOKIE_LANG_KEY);
        hideCookieConsent();
      });
    }
  }

  function translateElement(el, lang) {
    const key = lang === "ja" ? "i18nJa" : "i18nEn";
    if (Object.prototype.hasOwnProperty.call(el.dataset, key)) {
      el.textContent = el.dataset[key] || "";
    }
  }

  function applyLangAssetBindings(lang) {
    const srcKey = lang === "ja" ? "langSrcJa" : "langSrcEn";
    const hrefKey = lang === "ja" ? "langHrefJa" : "langHrefEn";

    document.querySelectorAll("[data-lang-src-en]").forEach((el) => {
      const src = el.dataset[srcKey] || el.dataset.langSrcEn || "";
      if (src && el.getAttribute("src") !== src) {
        el.setAttribute("src", src);
      }
    });

    document.querySelectorAll("[data-lang-href-en]").forEach((el) => {
      const href = el.dataset[hrefKey] || el.dataset.langHrefEn || "";
      if (href && el.getAttribute("href") !== href) {
        el.setAttribute("href", href);
      }
    });
  }

  function applyLang(lang) {
    document.documentElement.lang = lang;
    document.querySelectorAll("[data-i18n-en]").forEach((el) => translateElement(el, lang));
    applyLangAssetBindings(lang);

    document.querySelectorAll("[data-lang-btn]").forEach((btn) => {
      const active = (btn.getAttribute("data-lang-btn") || "") === lang;
      btn.classList.toggle("is-active", active);
      btn.setAttribute("aria-pressed", active ? "true" : "false");
    });

    const note = document.getElementById("lang-note");
    if (note) {
      const canStore = canStoreOptionalCookies();
      if (lang === "ja") {
        note.textContent = canStore
          ? "言語設定は Cookie (yonerai_lang) に保存されます。"
          : "言語設定は任意Cookie (yonerai_lang) を許可した場合のみ保存されます。";
      } else {
        note.textContent = canStore
          ? "Language preference is stored in cookie (yonerai_lang)."
          : "Language preference is stored only if you allow the optional cookie (yonerai_lang).";
      }
    }
    updateCookieConsentText(lang);
    window.dispatchEvent(new CustomEvent("yonerai:lang-changed", { detail: { lang } }));
  }

  function fitRailLinksToLongest() {
    const menu = document.querySelector(".oa-menu");
    if (!menu) {
      return;
    }

    const links = Array.from(menu.querySelectorAll(".rail-link"));
    if (!links.length) {
      return;
    }

    if (window.matchMedia("(max-width: 1180px)").matches) {
      menu.style.removeProperty("--oa-rail-link-w");
      document.body.style.removeProperty("--oa-rail-w");
      return;
    }

    let maxWidth = 0;
    links.forEach((el) => {
      const prevWidth = el.style.width;
      const prevMinWidth = el.style.minWidth;
      el.style.width = "max-content";
      el.style.minWidth = "0";
      maxWidth = Math.max(maxWidth, Math.ceil(el.getBoundingClientRect().width));
      el.style.width = prevWidth;
      el.style.minWidth = prevMinWidth;
    });

    if (maxWidth <= 0) {
      return;
    }

    const target = Math.min(Math.max(maxWidth, 112), 220);
    menu.style.setProperty("--oa-rail-link-w", `${target}px`);
    document.body.style.setProperty("--oa-rail-w", `${target + 10}px`);
  }

  function setupLangControls() {
    document.querySelectorAll("[data-lang-btn]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const lang = normalizeLang(btn.getAttribute("data-lang-btn") || "en");
        setLangCookie(lang);
        const target = localizedPath(lang);
        const current = `${window.location.pathname || "/"}${window.location.search || ""}${window.location.hash || ""}`;
        if (target !== current) {
          window.location.assign(target);
          return;
        }
        applyLang(lang);
        fitRailLinksToLongest();
      });
    });
  }

  function setupAuthEntries() {
    const nodes = Array.from(document.querySelectorAll("[data-auth-entry]"));
    if (!nodes.length) {
      return;
    }
    let isAuthed = false;

    const resolveText = (node, lang) => {
      const ja = normalizeLang(lang) === "ja";
      if (isAuthed) {
        return ja
          ? (node.dataset.authAuthedJa || "チャットを開く")
          : (node.dataset.authAuthedEn || "Open Chat");
      }
      return ja
        ? (node.dataset.authLoginJa || "ログイン")
        : (node.dataset.authLoginEn || "Sign in");
    };

    const applyState = () => {
      const lang = normalizeLang(document.documentElement.lang || detectLang());
      nodes.forEach((node) => {
        const configuredLoginHref = node.dataset.authLoginHref || "";
        const configuredAuthedHref = node.dataset.authAuthedHref || "";
        const loginHref =
          !configuredLoginHref || configuredLoginHref === "/auth/login?returnTo=/chat"
            ? resolveLocalizedLoginHref(lang)
            : configuredLoginHref;
        const authedHref =
          !configuredAuthedHref || configuredAuthedHref === "/chat"
            ? resolveLocalizedChatHref(lang)
            : configuredAuthedHref;
        node.setAttribute("href", isAuthed ? authedHref : loginHref);
        node.textContent = resolveText(node, lang);
        node.classList.toggle("is-authenticated", isAuthed);
      });
      markActiveNav();
    };

    applyState();
    window.addEventListener("yonerai:lang-changed", applyState);

    fetch("/api/auth/me", { credentials: "include" })
      .then((res) => {
        isAuthed = Boolean(res && res.ok);
      })
      .catch(() => {
        isAuthed = false;
      })
      .finally(() => {
        applyState();
      });
  }

  function markActiveNav() {
    const currentPath = window.location.pathname || "/";
    const path = (stripLocalePrefix(currentPath).replace(/\/$/, "") || "/").toLowerCase();
    const hash = (window.location.hash || "#research").toLowerCase();
    document.querySelectorAll(".nav-link, .rail-link").forEach((a) => {
      const raw = (a.getAttribute("href") || "").trim();
      const href = (raw.replace(/\/$/, "") || "/").toLowerCase();
      let active = false;
      if (raw.startsWith("#")) {
        active = raw.toLowerCase() === hash;
      } else if (raw.startsWith("/#")) {
        active = path === "/" && raw.slice(1).toLowerCase() === hash;
      } else {
        active = (href === "/" && path === "/") || (href !== "/" && path.startsWith(href));
      }
      a.classList.toggle("is-active", active);
    });
  }

  function setupReveal() {
    const nodes = Array.from(document.querySelectorAll(".reveal"));
    if (!nodes.length) {
      return;
    }

    const reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce || typeof IntersectionObserver === "undefined") {
      nodes.forEach((n) => n.classList.add("is-visible"));
      return;
    }

    const obs = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) {
          e.target.classList.add("is-visible");
          obs.unobserve(e.target);
        }
      });
    }, { threshold: 0.16 });

    nodes.forEach((n) => obs.observe(n));
  }

  function setupTopbarScrollState() {
    const topbar = document.querySelector(".oa-global-topbar");
    if (!topbar) {
      return;
    }

    const sync = () => {
      topbar.classList.toggle("is-scrolled", window.scrollY > 10);
    };

    sync();
    window.addEventListener("scroll", sync, { passive: true });
    window.addEventListener("resize", sync);
  }

  function setupAnchorNavigation() {
    const links = document.querySelectorAll(".rail-link[href^=\"#\"], .nav-link[href^=\"#\"]");
    if (!links.length) {
      return;
    }

    links.forEach((link) => {
      link.addEventListener("click", (ev) => {
        const raw = link.getAttribute("href") || "";
        const id = raw.replace(/^#/, "").trim();
        if (!id) {
          return;
        }
        const target = document.getElementById(id);
        if (!target) {
          return;
        }

        ev.preventDefault();
        target.scrollIntoView({ behavior: "smooth", block: "start" });
        window.history.replaceState(null, "", `#${id}`);
        markActiveNav();
      });
    });
  }

  function setupPointerGlow() {
    // Disabled by design:
    // glow should represent active selection, not hover pointer position.
    return;
  }

  function setupCardLinks() {
    const cards = document.querySelectorAll(".oa-card[data-card-href]");
    if (!cards.length) {
      return;
    }

    const openTarget = (href, target) => {
      if (!href) {
        return;
      }
      if (href.startsWith("#")) {
        const id = href.slice(1).trim();
        const node = id ? document.getElementById(id) : null;
        if (node) {
          node.scrollIntoView({ behavior: "smooth", block: "start" });
          window.history.replaceState(null, "", `#${id}`);
          markActiveNav();
        }
        return;
      }
      if (target === "_blank") {
        window.open(href, "_blank", "noopener,noreferrer");
      } else {
        window.location.assign(href);
      }
    };

    cards.forEach((card) => {
      const href = card.getAttribute("data-card-href") || "";
      const target = card.getAttribute("data-card-target") || "";
      if (!href) {
        return;
      }

      card.classList.add("is-clickable");
      card.setAttribute("role", "link");
      card.setAttribute("tabindex", "0");

      card.addEventListener("click", (ev) => {
        const t = ev.target;
        if (t && t.closest && t.closest("a, button, input, textarea, select, label")) {
          return;
        }
        openTarget(href, target);
      });

      card.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter" || ev.key === " ") {
          ev.preventDefault();
          openTarget(href, target);
        }
      });
    });
  }

  function createFlowCanvasRuntime({ canvas, stageCount, getLabels, onStep }) {
    const ctx = canvas.getContext("2d", { alpha: true });
    if (!ctx) {
      return null;
    }

    const clamp = (v, min, max) => Math.min(max, Math.max(min, v));
    const lerp = (a, b, t) => a + (b - a) * t;
    const easeInOut = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
    const hexToRgba = (hex, alpha) => {
      const m = String(hex).replace("#", "");
      if (m.length !== 6) {
        return `rgba(255,255,255,${alpha})`;
      }
      const r = Number.parseInt(m.slice(0, 2), 16);
      const g = Number.parseInt(m.slice(2, 4), 16);
      const b = Number.parseInt(m.slice(4, 6), 16);
      return `rgba(${r},${g},${b},${alpha})`;
    };

    const palette = ["#76ceff", "#7dbbff", "#8aabff", "#f8b36a", "#7cf0da", "#b8bfff", "#82d4ff"];
    const center = (stageCount - 1) / 2;
    const points = Array.from({ length: stageCount }, (_, i) => ({
      x: (i - center) * 2.2,
      y: (i % 2 === 0 ? -1 : 1) * (0.88 + ((i % 3) * 0.12)),
      z: Math.sin(i * 0.85) * 1.05,
      color: palette[i % palette.length],
    }));

    const defaultRoute = Array.from({ length: stageCount }, (_, i) => i);
    const normalizeRoute = (route) => {
      if (!Array.isArray(route) || !route.length) {
        return [...defaultRoute];
      }
      const out = [];
      route.forEach((value) => {
        const idx = Number(value);
        if (!Number.isInteger(idx)) {
          return;
        }
        if (idx < 0 || idx >= stageCount) {
          return;
        }
        if (!out.length || out[out.length - 1] !== idx) {
          out.push(idx);
        }
      });
      return out.length >= 2 ? out : [...defaultRoute];
    };

    const routeOrderMap = (route) => {
      const map = new Map();
      route.forEach((idx, order) => {
        if (!map.has(idx)) {
          map.set(idx, order);
        }
      });
      return map;
    };
    const state = {
      activeIndex: 0,
      running: false,
      runStart: 0,
      runRequest: "",
      requestText: "",
      phase: 0,
      pointerX: 0,
      pointerY: 0,
      paused: false,
      route: [...defaultRoute],
      routeOrder: routeOrderMap(defaultRoute),
      routeProgress: 0,
      segmentMs: 1100,
    };

    let raf = 0;
    let width = 0;
    let height = 0;
    let dpr = 1;
    let ro = null;
    const destroyers = [];

    const notifyStep = (idx, routeStep = 0, routeLength = Math.max(1, state.route.length - 1), route = state.route) => {
      const labels = getLabels();
      const safe = clamp(idx, 0, stageCount - 1);
      onStep({
        stageIndex: safe,
        label: labels[safe] || `Step ${safe + 1}`,
        routeStep,
        routeLength,
        progress: routeLength > 0 ? clamp(routeStep / routeLength, 0, 1) : 1,
        route: Array.isArray(route) ? [...route] : [...state.route],
      });
    };

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      if (!rect.width || !rect.height) {
        return;
      }
      dpr = clamp(window.devicePixelRatio || 1, 1, 2);
      width = rect.width;
      height = rect.height;
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const project = (pt, now) => {
      const drift = Math.sin(now * 0.00022) * 0.16;
      const angY = drift + state.pointerX * 0.14;
      const angX = Math.sin(now * 0.00019) * 0.05 + state.pointerY * 0.08;

      const cosY = Math.cos(angY);
      const sinY = Math.sin(angY);
      const cosX = Math.cos(angX);
      const sinX = Math.sin(angX);

      const y1 = pt.y * cosX - pt.z * sinX;
      const z1 = pt.y * sinX + pt.z * cosX;
      const x2 = pt.x * cosY - z1 * sinY;
      const z2 = pt.x * sinY + z1 * cosY;

      const depth = 580 + z2 * 90;
      const perspective = 620 / Math.max(260, depth);
      const sx = width * 0.5 + x2 * 112 * perspective;
      const sy = height * 0.5 + y1 * 86 * perspective;
      const r = 4 + 8.6 * perspective;
      return { x: sx, y: sy, r, p: perspective, z: z2 };
    };

    const cubicPoint = (a, b, t) => {
      const c1 = { x: lerp(a.x, b.x, 0.32), y: a.y - 0.7, z: a.z + 0.65 };
      const c2 = { x: lerp(a.x, b.x, 0.68), y: b.y + 0.7, z: b.z + 0.65 };
      const mt = 1 - t;
      return {
        x: (mt * mt * mt * a.x) + (3 * mt * mt * t * c1.x) + (3 * mt * t * t * c2.x) + (t * t * t * b.x),
        y: (mt * mt * mt * a.y) + (3 * mt * mt * t * c1.y) + (3 * mt * t * t * c2.y) + (t * t * t * b.y),
        z: (mt * mt * mt * a.z) + (3 * mt * mt * t * c1.z) + (3 * mt * t * t * c2.z) + (t * t * t * b.z),
      };
    };

    const drawBackground = () => {
      const grad = ctx.createLinearGradient(0, 0, width, height);
      grad.addColorStop(0, "rgba(7, 16, 31, 0.16)");
      grad.addColorStop(1, "rgba(5, 11, 22, 0.02)");
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, width, height);

      const lines = 9;
      ctx.save();
      ctx.strokeStyle = "rgba(123, 178, 240, 0.11)";
      ctx.lineWidth = 1;
      for (let i = 1; i < lines; i += 1) {
        const y = (height / lines) * i;
        ctx.beginPath();
        ctx.moveTo(18, y);
        ctx.lineTo(width - 18, y);
        ctx.stroke();
      }
      ctx.restore();
    };

    const drawLink = (a, b, now) => {
      const pa = project(a, now);
      const pb = project(b, now);
      const g = ctx.createLinearGradient(pa.x, pa.y, pb.x, pb.y);
      g.addColorStop(0, "rgba(126, 184, 255, 0.2)");
      g.addColorStop(1, "rgba(92, 146, 238, 0.14)");
      ctx.strokeStyle = g;
      ctx.lineWidth = Math.max(1, (pa.p + pb.p) * 1.7);
      ctx.beginPath();
      ctx.moveTo(pa.x, pa.y);
      ctx.lineTo(pb.x, pb.y);
      ctx.stroke();
    };

    const drawNode = (pt, idx, now) => {
      const p = project(pt, now);
      const active = idx === state.activeIndex;
      const order = state.routeOrder.get(idx);
      const inRoute = Number.isInteger(order);
      const complete = inRoute && order < state.routeProgress;
      const glow = active ? 0.52 : complete ? 0.26 : inRoute ? 0.14 : 0.08;
      const ringColor = active ? "#a8dcff" : complete ? "#85b4ff" : inRoute ? "#4f5f80" : "#34455f";

      ctx.save();
      ctx.shadowColor = hexToRgba(pt.color, glow);
      ctx.shadowBlur = active ? 30 : 18;
      ctx.fillStyle = hexToRgba(pt.color, complete ? 0.82 : inRoute ? 0.62 : 0.36);
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fill();

      ctx.lineWidth = active ? 2.4 : 1.4;
      ctx.strokeStyle = ringColor;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r + 2.1, 0, Math.PI * 2);
      ctx.stroke();
      ctx.restore();
    };

    const drawPackets = (now) => {
      if (!state.running) {
        return;
      }

      const route = state.route;
      const segmentCount = Math.max(1, route.length - 1);
      const totalMs = Math.max(state.segmentMs, segmentCount * state.segmentMs);
      const elapsed = clamp(now - state.runStart, 0, totalMs + 1200);
      const progress = clamp(elapsed / totalMs, 0, 1);
      const easedProgress = easeInOut(progress);
      const pathPos = easedProgress * segmentCount;
      const routeStep = clamp(Math.floor(pathPos), 0, segmentCount);

      if (routeStep !== state.routeProgress) {
        state.routeProgress = routeStep;
        state.activeIndex = route[routeStep];
        notifyStep(state.activeIndex, routeStep, segmentCount, route);
      }

      for (let i = 0; i < 6; i += 1) {
        const offset = i * 0.07;
        const t = pathPos - offset;
        if (t <= 0 || t >= segmentCount) {
          continue;
        }
        const seg = clamp(Math.floor(t), 0, segmentCount - 1);
        const localT = t - seg;
        const from = points[route[seg]];
        const to = points[route[seg + 1]];
        const world = cubicPoint(from, to, localT);
        const pp = project(world, now);
        const intensity = 1 - offset * 0.95;

        ctx.save();
        ctx.shadowColor = `rgba(113, 190, 255, ${0.48 * intensity})`;
        ctx.shadowBlur = 24 * intensity;
        ctx.fillStyle = `rgba(146, 212, 255, ${0.88 * intensity})`;
        ctx.beginPath();
        ctx.arc(pp.x, pp.y, Math.max(2.6, pp.r * 0.46), 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
      }

      if (elapsed >= totalMs + 1000) {
        state.running = false;
        state.routeProgress = segmentCount;
        state.activeIndex = route[segmentCount];
        notifyStep(state.activeIndex, state.routeProgress, segmentCount, route);
      }
    };

    const draw = (now) => {
      if (!width || !height) {
        resize();
      }
      ctx.clearRect(0, 0, width, height);
      drawBackground();

      for (let i = 0; i < points.length - 1; i += 1) {
        drawLink(points[i], points[i + 1], now);
      }

      for (let i = 0; i < state.route.length - 1; i += 1) {
        const from = points[state.route[i]];
        const to = points[state.route[i + 1]];
        const pa = project(from, now);
        const pb = project(to, now);
        const g = ctx.createLinearGradient(pa.x, pa.y, pb.x, pb.y);
        g.addColorStop(0, "rgba(168, 221, 255, 0.34)");
        g.addColorStop(1, "rgba(117, 176, 255, 0.28)");
        ctx.strokeStyle = g;
        ctx.lineWidth = Math.max(1.2, (pa.p + pb.p) * 2.2);
        ctx.beginPath();
        ctx.moveTo(pa.x, pa.y);
        ctx.lineTo(pb.x, pb.y);
        ctx.stroke();
      }

      drawPackets(now);

      points.forEach((pt, idx) => drawNode(pt, idx, now));

      if (!state.running) {
        const pulse = 0.5 + Math.sin(now * 0.0022) * 0.5;
        const origin = project(points[state.route[0]], now);
        ctx.save();
        ctx.strokeStyle = `rgba(116, 194, 255, ${0.14 + pulse * 0.2})`;
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.arc(origin.x, origin.y, origin.r + 8 + pulse * 8, 0, Math.PI * 2);
        ctx.stroke();
        ctx.restore();
      }
    };

    const frame = (now) => {
      if (!state.paused) {
        state.phase += 0.008;
        draw(now);
      }
      raf = window.requestAnimationFrame(frame);
    };

    const onMove = (ev) => {
      const rect = canvas.getBoundingClientRect();
      if (!rect.width || !rect.height) {
        return;
      }
      const nx = ((ev.clientX - rect.left) / rect.width) * 2 - 1;
      const ny = ((ev.clientY - rect.top) / rect.height) * 2 - 1;
      state.pointerX = clamp(nx, -1, 1);
      state.pointerY = clamp(ny, -1, 1);
    };

    const onLeave = () => {
      state.pointerX = 0;
      state.pointerY = 0;
    };

    resize();
    if ("ResizeObserver" in window) {
      ro = new ResizeObserver(resize);
      ro.observe(canvas);
    } else {
      window.addEventListener("resize", resize);
      destroyers.push(() => window.removeEventListener("resize", resize));
    }

    canvas.addEventListener("pointermove", onMove);
    canvas.addEventListener("pointerleave", onLeave);
    destroyers.push(() => canvas.removeEventListener("pointermove", onMove));
    destroyers.push(() => canvas.removeEventListener("pointerleave", onLeave));

    notifyStep(defaultRoute[0], 0, Math.max(1, defaultRoute.length - 1), defaultRoute);
    raf = window.requestAnimationFrame(frame);

    return {
      play(input) {
        const opts = (input && typeof input === "object")
          ? input
          : { requestText: input };
        const cleaned = String(opts.requestText || "").trim();
        const route = normalizeRoute(opts.route);
        state.requestText = cleaned || "Analyze this request path";
        state.runRequest = state.requestText;
        state.route = route;
        state.routeOrder = routeOrderMap(route);
        state.segmentMs = clamp(Number(opts.segmentMs) || 1100, 640, 2400);
        state.runStart = performance.now();
        state.running = true;
        state.routeProgress = 0;
        state.activeIndex = route[0];
        notifyStep(route[0], 0, Math.max(1, route.length - 1), route);
      },
      pause() {
        state.paused = true;
      },
      resume() {
        state.paused = false;
      },
      destroy() {
        window.cancelAnimationFrame(raf);
        if (ro) {
          ro.disconnect();
        }
        destroyers.forEach((fn) => fn());
      },
    };
  }

  function setupFlowVisualizers() {
    const roots = Array.from(document.querySelectorAll("[data-flow-visualizer]"));
    if (!roots.length) {
      return;
    }

    const reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const scenarioDefs = {
      safe: {
        route: [0, 1, 2, 3, 4, 5],
        segmentMs: 1020,
        title: { en: "Standard path", ja: "通常ルート" },
        trace: {
          en: [
            "Request normalized (source/user/channel).",
            "Context + selector build the execution plan.",
            "Risk scored as LOW.",
            "Policy allows execution without owner gate.",
            "Tool executes and artifacts are collected.",
            "Final response and audit trail returned.",
          ],
          ja: [
            "入力を正規化（source/user/channel）。",
            "文脈構築とセレクタで実行計画を作成。",
            "リスク判定はLOW。",
            "承認なしで実行可能とポリシー判定。",
            "ツールを実行して成果物を収集。",
            "最終応答と監査ログを返却。",
          ],
        },
      },
      approval: {
        route: [0, 1, 2, 3, 4, 5],
        segmentMs: 1160,
        title: { en: "Approval required", ja: "承認必須ルート" },
        trace: {
          en: [
            "Request normalized.",
            "High-impact action detected by selector.",
            "Risk scored as HIGH/CRITICAL.",
            "Approval request created (pending).",
            "Owner decision received within TTL.",
            "Tool executes after approval.",
            "Result submitted back to Core run.",
            "Final response + audit completed.",
          ],
          ja: [
            "入力を正規化。",
            "高影響アクションをセレクタが検知。",
            "リスク判定はHIGH/CRITICAL。",
            "承認リクエストを作成（pending）。",
            "TTL内にOwner判断を受信。",
            "承認後にツールを実行。",
            "結果をCore実行へ返却。",
            "最終応答と監査を確定。",
          ],
        },
      },
      blocked: {
        route: [0, 1, 2, 3, 5],
        segmentMs: 980,
        title: { en: "Blocked path", ja: "ブロックルート" },
        trace: {
          en: [
            "Request normalized.",
            "Risky action identified.",
            "Risk scored as HIGH/CRITICAL.",
            "Policy denies request (or approval expires).",
            "Tool execution blocked.",
            "Blocked response returned with reason.",
          ],
          ja: [
            "入力を正規化。",
            "危険操作を検知。",
            "リスク判定はHIGH/CRITICAL。",
            "ポリシー拒否（または承認期限切れ）。",
            "ツール実行をブロック。",
            "理由付きでブロック応答を返却。",
          ],
        },
      },
    };

    roots.forEach((root) => {
      const stages = Array.from(root.querySelectorAll("[data-flow-stage]"));
      const progress = root.querySelector("[data-flow-progress]");
      const status = root.querySelector("[data-flow-status]");
      const replayButton = root.querySelector("[data-flow-replay]");
      const runButton = root.querySelector("[data-flow-run]");
      const requestInput = root.querySelector("[data-flow-request]");
      const requestEcho = root.querySelector("[data-flow-request-echo]");
      const nodeInfo = root.querySelector("[data-flow-node-info]");
      const canvas = root.querySelector("[data-flow-canvas]");
      const traceList = root.querySelector("[data-flow-trace]");
      const scenarioButtons = Array.from(root.querySelectorAll("[data-flow-scenario]"));
      if (!stages.length) {
        return;
      }

      let timer = 0;
      let traceTimer = 0;
      let scene = null;
      let activeScenarioKey = "safe";
      let traceStep = 0;
      let flowState = {
        stageIndex: 0,
        routeStep: 0,
        routeLength: Math.max(1, stages.length - 1),
        route: Array.from({ length: stages.length }, (_, i) => i),
        label: "",
      };

      const currentLang = () => normalizeLang(document.documentElement.lang || detectLang());
      const labels = () => stages.map((stage, index) => {
        const lang = currentLang();
        const key = lang === "ja" ? "flowLabelJa" : "flowLabelEn";
        const fallback = stage.getAttribute("data-flow-label") || `Step ${index + 1}`;
        return stage.dataset[key] || fallback;
      });
      const getScenario = () => scenarioDefs[activeScenarioKey] || scenarioDefs.safe;

      const updateRequestUI = (value) => {
        const text = String(value || "").trim();
        if (requestEcho) {
          requestEcho.textContent = text || (currentLang() === "ja" ? "入力待機中..." : "Waiting for request...");
        }
      };

      const traceItems = () => Array.from(root.querySelectorAll(".flow-trace-item"));
      const setTraceStep = (idx) => {
        const items = traceItems();
        if (!items.length) {
          return;
        }
        const safe = Math.max(0, Math.min(idx, items.length - 1));
        items.forEach((item, n) => {
          item.classList.toggle("is-complete", n < safe);
          item.classList.toggle("is-active", n === safe);
          item.classList.toggle("is-pending", n > safe);
        });
        traceStep = safe;
      };

      const buildTrace = () => {
        if (!traceList) {
          return;
        }
        const scenario = getScenario();
        const lines = scenario.trace[currentLang()] || scenario.trace.en;
        traceList.innerHTML = lines
          .map((line, index) => `<li class="flow-trace-item is-pending"><span class="k">${String(index + 1).padStart(2, "0")}</span><span class="v">${line}</span></li>`)
          .join("");
        setTraceStep(0);
      };

      const render = () => {
        const scenario = getScenario();
        const route = Array.isArray(flowState.route) && flowState.route.length ? flowState.route : scenario.route;
        const routeMap = new Map(route.map((stageIndex, order) => [stageIndex, order]));
        const routeStep = Math.max(0, Math.min(flowState.routeStep, flowState.routeLength || 0));

        stages.forEach((stage, index) => {
          const order = routeMap.has(index) ? routeMap.get(index) : -1;
          stage.classList.toggle("is-active", index === flowState.stageIndex);
          stage.classList.toggle("is-complete", order !== -1 && order < routeStep);
        });

        if (progress) {
          const ratio = flowState.routeLength > 0
            ? Math.max(0, Math.min(flowState.routeStep / flowState.routeLength, 1))
            : 1;
          const pct = ratio * 100;
          progress.style.width = `${pct}%`;
        }

        const label = flowState.label || labels()[flowState.stageIndex] || `Step ${flowState.stageIndex + 1}`;
        const title = scenario.title[currentLang()] || scenario.title.en;
        if (status) {
          status.textContent = `${title} · ${label}`;
        }
        if (nodeInfo) {
          nodeInfo.textContent = label;
        }
        scenarioButtons.forEach((btn) => {
          const key = btn.getAttribute("data-flow-scenario") || "";
          btn.classList.toggle("is-active", key === activeScenarioKey);
        });
      };

      const stopFallback = () => {
        if (timer) {
          window.clearInterval(timer);
          timer = 0;
        }
      };

      const stopTraceTimeline = () => {
        if (traceTimer) {
          window.clearInterval(traceTimer);
          traceTimer = 0;
        }
      };

      const startFallback = () => {
        stopFallback();
        if (reduceMotion) {
          return;
        }
        const scenario = getScenario();
        const route = scenario.route;
        let routeStep = 0;
        flowState = {
          stageIndex: route[0],
          routeStep: 0,
          routeLength: Math.max(1, route.length - 1),
          route,
          label: labels()[route[0]] || `Step ${route[0] + 1}`,
        };
        render();
        timer = window.setInterval(() => {
          routeStep += 1;
          const maxStep = Math.max(1, route.length - 1);
          const safeStep = Math.max(0, Math.min(routeStep, maxStep));
          flowState = {
            stageIndex: route[safeStep],
            routeStep: safeStep,
            routeLength: maxStep,
            route,
            label: labels()[route[safeStep]] || `Step ${route[safeStep] + 1}`,
          };
          render();
          const nextTrace = Math.round((safeStep / maxStep) * Math.max(0, traceItems().length - 1));
          if (nextTrace > traceStep) {
            setTraceStep(nextTrace);
          }
          if (safeStep >= maxStep) {
            stopFallback();
          }
        }, scenario.segmentMs);
      };

      const runTraceTimeline = () => {
        stopTraceTimeline();
        const items = traceItems();
        if (items.length <= 1) {
          return;
        }
        const scenario = getScenario();
        const totalMs = Math.max(1200, scenario.segmentMs * Math.max(1, scenario.route.length - 1) + 800);
        const tickMs = Math.max(340, Math.round(totalMs / items.length));
        let idx = 0;
        traceTimer = window.setInterval(() => {
          idx += 1;
          if (idx >= items.length) {
            setTraceStep(items.length - 1);
            stopTraceTimeline();
            return;
          }
          setTraceStep(idx);
        }, tickMs);
      };

      const onSceneStep = (event) => {
        if (!event || typeof event !== "object") {
          return;
        }
        flowState = {
          stageIndex: Math.max(0, Math.min(Number(event.stageIndex) || 0, stages.length - 1)),
          routeStep: Math.max(0, Number(event.routeStep) || 0),
          routeLength: Math.max(0, Number(event.routeLength) || 0),
          route: Array.isArray(event.route) ? event.route : getScenario().route,
          label: event.label || "",
        };
        render();
        const itemsCount = traceItems().length;
        if (itemsCount > 1) {
          const ratio = flowState.routeLength > 0
            ? Math.max(0, Math.min(flowState.routeStep / flowState.routeLength, 1))
            : 1;
          const next = Math.round(ratio * (itemsCount - 1));
          if (next > traceStep) {
            setTraceStep(next);
          }
        }
      };

      const replay = () => {
        stopFallback();
        stopTraceTimeline();
        buildTrace();
        const scenario = getScenario();
        const requestText = requestInput ? requestInput.value : "";
        updateRequestUI(requestText);
        flowState = {
          stageIndex: scenario.route[0],
          routeStep: 0,
          routeLength: Math.max(1, scenario.route.length - 1),
          route: scenario.route,
          label: labels()[scenario.route[0]] || `Step ${scenario.route[0] + 1}`,
        };
        render();

        if (scene) {
          scene.play({
            requestText,
            route: scenario.route,
            segmentMs: scenario.segmentMs,
          });
        } else {
          startFallback();
        }
        runTraceTimeline();
      };

      if (canvas && !reduceMotion) {
        scene = createFlowCanvasRuntime({
          canvas,
          stageCount: stages.length,
          getLabels: labels,
          onStep: onSceneStep,
        });
      }

      const applyInputPlaceholder = () => {
        if (!requestInput) {
          return;
        }
        const lang = currentLang();
        const key = lang === "ja" ? "placeholderJa" : "placeholderEn";
        const placeholder = requestInput.dataset[key] || requestInput.getAttribute("placeholder") || "";
        requestInput.setAttribute("placeholder", placeholder);
      };

      const setScenario = (key) => {
        activeScenarioKey = scenarioDefs[key] ? key : "safe";
        buildTrace();
        render();
      };

      setScenario("safe");
      applyInputPlaceholder();
      replay();

      if (runButton) {
        runButton.addEventListener("click", replay);
      }
      if (replayButton) {
        replayButton.addEventListener("click", replay);
      }
      if (requestInput) {
        requestInput.addEventListener("keydown", (ev) => {
          if (ev.key === "Enter") {
            ev.preventDefault();
            replay();
          }
        });
        requestInput.addEventListener("input", () => {
          updateRequestUI(requestInput.value);
        });
      }
      scenarioButtons.forEach((btn) => {
        btn.addEventListener("click", () => {
          const key = btn.getAttribute("data-flow-scenario") || "safe";
          setScenario(key);
          replay();
        });
      });

      root.addEventListener("mouseenter", stopFallback);
      root.addEventListener("mouseleave", () => {
        if (!scene) {
          startFallback();
        }
      });

      document.addEventListener("visibilitychange", () => {
        if (document.hidden) {
          stopFallback();
          stopTraceTimeline();
          if (scene) {
            scene.pause();
          }
        } else {
          if (scene) {
            scene.resume();
          } else {
            startFallback();
          }
        }
      });

      window.addEventListener("yonerai:lang-changed", () => {
        applyInputPlaceholder();
        buildTrace();
        render();
      });
    });
  }

  function animateHorizontalScroll(el, to, durationMs) {
    return new Promise((resolve) => {
      const from = el.scrollLeft;
      const start = performance.now();

      const step = (now) => {
        const t = Math.min(1, (now - start) / durationMs);
        const eased = t < 0.5
          ? 4 * t * t * t
          : 1 - Math.pow(-2 * t + 2, 3) / 2;
        el.scrollLeft = from + (to - from) * eased;
        if (t < 1) {
          requestAnimationFrame(step);
        } else {
          resolve();
        }
      };

      requestAnimationFrame(step);
    });
  }

  async function setupMobileTopbarGuide() {
    try {
      const isMobile = window.matchMedia("(max-width: 760px)").matches;
      if (!isMobile) {
        return;
      }

      const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      if (reduce) {
        return;
      }

      const nav = document.querySelector(".oa-global-nav");
      if (!nav) {
        return;
      }

      if (localStorage.getItem(TOPBAR_HINT_KEY) === "1") {
        return;
      }

      const max = Math.max(0, nav.scrollWidth - nav.clientWidth);
      if (max < 40) {
        localStorage.setItem(TOPBAR_HINT_KEY, "1");
        return;
      }

      localStorage.setItem(TOPBAR_HINT_KEY, "1");
      await new Promise((r) => setTimeout(r, 900));
      await animateHorizontalScroll(nav, Math.min(max, Math.round(max * 0.45)), 2400);
      await new Promise((r) => setTimeout(r, 220));
      await animateHorizontalScroll(nav, 0, 2100);
    } catch {
      // best-effort onboarding hint
    }
  }

  function init() {
    const lang = detectLang();
    setLangCookie(lang);
    applyLang(lang);
    showCookieConsent(lang);
    setupLangControls();
    setupAuthEntries();
    markActiveNav();
    window.addEventListener("hashchange", markActiveNav);
    setupTopbarScrollState();
    setupAnchorNavigation();
    setupPointerGlow();
    setupCardLinks();
    setupFlowVisualizers();
    setupReveal();
    fitRailLinksToLongest();
    window.requestAnimationFrame(fitRailLinksToLongest);
    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(fitRailLinksToLongest).catch(() => {});
    }
    let railResizeTimer = 0;
    window.addEventListener("resize", () => {
      window.clearTimeout(railResizeTimer);
      railResizeTimer = window.setTimeout(fitRailLinksToLongest, 120);
    }, { passive: true });
    setupMobileTopbarGuide();
    window.requestAnimationFrame(() => {
      document.body.classList.remove("preload");
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  window.addEventListener("pageshow", () => {
    document.body.classList.remove("preload");
  });
})();

