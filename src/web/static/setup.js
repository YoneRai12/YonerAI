/* YonerAI Setup UI (sidebar + categories + section cards + toggles + i18n) */

const $ = (id) => document.getElementById(id);

// ---------------------------------------------------------------------------
// Viewport classes (wide / 4K scaling)
// ---------------------------------------------------------------------------

function _debounce(fn, ms) {
  let t = null;
  return (...args) => {
    if (t) clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
}

function _applyViewportClasses() {
  const w = window.innerWidth || 0;
  document.documentElement.classList.toggle("isWide", w >= 1400);
  document.documentElement.classList.toggle("is4k", w >= 2400);
}

// ---------------------------------------------------------------------------
// i18n (UI language)
// ---------------------------------------------------------------------------

const I18N = {
  en: {
    title: "YonerAI Setup",
    brand_desc: "Tokens, roles, permissions, approvals, MCP, relay. Everything from UI.",
    refresh: "Refresh",
    language: "Language",
    setup: "Setup",
    api_token: "API Token",
    show_desc: "Descriptions",
    override_mode: "Override Mode",
    override_mode_override: "override (UI wins)",
    override_mode_fill: "fill (only when env is missing)",
    save: "Save",
    filter_label: "Filter (key/description)",
    filter_ph: "e.g. TOKEN, ADMIN, ORA_MCP_, RELAY, APPROVAL",
    token_ph: "Bearer token (stored in this browser)",
    save_token: "Save",
    clear_token: "Clear",
    saved: "Saved.",
    cleared: "Cleared.",
    loading: "Loading...",
    no_changes: "No changes.",
    saved_prefix: "Saved",
    restart_hint: "Restart may be required.",
    overview_title: "Overview",
    overview_sub: "Quick actions and status.",
    quick_actions: "Quick actions",
    qa_roles: "Roles",
    qa_permissions: "Permissions",
    qa_approvals: "Approvals",
    qa_relay: "Relay/Tunnel",
    category_sub: "Edit settings in this category. Use filter to narrow down.",
    nav_overview_sub: "Quick actions, status",
    nav_default_sub: "Configure",
    bool_unset: "Unset",
    secret_ph: "Paste new value (leave empty = no change)",
    secret_clear: "Clear secret (danger)",
    src_prefix: "src=",
    api_token_hint: "If ORA_WEB_API_TOKEN is set, paste it in the sidebar token field.",
    error_prefix: "Error",
    status_title: "Status",
    notes_title: "Notes",
    dev_ui_title: "Developer UI",
    dev_ui_sub: "Per-user safe debug visibility toggle (Discord account ID).",
    dev_ui_user_id: "Discord User ID",
    dev_ui_enabled: "Enable safe developer metadata",
    dev_ui_load: "Load",
    dev_ui_save: "Save",
    dev_ui_loaded: "Loaded",
    dev_ui_saved: "Saved",
    k_secrets_present: "secrets_present",
    k_env_configured: "env_configured",
    k_state_dir: "state_dir",
    k_secrets_dir: "secrets_dir",
    default_prefix: "default=",
    locked: "locked",
    present: "present",
    missing: "missing",
    group_general: "General",
    group_secrets: "Secrets",
    group_tokens: "Tokens",
    group_ids: "IDs",
    group_policy: "Policy",
    group_limits: "Limits",
    group_tools: "Tools",
    group_openai: "OpenAI",
    group_anthropic: "Anthropic",
    group_google: "Google",
    group_grok: "Grok/xAI",
    group_mistral: "Mistral",
    group_cloudflare: "Cloudflare",
    group_relay: "Relay",
  },
  ja: {
    title: "YonerAI セットアップ",
    brand_desc: "トークン、ロール、権限、承認、MCP、Relay を UI からまとめて設定します。",
    refresh: "更新",
    language: "言語",
    setup: "設定",
    api_token: "APIトークン",
    show_desc: "説明表示",
    override_mode: "上書きモード",
    override_mode_override: "override（UIが優先）",
    override_mode_fill: "fill（env未設定のみ補完）",
    save: "保存",
    filter_label: "フィルタ（キー/説明）",
    filter_ph: "例: TOKEN, ADMIN, ORA_MCP_, RELAY, APPROVAL",
    token_ph: "Bearerトークン（このブラウザに保存）",
    save_token: "保存",
    clear_token: "消去",
    saved: "保存しました。",
    cleared: "消去しました。",
    loading: "読み込み中...",
    no_changes: "変更なし。",
    saved_prefix: "保存",
    restart_hint: "反映には再起動が必要な場合があります。",
    overview_title: "概要",
    overview_sub: "クイック操作と状態。",
    quick_actions: "クイック操作",
    qa_roles: "ロール",
    qa_permissions: "権限",
    qa_approvals: "承認",
    qa_relay: "Relay/Tunnel",
    category_sub: "このカテゴリの設定を編集します。フィルタで絞り込みできます。",
    nav_overview_sub: "クイック操作・状態",
    nav_default_sub: "設定",
    bool_unset: "未設定にする",
    secret_ph: "新しい値を貼り付け（空=変更なし）",
    secret_clear: "Secretを消去（危険）",
    src_prefix: "src=",
    api_token_hint: "ORA_WEB_API_TOKEN を設定している場合、左のトークン欄に貼り付けてください。",
    error_prefix: "エラー",
    status_title: "状態",
    notes_title: "メモ",
    dev_ui_title: "Developer UI",
    dev_ui_sub: "ユーザー単位の安全なデバッグ表示（Discord User ID）",
    dev_ui_user_id: "Discord User ID",
    dev_ui_enabled: "安全な開発メタ情報を表示",
    dev_ui_load: "読込",
    dev_ui_save: "保存",
    dev_ui_loaded: "読込完了",
    dev_ui_saved: "保存完了",
    k_secrets_present: "Secrets（設定済み）",
    k_env_configured: "env（設定済み）",
    k_state_dir: "状態ディレクトリ",
    k_secrets_dir: "Secretsディレクトリ",
    default_prefix: "default=",
    locked: "ロック",
    present: "設定済み",
    missing: "未設定",
    group_general: "一般",
    group_secrets: "シークレット",
    group_tokens: "トークン",
    group_ids: "ID",
    group_policy: "ポリシー",
    group_limits: "制限",
    group_tools: "ツール",
    group_openai: "OpenAI",
    group_anthropic: "Anthropic",
    group_google: "Google",
    group_grok: "Grok/xAI",
    group_mistral: "Mistral",
    group_cloudflare: "Cloudflare",
    group_relay: "Relay",
  },
};

const CAT_LABELS = {
  ja: {
    Overview: "概要",
    Roles: "ロール/管理者",
    Permissions: "権限",
    Approvals: "承認（Approvals）",
    Discord: "Discord",
    Providers: "プロバイダ/トークン",
    "Web/Auth": "Web/認証",
    MCP: "MCP",
    Music: "音楽",
    "Relay/Tunnel": "Relay/Tunnel",
    URLs: "URL",
    Sandbox: "サンドボックス",
    Remotion: "Remotion",
    Scheduler: "スケジューラ",
    Swarm: "Swarm",
    Browser: "ブラウザ",
    Storage: "ストレージ",
    "Logging/Debug": "ログ/デバッグ",
    Models: "モデル",
    Voice: "音声",
    Search: "検索",
    Other: "その他",
  },
  en: {},
};

function _defaultLang() {
  const nav = (navigator.language || "").toLowerCase();
  if (nav.startsWith("ja")) return "ja";
  return "en";
}

let _lang = (localStorage.getItem("yonerai_setup_lang") || "").trim().toLowerCase();
if (!_lang) _lang = _defaultLang();
if (!I18N[_lang]) _lang = "en";

function t(key) {
  return (I18N[_lang] && I18N[_lang][key]) || I18N.en[key] || key;
}

function catLabel(cat) {
  const m = CAT_LABELS[_lang] || {};
  return m[cat] || cat;
}

function _getBoolLS(key, def) {
  const raw = (localStorage.getItem(key) || "").trim().toLowerCase();
  if (!raw) return def;
  if (["1", "true", "yes", "on"].includes(raw)) return true;
  if (["0", "false", "no", "off"].includes(raw)) return false;
  return def;
}

// If Japanese: default descriptions OFF to avoid JP/EN mixing (env.example is English-heavy).
let _showDesc = _getBoolLS("yonerai_setup_show_desc", _lang !== "ja");

function _applyDescClass() {
  document.documentElement.classList.toggle("hideDesc", !_showDesc);
}

function setLang(lang) {
  const l = String(lang || "").trim().toLowerCase();
  if (!I18N[l]) return;
  _lang = l;
  localStorage.setItem("yonerai_setup_lang", _lang);

  // If the user hasn't explicitly chosen desc visibility yet, apply sensible default per language.
  if (!localStorage.getItem("yonerai_setup_show_desc")) {
    _showDesc = _lang !== "ja";
  }

  document.documentElement.lang = _lang;
  _applyDescClass();
  _applyStaticStrings();
  _syncPrefsUI();
  _renderNav("nav");
  _renderNav("navMobile");
  _renderPanel();
}

function setShowDesc(v) {
  _showDesc = !!v;
  localStorage.setItem("yonerai_setup_show_desc", _showDesc ? "1" : "0");
  _applyDescClass();
  _syncPrefsUI();
}

function _syncPrefsUI() {
  if ($("showDesc")) $("showDesc").checked = !!_showDesc;
  if ($("showDescMobile")) $("showDescMobile").checked = !!_showDesc;
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

function bearerHeaders() {
  const tok = (localStorage.getItem("ora_web_api_token") || "").trim();
  if (!tok) return {};
  return { Authorization: "Bearer " + tok };
}

async function apiGet(path) {
  const r = await fetch(path, { headers: { ...bearerHeaders() } });
  const txt = await r.text();
  let data = null;
  try {
    data = JSON.parse(txt);
  } catch (e) {
    /* ignore */
  }
  if (!r.ok) {
    const msg = data && (data.detail || data.message) ? (data.detail || data.message) : txt;
    throw new Error(r.status + " " + msg);
  }
  return data;
}

async function apiPost(path, body) {
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...bearerHeaders() },
    body: JSON.stringify(body || {}),
  });
  const txt = await r.text();
  let data = null;
  try {
    data = JSON.parse(txt);
  } catch (e) {
    /* ignore */
  }
  if (!r.ok) {
    const msg = data && (data.detail || data.message) ? (data.detail || data.message) : txt;
    throw new Error(r.status + " " + msg);
  }
  return data;
}

