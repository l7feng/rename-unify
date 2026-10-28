"""恢复H桌面窗口，显示器变化后限制在当前可见工作区内。"""
import ctypes
from ctypes import wintypes
import threading
import json

def work_areas():
    if not hasattr(ctypes,'windll'):return [(0,0,1920,1080)]
    result=[]
    class INFO(ctypes.Structure):
        _fields_=[('size',wintypes.DWORD),('monitor',wintypes.RECT),('work',wintypes.RECT),('flags',wintypes.DWORD)]
    cbtype=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HMONITOR,wintypes.HDC,ctypes.POINTER(wintypes.RECT),wintypes.LPARAM)
    def enum(monitor,dc,rect,param):
        info=INFO();info.size=ctypes.sizeof(INFO)
        if ctypes.windll.user32.GetMonitorInfoW(monitor,ctypes.byref(info)):
            r=info.work;result.append((r.left,r.top,r.right,r.bottom))
        return True
    ctypes.windll.user32.EnumDisplayMonitors(None,None,cbtype(enum),0)
    return result or [(0,0,1920,1080)]

def window_options(store):
    try:g=store.read().get('window',{})
    except (OSError,ValueError):g={}
    areas=work_areas();x=g.get('x');y=g.get('y')
    valid=lambda n:isinstance(n,(int,float)) and not isinstance(n,bool)
    area=next((a for a in areas if valid(x) and valid(y) and a[0]<=x<a[2] and a[1]<=y<a[3]),areas[0])
    left,top,right,bottom=area
    width=min(max(780,int(g.get('width',1240))) if valid(g.get('width',1240)) else 1240,right-left)
    height=min(max(560,int(g.get('height',860))) if valid(g.get('height',860)) else 860,bottom-top)
    return dict(width=width,height=height,x=max(left,min(int(x) if valid(x) else left+(right-left-width)//2,right-width)),y=max(top,min(int(y) if valid(y) else top+(bottom-top-height)//2,bottom-height)),min_size=(min(780,right-left),min(560,bottom-top)),maximized=g.get('maximized') is True,background_color='#191a1e')

def remember_window(win, store):
    lock=threading.RLock();timer=None
    initial=window_options(store)
    normal={k:initial[k] for k in ('x','y','width','height')};maximized=initial['maximized']
    def save():
        try:store.update(window=dict(normal,maximized=maximized))
        except (OSError,ValueError) as exc:print('[window-memory] 保存失败:',exc,flush=True)
    def capture(*args):
        nonlocal timer,maximized
        with lock:
            try:
                native=str(win.native.WindowState)
                if 'Minimized' in native:return
                if 'Maximized' in native:maximized=True
                elif 'Normal' in native:
                    maximized=False;normal.update(x=win.x,y=win.y,width=win.width,height=win.height)
            except AttributeError:
                if not maximized:normal.update(x=win.x,y=win.y,width=win.width,height=win.height)
            if timer:timer.cancel()
            timer=threading.Timer(.3,save);timer.daemon=True;timer.start()
    def on_maximized():
        nonlocal maximized
        maximized=True;capture()
    def on_restored():
        nonlocal maximized
        maximized=False;capture()
    closing=False
    def finish_close():
        # The first close is cancelled; evaluate after the GUI event returns.
        try:
            raw=win.evaluate_js("JSON.stringify({form:window.ToolPrefs&&window.ToolPrefs.snapshot(),glass:window.GlassPrefs&&window.GlassPrefs.snapshot()})")
            state=json.loads(raw) if isinstance(raw,str) else raw
            if isinstance(state,dict):
                patch={k:v for k,v in state.items() if isinstance(v,dict)}
                if patch:store.update(**patch)
        except Exception as exc:print('[window-memory] 关闭前参数保存失败:',exc,flush=True)
        finally:
            save();win.destroy()
    def on_closing():
        nonlocal closing
        with lock:
            if closing:return True
            closing=True
            if timer:timer.cancel()
            threading.Thread(target=finish_close,daemon=True).start()
            return False
    win.events.moved+=capture;win.events.resized+=capture
    win.events.maximized+=on_maximized;win.events.restored+=on_restored;win.events.closing+=on_closing
