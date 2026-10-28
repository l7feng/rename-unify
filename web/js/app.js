/* ════════════════════════════════════════════════════════════
   pt-audio-toolkit v4 · app.js（阶段 B：四页 SPA）
   桥存在 → 真功能；无桥（浏览器演示态）→ 视觉可看、动作提示去壳内跑
   ════════════════════════════════════════════════════════════ */
"use strict";

const HAS_BRIDGE = () => !!(window.pywebview && window.pywebview.api);
const api = () => (HAS_BRIDGE() ? window.pywebview.api : null);
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

/* ── 全局状态 ── */
const state = {
  modeIdx: 0,
  profile: null,        // {path, project, tracks[], mtime, fps, empty_tracks[], ...}
  logN: 0,
  libItems: [],
  hist: [],
  libFilter: "",
  emptyTracks: [],      // B2：档案里无音频块的轨道（剔除空轨候选）
  restored: new Set(),  // B2：用户「加回」的空轨（豁免剔除）
  fps: 25,              // B2：session.timecode_rate（视频时长→时间码）
};

/* ── 日志（四页共用一个流） ── */
function log(msg, cls) {
  const el = $("log");
  const d = document.createElement("div");
  if (cls) d.className = cls;
  d.textContent = new Date().toTimeString().slice(0, 8) + "  " + msg;
  el.appendChild(d);
  el.scrollTop = el.scrollHeight;
  $("logCnt").textContent = "（" + (++state.logN) + " 条）";
}
/* 壳侧进度回调挂点（pt_api.py evaluate_js → __onTaskLine） */
window.__onTaskLine = (cls, msg) => log(msg, cls || "");

/* ── 页签路由 ── */
const PAGES = ["scan", "export", "library", "clean"];
function goto(page) {
  PAGES.forEach((p) => {
    $("page-" + p).classList.toggle("on", p === page);
    $("tab-" + p).classList.toggle("on", p === page);
  });
  if (page === "library") refreshLibrary();
  if (page === "clean") renderClean();
}
function bindTabs() {
  PAGES.forEach((p) => { $("tab-" + p).onclick = () => goto(p); });
}

/* ── 风格 / 主题切换（持久化走桥） ── */

/* ── 通用：目录 / 档案选择 ── */
async function pickDir(inputId, title) {
  if (api()) {
    try { const d = await api().pick_directory(title); if (d) { $(inputId).value = d; window.ToolPrefs.touch(inputId); } return; } catch (e) {}
  }
  log("演示态：目录选择需在壳内运行（desktop_app.py）", "err");
}
async function pickProfile() {
  if (api()) {
    try { const f = await api().pick_file("选择工程档案"); if (f) await loadProfile(f); return; } catch (e) {}
  }
  log("演示态：档案选择需在壳内运行", "err");
}

/* ── 档案加载（扫描页/导出页/清理页共用） ── */
async function loadProfile(path) {
  if (!api()) { log("演示态：档案加载需在壳内运行", "err"); return; }
  const r = await api().load_profile(path);
  if (!r.ok) { log(r.message, "err"); return; }
  state.profile = r;
  state.emptyTracks = r.empty_tracks || [];   // B2：空轨候选
  state.fps = r.fps || 25;                    // B2：时间码 fps
  state.restored = new Set();                 // 换档案 → 加回记录清零
  $("expProfilePath").value = r.path;
  $("expProfileInfo").textContent =
    "工程 " + r.project + " · 轨道 " + r.track_count + " 条 · 档案 " + r.mtime + " · 来源 " + r.source_count;
  renderTracks(r.tracks);
  renderClean();
  log("✓ 档案已加载：" + r.project + "（" + r.track_count + " 轨）", "ok");
}

