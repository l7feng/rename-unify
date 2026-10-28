(function () {
  "use strict";
  var LS_KEY = "pt-h-glass-v2-"+location.pathname;
  var DOC = document.documentElement;
  var RENAME_GLASS = /(?:^|\/)re\.html$/.test(location.pathname);

  /* 默认值 = style.css 玻璃档现值（拖过之后想回原样 → 恢复默认） */
  var DEF = {
    blur: 6,          // px
    radius: 22,        // px
    blob: 1.0,         // 倍率，1 = 原浓度
    hl: 1,             // 高光边
    shadow: 1,         // 投影
    bars: 1,           // 顶栏底栏也透
    alphaWarm: RENAME_GLASS ? 0.765 : 0.82,   // 浅色档卡片 alpha
    alphaDark: RENAME_GLASS ? 0.765 : 0.82,  // 深色档卡片 alpha
    reduced: window.matchMedia("(prefers-reduced-transparency: reduce)").matches
  };

  var st = loadLocal();
  var ui = null;       // 面板 DOM 引用（懒建）
  var saveTimer = null;
  var revision = 0, loadSequence = 0;
  var statusMessage = "";
  var bridgeQueue=Promise.resolve();

  /* ── 存取 ── */
  // 只接收已知字段；旧配置越界时限幅，不让NaN或对象进入CSS变量。
  function normalize(raw) {
    var d = Object.assign({}, DEF), limits={blur:[0,8],radius:[16,28],blob:[0,2],alphaWarm:[.55,.98],alphaDark:[.55,.98]};
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return d;
    Object.keys(limits).forEach(function(k){var n=typeof raw[k]==='number' ? raw[k] : NaN;if(Number.isFinite(n))d[k]=Math.max(limits[k][0],Math.min(limits[k][1],n));});
    ['hl','shadow','bars'].forEach(function(k){if(raw[k]===true||raw[k]===1)d[k]=1;else if(raw[k]===false||raw[k]===0)d[k]=0;});
    if(typeof raw.reduced==='boolean')d.reduced=raw.reduced;
    return d;
  }
  function loadLocal() {
    try { return normalize(JSON.parse(localStorage.getItem(LS_KEY)||'{}')); } catch(e) { return normalize(null); }
  }
  function tell(message) { statusMessage=message;syncVals(); }
  function saveLocal() {
    try { localStorage.setItem(LS_KEY,JSON.stringify(st));return true; }
    catch(e) { tell('本地记忆失败：存储不可用，请重试。');return false; }
  }
  async function saveBridge(snapshot) {
    var bridge=window.pywebview&&window.pywebview.api;
    if(!bridge||!bridge.save_glass)return false;
    var timer;
    try {
      await Promise.race([(async function(){
        var r=await bridge.save_glass(snapshot);
        if(!r||r.ok!==true)throw Error(r&&r.message||'配置未保存');
        // 旧后端可能吞掉磁盘写入异常，必须读回参数确认实际持久化。
        if(!bridge.get_glass)throw Error('配置无法读回复核');
        var stored=await bridge.get_glass(),expected=JSON.parse(snapshot);
        if(!stored||stored.ok!==true||!stored.glass||!Object.keys(expected).every(function(k){return stored.glass[k]===expected[k];}))throw Error('配置写入后复核失败');
      })(),new Promise(function(_,reject){timer=setTimeout(function(){reject(Error('配置保存超时'));},8000);})]);
      return true;
    } finally { clearTimeout(timer); }
  }
  async function remember(button,success) {
    clearTimeout(saveTimer);var localOK=saveLocal(),snapshot=JSON.stringify(st),savedRevision=revision;
    button.disabled=true;tell('正在自动保存…');
    try {
      var task=bridgeQueue.catch(function(){}).then(function(){return saveBridge(snapshot);});bridgeQueue=task;
      var bridged=await task;
      if(!bridged&&!localOK)throw Error('本地存储不可用');
      tell(savedRevision===revision ? (bridged?'配置文件已保存。':'演示态：已保存在此浏览器，未写配置文件。') : '刚才的参数已保存；当前参数又有变化，请再次记住。');
      flash(button,savedRevision===revision?success:'请记住新参数');
    } catch(e) { tell('配置保存失败：'+(e.message||String(e))+'。'+(localOK?'本地预览已记忆，请重试。':''));flash(button,'保存失败'); }
    finally { button.disabled=false; }
  }
  function loadBridge() {
    if(revision>0)return;
    var bridge=window.pywebview&&window.pywebview.api;if(!bridge||!bridge.get_glass)return;
    var startedRevision=revision,sequence=++loadSequence;
    Promise.resolve().then(function(){return bridge.get_glass();}).then(function(r){
      // 桥值只覆盖未被用户编辑的初始状态；应用必须经过当前风格判断。
      if(sequence!==loadSequence||startedRevision!==revision)return;
      if(r&&r.ok&&r.glass){st=normalize(r.glass);refresh();}
      else if(r&&r.ok===false)tell('配置加载失败，继续使用本地参数。');
    }).catch(function(){if(startedRevision===revision)tell('配置加载失败，继续使用本地参数。');});
  }

  /* ── 应用（inline 变量） ── */
  function set(k, v) { DOC.style.setProperty(k, v); }
  function rm(k) { DOC.style.removeProperty(k); }
  /* 结算台深色主题共用深色玻璃参数。 */
  var DARK_THEMES = { dark: 1, warm: 1, ocean: 1 };
  function isDark() { return !!DARK_THEMES[DOC.dataset.mode]; }

  function apply() {
    document.body.classList.toggle('reduce-material',!!st.reduced);
    document.body.classList.toggle('allow-material',!st.reduced);
    var dark = isDark();
    var a = dark ? st.alphaDark : st.alphaWarm;
    // 统一命名的低端接近全透，中点约半透明；其他工具保持原标尺。
    var opacity = RENAME_GLASS ? .03 + ((a - .55) / (.98 - .55)) * .95 : a;
    var sheen = RENAME_GLASS ? Math.min(1, opacity / .82) : 1;
    set('--material-opacity',(Math.round(opacity*10000)/100)+'%');
    set('--glass-blur',st.blur+'px');set('--material-radius',st.radius+'px');set('--radius',st.radius+'px');
    set('--material-glow-primary',st.blob*12+'%');set('--material-glow-secondary',st.blob*10+'%');
    set('--material-shine',st.hl?'rgba(255,255,255,'+((dark?.28:.86)*sheen)+')':'transparent');
    set('--material-shade',st.hl?'rgba(10,18,30,'+(.18*sheen)+')':'transparent');
    set('--material-edge',st.hl?'color-mix(in srgb,var(--fg) 16%,transparent)':'transparent');
    set('--material-shadow',st.shadow?'inset 0 1px 0 var(--material-shine),inset 0 -1px 0 var(--material-shade),0 8px 24px rgba(0,0,0,.12)':'none');
    document.body.classList.toggle('solid-bars',!st.bars);
  }
  /* ── 面板 DOM ── */
  var HTML = ""
    + "<div class='gt-head' id='gtDrag'><b>设置 · 外观</b><button type='button' class='gt-close' id='gtClose' aria-label='收起玻璃微调'>✕</button></div>"
    + "<div class='gt-body'><label class='gt-theme-label'>语言 / Language<select id='appearanceLanguage' class='appearance-select'><option value='zh-CN'>中文</option><option value='en'>English</option></select></label><label class='gt-theme-label'>主题<select id='appearanceTheme' class='appearance-select'><option value='dark'>中性灰（深）</option><option value='claude'>暖陶灰（浅）</option><option value='warm'>暖夜棕（深）</option><option value='ocean'>深海蓝（深）</option></select></label><p class='gt-note' id='gtStatus' role='status' aria-live='polite'></p>"
    + "<label class='gt-row'>玻璃不透明度<span class='gt-val' id='vAlpha'></span>"
    + "<input type='range' id='rAlpha' min='0.55' max='0.98' step='" + (RENAME_GLASS ? '0.005' : '0.01') + "'></label>"
    + "<label class='gt-row'>模糊强度<span class='gt-val' id='vBlur'></span>"
    + "<input type='range' id='rBlur' min='0' max='8' step='1'></label>"
    + "<label class='gt-row'>圆角大小<span class='gt-val' id='vRadius'></span>"
    + "<input type='range' id='rRadius' min='16' max='28' step='1'></label>"
    + "<label class='gt-row'>背景光斑<span class='gt-val' id='vBlob'></span>"
    + "<input type='range' id='rBlob' min='0' max='2' step='0.05'></label>"
    + "<div class='gt-switches'>"
    + "<label><input type='checkbox' id='cHl'> 高光边</label>"
    + "<label><input type='checkbox' id='cShadow'> 投影</label>"
    + "<label><input type='checkbox' id='cBars'> 顶栏透明</label><label><input type='checkbox' id='cReduced'> 降低透明效果</label>"
    + "</div>"
    + "<div class='gt-actions'>"
    + "<button id='gtRemember' class='gt-pri'>记住</button>"
    + "<button id='gtCopy'>复制参数</button>"
    + "<button id='gtReset'>恢复默认</button>"
    + "</div>"
    + "<div class='gt-note'>浅色/深色的玻璃参数各存一份，当前调的是<b id='gtMode'>浅色</b>；调整后自动记住。" + (RENAME_GLASS ? "0.55接近全透明；默认0.765位于中间。" : "") + "</div>"
    + "</div>";

  function build() {
    var btn = document.createElement("button");
    btn.type="button";btn.setAttribute("aria-controls","gtPanel");btn.setAttribute("aria-expanded","false");
    btn.className = "gt-btn"; btn.id = "gtBtn"; btn.title = "设置外观";
    btn.textContent = "设置";

    var panel = document.createElement("div");
    panel.className = "gt-panel"; panel.id = "gtPanel";
    panel.innerHTML = HTML;

    var anchor = document.getElementById("modeSw");
    if (anchor && anchor.parentNode) {
      anchor.parentNode.insertBefore(btn, anchor.nextSibling);
    } else {
      document.body.appendChild(btn);
    }
    document.body.appendChild(panel);

    panel.querySelector('#appearanceLanguage').value=window.ToolI18n.language;
    panel.querySelector('#appearanceLanguage').onchange=function(event){window.ToolPrefs.setLanguage(event.target.value);};
    panel.querySelector('#appearanceTheme').value=DOC.dataset.mode;
    panel.querySelector('#appearanceTheme').onchange=function(e){window.ToolPrefs.setTheme(e.target.value);};
    btn.onclick = function () { panel.classList.toggle("open");btn.setAttribute("aria-expanded",String(panel.classList.contains("open")));clampPanel(); };
    panel.querySelector("#gtClose").onclick = function () { panel.classList.remove("open");btn.setAttribute("aria-expanded","false");btn.focus(); };

    /* 四旋钮 */
    panel.querySelector("#rAlpha").oninput = function (e) {
      st[isDark() ? "alphaDark" : "alphaWarm"] = parseFloat(e.target.value);
      onTick();
    };
    panel.querySelector("#rBlur").oninput = function (e) { st.blur = parseFloat(e.target.value); onTick(); };
    panel.querySelector("#rRadius").oninput = function (e) { st.radius = parseFloat(e.target.value); onTick(); };
    panel.querySelector("#rBlob").oninput = function (e) { st.blob = parseFloat(e.target.value); onTick(); };

    /* 三开关 */
    panel.querySelector("#cHl").onchange = function (e) { st.hl = e.target.checked ? 1 : 0; onTick(); };
    panel.querySelector("#cShadow").onchange = function (e) { st.shadow = e.target.checked ? 1 : 0; onTick(); };
    panel.querySelector("#cBars").onchange = function (e) { st.bars = e.target.checked ? 1 : 0; onTick(); };

    panel.querySelector("#cReduced").onchange=function(e){st.reduced=e.target.checked;onTick();};

    /* 三按钮 */
    panel.querySelector("#gtRemember").onclick = function () {
      remember(this,"已记住 ✓");
    };
    panel.querySelector("#gtCopy").onclick = function () { copyParams(this); };
    panel.querySelector("#gtReset").onclick = function () {
      st = normalize(null);revision++;statusMessage="";refresh();remember(this,"已还原并保存");
    };

    /* 标题栏拖动 */
    drag(panel, panel.querySelector("#gtDrag"));

    ui = panel;
    syncUI();
  }

  function onTick() { revision++;statusMessage="";st=normalize(st);refresh();saveLocalDebounced(); }
  function saveLocalDebounced() {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(function(){remember(ui.querySelector("#gtRemember"),"已记住 ✓");}, 300);
  }
  function flash(el, txt) {
    var old = window.ToolI18n.sourceText(el);
    el.textContent = txt;
    setTimeout(function () { el.textContent = old; }, 1200);
  }
  function copyParams(el) {
    var txt = JSON.stringify(st, null, 2);
    function fb() {
      try {
        var ta = document.createElement("textarea");
        ta.value = txt; document.body.appendChild(ta); ta.select();
        document.execCommand("copy"); document.body.removeChild(ta);
        flash(el, "已复制 ✓");
      } catch (e) { flash(el, "复制失败"); }
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(txt).then(function () { flash(el, "已复制 ✓"); }, fb);
    } else { fb(); }
  }
  function clampPanel() {
    var panel=ui;if(!panel||!panel.classList.contains('open'))return;
    var r=panel.getBoundingClientRect();panel.style.right='auto';panel.style.bottom='auto';
    panel.style.left=Math.max(8,Math.min(window.innerWidth-r.width-8,r.left))+'px';
    panel.style.top=Math.max(8,Math.min(window.innerHeight-48,r.top))+'px';
  }
  function drag(box,handle) {
    handle.addEventListener('pointerdown',function(e){
      if(e.button!==0||e.target.closest('button'))return;
      var sx=e.clientX,sy=e.clientY,r=box.getBoundingClientRect();handle.setPointerCapture(e.pointerId);e.preventDefault();
      function move(ev){box.style.right='auto';box.style.left=Math.max(8,Math.min(window.innerWidth-r.width-8,r.left+ev.clientX-sx))+'px';box.style.top=Math.max(8,Math.min(window.innerHeight-48,r.top+ev.clientY-sy))+'px';}
      function end(){handle.removeEventListener('pointermove',move);handle.removeEventListener('pointerup',end);handle.removeEventListener('pointercancel',end);}
      handle.addEventListener('pointermove',move);handle.addEventListener('pointerup',end);handle.addEventListener('pointercancel',end);
    });
    window.addEventListener('resize',clampPanel);
  }

  /* ── 状态同步到控件 ── */
  function syncVals() {
    if (!ui) { return; }
    ui.querySelector("#gtStatus").textContent=statusMessage||(st.reduced?"降低透明效果已开启：通透和模糊暂不显示，取消勾选可预览。":"实时预览；填写框和日志保持清晰，模糊最多8px。");
    var a = isDark() ? st.alphaDark : st.alphaWarm;
    ui.querySelector("#vAlpha").textContent = Number(a).toFixed(RENAME_GLASS ? 3 : 2);
    ui.querySelector("#vBlur").textContent = st.blur + "px";
    ui.querySelector("#vRadius").textContent = st.radius + "px";
    ui.querySelector("#vBlob").textContent = Math.round(st.blob * 100) + "%";
  }
  function syncUI() {
    if (!ui) { return; }
    var dark = isDark();
    ui.querySelector("#rAlpha").value = dark ? st.alphaDark : st.alphaWarm;
    ui.querySelector("#rBlur").value = st.blur;
    ui.querySelector("#rRadius").value = st.radius;
    ui.querySelector("#rBlob").value = st.blob;
    ui.querySelector("#cHl").checked = !!st.hl;
    ui.querySelector("#cShadow").checked = !!st.shadow;
    ui.querySelector("#cBars").checked = !!st.bars;
    ui.querySelector("#cReduced").checked=!!st.reduced;
    ui.querySelector('#appearanceTheme').value=DOC.dataset.mode;
    ui.querySelector("#gtMode").textContent = dark ? "深色" : "浅色";
    syncVals();
  }

  /* ── 风格/主题变化联动 ── */
  function refresh() {
    var glass = true;
    document.body.classList.toggle("gt-on", glass);
    if (glass) { apply(); } 
    if (ui) {
      syncUI();
      if (!glass) { ui.classList.remove("open");document.getElementById("gtBtn").setAttribute("aria-expanded","false"); }
    }
  }

  /* ── 启动 ── */
  window.GlassPrefs={snapshot:function(){return st;}};
  function init() {
    build();
    refresh();
    loadBridge();
    window.addEventListener("pywebviewready",loadBridge);
    document.addEventListener("keydown",function(e){if(e.key==="Escape"&&ui.classList.contains("open"))document.getElementById("gtClose").click();});
    new MutationObserver(refresh).observe(DOC, {
      attributes: true, attributeFilter: ["data-style", "data-mode"]
    });
    if (location.hash === "#gt-open") { /* 调试/截图深链：直接弹面板 */
      if (ui) { ui.classList.add("open"); }
    }
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else { init(); }
})();
