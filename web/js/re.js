/* ════════════════════════════════════════════════════════════
   pt-audio-toolkit v4 · re.js（阶段 D：rename-unify 五页签）
   桥存在 → 真功能；无桥（浏览器演示态）→ 视觉可看、动作提示去壳内跑
   壳挂点：__onReLine → __appendLog；__onReEvent ← busy/done/plan/applied/undo/ft_built
   ════════════════════════════════════════════════════════════ */
"use strict";

const HAS_BRIDGE = () => !!(window.pywebview && window.pywebview.api);
const api = () => (HAS_BRIDGE() ? window.pywebview.api : null);
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

/* ── 全局状态 ── */
const state = {
  logN: 0,
  busy: false,
  cfg: null,          // 页1/2 编辑态（template/fields/templates/targets + 页3 选项）
  items: [],          // 当前计划
  stats: {},
  planMode: "all",    // all | master-only
  planReady: false,
  planPending: false,
  planApplying: false,
  refreshAfterApply: false,
  logSel: null,       // 页4 选中 {kind:'log'|'audit', path}
  manualIdx: -1,
};

/* ── 日志（五页共用一个流） ── */
function log(msg, cls) {
  const el = $("log");
  const d = document.createElement("div");
  if (cls) d.className = cls;
  d.textContent = new Date().toTimeString().slice(0, 8) + "  " + msg;
  el.appendChild(d);
  el.scrollTop = el.scrollHeight;
  $("logCnt").textContent = "（" + (++state.logN) + " 条）";
}
window.__appendLog = (cls, msg) => log(msg, cls || "");
window.__onReLine = window.__appendLog;   // 浏览器直开兜底（壳会覆盖，行为等价）

/* ── 壳事件 ── */
function onShellEvent(name, value) {
  if (name === "busy") {
    state.busy = !!value;
    $("envBadge").textContent = value ? "⏳ 任务运行中…" : "就绪";
    syncPlanControls();
    if (!state.busy && state.refreshAfterApply) {
      state.refreshAfterApply = false;
      doPlan(state.planMode);
    }
  } else if (name === "plan") {
    renderPlan(filterPlanForMode(value || {}));
  } else if (name === "applied") {
    onApplied(value || {});
  } else if (name === "undo") {
    log("撤销完成：成功 " + (value && value.done) + " ｜ 失败 " + (value && value.failed),
        value && value.failed ? "err" : "ok");
  } else if (name === "ft_built") {
    log(value.message || ((value.failed ? "工程目录建立失败：新建 " : "工程目录建立完成：新建 ") + value.created + " / 跳过 " + value.skipped + " / 失败 " + value.failed),
        value.failed || value.ok === false ? "err" : "ok");
    if (value.project_root) state.lastFtRoot = value.project_root;
  }
}
window.__onShellEvent = onShellEvent;
window.__onReEvent = onShellEvent;

/* ── 页签路由 ── */
const PAGES = ["rule", "target", "run", "undo", "folder"];
function goto(page) {
  document.querySelector("main").scrollTop = 0;
  PAGES.forEach((p) => {
    $("page-" + p).classList.toggle("on", p === page);
    $("tab-" + p).classList.toggle("on", p === page);
  });
}
function bindTabs() {
  PAGES.forEach(p=>{$('tab-'+p).onclick=()=>goto(p);});
}

/* ── 风格 / 主题切换（家族级偏好，与 pt/剪映共用一份配置） ── */

/* ── 浏览 ── */
async function pickDir(inputId, title) {
  if (!api()) { log("演示态：目录选择需在壳内运行", "info"); return; }
  try { const d = await api().pick_directory(title || "选择目录", $(inputId).value.trim(), inputId); if (d) { $(inputId).value = d; window.ToolPrefs.touch(inputId); if(inputId === "ftTplRoot") updateNamingSamples(); } }
  catch (e) { log("选择失败：" + e, "err"); }
}
async function pickFile(title, kinds) {
  if (!api()) { log("演示态：文件选择需在壳内运行", "info"); return null; }
  try { return await api().pick_file(title || "选择文件", kinds || "csv", $("undoRoot").value.trim(), "undoFile:" + (kinds || "csv")); }
  catch (e) { log("选择失败：" + e, "err"); return null; }
}

