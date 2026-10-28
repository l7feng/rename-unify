# -*- coding: utf-8 -*-
"""v4 阶段 D · 统一命名工具壳入口：pywebview(WebView2) 优先；Edge --app 回退。

与 shell/desktop_app.py（pt 壳 26789）/ shell/jy_desktop.py（剪映壳 26790）同构：
- js_api 桥 = api.re_api.ReApi（同进程函数直调 core_rules/foldertree/config）；
- 页面 = /re.html（五页签：项目信息与模板 / 目标与归位 / 预览与执行 / 回溯与撤销 / 工程文件夹）；
- 端口 = 26791（占用 +1 自愈同样生效）。
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
from api.re_api import ReApi  # noqa: E402

PAGE = "re.html"
DEFAULT_PORT_RE = 26791
from shell.app_version import tool_version
TITLE = "统一命名工具 v" + tool_version("re")


def run_pywebview(port: int) -> None:
    import webview
    srv = make_server(port)
    # 服务跑后台线程（pywebview 独占主线程跑事件循环）
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = "http://127.0.0.1:%d/%s" % (srv.port, PAGE)
    print("[re-shell] pywebview @ %s" % url)
    api = ReApi()
    # 日志/事件挂点已内置于 web/js/re.js（__onReLine / __onShellEvent 本地定义，
    # 行为等价），壳无需再注入；且 pywebview 5.x 在 start() 前调 evaluate_js
    # 会抛 "Main window failed to start"（2026-09-30 打包冒烟实测）。
    from shell.window_memory import window_options, remember_window
    win = webview.create_window(
        TITLE, url, js_api=api,
        **window_options(api._h_preferences))
    remember_window(win, api._h_preferences)
    from shell.re_folder_drop import bind_project_drop
    win.events.loaded += lambda: bind_project_drop(win)
    webview.start(icon=os.path.join(WEB_DIR,'assets','logos','r.ico'))


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
        print("[re-shell] 未找到 Edge，回退默认浏览器")
        import webbrowser
        threading.Thread(target=lambda: (threading.Event().wait(0.6), webbrowser.open(url))).start()
    else:
        subprocess.Popen([edge, "--app=" + url, "--window-size=1240,860"])
    print("[re-httpd] serving @ %s" % url)   # 本进程兼任服务
    try:
        srv.serve_forever()
    finally:
        srv.server_close()


def main() -> None:
    ap = argparse.ArgumentParser(description="统一命名工具 v4 壳入口（阶段 D）")
    ap.add_argument("--shell", choices=["auto", "pywebview", "edge"], default="auto")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT_RE)
    args = ap.parse_args()

    shell = args.shell
    if shell == "auto":
        try:
            import webview
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