// ---------------------------------------------------------------------------
// Render helpers
// ---------------------------------------------------------------------------

function _normBoolValue(v) {
  const s = String(v || "").trim().toLowerCase();
  if (!s) return "";
  if (["1", "true", "yes", "on"].includes(s)) return "1";
  if (["0", "false", "no", "off"].includes(s)) return "0";
  return s;
}

function _rowHay(spec) {
  return [spec.key, spec.category || "", spec.kind || "", spec.description || ""].join(" ").toLowerCase();
}

function _makeBadge(text, cls) {
  const el = document.createElement("span");
  el.className = "badge" + (cls ? " " + cls : "");
  el.textContent = text;
  return el;
}

function _setRowChanged(rowEl, changed) {
  if (!rowEl) return;
  rowEl.classList.toggle("settingChanged", !!changed);
}

function _makeSecretEditor() {
  const wrap = document.createElement("div");
  wrap.className = "switchRow";

  const ta = document.createElement("textarea");
  ta.placeholder = t("secret_ph");
  wrap.appendChild(ta);

  const clearWrap = document.createElement("div");
  clearWrap.className = "switchWrap";
  const cb = document.createElement("input");
  cb.type = "checkbox";
  const lbl = document.createElement("span");
  lbl.className = "badge warn";
  lbl.textContent = t("secret_clear");
  clearWrap.appendChild(cb);
  clearWrap.appendChild(lbl);
  wrap.appendChild(clearWrap);

  return { wrap, ta, cb };
}