/* ══════════ 页 1：字段与模板 ══════════ */
function fieldsFromUi() {
  return { "片名": $("fProject").value.trim(), "日期": $("fDate").value.trim(),
           "版本": $("fVer").value.trim(), "用户": $("fUser").value.trim() };
}
function fillRule(cfg) {
  $("tplGlobal").value = (cfg && cfg.template) || "";
  const f = (cfg && cfg.fields) || {};
  $("fProject").value = f["片名"] || "";
  $("fDate").value = f["日期"] || "";
  $("fVer").value = f["版本"] || "";
  $("fUser").value = f["用户"] || "";
  renderTplTbl();
  updateSample();
}
function renderTplTbl() {
  const tpls = (state.cfg && state.cfg.templates) || [];
  if (!tpls.length) { $("tplTbl").innerHTML = "<div class='empty'>（模板库为空）</div>"; return; }
  $("tplTbl").innerHTML = "<table><thead><tr><th style='width:110px'>名称</th><th>模板</th><th style='width:50px'></th></tr></thead><tbody>" +
    tpls.map((t, i) =>
      "<tr><td><b>" + esc(t.name) + "</b></td>" +
      "<td><input type='text' data-i='" + i + "' class='tpl-edit' value=\"" + esc(t.tpl) + "\" style='width:100%'></td>" +
      "<td><button class='btn danger sm' data-del='" + i + "'>删</button></td></tr>").join("") +
    "</tbody></table>";
  $("tplTbl").querySelectorAll(".tpl-edit").forEach((inp) => {
    inp.onchange = () => { state.cfg.templates[+inp.dataset.i].tpl = inp.value.trim(); updateSample(); };
  });
  $("tplTbl").querySelectorAll("[data-del]").forEach((b) => {
    b.onclick = () => { state.cfg.templates.splice(+b.dataset.del, 1); renderTplTbl(); updateSample(); };
  });
}
function updateSample() {
  const f = fieldsFromUi();
  let s = $("tplGlobal").value || "";
  Object.entries({ "片名": f["片名"] || "剧名", "集数": "13", "日期": f["日期"] || "0929",
                   "版本": f["版本"] || "V01", "用户": f["用户"] || "7F",
                   "轨道信息": "DX BUS", "原始名": "原文件名" }).forEach(([k, v]) => {
    s = s.split("{" + k + "}").join(v);
  });
  $("tplSample").textContent = s + ".wav";
}
async function saveRule() {
  if (!state.cfg) state.cfg = {};
  state.cfg.template = $("tplGlobal").value.trim();
  state.cfg.fields = fieldsFromUi();
  if (!api()) { log("演示态：保存需在壳内运行", "info"); return; }
  const r = await api().save_config_patch({
    template: state.cfg.template, fields: state.cfg.fields,
    templates: state.cfg.templates || [], rename_subtracks: $("runRenameSubtracks").checked, group_master: $("runGroupMaster").checked, rename_files: $("runRenameFiles").checked,
    rename_ep_dirs: $("runRenameDirs").checked, ep_dir_template: $("runDirFormat").value.trim(),
    foldertree: {...(state.cfg.foldertree || {}), episode_template: $("ftEpFormat").value.trim(), episode_padding: +$("ftEpPadding").value, project_template: $("ftProjectFormat").value.trim()} });
  log(r.ok ? "✓ " + r.message : "✗ " + r.message, r.ok ? "ok" : "err");
}

/* ══════════ 页 2：目标表 ══════════ */
function renderTgtTbl() {
  const tpls = (state.cfg && state.cfg.templates) || [];
  const tgts = (state.cfg && state.cfg.targets) || [];
  if (!tgts.length) { $("tgtTbl").innerHTML = "<div class='empty'>（目标表为空——点「恢复出厂」或手动添加）</div>"; return; }
  
  $("tgtTbl").innerHTML = "<table><thead><tr>" +
    "<th style='width:44px'>启用</th><th style='width:70px'>目标</th><th style='width:70px'>归位目录</th>" +
    "<th style='width:90px'>集数</th><th>说明</th><th style='width:210px'>命名格式</th><th style='width:44px'></th>" +
    "</tr></thead><tbody>" +
    tgts.map((t, i) =>
      "<tr><td><input type='checkbox' data-en='" + i + "'" + (t.enabled ? " checked" : "") + "></td>" +
      "<td><input type='text' data-name='" + i + "' value=\"" + esc(t.name) + "\" style='width:100%;min-width:60px'></td>" +
      "<td><input type='text' data-dir='" + i + "' value=\"" + esc(t.dir || "") + "\" style='width:60px'></td>" +
      "<td><input type='text' data-eps='" + i + "' value=\"" + esc(t.eps || "") + "\" style='width:80px' placeholder='全集'></td>" +
      "<td><input type='text' data-note='" + i + "' value=\"" + esc(t.note || "") + "\" style='width:100%'></td>" +
      "<td><select data-tpl='" + i + "'><option value=''>跟随文件名格式</option><option value='custom'>单独设置</option></select>" +
      "<input type='text' data-format='" + i + "' value=\"" + esc((t.templates || [])[0] || "") + "\" style='width:100%;margin-top:4px'></td>" +
      "<td><button class='btn danger sm' data-del='" + i + "'>删</button></td></tr>").join("") +
    "</tbody></table>";
  $("tgtTbl").querySelectorAll("[data-name]").forEach((el) => {
    el.onchange = () => {
      const index = +el.dataset.name, target = state.cfg.targets[index];
      const previous = target.name, name = el.value.trim().toUpperCase();
      if (!name || state.cfg.targets.some((t, i) => i !== index && t.name.toUpperCase() === name)) {
        el.value = previous;
        log("目标名称不能为空或重复", "err");
        return;
      }
      target.name = name;
      el.value = name;
      const rules = state.cfg.rules?.length ? state.cfg.rules : state.defaults?.rules || [];
      state.cfg.rules = rules.map(row => row[0].toUpperCase() === previous.toUpperCase() ? [name, ...row.slice(1)] : [...row]);
    };
  });
  $("tgtTbl").querySelectorAll("[data-en]").forEach((el) => {
    el.onchange = () => { state.cfg.targets[+el.dataset.en].enabled = el.checked; };
  });
  $("tgtTbl").querySelectorAll("[data-dir]").forEach((el) => {
    el.onchange = () => { state.cfg.targets[+el.dataset.dir].dir = el.value.trim(); };
  });
  $("tgtTbl").querySelectorAll("[data-eps]").forEach((el) => {
    el.onchange = () => { state.cfg.targets[+el.dataset.eps].eps = el.value.trim(); };
  });
  $("tgtTbl").querySelectorAll("[data-note]").forEach((el) => {
    el.onchange = () => { state.cfg.targets[+el.dataset.note].note = el.value.trim(); };
  });
  $("tgtTbl").querySelectorAll("[data-tpl]").forEach((el) => {
    const t = state.cfg.targets[+el.dataset.tpl];
    const input = $("tgtTbl").querySelector('[data-format="' + el.dataset.tpl + '"]');
    el.value = (t.templates || []).length ? "custom" : "";
    input.disabled = !el.value;
    input.onchange = () => { t.templates = input.value.trim() ? [input.value.trim()] : []; t.tpl_name = ""; };
    el.onchange = () => {
      t.tpl_name = "";
      t.templates = el.value ? [input.value.trim() || $("tplGlobal").value] : [];
      input.value = t.templates[0] || "";
      input.disabled = !el.value;
    };
  });
  $("tgtTbl").querySelectorAll("[data-del]").forEach((b) => {
    b.onclick = () => { state.cfg.targets.splice(+b.dataset.del, 1); renderTgtTbl(); };
  });
}
async function saveTargets() {
  if (!api()) { log("演示态：保存需在壳内运行", "info"); return; }
  const r = await api().save_config_patch({ targets: (state.cfg && state.cfg.targets) || [], rules: (state.cfg && state.cfg.rules) || [] });
  log(r.ok ? "✓ " + r.message : "✗ " + r.message, r.ok ? "ok" : "err");
}

