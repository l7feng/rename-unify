"""Jianying OFX cache management. Inspect binaries without loading plug-in code."""
from __future__ import annotations
import base64, hashlib, json, os, shutil, struct, subprocess, tempfile, threading
from pathlib import Path

_LOCK=threading.RLock()
FLAGS={'creationflags':0x08000000} if os.name=='nt' else {}

def linked(path):
    return path.is_symlink() or (hasattr(path,'is_junction') and path.is_junction())

def jianying_running():
    p=subprocess.run(['tasklist','/FI','IMAGENAME eq JianyingPro.exe','/FO','CSV','/NH'],capture_output=True,text=True,errors='replace',timeout=15,**FLAGS)
    if p.returncode: raise RuntimeError('无法核对剪映运行状态，请稍后重试。')
    return 'jianyingpro.exe' in p.stdout.lower()

def recycle_directory(path):
    # SendToRecycleBin only; there is deliberately no permanent-delete fallback.
    literal=str(path).replace("'","''")
    script="""$ErrorActionPreference='Stop';Add-Type -AssemblyName Microsoft.VisualBasic;
[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory('%s',[Microsoft.VisualBasic.FileIO.UIOption]::OnlyErrorDialogs,[Microsoft.VisualBasic.FileIO.RecycleOption]::SendToRecycleBin,[Microsoft.VisualBasic.FileIO.UICancelOption]::ThrowException)"""%literal
    encoded=base64.b64encode(script.encode('utf-16-le')).decode('ascii')
    p=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',encoded],capture_output=True,text=True,errors='replace',timeout=120,**FLAGS)
    if p.returncode or path.exists(): raise RuntimeError('未能移入回收站。请完全退出剪映后重试；可能仍被占用或没有删除权限。')

def tree_info(path):
    rows=[];size=0;count=0
    if linked(path): raise ValueError('不支持链接或联接目录。')
    for base,dirs,files in os.walk(path,followlinks=False):
        for name in dirs+files:
            p=Path(base)/name
            if linked(p): raise ValueError('插件包含链接目录或文件，已停止。')
            st=p.stat();rows.append((str(p.relative_to(path)),st.st_size,st.st_mtime_ns,p.is_dir()))
            if p.is_file():size+=st.st_size;count+=1
    st=path.stat();token=hashlib.sha256(json.dumps([st.st_mtime_ns,sorted(rows)],ensure_ascii=False).encode()).hexdigest()
    return dict(files=count,bytes=size,token=token)

def validate_binary(path):
    data=path.read_bytes()
    if len(data)<128 or data[:2]!=b'MZ': raise ValueError('不是有效Windows插件：'+path.name)
    pe=struct.unpack_from('<I',data,60)[0]
    if pe+26>len(data) or data[pe:pe+4]!=b'PE\0\0' or struct.unpack_from('<H',data,pe+4)[0]!=0x8664:
        raise ValueError('剪映需要64位Windows OFX插件：'+path.name)
    if b'OfxGetNumberOfPlugins' not in data or b'OfxGetPlugin' not in data:
        raise ValueError('文件缺少OFX插件入口：'+path.name)

def bundle_binaries(path):
    win64=path/'Contents'/'Win64'
    binaries=list(win64.glob('*.ofx')) if win64.is_dir() else []
    if not binaries:raise ValueError('未找到Contents/Win64中的.ofx文件；请选完整.ofx.bundle文件夹。')
    for p in binaries:validate_binary(p)
    return binaries