function _makeBoolEditor(currentValue, srcLabel) {
  const wrap = document.createElement("div");
  wrap.className = "switchRow";

  const line = document.createElement("div");
  line.className = "switchWrap";

  const sw = document.createElement("label");
  sw.className = "switch";
  const input = document.createElement("input");
  input.type = "checkbox";
  const slider = document.createElement("span");
  slider.className = "slider";
  sw.appendChild(input);
  sw.appendChild(slider);

  const unset = document.createElement("button");
  unset.type = "button";
  unset.className = "unsetBtn";
  unset.textContent = t("bool_unset");

  const hint = _makeBadge(t("src_prefix") + (srcLabel || "?"), srcLabel === "override" ? "warn" : "");

  const cur = _normBoolValue(currentValue);
  input.checked = cur === "1";
  input.dataset.unset = cur ? "0" : "1";
  unset.style.opacity = input.dataset.unset === "1" ? "0.55" : "1";

  unset.onclick = () => {
    input.dataset.unset = "1";
    input.checked = false;
    unset.style.opacity = "0.55";
    input.dispatchEvent(new Event("change", { bubbles: true }));
    input.dispatchEvent(new Event("input", { bubbles: true }));
  };
  input.addEventListener("change", () => {
    input.dataset.unset = "0";
    unset.style.opacity = "1";
  });

  line.appendChild(sw);
  line.appendChild(unset);
  line.appendChild(hint);
  wrap.appendChild(line);
  return { wrap, input };
}

function _makeEnvEditor(spec, currentValue, srcLabel) {
  const inputType = String(spec.input || "text");
  if (inputType === "bool") return _makeBoolEditor(currentValue, srcLabel);

  if (inputType === "textarea" || inputType === "json") {
    const ta = document.createElement("textarea");
    ta.value = String(currentValue || "");
    if (spec.default && !String(currentValue || "").trim()) ta.placeholder = String(spec.default);
    return { wrap: ta, input: ta };
  }
  if (inputType === "number") {
    const inp = document.createElement("input");
    inp.type = "number";
    inp.value = String(currentValue || "");
    if (spec.default && !String(currentValue || "").trim()) inp.placeholder = String(spec.default);
    return { wrap: inp, input: inp };
  }

  const inp = document.createElement("input");
  inp.value = String(currentValue || "");
  if (spec.default && !String(currentValue || "").trim()) inp.placeholder = String(spec.default);
  return { wrap: inp, input: inp };
}

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

let _schema = null;
let _status = null;
let _byCat = new Map();
let _activePanel = "Overview";
const _rows = new Map(); // key -> row state
let _dirtyCount = 0;

function _updateSaveButton() {
  const btn = $("savePanel");
  if (!btn) return;
  const label = t("save");
  btn.textContent = _dirtyCount > 0 ? `${label} (${_dirtyCount})` : label;
  btn.disabled = _dirtyCount === 0;
}

function _recountDirty() {
  _dirtyCount = Array.from(_rows.values()).filter((r) => r && r.rowEl && r.rowEl.classList.contains("settingChanged")).length;
  _updateSaveButton();
}