/* ══════════ 页 3：计划与执行 ══════════ */
function runParams(mode = "all") {
  const params = {
    root: $("runRoot").value.trim(),
    exts: $("runExts").value.trim(),
    recursive: $("runRecursive").checked,
    date_from_mtime: $("runMtime").checked,
    rename_ep_dirs: $("runRenameDirs").checked,
    rename_subtracks: $("runRenameSubtracks").checked, group_master: $("runGroupMaster").checked, rename_files: $("runRenameFiles").checked, ep_dir_template: $("runDirFormat").value.trim(),
    template: $("tplGlobal").value.trim(),
    fields: fieldsFromUi(),
    targets: (state.cfg && state.cfg.targets) || [],
    rules: (state.cfg && state.cfg.rules) || [],
  };
  if (mode === "master-only") {
    params.rename_ep_dirs = false;
    params.rename_subtracks = false;
    params.group_master = false;
    params.rename_files = true;
  }
  return params;
}
function filterPlanForMode(plan) {
  if (state.planMode !== "master-only") return plan;
  const items = (plan.items || []).filter((item) => String(item.target || "").toUpperCase() === "MIX");
  return { ...plan, items, total: items.length, stats: recomputeStats(items),
    message: items.length ? plan.message : "没有识别到可命名的 Master（MIX）文件" };
}
function syncPlanControls() {
  const masterOnly = state.planMode === "master-only";
  const pending = state.stats.rename ?? state.stats[""] ?? 0;
  $("btnApply").textContent = masterOnly ? "▶ 执行 Master 改名" : "▶ 执行重命名";
  $("btnApply").disabled = state.busy || !state.planReady || !pending;
  $("btnCancelPlan").hidden = !(state.planReady || state.planPending);
  $("btnCancelPlan").disabled = state.busy || state.planPending || state.planApplying;
  ["planModeAll", "planModeMaster"].forEach((id) => { $(id).disabled = state.busy || state.planPending; });
  $("runModeHint").textContent = masterOnly
    ? (state.planPending ? "正在生成 Master 专用计划……"
      : state.planApplying ? "正在执行 Master 改名；不能中途取消，完成后可用改名记录撤销。"
      : state.busy ? "当前有其他任务运行；完成后可继续处理 Master 计划。"
      : state.planReady ? "Master 专用计划：仅改名，文件留在原目录。可执行或取消本次计划。"
      : "Master 专用模式：选择目录后生成计划。")
    : (state.planPending ? "正在生成计划……"
      : state.planApplying ? "正在执行重命名；不能中途取消，完成后可用改名记录撤销。"
      : state.planReady ? "计划已生成；确认预览后执行，或取消本次计划。"
      : "先生成计划，再执行。");
}
async function doPlan(mode = state.planMode) {
  if (!api()) { log("演示态：扫描需在壳内运行（python shell/re_desktop.py）", "info"); return; }
  if (state.busy) { log("已有任务在进行中", "err"); return; }
  state.planMode = mode;
  state.planReady = false;
  state.planPending = true;
  state.planApplying = false;
  state.planParams = null;
  state.items = [];
  state.stats = {};
  renderPlan({ items: [], total: 0, stats: {}, message: "正在生成计划……" }, false);
  state.planPending = true;
  syncPlanControls();
  try {
    await window.ToolPrefs.flush();
    const p = runParams(mode);
  if (mode !== "master-only" && !$("runDirFormat").checkValidity()) { $("runGroupDetails").open=true; $("runDirFormat").reportValidity(); renderPlan({ items: [], total: 0, stats: {}, message: "命名格式无效，未生成计划" }, false); return; }
    if (!p.root) { renderPlan({ items: [], total: 0, stats: {}, message: "请先选择目标目录" }, false); log("请先选择目标目录", "err"); return; }
    state.planParams = JSON.stringify(p);
    const r = await api().plan(p);
    if (!r.ok) { state.planParams = null; state.planPending = false; syncPlanControls(); log("✗ " + r.message, "err"); }
    else { log("✓ " + r.message, "ok"); if (Array.isArray(r.items)) renderPlan(filterPlanForMode(r)); }
    /* 后台计划结果走 plan 事件；空计划直接清空预览。 */
  } catch (e) { state.planPending = false; state.planParams = null; syncPlanControls(); log("扫描异常：" + e, "err"); }
}
const STATUS_LABEL = { "": "待处理", skip: "跳过", error: "错误", conflict: "冲突", excluded: "排除" };
function renderPlan(p, ready = true) {
  const priority = { "": 0, error: 1, conflict: 1, excluded: 2, skip: 3 };
  state.items = [...(p.items || [])].sort((a, b) => (priority[a.status] ?? 2) - (priority[b.status] ?? 2));
  state.stats = p.stats || {};
  state.planReady = ready;
  state.planPending = false;
  const n = state.stats.rename ?? state.stats[""] ?? 0;
  const bad = (state.stats.error || 0) + (state.stats.conflict || 0);
  $("planTag").textContent = "待处理 " + n + (bad ? " ｜ 错/冲突 " + bad : "");
  $("planText").textContent = "计划：" + (p.total || 0) + " 项 ｜ 待处理 " + n;
  $("planDot").classList.toggle("off", !p.total);
  $("btnApply").disabled = !n || !ready;
  syncPlanControls();
  if (!state.items.length) {
    $("planTbl").innerHTML = "<div class='empty'>（" + (p.message || "没有文件") + "）</div>";
    return;
  }
  $("planTbl").innerHTML = "<table><thead><tr>" +
    "<th style='width:64px'>状态</th><th style='width:56px'>目标</th><th style='width:190px'>原路径</th>" +
    "<th>目标路径</th><th style='width:150px'>说明</th><th style='width:56px'></th>" +
    "</tr></thead><tbody>" +
    state.items.map((it, i) => {
      const cls = it.status === "error" || it.status === "conflict" ? "err"
        : it.status === "excluded" || it.status === "skip" ? "dim" : "ok";
      const short = (s) => {
        const normalized = s.replaceAll('\\','/'), root = $("runRoot").value.trim().replaceAll('\\','/').replace(/\/$/,'');
        return esc(root && normalized.toLowerCase().startsWith(root.toLowerCase()+'/') ? normalized.slice(root.length+1) : normalized);
      };
      return "<tr class='" + cls + "'><td data-i18n-ui>" + (STATUS_LABEL[it.status] || it.status) + "</td>" +
        "<td>" + esc(it.target || "") + "</td>" +
        "<td title=\"" + esc(it.src) + "\">" + short(it.src) + "</td>" +
        "<td title=\"" + esc(it.dst) + "\">" + (it.changed_ !== false ? short(it.dst) : "—") + "</td>" +
        "<td style='font-size:11px;color:var(--dim)'>" + esc(it.note || "") + "</td>" +
        "<td>" + (it.status === "error" ? "<button class='btn ghost sm' data-man='" + i + "'>手动</button>" : "") + "</td></tr>";
    }).join("") + "</tbody></table>";
  $("planTbl").querySelectorAll("[data-man]").forEach((b) => {
    b.onclick = () => openManual(+b.dataset.man);
  });
}
function openManual(i) {
  const it = state.items[i];
  if (!it) return;
  state.manualIdx = i;
  $("manualFile").textContent = it.src.split("\\").slice(-1)[0];
  $("manEp").value = it.ep || "";
  $("manTarget").value = it.target || "MIX";
  $("manTarget").disabled = state.planMode === "master-only";
  $("manInfo").value = it.info || "";
  $("manualBox").style.display = "";
}
async function manualOk() {
  const it = state.items[state.manualIdx];
  if (!it || !api()) return;
  try {
    const params = runParams(state.planMode);
    const r = await api().manual_replan({
      path: it.src, ep: $("manEp").value.trim(),
      target: $("manTarget").value.trim(), info: $("manInfo").value.trim(),
      template: params.template, fields: params.fields,
      targets: (state.cfg && state.cfg.targets) || [],
      root: $("runRoot").value.trim(),
      rename_ep_dirs: params.rename_ep_dirs, rename_subtracks: params.rename_subtracks, group_master: params.group_master, rename_files: params.rename_files, ep_dir_template: params.ep_dir_template });
    if (!r.ok) { log("✗ " + r.message, "err"); return; }
    Object.assign(it, r.item, { note: "手动分类" });
    log("✓ 已重算：" + it.src.split("\\").slice(-1)[0] + " → " + it.dst.split("\\").slice(-1)[0], "ok");
    $("manualBox").style.display = "none";
    renderPlan({ items: state.items, total: state.items.length,
                 stats: recomputeStats(state.items) });
  } catch (e) { log("重算异常：" + e, "err"); }
}
function recomputeStats(items) {
  const s = {};
  items.forEach((i) => { s[i.status] = (s[i.status] || 0) + 1; });
  return s;
}
async function doApply() {
  if (!api()) { log("演示态：执行需在壳内运行", "info"); return; }
  if (state.busy) { log("已有任务在进行中", "err"); return; }
  if (state.planParams !== JSON.stringify(runParams(state.planMode))) { log("选项已改变，请重新生成计划", "err"); $("btnApply").disabled = true; return; }
  const todo = state.items.filter((i) => i.status === "" &&
    (state.planMode !== "master-only" || String(i.target || "").toUpperCase() === "MIX"));
  if (!todo.length) { log("没有「待改名」的文件", "err"); return; }
  const bad = (state.stats.error || 0) + (state.stats.conflict || 0);
  const operation = state.planMode === "master-only"
    ? "即将仅重命名 " + todo.length + " 个 Master 文件，不会移动或打包其他文件。"
    : "即将重命名/移动 " + todo.length + " 个文件。";
  if (!confirm(operation + "\n\n" +
      "· 会生成回溯日志 rename_log_*.csv，可随时撤销\n" +
      "· 如有同名文件将按计划跳过（不会覆盖）" +
      (bad ? "\n\n注意：另有 " + bad + " 个文件因识别失败或冲突将被跳过" : "") +
      "\n\n是否继续？")) return;
  try {
    state.planApplying = true;
    syncPlanControls();
    const r = await api().apply(todo, $("runRoot").value.trim());
    if (!r.ok) { state.planApplying = false; syncPlanControls(); }
    log(r.ok ? "✓ " + r.message : "✗ " + r.message, r.ok ? "ok" : "err");
  } catch (e) { state.planApplying = false; syncPlanControls(); log("执行异常：" + e, "err"); }
}
function onApplied(v) {
  $("undoRoot").value = $("runRoot").value.trim();
  if (v.log_path) log("回溯日志：" + v.log_path, "info");
  if (v.emptied && v.emptied.length) log("提示：" + v.emptied.length + " 个源集目录已空（只报告不删除）", "info");
  state.refreshAfterApply = true;
}
function cancelPlan() {
  if (state.busy || state.planPending || state.planApplying) return;
  state.planReady = false;
  state.planParams = null;
  state.items = [];
  state.stats = {};
  $("manualBox").style.display = "none";
  renderPlan({ items: [], total: 0, stats: {}, message: "本次计划已取消" }, false);
}

