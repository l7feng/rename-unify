/* ════════════════════════════════════════════════════════════
   pt-audio-toolkit v4 · jy.js（阶段 C：剪映工程工具包三页签）
   桥存在 → 真功能；无桥（浏览器演示态）→ 视觉可看、动作提示去壳内跑
   壳挂点：__onJyLine → __appendLog；__onShellEvent ← busy/done/phase1
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
  phase1Ok: false,     // 解析输入完成才允许开始导出
  demucsOk: false,
  ofxBusy: false, ofxRunning: false, ofxItems: [], ofxRoot: "",
};

/* ── 日志（三页共用一个流） ── */
function log(msg, cls) {
  const el = $("log");
  const d = document.createElement("div");
  if (cls) d.className = cls;
  d.textContent = new Date().toTimeString().slice(0, 8) + "  " + msg;
  el.appendChild(d);
  el.scrollTop = el.scrollHeight;
  $("logCnt").textContent = "（" + (++state.logN) + " 条）";
  if (cls === "err" || cls === "ok") {
    $("taskStatus").textContent = msg;
    $("taskStatus").classList.toggle("error", cls === "err");
    if (cls === "err") $("runDetails").open = true;
  }
}
/* 壳侧进度回调挂点（jy_desktop evaluate_js → __onJyLine → __appendLog） */
window.__appendLog = (cls, msg) => log(msg, cls || "");
window.__onJyLine = window.__appendLog;   // 浏览器直开兜底（壳会覆盖，行为等价）

/* ── 壳事件（jy_api._emit_event） ── */
function onShellEvent(name, value) {
  if (name === "busy") {
    state.busy = !!value;
    syncWorkflow();
    $("envBadge").textContent = value ? "⏳ 任务运行中…" : ($("envBadge").dataset.ok || "环境未检");
  } else if (name === "done") {
    log(value && value.ok ? "—— 任务结束 ——" : "—— 任务异常结束 ——", value && value.ok ? "ok" : "err");
  } else if (name === "phase1") {
    onPhase1(value || {});
  }
}
window.__onShellEvent = onShellEvent;
window.__onJyEvent = onShellEvent;

/* ── 页签路由 ── */
const PAGES = ["import", "export", "sep", "ofx"];
function goto(page) {
  if (page === "ofx") refreshOfx();
  if (page === "sep" && !state.demucsOk) demucsCheck(true);
  $("ptStatusWrap").hidden = page !== "import";
  PAGES.forEach((p) => {
    $("page-" + p).classList.toggle("on", p === page);
    $("tab-" + p).classList.toggle("on", p === page);
  });
}
function bindTabs() {
  PAGES.forEach((p) => { $("tab-" + p).onclick = () => goto(p); });
}

/* ── 风格 / 主题切换（家族级偏好，持久化与 pt-tools 共用一份配置） ── */

/* ── 浏览（壳原生对话框；演示态提示） ── */
async function pickDir(inputId, title) {
  if (!api()) { log("演示态：目录选择需在壳内运行", "info"); return; }
  try {
    const d = await api().pick_directory(title || "选择目录");
    if (d) { $(inputId).value = d; window.ToolPrefs.touch(inputId); if(inputId.startsWith("exp"))invalidateExport(); }
  } catch (e) { log("选择失败：" + e, "err"); }
}
async function pickFile(inputId, title, kinds) {
  if (!api()) { log("演示态：文件选择需在壳内运行", "info"); return; }
  try {
    const f = await api().pick_file(title || "选择文件", kinds || "json");
    if (f) { $(inputId).value = f; window.ToolPrefs.touch(inputId); }
  } catch (e) { log("选择失败：" + e, "err"); }
}

