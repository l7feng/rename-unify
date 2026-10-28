# -*- coding: utf-8 -*-
"""v4 阶段 C · 剪映工程工具包的 js_api 桥：HTML 前端 ↔ Python 核心（三页签）。

与 pt_api.py 的差异（30 号方案 §阶段 C）：
- pt-tools 复用 = 子进程 CLI；剪映复用 = **同进程函数直调**（gui.py 同款）：
  `import main`（main.py 是纯逻辑模块，无 tkinter 副作用，re-export 了
  load_config / videoname / pro_tools_status 全套）；
- 长任务（导入/导出/分离）= 后台线程 + ``contextlib.redirect_stdout`` 泵；
  重定向仅作用于任务线程，不影响 httpd / 壳自身日志；
- 分包缺视频项目名 = **两段式**：``export_phase1`` 返回 pending 清单 →
  前端渲染补录表单 → ``run_export(answers)`` 合并后执行
  （替代 tkinter 模态弹窗 ``videoname_dialog``）。

⚠️ 已知取舍：``import main`` 会把裸名 ``main`` / ``core`` 写进 sys.modules——
通用名，v4 自身不使用这两个名字，当前安全；未来引入同名模块时需改造为包导入。
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import traceback
from pathlib import Path

# --- 路径 ---
V4_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # src/v4
SRC_DIR = os.path.dirname(V4_DIR)
JY_CODE = os.path.join(SRC_DIR, "jianying-draft-toolkit", "code")       # code/（main.py 同层）
PT_ROOT = os.path.join(SRC_DIR, "pt-tools")                             # 家族级界面偏好复用 pt C2 层

for _p in (JY_CODE, PT_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ptools.core import config as ui_config   # noqa: E402  （界面偏好：theme/button_style）

_JY_LOCK = threading.Lock()
_JY = None


def _jy() -> dict:
    """懒加载剪映核心模块（首次调用才 import，失败信息可读）。"""
    global _JY
    with _JY_LOCK:
        if _JY is None:
            import main as jy_main          # noqa: E402  （剪映核心，非 v4 的 main）
            import import_audio as jy_imp   # noqa: E402
            import core.host as jy_host     # noqa: E402
            _JY = {"main": jy_main, "imp": jy_imp, "host": jy_host}
        return _JY


def _log_class(line: str) -> str:
    if re.search(r"\[错误\]|\[error\]|失败|Traceback|error", line, re.I):
        return "err"
    if re.search(r"✓|完成|成功|OK|done", line, re.I):
        return "ok"
    return ""


class _LineWriter:
    """redirect_stdout 的接收端：逐段推给前端（同 gui.py QueueWriter 语义）。"""

    def __init__(self, emit):
        self._emit = emit
        self._buf = ""

    def write(self, s: str) -> None:
        if not s:
            return
        self._buf += s
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if line.strip():
                self._emit(line.rstrip())

    def flush(self) -> None:
        if self._buf.strip():
            self._emit(self._buf.rstrip())
        self._buf = ""


from api.h_preferences import HPreferencesMixin


class JyApi(HPreferencesMixin):
    """暴露给 window.pywebview.api 的桥对象。方法名即 JS 侧调用名。"""

    def __init__(self) -> None:
        self._init_h_preferences("jy")
        self._task_lock = threading.Lock()
        self._busy = False
        self._demucs_cmd: list | None = None
        self._export_ctx: dict | None = None   # phase1 → run_export 的上下文

    # ---------- 界面偏好（家族级：与 pt-tools 共用 ptools C2 配置层） ----------

    def hello(self) -> dict:
        return {"ok": True, "app": "jy"}


    # ---------- 对话框 / 打开目录 ----------

    def pick_directory(self, title: str = "选择目录") -> str | None:
        import webview
        win = webview.windows[0] if webview.windows else None
        if win is None:
            return None
        result = win.create_file_dialog(webview.FOLDER_DIALOG)
        return result[0] if result else None

    def pick_file(self, title: str = "选择文件", kinds: str = "json") -> str | None:
        import webview
        win = webview.windows[0] if webview.windows else None
        if win is None:
            return None
        types = {
            "json": ("JSON 文件 (*.json)", "全部文件 (*.*)"),
            "audio": ("音频 (*.wav *.mp3 *.m4a *.flac)", "全部文件 (*.*)"),
            "ofx": ("OFX插件 (*.ofx)", "全部文件 (*.*)"),
        }.get(kinds, ("全部文件 (*.*)",))
        result = win.create_file_dialog(
            webview.OPEN_DIALOG, allow_multiple=False, file_types=types)
        return result[0] if result else None

    def open_path(self, path: str) -> dict:
        if path and (os.path.isdir(path) or os.path.isfile(path)):
            os.startfile(path)  # noqa: S606
            return {"ok": True}
        return {"ok": False, "message": "路径不存在：%s" % path}

    # ---------- OFX插件缓存管理 ----------

    def ofx_list(self) -> dict:
        try:
            from api.ofx_manager import OfxManager
            return OfxManager().list()
        except Exception as exc:
            return {"ok": False, "message": str(exc)}

    def ofx_install(self, source: str) -> dict:
        if self._busy:
            return {"ok": False, "message": "请先等待当前任务完成。"}
        try:
            from api.ofx_manager import OfxManager
            return OfxManager().install(source)
        except Exception as exc:
            return {"ok": False, "message": str(exc)}

    def ofx_delete(self, name: str, token: str) -> dict:
        if self._busy:
            return {"ok": False, "message": "请先等待当前任务完成。"}
        try:
            from api.ofx_manager import OfxManager
            return OfxManager().delete(name, token)
        except Exception as exc:
            return {"ok": False, "message": str(exc)}

    # ---------- 状态 ----------

    def pt_status(self) -> dict:
        """Pro Tools PTSL 探活（导入页前置条件，gui 同款 core.pro_tools_status）。"""
        try:
            ok, msg = _jy()["main"].pro_tools_status()
            return {"online": bool(ok), "message": msg}
        except Exception as exc:
            return {"online": False, "message": "探测失败：%s" % exc}

    def env_check(self) -> dict:
        """环境自检（main.check_environment：Python/ffmpeg/剪映/jy-draftc）。"""
        try:
            checks = _jy()["main"].check_environment()
            items = [{"name": k, "ok": bool(v[0]), "message": v[1]}
                     for k, v in checks.items()]
            return {"ok": all(i["ok"] for i in items), "items": items}
        except Exception as exc:
            return {"ok": False, "items": [], "message": str(exc)}

    # ---------- 任务基建（同进程线程 + stdout 泵） ----------

    def _emit(self, text: str, cls: str = "") -> None:
        """日志行 → 前端 __onJyLine；同时落 sys.__stdout__ 兜底（Edge/终端可见）。"""
        cls = cls or _log_class(text)
        try:
            print("[jy] %s" % text, file=sys.__stdout__, flush=True)
        except Exception:
            pass
        try:
            import webview
            win = webview.windows[0] if webview.windows else None
            if win is not None:
                win.evaluate_js("window.__onJyLine && window.__onJyLine(%s, %r)"
                                % (json.dumps(cls), text))
        except Exception:
            pass

    def _emit_event(self, name: str, value) -> None:
        try:
            import webview
            win = webview.windows[0] if webview.windows else None
            if win is not None:
                win.evaluate_js("window.__onJyEvent && window.__onJyEvent(%s, %s)"
                                % (json.dumps(name), json.dumps(value)))
        except Exception:
            pass

    def _run_bg(self, job, done_msg: str = "✓ 任务完成") -> dict:
        with self._task_lock:
            if self._busy:
                return {"ok": False, "message": "已有任务在进行中（看日志区）"}
            self._busy = True
        threading.Thread(target=self._worker, args=(job, done_msg), daemon=True).start()
        return {"ok": True, "message": "任务已启动（后台执行，日志区看进度）"}

    def _worker(self, job, done_msg: str) -> None:
        self._emit_event("busy", True)
        ok, tail = True, done_msg
        try:
            with contextlib.redirect_stdout(_LineWriter(self._emit)):
                job()
        except SystemExit as exc:          # import_audio CLI argparse 语义
            code = exc.code or 0
            ok = (code == 0)
            tail = "任务退出（code %s）" % code
        except Exception as exc:
            ok = False
            tail = "✗ 任务异常：%s" % exc
            self._emit(traceback.format_exc(limit=6), "err")
        finally:
            self._busy = False
            self._emit(tail, "ok" if ok else "err")
            self._emit_event("busy", False)
            self._emit_event("done", {"ok": ok, "tail": tail})

    # ---------- 导入页（PT 交付包 → 剪映草稿） ----------

    def preview_import(self, jp: str, draft: str) -> dict:
        """预演：解析 pt-clips.json，报轨道清单（只读不写）。"""
        try:
            jy = _jy()
            jp, draft = Path(jp), Path(draft)
            if not jp.is_file():
                return {"ok": False, "message": "pt-clips.json 不存在：%s" % jp}
            if not draft.is_dir():
                return {"ok": False, "message": "草稿目录不存在：%s" % draft}
            rows = jy["main"].parse_pt_clips(jp, tuple(jy["imp"].DEFAULT_EXCLUDE))
            tracks = jy["imp"].list_track_names(jp)
            return {"ok": True, "rows": len(rows), "tracks": tracks[:200],
                    "message": "解析到 %d 行 / %d 轨：%s"
                               % (len(rows), len(tracks), "、".join(tracks[:6]))}
        except Exception as exc:
            return {"ok": False, "message": "解析失败：%s" % exc}

    def run_import(self, jp: str, draft: str, only: str = "",
                   keep_aux: bool = False) -> dict:
        """执行导入：argv 伪装 CLI（gui.ImportTab 同款）+ 后台线程。"""
        jpp, ddp = Path(jp or ""), Path(draft or "")
        if not jpp.is_file():
            return {"ok": False, "message": "pt-clips.json 不存在：%s" % jp}
        if not ddp.is_dir():
            return {"ok": False, "message": "草稿目录不存在：%s" % draft}

        def job():
            jy = _jy()
            argv = ["import_audio.py", "--pt-clips", str(jpp), str(ddp)]
            if only.strip():
                argv += ["--only", only.strip()]
            if keep_aux:
                argv += ["--keep-aux"]
            old = sys.argv
            sys.argv = argv
            try:
                jy["imp"].main()
            finally:
                sys.argv = old

        return self._run_bg(job, "✓ 导入完成")

    # ---------- 导出页（剪映草稿 → 音频切片） ----------

    _CFG_KEYS_STR = ("input_dir", "output_dir", "audio_format", "conflict",
                     "clip_type_override", "remarks", "track_name_template",
                     "track_spec", "aaf_media_mode", "split_folder_template",
                     "sep_input", "sep_output", "sep_stems")
    _CFG_KEYS_BOOL = ("dedupe", "extract_video_tracks", "skip_existing",
                      "export_aaf", "split_by_video", "export_subtitles")

    def _load_cfg(self, jy: dict) -> dict:
        """读配置（gui 同款语义：DEFAULT_CONFIG 打底，文件值覆盖）。"""
        return {**jy["main"].DEFAULT_CONFIG,
                **jy["main"].load_config(jy["main"].CONFIG_PATH)}

    def _merge_export_cfg(self, jy: dict, params: dict) -> dict:
        """前端表单 → cfg dict（白名单 merge + 枚举校验 + 落盘）。

        校验语义对齐 ExportTab._read_spec/_read_conflict：非法值**显式报错**，
        绝不静默回落默认（v2.6.2 教训）。
        """
        cfg = self._load_cfg(jy)
        for k in self._CFG_KEYS_STR:
            if k in params and params[k] is not None:
                cfg[k] = str(params[k]).strip()
        for k in self._CFG_KEYS_BOOL:
            if k in params and params[k] is not None:
                cfg[k] = bool(params[k])
        if "bitrate_kbps" in params:
            try:
                cfg["bitrate_kbps"] = int(params["bitrate_kbps"])
            except (TypeError, ValueError):
                raise ValueError("码率必须是数字：%r" % params["bitrate_kbps"])
        modes = [m for m in ("tracks", "clips")
                 if (params.get("modes") or {}).get(m)]
        if modes:
            cfg["export_mode"] = modes
        elif isinstance(cfg.get("export_mode"), str):
            cfg["export_mode"] = [cfg["export_mode"]]
        if params.get("track_spec"):
            spec = str(params["track_spec"])
            if spec not in jy["main"].SPEC_PRESETS:
                raise ValueError("「整轨规格」值非法：%r（请从下拉重选）" % spec)
            cfg["track_spec"] = spec
        if params.get("conflict"):
            if params["conflict"] not in ("rename", "cover", "skip"):
                raise ValueError("「重名策略」值非法：%r" % params["conflict"])
        if params.get("aaf_media_mode"):
            if params["aaf_media_mode"] not in ("media", "embed"):
                raise ValueError("「交付方式」值非法：%r" % params["aaf_media_mode"])
        if params.get("name_templates_active") is not None:
            active = [t for t in (params["name_templates_active"] or []) if t]
            if active:
                cfg["name_templates_active"] = active
                cfg["name_template"] = active[0]   # 兼容旧字段 / CLI
        jy["main"].save_config(cfg)
        return cfg

    def get_export_config(self) -> dict:
        """当前剪映配置 → 前端表单回显。"""
        jy = _jy()
        cfg = self._load_cfg(jy)
        out = {k: cfg.get(k) for k in (
            "input_dir", "output_dir", "audio_format", "bitrate_kbps", "conflict",
            "clip_type_override", "dedupe", "extract_video_tracks", "skip_existing",
            "remarks", "track_name_template", "track_spec", "export_aaf",
            "aaf_media_mode", "split_by_video", "split_folder_template",
            "export_subtitles", "sep_input", "sep_output", "sep_stems",
            "name_templates", "name_templates_active")}
        em = cfg.get("export_mode", "tracks")
        out["modes"] = {"tracks": "tracks" in (em if isinstance(em, list) else [em]),
                        "clips": "clips" in (em if isinstance(em, list) else [em])}
        out["spec_options"] = [{"key": k, "label": v[0]}
                               for k, v in jy["main"].SPEC_PRESETS.items()]
        out["default_draft_root"] = str(jy["main"].DEFAULT_JIANYING_DRAFT_ROOT)
        return {"ok": True, "cfg": out}

    def export_phase1(self, params: dict) -> dict:
        """阶段 1（后台）：cfg 落盘 + 解析输入 + 分包视频名扫描。

        返回 pending 非空时，前端须先渲染补录表单、把答案交给 run_export。
        params.extra_paths：逐行文件路径（等价 tkinter 拖拽的 dropped_paths）。
        """
        try:
            jy = _jy()
            cfg = self._merge_export_cfg(jy, params)
        except Exception as exc:
            return {"ok": False, "message": str(exc)}
        root_str = (params.get("input_dir") or "").strip()
        extra = [Path(p.strip()) for p in (params.get("extra_paths") or [])
                 if p and p.strip()]
        split_by_video = bool(cfg.get("split_by_video"))

        def job():
            root = Path(root_str) if root_str else Path(jy["main"].DEFAULT_JIANYING_DRAFT_ROOT)
            drafts, media, file_mode = [], [], False
            if extra:
                found, r2, fm = jy["main"].resolve_input_paths(extra)
                file_mode = bool(fm)
                drafts = found
                root = r2 if (r2 is not None and str(r2)) else root
                if file_mode:                     # gui 同款：file_mode 即按媒体文件处理
                    media = [p for p in extra
                             if p.is_file() and jy["main"].media_kind(p)]
                    for p in extra:
                        if p.is_dir():
                            media.extend(f for f in p.rglob("*")
                                         if f.is_file() and jy["main"].media_kind(f))
            else:
                if root_str:
                    found, _, _ = jy["main"].resolve_input_paths([root])
                    drafts = found

            pending, suggest = [], ""
            if split_by_video:
                answers = cfg.get("video_project_answers") or {}
                pending, suggest = self._scan_video_names(jy, root, drafts, answers)

            self._export_ctx = {"cfg": cfg, "root": root, "drafts": drafts,
                                "media": media, "pending_keys": [p["key"] for p in pending]}
            self._emit("解析完成：%d 个草稿 ｜ 媒体文件模式：%s"
                       % (len(drafts), "是（%d 文件）" % len(media) if file_mode else "否"))
            for d in drafts[:20]:
                self._emit("    · 草稿 %s" % d.name)
            self._emit_event("phase1", {
                "ok": True, "root": str(root), "draft_count": len(drafts),
                "file_mode": file_mode, "media_count": len(media),
                "pending": pending, "suggest": suggest,
                "has_pending": bool(pending)})

        return self._run_bg(job, "✓ 输入解析完成")

    def _scan_video_names(self, jy: dict, root, drafts, answers) -> tuple:
        """分包视频名扫描（main.videoname 三件套，逻辑对齐 ExportTab._scan_video_names）。"""
        names = []
        dirs = list(drafts or [])
        if not dirs and root:
            try:
                dirs = jy["main"].scan_drafts(Path(root))
            except Exception as exc:
                self._emit("  [warn] 扫描草稿失败：%s" % exc)
        for i, d in enumerate(dirs, 1):
            try:
                self._emit("  · 解析视频名（%d/%d）：%s" % (i, len(dirs), d.name))
                raw = jy["main"].resolve_draft_content_file(Path(d))
                dec = jy["main"].decrypt_draft_file(raw)
                for ch in jy["main"].parse_video_chunks(Path(d), dec):
                    if ch.material_name:
                        names.append(ch.material_name)
            except Exception as exc:
                self._emit("  [warn] 视频名解析失败（%s）：%s" % (Path(d).name, exc))
        if not names:
            return [], ""
        infos = jy["main"].apply_project(jy["main"].parse_many(names), answers or {})
        pend = jy["main"].pending_map(infos)
        sugg = jy["main"].suggest_project(infos) or ""
        return [{"key": k, "raw": v.raw, "reason": v.reason, "suggest": v.suggest}
                for k, v in pend.items()], sugg

    def run_export(self, answers: dict = None) -> dict:
        """阶段 2：合并视频项目名答案 → 后台 execute_export。

        有 pending 而未补全 → 返回 need_answers=True（前端保持表单）。
        """
        ctx = self._export_ctx
        if not ctx:
            return {"ok": False, "message": "请先点「解析输入」（阶段 1）"}
        jy = _jy()
        cfg = dict(ctx["cfg"])
        if ctx["pending_keys"]:
            merged = dict(cfg.get("video_project_answers") or {})
            for k, v in (answers or {}).items():
                if str(v or "").strip():
                    merged[k] = str(v).strip()
            missing = [k for k in ctx["pending_keys"] if not merged.get(k)]
            if missing:
                return {"ok": False, "need_answers": True,
                        "missing": missing,
                        "message": "还有 %d 个视频项目名未补录：%s"
                                   % (len(missing), "、".join(missing[:5]))}
            cfg["video_project_answers"] = merged
            cfg["split_by_video"] = True
            try:
                jy["main"].save_config(cfg)    # 快照与共享配置各一份（gui 同款）
            except Exception:
                pass
        root, drafts, media = ctx["root"], ctx["drafts"], ctx["media"]

        def job():
            stats = jy["main"].execute_export(cfg, Path(root),
                                              draft_dirs=drafts, media_files=media)
            self._emit("✓ 导出完成：成功 %s ｜ 失败 %s ｜ 跳过 %s"
                       % (stats.get("success", 0), stats.get("failed", 0),
                          stats.get("skipped", 0)))

        return self._run_bg(job, "✓ 导出完成")

    # ---------- 分离页（Demucs） ----------

    def check_demucs(self) -> dict:
        """demucs 可用性检测（同 SeparationTab：PATH 命令优先，非冻结再探 -m）。"""
        exe = shutil.which("demucs")
        if exe:
            self._demucs_cmd = [exe]
            return {"ok": True, "via": "PATH", "cmd": exe}
        if not getattr(sys, "frozen", False):
            try:
                r = subprocess.run(
                    [sys.executable, "-c",
                     "import demucs; print(getattr(demucs, '__version__', ''))"],
                    capture_output=True, text=True, timeout=20)
                if r.returncode == 0:
                    self._demucs_cmd = [sys.executable, "-m", "demucs"]
                    return {"ok": True, "via": "python",
                            "ver": (r.stdout or "").strip()}
            except Exception:
                pass
        self._demucs_cmd = None
        return {"ok": False,
                "message": "Demucs 未安装——请运行 pip install demucs 后重新检测"}

    def run_separation(self, inp: str, out: str, stems: str = "vocals") -> dict:
        """执行人声分离（demucs 子进程逐文件，gui._run_demucs 同逻辑）。"""
        inp = (inp or "").strip()
        out = (out or "").strip()
        if not self._demucs_cmd:
            return {"ok": False, "message": "Demucs 未就绪，请先「重新检测」"}
        if not inp or not Path(inp).exists():
            return {"ok": False, "message": "请选择要分离的音频文件或目录"}
        if not out:
            out = str(Path(inp).parent / "separated")
        Path(out).mkdir(parents=True, exist_ok=True)
        try:
            jy = _jy()
            cfg = self._load_cfg(jy)
            cfg.update({"sep_input": inp, "sep_output": out, "sep_stems": stems})
            jy["main"].save_config(cfg)
        except Exception:
            pass

        def job():
            p = Path(inp)
            if p.is_dir():
                files = [str(x) for x in p.iterdir()
                         if x.suffix.lower() in (".wav", ".mp3", ".m4a", ".flac")]
            else:
                files = [inp]
            if not files:
                self._emit("[错误] 没找到音频文件", "err")
                return
            self._emit("[信息] 共 %d 个文件，输出到 %s" % (len(files), out))
            for i, f in enumerate(files, 1):
                self._emit("[%d/%d] %s" % (i, len(files), Path(f).name))
                cmd = list(self._demucs_cmd) + ["-o", out]
                if stems == "vocals":
                    cmd.append("--two-stems=vocals")
                cmd.append(f)
                self._emit("  $ " + " ".join(cmd))
                r = subprocess.run(cmd)
                self._emit("  [失败] 返回码 %s" % r.returncode if r.returncode
                           else "  [完成]", "" if r.returncode else "ok")
            self._emit("[全部完成] 产物在: %s" % out)

        return self._run_bg(job, "✓ 分离完成")
