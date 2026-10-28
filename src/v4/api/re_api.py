# -*- coding: utf-8 -*-
"""v4 阶段 D · rename-unify 的 js_api 桥：HTML 前端 ↔ Python 核心（五页签）。

复用通道（30 号方案 §阶段 D）＝**同进程函数直调**（与 jy_api 同款）：
- `import core_rules`（规则引擎：identify/make_plan/apply_plan/undo 链，零 tkinter）；
- `import foldertree`（工程建树：parse_episodes/plan_creation/apply_plan，零 tkinter）；
- `import config`（load_config()/save_config(cfg)，无参形态）。
⚠️ 裸名冲突核查：剪映线占用 `main`/`core`/`core.config`；rename 线只用
`core_rules`/`foldertree`/`config` 三个裸名，互不相撞；rename 的 `main.py`
（GUI 层）**永不 import**。

两阶段安全闸保真（core 零改动）：
- make_plan 状态机：''(待处理)/skip/error/conflict/excluded；
- apply_plan 两阶段提交 + 回溯日志 rename_log_*.csv；
- 执行前审计快照 rename_audit_*.json（覆盖执行到一半崩了的场景）；
- 撤销 undo_from_log / undo_from_rows（原,新列序，倒序防交叉）。
"""
from __future__ import annotations

import csv
import datetime
import json
import os
import re
import sys
import threading

# --- 路径 ---
V4_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # src/v4
SRC_DIR = os.path.dirname(V4_DIR)
RE_CODE = os.path.join(SRC_DIR, "rename-unify", "code")
PT_ROOT = os.path.join(SRC_DIR, "pt-tools")                             # 家族级界面偏好