/* ══════════ 页 1：导入 ══════════ */
async function impPreview() {
  const jp = $("impJson").value.trim(), draft = $("impDraft").value.trim();
  if (!jp || !draft) { log("请先填 pt-clips.json 与目标草稿目录", "err"); return; }
  if (!api()) { log("演示态：预演需在壳内运行", "info"); return; }
  log("预演解析中…");
  try {
    const r = await api().preview_import(jp, draft);
    if (!r.ok) { log(r.message || "解析失败", "err"); return; }
    $("impInfo").textContent = "✓ " + (r.message || ("共 " + r.rows + " 行"));
    $("impTracks").innerHTML = (r.tracks || []).map((t) =>
      "<div class='trow'>" + esc(t) + "</div>").join("") ||
      "<div class='empty'>（交付包内没有轨道）</div>";
    log("✓ 预演通过：" + (r.tracks || []).length + " 轨", "ok");
  } catch (e) { log("预演异常：" + e, "err"); }
}
async function impRun() {
  await window.ToolPrefs.flush();
  const jp = $("impJson").value.trim(), draft = $("impDraft").value.trim();
  if (!jp || !draft) { log("请先填 pt-clips.json 与目标草稿目录", "err"); return; }
  if (!api()) { log("演示态：导入需在壳内运行（python shell/jy_desktop.py）", "info"); return; }
  if (!confirm("将向草稿写入多轨音频：\n" + draft + "\n\n请确认剪映已关闭、草稿已备份。继续？")) return;
  try {
    const r = await api().run_import(jp, draft, $("impOnly").value.trim(), $("impKeepAux").checked);
    log(r.ok ? "✓ " + r.message : "✗ " + r.message, r.ok ? "ok" : "err");
  } catch (e) { log("导入异常：" + e, "err"); }
}
function renderImpInfo() {
  $("impTracks").innerHTML = "<div class='empty'>（点「预演」列出交付包内的轨道）</div>";
}

