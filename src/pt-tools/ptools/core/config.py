# -*- coding: utf-8 -*-
"""配置读取 / 保存 / 迁移（W1 三层拆分 · core/config）。

只补缺省、绝不擦用户已存键；全部 OSError 静默（配置异常不挡启动）。

v3.13.0 C2（裁决 13-1）：配置拆双文件 ——
  config.json       通用键（模板/开关/语言/窗口…），随 Syncthing 两机同步；
  config.local.json 机器相关键（本机磁盘路径），两机 .stignore 各加一行
                    `config.local.json` 排除同步，各机各留各的。
背景：exe 目录在 Syncthing 同步盘内，config.json 携 A 机
C:\\Users\\<A>\\... 路径到 B 机会拿别的机器的盘来用（剪映「发现 0 个草稿」
同源根因）。拆分语义见 _split_machine_config。
"""
import json
import os
import shutil
from .i18n import detect_system_lang
from .settings import (
    APP_DIR, CONFIG_FILE, LOCAL_CONFIG_FILE,
    DEFAULT_EXPORT_FORMAT, DEFAULT_FALLBACK_DURATION,
    DEFAULT_OUT_ROOT, DEFAULT_PROFILE_DIR, DEFAULT_VIDEO_MARGIN,
)


# ── v3.13.0 C2（裁决 13-1）：机器相关键清单 ──────────────────────
# 判据＝值是「本机磁盘路径」且两机不等价的键。skills_root 虽也是路径，
# 但指 D:\\Ai-Files（Syncthing 两机同构的同步盘根），两机等价 →
# 故意**留在通用文件**，别按「它是路径」想当然搬进 local。
MACHINE_KEYS = ("last_out_dir", "profile_dir")


# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

def migrate_legacy_config():
    """W4（v1.5.0）：旧 %APPDATA%\\pt-tools\\config.json → exe 旁（只复制不删除）。

    仅当 exe 旁还没有配置且旧文件存在时执行一次；复制失败静默
    （大不了从头配，绝不挡启动）。
    """
    from .settings import LEGACY_CONFIG_FILE
    try:
        if os.path.isfile(CONFIG_FILE) or not os.path.isfile(LEGACY_CONFIG_FILE):
            return False
        os.makedirs(APP_DIR, exist_ok=True)
        shutil.copy2(LEGACY_CONFIG_FILE, CONFIG_FILE)
        return True
    except OSError:
        return False


def _read_json(path):
    """读 JSON dict；文件不存在/损坏返回 None，损坏但存在返回 None 也当无。"""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _write_json(path, data):
    """写 JSON dict（UTF-8/不转义中文/缩进2）；失败静默。"""
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        return True
    except OSError:
        return False


def _split_machine_config(cfg):
    """C2 核心：把 config.json 里的机器键分流到 config.local.json（两态）。

    态① local 文件不存在（首次升级）：
        主文件里的机器键 → 迁入新建的 local 文件（本机已有配置无损拆分），
        主文件就地洗净（机器键移除）——同步盘里的 config.json 从此干净。
    态② local 文件已存在：
        主文件里再出现机器键 = 他机 config.json 同步带来的**污染**，
        忽略之（绝不覆盖本机 local 的值），只把主文件洗净——
        两机各自 load 各自的 local，合流不互踩。
    返回机器键值的 dict（调用方叠加进生效配置）。
    """
    machine = {}
    for k in MACHINE_KEYS:
        if k in cfg:
            machine[k] = cfg.pop(k)
    local = _read_json(LOCAL_CONFIG_FILE)
    if local is None:
        if machine:
            _write_json(LOCAL_CONFIG_FILE, machine)
            _write_json(CONFIG_FILE, cfg)      # 主文件洗净后写回同步盘
        return dict(machine)
    if machine:
        _write_json(CONFIG_FILE, cfg)          # 污染键清除；local 原值不动
    return local


def load_config():
    migrate_legacy_config()
    cfg = _read_json(CONFIG_FILE) or {}
    # v3.13.0 C2：先分流机器键（local 优先叠加），再走原有补缺省逻辑
    local = _split_machine_config(cfg)
    cfg.update(local)
    cfg.setdefault("skills_root", "")
    cfg.setdefault("last_profile", "")
    cfg.setdefault("last_out_dir", "")
    cfg.setdefault("lang", detect_system_lang())
    # v1.4.0：档案目录 / 输出根的出厂默认（老配置缺键时补，不覆盖已设值）
    cfg.setdefault("profile_dir", DEFAULT_PROFILE_DIR)
    if not str(cfg.get("last_out_dir") or "").strip():
        cfg["last_out_dir"] = DEFAULT_OUT_ROOT
    _migrate_cfg(cfg)
    return cfg


def _migrate_cfg(cfg):
    """配置迁移（只补缺省 / 升级已知坏值，绝不擦掉用户已存的其它键）。

    v1.3.0（cfg_version 1 → 2）三处默认值修正，都是"旧默认会把活悄悄做错"：
      ① format：旧默认 `mono` 会把立体声**下混**，用户完全不知情 → interleaved
      ② video_margin：旧默认 240s，每条片子都被加 4 分钟尾巴 → 0
      ③ fallback_duration：旧默认 240s，没检出视频时**假装片子 4 分钟**
        （6 分钟的片会被悄悄截断）→ 60
    v1.4.0（cfg_version 2 → 3）默认路径收口：
      ④ profile_dir 缺省 → Backup-PT-Tools/json（建档输出 + 档案浏览默认目录）
      ⑤ last_out_dir 为空 → Backup-PT-Tools/out
    用户若手工改过这些值，一律保留，不覆盖。
    """
    ver = int(cfg.get("cfg_version") or 0)
    if ver >= 3:
        return
    if ver < 2:
        if cfg.get("format") in (None, "", "mono"):
            cfg["format"] = DEFAULT_EXPORT_FORMAT
        if _as_int(cfg.get("video_margin")) in (None, 240):
            cfg["video_margin"] = DEFAULT_VIDEO_MARGIN
        if _as_int(cfg.get("fallback_duration")) in (None, 240):
            cfg["fallback_duration"] = DEFAULT_FALLBACK_DURATION
    if not str(cfg.get("profile_dir") or "").strip():
        cfg["profile_dir"] = DEFAULT_PROFILE_DIR
    if not str(cfg.get("last_out_dir") or "").strip():
        cfg["last_out_dir"] = DEFAULT_OUT_ROOT
    cfg["cfg_version"] = 3


def _as_int(v):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def save_config(cfg):
    """保存配置（v3.13.0 C2 起分流）：通用键 → config.json，机器键 → config.local.json。

    local 按 merge 写回（先读现有文件再叠加），保留未来版本可能新增的
    本机键；OSError 一律静默（配置写不进不挡主流程）。
    """
    try:
        os.makedirs(APP_DIR, exist_ok=True)
        machine = {k: cfg[k] for k in MACHINE_KEYS if k in cfg}
        common = {k: v for k, v in cfg.items() if k not in MACHINE_KEYS}
        with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
            json.dump(common, fh, ensure_ascii=False, indent=2)
        if machine:
            local = _read_json(LOCAL_CONFIG_FILE) or {}
            local.update(machine)
            _write_json(LOCAL_CONFIG_FILE, local)
    except OSError:
        pass
