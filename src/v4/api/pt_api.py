# -*- coding: utf-8 -*-
"""v4 阶段 B · pt-tools 的 js_api 桥：HTML 前端 ↔ Python 核心（四页全链路）。

设计约束（30 号方案 §一）：
- 核心逻辑（ptools/core、skills/*）零改动——导出命令复用 core/naming.build_export_cmds，
  技能解析复用 core/paths.PathResolver，配置读写复用 C2 双文件层；
- 长任务（扫描/导出/交付包）子进程后台线程，进度经 evaluate_js 推回前端；
- 前端演示态（浏览器直开）不依赖本桥，桥缺失时由 app.js 降级。
"""
from __future__ import annotations

import datetime
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time

# --- 路径 ---
V4_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # src/v4
PT_ROOT = os.path.join(os.path.dirname(V4_DIR), "pt-tools")             # src/pt-tools
SCAN_SCRIPT = os.path.join(PT_ROOT, "skills", "pt-scanner", "scripts", "pt_scan.py")

if PT_ROOT not in sys.path:
    sys.path.insert(0, PT_ROOT)

from ptools.core import config as core_config          # noqa: E402  （C2 双文件层）
from ptools.core.paths import PathResolver             # noqa: E402  （技能解析）
from ptools.core.naming import build_export_cmds       # noqa: E402  （导出命令）
from ptools.core.settings import EXPORT_MODES          # noqa: E402  （mix/bus/stem/track）

PTSL_HOST, PTSL_PORT = "127.0.0.1", 31416


def _log_class(line: str) -> str:
    if re.search(r"\[error\]|失败|Traceback|error", line, re.I):
        return "err"
    if re.search(r"✓|完成|成功|OK|done", line, re.I):
        return "ok"
    return ""


from api.h_preferences import HPreferencesMixin


