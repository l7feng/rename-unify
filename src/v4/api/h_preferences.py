"""H版独立本机记忆：原子写入，路径/窗口不写入T版或共享配置。"""
from __future__ import annotations
import json
import os
import sys
import threading
from pathlib import Path

THEMES=('dark','claude','warm','ocean')

class Preferences:
    def __init__(self, tool):
        root=Path(os.environ.get('PT_H_PREFS_ROOT') or (Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parents[3]/'build'/'local-preferences'))
        self.path=root/(tool+('.preferences.local.json' if tool=='re' else '.h-preferences.local.json'))
        self.legacy_path=root/'re.h-preferences.local.json' if tool=='re' else None
        self.lock=threading.RLock()

    def read(self):
        with self.lock:
            try:
                source=self.path if self.path.exists() or self.legacy_path is None else self.legacy_path
                data=json.loads(source.read_text(encoding='utf-8'))
                if not isinstance(data,dict): raise ValueError('记忆文件格式错误')
                return data
            except FileNotFoundError:
                return {}

    def update(self, **patch):
        with self.lock:
            data=self.read();data.update(patch)
            self.path.parent.mkdir(parents=True,exist_ok=True)
            temp=self.path.with_suffix('.tmp')
            try:
                with temp.open('w',encoding='utf-8') as f:
                    json.dump(data,f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
                os.replace(temp,self.path)
                actual=self.read()
                if any(actual.get(k)!=v for k,v in patch.items()):raise OSError('写入后读取不一致')
            finally:
                if temp.exists():temp.unlink()

class HPreferencesMixin:
    def _init_h_preferences(self, tool):
        self._h_tool=tool
        self._h_preferences=Preferences(tool)

    @staticmethod
    def _existing_dialog_directory(raw):
        raw = str(raw or "").strip().strip('"')
        if not raw:
            return ""
        path = Path(os.path.expandvars(os.path.expanduser(raw)))
        if not path.is_absolute():
            return ""
        while not path.is_dir():
            if path.parent == path:
                return ""
            path = path.parent
        return str(path)

    def _dialog_directory(self, current, key):
        # Form restoration and native chooser initialization are separate contracts.
        try:
            saved = self._h_preferences.read().get('dialogs', {}).get(key, '')
        except (OSError, ValueError):
            saved = ''
        return self._existing_dialog_directory(current) or self._existing_dialog_directory(saved)

    def _remember_dialog(self, result, key, folder):
        if not result:
            return None
        selected = str(result[0])
        directory = selected if folder else str(Path(selected).parent)
        with self._h_preferences.lock:
            saved = self._h_preferences.read().get('dialogs', {})
            saved[key] = directory
            self._h_preferences.update(dialogs=saved)
        return selected

    def set_ui_language(self, language):
        if language not in ('zh-CN','en'):return {'ok':False,'message':'Invalid language'}
        import webview
        from shell.app_version import tool_version
        names={'pt':('Pro Tools 工具箱','Pro Tools Toolkit'),'jy':('剪映工程工具包','Jianying Draft Toolkit'),'re':('统一命名工具','Rename Unify')}
        if webview.windows:
            webview.windows[0].set_title(names[self._h_tool][language=='en']+(' v' if self._h_tool=='re' else ' H v')+tool_version(self._h_tool))
        return {'ok':True}

    def get_ui_prefs(self):
        try:
            state=self._h_preferences.read().get('form',{})
            theme=state.get('theme','dark')
            return {'theme':theme if theme in THEMES else 'dark','button_style':'glass'}
        except (OSError,ValueError) as exc:
            return {'theme':'dark','button_style':'glass','error':str(exc)}

    def get_form_state(self):
        try:return {'ok':True,'state':self._h_preferences.read().get('form',{})}
        except (OSError,ValueError) as exc:return {'ok':False,'message':str(exc)}

    def save_form_state(self, raw):
        try:
            state=json.loads(raw)
            if not isinstance(state,dict) or not isinstance(state.get('fields'),dict):raise ValueError('参数格式错误')
            if any(not isinstance(k,str) or not isinstance(v,(str,bool)) for k,v in state['fields'].items()):raise ValueError('参数值格式错误')
            state['language']='en' if state.get('language')=='en' else 'zh-CN'
            state['theme']=state.get('theme') if state.get('theme') in THEMES else 'dark'
            self._h_preferences.update(form=state)
            return {'ok':True}
        except (OSError,ValueError) as exc:return {'ok':False,'message':str(exc)}

    def set_style(self, style):
        return {'ok':style=='glass','style':'glass','message':'仅提供玻璃外观'}

    def set_mode(self, mode):
        if mode not in THEMES:return {'ok':False,'message':'未知主题'}
        try:
            state=self._h_preferences.read().get('form',{});state['theme']=mode
            self._h_preferences.update(form=state);return {'ok':True,'mode':mode}
        except (OSError,ValueError) as exc:return {'ok':False,'message':str(exc)}

    def get_glass(self):
        try:return {'ok':True,'glass':self._h_preferences.read().get('glass')}
        except (OSError,ValueError) as exc:return {'ok':False,'message':str(exc)}

    def save_glass(self, raw):
        try:
            glass=json.loads(raw)
            if not isinstance(glass,dict):raise ValueError('玻璃参数格式错误')
            self._h_preferences.update(glass=glass);return {'ok':True}
        except (OSError,ValueError) as exc:return {'ok':False,'message':str(exc)}