/* ══════════ 页 4：回溯与撤销 ══════════ */
async function listLogs(kind) {
  if (!api()) { log("演示态：需在壳内运行", "info"); return; }
  const root = ($("undoRoot").value.trim() || $("runRoot").value.trim());
  if (!root) { log("请先填目标目录", "err"); return; }
  try {
    const r = await (kind === "audit" ? api().list_audits(root) : api().list_logs(root));
    if (!r.ok) { log("✗ " + r.message, "err"); return; }
    log("✓ " + r.message, "ok");
    state.logSel = null;
    ["btnLogPreview", "btnUndoDry", "btnUndoRun"].forEach((id) => { $(id).disabled = true; });
    $("logTbl").innerHTML = r.items.length
      ? "<table><thead><tr><th style='width:34px'></th><th>文件</th><th style='width:110px'>时间</th><th style='width:64px'>KB</th></tr></thead><tbody>" +
        r.items.map((it, i) =>
          "<tr><td><input type='radio' name='logsel' data-i='" + i + "'></td>" +
          "<td title=\"" + esc(it.path) + "\">" + esc(it.file) + "</td>" +
          "<td>" + esc(it.mtime) + "</td><td>" + it.size_kb + "</td></tr>").join("") +
        "</tbody></table>"
      : "<div class='empty'>（没有找到）</div>";
    $("logTbl").querySelectorAll("input[name=logsel]").forEach((el) => {
      el.onchange = () => {
        const it = r.items[+el.dataset.i];
        state.logSel = { kind: kind, path: it.path };
        ["btnLogPreview", "btnUndoDry", "btnUndoRun"].forEach((id) => { $(id).disabled = false; });
      };
    });
  } catch (e) { log("列举异常：" + e, "err"); }
}
async function previewSel() {
  if (!state.logSel || !api()) return;
  try {
    const r = state.logSel.kind === "audit"
      ? await api().preview_log(state.logSel.path)
      : await api().preview_log(state.logSel.path);
    if (!r.ok) { log("✗ " + r.message, "err"); return; }
    $("logPreview").innerHTML =
      "<table><thead><tr><th style='width:50%'>原文件</th><th>新文件</th></tr></thead><tbody>" +
      r.rows.map((row) => "<tr><td style='font-size:11.5px'>" + esc(row[0]) + "</td>" +
        "<td style='font-size:11.5px'>" + esc(row[1]) + "</td></tr>").join("") +
      "</tbody></table><div class='note'>共 " + r.total + " 行" +
      (r.total > 200 ? "（只显示前 200）" : "") + "</div>";
  } catch (e) { log("预览异常：" + e, "err"); }
}
async function undoSel(dry) {
  if (!state.logSel || !api()) return;
  if (!dry && !confirm("将按该文件倒序把「新文件」改回「原文件」。\n确认执行撤销？")) return;
  try {
    const fn = state.logSel.kind === "audit" ? api().undo_audit : api().undo_log;
    const r = await fn(state.logSel.path, !!dry);
    log(r.ok ? "✓ " + r.message : "✗ " + r.message, r.ok ? "ok" : "err");
  } catch (e) { log("撤销异常：" + e, "err"); }
}