/* ══════════ 页 2：导出 ══════════ */
function fillExportCfg(cfg) {
  if (!cfg) return;
  $("expInput").value = cfg.input_dir || "";
  $("expOut").value = cfg.output_dir || "";
  const em = cfg.modes || {};
  $("mdTracks").checked = !!em.tracks;
  $("mdClips").checked = !!em.clips;
  $("expSpec").innerHTML = (cfg.spec_options || []).map((s) =>
    "<option value='" + esc(s.key) + "'>" + esc(s.label) + "</option>").join("");
  $("expSpec").value = cfg.track_spec || "keep";
  $("expTrackTpl").value = cfg.track_name_template || "{项目名}_{轨道名}";
  $("expAaf").checked = !!cfg.export_aaf;
  $("expAafMode").value = cfg.aaf_media_mode || "media";
  $("expSplit").checked = !!cfg.split_by_video;
  $("expSplitTpl").value = cfg.split_folder_template || "{视频名}";
  $("expSubs").checked = !!cfg.export_subtitles;
  $("expFmt").value = cfg.audio_format || "wav";
  $("expBitrate").value = String(cfg.bitrate_kbps || 320);
  $("expConflict").value = cfg.conflict || "rename";
  $("expClipType").value = cfg.clip_type_override || "";
  $("expDedupe").checked = cfg.dedupe !== false;
  $("expVideoTracks").checked = cfg.extract_video_tracks !== false;
  $("expSkipExisting").checked = !!cfg.skip_existing;
  $("expRemarks").value = cfg.remarks || "";
  $("sepIn").value = cfg.sep_input || "";
  $("sepOut").value = cfg.sep_output || "";
  if (cfg.sep_stems) {
    const r = document.querySelector("input[name=sepStems][value='" + cfg.sep_stems + "']");
    if (r) r.checked = true;
  }
}
async function loadExportCfg() {
  if (!api()) return;
  try {
    const r = await api().get_export_config();
    if (r.ok) fillExportCfg(r.cfg);
  } catch (e) {}
}
function exportParams() {
  return {
    input_dir: $("expInput").value.trim(),
    output_dir: $("expOut").value.trim(),
    extra_paths: $("expPaths").value.split("\n").map((s) => s.trim()).filter(Boolean),
    modes: { tracks: $("mdTracks").checked, clips: $("mdClips").checked },
    track_spec: $("expSpec").value || "",
    track_name_template: $("expTrackTpl").value.trim(),
    export_aaf: $("mdTracks").checked && $("expAaf").checked,
    aaf_media_mode: $("expAafMode").value,
    split_by_video: $("mdTracks").checked && $("expSplit").checked,
    split_folder_template: $("expSplitTpl").value.trim() || "{视频名}",
    export_subtitles: $("expSubs").checked,
    audio_format: $("expFmt").value,
    bitrate_kbps: parseInt($("expBitrate").value, 10) || 320,
    conflict: $("expConflict").value,
    clip_type_override: $("expClipType").value.trim(),
    dedupe: $("expDedupe").checked,
    extract_video_tracks: $("expVideoTracks").checked,
    skip_existing: $("expSkipExisting").checked,
    remarks: $("expRemarks").value.trim(),
  };
}
async function envCheck() {
  if (!api()) { log("演示态：环境自检需在壳内运行", "info"); return; }
  log("环境自检中…");
  try {
    const r = await api().env_check();
    (r.items || []).forEach((i) =>
      log((i.ok ? "✓ " : "✗ ") + i.name + " — " + i.message, i.ok ? "ok" : "err"));
    const allOk = !!r.ok;
    $("envBadge").dataset.ok = allOk ? "环境 OK" : "环境缺项";
    $("envBadge").textContent = allOk ? "环境 OK" : "环境缺项";
    $("warnBar").style.display = allOk ? "none" : "";
    log(allOk ? "✓ 环境自检全部通过" : "⚠ 有缺项——导出前请先补齐", allOk ? "ok" : "err");
  } catch (e) { log("自检异常：" + e, "err"); }
}
async function phase1() {
  if (!api()) { log("演示态：解析输入需在壳内运行", "info"); return; }
  if (state.busy) { log("已有任务在进行中", "err"); return; }
  const p = exportParams();
  if (!p.modes.tracks && !p.modes.clips) { log("请至少勾选一种导出模式（整轨 / 片段）", "err"); return; }
  if (!p.output_dir) { log("请先填写「输出目录」", "err"); return; }
  state.phase1Ok = false;
  syncWorkflow();
  log("① 解析输入中（大目录可能较慢）…");
  try {
    const r = await api().export_phase1(p);
    if (!r.ok) { log("✗ " + r.message, "err"); return; }
    log("✓ " + r.message, "ok");
    /* 真正的解析结果走 phase1 事件（后台线程完成时推送） */
  } catch (e) { log("解析异常：" + e, "err"); }
}
function onPhase1(p) {
  state.phase1Ok = true;
  state.hasPending = !!p.has_pending;
  syncWorkflow();
  $("pendingBox").style.display = "none";
  if (p.file_mode) {
    log("识别为媒体文件模式（" + p.media_count + " 个文件），将按整轨提取", "info");
  }
  if (!p.has_pending) {
    $("exportHint").textContent = "解析完成，可以开始导出。";
    log("解析完成：" + p.draft_count + " 个草稿。可直接点「② 开始导出」", "ok");
    return;
  }
  const suggest = p.suggest || "";
  $("pendingHint").textContent =
    "分包需要每个视频窗的项目名（共 " + p.pending.length + " 项缺）" +
    (suggest ? "；建议统一填「" + suggest + "」：" : "：");
  $("pendingList").innerHTML = p.pending.map((it) =>
    "<div class='field'><label>" + esc(it.raw) + "</label>" +
    "<input type='text' data-key='" + esc(it.key) + "' value='" + esc(it.suggest || suggest) + "'" +
    " placeholder='项目名（" + esc(it.reason || "待补") + "）'></div>").join("");
  $("pendingBox").style.display = "";
  log("⚠ 有 " + p.pending.length + " 个视频项目名待补录——填完后点「✓ 填好了」", "err");
}
async function exportRun(answers) {
  await window.ToolPrefs.flush();
  if (!api()) { log("演示态：导出需在壳内运行", "info"); return; }
  if (state.busy) { log("已有任务在进行中", "err"); return; }
  if (!state.phase1Ok) { log("请先点「① 解析输入」", "err"); return; }
  try {
    const r = await api().run_export(answers || null);
    if (!r.ok) {
      log("✗ " + r.message, "err");
      if (r.need_answers) $("pendingBox").style.display = "";
      return;
    }
    log("✓ " + r.message, "ok");
    $("pendingBox").style.display = "none";
  } catch (e) { log("导出异常：" + e, "err"); }
}
function pendingSubmit() {
  const answers = {};
  document.querySelectorAll("#pendingList input[data-key]").forEach((inp) => {
    answers[inp.dataset.key] = inp.value.trim();
  });
  exportRun(answers);
}

