/* YonerAI Setup UI (sidebar + categories + toggles) */

const $ = (id) => document.getElementById(id);

function bearerHeaders() {
  const t = (localStorage.getItem("ora_web_api_token") || "").trim();
  if (!t) return {};
  return { Authorization: "Bearer " + t };
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

function _makeSecretEditor(spec) {
  const wrap = document.createElement("div");
  wrap.className = "switchRow";

  const ta = document.createElement("textarea");
  ta.placeholder = "Paste new value (leave empty = no change)";
  wrap.appendChild(ta);

  const clearWrap = document.createElement("div");
  clearWrap.className = "switchWrap";
  const cb = document.createElement("input");
  cb.type = "checkbox";
  const lbl = document.createElement("span");
  lbl.className = "badge warn";
  lbl.textContent = "Clear secret (danger)";
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
  unset.textContent = "Unset";

  const hint = _makeBadge(srcLabel ? "src=" + srcLabel : "src=?", srcLabel === "override" ? "warn" : "");

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
  const t = String(spec.input || "text");
  if (t === "bool") return _makeBoolEditor(currentValue, srcLabel);

  if (t === "textarea" || t === "json") {
    const ta = document.createElement("textarea");
    ta.value = String(currentValue || "");
    if (spec.default && !String(currentValue || "").trim()) ta.placeholder = String(spec.default);
    return { wrap: ta, input: ta };
  }
  if (t === "number") {
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

let _schema = null;
let _status = null;
let _byCat = new Map();
let _activePanel = "Overview";
const _rows = new Map(); // key -> row state

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
    left.innerHTML = "<div>" + cat + "</div>";
    const sub = document.createElement("div");
    sub.className = "sub";
    sub.textContent = cat === "Overview" ? "Status, guard token, quick notes" : "Configure " + cat;
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
  $("pillProfile").textContent = "profile=" + String(st.profile || "?");
  $("pillInstance").textContent = "instance=" + String(st.instance_id || "?");
  $("pillMode").textContent = "mode=" + String(st.override_mode || "?");
  if ($("SETTINGS_OVERRIDE_MODE")) $("SETTINGS_OVERRIDE_MODE").value = String(st.override_mode || "override").toLowerCase() === "fill" ? "fill" : "override";
}

function _renderOverview() {
  const body = $("panelBody");
  body.innerHTML = "";
  _rows.clear();

  const st = _status || {};
  const card = document.createElement("div");
  card.className = "card";
  card.innerHTML = `
    <div style="font-weight:900; letter-spacing:0.2px;">Status</div>
    <div class="msg" style="margin-top:8px;">
      secrets_present: ${Object.values(st.secrets_present || {}).filter(Boolean).length}/${Object.keys(st.secrets_present || {}).length}\n
      env_configured: ${Object.values(st.env || {}).filter((v)=>!!v).length}/${Object.keys(st.env || {}).length}\n
      state_dir: ${String(st.state_dir || "")}\n
      secrets_dir: ${String(st.secrets_dir || "")}
    </div>
    <div class="msg">${(st.notes || []).join("\\n")}</div>
  `;
  body.appendChild(card);
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

  specs.forEach((spec) => {
    const key = String(spec.key || "").trim();
    if (!key) return;

    const row = document.createElement("div");
    row.className = "settingRow";
    row.dataset.key = key;
    row.dataset.hay = _rowHay(spec);

    const left = document.createElement("div");
    const k = document.createElement("div");
    k.className = "settingKey";
    k.textContent = key;
    left.appendChild(k);

    const desc = document.createElement("div");
    desc.className = "settingDesc";
    desc.textContent = String(spec.description || "");
    left.appendChild(desc);

    const meta = document.createElement("div");
    meta.className = "settingMeta";
    meta.appendChild(_makeBadge(String(spec.kind || "env"), spec.kind === "secret" ? "warn" : ""));
    if (spec.default) meta.appendChild(_makeBadge("default=" + String(spec.default), ""));
    if (spec.locked) meta.appendChild(_makeBadge("locked", "bad"));

    const kind = String(spec.kind || "env");
    if (kind === "secret") {
      const present = !!secretsPresent[key];
      meta.appendChild(_makeBadge(present ? "present" : "missing", present ? "good" : "bad"));
    } else {
      const src = envSources[key] ? String(envSources[key]) : (env[key] ? "env" : "unset");
      meta.appendChild(_makeBadge("src=" + src, src === "override" ? "warn" : ""));
    }
    left.appendChild(meta);

    const right = document.createElement("div");

    if (kind === "secret") {
      const ed = _makeSecretEditor(spec);
      right.appendChild(ed.wrap);
      const onChange = () => {
        const changed = (ed.cb && ed.cb.checked) || ((ed.ta.value || "").trim().length > 0);
        _setRowChanged(row, changed);
      };
      ed.ta.addEventListener("input", onChange);
      ed.cb.addEventListener("change", onChange);
      _rows.set(key, { kind, spec, rowEl: row, inputEl: ed.ta, clearEl: ed.cb, orig: "" });
    } else {
      const current = env[key] || "";
      const src = envSources[key] ? String(envSources[key]) : (env[key] ? "env" : "unset");

      if (spec.locked) {
        const inp = document.createElement("input");
        inp.value = String(current || "");
        inp.disabled = true;
        right.appendChild(inp);
        _rows.set(key, { kind, spec, rowEl: row, inputEl: inp, clearEl: null, orig: String(current || "") });
      } else {
        const ed = _makeEnvEditor(spec, current, src);
        right.appendChild(ed.wrap);

        const inp = ed.input;
        const orig = String(current || "");
        const t = String(spec.input || "");
        const origNorm = t === "bool" ? _normBoolValue(orig) : orig;
        const onChange = () => {
          let now;
          if (t === "bool") now = inp.dataset && inp.dataset.unset === "1" ? "" : (inp.checked ? "1" : "0");
          else now = (inp.value || "").trim();
          const nowNorm = t === "bool" ? _normBoolValue(now) : String(now);
          _setRowChanged(row, nowNorm !== origNorm);
        };
        inp.addEventListener("input", onChange);
        inp.addEventListener("change", onChange);
        _rows.set(key, { kind, spec, rowEl: row, inputEl: inp, clearEl: null, orig });
      }
    }

    row.appendChild(left);
    row.appendChild(right);
    body.appendChild(row);
  });

  _applyFilter();
}

function _renderPanel() {
  $("panelMsg").textContent = "";
  if (_activePanel === "Overview") {
    $("panelTitle").textContent = "Overview";
    $("panelSubtitle").textContent = "Status and quick notes.";
    _renderOverview();
    return;
  }
  $("panelTitle").textContent = _activePanel;
  $("panelSubtitle").textContent = "Edit settings in this category. Use filter to narrow down.";
  _renderCategory(_activePanel);
}

async function _refreshAll() {
  $("panelMsg").textContent = "Loading...";
  _schema = await apiGet("/api/settings/schema");
  _status = await apiGet("/api/settings/status");
  _byCat = _buildCategoryMap(_schema);
  _syncTopPills();
  _renderNav("nav");
  _renderNav("navMobile");
  _renderPanel();
  $("panelMsg").textContent = "";
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
    const t = String(spec.input || "");
    if (t === "bool") {
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
      $("panelMsg").textContent = "No changes.";
      return;
    }
    $("panelMsg").textContent = "Saved: " + did.join(", ") + ". Restart may be required.";
    await _refreshAll();
  } catch (e) {
    $("panelMsg").textContent = "Error: " + e.message;
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

function init() {
  const saved = (localStorage.getItem("ora_web_api_token") || "").trim();
  if ($("token")) $("token").value = saved;
  if ($("tokenMobile")) $("tokenMobile").value = saved;

  const saveToken = (inputId, msgId) => {
    const t = ($(inputId).value || "").trim();
    if (t) localStorage.setItem("ora_web_api_token", t);
    else localStorage.removeItem("ora_web_api_token");
    $(msgId).textContent = "Saved.";
  };
  const clearToken = (inputId, msgId) => {
    localStorage.removeItem("ora_web_api_token");
    $(inputId).value = "";
    $(msgId).textContent = "Cleared.";
  };

  $("saveToken").onclick = () => saveToken("token", "authMsg");
  $("clearToken").onclick = () => clearToken("token", "authMsg");
  $("saveTokenMobile").onclick = () => saveToken("tokenMobile", "authMsgMobile");
  $("clearTokenMobile").onclick = () => clearToken("tokenMobile", "authMsgMobile");

  $("refresh").onclick = async () => {
    try {
      await _refreshAll();
    } catch (e) {
      $("panelMsg").textContent = "Error: " + e.message;
    }
  };
  $("savePanel").onclick = _saveActivePanel;
  $("filter").oninput = _applyFilter;

  if ($("menuBtn")) $("menuBtn").onclick = _openDrawer;
  $("drawerMask").onclick = _closeDrawer;

  _refreshAll().catch((e) => {
    $("panelMsg").textContent = "Error: " + e.message + "\\n\\nIf ORA_WEB_API_TOKEN is set, paste it in the sidebar token field.";
  });
}

init();

