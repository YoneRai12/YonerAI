(() => {
  "use strict";

  const VERSION = "20260601-runtime-feed-contract-stable";

  const DEFAULT_STATES = {
    operational: { severity: 0, color: "#25c39a", label: { ja: "稼働中", en: "Operational" } },
    alpha_only: { severity: 10, color: "#a9b0ba", label: { ja: "alpha のみ", en: "Alpha only" } },
    not_started: { severity: 20, color: "#a9b0ba", label: { ja: "準備中", en: "Preparing" } },
    maintenance: { severity: 30, color: "#f97316", label: { ja: "メンテナンス", en: "Maintenance" } },
    degraded: { severity: 40, color: "#f6bd3f", label: { ja: "性能低下", en: "Degraded" } },
    partial_outage: { severity: 50, color: "#ff7a59", label: { ja: "一部障害", en: "Partial outage" } },
    major_outage: { severity: 60, color: "#ef5b4a", label: { ja: "重大障害", en: "Major outage" } },
    resolved: { severity: 0, color: "#25c39a", label: { ja: "解決済み", en: "Resolved" } },
    monitoring: { severity: 45, color: "#3a9dff", label: { ja: "監視中", en: "Monitoring" } },
    identified: { severity: 42, color: "#f6bd3f", label: { ja: "原因特定", en: "Identified" } },
    investigating: { severity: 48, color: "#ff6b6b", label: { ja: "調査中", en: "Investigating" } },
  };
  const COPY = {
    ja: {
      lang: "ja",
      title: "YonerAIのステータス",
      metaDescription: "YonerAI Status は、YonerAI サービスの準備中ステータスを表示します。監視運用はまだ開始していません。",
      subscribe: "最新情報を受け取るには登録してください",
      themeLight: "ライト",
      themeDark: "ダーク",
      themeLabel: "テーマを切り替え",
      noticeTitle: "ステータス監視の準備",
      noticeCopy: "YonerAIのステータス監視機能はまだ稼働していません。稼働時間、インシデント、ライブチェックのデータが収集されていないため、すべてのコンポーネントが灰色で表示されています。",
      systemStatus: "システムステータス",
      previousRange: "前の期間",
      nextRange: "次の期間",
      range: "2026年2月〜2026年5月",
      pastDays: "過去90日間。",
      historyHint: "稼働履歴はまだ存在しません。",
      categoryLabel: "YonerAI ステータス分類",
      historyButton: "履歴を表示",
      incidentsTitle: "過去の事件",
      incidentTime: "運用開始前",
      incidentTitle: "公開中の障害履歴はありません",
      incidentCopy: "YonerAIはまだ公式な運用を開始していないため、報告すべき具体的な事件や解決事例はありません。",
      footerPowered: "YonerAI搭載",
      footerCopy: "可用性に関する指標はまだ収集されていません。実際の監視が接続されるまで、すべてのカテゴリはグレー表示のままです。",
      componentSingular: "component",
      componentPlural: "components",
      scaleStart: "90日前",
      scaleEnd: "今日",
      scaleUptime: "稼働率: データなし",
      currentFact: "現在の事実",
      monitoring: "監視",
      publicClaim: "公開claim",
      notConnected: "未接続",
      noClaim: "本番運用は未主張",
      target: "対象",
      date: "日付",
      state: "表示状態",
      source: "ソース",
      detail: "詳細",
      back: "戻る",
      affected: "影響を受けたコンポーネント",
      updates: "Updates",
      affectedOne: "affected component",
      incidentTimeline: "障害タイムラインを見る",
      allUpdates: "すべての更新を見る",
      fallbackStatusMessage: "これは status feed から生成されたステータス表示です。",
      tooltipNoData: "この日のデータは存在しません。",
      subscribeAlert: "準備中: ステータス通知の購読機能はまだありません。",
      historyAlert: "準備中: 公開できる稼働履歴はまだありません。",
      historyHintAlert: "過去90日分の表示枠だけがあります。実データはまだ接続していません。",
      locale: "ja-JP",
    },
    en: {
      lang: "en",
      title: "YonerAI Status",
      metaDescription: "YonerAI Status shows the current preparation state for YonerAI services. Monitoring is not operating yet.",
      subscribe: "Subscribe to updates",
      themeLight: "Light",
      themeDark: "Dark",
      themeLabel: "Toggle theme",
      noticeTitle: "Preparing status monitoring",
      noticeCopy: "YonerAI status monitoring is not operating yet. All components are shown in gray because uptime, incidents, and live checks are not being collected.",
      systemStatus: "System status",
      previousRange: "Previous range",
      nextRange: "Next range",
      range: "Feb 2026 - May 2026",
      pastDays: "Past 90 days.",
      historyHint: "No uptime history exists yet.",
      categoryLabel: "YonerAI status categories",
      historyButton: "View history",
      incidentsTitle: "Past incidents",
      incidentTime: "Before operations",
      incidentTitle: "No public incident history",
      incidentCopy: "YonerAI has not started public status operations, so there are no factual incidents or resolutions to report.",
      footerPowered: "Powered by YonerAI",
      footerCopy: "Availability metrics are not collected yet. All categories stay gray until real monitoring is connected.",
      componentSingular: "component",
      componentPlural: "components",
      scaleStart: "90 days ago",
      scaleEnd: "Today",
      scaleUptime: "uptime: no data",
      currentFact: "Current fact",
      monitoring: "Monitoring",
      publicClaim: "Public claim",
      notConnected: "Not connected",
      noClaim: "No production operation claim",
      target: "Target",
      date: "Date",
      state: "Display state",
      source: "Source",
      detail: "detail",
      back: "Back",
      affected: "Affected components",
      updates: "Updates",
      affectedOne: "affected component",
      incidentTimeline: "View incident timeline",
      allUpdates: "View all updates",
      fallbackStatusMessage: "This status view is generated from the feed.",
      tooltipNoData: "No data exists for this day.",
      subscribeAlert: "Preparing: status subscriptions are not available yet.",
      historyAlert: "Preparing: no public uptime history exists yet.",
      historyHintAlert: "Only the 90-day UI frame exists. Real uptime data is not connected yet.",
      locale: "en-US",
    },
  };

  if (window.YonerAIStatusRuntime?.destroy) {
    window.YonerAIStatusRuntime.destroy();
  }

  const controller = new AbortController();
  const signal = controller.signal;
  const root = document.documentElement;
  const $ = (selector, base = document) => base.querySelector(selector);
  const $$ = (selector, base = document) => Array.from(base.querySelectorAll(selector));

  const runtime = {
    locale: detectLocale(),
    feed: null,
    rawFeed: null,
    feedSequence: 0,
    acceptedSequence: 0,
    bars: new Map(),
    interactionEpoch: 0,
    routeEpoch: 0,
    selected: null,
    selectedToken: 0,
    selectedTimer: 0,
    hovered: null,
    hoverNeighbors: [],
    tooltipKey: "",
    tooltipTarget: null,
    tooltipCurrent: null,
    tooltipFrame: 0,
    tooltipToken: 0,
    touchPinned: false,
    refreshTimer: 0,
    eventSource: null,
    cascadeUntil: 0,
    smokeRan: false,
    smokeRunning: false,
  };

  function t(key) {
    return (COPY[runtime.locale] || COPY.en)[key] || COPY.en[key] || key;
  }

  function detectLocale() {
    const path = location.pathname.toLowerCase();
    if (path === "/en" || path.startsWith("/en/")) return "en";
    if (path === "/jp" || path.startsWith("/jp/") || path === "/ja" || path.startsWith("/ja/")) return "ja";
    const languages = navigator.languages?.length ? navigator.languages : [navigator.language || ""];
    if (languages.some((language) => String(language).toLowerCase().startsWith("ja"))) return "ja";
    return Intl.DateTimeFormat().resolvedOptions().timeZone === "Asia/Tokyo" ? "ja" : "en";
  }

  function local(value, fallback = "") {
    if (value == null) return fallback;
    if (typeof value === "string") return value;
    if (Array.isArray(value)) return value.map((item) => local(item)).filter(Boolean).join(" ・ ");
    return value[runtime.locale] || value.en || value.ja || fallback;
  }

  function sid(value) {
    return String(value || "not_started").trim().toLowerCase();
  }

  function cssState(value) {
    return sid(value).replace(/_/g, "-").replace(/[^a-z0-9-]/g, "");
  }

  function esc(value) {
    return String(value == null ? "" : value).replace(/[&<>"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[char]);
  }

  function enc(value) {
    return encodeURIComponent(String(value));
  }

  function setText(id, value) {
    const node = document.getElementById(id);
    if (node) node.textContent = value;
  }

  function stateDef(state) {
    return runtime.feed?.states?.[sid(state)] || DEFAULT_STATES[sid(state)] || DEFAULT_STATES.not_started;
  }

  function stateLabel(state) {
    const def = stateDef(state);
    return local(def.label || def.labels, sid(state));
  }

  function stateColor(state) {
    return stateDef(state).color || DEFAULT_STATES.not_started.color;
  }

  function stateSeverity(state) {
    const severity = Number(stateDef(state).severity);
    return Number.isFinite(severity) ? severity : DEFAULT_STATES.not_started.severity;
  }

  function rgbFromHex(hex) {
    const clean = String(hex || "").replace("#", "").trim();
    if (!/^[0-9a-f]{6}$/i.test(clean)) return "169,176,186";
    return [
      parseInt(clean.slice(0, 2), 16),
      parseInt(clean.slice(2, 4), 16),
      parseInt(clean.slice(4, 6), 16),
    ].join(",");
  }

  function worstStatus(statuses) {
    return statuses.filter(Boolean).sort((a, b) => stateSeverity(b) - stateSeverity(a))[0] || "not_started";
  }

  function dateAdd(date, offset) {
    const next = new Date(`${date}T00:00:00Z`);
    next.setUTCDate(next.getUTCDate() + offset);
    return next.toISOString().slice(0, 10);
  }

  function formatDate(date) {
    return new Intl.DateTimeFormat(t("locale"), {
      timeZone: "UTC",
      year: "numeric",
      month: "long",
      day: "numeric",
    }).format(new Date(`${date}T00:00:00Z`));
  }

  function el(tag, className = "", text = null) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  function applyStaticCopy() {
    document.documentElement.lang = t("lang");
    document.title = t("title");
    const description = t("metaDescription");
    $("meta[name='description']")?.setAttribute("content", description);
    $("meta[property='og:title']")?.setAttribute("content", t("title"));
    $("meta[property='og:description']")?.setAttribute("content", description);
    $("meta[name='twitter:title']")?.setAttribute("content", t("title"));
    $("meta[name='twitter:description']")?.setAttribute("content", description);
    setText("subscribeButton", t("subscribe"));
    setText("noticeTitle", t("noticeTitle"));
    setText("noticeCopy", t("noticeCopy"));
    setText("systemStatusTitle", t("systemStatus"));
    setText("rangeLabel", t("range"));
    setText("pastDaysLabel", t("pastDays"));
    setText("historyHint", t("historyHint"));
    setText("historyButtonText", t("historyButton"));
    setText("incidentsTitle", t("incidentsTitle"));
    setText("incidentTime", t("incidentTime"));
    setText("incidentTitle", t("incidentTitle"));
    setText("incidentCopy", t("incidentCopy"));
    setText("footerPowered", t("footerPowered"));
    setText("footerCopy", t("footerCopy"));
    $("#rangePrev")?.setAttribute("aria-label", t("previousRange"));
    $("#rangeNext")?.setAttribute("aria-label", t("nextRange"));
    $("#categoryList")?.setAttribute("aria-label", t("categoryLabel"));
  }

  function configureTheme() {
    let theme = "light";
    try {
      const stored = localStorage.getItem("yonerai-status-theme");
      if (stored === "dark" || stored === "light") theme = stored;
    } catch (_) {}
    root.dataset.theme = theme;
    updateThemeToggle();
  }

  function updateThemeToggle() {
    const button = $("#themeToggle");
    const text = $("#themeToggleText");
    if (!button || !text) return;
    const dark = root.dataset.theme === "dark";
    button.setAttribute("aria-label", t("themeLabel"));
    button.setAttribute("title", t("themeLabel"));
    button.setAttribute("aria-pressed", String(dark));
    text.textContent = dark ? t("themeDark") : t("themeLight");
  }

  function toggleTheme() {
    root.dataset.theme = root.dataset.theme === "dark" ? "light" : "dark";
    try {
      localStorage.setItem("yonerai-status-theme", root.dataset.theme);
    } catch (_) {}
    updateThemeToggle();
  }

  function feedUrl() {
    const params = new URLSearchParams(location.search);
    const override = params.get("feed") || params.get("statusFeed");
    const cacheBust = params.get("cacheBust");
    if (override) {
      try {
        const url = new URL(override, location.href);
        if (url.origin === location.origin) return url.pathname + url.search;
      } catch (_) {}
    }
    const suffix = cacheBust ? `?v=${enc(cacheBust)}` : "";
    const legacyMockHash = /^#(?:status-test-|incident-test-)/.test(location.hash);
    const localPreviewHost =
      location.protocol === "file:" ||
      location.hostname === "localhost" ||
      location.hostname === "127.0.0.1" ||
      location.hostname === "";
    if (params.get("mockStatus") === "1" || (localPreviewHost && legacyMockHash)) {
      return `/status-feed.mock.json${suffix}`;
    }
    return `/status-feed.json${suffix}`;
  }

  function assertFeed(condition, message) {
    if (!condition) throw new Error(`Invalid status feed: ${message}`);
  }

  function validateLocalized(value, path) {
    assertFeed(
      typeof value === "string" || (value && typeof value === "object"),
      `${path} must be a string or localized object`
    );
  }

  function collectStateIds(raw) {
    const feedStateKeys = Array.isArray(raw.states) ? raw.states : Object.keys(raw.states || {});
    return new Set([...Object.keys(DEFAULT_STATES), ...feedStateKeys].map(sid));
  }

  function assertKnownState(stateIds, value, path) {
    if (value == null || value === "") return;
    assertFeed(stateIds.has(sid(value)), `${path} references unknown state "${value}"`);
  }

  function validateFeedShape(raw) {
    assertFeed(raw && typeof raw === "object" && !Array.isArray(raw), "root must be an object");
    assertFeed(raw.categories == null || Array.isArray(raw.categories), "categories must be an array");
    assertFeed(raw.incidents == null || Array.isArray(raw.incidents), "incidents must be an array");
    if (raw.range) {
      assertFeed(typeof raw.range === "object" && !Array.isArray(raw.range), "range must be an object");
      if (raw.range.start) assertFeed(/^\d{4}-\d{2}-\d{2}$/.test(raw.range.start), "range.start must be YYYY-MM-DD");
      if (raw.range.days != null) {
        const days = Number(raw.range.days);
        assertFeed(Number.isInteger(days) && days > 0 && days <= 366, "range.days must be an integer from 1 to 366");
      }
    }

    const stateIds = collectStateIds(raw);
    Object.entries(raw.states || {}).forEach(([key, value]) => {
      assertFeed(value && typeof value === "object" && !Array.isArray(value), `states.${key} must be an object`);
      validateLocalized(value.label || value.labels || key, `states.${key}.label`);
      if (value.severity != null) assertFeed(Number.isFinite(Number(value.severity)), `states.${key}.severity must be a number`);
      if (value.color != null) assertFeed(/^#[0-9a-f]{6}$/i.test(String(value.color)), `states.${key}.color must be a 6 digit hex color`);
    });

    const categoryIds = new Set();
    const componentIdsByCategory = new Map();
    (raw.categories || []).forEach((category, categoryIndex) => {
      const path = `categories[${categoryIndex}]`;
      assertFeed(category && typeof category === "object" && !Array.isArray(category), `${path} must be an object`);
      assertFeed(category.id, `${path}.id is required`);
      assertFeed(!categoryIds.has(String(category.id)), `${path}.id duplicates "${category.id}"`);
      categoryIds.add(String(category.id));
      validateLocalized(category.name || category.id, `${path}.name`);
      assertKnownState(stateIds, category.default_status || category.default_state, `${path}.default_status`);
      const components = category.components || category.children || [];
      assertFeed(Array.isArray(components), `${path}.components must be an array`);
      const componentIds = new Set();
      components.forEach((component, componentIndex) => {
        const componentPath = `${path}.components[${componentIndex}]`;
        assertFeed(component && typeof component === "object" && !Array.isArray(component), `${componentPath} must be an object`);
        assertFeed(component.id, `${componentPath}.id is required`);
        assertFeed(!componentIds.has(String(component.id)), `${componentPath}.id duplicates "${component.id}"`);
        componentIds.add(String(component.id));
        validateLocalized(component.name || component.id, `${componentPath}.name`);
        assertKnownState(
          stateIds,
          component.default_status || component.default_state || category.default_status || category.default_state,
          `${componentPath}.default_status`
        );
        const overrides = component.day_overrides || component.days || [];
        assertFeed(Array.isArray(overrides), `${componentPath}.day_overrides must be an array`);
        overrides.forEach((day, dayIndex) => {
          const dayPath = `${componentPath}.day_overrides[${dayIndex}]`;
          assertFeed(day && typeof day === "object" && !Array.isArray(day), `${dayPath} must be an object`);
          assertFeed(day.date == null || /^\d{4}-\d{2}-\d{2}$/.test(day.date), `${dayPath}.date must be YYYY-MM-DD`);
          if (day.index != null) assertFeed(Number.isInteger(Number(day.index)) && Number(day.index) >= 0, `${dayPath}.index must be a non-negative integer`);
          assertKnownState(stateIds, day.status || day.state, `${dayPath}.status`);
        });
      });
      componentIdsByCategory.set(String(category.id), componentIds);
    });

    const incidentIds = new Set();
    (raw.incidents || []).forEach((incident, incidentIndex) => {
      const path = `incidents[${incidentIndex}]`;
      assertFeed(incident && typeof incident === "object" && !Array.isArray(incident), `${path} must be an object`);
      assertFeed(incident.id, `${path}.id is required`);
      assertFeed(!incidentIds.has(String(incident.id)), `${path}.id duplicates "${incident.id}"`);
      incidentIds.add(String(incident.id));
      validateLocalized(incident.title || incident.id, `${path}.title`);
      assertKnownState(stateIds, incident.state, `${path}.state`);
      assertKnownState(stateIds, incident.impact, `${path}.impact`);
      if (incident.date) assertFeed(/^\d{4}-\d{2}-\d{2}$/.test(incident.date), `${path}.date must be YYYY-MM-DD`);
      if (incident.category_id) assertFeed(categoryIds.has(String(incident.category_id)), `${path}.category_id references unknown category "${incident.category_id}"`);
      if (incident.component_id && incident.category_id) {
        const componentIds = componentIdsByCategory.get(String(incident.category_id)) || new Set();
        assertFeed(componentIds.has(String(incident.component_id)), `${path}.component_id references unknown component "${incident.component_id}"`);
      }
      const affected = Array.isArray(incident.affected) ? incident.affected : (incident.affected ? [incident.affected] : []);
      affected.forEach((item, affectedIndex) => {
        const affectedPath = `${path}.affected[${affectedIndex}]`;
        assertFeed(item && typeof item === "object" && !Array.isArray(item), `${affectedPath} must be an object`);
        assertFeed(item.segments == null || Array.isArray(item.segments), `${affectedPath}.segments must be an array`);
        (item.segments || []).forEach((segment, segmentIndex) => {
          const segmentPath = `${affectedPath}.segments[${segmentIndex}]`;
          assertFeed(segment && typeof segment === "object" && !Array.isArray(segment), `${segmentPath} must be an object`);
          assertKnownState(stateIds, segment.state || segment.status, `${segmentPath}.state`);
          if (segment.percent != null) assertFeed(Number(segment.percent) > 0, `${segmentPath}.percent must be positive`);
          if (segment.weight != null) assertFeed(Number(segment.weight) > 0, `${segmentPath}.weight must be positive`);
        });
      });
      (incident.updates || []).forEach((update, updateIndex) => {
        const updatePath = `${path}.updates[${updateIndex}]`;
        assertFeed(update && typeof update === "object" && !Array.isArray(update), `${updatePath} must be an object`);
        assertKnownState(stateIds, update.status, `${updatePath}.status`);
        validateLocalized(update.title || update.label || update.status || "update", `${updatePath}.title`);
      });
    });

    (raw.categories || []).forEach((category) => {
      (category.components || category.children || []).forEach((component) => {
        (component.day_overrides || component.days || []).forEach((day) => {
          if (day.incident_id) assertFeed(incidentIds.has(String(day.incident_id)), `component ${component.id} references unknown incident "${day.incident_id}"`);
        });
      });
    });
    return true;
  }

  function validateFeed(raw) {
    validateFeedShape(raw);
    return { ok: true, schema: raw.schema_version || "yonerai.status.feed.v1" };
  }

  function sameOriginHref(url) {
    const parsed = new URL(url, location.href);
    if (parsed.origin !== location.origin) {
      throw new Error(`Status feed URL must be same-origin: ${parsed.href}`);
    }
    return parsed.href;
  }

  function runtimeError(error) {
    return {
      name: error?.name || "Error",
      message: error?.message || String(error),
    };
  }

  async function refresh() {
    try {
      root.dataset.statusRuntime = runtime.feed ? "refreshing" : "loading";
      root.dataset.statusFeedUrl = feedUrl();
      await reload(feedUrl(), { animate: false, source: "refresh" });
    } catch (error) {
      root.dataset.statusRuntime = runtime.feed ? "feed-error" : "error";
      root.dataset.statusFeedError = error.message || String(error);
      console.error("YonerAI status feed failed", error);
    }
  }

  function normalizeFeed(raw) {
    if (!raw || typeof raw !== "object") throw new Error("Invalid status feed");
    validateFeedShape(raw);
    const rangeStart = raw.range?.start || "2026-02-27";
    const dayCount = Number(raw.range?.days || 90);
    const dates = Array.from({ length: dayCount }, (_, index) => dateAdd(rangeStart, index));
    const states = normalizeStates(raw.states || {});
    const incidents = new Map((raw.incidents || []).map((incident) => [String(incident.id), incident]));
    const categories = (raw.categories || []).map((category) => normalizeCategory(category, dates));
    return {
      raw,
      states,
      incidents,
      categories,
      range: { start: rangeStart, days: dayCount, dates },
      meta: raw.meta || {},
      schema_version: raw.schema_version || "yonerai.status.feed.v1",
    };
  }

  function normalizeStates(states) {
    const normalized = { ...DEFAULT_STATES };
    if (Array.isArray(states)) {
      states.forEach((value) => {
        const key = sid(value);
        normalized[key] = {
          ...DEFAULT_STATES[key],
          label: DEFAULT_STATES[key]?.label || { ja: key, en: key },
        };
      });
      return normalized;
    }
    Object.entries(states).forEach(([key, value]) => {
      normalized[sid(key)] = {
        ...DEFAULT_STATES[sid(key)],
        ...value,
        label: value.label || value.labels || DEFAULT_STATES[sid(key)]?.label || { ja: key, en: key },
      };
    });
    return normalized;
  }

  function normalizeCategory(category, dates) {
    const components = (category.components || category.children || []).map((component) => normalizeComponent(component, category, dates));
    const days = dates.map((date, index) => {
      const componentDays = components.map((component) => component.days[index]).filter(Boolean);
      const status = worstStatus(componentDays.map((day) => day.status));
      const source = componentDays.find((day) => sid(day.status) === sid(status)) || {};
      return {
        date,
        status,
        source: "component aggregate",
        message: source.message,
        incident_id: source.incident_id || null,
      };
    });
    return {
      id: String(category.id),
      name: category.name,
      fact: category.fact,
      monitoring: category.monitoring,
      claim: category.claim,
      components,
      days,
      state: days[days.length - 1]?.status || category.default_status || category.default_state || "not_started",
    };
  }

  function normalizeComponent(component, category, dates) {
    const defaultStatus = sid(
      component.default_status ||
        component.default_state ||
        category.default_status ||
        category.default_state ||
        "not_started"
    );
    const byDate = new Map();
    (component.days || []).forEach((day) => {
      if (day.date) byDate.set(day.date, day);
    });
    (component.day_overrides || []).forEach((day) => {
      const date = day.date || (Number.isInteger(day.index) ? dates[day.index] : null);
      if (date) byDate.set(date, { ...day, date });
    });
    const days = dates.map((date) => {
      const day = byDate.get(date) || {};
      const status = sid(day.status || day.state || defaultStatus);
      return {
        date,
        status,
        source: day.source || (day.status || day.state ? "status feed override" : "default_status"),
        message: day.message || component.fact || null,
        incident_id: day.incident_id || null,
      };
    });
    return {
      id: String(component.id),
      name: component.name,
      fact: component.fact,
      monitoring: component.monitoring,
      claim: component.claim,
      days,
      state: days[days.length - 1]?.status || defaultStatus,
    };
  }

  function setFeed(rawFeed, options = {}) {
    const sequence = Number.isFinite(Number(options.sequence))
      ? Number(options.sequence)
      : runtime.feedSequence + 1;
    const normalized = normalizeFeed(rawFeed);
    if (sequence < runtime.acceptedSequence) return runtime.rawFeed;
    runtime.feedSequence = Math.max(runtime.feedSequence, sequence);
    runtime.acceptedSequence = sequence;
    clearInteractionState();
    runtime.rawFeed = rawFeed;
    runtime.feed = normalized;
    root.dataset.statusRuntime = "feed";
    root.dataset.statusRuntimeVersion = VERSION;
    root.dataset.statusRuntimeGlobal = "ready";
    root.dataset.statusRuntimeApi = "ready";
    root.dataset.statusFeedApplied = VERSION;
    root.dataset.statusFeedSource = String(options.source || runtime.feed.meta.source || runtime.feed.schema_version || "feed");
    root.dataset.statusFeedSequence = String(sequence);
    delete root.dataset.statusFeedError;
    renderFeed();
    scheduleRefresh(runtime.feed.meta.refresh_ms);
    syncRoute();
    emit("yonerai-status-feed-applied", { feed: runtime.feed, source: root.dataset.statusFeedSource });
    runRuntimeSmokeIfRequested();
    return runtime.rawFeed;
  }

  function applyFeed(rawFeed, options = {}) {
    return setFeed(rawFeed, options);
  }

  function trySetFeed(rawFeed, options = {}) {
    try {
      const feed = setFeed(rawFeed, options);
      return { ok: true, feed, state: getState() };
    } catch (error) {
      root.dataset.statusRuntime = runtime.feed ? "feed-error" : "error";
      root.dataset.statusFeedError = error.message || String(error);
      emit("yonerai-status-feed-rejected", { error: runtimeError(error), state: getState() });
      return { ok: false, error: runtimeError(error), state: getState() };
    }
  }

  async function reload(url = feedUrl(), options = {}) {
    const href = sameOriginHref(url);
    const sequence = runtime.feedSequence + 1;
    root.dataset.statusFeedUrl = href;
    const response = await fetch(href, { cache: "no-store" });
    if (!response.ok) throw new Error(`Failed to load ${href}: ${response.status}`);
    return setFeed(await response.json(), { source: "reload", ...options, url: href, sequence });
  }

  function disconnectEvents() {
    if (runtime.eventSource) runtime.eventSource.close();
    runtime.eventSource = null;
    root.dataset.statusFeedEvents = "closed";
    return getState();
  }

  function connectEvents(url = "/status-feed/events", options = {}) {
    if (!window.EventSource) throw new Error("EventSource is not available in this browser");
    const href = sameOriginHref(url);
    disconnectEvents();
    const source = new EventSource(href);
    runtime.eventSource = source;
    root.dataset.statusFeedEvents = "connecting";
    root.dataset.statusFeedEventsUrl = href;
    source.addEventListener("open", () => {
      root.dataset.statusFeedEvents = "open";
    });
    source.addEventListener("status-feed", (event) => {
      try {
        const result = trySetFeed(JSON.parse(event.data), { animate: false, source: "sse", ...options, url: href });
        if (!result.ok) console.warn("YonerAI status feed event rejected", result.error);
      } catch (error) {
        root.dataset.statusFeedEventError = error.message || String(error);
        console.warn("YonerAI status feed event rejected", error);
      }
    });
    source.addEventListener("error", () => {
      root.dataset.statusFeedEvents = "error";
    });
    return source;
  }

  function clearInteractionState() {
    runtime.interactionEpoch += 1;
    runtime.tooltipToken = runtime.interactionEpoch;
    runtime.selectedToken = runtime.interactionEpoch;
    runtime.selected = null;
    runtime.touchPinned = false;
    clearHovered(true);
    clearSelected();
    hideTooltip(true);
    return getState();
  }

  function rerender(options = {}) {
    if (!runtime.rawFeed) return null;
    return setFeed(runtime.rawFeed, { source: "rerender", ...options });
  }

  function scheduleRefresh(refreshMs) {
    if (runtime.refreshTimer) clearInterval(runtime.refreshTimer);
    runtime.refreshTimer = 0;
    const interval = Number(refreshMs);
    if (Number.isFinite(interval) && interval >= 5000) {
      runtime.refreshTimer = setInterval(refresh, interval);
    }
  }

  function renderFeed() {
    const list = $("#categoryList");
    const template = $("#categoryTemplate");
    if (!list || !template) return;
    runtime.bars.clear();
    list.replaceChildren(...runtime.feed.categories.map((category, index) => renderCategory(category, index)));
    runtime.cascadeUntil = performance.now() + Math.min(1400, 360 + runtime.feed.categories.length * 80);
  }

  function renderCategory(category, rowIndex) {
    const node = $("#categoryTemplate").content.firstElementChild.cloneNode(true);
    node.dataset.categoryId = category.id;
    node.dataset.statusRuntime = "feed";
    node.style.setProperty("--status-color", stateColor(category.state));
    node.style.setProperty("--status-rgb", rgbFromHex(stateColor(category.state)));
    node.style.setProperty("--row-delay", `${rowIndex * 70}ms`);

    const summary = $(".category-summary", node);
    const children = $(".children", node);
    const childrenContent = $(".children-content", node);
    $(".category-name", node).textContent = local(category.name);
    $(".category-count", node).textContent = `${category.components.length} ${category.components.length === 1 ? t("componentSingular") : t("componentPlural")}`;
    $(".category-state", node).textContent = stateLabel(category.state);
    fillScale(node);
    buildBars($(".category-bars", node), category, null, category.days, rowIndex);
    category.components.forEach((component, childIndex) => {
      childrenContent.append(renderChild(category, component, rowIndex + childIndex + 1, childIndex));
    });
    bindDisclosure(summary, children, node, () => {
      replayBars($$(".bars", children));
    });
    return node;
  }

  function renderChild(category, component, rowIndex, childIndex) {
    const node = $("#childTemplate").content.firstElementChild.cloneNode(true);
    node.dataset.categoryId = category.id;
    node.dataset.componentId = component.id;
    node.style.setProperty("--status-color", stateColor(component.state));
    node.style.setProperty("--status-rgb", rgbFromHex(stateColor(component.state)));
    node.style.setProperty("--child-index", childIndex);
    node.style.setProperty("--child-delay", `${childIndex * 120}ms`);

    const summary = $(".child-summary", node);
    const detail = $(".child-detail", node);
    $(".child-name", node).textContent = local(component.name);
    $(".category-state", node).textContent = stateLabel(component.state);
    $(".detail-current-label", node).textContent = t("currentFact");
    $(".fact", node).textContent = local(component.fact, t("fallbackStatusMessage"));
    $(".detail-monitoring-label", node).textContent = t("monitoring");
    $(".detail-monitoring-value", node).textContent = local(component.monitoring, t("notConnected"));
    $(".detail-claim-label", node).textContent = t("publicClaim");
    $(".detail-claim-value", node).textContent = local(component.claim, t("noClaim"));
    buildBars($(".child-bars", node), category, component, component.days, rowIndex);
    bindDisclosure(summary, detail, node, () => {
      replayBars([$(".child-bars", node)]);
    });
    return node;
  }

  function fillScale(node) {
    $(".scale-start", node).textContent = t("scaleStart");
    $(".scale-uptime", node).textContent = t("scaleUptime");
    $(".scale-end", node).textContent = t("scaleEnd");
  }

  function buildBars(target, category, component, days, rowIndex) {
    target.replaceChildren();
    target.classList.add("is-animated");
    target.dataset.categoryId = category.id;
    target.dataset.componentId = component ? component.id : "__category__";
    target.dataset.statusRuntime = "feed";
    target.style.setProperty("--bar-count", String(days.length));
    const isChildRow = target.classList.contains("child-bars");
    const step = isChildRow ? 9 : 8;
    days.forEach((day, index) => {
      const bar = document.createElement("button");
      const status = sid(day.status);
      const color = stateColor(status);
      const route = routeFor(category.id, component ? component.id : "__category__", day.date, status);
      bar.type = "button";
      bar.className = `bar bar-state-${cssState(status)} is-clickable`;
      bar.dataset.route = route;
      bar.dataset.categoryId = category.id;
      bar.dataset.componentId = component ? component.id : "__category__";
      bar.dataset.date = day.date;
      bar.dataset.status = status;
      bar.dataset.mockStatus = status;
      bar.dataset.statusRuntime = "feed";
      if (day.incident_id) bar.dataset.incidentId = day.incident_id;
      bar.style.setProperty("--bar-index", index);
      bar.style.setProperty("--bar-delay", `${rowIndex * 42 + index * step}ms`);
      bar.style.setProperty("--bar-duration", isChildRow ? "220ms" : "260ms");
      bar.style.setProperty("--status-color", color);
      bar.style.setProperty("--status-rgb", rgbFromHex(color));
      bar.style.setProperty("--bar-color", color);
      bar.style.backgroundColor = color;
      bar.setAttribute("aria-label", `${formatDate(day.date)}: ${stateLabel(status)}`);
      target.append(bar);
      runtime.bars.set(route, bar);
    });
    bindBars(target);
  }

  function bindDisclosure(button, panel, node, onOpen) {
    button.setAttribute("aria-expanded", "false");
    panel.hidden = false;
    panel.setAttribute("aria-hidden", "true");
    if ("inert" in panel) panel.inert = true;
    button.addEventListener("click", () => {
      const opening = button.getAttribute("aria-expanded") !== "true";
      button.setAttribute("aria-expanded", String(opening));
      panel.setAttribute("aria-hidden", String(!opening));
      if ("inert" in panel) panel.inert = !opening;
      node.classList.toggle("is-open", opening);
      if (opening && onOpen) {
        requestAnimationFrame(onOpen);
      }
    }, { signal });
  }

  function replayBars(containers) {
    containers.filter(Boolean).forEach((container, row) => {
      container.classList.remove("is-animated");
      void container.offsetWidth;
      $$(".bar", container).forEach((bar, index) => {
        bar.style.setProperty("--bar-delay", `${row * 80 + index * 8}ms`);
      });
      container.classList.add("is-animated");
    });
    runtime.cascadeUntil = Math.max(runtime.cascadeUntil, performance.now() + 950);
  }

  function bindBars(container) {
    container.addEventListener("pointermove", (event) => {
      const token = runtime.interactionEpoch;
      const bar = event.target.closest(".bar") || barFromPoint(container, event.clientX);
      if (!bar) return;
      setHovered(bar, token);
      showTooltip(bar, event.clientX, event.clientY, event.pointerType === "touch");
      if (event.pointerType === "touch") event.preventDefault();
    }, { signal });
    container.addEventListener("pointerdown", (event) => {
      const token = runtime.interactionEpoch;
      const bar = event.target.closest(".bar") || barFromPoint(container, event.clientX);
      if (!bar) return;
      if (event.pointerType === "touch") runtime.touchPinned = true;
      setHovered(bar, token);
      showTooltip(bar, event.clientX, event.clientY, event.pointerType === "touch");
    }, { signal });
    container.addEventListener("pointerleave", () => {
      const token = runtime.interactionEpoch;
      if (runtime.interactionEpoch !== token) return;
      clearHovered(false);
      if (!runtime.touchPinned) hideTooltip();
    }, { signal });
    container.addEventListener("click", (event) => {
      const bar = event.target.closest(".bar") || barFromPoint(container, event.clientX);
      if (bar) activateBar(bar);
    }, { signal });
  }

  function barFromPoint(container, clientX) {
    const bars = $$(".bar", container);
    if (!bars.length) return null;
    const rect = container.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(0.999999, (clientX - rect.left) / Math.max(1, rect.width)));
    return bars[Math.floor(ratio * bars.length)] || bars[bars.length - 1];
  }

  function setHovered(bar, token = runtime.interactionEpoch) {
    if (runtime.interactionEpoch !== token) return;
    if (runtime.hovered === bar) return;
    clearHovered(false);
    runtime.hovered = bar;
    bar.classList.add("is-hovered");
    const bars = $$(".bar", bar.parentElement);
    const index = bars.indexOf(bar);
    runtime.hoverNeighbors = [bars[index - 1], bars[index + 1]].filter(Boolean);
    runtime.hoverNeighbors.forEach((neighbor) => neighbor.classList.add("is-near-hover"));
  }

  function clearHovered(hide = true) {
    runtime.hovered?.classList.remove("is-hovered");
    runtime.hoverNeighbors.forEach((bar) => bar.classList.remove("is-near-hover"));
    runtime.hovered = null;
    runtime.hoverNeighbors = [];
    if (hide) hideTooltip(true);
  }

  function showTooltip(bar, x, y, preferAbove = false) {
    const token = runtime.interactionEpoch;
    const tip = $("#barTooltip");
    if (!tip) return;
    const category = findCategory(bar.dataset.categoryId);
    const component = bar.dataset.componentId === "__category__" ? null : findComponent(category, bar.dataset.componentId);
    const day = findDay(category, component, bar.dataset.date);
    const key = `${bar.dataset.route}:${day?.message || ""}`;
    if (runtime.tooltipKey !== key) {
      const ownerName = component ? local(component.name) : local(category?.name);
      const title = el("strong", "", formatDate(bar.dataset.date));
      const line = el("span", "", `${ownerName}: ${stateLabel(bar.dataset.status)}${day?.message ? ` - ${local(day.message)}` : ""}`);
      tip.replaceChildren(title, line);
      runtime.tooltipKey = key;
    }
    runtime.tooltipToken = token;
    tip.style.pointerEvents = "none";
    tip.hidden = false;
    tip.classList.add("is-visible");
    moveTooltip(x, y, preferAbove);
  }

  function moveTooltip(x, y, preferAbove = false) {
    if (runtime.interactionEpoch !== runtime.tooltipToken) return;
    const tip = $("#barTooltip");
    if (!tip) return;
    runtime.tooltipTarget = { x, y, preferAbove, token: runtime.tooltipToken };
    if (!runtime.tooltipCurrent || tip.hidden) {
      runtime.tooltipCurrent = { ...runtime.tooltipTarget };
    }
    if (!runtime.tooltipFrame) {
      runtime.tooltipFrame = requestAnimationFrame(animateTooltip);
    }
  }

  function animateTooltip() {
    const tip = $("#barTooltip");
    if (!tip || !runtime.tooltipTarget || tip.hidden || runtime.interactionEpoch !== runtime.tooltipTarget.token) {
      runtime.tooltipFrame = 0;
      return;
    }
    const current = runtime.tooltipCurrent || runtime.tooltipTarget;
    current.x += (runtime.tooltipTarget.x - current.x) * 0.24;
    current.y += (runtime.tooltipTarget.y - current.y) * 0.24;
    current.preferAbove = runtime.tooltipTarget.preferAbove;
    placeTooltip(current);
    const dx = Math.abs(runtime.tooltipTarget.x - current.x);
    const dy = Math.abs(runtime.tooltipTarget.y - current.y);
    if (dx > 0.35 || dy > 0.35) {
      runtime.tooltipFrame = requestAnimationFrame(animateTooltip);
      return;
    }
    runtime.tooltipCurrent = { ...runtime.tooltipTarget };
    placeTooltip(runtime.tooltipCurrent);
    runtime.tooltipFrame = 0;
  }

  function placeTooltip(point) {
    const tip = $("#barTooltip");
    if (!tip) return;
    const margin = 12;
    const offset = point.preferAbove ? 28 : 16;
    const rect = tip.getBoundingClientRect();
    const width = rect.width || 280;
    const height = rect.height || 74;
    let left = point.x + 14;
    let top = point.preferAbove ? point.y - height - offset : point.y + offset;
    if (left + width + margin > innerWidth) left = point.x - width - 14;
    if (top + height + margin > innerHeight) top = point.y - height - offset;
    if (top < margin) top = margin;
    left = Math.max(margin, Math.min(left, innerWidth - width - margin));
    tip.style.transform = `translate3d(${Math.round(left)}px, ${Math.round(top)}px, 0)`;
  }

function hideTooltip(force = false) {
    if (runtime.touchPinned && !force) return;
    const tip = $("#barTooltip");
    if (!tip) return;
    const token = runtime.tooltipToken;
    runtime.touchPinned = false;
    runtime.tooltipKey = "";
    runtime.tooltipTarget = null;
    runtime.tooltipCurrent = null;
    if (runtime.tooltipFrame) cancelAnimationFrame(runtime.tooltipFrame);
    runtime.tooltipFrame = 0;
    tip.classList.remove("is-visible");
    setTimeout(() => {
      if (runtime.tooltipToken === token && !tip.classList.contains("is-visible")) tip.hidden = true;
    }, 130);
  }

  function activateBar(bar) {
    history.pushState("", document.title, location.pathname + location.search + bar.dataset.route);
    syncRoute();
  }

  function routeFor(categoryId, componentId, date, status) {
    return `#status/${enc(categoryId)}/${enc(componentId || "__category__")}/${enc(date)}/${enc(sid(status))}`;
  }

  function incidentRoute(id) {
    return `#incident/${enc(id)}`;
  }

  function parseHash() {
    const raw = decodeURIComponent(location.hash.replace(/^#/, ""));
    if (!raw) return { type: "overview" };
    const parts = raw.split("/").filter(Boolean);
    if (parts[0] === "status" && parts.length >= 5) {
      return { type: "status", categoryId: parts[1], componentId: parts[2], date: parts[3], state: parts[4] };
    }
    if (parts[0] === "incident" && parts[1]) {
      return { type: "incident", id: parts.slice(1).join("/") };
    }
    const legacyIncident = raw.match(/^incident-test-(\d+)-(.+)$/);
    if (legacyIncident) {
      return { type: "incident", id: `incident-test-${legacyIncident[1]}-${legacyIncident[2]}` };
    }
    const legacyStatus = raw.match(/^status-test-(\d+)-(.+)$/);
    if (legacyStatus) {
      const category = findCategory("status-bar-test");
      const component = findComponent(category, "status-bar-test-component");
      const index = Math.max(0, Math.min((component?.days.length || 1) - 1, Number(legacyStatus[1]) - 1));
      const day = component?.days[index];
      if (day) return { type: "status", categoryId: category.id, componentId: component.id, date: day.date, state: legacyStatus[2] };
    }
    return { type: "missing", raw };
  }

  function syncRoute() {
    runtime.routeEpoch += 1;
    clearInteractionState();
    if (!runtime.feed) return;
    const route = parseHash();
    root.dataset.statusRouteHash = location.hash.replace(/^#/, "");
    if (route.type === "overview") return showOverviewRoute();
    if (route.type === "status") return showStatusRoute(route);
    if (route.type === "incident") return showIncidentRoute(route);
    return showMissingRoute(route.raw);
  }

  function showOverviewRoute() {
    root.dataset.statusRouteType = "overview";
    root.dataset.incidentDetailView = "false";
    document.body.classList.remove("is-incident-route");
    resetRouteInteraction({ closeDisclosures: true });
    showMainSections(true);
    removePanels();
  }

  function showStatusRoute(route) {
    const category = findCategory(route.categoryId);
    const component = route.componentId === "__category__" ? null : findComponent(category, route.componentId);
    const day = findDay(category, component, route.date);
    if (!category || (route.componentId !== "__category__" && !component) || !day) {
      return showMissingRoute(location.hash.replace(/^#/, ""));
    }
    removeIncidentPanel();
    root.dataset.statusRouteType = "status";
    root.dataset.incidentDetailView = "false";
    document.body.classList.remove("is-incident-route");
    resetRouteInteraction({ closeDisclosures: true });
    showMainSections(true);
    if (component) openCategory(category.id);
    const canonical = routeFor(category.id, component ? component.id : "__category__", day.date, day.status);
    if (location.hash !== canonical) {
      history.replaceState("", document.title, location.pathname + location.search + canonical);
      root.dataset.statusRouteHash = canonical.replace(/^#/, "");
    }
    selectBar(runtime.bars.get(canonical));
    renderStatusPanel(category, component, day);
  }

  function showIncidentRoute(route) {
    const incident = runtime.feed.incidents.get(route.id);
    resetRouteInteraction({ closeDisclosures: true });
    removeStatusPanel();
    if (!incident) return showMissingRoute(route.id);
    root.dataset.statusRouteType = "incident";
    root.dataset.incidentDetailView = "true";
    document.body.classList.add("is-incident-route");
    showMainSections(false);
    renderIncidentPanel(incident);
  }

  function showMissingRoute(raw) {
    root.dataset.statusRouteMissing = raw || "unknown";
    history.replaceState("", document.title, location.pathname + location.search);
    showOverviewRoute();
  }

  function showMainSections(visible) {
    ["#noticePanel", "#statusCard", "#historyAction", "#incidentsSection"].forEach((selector) => {
      const node = $(selector);
      if (node) node.hidden = !visible;
    });
  }

  function resetRouteInteraction({ closeDisclosures = false } = {}) {
    clearSelected();
    clearHovered(false);
    hideTooltip(true);
    if (closeDisclosures) closeAllDisclosures();
  }

  function closeAllDisclosures() {
    $$(".category.is-open, .child.is-open").forEach((node) => {
      const isCategory = node.classList.contains("category");
      const button = $(isCategory ? ".category-summary" : ".child-summary", node);
      const panel = $(isCategory ? ".children" : ".child-detail", node);
      button?.setAttribute("aria-expanded", "false");
      panel?.setAttribute("aria-hidden", "true");
      if (panel && "inert" in panel) panel.inert = true;
      node.classList.remove("is-open");
    });
  }

  function openCategory(categoryId) {
    const node = $(`.category[data-category-id="${CSS.escape(categoryId)}"]`);
    const summary = $(".category-summary", node);
    const children = $(".children", node);
    if (node && summary && children && !node.classList.contains("is-open")) {
      summary.setAttribute("aria-expanded", "true");
      children.setAttribute("aria-hidden", "false");
      if ("inert" in children) children.inert = false;
      node.classList.add("is-open");
      replayBars($$(".bars", children));
    }
  }

  function selectBar(bar) {
    clearSelected();
    if (!bar) return;
    runtime.selected = bar;
    runtime.selectedToken = ++runtime.interactionEpoch;
    const delay = performance.now() < runtime.cascadeUntil
      ? Math.max(0, Number.parseFloat(bar.style.getPropertyValue("--bar-delay")) + 240)
      : 0;
    runtime.selectedTimer = setTimeout(() => {
      if (runtime.interactionEpoch !== runtime.selectedToken || runtime.selected !== bar) return;
      bar.classList.add("is-selected");
      bar.setAttribute("aria-current", "date");
    }, delay);
  }

  function clearSelected() {
    if (runtime.selectedTimer) clearTimeout(runtime.selectedTimer);
    runtime.selectedTimer = 0;
    $$(".bar.is-selected").forEach((bar) => {
      bar.classList.remove("is-selected");
      bar.removeAttribute("aria-current");
    });
    runtime.selected = null;
    runtime.selectedToken = runtime.interactionEpoch;
  }

  function findCategory(categoryId) {
    return runtime.feed?.categories.find((category) => category.id === categoryId) || null;
  }

  function findComponent(category, componentId) {
    return category?.components.find((component) => component.id === componentId) || null;
  }

  function findDay(category, component, date) {
    const days = component ? component.days : category?.days;
    return days?.find((day) => day.date === date) || null;
  }

  function renderStatusPanel(category, component, day) {
    removeStatusPanel();
    const owner = component || category;
    const panel = el("section", "bar-detail-panel");
    panel.id = "barDetailPanel";
    panel.dataset.feedDriven = "true";
    panel.dataset.state = sid(day.status);
    panel.dataset.severity = sid(day.status);
    panel.classList.add(`is-${cssState(day.status)}`, "is-entering");
    panel.style.setProperty("--status-color", stateColor(day.status));
    panel.style.setProperty("--status-rgb", rgbFromHex(stateColor(day.status)));
    const incident = day.incident_id ? runtime.feed.incidents.get(day.incident_id) : null;
    panel.innerHTML = `
      <div class="bar-detail-shell" data-severity="${esc(sid(day.status))}">
        <div class="bar-detail-topline">
          <button class="bar-detail-close" type="button" aria-label="${esc(t("back"))}">&lsaquo;</button>
          <div>
            <p class="bar-detail-kicker">${esc(sid(day.status))} / ${esc(stateLabel(day.status))}</p>
            <h2>${esc(local(owner.name))} - ${esc(t("detail"))}</h2>
          </div>
        </div>
        <div class="bar-detail-copy">
          <p>${esc(local(day.message, local(owner.fact, t("fallbackStatusMessage"))))}</p>
          <p>${esc(day.source || "status feed")}</p>
        </div>
        <dl class="bar-detail-facts">
          <div><dt>${esc(t("target"))}</dt><dd>${esc(local(owner.name))}</dd></div>
          <div><dt>${esc(t("date"))}</dt><dd>${esc(formatDate(day.date))}</dd></div>
          <div><dt>${esc(t("state"))}</dt><dd>${esc(sid(day.status))} / ${esc(stateLabel(day.status))}</dd></div>
        </dl>
        ${incident ? `<div class="bar-detail-actions"><button class="drilldown-button detail-incident-link" type="button">${esc(t("incidentTimeline"))}</button></div>` : ""}
      </div>`;
    $(".bar-detail-close", panel)?.addEventListener("click", () => {
      history.pushState("", document.title, location.pathname + location.search);
      syncRoute();
    }, { signal });
    $(".detail-incident-link", panel)?.addEventListener("click", () => {
      history.pushState("", document.title, location.pathname + location.search + incidentRoute(incident.id));
      syncRoute();
    }, { signal });
    $("#statusCard")?.after(panel);
  }

  function affectedRouteCandidates(incident) {
    const affectedItems = Array.isArray(incident.affected)
      ? incident.affected
      : (incident.affected ? [incident.affected] : []);
    const affectedComponents = affectedItems.flatMap((affected) => (
      Array.isArray(affected.components) ? affected.components : []
    ));
    return [incident, ...affectedItems, ...affectedComponents].filter(Boolean);
  }

  function incidentBackHash(incident) {
    for (const candidate of affectedRouteCandidates(incident)) {
      const categoryId = candidate.category_id || incident.category_id;
      const componentId = candidate.component_id || incident.component_id;
      const date = candidate.date || candidate.start_date || incident.date;
      if (!categoryId || !date) continue;
      const category = findCategory(categoryId);
      const component = findComponent(category, componentId);
      const day = findDay(category, component, date);
      if (category && day) {
        return routeFor(category.id, component ? component.id : "__category__", day.date, day.status);
      }
    }
    return "";
  }

  function renderIncidentPanel(incident) {
    removeIncidentPanel();
    const panel = el("section", "incident-detail-panel");
    panel.id = "incidentDetailPanel";
    panel.dataset.feedDriven = "true";
    panel.dataset.state = sid(incident.state || "resolved");
    panel.style.setProperty("--status-color", stateColor(incident.state || "resolved"));
    panel.style.setProperty("--status-rgb", rgbFromHex(stateColor(incident.state || "resolved")));

    const hero = el("article", "incident-hero");
    hero.innerHTML = `
      <div class="incident-hero-head">
        <button class="incident-back" type="button" aria-label="${esc(t("back"))}">&lsaquo;</button>
        <div>
          <p class="incident-kicker">${esc(sid(incident.state))} / ${esc(stateLabel(incident.state))}</p>
          <h2 class="incident-title-text">${esc(local(incident.title, incident.id))}</h2>
        </div>
      </div>
      <p class="incident-meta">${esc([
        local(incident.status_label, stateLabel(incident.state)),
        local(incident.impact_label, stateLabel(incident.impact || incident.state)),
        local(incident.kind_label, "Display test"),
      ].filter(Boolean).join(" ・ "))}</p>
      <div class="incident-copy">${paragraphs(local(incident.summary, ""))}${paragraphs(local(incident.description, ""))}</div>
      <p class="incident-date">${esc(formatDate(incident.date || runtime.feed.range.dates[0]))} ・ ${esc(t("allUpdates"))}</p>`;
    $(".incident-back", hero)?.addEventListener("click", () => {
      const hash = incidentBackHash(incident);
      history.pushState("", document.title, location.pathname + location.search + hash);
      syncRoute();
    }, { signal });
    panel.append(hero, renderAffected(incident), renderUpdates(incident));
    $("#mainContent")?.append(panel);
    $$(".affected-timeline", panel).forEach(bindAffectedTimeline);
  }

  function paragraphs(text) {
    return String(text || "").split(/\n\s*\n/).filter(Boolean).map((paragraph) => `<p>${esc(paragraph)}</p>`).join("");
  }

  function renderAffected(incident) {
    const section = el("article", "incident-section affected-section");
    section.append(el("h3", "", local(incident.affected_title, t("affected"))));
    const affectedItems = Array.isArray(incident.affected) ? incident.affected : (incident.affected ? [incident.affected] : []);
    affectedItems.forEach((affected) => {
      const windowRow = el("div", "affected-window");
      windowRow.append(el("span", "", local(affected.start_label, "")), el("span", "", local(affected.end_label, "")));
      const row = el("div", "affected-row");
      const header = el("div", "affected-row-header");
      header.append(
        el("strong", "", local(affected.component_label || affected.label, affected.component_id || "component")),
        el("span", "", local(affected.count_label, `1 ${t("affectedOne")}`))
      );
      const timeline = el("div", "affected-timeline");
      timeline.dataset.tooltip = local(affected.tooltip, local(incident.title, incident.id));
      (affected.segments || []).forEach((segment) => {
        const status = sid(segment.state || segment.status);
        const seg = el("span", "segment");
        seg.dataset.status = status;
        seg.dataset.label = local(segment.label, stateLabel(status));
        const weight = Number(segment.percent ?? segment.weight ?? segment.width ?? 1);
        const color = stateColor(status);
        seg.style.setProperty("--segment-weight", weight);
        seg.style.setProperty("--segment-color", color);
        seg.style.setProperty("flex", `${weight} 1 0`, "important");
        seg.style.setProperty("background-color", color, "important");
        timeline.append(seg);
      });
      row.append(header, timeline);
      section.append(windowRow, row);
    });
    return section;
  }

  function bindAffectedTimeline(timeline) {
    timeline.addEventListener("pointermove", (event) => {
      const segment = event.target.closest(".segment");
      if (!segment) return;
      const tip = $("#barTooltip");
      if (!tip) return;
      const key = `${segment.dataset.status}:${segment.dataset.label}:${timeline.dataset.tooltip}`;
      if (runtime.tooltipKey !== key) {
        tip.replaceChildren(el("strong", "", segment.dataset.label || stateLabel(segment.dataset.status)), el("span", "", timeline.dataset.tooltip || ""));
        runtime.tooltipKey = key;
      }
      tip.style.pointerEvents = "none";
      tip.hidden = false;
      tip.classList.add("is-visible");
      runtime.touchPinned = event.pointerType === "touch";
      moveTooltip(event.clientX, event.clientY, event.pointerType === "touch");
    }, { signal });
    timeline.addEventListener("pointerleave", () => hideTooltip(), { signal });
  }

  function renderUpdates(incident) {
    const section = el("article", "incident-section updates-section");
    section.append(el("h3", "", t("updates")));
    const list = el("ol", "updates-timeline");
    list.id = "updatesTimeline";
    (incident.updates || []).forEach((update) => {
      const status = sid(update.status || "resolved");
      const item = el("li", `update-item update-${cssState(status)}`);
      item.dataset.status = status;
      item.style.setProperty("--timeline-color", stateColor(status));
      item.style.setProperty("--status-color", stateColor(status));
      item.append(el("strong", "update-status", local(update.title || update.label, stateLabel(status))));
      String(local(update.body, "")).split(/\n\s*\n/).filter(Boolean).forEach((paragraph) => {
        item.append(el("p", "", paragraph));
      });
      item.append(el("time", "", [update.time_utc || update.utc || "", update.time_local || update.local || update.jst || ""].filter(Boolean).join(" ・ ")));
      list.append(item);
    });
    section.append(list);
    return section;
  }

  function removePanels() {
    removeStatusPanel();
    removeIncidentPanel();
  }

  function removeStatusPanel() {
    $("#barDetailPanel")?.remove();
  }

  function removeIncidentPanel() {
    $("#incidentDetailPanel")?.remove();
  }

  function emit(name, detail = {}) {
    document.dispatchEvent(new CustomEvent(name, { detail: { version: VERSION, ...detail } }));
  }

  function runRuntimeSmokeIfRequested() {
    const params = new URLSearchParams(location.search);
    if (params.get("runtimeSmoke") !== "1" || params.get("mockStatus") !== "1") return;
    if (runtime.smokeRan || runtime.smokeRunning) return;
    runtime.smokeRan = true;
    runtime.smokeRunning = true;
    root.dataset.statusRuntimeSmoke = "running";
    setTimeout(runRuntimeSmoke, 0);
  }

  async function runRuntimeSmoke() {
    try {
      const next = JSON.parse(JSON.stringify(runtime.rawFeed));
      next.meta = {
        ...(next.meta || {}),
        source: "runtime.applyFeed.smoke.v1",
        live_monitoring: true,
      };
      next.categories = Array.isArray(next.categories) ? next.categories : [];
      next.incidents = Array.isArray(next.incidents) ? next.incidents : [];
      next.categories.push({
        id: "runtime-smoke",
        name: { ja: "Runtime差し替えテスト", en: "Runtime swap test" },
        default_status: "operational",
        components: [
          {
            id: "runtime-smoke-component",
            name: { ja: "Runtime差し替えComponent", en: "Runtime swap component" },
            default_status: "operational",
            fact: { ja: "applyFeedで追加された表示テストです。", en: "Display test added through applyFeed." },
            monitoring: { ja: "テスト接続", en: "Test connected" },
            claim: { ja: "実運用claimではありません", en: "Not a production claim" },
            day_overrides: [
              {
                date: "2026-03-28",
                status: "degraded",
                incident_id: "runtime-smoke-incident",
                message: { ja: "applyFeed degraded smoke", en: "applyFeed degraded smoke" },
              },
            ],
          },
        ],
      });
      next.incidents.push({
        id: "runtime-smoke-incident",
        date: "2026-03-28",
        category_id: "runtime-smoke",
        component_id: "runtime-smoke-component",
        state: "degraded",
        impact: "degraded",
        kind: "runtime_smoke",
        title: { ja: "Runtime差し替え: 性能低下テスト", en: "Runtime swap: degraded test" },
        status_label: { ja: "監視中", en: "Monitoring" },
        impact_label: { ja: "性能低下", en: "Degraded" },
        kind_label: { ja: "runtime smoke", en: "runtime smoke" },
        summary: { ja: "applyFeed差し替えで障害詳細を表示するテストです。", en: "Incident detail rendered from applyFeed test data." },
        description: { ja: "これは実データではありません。", en: "This is not real data." },
        affected: {
          start_label: "2026-03-28 09:00",
          end_label: "09:30",
          component_label: { ja: "Runtime差し替えComponent", en: "Runtime swap component" },
          count_label: { ja: "1 affected component", en: "1 affected component" },
          tooltip: { ja: "Runtime差し替えComponent: 性能低下", en: "Runtime swap component: degraded" },
          segments: [
            { status: "operational", width: 20 },
            { status: "degraded", width: 60 },
            { status: "operational", width: 20 },
          ],
        },
        updates: [
          {
            status: "monitoring",
            title: { ja: "監視中", en: "Monitoring" },
            body: { ja: "runtime feed 差し替え後の更新です。", en: "Update after runtime feed swap." },
            time_utc: "2026-06-01 00:00 UTC",
            time_local: "2026-06-01 09:00 JST",
          },
        ],
      });

      validateFeed(next);
      history.replaceState("", document.title, location.pathname + location.search + routeFor("runtime-smoke", "runtime-smoke-component", "2026-03-28", "degraded"));
      applyFeed(next);
      await delay(1100);
      const status = collectRuntimeSmokeState();
      history.replaceState("", document.title, location.pathname + location.search + incidentRoute("runtime-smoke-incident"));
      syncRoute();
      await delay(150);
      const incident = collectRuntimeSmokeState();

      root.dataset.statusRuntimeSmoke = "ok";
      root.dataset.statusRuntimeSmokeSource = root.dataset.statusFeedSource || "";
      root.dataset.statusRuntimeSmokeStatusRoute = status.routeType;
      root.dataset.statusRuntimeSmokeIncidentRoute = incident.routeType;
      root.dataset.statusRuntimeSmokeCategoryCount = String(status.categories);
      root.dataset.statusRuntimeSmokeBarCount = String(status.bars);
      root.dataset.statusRuntimeSmokeSelectedCount = String(status.selected);
      root.dataset.statusRuntimeSmokeStatusPanels = String(status.statusPanels);
      root.dataset.statusRuntimeSmokeIncidentPanels = String(incident.incidentPanels);
      root.dataset.statusRuntimeSmokeMojibake = String(status.mojibake || incident.mojibake);
      root.dataset.statusRuntimeSmokeOverflow = String(status.overflow || incident.overflow);
    } catch (error) {
      root.dataset.statusRuntimeSmoke = "error";
      root.dataset.statusRuntimeSmokeError = error.message || String(error);
      console.error("YonerAI status runtime smoke failed", error);
    } finally {
      runtime.smokeRunning = false;
    }
  }

  function nextFrame() {
    return new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  }

  function delay(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  function collectRuntimeSmokeState() {
    const text = document.body.innerText || "";
    return {
      routeType: root.dataset.statusRouteType || "",
      categories: $$(".category").length,
      bars: $$(".bar").length,
      selected: $$(".bar.is-selected").length,
      statusPanels: $$("#barDetailPanel").length,
      incidentPanels: $$("#incidentDetailPanel").length,
      mojibake: [0x00e3, 0x7e3a, 0x8b41, 0xfffd].some((code) => text.includes(String.fromCharCode(code))),
      overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 2,
    };
  }

  function getState() {
    return {
      version: VERSION,
      locale: runtime.locale,
      route: parseHash(),
      theme: root.dataset.theme,
      schema: runtime.feed?.schema_version || "",
      source: runtime.feed?.meta?.source || "",
      categories: runtime.feed?.categories.length || 0,
      bars: runtime.bars.size,
      selectedRoute: runtime.selected?.dataset.route || null,
      selectedCount: $$(".bar.is-selected").length,
      statusPanels: $$("#barDetailPanel").length,
      incidentPanels: $$("#incidentDetailPanel").length,
      eventSourceState: runtime.eventSource?.readyState ?? null,
      feedSequence: runtime.acceptedSequence,
      error: root.dataset.statusFeedError || "",
      runtimeStatus: root.dataset.statusRuntime,
    };
  }

  function destroy() {
    controller.abort();
    if (runtime.refreshTimer) clearInterval(runtime.refreshTimer);
    disconnectEvents();
    if (runtime.tooltipFrame) cancelAnimationFrame(runtime.tooltipFrame);
  }

  function feedEventPayload(detail) {
    if (detail && typeof detail === "object" && Object.prototype.hasOwnProperty.call(detail, "feed")) {
      return {
        feed: detail.feed,
        options: {
          source: detail.source || detail.options?.source || "event",
          ...(detail.options || {}),
        },
      };
    }
    return { feed: detail, options: { source: "event" } };
  }

  function handleSetFeedEvent(event) {
    const payload = feedEventPayload(event.detail);
    const result = trySetFeed(payload.feed, payload.options);
    if (!result.ok) console.warn("YonerAI status feed event rejected", result.error);
  }

  function boot() {
    configureTheme();
    applyStaticCopy();
    $("#themeToggle")?.addEventListener("click", toggleTheme, { signal });
    $("#subscribeButton")?.addEventListener("click", () => alert(t("subscribeAlert")), { signal });
    $("#historyButton")?.addEventListener("click", () => alert(t("historyAlert")), { signal });
    $("#historyHint")?.addEventListener("click", () => alert(t("historyHintAlert")), { signal });
    document.addEventListener("pointerdown", (event) => {
      if (event.target.closest(".bars, .tooltip, .affected-timeline")) return;
      runtime.touchPinned = false;
      clearHovered();
      hideTooltip(true);
    }, { signal });
    window.addEventListener("scroll", () => hideTooltip(true), { passive: true, signal });
    window.addEventListener("hashchange", syncRoute, { signal });
    document.addEventListener("yonerai-status-feed:update", handleSetFeedEvent, { signal });
    document.addEventListener("yonerai-status:set-feed", handleSetFeedEvent, { signal });
    document.addEventListener("yonerai-status-feed:refresh", refresh, { signal });
    window.YonerAIStatusRuntime = {
      __version: VERSION,
      version: VERSION,
      applyFeed,
      setFeed,
      trySetFeed,
      reload,
      refresh,
      connectEvents,
      disconnectEvents,
      validateFeed,
      syncRoute,
      clearInteractionState,
      rerender,
      getState,
      getFeed: () => runtime.rawFeed,
      destroy,
    };
    window.YonerAIStatus = window.YonerAIStatusRuntime;
    window.yoneraiStatusApplyFeed = applyFeed;
    window.yoneraiStatusSetFeed = setFeed;
    window.yoneraiStatusTrySetFeed = trySetFeed;
    window.yoneraiStatusReload = reload;
    window.yoneraiStatusRefresh = refresh;
    window.yoneraiStatusGetState = getState;
    window.yoneraiStatusGetFeed = () => runtime.rawFeed;
    root.dataset.statusRuntimeGlobal = "ready";
    root.dataset.statusRuntimeApi = "ready";
    emit("yonerai-status-runtime-ready");
    refresh();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }
})();