/* ══════════ 页 5：工程文件夹 ══════════ */
function ftParams() {
  return {
    template_root: $("ftTplRoot").value.trim(), output_root: $("ftOutRoot").value.trim(),
    name: $("ftName").value.trim(), seq: $("ftSeq").value.trim(),
    level: $("ftLevel").value.trim(), date: $("ftDate").value.trim(),
    user: $("ftUser").value.trim(), eps: $("ftEps").value.trim(),
    episode_template: $("ftEpFormat").value.trim(), episode_padding: +$("ftEpPadding").value,
    project_template: $("ftProjectFormat").value.trim(), ptx_mode: $("ftPtx").value,
    skip_existing: $("ftSkip").checked,
  };
}
function fillFt(form, opts) {
  const f = form || {};
  $("ftTplRoot").value = f.template_root || "";
  $("ftOutRoot").value = f.output_root || "";
  $("ftName").value = f.name || "";
  $("ftSeq").value = f.seq || "";
  $("ftLevel").value = f.level || "";
  $("ftDate").value = f.date || "";
  $("ftUser").value = f.user || "";
  $("ftEps").value = f.eps || "1-10";
  $("ftEpFormat").value = f.episode_template || "{片名} {集数}集";
  $("ftEpPadding").value = String(f.episode_padding || 0);
  $("ftProjectFormat").value = f.project_template || "{片名}{等级}_{日期}_{用户}";
  $("ftPtx").innerHTML = (opts && opts.ptx_modes || []).map((o) =>
    "<option value='" + esc(o.key) + "'>" + esc(o.label) + "</option>").join("");
  $("ftPtx").value = f.ptx_mode || "原样复制";
}
function validFolderFormats() {
  for (const id of ["ftProjectFormat", "ftEpFormat"]) if (!$(id).checkValidity()) { const group=$(id).closest("details");if(group)group.open=true; $(id).reportValidity(); return false; }
  return true;
}
async function ftPlan(silent) {
  if (!validFolderFormats()) return;
  await window.ToolPrefs.flush();
  if (!api()) { $("ftPreview").textContent = "（演示态：预览需在壳内运行）"; return; }
  try {
    const r = await api().ft_plan(ftParams());
    if (!r.ok) { $("ftPreview").textContent = r.preview || r.message || "规划失败"; $("ftExample").textContent = "未生成建立计划"; if (!silent) log("✗ " + (r.message || "规划失败"), "err"); return; }
    $("ftPreview").textContent = r.preview;
    $("ftExample").textContent = "示例：" + r.example + "（" + r.steps + " 步）";
    if (!silent) log("✓ 已刷新预览：" + r.steps + " 步", "ok");
  } catch (e) { if (!silent) log("规划异常：" + e, "err"); }
}
async function ftPrecheck() {
  if (!validFolderFormats()) return;
  if (!api()) { log("演示态：预检需在壳内运行", "info"); return; }
  try {
    const r = await api().ft_precheck(ftParams());
    const probs = r.problems || [];
    log(probs.length ? "⚠ 预检发现 " + probs.length + " 个问题：\n· " + probs.join("\n· ")
                     : "✓ 预检通过，无问题", probs.length ? "err" : "ok");
  } catch (e) { log("预检异常：" + e, "err"); }
}
async function ftBuild() {
  if (!validFolderFormats()) return;
  await window.ToolPrefs.flush();
  if (!api()) { log("演示态：建立需在壳内运行", "info"); return; }
  if (state.busy) { log("已有任务在进行中", "err"); return; }
  const p = ftParams();
  if (!p.output_root) { log("请先选输出根目录", "err"); return; }
  if (!confirm("将在以下位置建立目录/文件：\n" + p.output_root + "\n\n是否继续？")) return;
  try {
    const r = await api().ft_build(p);
    log(r.ok ? "✓ " + r.message : "✗ " + r.message, r.ok ? "ok" : "err");
  } catch (e) { log("建立异常：" + e, "err"); }
}
async function ftInfer() {
  await window.ToolPrefs.flush();
  if (!api()) { log("演示态：提取需在壳内运行", "info"); return; }
  const out = $("ftOutRoot").value.trim();
  if (!out) { log("先填输出根目录", "err"); return; }
  try {
    const r = await api().ft_infer(out);
    if (!r.ok) { log("✗ " + r.message, "err"); return; }
    const f = r.fields || {};
    if (f.name) $("ftName").value = f.name;
    if (f.level) $("ftLevel").value = f.level;
    if (f.date) $("ftDate").value = f.date;
    if (f.user) $("ftUser").value = f.user;
    if (r.next_seq) $("ftSeq").value = String(r.next_seq);
    log("✓ 已提取：" + JSON.stringify(f) + "，下一序号 " + r.next_seq, "ok");
  } catch (e) { log("提取异常：" + e, "err"); }
}