/* ── 扫描页 ── */
function bindScan() {
  $("btnBrowse").onclick = () => pickDir("outDir", "选择档案输出目录");
  $("btnPkgBrowse").onclick = () => pickDir("pkgDir", "选择交付包输出目录");
  $("btnScan").onclick = async () => {
    const out = $("outDir").value.trim();
    if (!out) { log("请先选择输出目录", "err"); return; }
    setBusy(true, "btnScan");
    log("开始扫描当前工程 → " + out, "info");
    if (api()) {
      try {
        const r = await api().run_scan(out, $("profName").value.trim() || "pt-profile.json");
        log(r.message, r.ok ? "info" : "err");
      } catch (e) { log("扫描失败：" + e, "err"); }
    } else {
      for (const s of ["连接 PTSL…", "读取轨道列表… 55 条", "读取总线… 8 条",
                       "计算音频时长… 132 个", "写出 pt-profile.json …"]) {
        await new Promise((r) => setTimeout(r, 350)); log(s);
      }
      log("✓ 档案已生成（演示态）", "ok");
    }
    setBusy(false, "btnScan");
  };
  $("btnStop").onclick = async () => {
    if (api()) { try { const r = await api().stop_task(); log(r.message, "err"); } catch (e) {} }
    setBusy(false, "btnScan");
  };
  $("btnDeliver").onclick = async () => {
    const pkg = $("pkgDir").value.trim();
    if (!pkg) { log("请先选择包输出目录", "err"); return; }
    setBusy(true, "btnDeliver");
    log("生成交付包 → " + pkg, "info");
    if (api()) {
      try { const r = await api().deliver(pkg); log(r.message, r.ok ? "info" : "err"); }
      catch (e) { log("交付包失败：" + e, "err"); }
    } else { log("演示态：交付包需在壳内运行", "err"); }
    setBusy(false, "btnDeliver");
  };
}
function setBusy(busy, btnId) {
  const b = $(btnId);
  if (b) b.disabled = busy;
  $("btnStop").style.display = busy ? "" : "none";
}

