/* Applies the downloaded Apple design references to this desktop WebView. */
(function(){'use strict';
function init(){
 const panel=document.getElementById('gtPanel');if(!panel)return;
 const body=panel.querySelector('.gt-body'),head=panel.querySelector('.gt-head b');head.id='reSettingsTitle';panel.setAttribute('role','dialog');panel.setAttribute('aria-labelledby',head.id);
 const backdrop=document.createElement('div');backdrop.className='re-settings-backdrop';backdrop.hidden=true;document.body.appendChild(backdrop);
 function group(title,elements){const section=document.createElement('section');section.className='re-settings-group';const h=document.createElement('h3');h.textContent=title;section.appendChild(h);elements.forEach(el=>section.appendChild(el));return section;}
 const basics=group('常规设置',[document.getElementById('appearanceLanguage').closest('label'),document.getElementById('appearanceTheme').closest('label')]);
 const material=group('材质效果',['rAlpha','rBlur','rRadius'].map(id=>document.getElementById(id).closest('label')));
 const advanced=document.createElement('details');advanced.className='re-settings-advanced';const summary=document.createElement('summary');summary.textContent='高级调节';advanced.appendChild(summary);['rBlob'].forEach(id=>advanced.appendChild(document.getElementById(id).closest('label')));advanced.appendChild(panel.querySelector('.gt-switches'));
 body.prepend(advanced);body.prepend(material);body.prepend(basics);body.appendChild(document.getElementById('gtStatus'));
 // Keep a direct numeric editor beside each slider, using the existing input handler and storage.
 ['rAlpha','rBlur','rRadius','rBlob'].forEach(id=>{
  const range=document.getElementById(id),editor=document.createElement('span'),number=document.createElement('input'),unit=document.createElement('span');
  editor.className='re-value-editor';number.className='re-number';number.type='number';number.id=id+'Number';number.min=range.min;number.max=range.max;number.step=range.step;number.value=range.value;
  number.setAttribute('aria-labelledby',id+'Label');const label=range.closest('label'),labelText=document.createElement('span');labelText.id=id+'Label';const text=[...label.childNodes].find(n=>n.nodeType===Node.TEXT_NODE);if(text){labelText.textContent=text.textContent;text.replaceWith(labelText);}
  unit.textContent=id==='rBlur'||id==='rRadius'?'px':id==='rBlob'?'×':'';editor.append(number,unit);label.insertBefore(editor,range);
  range.addEventListener('input',()=>{number.value=range.value;});
  number.addEventListener('input',()=>{if(number.value!==''&&number.validity.valid){range.value=number.value;range.dispatchEvent(new Event('input',{bubbles:true}));}});
  number.addEventListener('change',()=>{if(number.value===''||!number.validity.valid)number.value=range.value;});
  new MutationObserver(()=>{if(document.activeElement!==number)number.value=range.value;}).observe(label.querySelector('.gt-val'),{childList:true,characterData:true,subtree:true});
 });

 const note=document.createElement('p');note.className='gt-note';body.insertBefore(note,document.getElementById('gtStatus'));note.textContent='导航与工具栏可调节玻璃效果，输入区和设置内容保持清晰。';
 function center(){if(!panel.classList.contains('open'))return;const rect=panel.getBoundingClientRect();panel.style.left=Math.max(16,(innerWidth-rect.width)/2)+'px';panel.style.top=Math.max(16,(innerHeight-Math.min(rect.height,innerHeight-32))/2)+'px';panel.style.right='auto';}
 function focusable(){return [...panel.querySelectorAll('button,input,select,textarea,summary,[tabindex="0"]')].filter(el=>!el.disabled&&el.getClientRects().length);}
 let wasOpen=false;
 function sync(){const open=panel.classList.contains('open');backdrop.hidden=!open;panel.setAttribute('aria-modal',String(open));if(open&&!wasOpen){center();focusable()[0]?.focus();}wasOpen=open;}
 new MutationObserver(sync).observe(panel,{attributes:true,attributeFilter:['class']});
 backdrop.addEventListener('click',()=>document.getElementById('gtClose').click());
 panel.addEventListener('keydown',event=>{if(event.key==='Escape'){event.preventDefault();document.getElementById('gtClose').click();}else if(event.key==='Tab'){const all=focusable(),first=all[0],last=all[all.length-1];if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus();}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus();}}});
 window.addEventListener('resize',center);advanced.addEventListener('toggle',center);
 const nav=document.querySelector('nav.naming-nav');function selection(){nav.querySelectorAll('button').forEach(button=>{if(button.classList.contains('on'))button.setAttribute('aria-current','page');else button.removeAttribute('aria-current');});}new MutationObserver(selection).observe(nav,{subtree:true,attributes:true,attributeFilter:['class']});selection();
 window.ToolI18n?.refresh();
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