for _p in (RE_CODE, PT_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ptools.core import config as ui_config   # noqa: E402  （界面偏好：theme/button_style）

_RE_LOCK = threading.Lock()
_RE = None


def _re() -> dict:
    """懒加载 rename-unify 核心模块。"""
    global _RE
    with _RE_LOCK:
        if _RE is None:
            import core_rules as re_core   # noqa: E402
            import foldertree as re_ft     # noqa: E402
            import config as re_cfg        # noqa: E402  （rename 的 config，非剪映）
            _RE = {"core": re_core, "ft": re_ft, "cfg": re_cfg}
        return _RE


def _log_class(line: str) -> str:
    if re.search(r"失败|错误|Traceback|error|\[✗\]", line, re.I):
        return "err"
    if re.search(r"✓|完成|成功|OK|done", line, re.I):
        return "ok"
    return ""


def _item_dict(i) -> dict:
    return {"src": i.src, "dst": i.dst, "target": i.target, "info": i.info,
            "ep": i.ep, "status": i.status, "note": i.note,
            "new_dir": bool(i.new_dir)}


from api.h_preferences import HPreferencesMixin


class ReApi(HPreferencesMixin):
    """暴露给 window.pywebview.api 的桥对象。方法名即 JS 侧调用名。"""

    def __init__(self) -> None:
        self._init_h_preferences("re")
        self._task_lock = threading.Lock()
        self._busy = False
        self._plan_ctx = None      # plan → apply 的计划上下文（前端持有 items 亦可）

    # ---------- 界面偏好（家族级：与 pt-tools 共用 ptools C2 配置层） ----------

    def hello(self) -> dict:
        return {"ok": True, "app": "re"}


    # ---------- 对话框 / 打开目录 ----------

    def pick_directory(self, title: str = "选择目录", current: str = "", key: str = "") -> str | None:
        import webview
        win = webview.windows[0] if webview.windows else None
        if win is None:
            return None
        result = win.create_file_dialog(webview.FOLDER_DIALOG, directory=self._dialog_directory(current, key or title))
        return self._remember_dialog(result, key or title, folder=True)

    def pick_file(self, title: str = "选择文件", kinds: str = "csv", current: str = "", key: str = "") -> str | None:
        import webview
        win = webview.windows[0] if webview.windows else None
        if win is None:
            return None
        types = {
            "csv": ("回溯日志 (*.csv)", "全部文件 (*.*)"),
            "json": ("审计文件 (*.json)", "全部文件 (*.*)"),
        }.get(kinds, ("全部文件 (*.*)",))
        result = win.create_file_dialog(
            webview.OPEN_DIALOG, directory=self._dialog_directory(current, key or kinds), allow_multiple=False, file_types=types)
        return self._remember_dialog(result, key or kinds, folder=False)

    def open_path(self, path: str) -> dict:
        if path and (os.path.isdir(path) or os.path.isfile(path)):
            os.startfile(path)  # noqa: S606
            return {"ok": True}
        return {"ok": False, "message": "路径不存在：%s" % path}

    # ---------- 日志/事件泵 ----------

    def _emit(self, text: str, cls: str = "") -> None:
        cls = cls or _log_class(text)
        try:
            print("[re] %s" % text, file=sys.__stdout__, flush=True)
        except Exception:
            pass
        try:
            import webview
            win = webview.windows[0] if webview.windows else None
            if win is not None:
                win.evaluate_js("window.__onReLine && window.__onReLine(%s, %r)"
                                % (json.dumps(cls), text))
        except Exception:
            pass

    def _emit_event(self, name: str, value) -> None:
        try:
            import webview
            win = webview.windows[0] if webview.windows else None
            if win is not None:
                win.evaluate_js("window.__onReEvent && window.__onReEvent(%s, %s)"
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
            result = job()
            if isinstance(result, dict):
                ok = bool(result.get("ok", True))
                tail = result.get("tail") or (done_msg if ok else "✗ 任务失败")
        except Exception as exc:
            ok = False
            tail = "✗ 任务异常：%s" % exc
            self._emit(tail, "err")
        finally:
            self._busy = False
            self._emit_event("busy", False)
            self._emit_event("done", {"ok": ok, "tail": tail})

    # ---------- 配置读写（页1/页2） ----------

    def get_config(self) -> dict:
        r = _re()
        cfg = r["cfg"].load_config()
        keys = ("last_root", "recursive", "exts", "template", "fields",
                "rules", "templates", "targets", "date_from_mtime",
                "rename_ep_dirs", "rename_files", "group_master", "rename_subtracks", "ep_dir_template", "foldertree")
        out = {k: cfg.get(k) for k in keys}
        c = r["core"]
        return {"ok": True, "cfg": out,
                "defaults": {"templates": c.DEFAULT_TEMPLATES,
                             "targets": c.DEFAULT_TARGETS, "rules": c.DEFAULT_RULES}}

    _CFG_KEYS = ("last_root", "recursive", "exts", "template", "fields",
                 "rules", "templates", "targets", "date_from_mtime",
                 "rename_ep_dirs", "rename_files", "group_master", "rename_subtracks", "ep_dir_template", "foldertree")

    def save_config_patch(self, patch: dict) -> dict:
        r = _re()
        cfg = r["cfg"].load_config()
        for k in self._CFG_KEYS:
            if k in patch and patch[k] is not None:
                cfg[k] = patch[k]
        try:
            r["cfg"].save_config(cfg)
            return {"ok": True, "message": "配置已保存"}
        except Exception as exc:
            return {"ok": False, "message": "保存失败：%s" % exc}

    # ---------- 页3：计划 / 手动分类 / 执行 ----------

    @staticmethod
    def _parse_exts(raw: str):
        parts = (raw or "").replace(",", " ").split()
        return tuple(e if e.startswith(".") else "." + e for e in parts) or None

    def plan(self, params: dict) -> dict:
        """扫描 + 生成计划（后台）。targets/rules 缺省读 cfg；前端可传当前编辑态覆盖。"""
        r = _re()
        root = (params.get("root") or "").strip()
        if not root or not os.path.isdir(root):
            return {"ok": False, "message": "目标目录不存在：%s" % (root or "（空）")}
        cfg = r["cfg"].load_config()
        template = (params.get("template") or "").strip() or cfg.get("template", "")
        fields = params.get("fields") or cfg.get("fields") or {}
        targets = params.get("targets")
        if targets is None:
            targets = cfg.get("targets") or []
        rules = params.get("rules")
        if rules is None:
            rules = cfg.get("rules") or []
        recursive = bool(params.get("recursive", cfg.get("recursive", True)))
        exts = self._parse_exts(params.get("exts") or cfg.get("exts", ""))
        date_from_mtime = bool(params.get("date_from_mtime",
                                          cfg.get("date_from_mtime", True)))
        rename_ep_dirs = bool(params.get("rename_ep_dirs",
                                         cfg.get("rename_ep_dirs", True)))
        rename_files = bool(params.get("rename_files", cfg.get("rename_files", False)))
        group_master = bool(params.get("group_master", cfg.get("group_master", True)))
        rename_subtracks = bool(params.get("rename_subtracks", cfg.get("rename_subtracks", True)))
        ep_dir_template = str(params.get("ep_dir_template", cfg.get("ep_dir_template", "{集数}")))
        paths_arg = params.get("paths")
        if paths_arg:
            paths = [os.path.abspath(p) for p in paths_arg
                     if p and os.path.isfile(p)]
        else:
            paths = r["core"].scan_dir(root, recursive=recursive, exts=exts)
        if not paths:
            return {"ok": True, "items": [], "stats": {}, "count": 0,
                    "message": "扫描到 0 个音频文件（检查扩展名/递归开关）"}

        def job():
            self._emit("扫描 %s：%d 个文件，生成计划中…" % (root, len(paths)))
            items, stats = r["core"].make_plan(
                paths, template, rules, fields, targets=targets, root=root,
                date_from_mtime=date_from_mtime, rename_ep_dirs=rename_ep_dirs,
                rename_files=rename_files, ep_dir_template=ep_dir_template, group_master=group_master, rename_subtracks=rename_subtracks)
            self._plan_ctx = {"root": root, "template": template, "fields": fields,
                              "targets": targets, "rules": rules,
                              "rename_ep_dirs": rename_ep_dirs, "rename_files": rename_files, "group_master": group_master, "rename_subtracks": rename_subtracks, "ep_dir_template": ep_dir_template}
            err_n = stats.get("error", 0) + stats.get("conflict", 0)
            self._emit("计划完成：待处理 %s ｜ 跳过 %s ｜ 错误 %s ｜ 冲突 %s ｜ 排除 %s"
                       % (stats.get("rename", 0), stats.get("skip", 0), stats.get("error", 0),
                          stats.get("conflict", 0), stats.get("excluded", 0)),
                       "err" if err_n else "ok")
            self._emit_event("plan", {
                "items": [_item_dict(i) for i in items[:800]],
                "total": len(items), "stats": stats})

        return self._run_bg(job, "✓ 计划生成完成")

    def manual_replan(self, params: dict) -> dict:
        """人工分类单文件重算（同步、快）——与自动流程同一套落点/渲染逻辑。"""
        r = _re()
        p = params.get("path") or ""
        if not p or not os.path.isfile(p):
            return {"ok": False, "message": "文件不存在：%s" % p}
        ctx = self._plan_ctx or {}
        template = params.get("template") or ctx.get("template") or ""
        fields = params.get("fields") or ctx.get("fields") or {}
        targets = params.get("targets")
        if targets is None:
            targets = ctx.get("targets") or []
        root = params.get("root") or ctx.get("root") or None
        try:
            item = r["core"].manual_plan_item(
                p, str(params.get("ep") or ""), str(params.get("target") or ""),
                str(params.get("info") or ""), template, fields, root=root,
                targets=targets,
                rename_ep_dirs=bool(params.get("rename_ep_dirs",
                                               ctx.get("rename_ep_dirs", True))),
                rename_files=bool(params.get("rename_files", ctx.get("rename_files", False))),
                ep_dir_template=params.get("ep_dir_template", ctx.get("ep_dir_template", "{集数}")),
                group_master=bool(params.get("group_master", ctx.get("group_master", True))),
                rename_subtracks=bool(params.get("rename_subtracks", ctx.get("rename_subtracks", True))))
            return {"ok": True, "item": _item_dict(item)}
        except Exception as exc:
            return {"ok": False, "message": "重算失败：%s" % exc}

    def apply(self, items: list, root: str = "") -> dict:
        """执行改名（后台）：审计快照 → 两阶段提交 apply_plan → 空目录报告。"""
        r = _re()
        todo = []
        for d in (items or []):
            if not d or not d.get("src") or not d.get("dst"):
                continue
            it = r["core"].PlanItem(d["src"], d["dst"],
                                    d.get("target", ""), d.get("info", ""),
                                    d.get("ep", ""), status="",
                                    note=d.get("note", ""),
                                    new_dir=bool(d.get("new_dir")))
            todo.append(it)
        if not todo:
            return {"ok": False, "message": "计划里没有「待改名」的文件"}
        base = os.path.dirname(os.path.abspath(todo[0].src)) or "."

        def job():
            # 审计快照（执行前；写失败只告警不阻断——与 GUI 同语义）
            audit_path = None
            rows = [[os.path.abspath(i.src), os.path.abspath(i.dst)] for i in todo]
            apath = os.path.join(base, "rename_audit_%s.json"
                                 % datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
            try:
                r["core"].write_audit(apath, rows,
                                      {"count": len(rows), "root": root or ""})
                audit_path = apath
                self._emit("审计快照：%s" % apath)
            except Exception as exc:
                self._emit("  警告: 审计文件写入失败 (%s)" % exc, "err")

            self._emit("=== 开始执行：待处理 %d ===" % len(todo))
            done, failed, log_path = r["core"].apply_plan(todo, write_log=True, progress=self._emit)
            for s, d2, why in failed[:20]:
                self._emit("  ✗ %s → %s：%s" % (os.path.basename(s),
                                                os.path.basename(d2), why), "err")
            self._emit("=== 执行结束：成功 %d ｜ 失败 %d ===" % (len(done), len(failed)),
                       "ok" if not failed else "err")
            emptied = r["core"].list_emptied_dirs(todo)
            if emptied:
                self._emit("提示：%d 个源集目录已空（只报告不删除，可自行回收）" % len(emptied))
            self._emit_event("applied", {
                "done": len(done), "failed": len(failed),
                "log_path": log_path, "audit_path": audit_path,
                "emptied": emptied[:50]})
            return {"ok": not failed, "tail": "✓ 重命名及分组完成" if not failed else "✗ 重命名/分组失败，请查看回退日志"}

        return self._run_bg(job, "✓ 改名执行完成")

    # ---------- 页4：回溯与撤销 ----------

    @staticmethod
    def _walk_find(root: str, prefix: str, suffix: str) -> list:
        found = []
        for dp, _dn, fns in os.walk(root):
            for fn in fns:
                if fn.lower().startswith(prefix) and fn.lower().endswith(suffix):
                    p = os.path.join(dp, fn)
                    try:
                        st = os.stat(p)
                        found.append({"path": p, "file": fn,
                                      "mtime": datetime.datetime.fromtimestamp(
                                          st.st_mtime).strftime("%Y-%m-%d %H:%M"),
                                      "size_kb": round(st.st_size / 1024, 1)})
                    except OSError:
                        continue
        found.sort(key=lambda x: x["mtime"], reverse=True)
        return found

    def list_logs(self, root: str) -> dict:
        if not root or not os.path.isdir(root):
            return {"ok": False, "message": "目录无效，请先在「预览与执行」页选择目标目录"}
        logs = self._walk_find(root, "rename_log_", ".csv")
        return {"ok": True, "items": logs[:200],
                "message": "找到 %d 份回溯日志" % len(logs)}

    def list_audits(self, root: str) -> dict:
        if not root or not os.path.isdir(root):
            return {"ok": False, "message": "目录无效，请先在「预览与执行」页选择目标目录"}
        audits = self._walk_find(root, "rename_audit_", ".json")
        return {"ok": True, "items": audits[:200],
                "message": "找到 %d 份审计快照" % len(audits)}

    def preview_log(self, path: str) -> dict:
        try:
            with open(path, "r", encoding="utf-8-sig", newline="") as fp:
                rows = list(csv.reader(fp))
        except OSError as exc:
            return {"ok": False, "message": "读取失败：%s" % exc}
        header = rows[0] if rows else []
        body = rows[1:] if rows and header[:1] == ["原文件"] else rows
        return {"ok": True, "total": len(body),
                "rows": [r[:2] for r in body[:200]]}

    def undo_log(self, path: str, dry_run: bool = False) -> dict:
        return self._undo_core(lambda: _re()["core"].undo_from_log(path, dry_run=dry_run),
                               ("dry-run 演练" if dry_run else "撤销"), path)

    def undo_audit(self, path: str, dry_run: bool = False) -> dict:
        def job_rows():
            rows, _meta = _re()["core"].load_audit(path)
            return _re()["core"].undo_from_rows(rows, dry_run=dry_run)
        return self._undo_core(job_rows,
                               ("审计 dry-run 演练" if dry_run else "按审计撤销"), path)

    def _undo_core(self, fn, label: str, path: str) -> dict:
        r = _re()

        def job():
            self._emit("=== %s：%s ===" % (label, path))
            done, failed = fn()
            for new_p, old_p, why in failed[:20]:
                self._emit("  ✗ %s → %s：%s" % (os.path.basename(new_p),
                                                os.path.basename(old_p), why), "err")
            self._emit("=== %s结束：成功 %d ｜ 失败 %d ===" % (label, len(done), len(failed)),
                       "ok" if not failed else "err")
            self._emit_event("undo", {"done": len(done), "failed": len(failed)})

        return self._run_bg(job, "✓ %s完成" % label)

    # ---------- 页5：工程文件夹建树 ----------

    def ft_form(self) -> dict:
        r = _re()
        cfg = r["cfg"].load_config()
        ft = dict(cfg.get("foldertree") or {})
        ft["template_root"] = r["ft"].normalize_template_root(ft.get("template_root", ""))
        return {"ok": True, "form": ft,
                "ptx_modes": [{"key": k, "label": lb} for k, lb in r["ft"].PTX_MODES],
                "ep_namings": [
                    {"key": "name_num", "label": "项目名+集数（默认）"},
                    {"key": "num", "label": "纯数字"},
                    {"key": "name_level_num", "label": "项目名+等级+集数"}]}

    @staticmethod
    def _ft_args(params: dict, ft: dict) -> dict:
        g = lambda k: str(params.get(k, ft.get(k, "")) or "").strip()
        return {"name": g("name"), "seq": g("seq"), "level": g("level"),
                "date": g("date"), "user": g("user"), "eps_text": g("eps"),
                "output_root": g("output_root"),
                "template_root": _re()["ft"].normalize_template_root(g("template_root")),
                "ptx_mode": g("ptx_mode") or "原样复制",
                "ep_naming": g("ep_naming") or "name_num",
                "episode_template": g("episode_template") or "{片名} {集数}集",
                "episode_padding": int(params.get("episode_padding", ft.get("episode_padding", 0)) or 0),
                "project_template": g("project_template") or "{片名}{等级}_{日期}_{用户}"}

    def ft_plan(self, params: dict) -> dict:
        """规划（只算不写）：项目根 + 目录树预览文本 + 警告。"""
        r = _re()
        ft = (r["cfg"].load_config().get("foldertree") or {})
        a = self._ft_args(params, ft)
        eps, errs = r["ft"].parse_episodes(a["eps_text"])
        if errs or not eps:
            message = "集数输入无效，未生成建立计划：" + "；".join(errs or ["没有有效集数"])
            return {"ok": False, "message": message, "preview": message, "eps": eps, "steps": 0}
        project_root, steps, warns, ep_names = r["ft"].plan_creation(
            eps, a["name"], a["seq"], a["level"], a["date"], a["user"],
            a["output_root"], a["template_root"],
            ptx_mode=a["ptx_mode"], ep_naming=a["ep_naming"],
            episode_template=a["episode_template"], episode_padding=a["episode_padding"], project_template=a["project_template"])
        source = r["ft"].locate_template_ptx(a["template_root"]) if a["ptx_mode"] != "none" else None
        lines = ["模板根: %s" % a["template_root"], "工程文件模板: %s" % (source or "不复制/未找到"), "项目根: %s" % project_root]
        lines.extend("⚠ %s" % w for w in warns)
        lines.extend("⚠ 集数解析: %s" % e for e in errs)
        if not eps:
            lines.append("(无有效集数，仅建立分类目录)")
        lines.append("")
        lines.append(r["ft"].plan_tree_text(project_root, steps, ep_names))
        return {"ok": True, "project_root": project_root,
                "steps": len(steps), "eps": eps,
                "preview": "\n".join(lines),
                "example": os.path.basename(project_root)}

    def ft_precheck(self, params: dict) -> dict:
        r = _re()
        ft = (r["cfg"].load_config().get("foldertree") or {})
        a = self._ft_args(params, ft)
        eps, errs = r["ft"].parse_episodes(a["eps_text"])
        project_root, steps, _warns, _ep_names = r["ft"].plan_creation(
            eps, a["name"], a["seq"], a["level"], a["date"], a["user"],
            a["output_root"], a["template_root"],
            ptx_mode=a["ptx_mode"], ep_naming=a["ep_naming"],
            episode_template=a["episode_template"], episode_padding=a["episode_padding"], project_template=a["project_template"])
        problems = list(errs)
        if not eps and not problems:
            problems.append("没有有效集数")
        problems.extend(r["ft"].precheck_build(a["template_root"], a["output_root"],
                                          project_root, a["ptx_mode"]))
        return {"ok": True, "problems": problems, "steps": len(steps)}

    def ft_build(self, params: dict) -> dict:
        """建立（后台）：预检 → locate_template_ptx → FT.apply_plan。"""
        r = _re()
        ft = dict((r["cfg"].load_config().get("foldertree") or {}))
        a = self._ft_args(params, ft)
        skip = bool(params.get("skip_existing", ft.get("skip_existing", True)))
        eps, errs = r["ft"].parse_episodes(a["eps_text"])
        if errs or not eps:
            return {"ok": False, "message": "集数输入无效，已停止建立：" + "；".join(errs or ["没有有效集数"])}
        if a["ptx_mode"] != "none":
            source = r["ft"].locate_template_ptx(a["template_root"])
            if source is None:
                return {"ok": False, "message": "未找到可复制的PTX工程模板，已停止建立。请选择包含Project模板的模板根目录，或明确选择不复制。"}
            try:
                with open(source, "rb") as handle:
                    handle.read(1)
            except OSError as exc:
                return {"ok": False, "message": "PTX工程模板不可读取，已停止建立：%s" % exc}

        def job():
            eps, errs = r["ft"].parse_episodes(a["eps_text"])
            project_root, steps, warns, _ep_names = r["ft"].plan_creation(
                eps, a["name"], a["seq"], a["level"], a["date"], a["user"],
                a["output_root"], a["template_root"],
                ptx_mode=a["ptx_mode"], ep_naming=a["ep_naming"],
            episode_template=a["episode_template"], episode_padding=a["episode_padding"], project_template=a["project_template"])
            if not steps:
                message = "无可建立项——请检查集数/模板路径"
                self._emit(message, "err")
                return {"ok": False, "tail": "✗ " + message}
            problems = r["ft"].precheck_build(a["template_root"], a["output_root"],
                                              project_root, a["ptx_mode"])
            for p in problems:
                self._emit("  ⚠ 预检：%s" % p, "err")
            for w in warns:
                self._emit("  ⚠ %s" % w)
            src_ptx = (r["ft"].locate_template_ptx(a["template_root"])
                       if a["ptx_mode"] != "none" else None)
            self._emit("=== 开始建立: %s（%d 步）===" % (project_root, len(steps)))
            created, skipped2, failed = r["ft"].apply_plan(
                project_root, steps, src_ptx=src_ptx, skip_existing=skip,
                log=lambda m: self._emit("  %s" % m))
            # 模板若在规划后消失，核心可能跳过copy；缺失的目标不能算建立成功。
            missing = [path for action, path in steps if action == "copy" and not os.path.isfile(path)]
            if missing and not failed:
                failed = len(missing)
                skipped2 = max(0, skipped2 - failed)
            if failed:
                message = "建立失败：新建 %d / 跳过 %d / 失败 %d" % (created, skipped2, failed)
            elif created:
                message = "工程目录建立完成：新建 %d / 跳过 %d / 失败 0" % (created, skipped2)
            else:
                message = "无需新建：全部 %d 项已存在，已跳过" % skipped2
            self._emit(message, "err" if failed else "ok")
            self._emit_event("ft_built", {"ok": failed == 0, "message": message,
                                        "created": created, "skipped": skipped2,
                                        "failed": failed, "project_root": project_root})
            return {"ok": failed == 0, "tail": ("✗ " if failed else "✓ ") + message}

        return self._run_bg(job, "✓ 工程文件夹建立完成")

    def ft_infer(self, output_root: str) -> dict:
        """从上次项目输出目录提取字段（名称/日期/用户/下一个序号）。"""
        r = _re()
        if not output_root or not os.path.isdir(output_root):
            return {"ok": False, "message": "输出目录不存在：%s" % (output_root or "（空）")}
        fields = r["ft"].infer_fields_from_output(output_root)
        return {"ok": True, "fields": fields,
                "next_seq": r["ft"].detect_next_seq(output_root)}


    def ft_read_project_folder(self, paths: list) -> dict:
        """Read dropped project metadata; never create or rename anything."""
        try:
            return dict(ok=True, **_re()["ft"].inspect_project_drop(paths))
        except (ValueError, OSError) as exc:
            return {"ok": False, "message": str(exc)}