function _buildCategoryMap(schema) {
  const settings = schema && schema.settings ? schema.settings : [];
  const map = new Map();
  settings.forEach((s) => {
    const cat = String(s.category || "Other");
    if (!map.has(cat)) map.set(cat, []);
    map.get(cat).push(s);
  });
  for (const [cat, arr] of map.entries()) arr.sort((a, b) => String(a.key).localeCompare(String(b.key)));
  return map;
}

function _navOrder(cats) {
  const preferred = [
    "Overview",
    "Roles",
    "Permissions",
    "Approvals",
    "Discord",
    "Providers",
    "Web/Auth",
    "MCP",
    "Music",
    "Relay/Tunnel",
    "Sandbox",
    "Browser",
    "Storage",
    "Logging/Debug",
    "Models",
    "Voice",
    "Search",
    "Other",
  ];
  const set = new Set(cats);
  const out = [];
  preferred.forEach((c) => {
    if (set.has(c)) out.push(c);
  });
  const rest = cats.filter((c) => !out.includes(c)).sort();
  return out.concat(rest);
}

function _renderNav(targetId) {
  const nav = $(targetId);
  nav.innerHTML = "";
  const cats = _navOrder(["Overview"].concat(Array.from(_byCat.keys())));
  const seen = new Set();
  cats.forEach((cat) => {
    if (seen.has(cat)) return;
    seen.add(cat);

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "navItem" + (cat === _activePanel ? " active" : "");
    const left = document.createElement("div");
    left.innerHTML = '<div class="navLabel"><span class="navIcon"></span><span>' + catLabel(cat) + "</span></div>";
    const sub = document.createElement("div");
    sub.className = "sub";
    sub.textContent = cat === "Overview" ? t("nav_overview_sub") : (t("nav_default_sub") + " " + catLabel(cat));
    left.appendChild(sub);

    const count = document.createElement("span");
    count.className = "count";
    count.textContent = String(cat === "Overview" ? "" : ((_byCat.get(cat) || []).length));

    btn.appendChild(left);
    btn.appendChild(count);
    btn.onclick = () => {
      _activePanel = cat;
      _renderNav("nav");
      _renderNav("navMobile");
      _renderPanel();
      _closeDrawer();
    };
    nav.appendChild(btn);
  });
}

function _applyFilter() {
  const q = ($("filter") ? $("filter").value : "").trim().toLowerCase();
  const rows = Array.from(document.querySelectorAll(".settingRow"));
  rows.forEach((row) => {
    const hay = String(row.dataset.hay || "");
    row.style.display = !q || hay.includes(q) ? "" : "none";
  });
}

function _syncTopPills() {
  const st = _status || {};
  if ($("pillProfile")) $("pillProfile").textContent = "profile=" + String(st.profile || "?");
  if ($("pillInstance")) $("pillInstance").textContent = "instance=" + String(st.instance_id || "?");
  if ($("pillMode")) $("pillMode").textContent = "mode=" + String(st.override_mode || "?");
  if ($("SETTINGS_OVERRIDE_MODE")) {
    $("SETTINGS_OVERRIDE_MODE").value = String(st.override_mode || "override").toLowerCase() === "fill" ? "fill" : "override";
  }
}

function _gotoPanel(name) {
  _activePanel = name;
  _renderNav("nav");
  _renderNav("navMobile");
  _renderPanel();
  _closeDrawer();
}