/* ══════════ 页 3：人声分离 ══════════ */
async function demucsCheck(silent) {
  if (!api()) {
    $("sepEnv").textContent = "模型环境：演示态（需壳内检测）";
    return;
  }
  try {
    const r = await api().check_demucs();
    state.demucsOk = !!r.ok;
    $("sepEnv").innerHTML = r.ok
      ? "模型环境：<span style='color:var(--green,#4a4)'>✓ Demucs 就绪</span>" +
        (r.ver ? "（" + esc(r.ver) + "）" : "") + "　via " + esc(r.via || "")
      : "模型环境：<span style='color:var(--red)'>✗ " + esc(r.message || "未安装") + "</span>";
    if (!silent) log(r.ok ? "✓ Demucs 就绪" : "✗ " + (r.message || "Demucs 未安装"), r.ok ? "ok" : "err");
  } catch (e) { if (!silent) log("检测异常：" + e, "err"); }
}
async function sepRun() {
  await window.ToolPrefs.flush();
  if (!api()) { log("演示态：分离需在壳内运行", "info"); return; }
  if (!state.demucsOk) { log("Demucs 未就绪——请先「重新检测」或 pip install demucs", "err"); return; }
  const stems = (document.querySelector("input[name=sepStems]:checked") || {}).value || "vocals";
  try {
    const r = await api().run_separation($("sepIn").value.trim(), $("sepOut").value.trim(), stems);
    log(r.ok ? "✓ " + r.message : "✗ " + r.message, r.ok ? "ok" : "err");
  } catch (e) { log("分离异常：" + e, "err"); }
}

/* ── 状态轮询（PTSL） ── */
async function pollStatus() {
  if (!api() || !$("page-import").classList.contains("on") || state.busy) return;
  try {
    const r = await api().pt_status();
    $("ptDot").classList.toggle("off", !r.online);
    $("ptDot").classList.toggle("on", !!r.online);
    $("ptText").textContent = r.online ? "Pro Tools 在线（PTSL）" : "Pro Tools 未连接";
  } catch (e) {}
}