/* ── 导出页 ── */
function renderTracks(tracks) {
  const wrap = $("trackTbl");
  if (!tracks || !tracks.length) {
    wrap.innerHTML = '<div class="empty">（档案无轨道数据）</div>';
    return;
  }
  const noDrop = !$("mdExcludeEmpty").checked;   // 不剔除时空轨也默认勾上
  wrap.innerHTML = "<table class='grid'><thead><tr><th style='width:34px'></th><th>轨道</th><th style='width:90px'>格式覆盖</th></tr></thead><tbody>" +
    tracks.map((t, i) => {
      const isEmpty = state.emptyTracks.indexOf(t) >= 0;
      const on = !isEmpty || noDrop || state.restored.has(t);
      return "<tr" + (isEmpty ? " title='空轨（无音频块）'" : "") + "><td><input type='checkbox' class='trk' data-name=\"" + esc(t) + "\"" + (on ? " checked" : "") + "></td>" +
      "<td>" + esc(t) + (isEmpty ? " <span data-i18n-ui style='color:var(--faint)'>(空轨)</span>" : "") + "</td>" +
      "<td><select class='trkfmt' data-name=\"" + esc(t) + "\"><option value=''>默认</option>" +
      "<option value='interleaved'>立体声/多声道</option><option value='multiple-mono'>多单声道 L/R</option><option value='mono'>单声道</option></select></td></tr>";
    }).join("") + "</tbody></table>";
  updateSrcCount();
  updateExcludedBtn();
}
/* B2：被剔除的（空轨 − 已加回），与 T版 _dropped_names 同口径 */
function droppedNames() {
  if (!$("mdExcludeEmpty").checked) { return []; }
  return state.emptyTracks.filter((n) => !state.restored.has(n));
}
function updateExcludedBtn() {
  const n = droppedNames().length;
  const b = $("btnExcluded");
  b.textContent = "被剔除的 " + n + " 条 ▸";
  b.disabled = !n;
}
/* B2：通用小窗 */
function openModal(title, bodyHtml, footHtml) {
  $("modalBox").innerHTML =
    '<div class="m-head"><span>' + title + '</span><span class="m-close" id="mClose">✕</span></div>' +
    '<div class="m-body">' + bodyHtml + '</div>' +
    (footHtml ? '<div class="m-foot">' + footHtml + '</div>' : '');
  $("modalMask").style.display = "flex";
  $("mClose").onclick = closeModal;
  $("modalMask").onclick = (e) => { if (e.target.id === "modalMask") closeModal(); };
}
function closeModal() { $("modalMask").style.display = "none"; }
function showExcluded() {
  const names = droppedNames();
  if (!names.length) { return; }
  openModal("被剔除的轨道（空轨）— 可加回",
    names.map((n) =>
      '<div class="m-row"><span class="m-name">' + esc(n) + '</span>' +
      '<button class="btn ghost sm" data-restore="' + esc(n) + '">加回</button></div>').join(""),
    '<button class="btn ghost sm" id="mRestoreAll">全部加回</button><button class="btn primary sm" id="mDone">完成</button>');
  document.querySelectorAll("#modalBox [data-restore]").forEach((b) => {
    b.onclick = () => restoreTrack(b.dataset.restore);
  });
  $("mRestoreAll").onclick = () => { names.forEach(restoreTrackSilent); closeModal(); log("已全部加回（" + names.length + " 条空轨不再剔除）", "ok"); };
  $("mDone").onclick = closeModal;
}
function restoreTrackSilent(n) {
  state.restored.add(n);
  const box = document.querySelector('#trackTbl .trk[data-name="' + n.replace(/"/g, '\\"') + '"]');
  if (box) { box.checked = true; }
}
function restoreTrack(n) {
  restoreTrackSilent(n);
  updateSrcCount(); updateExcludedBtn();
  log("已加回「" + n + "」（本次不再按空轨剔除）", "ok");
  showExcluded();   // 重画小窗（少一行）
}
/* B2：帧号 → HH:MM:SS:FF（T版 core/naming.frame_to_tc 同口径） */
function frameToTc(frames, fps) {
  fps = Math.max(Math.round(fps), 1);
  const f = Math.round(frames) % fps;
  const total = Math.floor(Math.round(frames) / fps);
  const h = Math.floor(total / 3600), rem = total % 3600;
  const m = Math.floor(rem / 60), s = rem % 60;
  const p2 = (n) => String(n).padStart(2, "0");
  return p2(h) + ":" + p2(m) + ":" + p2(s) + ":" + p2(f);
}
function applyVideoDuration(v) {
  const fps = (state.profile && state.profile.fps) || 25;
  const margin = parseFloat($("expMargin").value);
  const mg = isNaN(margin) ? 0 : Math.max(margin, 0);
  $("expStart").value = "00:00:00:00";
  $("expEnd").value = frameToTc(Math.round((v.duration_sec + mg) * fps), fps);
  log("✓ 已按「" + (v.name || "视频") + "」自动填时间码：结束 " + $("expEnd").value +
      "（fps " + fps + " · 余量 " + mg + "s）", "ok");
}
function collectExportParams() {
  const tracks = [...document.querySelectorAll("#trackTbl .trk:checked")].map((x) => x.dataset.name);
  const trackFormats = {};
  document.querySelectorAll("#trackTbl .trkfmt").forEach((s) => {
    if (s.value) trackFormats[s.dataset.name] = s.value;
  });
  return {
    profile_path: state.profile ? state.profile.path : $("expProfilePath").value.trim(),
    out_dir: $("expOutDir").value.trim(),
    modes: {
      mix: $("mdMix").checked, bus: $("mdBus").checked,
      stem: $("mdStem").checked, track: $("mdTrack").checked,
    },
    stem_aux: $("mdStemAux").checked,
    exclude_empty: $("mdExcludeEmpty").checked,
    /* B2：剔除名单 = 空轨 − 已加回（与 T版 build_export_cmds 语义一致） */
    exclude_names: droppedNames(),
    tracks,
    track_formats: trackFormats,
    session: $("expSession").value.trim(),
    start: $("expStart").value.trim(),
    end: $("expEnd").value.trim(),
    sample_rate: $("expSr").value,
    bit_depth: $("expBd").value,
    fmt: $("expFmt").value,
  };
}
function updateSrcCount() {
  const all = document.querySelectorAll("#trackTbl .trk").length;
  const on = document.querySelectorAll("#trackTbl .trk:checked").length;
  $("srcCount").textContent = "已选 " + on + " / " + all + " 轨";
}
function bindExport() {
  $("expBrowseProfile").onclick = pickProfile;
  $("expBrowseOut").onclick = () => pickDir("expOutDir", "选择导出输出目录");
  $("trackTbl").addEventListener("change", updateSrcCount);
  $("btnAll").onclick = () => { document.querySelectorAll("#trackTbl .trk").forEach((x) => (x.checked = true)); updateSrcCount(); };
  $("btnNone").onclick = () => { document.querySelectorAll("#trackTbl .trk").forEach((x) => (x.checked = false)); updateSrcCount(); };
  $("btnExcluded").onclick = showExcluded;
  $("mdExcludeEmpty").onchange = () => { updateExcludedBtn(); };
  /* B2：视频时长自动检测 */
  $("btnVideoDetect").onclick = async () => {
    if (!api()) { log("演示态：视频检测需在壳内运行", "err"); return; }
    const prof = state.profile ? state.profile.path : $("expProfilePath").value.trim();
    if (!prof) { log("请先加载工程档案（扫描页或本页浏览）", "err"); return; }
    const sess = $("expSession").value.trim();
    if (!sess) { log("请先填写工程会话（.ptx）路径——视频按它所在目录树检索", "err"); return; }
    log("正在检索工程视频…（候选根：.ptx 同级 → 父级 → 祖父级）", "info");
    let r;
    try { r = await api().detect_videos(sess, prof); }
    catch (e) { log("视频检测失败：" + e, "err"); return; }
    if (!r.ok) { log(r.message, "err"); return; }
    if (!r.videos || !r.videos.length) { log("未检出视频——检查 .ptx 路径与工程目录树", "err"); return; }
    if (r.root) { log("检索根命中：" + r.root, "info"); }
    if (r.videos.length === 1) { applyVideoDuration(r.videos[0]); return; }
    openModal("检出 " + r.videos.length + " 个视频 — 选一个",
      r.videos.map((v, i) =>
        '<div class="m-row"><span class="m-name">' + esc(v.name || ("视频" + (i + 1))) + '</span>' +
        '<span class="m-sub">' + (v.duration_sec ? v.duration_sec.toFixed(1) + " s" : "") + '</span>' +
        '<button class="btn ghost sm" data-vi="' + i + '">用这个</button></div>').join(""),
      '<button class="btn primary sm" id="mDone">取消</button>');
    document.querySelectorAll("#modalBox [data-vi]").forEach((b) => {
      b.onclick = () => { applyVideoDuration(r.videos[+b.dataset.vi]); closeModal(); };
    });
    const done = $("mDone");
    if (done) { done.onclick = closeModal; }
  };
  $("btnPreview").onclick = async () => {
    if (!api()) { log("演示态：预览需在壳内运行", "err"); return; }
    const r = await api().export_preview(collectExportParams());
    if (!r.ok) { log(r.message, "err"); return; }
    log("── 导出预览（" + r.cmds.length + " 条）──", "info");
    r.cmds.forEach((c) => log("  " + c));
  };
  $("btnExport").onclick = async () => {
    if (!api()) { log("演示态：导出需在壳内运行", "err"); return; }
    setBusy(true, "btnExport");
    log("开始导出…", "info");
    try { const r = await api().run_export(collectExportParams()); log(r.message, r.ok ? "info" : "err"); }
    catch (e) { log("导出失败：" + e, "err"); }
    setBusy(false, "btnExport");
  };
}

/* ── 档案库页 ── */
async function refreshLibrary() {
  if (!api()) { $("libWrap").innerHTML = '<div class="empty">演示态：档案库需在壳内运行</div>'; return; }
  const r = await api().list_library();
  if (!r.ok) { log(r.message, "err"); return; }
  state.libItems = r.items;
  state.hist = r.history;
  $("libDir").textContent = r.profile_dir || "（未设置档案目录）";
  renderLibTable();
  const h = $("histWrap");
  h.innerHTML = r.history.length
    ? "<table class='grid'><thead><tr><th>输出文件夹</th><th style='width:150px'>修改时间</th></tr></thead><tbody>" +
      r.history.map((x) => "<tr data-path=\"" + esc(x.path) + "\" class='histrow' style='cursor:pointer'><td>" + esc(x.name) + "</td><td>" + esc(x.mtime) + "</td></tr>").join("") +
      "</tbody></table>"
    : '<div class="empty">（导出历史为空——输出根还没有工程文件夹）</div>';
  h.querySelectorAll(".histrow").forEach((tr) => {
    tr.onclick = () => { if (api()) api().open_path(tr.dataset.path); };
  });
}
function renderLibTable() {
  const kw = state.libFilter.trim().toLowerCase();
  const rows = state.libItems.filter((x) => !kw || x.file.toLowerCase().includes(kw));
  const wrap = $("libWrap");
  wrap.innerHTML = rows.length
    ? "<table class='grid'><thead><tr><th>档案文件</th><th>工程</th><th style='width:140px'>修改时间</th><th style='width:80px'>大小</th></tr></thead><tbody>" +
      rows.map((x) => "<tr data-path=\"" + esc(x.path) + "\" class='librow' style='cursor:pointer'><td>" + esc(x.file) + "</td><td>" +
        esc(x.file.replace(/-pt-profile\.json$/i, "").replace(/\.json$/i, "")) + "</td><td>" + esc(x.mtime) + "</td><td style='text-align:right'>" + x.size_kb + "KB</td></tr>").join("") +
      "</tbody></table>"
    : '<div class="empty">（无匹配档案）</div>';
  wrap.querySelectorAll(".librow").forEach((tr) => {
    tr.onclick = async () => { await loadProfile(tr.dataset.path); goto("export"); };
  });
}
function bindLibrary() {
  $("libSearch").oninput = () => { state.libFilter = $("libSearch").value; renderLibTable(); };
  $("libRefresh").onclick = refreshLibrary;
  $("libOpenDir").onclick = () => {
    if (api() && $("libDir").textContent && !$("libDir").textContent.startsWith("（")) api().open_path($("libDir").textContent);
    else log("档案目录未设置或演示态", "err");
  };
  $("libDelete").onclick = async () => {
    const sel = $("libWrap").querySelector(".librow.sel");
    if (!sel) { log("先在列表里点选一条档案", "err"); return; }
    if (api()) { const r = await api().delete_profile(sel.dataset.path); log(r.message, r.ok ? "ok" : "err"); refreshLibrary(); }
    else log("演示态：删除需在壳内运行", "err");
  };
  $("libWrap").addEventListener("click", (e) => {
    const tr = e.target.closest(".librow");
    if (!tr) return;
    $("libWrap").querySelectorAll(".librow").forEach((x) => x.classList.remove("sel"));
    tr.classList.add("sel");
  });
}

/* ── 清理页（展示已加载档案的轨道清单） ── */
function renderClean() {
  const wrap = $("cleanTbl");
  const t = state.profile && state.profile.tracks;
  if (!t || !t.length) {
    wrap.innerHTML = '<div class="empty">（尚未加载档案——在「扫描建档」或「档案库」页加载后，这里列出可清理目标的轨道）</div>';
    return;
  }
  wrap.innerHTML = "<table class='grid'><thead><tr><th style='width:44px'>#</th><th>轨道（清理目标参照）</th></tr></thead><tbody>" +
    t.map((n, i) => "<tr><td>" + (i + 1) + "</td><td>" + esc(n) + "</td></tr>").join("") + "</tbody></table>";
}

/* ── 状态条轮询 ── */
async function pollStatus() {
  if (!api()) return;
  try {
    const s = await api().ptsl_status();
    $("ptslDot").className = "dot " + (s.online ? "on" : "off");
    $("ptslText").textContent = s.online ? "PTSL 在线（" + s.host + "）" : "PTSL 离线（请先启动 Pro Tools）";
    $("warnBar").style.display = s.online ? "none" : "";
    const sk = await api().skills_status();
    const b = $("skillBadge");
    b.textContent = sk.ok ? "技能可用" : "技能未就绪";
    b.className = "badge" + (sk.ok ? "" : " bad");
    b.title = sk.message || "";
  } catch (e) {}
}

/* ── 初始化 ── */
let uiBound=false, bridgeBound=false;
async function init() {
  if(uiBound && (!HAS_BRIDGE() || bridgeBound)) return;
  uiBound=true;
  bindTabs();
  bindScan();
  bindExport();
  bindLibrary();
  $("btnClear").onclick = () => { $("log").innerHTML = ""; state.logN = 0; $("logCnt").textContent = "（0 条）"; };
  if (!HAS_BRIDGE()) {
    $("demoTip").style.display = "block";
    setTimeout(() => log("提示：浏览器演示态——扫描/导出/档案库需在壳内运行（python shell/desktop_app.py）", "info"), 200);
    window.dispatchEvent(new Event('toolready'));
    return;
  }
  bridgeBound=true;
  try {
    pollStatus();
    setInterval(pollStatus, 5000);
  } catch (e) {}
  window.dispatchEvent(new Event('toolready'));
}
window.addEventListener("pywebviewready", init);
if (HAS_BRIDGE()) { /* 壳先于事件时兜底 */ setTimeout(init, 50); } else { document.addEventListener("DOMContentLoaded", init); }