function _renderOverview() {
  const body = $("panelBody");
  body.innerHTML = "";
  _rows.clear();

  const st = _status || {};

  const grid = document.createElement("div");
  grid.className = "sectionGrid";
  body.appendChild(grid);

  const quick = document.createElement("div");
  quick.className = "sectionCard";
  quick.innerHTML = `
    <div class="sectionHead">
      <h3 class="sectionTitle">${t("quick_actions")}</h3>
      <p class="sectionHint"></p>
    </div>
  `;

  const quickBtns = document.createElement("div");
  quickBtns.style.display = "grid";
  quickBtns.style.gridTemplateColumns = "repeat(2, minmax(0, 1fr))";
  quickBtns.style.gap = "10px";

  const mk = (label, target) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "secondary";
    b.style.textAlign = "left";
    b.style.padding = "12px";
    b.style.borderRadius = "16px";
    b.textContent = label;
    b.onclick = () => _gotoPanel(target);
    return b;
  };

  quickBtns.appendChild(mk(t("qa_roles"), "Roles"));
  quickBtns.appendChild(mk(t("qa_permissions"), "Permissions"));
  quickBtns.appendChild(mk(t("qa_approvals"), "Approvals"));
  quickBtns.appendChild(mk(t("qa_relay"), "Relay/Tunnel"));
  quick.appendChild(quickBtns);
  grid.appendChild(quick);

  const status = document.createElement("div");
  status.className = "sectionCard";
  status.innerHTML = `
    <div class="sectionHead">
      <h3 class="sectionTitle">${t("status_title")}</h3>
      <p class="sectionHint"></p>
    </div>
    <div class="msg" style="margin-top:8px;">
      ${t("k_secrets_present")}: ${Object.values(st.secrets_present || {}).filter(Boolean).length}/${Object.keys(st.secrets_present || {}).length}\n
      ${t("k_env_configured")}: ${Object.values(st.env || {}).filter((v)=>!!v).length}/${Object.keys(st.env || {}).length}\n
      ${t("k_state_dir")}: ${String(st.state_dir || "")}\n
      ${t("k_secrets_dir")}: ${String(st.secrets_dir || "")}
    </div>
  `;
  grid.appendChild(status);

  const devUi = document.createElement("div");
  devUi.className = "sectionCard";
  devUi.innerHTML = `
    <div class="sectionHead">
      <h3 class="sectionTitle">${t("dev_ui_title")}</h3>
      <p class="sectionHint">${t("dev_ui_sub")}</p>
    </div>
  `;
  const devUiWrap = document.createElement("div");
  devUiWrap.style.display = "grid";
  devUiWrap.style.gridTemplateColumns = "1fr";
  devUiWrap.style.gap = "8px";

  const uidLabel = document.createElement("label");
  uidLabel.textContent = t("dev_ui_user_id");
  const uidInput = document.createElement("input");
  uidInput.placeholder = "123456789012345678";
  uidInput.id = "devUiUserId";

  const enabledRow = document.createElement("label");
  enabledRow.style.display = "inline-flex";
  enabledRow.style.gap = "8px";
  enabledRow.style.alignItems = "center";
  const enabledInput = document.createElement("input");
  enabledInput.type = "checkbox";
  enabledInput.id = "devUiEnabled";
  const enabledText = document.createElement("span");
  enabledText.textContent = t("dev_ui_enabled");
  enabledRow.appendChild(enabledInput);
  enabledRow.appendChild(enabledText);

  const buttonRow = document.createElement("div");
  buttonRow.className = "row";
  const loadBtn = document.createElement("button");
  loadBtn.type = "button";
  loadBtn.className = "secondary";
  loadBtn.textContent = t("dev_ui_load");
  const saveBtn = document.createElement("button");
  saveBtn.type = "button";
  saveBtn.textContent = t("dev_ui_save");
  buttonRow.appendChild(loadBtn);
  buttonRow.appendChild(saveBtn);

  const devUiMsg = document.createElement("div");
  devUiMsg.className = "msg";
  devUiMsg.id = "devUiMsg";

  loadBtn.onclick = async () => {
    const uid = (uidInput.value || "").trim();
    if (!uid) {
      devUiMsg.textContent = t("error_prefix") + ": " + t("dev_ui_user_id");
      return;
    }
    try {
      const out = await apiGet("/api/platform/dev-ui/status?user_id=" + encodeURIComponent(uid));
      enabledInput.checked = !!out.dev_ui_enabled;
      devUiMsg.textContent = t("dev_ui_loaded") + `: ${out.dev_ui_enabled ? "ON" : "OFF"}`;
    } catch (e) {
      devUiMsg.textContent = t("error_prefix") + ": " + e.message;
    }
  };

  saveBtn.onclick = async () => {
    const uid = (uidInput.value || "").trim();
    if (!uid) {
      devUiMsg.textContent = t("error_prefix") + ": " + t("dev_ui_user_id");
      return;
    }
    try {
      const out = await apiPost("/api/platform/dev-ui/status", {
        user_id: uid,
        enabled: !!enabledInput.checked,
      });
      enabledInput.checked = !!out.dev_ui_enabled;
      devUiMsg.textContent = t("dev_ui_saved") + `: ${out.dev_ui_enabled ? "ON" : "OFF"}`;
    } catch (e) {
      devUiMsg.textContent = t("error_prefix") + ": " + e.message;
    }
  };

  devUiWrap.appendChild(uidLabel);
  devUiWrap.appendChild(uidInput);
  devUiWrap.appendChild(enabledRow);
  devUiWrap.appendChild(buttonRow);
  devUiWrap.appendChild(devUiMsg);
  devUi.appendChild(devUiWrap);
  grid.appendChild(devUi);

  if ((st.notes || []).length) {
    const notes = document.createElement("div");
    notes.className = "sectionCard";
    notes.innerHTML = `
      <div class="sectionHead">
        <h3 class="sectionTitle">${t("notes_title")}</h3>
        <p class="sectionHint"></p>
      </div>
      <div class="msg">${(st.notes || []).join("\\n")}</div>
    `;
    grid.appendChild(notes);
  }
}