/* ── 加载配置 ── */
async function loadAll() {
  if (!api()) return;
  try {
    const r = await api().get_config();
    if (r.ok) {
      state.cfg = r.cfg;
      state.defaults = r.defaults;
      if (!state.cfg.templates || !state.cfg.templates.length) state.cfg.templates = r.defaults.templates;
      if (!state.cfg.targets || !state.cfg.targets.length) state.cfg.targets = r.defaults.targets;
      fillRule(state.cfg);
      renderTgtTbl();
      $("runRoot").value = r.cfg.last_root || "";
      $("undoRoot").value = r.cfg.last_root || "";
      $("runExts").value = r.cfg.exts || ".wav .aif .aiff .mp3 .flac .w64";
      $("runRecursive").checked = r.cfg.recursive !== false;
      $("runMtime").checked = r.cfg.date_from_mtime !== false;
      $("runRenameDirs").checked = r.cfg.rename_ep_dirs !== false;
      $("runRenameFiles").checked = r.cfg.rename_files === true;
      $("runGroupMaster").checked = r.cfg.group_master !== false;
      $("runRenameSubtracks").checked = r.cfg.rename_subtracks !== false;
      $("runDirFormat").value = r.cfg.ep_dir_template || "{集数}";
    }
    const f = await api().ft_form();
    if (f.ok) fillFt(f.form, f);
  } catch (e) { log("配置加载失败：" + e, "err"); }
}

