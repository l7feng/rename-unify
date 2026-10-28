# -*- coding: utf-8 -*-
"""rename-unify 配置与路径（单一来源，避免两处各猜 frozen）

⚠️ frozen 模式下代码在 _internal\\ 里（只读、可能被清理），
   配置/日志/回溯日志绝不能写代码目录 —— 一律落 exe 旁（APP_DIR）。
"""
import json
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

APP_NAME = "rename-unify"
# 四工具统一口径：版本号 X.Y.Z（不带 v 前缀），显示时补 v（见 title()）。
# v1.5.0（2026-09-24）：R1 执行前审计 json（rename_audit_*.json）+ 按审计跨会话回滚
#   + R3 规则集导出/导入。
# v1.7.0（2026-09-27）：D 档 F7+R2 合并（甲案）——原 pt-project-folder-builder
#   作为第 5 页签「工程文件夹」并入，逻辑在 foldertree.py（纯逻辑、零 tkinter）。
APP_VERSION = "3.14.0"


def app_dir():
    """可写目录：frozen 取 exe 旁，源码模式取项目根。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def asset_dir():
    """只读资源目录：frozen 时是 _internal。"""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable)))
    return os.path.dirname(os.path.abspath(__file__))


CONFIG_PATH = os.path.join(app_dir(), "config.json")
# v3.13.0 C2（裁决 13-1）：机器相关键落 config.local.json（Syncthing 排除，
# 两机各留各的）；config.json 只留通用键继续同步。exe 目录在同步盘内，
# 机器路径跟着 config.json 走会把 A 机的盘符/用户名搬到 B 机用。
LOCAL_CONFIG_PATH = os.path.join(app_dir(), "config.local.json")

# 机器键清单：值是「本机磁盘路径」且两机不等价的键。
#   last_root                    页1 扫描根（上次用过的目录）
#   foldertree.template_root     页5 文件夹模板根
#   foldertree.output_root       页5 输出根
# ⚠️ 已知边界：targets[].dir（页2 目标表里的目录）也是路径，但 targets 与
#    命名模板/备注混在同一份用户数据里，拆开会让整张目标表两机分叉 ——
#    本轮**不拆**（维持同步），若实际出现互踩再立项。
MACHINE_KEYS = ("last_root",)
MACHINE_NESTED = {"foldertree": ("template_root", "output_root")}


def _read_json_file(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _write_json_file(path, data):
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        return True
    except OSError:
        return False


def _pop_machine_keys(cfg):
    """从 cfg 就地摘出机器键（含嵌套），返回摘出的 machine dict。"""
    machine = {}
    for k in MACHINE_KEYS:
        if k in cfg:
            machine[k] = cfg.pop(k)
    for parent, subkeys in MACHINE_NESTED.items():
        sub = cfg.get(parent)
        if isinstance(sub, dict):
            picked = {}
            for k in subkeys:
                if k in sub:
                    picked[k] = sub.pop(k)
            if picked:
                machine.setdefault(parent, {}).update(picked)
            if not sub:
                cfg.pop(parent, None)   # 空壳一并清掉，主文件保持干净
    return machine


def _split_machine_config(cfg):
    """两态迁移（同 pt-tools/剪映 实现，裁决 13-1）：cfg 就地洗净机器键。

    态① local 不存在（首次升级）→ 机器键迁入新建 local、主文件洗净写回；
    态② local 已存在 → 主文件里的机器键视为他机同步污染，忽略并洗净主文件
    （本机 local 原值不动）——两机合流不互踩。
    返回 local 机器键值 dict。"""
    machine = _pop_machine_keys(cfg)
    local = _read_json_file(LOCAL_CONFIG_PATH)
    if local is None:
        if machine:
            _write_json_file(LOCAL_CONFIG_PATH, machine)
            _write_json_file(CONFIG_PATH, cfg)
        return dict(machine)
    if machine:
        _write_json_file(CONFIG_PATH, cfg)   # 污染键清除；本机 local 原值不动
    return local

# 跨机通用默认（2026-10-06 路径统一）：两机 D 盘路径完全一致，故直接绑定 D 盘标准位。
#   工程根 = D:\DAW-Project；模板根 = D:\Ai-Files\Templates\文件夹模板
# 已配置过的键（exe 旁 config.json / config.local.json）始终优先。
_HOME_DAW = r"D:\DAW-Project"
_TEMPLATE_ROOT = r"D:\Ai-Files\Templates"

DEFAULTS = {
    "last_root": _HOME_DAW,
    "recursive": True,
    "exts": ".wav .aif .aiff .mp3 .flac .w64",
    # 全局模板：目标没在「目标表」里单独配模板时用它兜底
    "template": "{片名} {集数}集 {日期} {版本} {用户}_{轨道信息}",
    "fields": {"片名": "片名", "日期": "0920", "版本": "V01", "用户": "7F"},
    "rules": [],          # 空 = 用 core_rules.DEFAULT_RULES
    # 模板库（页1 可增删改）：空 = 用 core_rules.DEFAULT_TEMPLATES
    "templates": [],
    # 目标表（页2「目标与归位」）：空 = 用 core_rules.DEFAULT_TARGETS
    # 每项 = {name, dir, enabled, eps, note, templates[], tpl_name}
    "targets": [],
    # v1.3.0 开关：
    # date_from_mtime —— 源名/集目录都没有日期时，用文件修改时间(MMDD)兜底
    #   （导出时刻，与手工标注 100% 吻合；优先级：源名 > 多数票 > mtime > 全局）
    "date_from_mtime": True,
    # rename_ep_dirs —— 集目录名统一按「片名 N集 日期 版本 用户」渲染改名
    #   （13/ → 剧甲 13集 0922 V01 7F/）；关掉 = 沿用旧「就地不改名」行为
    "rename_ep_dirs": True,
    "rename_files": False,
    "group_master": True,
    "rename_subtracks": True,
    "ep_dir_template": "{集数}",
    # ⚠️ 仅作 v1.1.0 → v1.2.0 的迁移源：旧「命名清单」会被折成目标表
    #    （core.migrate_enabled_types），新配置不再写这个键。
    "enabled_types": [],
    "window": "1180x760",
    # v3.12.1：界面外观三键进 DEFAULTS 白名单 —— 旧版 load_config 只认
    # DEFAULTS 里的键，theme/particle_bg 被静默丢弃，主题选择从未持久化成功。
    # 空串 = 未选过，运行时回落 theme.DEFAULT_THEME / DEFAULT_BUTTON_STYLE。
    "theme": "",
    "button_style": "",
    "particle_bg": True,
    # v1.7.0（D 档合并）：工程文件夹建树（原 pt-project-folder-builder）。
    # ⚠️ F5：「项目根」选项已删除 —— 集数文件夹固定建在 Project 子目录下，
    #    故这里**没有** placement 键（旧配置的该键会被忽略）。
    "foldertree": {
        "template_root": _TEMPLATE_ROOT,
        "output_root": _HOME_DAW,
        "name": "测试",
        "level": "D",
        "user": "7F",
        "eps": "1-10",
        "ep_naming": "name_num",
        "episode_template": "{片名} {集数}集",
        "episode_padding": 0,
        "project_template": "{片名}{等级}_{日期}_{用户}",
        "ptx_mode": "原样复制",
        "skip_existing": True,
    },
}


def load_config():
    cfg = _read_json_file(CONFIG_PATH)
    if cfg is None:
        cfg = {}
    # v3.13.0 C2：先做机器键分流（local 优先叠加），再走原有白名单合并。
    # 嵌套键（foldertree）按「通用∪本机」浅合并，缺键由下方逐键合并兜底。
    local = _split_machine_config(cfg)
    for k, v in local.items():
        if k in MACHINE_NESTED and isinstance(v, dict) and isinstance(cfg.get(k), dict):
            merged_sub = dict(cfg[k])
            merged_sub.update(v)
            cfg[k] = merged_sub
        else:
            cfg[k] = v
    out = dict(DEFAULTS)
    out.update({k: v for k, v in cfg.items() if k in DEFAULTS})
    # fields 做逐键合并，避免用户配置缺键导致 KeyError
    raw_fields = cfg.get("fields") if isinstance(cfg.get("fields"), dict) else {}
    f = dict(DEFAULTS["fields"])
    if raw_fields:
        f.update({str(k): str(v) for k, v in raw_fields.items()})
    # v1.1.0 的「档位」→ v1.2.0 的「用户」（7F 是用户代号，不是「档位」）。
    # ⚠️ 判据必须看**旧配置原文** raw_fields，不能看合并后的 f：
    #    DEFAULTS 里「用户」已带占位值 7F，用 f 判断会误认为「用户已设过」，
    #    导致旧配置的「档位」被静默丢掉（2026-09-23 回归抓到的 bug）。
    if "档位" in raw_fields and not str(raw_fields.get("用户", "") or "").strip():
        f["用户"] = str(raw_fields["档位"])
    f.pop("档位", None)
    out["fields"] = f
    # foldertree 逐键合并（v1.7.0）：用户配置缺键时补默认，避免 KeyError；
    # 只接受 DEFAULTS 里已有的键，脏键静默丢弃。
    raw_ft = cfg.get("foldertree") if isinstance(cfg.get("foldertree"), dict) else {}
    ft = dict(DEFAULTS["foldertree"])
    if raw_ft:
        ft.update({k: v for k, v in raw_ft.items() if k in DEFAULTS["foldertree"]})
    out["foldertree"] = ft
    # enabled_types 逐项清洗，容忍手改配置写坏结构
    out["enabled_types"] = _clean_enabled_types(cfg.get("enabled_types"))
    return out


def _clean_enabled_types(raw):
    """规范化命名实体清单：只留已知字段，补齐缺省，丢掉无 type 的项。"""
    if not isinstance(raw, list):
        return []
    out = []
    for e in raw:
        if not isinstance(e, dict):
            continue
        t = str(e.get("type", "")).strip()
        if not t:
            continue
        en = e.get("enabled", True)
        out.append({
            "type": t,
            "enabled": bool(en) if isinstance(en, bool) else str(en).strip().lower() not in ("0", "false", "no", ""),
            "eps": str(e.get("eps", "") or "").strip(),
            "note": str(e.get("note", "") or "").strip(),
        })
    return out


def save_config(cfg):
    """v3.13.0 C2 起分流保存：通用键 → config.json，机器键（含
    foldertree.template_root / foldertree.output_root）→ config.local.json
    （merge 写回，两机 .stignore 排除同步）。"""
    try:
        os.makedirs(app_dir(), exist_ok=True)
        common = dict(cfg)
        machine = _pop_machine_keys(common)
        with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
            json.dump(common, fh, ensure_ascii=False, indent=2)
        if machine:
            local = _read_json_file(LOCAL_CONFIG_PATH) or {}
            for k, v in machine.items():
                if isinstance(v, dict) and isinstance(local.get(k), dict):
                    merged_sub = dict(local[k])
                    merged_sub.update(v)
                    local[k] = merged_sub
                else:
                    local[k] = v
            _write_json_file(LOCAL_CONFIG_PATH, local)
        return True
    except OSError:
        return False


def build_date():
    """构建日期：frozen 取 exe 修改时间，源码模式取本文件时间。

    ⚠️ sys.executable 是 str，必须先包一层 Path 再 .stat()。
    """
    try:
        from pathlib import Path
        src = Path(sys.executable) if getattr(sys, "frozen", False) else Path(__file__)
        import datetime
        return datetime.datetime.fromtimestamp(src.stat().st_mtime).strftime("%Y-%m-%d")
    except Exception:
        return "未知"


def title():
    return "统一命名工具 v%s (%s)" % (APP_VERSION, build_date())


def setup_logging():
    """初始化滚动日志到 app_dir()/rename-unify.log（W2 骨架）。

    配置/日志/回溯日志一律落 exe 旁（APP_DIR），不写代码目录。
    返回 logger；失败静默返回 None（日志绝不影响主流程）。
    """
    try:
        os.makedirs(app_dir(), exist_ok=True)
        path = os.path.join(app_dir(), "rename-unify.log")
        logger = logging.getLogger("rename-unify")
        if not logger.handlers:
            handler = RotatingFileHandler(path, maxBytes=1_000_000,
                                          backupCount=3, encoding="utf-8")
            handler.setFormatter(logging.Formatter(
                "%(asctime)s [%(levelname)s] %(message)s"))
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
            logger.info("=== rename-unify v%s (%s) 启动 ===",
                        APP_VERSION, build_date())
        return logger
    except Exception:
        return None