/* Conditional options and parse invalidation: never export an old parameter snapshot. */
function syncWorkflow() {
  const busy = state.busy || state.ofxBusy;
  document.querySelectorAll('#page-export input,#page-export select,#page-export textarea').forEach(el => el.disabled=busy);
  const tracks=$('mdTracks').checked, clips=$('mdClips').checked;
  const visible={tracks,clips,aaf:tracks&&$('expAaf').checked,split:tracks&&$('expSplit').checked};
  document.querySelectorAll('[data-export-feature]').forEach(el => el.hidden=!visible[el.dataset.exportFeature]);
  $('expBitrate').disabled=busy || $('expFmt').value!=='mp3';
  $('btnExportRun').disabled=busy || !state.phase1Ok || !!state.hasPending;
  ['btnPhase1','btnImpPreview','btnImpRun','btnPendingOk','btnSepRun'].forEach(id => $(id).disabled=busy);
  $('btnOfxInstall').disabled=busy || state.ofxRunning || !HAS_BRIDGE();
  $('btnOfxRefresh').disabled=state.ofxBusy;
  document.querySelectorAll('[data-ofx-delete]').forEach(el => el.disabled=el.dataset.ofxInvalid==="true"||state.ofxBusy||state.ofxRunning||state.busy);
}
function invalidateExport() {
  state.phase1Ok=false;state.hasPending=false;
  $('pendingBox').style.display='none';
  $('exportHint').textContent='导出条件已变化，请重新解析输入。';
  syncWorkflow();
}
function ofxSize(n) { return n>=1048576?(n/1048576).toFixed(1)+' MiB':(n/1024).toFixed(1)+' KiB'; }
function renderOfx() {
  const list=$('ofxList');list.replaceChildren();$('ofxCount').textContent=state.ofxItems.length+' 个';
  $('ofxRoot').textContent=state.ofxRoot;
  $('ofxProcessState').textContent=state.ofxRunning?'剪映正在运行，请退出后再安装或删除。':'剪映已退出，可以安装或删除。';
  if(!state.ofxItems.length) { const empty=document.createElement('div');empty.className='empty';empty.textContent='暂无插件。选择上方的插件文件夹，安装第一款插件。';list.append(empty); }
  state.ofxItems.forEach(item=>{
    const row=document.createElement('div');row.className='jy-plugin-row';
    const copy=document.createElement('div');copy.className='jy-plugin-copy';
    const title=document.createElement('strong');title.textContent=item.label;
    const name=document.createElement('code');name.textContent=item.name;
    const meta=document.createElement('div');meta.className='jy-plugin-meta';meta.textContent=item.error||`${item.files} 个文件 · ${ofxSize(item.bytes)} · 缓存副本`;
    copy.append(title,name,meta);
    const actions=document.createElement('div');actions.className='jy-plugin-actions';
    const open=document.createElement('button');open.type='button';open.className='btn ghost sm';open.textContent='打开位置';open.onclick=()=>api()?.open_path(item.path);
    const remove=document.createElement('button');remove.type='button';remove.className='btn danger sm';remove.textContent='删除';remove.dataset.ofxDelete='';
    remove.dataset.ofxInvalid=String(!item.token);
    remove.disabled=!item.token || state.ofxRunning || state.ofxBusy || state.busy;
    remove.onclick=()=>{
      state.deleteCandidate=item;
      $('ofxDeleteName').textContent=item.label+'（'+item.name+'）';
      $('ofxDeletePath').textContent=item.path;
      $('ofxDeleteSize').textContent=`${item.files} 个文件，共 ${ofxSize(item.bytes)}。`;
      $('ofxDeleteDialog').showModal();
    };
    if(!item.token) remove.title='路径存在异常，不能在这里删除。';
    actions.append(open,remove);row.append(copy,actions);list.append(row);
  });
  syncWorkflow();
}
async function refreshOfx() {
  if(!api()) { $('ofxList').textContent='浏览器预览不读取插件缓存，请使用 EXE。';$('ofxProcessState').textContent='请使用 EXE 管理插件。';return; }
  try {
    const r=await api().ofx_list();
    if(!r.ok) { log(r.message||'无法读取插件缓存','err');return; }
    state.ofxItems=r.plugins||[];state.ofxRunning=!!r.running;state.ofxRoot=r.root;renderOfx();
  } catch(e) { log('插件列表读取失败：'+e,'err'); }
}
async function installOfx() {
  const source=$('ofxSource').value.trim();if(!source){log('请先选择插件文件夹或.ofx文件。','err');return;}
  if(!api()||state.ofxBusy)return;
  state.ofxBusy=true;syncWorkflow();$('taskStatus').textContent='正在检查并安装插件…';
  try { const r=await api().ofx_install(source);log(r.message,r.ok?'ok':'err'); }
  catch(e){log('插件安装失败：'+e,'err');}
  finally{state.ofxBusy=false;await refreshOfx();syncWorkflow();}
}
async function confirmDeleteOfx() {
  const item=state.deleteCandidate;$('ofxDeleteDialog').close();state.deleteCandidate=null;
  if(!item||!api()||state.ofxBusy)return;
  state.ofxBusy=true;syncWorkflow();$('taskStatus').textContent='正在移入回收站…';
  try{const r=await api().ofx_delete(item.name,item.token);log(r.message,r.ok?'ok':'err');}
  catch(e){log('插件删除失败：'+e,'err');}
  finally{state.ofxBusy=false;await refreshOfx();syncWorkflow();}
}
function bindWorkflow() {
  document.querySelectorAll('#page-export input,#page-export select,#page-export textarea').forEach(el=>{
    if(!el.closest('#pendingBox')){el.addEventListener('input',invalidateExport);el.addEventListener('change',invalidateExport);}
  });
  $('ofxBrowseBundle').onclick=()=>pickDir('ofxSource','选择完整的.ofx.bundle文件夹');
  $('ofxBrowseFile').onclick=()=>pickFile('ofxSource','选择64位OFX文件','ofx');
  $('btnOfxRefresh').onclick=refreshOfx;$('btnOfxInstall').onclick=installOfx;
  $('btnOfxOpenRoot').onclick=()=>state.ofxRoot&&api()?.open_path(state.ofxRoot);
  $('ofxDeleteCancel').onclick=()=>{$('ofxDeleteDialog').close();state.deleteCandidate=null;};
  $('ofxDeleteConfirm').onclick=confirmDeleteOfx;
  window.addEventListener('parametersrestored',()=>{state.phase1Ok=false;syncWorkflow();});
  syncWorkflow();
}