/* ── 初始化 ── */
let inited = false;
async function init() {
  if (inited && (!HAS_BRIDGE() || state.bridgeLoaded)) return;
  inited = true;
  bindTabs();
  /* 页1 */
  ["tplGlobal", "fProject", "fDate", "fVer", "fUser"].forEach((id) => {
    $(id).addEventListener("input", updateSample);
  });
  $("btnRuleSave").onclick = saveRule;
  $("btnTplAdd").onclick = () => {
    const name = $("tplNewName").value.trim(), tpl = $("tplNewBody").value.trim();
    if (!name || !tpl) { log("模板名与内容都要填", "err"); return; }
    state.cfg.templates.push({ name: name, tpl: tpl });
    $("tplNewName").value = ""; $("tplNewBody").value = "";
    renderTplTbl(); log("已加模板（记得保存）：" + name, "info");
  };
  $("btnTplReset").onclick = () => {
    if (!confirm("模板库恢复出厂（当前修改丢弃）？")) return;
    state.cfg.templates = JSON.parse(JSON.stringify((state.defaults || {}).templates ||
      [{ name: "全格式", tpl: "{片名} {集数}集 {日期} {版本} {用户}_{轨道信息}" }]));
    renderTplTbl();
  };
  /* 页2 */
  $("btnTgtAdd").onclick = () => {
    state.cfg.targets.push({ name: "NEW", dir: "", enabled: false, eps: "",
                             note: "", templates: [], tpl_name: "" });
    renderTgtTbl();
  };
  $("btnTgtAllOn").onclick = () => { state.cfg.targets.forEach((t) => { t.enabled = true; }); renderTgtTbl(); };
  $("btnTgtAllOff").onclick = () => { state.cfg.targets.forEach((t) => { t.enabled = false; }); renderTgtTbl(); };
  $("btnTgtReset").onclick = () => {
    if (!confirm("目标表恢复出厂（当前修改丢弃）？")) return;
    state.cfg.targets = JSON.parse(JSON.stringify((state.defaults || {}).targets ||
      [{ name: "MIX", dir: "", enabled: true }, { name: "BUS", dir: "BUS", enabled: true },
       { name: "STEM", dir: "STEM", enabled: true }, { name: "AIFX", dir: "STEM", enabled: true }]));
    renderTgtTbl();
  };
  $("btnTgtSave").onclick = saveTargets;
  /* 页3 */
  $("runBrowseRoot").onclick = () => pickDir("runRoot", "选择目标目录");
  $("planModeAll").onchange = () => { if ($("planModeAll").checked) doPlan("all"); };
  $("planModeMaster").onchange = () => { if ($("planModeMaster").checked) doPlan("master-only"); };
  [["btnPlan", "planModeAll", "all"], ["btnMasterOnly", "planModeMaster", "master-only"]].forEach(([labelId, radioId, mode]) => {
    const label = $(labelId);
    label.addEventListener("pointerdown", () => { label.dataset.wasSelected = String($(radioId).checked); });
    label.addEventListener("keydown", (event) => { if (event.key === " " && $(radioId).checked) label.dataset.wasSelected = "true"; });
    label.onclick = () => {
      if (label.dataset.wasSelected === "true" && $(radioId).checked) doPlan(mode);
      delete label.dataset.wasSelected;
    };
  });
  $("btnCancelPlan").onclick = cancelPlan;
  $("btnApply").onclick = doApply;
  $("btnManOk").onclick = manualOk;
  $("btnManCancel").onclick = () => { $("manualBox").style.display = "none"; };
  /* 页4 */
  $("undoBrowseRoot").onclick = () => pickDir("undoRoot", "选择目标目录");
  $("btnListLogs").onclick = () => listLogs("log");
  $("btnListAudits").onclick = () => listLogs("audit");
  $("btnLogPreview").onclick = previewSel;
  $("btnUndoDry").onclick = () => undoSel(true);
  $("btnUndoRun").onclick = () => undoSel(false);
  /* 页5 */
  $("ftBrowseTpl").onclick = () => pickDir("ftTplRoot", "选择模板根目录");
  $("ftBrowseOut").onclick = () => pickDir("ftOutRoot", "选择输出根目录");
  $("btnFtInfer").onclick = ftInfer;
  $("btnFtPlan").onclick = () => ftPlan(false);
  $("btnFtPrecheck").onclick = ftPrecheck;
  $("btnFtBuild").onclick = ftBuild;
  $("btnClear").onclick = () => { $("log").innerHTML = ""; state.logN = 0; $("logCnt").textContent = "（0 条）"; };

  if (HAS_BRIDGE()) {
    state.bridgeLoaded=true;
    
    await loadAll();
    log("✓ 工具已就绪", "ok");
  } else {
    $("demoTip").style.display = "";
    $("planText").textContent = "演示态不探测";
    setTimeout(() => log("提示：浏览器演示态——五页真功能需在壳内运行（python shell/re_desktop.py）", "info"), 200);
  }
  initNamingFormats();
  syncPlanControls();
  window.dispatchEvent(new Event('toolready'));
}
window.addEventListener("pywebviewready", init);
if (HAS_BRIDGE()) { setTimeout(init, 50); }
else { document.addEventListener("DOMContentLoaded", init); }

window.addEventListener('parametersrestored', () => { syncFormats(); updateSample(); updateNamingSamples(); });