function _groupIdFor(cat, key, kind) {
  const K = String(key || "").toUpperCase();
  if (kind === "secret") return "secrets";

  if (cat === "Providers") {
    if (K.includes("OPENAI")) return "openai";
    if (K.includes("ANTHROPIC") || K.includes("CLAUDE")) return "anthropic";
    if (K.includes("GOOGLE") || K.includes("GEMINI")) return "google";
    if (K.includes("GROK") || K.includes("XAI")) return "grok";
    if (K.includes("MISTRAL")) return "mistral";
    return "general";
  }
  if (cat === "Discord") {
    if (K.includes("TOKEN")) return "tokens";
    if (K.includes("APP") || K.includes("CLIENT") || K.includes("GUILD") || K.includes("CHANNEL") || K.endsWith("_ID")) return "ids";
    return "general";
  }
  if (cat === "Roles") {
    if (K.includes("ADMIN") || K.includes("OWNER")) return "ids";
    if (K.includes("ROLE")) return "policy";
    return "general";
  }
  if (cat === "Permissions") {
    if (K.includes("ALLOW") || K.includes("DENY") || K.includes("WHITELIST") || K.includes("BLACKLIST")) return "tools";
    if (K.includes("GUEST") || K.includes("SHARED")) return "policy";
    if (K.includes("RATE") || K.includes("LIMIT")) return "limits";
    return "general";
  }
  if (cat === "Approvals") {
    if (K.includes("TTL") || K.includes("TIMEOUT")) return "limits";
    if (K.includes("CODE")) return "policy";
    if (K.includes("RATE") || K.includes("LIMIT")) return "limits";
    return "policy";
  }
  if (cat === "Relay/Tunnel") {
    if (K.includes("CLOUDFLARE") || K.includes("TUNNEL") || K.includes("CF_")) return "cloudflare";
    if (K.includes("RELAY")) return "relay";
    return "general";
  }
  return "general";
}

function _groupLabel(groupId) {
  return t("group_" + groupId);
}

function _groupOrderFor(cat) {
  if (cat === "Providers") return ["openai", "anthropic", "google", "grok", "mistral", "secrets", "general"];
  if (cat === "Discord") return ["tokens", "ids", "general", "secrets"];
  if (cat === "Permissions") return ["policy", "tools", "limits", "general", "secrets"];
  if (cat === "Approvals") return ["policy", "limits", "general", "secrets"];
  if (cat === "Relay/Tunnel") return ["relay", "cloudflare", "general", "secrets"];
  return ["general", "secrets"];
}

function _renderCategory(cat) {
  const body = $("panelBody");
  body.innerHTML = "";
  _rows.clear();

  const specs = _byCat.get(cat) || [];
  const st = _status || {};
  const env = st.env || {};
  const envSources = st.env_sources || {};
  const secretsPresent = st.secrets_present || {};

  const groups = new Map(); // groupId -> specs[]
  specs.forEach((spec) => {
    const key = String(spec.key || "").trim();
    if (!key) return;
    const kind = String(spec.kind || "env");
    const gid = _groupIdFor(cat, key, kind);
    if (!groups.has(gid)) groups.set(gid, []);
    groups.get(gid).push(spec);
  });

  const grid = document.createElement("div");
  grid.className = "sectionGrid";
  body.appendChild(grid);

  const order = _groupOrderFor(cat);
  const orderedGroupIds = Array.from(new Set(order.concat(Array.from(groups.keys()).sort())));
  orderedGroupIds.forEach((gid) => {
    const arr = groups.get(gid) || [];
    if (!arr.length) return;

    const card = document.createElement("div");
    card.className = "sectionCard";

    const head = document.createElement("div");
    head.className = "sectionHead";

    const h = document.createElement("h3");
    h.className = "sectionTitle";
    h.textContent = _groupLabel(gid);

    const hint = document.createElement("p");
    hint.className = "sectionHint";
    hint.textContent = "";

    head.appendChild(h);
    head.appendChild(hint);
    card.appendChild(head);

    const fieldGrid = document.createElement("div");
    fieldGrid.className = "fieldGrid";
    card.appendChild(fieldGrid);

    arr.forEach((spec) => {
      const key = String(spec.key || "").trim();
      if (!key) return;

      const row = document.createElement("div");
      row.className = "settingRow";
      row.dataset.key = key;
      row.dataset.hay = _rowHay(spec);

      const kind = String(spec.kind || "env");
      const current = env[key] || "";
      const src = envSources[key] ? String(envSources[key]) : (env[key] ? "env" : "unset");

      const k = document.createElement("div");
      k.className = "fieldKey";
      k.textContent = key;
      row.appendChild(k);

      const descText = String(spec.description || "");
      if (descText) {
        const d = document.createElement("div");
        d.className = "fieldDesc";
        d.textContent = descText;
        row.appendChild(d);
      }

      const meta = document.createElement("div");
      meta.className = "settingMeta";
      meta.appendChild(_makeBadge(String(spec.kind || "env"), kind === "secret" ? "warn" : ""));
      if (spec.default) meta.appendChild(_makeBadge(t("default_prefix") + String(spec.default), ""));
      if (spec.locked) meta.appendChild(_makeBadge(t("locked"), "bad"));

      if (kind === "secret") {
        const present = !!secretsPresent[key];
        meta.appendChild(_makeBadge(present ? t("present") : t("missing"), present ? "good" : "bad"));
      } else {
        meta.appendChild(_makeBadge(t("src_prefix") + src, src === "override" ? "warn" : ""));
      }
      row.appendChild(meta);

      if (kind === "secret") {
        const ed = _makeSecretEditor(spec);
        row.appendChild(ed.wrap);

        const onChange = () => {
          const changed = (ed.cb && ed.cb.checked) || ((ed.ta.value || "").trim().length > 0);
          _setRowChanged(row, changed);
          _recountDirty();
        };
        ed.ta.addEventListener("input", onChange);
        ed.cb.addEventListener("change", onChange);
        _rows.set(key, { kind, spec, rowEl: row, inputEl: ed.ta, clearEl: ed.cb, orig: "" });

        row.classList.add("wide");
      } else {
        if (spec.locked) {
          const inp = document.createElement("input");
          inp.value = String(current || "");
          inp.disabled = true;
          row.appendChild(inp);
          _rows.set(key, { kind, spec, rowEl: row, inputEl: inp, clearEl: null, orig: String(current || "") });
        } else {
          const ed = _makeEnvEditor(spec, current, src);
          row.appendChild(ed.wrap);

          const inp = ed.input;
          const orig = String(current || "");
          const inputType = String(spec.input || "");
          const origNorm = inputType === "bool" ? _normBoolValue(orig) : orig;

          const onChange = () => {
            let now;
            if (inputType === "bool") now = inp.dataset && inp.dataset.unset === "1" ? "" : (inp.checked ? "1" : "0");
            else now = (inp.value || "").trim();
            const nowNorm = inputType === "bool" ? _normBoolValue(now) : String(now);
            _setRowChanged(row, nowNorm !== origNorm);
            _recountDirty();
          };
          inp.addEventListener("input", onChange);
          inp.addEventListener("change", onChange);
          _rows.set(key, { kind, spec, rowEl: row, inputEl: inp, clearEl: null, orig });

          if (["textarea", "json"].includes(String(spec.input || ""))) row.classList.add("wide");
        }
      }

      fieldGrid.appendChild(row);
    });

    grid.appendChild(card);
  });

  _applyFilter();
  _recountDirty();
}

