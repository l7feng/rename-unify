# -*- coding: utf-8 -*-
"""v4 内置 http 服务：127.0.0.1 固定端口，serve web/ 静态资源。

⚠ 30 号方案 §一：必须 http 源 + 固定端口（settlement 2026-09-28 实测结论）——
file:// 或随机端口都会丢会话态。
"""
from __future__ import annotations

import functools
import os
import sys
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

WEB_DIR = (os.path.join(sys._MEIPASS, "web") if getattr(sys, "frozen", False)
           else os.environ.get("PT_WEB_ROOT", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "web"))))
DEFAULT_PORT = 26789          # settlement-tool 占 26788，错开
MAX_RETRY = 10                # 端口占用自愈：+1 重试


def make_server(port: int = DEFAULT_PORT):
    handler = functools.partial(SimpleHTTPRequestHandler, directory=WEB_DIR)
    last_err: Exception | None = None
    for p in range(port, port + MAX_RETRY):
        try:
            srv = ThreadingHTTPServer(("127.0.0.1", p), handler)
            srv.port = p
            return srv
        except OSError as exc:          # 端口占用 → +1 自愈
            last_err = exc
    raise RuntimeError("端口 %d~%d 全部占用：%s" % (port, port + MAX_RETRY - 1, last_err))


def serve_forever(port: int = DEFAULT_PORT) -> int:
    """阻塞版：Edge 回退模式用（壳进程即服务进程）。返回实际端口。"""
    srv = make_server(port)
    print("[v4-httpd] serving %s @ http://127.0.0.1:%d" % (WEB_DIR, srv.port))
    try:
        srv.serve_forever()
    finally:
        srv.server_close()
    return srv.port


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="v4 web 静态服务（调试用）")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = ap.parse_args()
    serve_forever(args.port)