/* Explicit format objects share the same value across settings and the creation page. */
const formatPairs = [["ftProjectFormat", "cfgProjectFormat"], ["ftEpFormat", "cfgEpisodeFormat"], ["ftEpPadding", "cfgEpisodePadding"]];
function syncFormats() { formatPairs.forEach(([main, copy]) => { $(copy).value = $(main).value; }); }
function folderExample(template, fields, pad=0, required=false) {
  if (!template.trim()) throw Error("命名格式不能为空");
  if (required && !template.includes("{集数}")) throw Error("集数文件夹格式必须包含{集数}");
  let result=template.replace(/\{([^{}]+)\}/g, (_, key) => {
    if (!Object.prototype.hasOwnProperty.call(fields,key)) throw Error("命名格式含未知字段");
    return key === "集数" ? String(Number(fields[key])).padStart(pad,"0") : fields[key];
  }).replace(/\s+/g," ").trim();
  if (/[{}<>:"/\\|?*\x00-\x1f]/.test(result) || !result || result === "." || result === ".." || result.endsWith(".") || /^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?$/i.test(result)) throw Error("命名结果不是有效的Windows文件夹名");
  return result;
}
function updateNamingSamples() {
  $("runFileSummary").textContent = $("tplGlobal").value || "—";
  const t=window.ToolI18n.translate;
  $("runScanSummary").textContent=t($("runRecursive").checked ? "含子目录" : "仅当前目录") + " · " + $("runExts").value.trim();
  $("runFileModeSummary").textContent=$("runRenameFiles").checked ? ($("tplGlobal").value || "—") : t("保持原名");
  $("runFileModeSummary").title=$("runFileModeSummary").textContent;
  const ft={片名:$("ftName").value || "片名",等级:$("ftLevel").value,日期:$("ftDate").value || "1015",版本:"V01",用户:$("ftUser").value,集数:($("ftEps").value.match(/\d+/)||["24"])[0]};
  const batch={...fieldsFromUi(),集数:"24",等级:""};
  for(const [input, output, fields, padding, required] of [["ftEpFormat","ftNameSample",ft,+$("ftEpPadding").value,true],["runDirFormat","runDirSample",batch,0,true],["ftProjectFormat",null,ft,0,false]]) {
    const el=$(input);let error="";
    try{const text=folderExample(el.value,fields,padding,required);if(output)$(output).textContent=text;}
    catch(e){error=e.message;if(output)$(output).textContent=window.ToolI18n.translate(error);}
    el.setCustomValidity(error);
  }
  $("runGroupSummary").textContent=$("runRenameDirs").checked ? $("runDirFormat").value + " → " + $("runDirSample").textContent : t("已关闭");
  $("runGroupSummary").title=$("runGroupSummary").textContent;
  $("cfgEpisodeSample").textContent=$("ftNameSample").textContent;
  for (const [output, value] of [["ftTemplateSummary",$("ftTplRoot").value || "—"],["ftProjectSummary",$("ftProjectFormat").value],["ftEpisodeSummary",$("ftEpFormat").value + " → " + $("ftNameSample").textContent]]) {
    $(output).textContent=value;$(output).title=value;
  }
  const selected=$("ftPtx").selectedOptions[0];
  $("ftFileSummary").textContent=selected ? window.ToolI18n.sourceText(selected) : "—";
  $("runDirFormat").disabled=!$("runRenameDirs").checked;
  document.querySelectorAll("#runGroupDetails [data-field]").forEach(button=>{button.disabled=!$("runRenameDirs").checked;});
  $("btnApply").disabled=!(state.stats.rename ?? state.stats[""] ?? 0);
}
let namingBound=false;
function initNamingFormats() {
  if(namingBound){syncFormats();updateNamingSamples();return;} namingBound=true;
  formatPairs.forEach(([main,copy]) => {
    for(const [from,to] of [[main,copy],[copy,main]]) ["input","change"].forEach(event => $(from).addEventListener(event,()=>{ $(to).value=$(from).value;window.ToolPrefs.touch(to);updateNamingSamples(); }));
  });
  document.querySelectorAll('[data-insert]').forEach(group=>{
    group.innerHTML=group.dataset.fields.split(',').map(field=>'<button type="button" class="btn ghost sm" data-field="'+field+'">'+field+'</button>').join('');
    group.querySelectorAll('button').forEach(btn=>btn.onclick=()=>{const input=$(group.dataset.insert);input.focus();input.setRangeText('{'+btn.dataset.field+'}',input.selectionStart,input.selectionEnd,'end');input.dispatchEvent(new Event('input',{bubbles:true}));});
  });
  document.querySelectorAll('[data-ep-format]').forEach(btn=>btn.onclick=()=>{$('ftEpFormat').value=btn.dataset.epFormat;$('ftEpFormat').dispatchEvent(new Event('input',{bubbles:true}));});
  ["runExts","runRecursive","runMtime","ftTplRoot","ftPtx","ftName","ftLevel","ftDate","ftUser","ftEps","ftEpPadding","ftEpFormat","ftProjectFormat","runDirFormat","runRenameDirs","runRenameFiles","tplGlobal","fProject","fDate","fVer","fUser"].forEach(id=>$(id).addEventListener('input',updateNamingSamples));
  ['ftEpPadding','ftPtx'].forEach(id=>$(id).addEventListener('change',updateNamingSamples));
  ['runRenameDirs','runRenameFiles','runGroupMaster','runRenameSubtracks'].forEach(id=>$(id).addEventListener('change',()=>{state.items=[];state.stats={};renderPlan({items:[],message:'选项已改变，请重新生成计划'});updateNamingSamples();}));
  $('editFileFormat').onclick=()=>goto('rule');
  syncFormats();updateNamingSamples();
}

/* App version comes from the same manifest consumed by the native shell and builder. */
let currentAppVersion = "";
function showAppVersion() {
  if (!currentAppVersion) return;
  document.querySelector('.ver').textContent = 'v' + currentAppVersion;
  document.title = window.ToolI18n.translate('统一命名工具') + ' v' + currentAppVersion;
}
fetch('app-versions.json', {cache:'no-store'}).then(r => {
  if (!r.ok) throw Error('Version manifest unavailable');
  return r.json();
}).then(versions => {
  if (!/^\d+\.\d+\.\d+$/.test(versions.re)) throw Error('Invalid version');
  currentAppVersion = versions.re;showAppVersion();
}).catch(e => console.error('App version:', e));
window.addEventListener('languagechanged',showAppVersion);

window.addEventListener("languagechanged",()=>{if(namingBound)updateNamingSamples();});