function _renderPanel() {
  if ($("panelMsg")) $("panelMsg").textContent = "";
  if (_activePanel === "Overview") {
    $("panelTitle").textContent = t("overview_title");
    $("panelSubtitle").textContent = t("overview_sub");
    _renderOverview();
    return;
  }
  $("panelTitle").textContent = catLabel(_activePanel);
  $("panelSubtitle").textContent = t("category_sub");
  _renderCategory(_activePanel);
}

async function _refreshAll() {
  if ($("panelMsg")) $("panelMsg").textContent = t("loading");
  _schema = await apiGet("/api/settings/schema");
  _status = await apiGet("/api/settings/status");
  _byCat = _buildCategoryMap(_schema);
  _syncTopPills();
  _renderNav("nav");
  _renderNav("navMobile");
  _renderPanel();
  if ($("panelMsg")) $("panelMsg").textContent = "";
  _recountDirty();
}

async function _saveActivePanel() {
  const envChanges = {};
  const secretChanges = {};

  for (const [key, row] of _rows.entries()) {
    const spec = row.spec || {};
    if (row.kind === "secret") {
      const v = row.inputEl && row.inputEl.value ? row.inputEl.value.trim() : "";
      if (row.clearEl && row.clearEl.checked) secretChanges[key] = null;
      else if (v) secretChanges[key] = v;
      continue;
    }
    if (spec.locked) continue;

    const inp = row.inputEl;
    const orig = String(row.orig || "");
    const inputType = String(spec.input || "");

    if (inputType === "bool") {
      const now = inp.dataset && inp.dataset.unset === "1" ? "" : (inp.checked ? "1" : "0");
      const nowNorm = _normBoolValue(now);
      const origNorm = _normBoolValue(orig);
      if (nowNorm === origNorm) continue;
      envChanges[key] = nowNorm ? nowNorm : null;
      continue;
    }

    const now = inp && inp.value ? String(inp.value).trim() : "";
    if (now === orig.trim()) continue;
    envChanges[key] = now ? now : null;
  }

  const mode = $("SETTINGS_OVERRIDE_MODE") && $("SETTINGS_OVERRIDE_MODE").value ? $("SETTINGS_OVERRIDE_MODE").value.trim() : "override";
  const did = [];

  try {
    if (Object.keys(secretChanges).length) {
      await apiPost("/api/settings/secrets", { secrets: secretChanges });
      did.push("secrets");

      // Keep sidebar token in sync when ORA_WEB_API_TOKEN is changed via secrets API.
      if (secretChanges["ORA_WEB_API_TOKEN"] !== undefined) {
        const v = secretChanges["ORA_WEB_API_TOKEN"];
        if (typeof v === "string" && v.trim()) {
          localStorage.setItem("ora_web_api_token", v.trim());
          if ($("token")) $("token").value = v.trim();
          if ($("tokenMobile")) $("tokenMobile").value = v.trim();
        } else if (v === null) {
          localStorage.removeItem("ora_web_api_token");
          if ($("token")) $("token").value = "";
          if ($("tokenMobile")) $("tokenMobile").value = "";
        }
      }
    }

    if (Object.keys(envChanges).length) {
      await apiPost("/api/settings/env", { env: envChanges, mode });
      did.push("env");
    }

    if (!did.length) {
      if ($("panelMsg")) $("panelMsg").textContent = t("no_changes");
      return;
    }

    if ($("panelMsg")) $("panelMsg").textContent = t("saved_prefix") + ": " + did.join(", ") + ". " + t("restart_hint");
    await _refreshAll();
  } catch (e) {
    if ($("panelMsg")) $("panelMsg").textContent = t("error_prefix") + ": " + e.message;
  }
}

