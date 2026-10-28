# -*- coding: utf-8 -*-
"""v4 壳入口：pywebview(WebView2) 优先；Edge --app 手动回退（--shell edge）。

阶段 A 范围（30 号方案 §三）：
- pywebview 直启 + js_api 桥（PtApi）；
- 探针（像素级渲染检查）完整版在阶段 E 接入，本阶段提供 --shell edge 手动回退；
- http 源 + 固定端口（httpd.py），不用 file://。

用法：
  python desktop_app.py                 # pywebview 壳（默认）
  python desktop_app.py --shell edge    # Edge --app 回退（本进程兼任 httpd）
  python desktop_app.py --port 26789    # 指定端口
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

from shell.httpd import DEFAULT_PORT, make_server, WEB_DIR  # noqa: E402
from api.pt_api import PtApi  # noqa: E402


def run_pywebview(port: int) -> None:
    import webview
    srv = make_server(port)
    # 服务跑后台线程（pywebview 独占主线程跑事件循环）
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = "http://127.0.0.1:%d/index.html" % srv.port
    print("[v4-shell] pywebview @ %s" % url)
    api = PtApi()
    # 日志回调挂点已内置于 web/js/app.js（__onTaskLine 本地定义，行为等价），
    # 壳无需再注入；且 pywebview 5.x 在 start() 前调 evaluate_js 会抛
    # "Main window failed to start"（2026-09-30 打包冒烟实测），故不在此注入。
    from shell.window_memory import window_options, remember_window
    win = webview.create_window(
        "Pro Tools 工具箱 H v4.2.1", url, js_api=api,
        **window_options(api._h_preferences))
    remember_window(win, api._h_preferences)
    webview.start(icon=os.path.join(WEB_DIR,'assets','logos','p.ico'))


def run_edge(port: int) -> None:
    from shell import httpd
    srv = httpd.make_server(port)   # 先占端口（占用自愈在此发生）再拼 URL
    url = "http://127.0.0.1:%d/index.html" % srv.port
    edge_candidates = [
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
    ]
    edge = next((p for p in edge_candidates if os.path.isfile(p)), None)
    if edge is None:
        print("[v4-shell] 未找到 Edge，回退默认浏览器")
        import webbrowser
        threading.Thread(target=lambda: (threading.Event().wait(0.6), webbrowser.open(url))).start()
    else:
        subprocess.Popen([edge, "--app=" + url, "--window-size=1240,860"])
    print("[v4-httpd] serving @ %s" % url)   # 本进程兼任服务
    try:
        srv.serve_forever()
    finally:
        srv.server_close()


def main() -> None:
    ap = argparse.ArgumentParser(description="pt-audio-toolkit v4 壳入口（阶段 A）")
    ap.add_argument("--shell", choices=["auto", "pywebview", "edge"], default="auto")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = ap.parse_args()

    shell = args.shell
    if shell == "auto":
        try:
            import webview
            # 防同名假模块（daimon base 里有不带 API 的 webview）：必须验 API 存在
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
