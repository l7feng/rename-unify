# -*- coding: utf-8 -*-
"""v4 阶段 C · 剪映工程工具包壳入口：pywebview(WebView2) 优先；Edge --app 回退。

与 shell/desktop_app.py（pt-tools 壳）同构，差异：
- js_api 桥 = api.jy_api.JyApi（同进程函数直调剪映核心）；
- 页面 = /jy.html（三页签：导入 / 导出 / 人声分离）；
- 端口 = 26790（pt 壳 26789 占用 +1 自愈同样生效）。

用法：
  python shell/jy_desktop.py                 # pywebview 壳（默认）
  python shell/jy_desktop.py --shell edge    # Edge --app 回退（本进程兼任 httpd）
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
V4_DIR = os.path.dirname(HERE)
if V4_DIR not in sys.path:
    sys.path.insert(0, V4_DIR)

from shell.httpd import make_server, WEB_DIR  # noqa: E402
from api.jy_api import JyApi  # noqa: E402

PAGE = "jy.html"
DEFAULT_PORT_JY = 26790
from shell.app_version import tool_version
TITLE = "剪映工程工具包 H v" + tool_version("jy")


def run_pywebview(port: int) -> None:
    import webview
    srv = make_server(port)
    # 服务跑后台线程（pywebview 独占主线程跑事件循环）
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = "http://127.0.0.1:%d/%s" % (srv.port, PAGE)
    print("[jy-shell] pywebview @ %s" % url)
    api = JyApi()
    # 日志/事件挂点已内置于 web/js/jy.js（__onJyLine / __onShellEvent 本地定义，
    # 行为等价），壳无需再注入；且 pywebview 5.x 在 start() 前调 evaluate_js
    # 会抛 "Main window failed to start"（2026-09-30 打包冒烟实测）。
    from shell.window_memory import window_options, remember_window
    win = webview.create_window(
        TITLE, url, js_api=api,
        **window_options(api._h_preferences))
    remember_window(win, api._h_preferences)
    webview.start(icon=os.path.join(WEB_DIR,'assets','logos','j.ico'))


def run_edge(port: int) -> None:
    from shell import httpd
    srv = httpd.make_server(port)   # 先占端口（占用自愈在此发生）再拼 URL
    url = "http://127.0.0.1:%d/%s" % (srv.port, PAGE)
    edge_candidates = [
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
    ]
    edge = next((p for p in edge_candidates if os.path.isfile(p)), None)
    if edge is None:
        print("[jy-shell] 未找到 Edge，回退默认浏览器")
        import webbrowser
        threading.Thread(target=lambda: (threading.Event().wait(0.6), webbrowser.open(url))).start()
    else:
        subprocess.Popen([edge, "--app=" + url, "--window-size=1240,860"])
    print("[jy-httpd] serving @ %s" % url)   # 本进程兼任服务
    try:
        srv.serve_forever()
    finally:
        srv.server_close()


def main() -> None:
    if len(sys.argv) == 3 and sys.argv[1] == "--self-check":
        import json
        from pathlib import Path
        from api.ofx_manager import OfxManager
        result={"version":tool_version("jy"),"hello":JyApi().hello(),"ofx":OfxManager().list(),"web":str(WEB_DIR)}
        Path(sys.argv[2]).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
        return
    ap = argparse.ArgumentParser(description="剪映工程工具包 v4 壳入口（阶段 C）")
    ap.add_argument("--shell", choices=["auto", "pywebview", "edge"], default="auto")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT_JY)
    args = ap.parse_args()

    shell = args.shell
    if shell == "auto":
        try:
            import webview
            # 防同名假模块（必须验 API 存在，同 desktop_app.py 教训）
            assert hasattr(webview, "create_window") and hasattr(webview, "start")
            shell = "pywebview"
        except Exception:
            shell = "edge"

    if shell == "pywebview":
        run_pywebview(args.port)
    else:
        run_edge(args.port)


if __name__ == "__main__":
    main()