class PtApi(HPreferencesMixin):
    """暴露给 window.pywebview.api 的桥对象。方法名即 JS 侧调用名。"""

    def __init__(self) -> None:
        self._init_h_preferences("pt")
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        cfg = core_config.load_config()
        self.resolver, self.resolver_ok, self.resolver_msg = PathResolver.detect(cfg)
        # B2 补齐：任务种类（export 才触发自动质检）+ 质检上下文
        self._task_kind = ""
        self._qc_ctx: dict | None = None

    # ---------- 界面偏好（复用 C2 双文件配置层） ----------


    # ---------- 状态 ----------

    def ptsl_status(self) -> dict:
        try:
            with socket.create_connection((PTSL_HOST, PTSL_PORT), timeout=0.8):
                return {"online": True, "host": "%s:%d" % (PTSL_HOST, PTSL_PORT)}
        except OSError:
            return {"online": False, "host": "%s:%d" % (PTSL_HOST, PTSL_PORT)}

    def skills_status(self) -> dict:
        ok, msg = self.resolver.status()
        return {"ok": ok, "message": msg}

    # ---------- 目录 / 文件选择（pywebview 原生对话框） ----------

    def pick_directory(self, title: str = "选择目录") -> str | None:
        import webview
        win = webview.windows[0] if webview.windows else None
        if win is None:
            return None
        result = win.create_file_dialog(webview.FOLDER_DIALOG)
        if result:
            self._remember_out_dir(result[0])
            return result[0]
        return None

    def pick_file(self, title: str = "选择档案") -> str | None:
        import webview
        win = webview.windows[0] if webview.windows else None
        if win is None:
            return None
        result = win.create_file_dialog(
            webview.OPEN_DIALOG, allow_multiple=False,
            file_types=("JSON 档案 (*.json)", "全部文件 (*.*)"))
        if result:
            return result[0]
        return None

    def open_path(self, path: str) -> dict:
        if os.path.isdir(path) or os.path.isfile(path):
            os.startfile(path)  # noqa: S606
            return {"ok": True}
        return {"ok": False, "message": "路径不存在：%s" % path}

    def _remember_out_dir(self, d: str) -> None:
        cfg = core_config.load_config()
        cfg["last_out_dir"] = d
        core_config.save_config(cfg)

    # ---------- 档案（profile） ----------

    def load_profile(self, path: str) -> dict:
        """读档案 json → 前端摘要（工程名/轨道/源计数）。

        B2 补齐：多回 fps（session.timecode_rate，视频时长→时间码换算用）
        与 empty_tracks（无音频块的轨道名，剔除空轨管理的候选名单）——
        判定口径与 T版 gui/app.py _empty_track_names 完全一致。
        """
        if not os.path.isfile(path):
            return {"ok": False, "message": "档案不存在：%s" % path}
        try:
            data = json.loads(open(path, encoding="utf-8-sig").read())
        except Exception as exc:
            return {"ok": False, "message": "档案解析失败：%s" % exc}
        tracks = data.get("tracks", []) or []
        sources = data.get("sources", data.get("audio_files", [])) or []
        st = os.stat(path)
        name = (data.get("project") or data.get("session") or
                os.path.basename(path).replace("-pt-profile.json", "").replace(".json", ""))

        def _tname(t):
            return t.get("name", "") if isinstance(t, dict) else str(t)

        empty: list = []
        for t in tracks:
            if not isinstance(t, dict):
                continue
            cc = (t.get("attributes") or {}).get("contains_clips")
            if cc is None:
                cc = t.get("contains_clips")
            if cc is False and t.get("name"):
                empty.append(t["name"])
        try:
            fps = float(str((data.get("session") or {}).get("timecode_rate")
                            or "25").split()[0])
        except (TypeError, ValueError, AttributeError):
            fps = 25.0
        return {"ok": True, "path": path, "project": name,
                "mtime": datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
                "track_count": len(tracks),
                "tracks": [_tname(t) for t in tracks[:400]],
                "empty_tracks": empty,
                "fps": fps,
                "source_count": len(sources) if isinstance(sources, list) else 0}

    def list_library(self) -> dict:
        """档案库：profile_dir 平铺的 *.json + 导出历史（last_out_dir 下工程文件夹）。"""
        cfg = core_config.load_config()
        pdir = cfg.get("profile_dir", "") or ""
        items = []
        if pdir and os.path.isdir(pdir):
            for fn in os.listdir(pdir):
                if not fn.lower().endswith(".json"):
                    continue
                p = os.path.join(pdir, fn)
                try:
                    st = os.stat(p)
                except OSError:
                    continue
                items.append({"path": p, "file": fn,
                              "mtime": datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
                              "size_kb": round(st.st_size / 1024, 1)})
        items.sort(key=lambda x: x["mtime"], reverse=True)
        hist = []
        outroot = cfg.get("last_out_dir", "") or ""
        if outroot and os.path.isdir(outroot):
            for fn in sorted(os.listdir(outroot), reverse=True):
                p = os.path.join(outroot, fn)
                if os.path.isdir(p):
                    try:
                        mt = datetime.datetime.fromtimestamp(os.stat(p).st_mtime).strftime("%Y-%m-%d %H:%M")
                    except OSError:
                        continue
                    hist.append({"name": fn, "path": p, "mtime": mt})
        return {"ok": True, "profile_dir": pdir, "items": items[:200], "history": hist[:100]}

    def delete_profile(self, path: str) -> dict:
        """删除档案 → Windows 回收站（照 LibraryTab 语义：绝不静默硬删）。"""
        if not os.path.isfile(path):
            return {"ok": False, "message": "文件不存在：%s" % path}
        ps = ("Add-Type -AssemblyName Microsoft.VisualBasic;"
              "[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile("
              "'%s', 'OnlyErrorDialogs', 'SendToRecycleBin')" % path.replace("'", "''"))
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                           capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            return {"ok": True, "message": "已移入回收站：%s" % os.path.basename(path)}
        return {"ok": False, "message": "删除失败：%s" % (r.stderr or ("exit %d" % r.returncode))}

    # ---------- 通用子进程（扫描/导出/交付包共用日志流） ----------

    def _spawn(self, cmds: list) -> dict:
        if self._proc and self._proc.poll() is None:
            return {"ok": False, "message": "已有任务在进行中"}
        with self._lock:
            self._proc = subprocess.Popen(
                cmds,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        threading.Thread(target=self._pump, args=(self._proc,), daemon=True).start()
        return {"ok": True, "message": "任务已启动（后台执行，日志区看进度）"}

    def run_scan(self, out_dir: str, name: str = "pt-profile.json") -> dict:
        if not os.path.isdir(out_dir):
            return {"ok": False, "message": "输出目录不存在：%s" % out_dir}
        r = self._spawn([sys.executable, SCAN_SCRIPT, "--out", out_dir, "--name", name])
        if r.get("ok"):
            self._task_kind = "scan"
        return r

    def stop_task(self) -> dict:
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            return {"ok": True, "message": "已请求中止"}
        return {"ok": False, "message": "没有在跑的任务"}

    def _pump(self, proc: subprocess.Popen) -> None:
        import webview
        win = webview.windows[0] if webview.windows else None
        assert proc.stdout is not None
        for raw in proc.stdout:
            line = raw.rstrip()
            if not line or win is None:
                continue
            try:
                win.evaluate_js("window.__onTaskLine && window.__onTaskLine(%s, %r)"
                                % (json.dumps(_log_class(line)), line))
            except Exception:
                pass
        rc = proc.wait()
        if win:
            tail = "✓ 任务完成（exit %d）" % rc if rc == 0 else "✗ 任务退出（exit %d）" % rc
            try:
                win.evaluate_js("window.__onTaskLine && window.__onTaskLine(%s, %r)"
                                % (json.dumps("ok" if rc == 0 else "err"), tail))
            except Exception:
                pass
        # B2 补齐：真导出成功 → 后台质检本次落盘的 wav（T版同款语义）
        kind = self._task_kind
        self._task_kind = ""
        if kind == "export" and rc == 0 and self._qc_ctx:
            ctx = self._qc_ctx
            self._qc_ctx = None
            threading.Thread(target=self._qc_worker, args=(ctx,), daemon=True).start()

    # ---------- 导出（复用 core/naming.build_export_cmds） ----------

    def export_preview(self, params: dict) -> dict:
        try:
            return {"ok": True, "cmds": self._build_cmds(params, dry_run=True)}
        except Exception as exc:
            return {"ok": False, "message": str(exc)}

    def run_export(self, params: dict) -> dict:
        try:
            cmds = self._build_cmds(params, dry_run=False)
        except Exception as exc:
            return {"ok": False, "message": str(exc)}
        r = self._spawn(cmds)
        if r.get("ok"):
            self._task_kind = "export"
            # B2 补齐：真导出才挂质检上下文（T版 v1.5.0 口径：预演不触发）
            try:
                self._qc_ctx = {
                    "dir": params.get("out_dir", ""),
                    "since": time.time(),
                    "sr": int(params["sample_rate"]) if params.get("sample_rate") else None,
                    "bd": int(params["bit_depth"]) if params.get("bit_depth") else None,
                }
            except Exception:
                self._qc_ctx = None
        else:
            self._task_kind = ""
        return r

    def _build_cmds(self, p: dict, dry_run: bool) -> list:
        profile_path = p.get("profile_path", "")
        if not profile_path or not os.path.isfile(profile_path):
            raise ValueError("档案不存在：%s" % profile_path)
        profile = json.loads(open(profile_path, encoding="utf-8-sig").read())
        out = p.get("out_dir", "")
        if not out:
            raise ValueError("请先选择输出目录")
        os.makedirs(out, exist_ok=True)
        self._remember_out_dir(out)
        modes = [m for m in EXPORT_MODES if p.get("modes", {}).get(m)]
        if not modes:
            raise ValueError("请至少勾选一种导出模式（mix/bus/stem/track）")
        tracks = p.get("tracks") or []
        return build_export_cmds(
            self.resolver.venv_python,
            self.resolver.script("pt-exporter"),
            profile_path, profile,
            modes=modes,
            stem_aux=bool(p.get("stem_aux")),
            tracks=tracks if p.get("modes", {}).get("track") else [],
            stem_tracks=tracks if (p.get("modes", {}).get("stem") and tracks) else [],
            exclude_names=[x for x in (p.get("exclude_names") or []) if x],
            session=p.get("session", ""),
            out=out,
            start=p.get("start", ""),
            end=p.get("end", ""),
            sample_rate=p.get("sample_rate", ""),
            bit_depth=p.get("bit_depth", ""),
            fmt=p.get("fmt", ""),
            dry_run=dry_run,
            track_formats=p.get("track_formats") or {},
            exclude_empty=bool(p.get("exclude_empty")),
        )

    # ---------- 交付包（pt-clips 一步直出） ----------

    def deliver(self, pkg_dir: str) -> dict:
        if not pkg_dir:
            return {"ok": False, "message": "请先选择包输出目录"}
        os.makedirs(pkg_dir, exist_ok=True)
        self._remember_out_dir(pkg_dir)
        if not self.ptsl_status()["online"]:
            return {"ok": False, "message": "需要 Pro Tools 在线（PTSL 离线）——请先启动并加载工程"}
        cmds = [self.resolver.venv_python, self.resolver.script("pt-clips"),
                "--json-dir", os.path.join(pkg_dir, "_json"), "--pkg-dir", pkg_dir]
        r = self._spawn(cmds)
        if r.get("ok"):
            self._task_kind = "deliver"
        return r

    # ---------- B2 补齐：视频时长自动检测 / 导出质检 ----------

    def detect_videos(self, session_path: str, profile_path: str = "") -> dict:
        """工程目录树检索视频（T版 Q1 同款）。

        候选根链：.ptx 同级 → 父级 → 祖父级，逐个试到检出为止；
        检索脚本复用 T版技能 find_session_videos.py（同一份，零拷贝）。
        """
        try:
            script = os.path.join(os.path.dirname(self.resolver.script("pt-exporter")),
                                  "find_session_videos.py")
        except Exception:
            script = ""
        if not script or not os.path.isfile(script):
            return {"ok": False, "message": "未找到 find_session_videos.py（技能目录未就绪）"}
        sp = (session_path or "").strip()
        if not sp or not os.path.isfile(sp):
            return {"ok": False, "message": "请先填写工程会话（.ptx）路径——视频按它所在目录树检索"}
        roots: list = []
        seen: set = set()
        cur = os.path.dirname(os.path.abspath(sp))
        for _ in range(3):
            if cur and cur not in seen and os.path.isdir(cur):
                roots.append(cur)
                seen.add(cur)
            parent = os.path.dirname(cur)
            if not parent or parent == cur:
                break
            cur = parent
        for root in roots:
            try:
                p = subprocess.run(
                    [self.resolver.venv_python, script, "--dir", root,
                     "--profile", profile_path or ""],
                    capture_output=True, text=True, encoding="utf-8",
                    errors="replace", timeout=120,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                text = p.stdout or ""
            except Exception as exc:
                return {"ok": False, "message": "检索失败：%s" % exc}
            data = None
            try:
                data = json.loads(text[text.index("{"):text.rindex("}") + 1])
            except (ValueError, json.JSONDecodeError):
                data = None
            if (data or {}).get("videos"):
                return {"ok": True, "videos": data["videos"], "root": root}
        return {"ok": True, "videos": [], "root": ""}

    def _push_line(self, cls: str, text: str) -> None:
        """向前端日志区推一行（与 _pump 同通道）。"""
        import webview
        win = webview.windows[0] if webview.windows else None
        if not win:
            return
        try:
            win.evaluate_js("window.__onTaskLine && window.__onTaskLine(%s, %r)"
                            % (json.dumps(cls), text))
        except Exception:
            pass

    def _qc_worker(self, ctx: dict) -> None:
        """导出后自动质检（T版 v1.5.0 同款）：wav 头逐个核对。纯标准库。"""
        try:
            from ptools.core.qc import qc_wavs   # noqa: E402
        except Exception as exc:
            self._push_line("err", "质检模块不可用：%s" % exc)
            return
        self._push_line("info", "── 导出质检：核对本次落盘的 wav ──")
        try:
            checked, issues = qc_wavs(ctx.get("dir", ""), since_ts=ctx.get("since") or 0.0,
                                      expected_sr=ctx.get("sr"), expected_bd=ctx.get("bd"))
        except Exception as exc:
            self._push_line("err", "质检执行失败：%s" % exc)
            return
        LIMIT = 12
        for path, h in checked[:LIMIT]:
            self._push_line("info", "  ✓ %s（%s ch / %s Hz / %s bit / %.1f s）" % (
                os.path.basename(path), h.get("channels"), h.get("sample_rate"),
                h.get("bits"), h.get("duration_sec") or 0.0))
        if len(checked) > LIMIT:
            self._push_line("info", "  …其余 %d 个产物略" % (len(checked) - LIMIT))
        for path, reason in issues[:50]:
            self._push_line("err", "  ✗ %s：%s" % (os.path.basename(path), reason))
        if issues:
            self._push_line("err", "质检完成：%d 个通过，%d 个异常（导错了别当导对了）"
                            % (len(checked), len(issues)))
        else:
            self._push_line("ok", "✓ 质检完成：%d 个产物全部通过" % len(checked))
