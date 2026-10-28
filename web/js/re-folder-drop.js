/* One-folder read-only import for the project output field. */
(function(){'use strict';
 let nativeReady=false,sequence=0,message=null,lastDrop=null,lastOutput=null;
 const q=id=>document.getElementById(id),tr=(zh,en)=>window.ToolI18n?.language==='en'?en:zh;
 function show(zh,en,error=false){message={zh,en,error};const el=q('ftDropStatus');el.textContent=tr(zh,en);el.classList.toggle('error',error);}
 function outputFor(result){return result.matched&&!q('ftDropParent').checked?result.project_root:result.output_root;}
 async function receive(paths){
  const ticket=++sequence;
  if(typeof state!=='undefined'&&state.busy){show('任务运行中，请完成后再读取工程信息。','Wait for the current task before importing.',true);return;}
  const bridge=window.pywebview?.api;
  if(!bridge?.ft_read_project_folder){show('请在桌面版拖入文件夹；也可手动填写输出路径。','Use the desktop app to drop a folder, or type the output path.',true);return;}
  show('正在读取文件夹信息…','Reading folder information…');
  try{
   const result=await bridge.ft_read_project_folder(paths);if(ticket!==sequence)return;
   if(!result?.ok){show(result?.message||'读取失败，原参数保留。','Could not read this folder. Existing values were kept.',true);return;}
   const output=outputFor(result);
   const values={ftOutRoot:output};
   if(result.matched){const f=result.fields;Object.assign(values,{ftName:f.name,ftSeq:f.seq,ftLevel:f.level,ftDate:f.date,ftUser:f.user});}
   Object.entries(values).forEach(([id,value])=>{q(id).value=value;window.ToolPrefs.touch(id);});
   lastDrop=result;lastOutput=output;
   if(result.matched)show('已读取 '+result.project_root+'；输出：'+output+'。保留原序号，不自动递增。','Read '+result.project_root+'; output: '+output+'. Original sequence retained.');
   else show('未识别到工程命名：已将拖入目录作为输出路径，项目信息保持原样。','No project naming found. The folder is the output path; project fields are unchanged.');
   await window.ToolPrefs.flush();if(ticket!==sequence)return;
   if(typeof updateNamingSamples==='function')updateNamingSamples();
   if(typeof ftPlan==='function')await ftPlan(true);
  }catch(error){if(ticket===sequence)show('读取失败：'+error.message,'Import failed: '+error.message,true);}
 }
 function pathsFromText(text){return text.split(/\r?\n/).map(s=>s.trim()).filter(s=>s&&!s.startsWith('#')).map(s=>{if(!s.startsWith('file:'))return s;try{const url=new URL(s);let p=decodeURIComponent(url.pathname);if(url.hostname)return '\\\\'+url.hostname+p.replaceAll('/','\\');return p.replace(/^\/([A-Za-z]:)/,'$1').replaceAll('/','\\');}catch{return s;}});}
 function init(){const input=q('ftOutRoot');
  q('ftDropParent').addEventListener('change',async()=>{
   if(!lastDrop?.matched)return;
   if(input.value!==lastOutput||(typeof state!=='undefined'&&state.busy)){
    show('选择已记住，将用于下次拖入；当前输出路径保留。','Choice saved for the next drop; the current output path is unchanged.');return;
   }
   const output=outputFor(lastDrop);input.value=output;lastOutput=output;window.ToolPrefs.touch('ftOutRoot');
   show('输出路径已切换：'+output,'Output path changed: '+output);
   await window.ToolPrefs.flush();if(typeof ftPlan==='function')await ftPlan(true);
  });

  input.addEventListener('dragover',event=>{event.preventDefault();event.dataTransfer.dropEffect='copy';input.classList.add('drop-active');});
  input.addEventListener('dragleave',()=>input.classList.remove('drop-active'));
  input.addEventListener('drop',event=>{event.preventDefault();input.classList.remove('drop-active');const files=[...event.dataTransfer.files];if(files.length){if(nativeReady)return;const paths=files.map(f=>f.pywebviewFullPath||f.path||'');if(paths.every(Boolean))receive(paths);else show('未获取到完整路径，请在桌面版拖入或粘贴完整路径。','Full paths are unavailable. Use the desktop app or paste a full path.',true);}else{const text=event.dataTransfer.getData('text/uri-list')||event.dataTransfer.getData('text/plain');receive(pathsFromText(text));}});
  document.addEventListener('drop',event=>{if(event.dataTransfer?.files.length)event.preventDefault();});
 }
 window.RenameProjectDrop={receive,setNativeReady:(value,error)=>{nativeReady=!!value;window.RenameProjectDrop.bindingError=error||null;if(error)show("拖入初始化失败："+error,"Drop initialization failed: "+error,true);},get nativeReady(){return nativeReady;}};
 window.addEventListener('languagechanged',()=>{if(message)show(message.zh,message.en,message.error);});
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