/* ── 初始化 ── */
let inited = false;
async function init() {
  if (inited && (!HAS_BRIDGE() || state.bridgeLoaded)) return;
  inited = true;
  bindTabs();
  bindWorkflow();
  /* 按钮 */
  $("btnImpPreview").onclick = impPreview;
  $("btnImpRun").onclick = impRun;
  $("impBrowseJson").onclick = () => pickFile("impJson", "选择 pt-clips.json", "json");
  $("impBrowseDraft").onclick = () => pickDir("impDraft", "选择目标草稿目录");
  $("btnEnvCheck").onclick = envCheck;
  $("btnPhase1").onclick = phase1;
  $("btnExportRun").onclick = () => exportRun(null);
  $("btnPendingOk").onclick = pendingSubmit;
  $("expBrowseInput").onclick = () => pickDir("expInput", "选择剪映草稿根目录");
  $("expBrowseOut").onclick = () => pickDir("expOut", "选择输出目录");
  $("btnOpenOut").onclick = async () => {
    const d = $("expOut").value.trim();
    if (!d) { log("先填输出目录", "err"); return; }
    if (api()) { try { await api().open_path(d); } catch (e) {} }
    else log("演示态：打开目录需在壳内运行", "info");
  };
  $("btnSepRun").onclick = sepRun;
  $("btnSepRecheck").onclick = () => demucsCheck(false);
  $("btnSepOpen").onclick = async () => {
    const d = $("sepOut").value.trim();
    if (!d) { log("先填分离输出目录", "err"); return; }
    if (api()) { try { await api().open_path(d); } catch (e) {} }
  };
  $("sepBrowseIn").onclick = () => pickFile("sepIn", "选择音频文件", "audio");
  $("sepBrowseOut").onclick = () => pickDir("sepOut", "选择输出目录");
  $("btnClear").onclick = () => { $("log").innerHTML = ""; state.logN = 0; $("logCnt").textContent = "（0 条）"; };

  if (HAS_BRIDGE()) {
    state.bridgeLoaded=true;
    
    await loadExportCfg();
    // Model detection is deferred until the separation page is opened.
    pollStatus();
    setInterval(pollStatus, 10000);
    log("✓ 工具已就绪", "ok");
  } else {
    $("demoTip").style.display = "";
    $("ptText").textContent = "PTSL —（演示态不探测）";
    setTimeout(() => log("提示：浏览器演示态——导入/导出/分离需在壳内运行（python shell/jy_desktop.py）", "info"), 200);
  }
  window.dispatchEvent(new Event('toolready'));
}
window.addEventListener("pywebviewready", init);
if (HAS_BRIDGE()) { setTimeout(init, 50); }   // 壳先于事件时兜底
else { document.addEventListener("DOMContentLoaded", init); }
