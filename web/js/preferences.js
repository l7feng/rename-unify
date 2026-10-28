/* H v4.2.0: 结算台主题、控件参数与本机路径自动记忆。 */
(function(){
  'use strict';
  const tool=location.pathname.endsWith('re.html')?'re':location.pathname.endsWith('jy.html')?'jy':'pt';
  const key='pt-h-v2-'+tool;
  const themes=[['dark','中性灰（深）'],['claude','暖陶灰（浅）'],['warm','暖夜棕（深）'],['ocean','深海蓝（深）']];
  const skip=new Set(['tplNewName','tplNewBody','manEp','manTarget','manInfo','libSearch']);
  let controls=[],dirty=new Set(),saved={},timer,revision=0,bridgeLoaded=false,restoring=false,queue=Promise.resolve();
  try{saved=JSON.parse(localStorage.getItem(key)||'{}')||{};}catch(e){}
  const api=()=>window.pywebview&&window.pywebview.api;
  function status(text,error=false){const el=document.getElementById('saveStatus');if(el){el.textContent=text;el.classList.toggle('error',error);}}
  function snapshot(){const fields={};controls.forEach(el=>{fields[el.id]=['checkbox','radio'].includes(el.type)?el.checked:el.value;});return {fields,page:document.querySelector('.page.on')?.id.replace('page-',''),theme:document.documentElement.dataset.mode,language:window.ToolI18n.language,moreOpen:document.getElementById('moreTools')?.open||false};}
  function local(){try{localStorage.setItem(key,JSON.stringify(saved));return true;}catch(e){status('本地记忆失败，请重试',true);return false;}}
  function persist(){saved=snapshot();const localOK=local(),raw=JSON.stringify(saved);const version=++revision;
    const bridge=api();if(!bridge?.save_form_state){status(localOK?'已记住（浏览器预览）':'记忆失败',!localOK);return Promise.resolve();}
    status('正在记住…');queue=queue.catch(()=>{}).then(async()=>{let timeout;const r=await Promise.race([bridge.save_form_state(raw),new Promise((_,reject)=>{timeout=setTimeout(()=>reject(Error('保存超时')),8000);})]).finally(()=>clearTimeout(timeout));if(!r?.ok)throw Error(r?.message||'保存失败');if(version===revision)status('已自动记住');}).catch(e=>status('记忆失败：'+e.message,true));return queue;}
  function schedule(el){if(restoring)return;if(el?.id)dirty.add(el.id);clearTimeout(timer);timer=setTimeout(persist,250);}
  function setTheme(value,save=true){const theme=themes.some(t=>t[0]===value)?value:'dark';const doc=document.documentElement;doc.dataset.style='glass';doc.dataset.mode=theme;const label=document.getElementById('modeLabel');if(label)label.textContent=themes.find(t=>t[0]===theme)[1];const select=document.getElementById('appearanceTheme');if(select)select.value=theme;if(save){dirty.add('@theme');schedule();}}
  function setLanguage(value,save=true){window.ToolI18n.setLanguage(value);if(api()?.set_ui_language)api().set_ui_language(window.ToolI18n.language).catch(e=>console.warn('Window language:',e));if(save){dirty.add('@language');schedule();}}
  function restore(data){if(!data||typeof data!=='object')return;restoring=true;
    controls.forEach(el=>{if(dirty.has(el.id)||!Object.prototype.hasOwnProperty.call(data.fields||{},el.id))return;const value=data.fields[el.id];if(['checkbox','radio'].includes(el.type)){if(typeof value==='boolean')el.checked=value;}else if(typeof value==='string'&&(!el.matches('select')||Array.from(el.options).some(o=>o.value===value)))el.value=value;});
    if(!dirty.has('@language'))setLanguage(data.language||'zh-CN',false);
    if(!dirty.has('@theme'))setTheme(data.theme||'dark',false);
    if(!dirty.has('@page')&&data.page&&document.getElementById('tab-'+data.page))document.getElementById('tab-'+data.page).click();
    const more=document.getElementById('moreTools');if(more&&typeof data.moreOpen==='boolean')more.open=data.moreOpen;
    restoring=false;window.dispatchEvent(new Event('parametersrestored'));
  }
  async function loadBridge(){if(bridgeLoaded||!api()?.get_form_state)return;bridgeLoaded=true;
    try{const r=await api().get_form_state();if(!r?.ok)throw Error(r?.message||'读取失败');if(Object.keys(r.state||{}).length)saved=r.state;restore(saved);status('参数与路径已恢复');}
    catch(e){status('记忆读取失败：'+e.message,true);}
  }
  function ready(){restore(saved);loadBridge();}
  function init(){
    const badge=document.createElement('span');badge.id='saveStatus';badge.className='save-status';badge.setAttribute('role','status');document.querySelector('.hero').appendChild(badge);
    // Only original form controls, excluding temporary dialogs, table edits, and password fields.
    document.querySelectorAll('.page input[type=radio][name]').forEach(el=>{if(!el.id)el.id='memory-'+el.name+'-'+el.value;});
    controls=Array.from(document.querySelectorAll('.page input[id],.page select[id],.page textarea[id]')).filter(el=>!skip.has(el.id)&&!el.closest('.tbl-wrap,#manualBox,#pendingBox')&&!['password','file','hidden','button'].includes(el.type));
    controls.forEach(el=>{el.addEventListener('input',()=>schedule(el));el.addEventListener('change',()=>schedule(el));});
    document.getElementById('modeSw').onclick=()=>{const i=themes.findIndex(t=>t[0]===document.documentElement.dataset.mode);setTheme(themes[(i+1)%themes.length][0]);};
    document.addEventListener('click',e=>{if(e.target.closest('[id^="tab-"]')&&!restoring){dirty.add('@page');schedule();}});

    document.addEventListener('keydown',e=>{if(e.key==='Escape'){const more=document.getElementById('moreTools');if(more)more.open=false;}});
    document.addEventListener('click',e=>{const more=document.getElementById('moreTools');if(more?.open&&!e.target.closest('.more-tools'))more.open=false;});
    restore(saved);status(api()?'正在恢复参数…':'浏览器预览');
  }
  window.ToolPrefs={snapshot,themes,setTheme,setLanguage,applyPrefs:()=>{},flush:()=>{clearTimeout(timer);return persist();},touch:id=>{dirty.add(id);schedule();}};
  window.addEventListener('toolready',ready);

  window.addEventListener('pagehide',()=>{saved=snapshot();local();});
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