function _openDrawer() {
  $("drawerMask").classList.add("on");
  $("drawer").classList.add("on");
}

function _closeDrawer() {
  $("drawerMask").classList.remove("on");
  $("drawer").classList.remove("on");
}

function _applyStaticStrings() {
  document.title = t("title");
  if ($("brandTitle")) $("brandTitle").textContent = t("title");
  if ($("brandDesc")) $("brandDesc").textContent = t("brand_desc");
  if ($("refresh")) $("refresh").textContent = t("refresh");
  if ($("overrideModeLabel")) $("overrideModeLabel").textContent = t("override_mode");
  if ($("filterLabel")) $("filterLabel").textContent = t("filter_label");
  if ($("filter")) $("filter").placeholder = t("filter_ph");
  if ($("token")) $("token").placeholder = t("token_ph");
  if ($("tokenMobile")) $("tokenMobile").placeholder = t("token_ph");
  if ($("saveToken")) $("saveToken").textContent = t("save_token");
  if ($("clearToken")) $("clearToken").textContent = t("clear_token");
  if ($("saveTokenMobile")) $("saveTokenMobile").textContent = t("save_token");
  if ($("clearTokenMobile")) $("clearTokenMobile").textContent = t("clear_token");
  if ($("langTitle")) $("langTitle").textContent = t("language");
  if ($("langTitleMobile")) $("langTitleMobile").textContent = t("language");
  if ($("setupTitle")) $("setupTitle").textContent = t("setup");
  if ($("setupTitleMobile")) $("setupTitleMobile").textContent = t("setup");
  if ($("apiTokenTitle")) $("apiTokenTitle").textContent = t("api_token");
  if ($("apiTokenTitleMobile")) $("apiTokenTitleMobile").textContent = t("api_token");
  if ($("showDescTitle")) $("showDescTitle").textContent = t("show_desc");
  if ($("showDescTitleMobile")) $("showDescTitleMobile").textContent = t("show_desc");

  const modeSel = $("SETTINGS_OVERRIDE_MODE");
  if (modeSel && modeSel.options && modeSel.options.length >= 2) {
    modeSel.options[0].textContent = t("override_mode_override");
    modeSel.options[1].textContent = t("override_mode_fill");
  }
  _updateSaveButton();
}

function init() {
  _applyViewportClasses();
  window.addEventListener("resize", _debounce(_applyViewportClasses, 120));

  const saved = (localStorage.getItem("ora_web_api_token") || "").trim();
  if ($("token")) $("token").value = saved;
  if ($("tokenMobile")) $("tokenMobile").value = saved;

  document.documentElement.lang = _lang;
  _applyDescClass();

  const saveToken = (inputId, msgId) => {
    const tok = ($(inputId).value || "").trim();
    if (tok) localStorage.setItem("ora_web_api_token", tok);
    else localStorage.removeItem("ora_web_api_token");
    $(msgId).textContent = t("saved");
  };

  const clearToken = (inputId, msgId) => {
    localStorage.removeItem("ora_web_api_token");
    $(inputId).value = "";
    $(msgId).textContent = t("cleared");
  };

  $("saveToken").onclick = () => saveToken("token", "authMsg");
  $("clearToken").onclick = () => clearToken("token", "authMsg");
  $("saveTokenMobile").onclick = () => saveToken("tokenMobile", "authMsgMobile");
  $("clearTokenMobile").onclick = () => clearToken("tokenMobile", "authMsgMobile");

  $("refresh").onclick = async () => {
    try {
      await _refreshAll();
    } catch (e) {
      if ($("panelMsg")) $("panelMsg").textContent = t("error_prefix") + ": " + e.message;
    }
  };

  $("savePanel").onclick = _saveActivePanel;
  $("filter").oninput = _applyFilter;

  if ($("menuBtn")) $("menuBtn").onclick = _openDrawer;
  $("drawerMask").onclick = _closeDrawer;

  // Language selectors
  if ($("lang")) $("lang").value = _lang;
  if ($("langMobile")) $("langMobile").value = _lang;
  if ($("lang")) $("lang").onchange = () => { setLang($("lang").value); if ($("langMobile")) $("langMobile").value = _lang; };
  if ($("langMobile")) $("langMobile").onchange = () => { setLang($("langMobile").value); if ($("lang")) $("lang").value = _lang; };

  // Description toggle
  _syncPrefsUI();
  if ($("showDesc")) $("showDesc").onchange = () => { setShowDesc($("showDesc").checked); if ($("showDescMobile")) $("showDescMobile").checked = _showDesc; };
  if ($("showDescMobile")) $("showDescMobile").onchange = () => { setShowDesc($("showDescMobile").checked); if ($("showDesc")) $("showDesc").checked = _showDesc; };

  _applyStaticStrings();

  _refreshAll().catch((e) => {
    if ($("panelMsg")) $("panelMsg").textContent = t("error_prefix") + ": " + e.message + "\n\n" + t("api_token_hint");
  });
}

init();