class OfxManager:
    def __init__(self,root=None):
        self.root=Path(root) if root else Path(os.environ['LOCALAPPDATA'])/'JianyingPro/User Data/Cache/OFX'
    def _check_root(self):
        for p in [self.root,*self.root.parents]:
            if linked(p):raise ValueError('插件缓存路径包含链接或联接，已停止操作。')
    def _target(self,name):
        self._check_root()
        if not name or Path(name).name!=name or any(c in name for c in '/\\:') or not name.lower().endswith('.ofx.bundle'):
            raise ValueError('无效插件名称。请刷新列表后选择。')
        target=self.root/name
        if target.resolve().parent!=self.root.resolve():raise ValueError('插件路径超出缓存目录。')
        if linked(target):raise ValueError('拒绝操作链接目录。')
        return target
    def _idle(self):
        if jianying_running():raise RuntimeError('请先保存工程并完全退出剪映（含托盘），再安装或删除插件。')
    def list(self):
        self._check_root();items=[]
        labels={'JYMixBridge.ofx.bundle':'剪映混音交互','JYAudioToolkit.ofx.bundle':'旧版音频工具','JYInterfaceProbe.ofx.bundle':'旧诊断插件'}
        if self.root.is_dir():
            for p in sorted(self.root.iterdir(),key=lambda x:x.name.lower()):
                if not p.name.lower().endswith('.ofx.bundle'):continue
                item=dict(name=p.name,label=labels.get(p.name,p.name.removesuffix('.ofx.bundle')),path=str(p),valid=False)
                try:
                    self._target(p.name);item.update(tree_info(p));bundle_binaries(p);item['valid']=True
                except Exception as e:item['error']=str(e)
                items.append(item)
        return dict(ok=True,root=str(self.root),running=jianying_running(),plugins=items,
                    message='缓存安装不等于启用；请在剪映启动后确认插件列表。')
    def install(self,source):
        with _LOCK:
            self._check_root();self._idle()
            src=Path(str(source).strip().strip('"'))
            if not src.is_absolute() or not src.exists() or linked(src):raise ValueError('请选择存在的完整插件文件夹或.ofx文件。')
            for parent in src.parents:
                if linked(parent):raise ValueError('插件来源路径包含链接目录。')
            is_bundle=src.is_dir() and src.name.lower().endswith('.ofx.bundle')
            if is_bundle:
                before=tree_info(src);bundle_binaries(src);name=src.name
            elif src.is_file() and src.suffix.lower()=='.ofx':
                validate_binary(src);before=None;name=src.name+'.bundle'
            else:raise ValueError('请选择.ofx.bundle文件夹或64位.ofx文件，不要选择Win64目录。')
            dst=self._target(name)
            if dst.exists():raise ValueError('同名插件已存在。若需更换版本，请先在列表中删除旧副本，再安装新版。')
            self.root.mkdir(parents=True,exist_ok=True)
            with tempfile.TemporaryDirectory(prefix='jy-ofx-install-') as temp:
                stage=Path(temp)/name
                if is_bundle:
                    shutil.copytree(src,stage)
                    if tree_info(src)['token']!=before['token']:raise ValueError('复制期间源插件发生变化，请重新选择。')
                else:
                    (stage/'Contents/Win64').mkdir(parents=True);shutil.copy2(src,stage/'Contents/Win64'/src.name)
                info=tree_info(stage);bundle_binaries(stage);self._idle();self._check_root()
                if dst.exists():raise ValueError('同名插件刚被其他操作安装，请刷新列表。')
                # Final move is within the destination volume; publishing the directory is atomic.
                with tempfile.TemporaryDirectory(prefix='.ofx-stage-',dir=self.root.parent) as publish:
                    prepared=Path(publish)/name;shutil.copytree(stage,prepared);bundle_binaries(prepared)
                    prepared.rename(dst)
            actual=tree_info(dst)
            if (actual['files'],actual['bytes'])!=(info['files'],info['bytes']):raise RuntimeError('缓存副本校验失败，请刷新检查。')
            return dict(ok=True,message='已安装到剪映缓存。重新启动剪映后确认；若未显示，请在剪映插件页使用原生导入。',path=str(dst))
    def delete(self,name,token):
        with _LOCK:
            target=self._target(name);self._idle()
            if not target.is_dir():raise ValueError('插件已不存在，请刷新列表。')
            actual=tree_info(target)
            if not token or actual['token']!=token:raise ValueError('插件文件已变化，请刷新列表并重新确认删除。')
            recycle_directory(target)
            return dict(ok=True,message='已移入回收站：'+name,path=str(target))
