# -*- coding: utf-8 -*-
"""共享视觉主题（S13 / v3.10.0）—— 同源三副本之一。

副本规则（与 scrollable.py 相同）：
  ① src/pt-tools/ptools/gui/theme.py         ← 权威源
  ② src/rename-unify/code/theme.py           ← 整文件复制
  ③ src/jianying-draft-toolkit/code/theme.py  ← 整文件复制
改一必须同步二三。

设计取向（2026-09-28 裁决 D3-甲 + 本轮追加「多色彩主题」）：
  六套内置主题，运行时可切换、持久化到 cfg["theme"]（默认 warm 米白暖调·Claude 风）：
    · warm     米白暖调（Claude Desktop 风）
    · cool     冷灰专业（偏蓝灰，适合白天大屏）
    · dark     深蓝夜间（低亮度护眼，默认）
    · contrast 墨黑高对比（视力辅助 / 投影）
    · nord     Nord 蓝灰冷调 / emerald 翡翠极简 / ocean 海洋蓝
  主按钮一个强调色，删除类按钮标红；每主题带三色（ACCENT/ACCENT_2/ACCENT_3）
  与中间过渡色（MID_1/MID_2），功能板块用遮罩色（*_SOFT）着色。

v3.12.1 按钮风格切换（持久化到 cfg["button_style"]，默认 pixel 像素）：
    · rounded  圆润（苹果风）—— flat 无边框 + 大内边距
    · pixel    像素（复古风）—— raised 浮雕硬边框 + 紧凑内边距
  用法：
    theme.apply(root, button_style="pixel")
    theme.set_button_style(root, "pixel")           # 运行时切换
    for k, v in theme.list_button_styles(): ...     # 设置菜单枚举

用法：
    import theme
    theme.apply(root)                              # 入口：装配全部 ttk 样式（读 cfg 或默认 dark）
    theme.apply(root, theme_name="dark")          # 强制指定主题
    theme.set_theme(root, "cool")                 # 运行时切换（含原生控件重着色）
    for name, label in theme.list_themes(): ...   # 设置菜单枚举
    root.geometry(theme.initial_geometry(cfg.get("window"), root))   # S12
    theme.window_size(root)                        # 关闭前取 "WxH" 存回 cfg["window"]
    ttk.Button(..., style="Accent.TButton")       # 主按钮（开始/导出/执行）
    ttk.Button(..., style="Danger.TButton")       # 危险按钮（删除/清空/中止）
"""

import re
import tkinter as tk
from tkinter import ttk

# ── 主题注册表（v3.11.0：6套主题，参考 Claude/ChatGPT/Grok/OpenCode/Kimi）──
# 每套主题必须包含全部色键；切换时整组替换。
THEMES = {
    # ── Claude 风：暖调人文 ──
    "warm": {
        "label":      "米白暖调",
        "BG":         "#f3f0ea",   # 窗口底（Claude #F0ECE0 微调）
        "SURFACE":    "#fdfcfa",   # 卡片/输入框（极淡暖白，非纯白）
        "BORDER":     "#e0ddd6",   # 细边框（Claude #E5E0D6）
        "FG":         "#1a1a18",   # 正文（Claude #1a1a18）
        "FG_DIM":     "#6b6860",   # 次要文字（Claude #5b5950 微调）
        "ACCENT":     "#c96442",   # 主按钮（Claude 赤陶 #c96442）
        "ACCENT_HV":  "#b4552f",   # 主按钮悬停
        # v3.13.0 C2.5 色彩收敛（裁决 13-6）：warm 同屏 7 色相 → 3（赤陶/青灰蓝/红）。
        # ACCENT_2 琥珀与赤陶同屏打架 → 并入赤陶（键保留，三色遮罩体系兼容）；
        # INFO 纯蓝→青灰蓝；WARNING→暖沙；SUCCESS 降一档。改值不删键
        # （27 号 T1 契约：primitive 原名单保留）。
        "ACCENT_2":   "#c96442",   # 第二强调（并入赤陶，消灭第二橙）
        "ACCENT_3":   "#5e7a8b",   # 第三强调（青灰蓝，唯一冷色族）
        "DANGER":     "#dc2626",   # 删除（统一语义色）
        "DANGER_HV":  "#b91c1c",
        "SELECT_BG":  "#e8e4dc",   # 选中底
        "HEAD_BG":    "#efece5",   # 表头底
        "SUCCESS":    "#15803d",   # 成功（降一档：不比主按钮亮）
        "WARNING":    "#b08968",   # 警告（暖沙：消灭第三橙）
        "INFO":       "#5e7a8b",   # 信息（纯蓝→青灰蓝，撞色消失）
    },
    # ── ChatGPT 风：极简克制 + 翡翠绿 ──
    "emerald": {
        "label":      "翡翠极简",
        "BG":         "#f7f7f8",   # 窗口底（ChatGPT #F7F7F8）
        "SURFACE":    "#ffffff",   # 卡片/输入框（ChatGPT 纯白）
        "BORDER":     "#e5e5e5",   # 细边框
        "FG":         "#2d2d2d",   # 正文（ChatGPT #2D2D2D）
        "FG_DIM":     "#6b6b6b",   # 次要文字
        "ACCENT":     "#10a37f",   # 主按钮（ChatGPT 翡翠绿 #10A37F）
        "ACCENT_HV":  "#0e8c6d",
        # C2.5 收敛：天蓝并入翡翠；INFO→石板灰蓝；SUCCESS/WARNING 降饱和
        "ACCENT_2":   "#10a37f",   # 第二强调（并入翡翠）
        "ACCENT_3":   "#64748b",   # 第三强调（石板灰蓝）
        "DANGER":     "#dc2626",
        "DANGER_HV":  "#b91c1c",
        "SELECT_BG":  "#e8f5f0",   # 选中底（淡翡翠）
        "HEAD_BG":    "#f0f0f2",
        "SUCCESS":    "#15803d",
        "WARNING":    "#b08968",
        "INFO":       "#64748b",
    },
    # ── OpenCode Nord 风：蓝灰冷调 ──
    "nord": {
        "label":      "Nord蓝灰",
        "BG":         "#eceff4",   # Nord nord6（窗口底）
        "SURFACE":    "#ffffff",   # 卡片
        "BORDER":     "#d8dee9",   # Nord nord4（边框）
        "FG":         "#2e3440",   # Nord nord0（正文）
        "FG_DIM":     "#4c566a",   # Nord nord3（次要）
        "ACCENT":     "#5e81ac",   # Nord nord10（主按钮蓝）
        "ACCENT_HV":  "#4c6f9a",
        # C2.5 收敛：青绿/雪青紫并入主蓝（Nord 本就低饱和，砍到蓝+红两族）
        "ACCENT_2":   "#5e81ac",   # 第二强调（并入主蓝）
        "ACCENT_3":   "#5e81ac",   # 第三强调（并入主蓝）
        "DANGER":     "#bf616a",   # Nord nord11
        "DANGER_HV":  "#a54e57",
        "SELECT_BG":  "#d8dee9",   # Nord nord4
        "HEAD_BG":    "#e5e9f0",   # Nord nord5
        "SUCCESS":    "#8fa872",   # 降饱和（nord14 绿降一档）
        "WARNING":    "#b08968",   # 暖沙（nord12 橙退役）
        "INFO":       "#5e81ac",   # 并入主蓝（nord9 色相同族，收敛同值）
    },
    # ── Grok 风：近纯黑深色 ──
    "dark": {
        "label":      "深夜纯黑",
        "BG":         "#141414",   # Grok #141414（近纯黑）
        "SURFACE":    "#1f1f1f",   # Grok #212121（输入区）
        "BORDER":     "#2a2a2a",   # Grok #2a2a2a
        "FG":         "#f5f5f5",   # 正文（接近纯白）
        "FG_DIM":     "#9a9a9a",   # 次要文字（v3.13.0 T2 提亮一阶：8a 对比不足）
        "ACCENT":     "#4f8cff",   # 主按钮（亮蓝，黑底下够亮）
        "ACCENT_HV":  "#3b7aef",
        # C2.5 收敛：霓虹青/柔紫并入主蓝；INFO 与 ACCENT 同族保留
        "ACCENT_2":   "#4f8cff",   # 第二强调（并入主蓝）
        "ACCENT_3":   "#7a95a8",   # 第三强调（柔紫→青灰蓝亮阶，黑底可读）
        "DANGER":     "#ef4444",
        "DANGER_HV":  "#dc2626",
        "SELECT_BG":  "#2e343f",   # v3.13.0 T2：混入 10% 主蓝（原 #2a2a2a 与 BORDER 同色，选中态不醒目）
        "HEAD_BG":    "#1a1a1a",
        "SUCCESS":    "#1fa855",   # 降饱和提亮度（黑底可读且不抢主按钮）
        "WARNING":    "#d9a05b",   # 暖沙亮阶（黑底可读）
        "INFO":       "#4f8cff",   # 并入主蓝（同 221° 族，收敛同值）
    },
    # ── OpenCode 风：暖黑深色 ──
    "contrast": {
        "label":      "暖黑高对比",
        "BG":         "#201d1d",   # OpenCode #201d1d（暖近黑）
        "SURFACE":    "#2a2727",   # 卡片（暖黑提亮）
        "BORDER":     "#3d3a3a",
        "FG":         "#fdfcfc",   # OpenCode #fdfcfc（亮米白）
        "FG_DIM":     "#9a9898",   # OpenCode #9a9898（暖灰）
        "ACCENT":     "#007aff",   # OpenCode Apple 蓝 #007aff
        "ACCENT_HV":  "#0066d6",
        # C2.5 收敛：Apple 青/紫并入主蓝
        "ACCENT_2":   "#007aff",   # 第二强调（并入主蓝）
        "ACCENT_3":   "#7a95a8",   # 第三强调（青灰蓝亮阶）
        "DANGER":     "#ff3b30",   # OpenCode Apple 红
        "DANGER_HV":  "#e02e24",
        "SELECT_BG":  "#2a2a2a",
        "HEAD_BG":    "#252222",
        "SUCCESS":    "#1fa855",   # 降饱和
        "WARNING":    "#c9a26b",   # Apple 橙→暖沙亮阶
        "INFO":       "#007aff",
    },
    # ── Kimi 风：蓝色专业浅色 ──
    "ocean": {
        "label":      "海洋蓝",
        "BG":         "#f0f4f8",   # 浅蓝灰底
        "SURFACE":    "#ffffff",
        "BORDER":     "#d0d9e2",
        "FG":         "#1a2332",   # 深蓝黑正文
        "FG_DIM":     "#5a6a7a",
        "ACCENT":     "#1565c0",   # Kimi 主色 #1565C0
        "ACCENT_HV":  "#0d47a1",
        # C2.5 收敛：青绿/雅紫并入主蓝
        "ACCENT_2":   "#1565c0",   # 第二强调（并入主蓝）
        "ACCENT_3":   "#5e7a8b",   # 第三强调（青灰蓝）
        "DANGER":     "#dc2626",
        "DANGER_HV":  "#b91c1c",
        "SELECT_BG":  "#dbeafe",   # 淡蓝选中
        "HEAD_BG":    "#e8eef4",
        "SUCCESS":    "#15803d",
        "WARNING":    "#b08968",
        "INFO":       "#1565c0",
    },
}

DEFAULT_THEME = "warm"   # v3.12.1：默认暖色（用户裁决：默认主题是米白暖调·Claude 风）
_state = {"current": None, "button_style": None}   # 运行时当前主题名 / 按钮风格

# ── v3.13.0 C2.5 风格注册表（像素 / 玻璃 / 圆润，标签中英双语）─────────
# 风格档案 = 主题(色) × 风格(shape/border/motion) 两轴中的风格轴：
#   pixel  像素 —— 直角、raised 硬边框、亮棱暗棱浮雕（实现已就位）
#   glass  玻璃 —— 壳玻璃+实心内容：玻璃只用于按钮等控件层（tkinter 无真
#          模糊，用「面板混白 + 白描边 + 顶缘高光」模拟；列表/日志等内容区
#          恒实心，不受档案影响——Liquid Glass 纪律: Do Not Use For content）
#   rounded 圆润 —— ⛔ v3.14.0 裁决 15-6：**并入玻璃档**（ttk 底座同为方形、
#          两档肉眼差异微小——人类实测「这两个功能区别不大」；玻璃档承接苹果风
#          方向：渐变壳+柔和阴影+水波纹）。旧 cfg 值 rounded 经
#          normalize_button_style() 自动迁移为 glass，配置兼容不丢档。
DEFAULT_BUTTON_STYLE = "pixel"
BUTTON_STYLES = {
    "pixel":   "像素 Pixel",
    "glass":   "玻璃 Glass",
}
_STYLE_MERGED = {"rounded": "glass"}     # 旧档位 -> 新档位映射


def normalize_button_style(name):
    """旧档位迁移（裁决 15-6）：rounded → glass；未知值原样返回。"""
    return _STYLE_MERGED.get(name, name)


def list_button_styles():
    """返回 [(key, 中文标签), ...]，供设置菜单枚举。"""
    return [(k, v) for k, v in BUTTON_STYLES.items()]


def current_button_style():
    """当前按钮风格 key；未设置过返回默认 pixel。旧值 rounded 自动迁移 glass。"""
    return normalize_button_style(_state.get("button_style") or DEFAULT_BUTTON_STYLE)


def button_style_label(name):
    """key → 中文标签；未知 key 返回 key 本身。"""
    return BUTTON_STYLES.get(name, name)

# v3.11.0 字体层级系统（参考五款产品：标题/副标题/正文/辅助/等宽）
FONT_TITLE    = ("Microsoft YaHei UI", 16, "bold")   # 窗口标题/页标题
FONT_SUBTITLE = ("Microsoft YaHei UI", 12, "bold")   # 分组标题/LabelFrame标签
FONT_BODY     = ("Microsoft YaHei UI", 10)            # 正文（从9pt升到10pt，更清晰）
FONT_BOLD     = ("Microsoft YaHei UI", 10, "bold")    # 加粗正文/按钮
FONT_SMALL    = ("Microsoft YaHei UI", 9)             # 辅助文字/状态栏/次要信息
FONT_MONO     = ("Consolas", 10)                       # 等宽：日志/路径/代码/数据
FONT_MONO_SM  = ("Consolas", 9)                        # 等宽小号
# 兼容旧引用
FONT = FONT_BODY

MIN_W, MIN_H = 900, 620   # S12：三工具统一最小尺寸

# S13-v4：统一间距常量（布局重排用）
PAD_XS = 2
PAD_SM = 4
PAD_MD = 8
PAD_LG = 12
PAD_XL = 16
PAD_XXL = 24
# 标准内边距元组（左, 上, 右, 下）
PAD_BODY = (PAD_LG, PAD_MD, PAD_LG, PAD_MD)     # 页面主体
PAD_CARD = (PAD_MD, PAD_MD, PAD_MD, PAD_MD)      # 卡片内部
PAD_BTN_ROW = (0, PAD_SM, 0, PAD_SM)             # 按钮行
PAD_STATUSBAR = (PAD_LG, PAD_SM, PAD_LG, PAD_SM)  # 状态栏


# ── 主题查询 ──────────────────────────────────────────────────────

def list_themes():
    """返回 [(key, 中文标签), ...]，供设置菜单枚举。"""
    return [(k, v["label"]) for k, v in THEMES.items()]


def current_theme_name():
    """当前已应用的主题 key；未 apply 过返回 None。"""
    return _state["current"]


def theme_label(name):
    """key → 中文标签；未知 key 返回 key 本身。"""
    return THEMES.get(name, {}).get("label", name)


def _resolve_theme(name):
    """取主题调色板；未知或 None → 默认。"""
    if name and name in THEMES:
        return name, THEMES[name]
    return DEFAULT_THEME, THEMES[DEFAULT_THEME]


# ── 主题应用 ──────────────────────────────────────────────────────

def apply(root, theme_name=None, button_style=None):
    """装配主题。幂等：重复调用无害。

    v3.13.0 T2：本函数属 component 层，只引用语义 token
    （tok["action.primary"] 式，经语义别名本地化后引用），禁止直戳
    primitive 色键——层级卫生由 test_theme_geometry 静态断言守护。

    theme_name 为 None 时不改变当前主题（首次则用默认 warm 米白暖调）；
    传入具体 key 则切换到该主题。运行时切换请用 set_theme()。
    button_style 为 None 时沿用当前按钮风格（首次则用默认 pixel 像素）；
    传入 "rounded"/"pixel" 则切换。运行时切换请用 set_button_style()。
    """
    name, _pal = _resolve_theme(theme_name or _state["current"])
    _state["current"] = name
    button_style = normalize_button_style(button_style)   # 15-6：rounded→glass
    bstyle = button_style if button_style in BUTTON_STYLES else (
        normalize_button_style(_state.get("button_style")) or DEFAULT_BUTTON_STYLE)
    if bstyle not in BUTTON_STYLES:
        bstyle = DEFAULT_BUTTON_STYLE
    _state["button_style"] = bstyle

    # v3.13.0 T2：语义 token 全集（primitive + 派生 + 语义别名）
    tok = tokens(name)

    st = ttk.Style(root)
    # clam：tkinter 自带主题里唯一能完整控制配色的底子
    try:
        st.theme_use("clam")
    except Exception:
        pass

    # 语义键本地化（component 表：27号文档 §二第 3 层）
    WIN = tok["surface.window"]          # 窗口底
    CARD = tok["surface.card"]           # 卡片/输入
    LINE = tok["border.default"]         # 常规边框
    INK = tok["text.primary"]            # 正文
    INK_DIM = tok["text.secondary"]      # 次要文字
    ACT = tok["action.primary"]          # 主操作
    ACT_HV = tok["action.primary.hover"]
    DNG = tok["action.danger"]           # 危险操作
    DNG_HV = tok["action.danger.hover"]
    SEL = tok["state.selected.bg"]       # 选中底
    HEAD = tok["state.header.bg"]        # 表头底
    ON_ACCENT = tok["text.on.accent"]    # 强调底上的文字（恒白）

    st.configure(".", background=WIN, foreground=INK, font=FONT_BODY,
                 bordercolor=LINE, lightcolor=LINE, darkcolor=LINE,
                 troughcolor=WIN, selectbackground=SEL, selectforeground=INK)
    st.configure("TFrame", background=WIN)
    st.configure("TLabel", background=WIN, foreground=INK, font=FONT_BODY)
    if bstyle == "pixel":
        # v3.12.1 像素风（复古 8-bit）：raised 浮雕硬边框 + 紧凑内边距，
        # 用 lightcolor（亮棱）/darkcolor（暗棱）撑出方块立体感
        px_hover = _lighten(CARD, 10) if _is_dark(tok) else _darken(CARD, 6)
        px_press = _lighten(CARD, 4) if _is_dark(tok) else _darken(CARD, 12)
        px_l = _lighten(CARD, 24)
        px_d = _darken(CARD, 34)
        st.configure("TButton", background=CARD, foreground=INK, font=FONT_BOLD,
                     bordercolor=LINE, lightcolor=px_l, darkcolor=px_d,
                     relief="raised", borderwidth=2, padding=(10, 5),
                     focusthickness=0)
        st.map("TButton",
               background=[("pressed", px_press), ("active", px_hover),
                           ("disabled", WIN)],
               foreground=[("disabled", INK_DIM)],
               lightcolor=[("pressed", px_d), ("active", px_l)],
               darkcolor=[("pressed", px_d), ("active", px_l)])
        # 主按钮（Accent·像素）：亮棱暗棱各让 30+，浮雕感更强
        a_l, a_d = _lighten(ACT, 32), _darken(ACT, 36)
        st.configure("Accent.TButton", background=ACT, foreground=ON_ACCENT,
                     font=FONT_BOLD, bordercolor=_darken(ACT, 44),
                     lightcolor=a_l, darkcolor=a_d, relief="raised",
                     borderwidth=2, padding=(10, 5), focusthickness=0)
        st.map("Accent.TButton",
               background=[("disabled", _dim(ACT, WIN)),
                           ("pressed", ACT_HV), ("active", a_l)],
               foreground=[("disabled", _dim(ON_ACCENT, WIN))],
               lightcolor=[("pressed", a_d), ("active", a_l)],
               darkcolor=[("pressed", a_d), ("active", a_l)])
        # 危险按钮（Danger·像素）
        d_l, d_d = _lighten(DNG, 30), _darken(DNG, 32)
        st.configure("Danger.TButton", background=DNG, foreground=ON_ACCENT,
                     font=FONT_BOLD, bordercolor=_darken(DNG, 44),
                     lightcolor=d_l, darkcolor=d_d, relief="raised",
                     borderwidth=2, padding=(10, 5), focusthickness=0)
        st.map("Danger.TButton",
               background=[("disabled", _dim(DNG, WIN)),
                           ("pressed", DNG_HV), ("active", d_l)],
               foreground=[("disabled", _dim(ON_ACCENT, WIN))],
               lightcolor=[("pressed", d_d), ("active", d_l)],
               darkcolor=[("pressed", d_d), ("active", d_l)])
    elif bstyle == "glass":
        # v3.13.0 C2.5 玻璃档案：控件层 = 面板混白 + 白描边 + 顶缘高光
        #（tkinter 无真模糊，调色模拟）；主/危险按钮保持实底强调色
        #（主按钮唯一赤陶），内容区（Treeview/Entry/日志）不受影响。
        dark = _is_dark(tok)
        if dark:
            panel = _lighten(CARD, 16)          # 深色：面板向白混一档
            stroke = _lighten(WIN, 46)          # 亮描边（深底上的"白"描边）
            hl = _lighten(panel, 26)            # 顶缘高光
        else:
            panel = _blend(CARD, "#ffffff", 0.45)   # 浅色：面板混白 45%
            stroke = _blend(WIN, "#ffffff", 0.65)   # 白描边
            hl = "#ffffff"
        st.configure("TButton", background=panel, foreground=INK, font=FONT_BOLD,
                     bordercolor=stroke, lightcolor=hl, darkcolor=panel,
                     relief="flat", borderwidth=1, padding=(14, 6), focusthickness=0)
        st.map("TButton",
               background=[("pressed", _darken(panel, 10)),
                           ("active", _lighten(panel, 8) if dark else _lighten(panel, 16)),
                           ("disabled", WIN)],
               foreground=[("disabled", INK_DIM)],
               lightcolor=[("pressed", panel), ("active", hl)],
               darkcolor=[("pressed", panel), ("active", panel)])
        # 主按钮（Accent·玻璃）：实底强调色不透——强调色是语义不是材质
        st.configure("Accent.TButton", background=ACT, foreground=ON_ACCENT,
                     font=FONT_BOLD, bordercolor=stroke,
                     lightcolor=_lighten(ACT, 26), darkcolor=ACT_HV,
                     relief="flat", borderwidth=1, padding=(16, 7), focusthickness=0)
        st.map("Accent.TButton",
               background=[("disabled", _dim(ACT, WIN)),
                           ("pressed", ACT_HV), ("active", ACT_HV)],
               foreground=[("disabled", _dim(ON_ACCENT, WIN))])
        # 危险按钮（Danger·玻璃）
        st.configure("Danger.TButton", background=DNG, foreground=ON_ACCENT,
                     font=FONT_BOLD, bordercolor=stroke,
                     lightcolor=_lighten(DNG, 22), darkcolor=DNG_HV,
                     relief="flat", borderwidth=1, padding=(12, 6), focusthickness=0)
        st.map("Danger.TButton",
               background=[("disabled", _dim(DNG, WIN)),
                           ("pressed", DNG_HV), ("active", DNG_HV)],
               foreground=[("disabled", _dim(ON_ACCENT, WIN))])
    else:
        # 圆润风（苹果）：flat 无边框 + 大内边距 + 纯色块
        st.configure("TButton", background=CARD, foreground=INK, font=FONT_BOLD,
                     bordercolor=LINE, lightcolor=CARD, darkcolor=LINE,
                     relief="flat", padding=(14, 6), focusthickness=1)
        # 普通按钮悬停色：浅色主题用稍深灰，深色主题用稍亮灰
        btn_hover = _lighten(WIN, 8) if _is_dark(tok) else _darken(WIN, 6)
        btn_press = _lighten(WIN, 4) if _is_dark(tok) else _darken(WIN, 10)
        st.map("TButton",
               background=[("pressed", btn_press), ("active", btn_hover),
                           ("disabled", WIN)],
               foreground=[("disabled", INK_DIM)],
               lightcolor=[("pressed", btn_press), ("active", btn_hover)],
               darkcolor=[("pressed", btn_press), ("active", btn_hover)])
        # 主按钮（Accent）
        st.configure("Accent.TButton", background=ACT, foreground=ON_ACCENT,
                     font=FONT_BOLD, bordercolor=ACT, lightcolor=ACT,
                     darkcolor=ACT, relief="flat", padding=(16, 7))
        st.map("Accent.TButton",
               background=[("disabled", _dim(ACT, WIN)),
                           ("pressed", ACT_HV), ("active", ACT_HV)],
               foreground=[("disabled", _dim(ON_ACCENT, WIN))],
               lightcolor=[("pressed", ACT_HV), ("active", ACT_HV)],
               darkcolor=[("pressed", ACT_HV), ("active", ACT_HV)])
        # 危险按钮（Danger）
        st.configure("Danger.TButton", background=DNG, foreground=ON_ACCENT,
                     font=FONT_BOLD, bordercolor=DNG, lightcolor=DNG,
                     darkcolor=DNG, relief="flat", padding=(12, 6))
        st.map("Danger.TButton",
               background=[("disabled", _dim(DNG, WIN)),
                           ("pressed", DNG_HV), ("active", DNG_HV)],
               foreground=[("disabled", _dim(ON_ACCENT, WIN))],
               lightcolor=[("pressed", DNG_HV), ("active", DNG_HV)],
               darkcolor=[("pressed", DNG_HV), ("active", DNG_HV)])
    # 输入类
    st.configure("TEntry", fieldbackground=CARD, foreground=INK,
                 bordercolor=LINE, lightcolor=LINE, insertcolor=INK, padding=2)
    st.configure("TCombobox", fieldbackground=CARD, background=CARD,
                 foreground=INK, bordercolor=LINE, lightcolor=LINE,
                 arrowcolor=INK_DIM, padding=2)
    st.map("TEntry",
           bordercolor=[("focus", ACT), ("active", ACT)],
           lightcolor=[("focus", ACT)])
    st.map("TCombobox",
           fieldbackground=[("readonly", CARD)],
           bordercolor=[("focus", ACT), ("active", ACT)],
           lightcolor=[("focus", ACT)])
    st.configure("TSpinbox", fieldbackground=CARD, background=CARD,
                 foreground=INK, bordercolor=LINE, lightcolor=LINE,
                 arrowcolor=INK_DIM, padding=2)
    st.map("TSpinbox",
           fieldbackground=[("readonly", CARD)],
           bordercolor=[("focus", ACT), ("active", ACT)])
    # 页签（v3.12.1：选中页签用强调色遮罩，一眼看出所在页）
    st.configure("TNotebook", background=WIN, bordercolor=LINE, tabmargins=(8, 6, 8, 0))
    st.configure("TNotebook.Tab", background=WIN, foreground=INK_DIM, padding=(16, 8),
                 font=FONT_BODY)
    st.map("TNotebook.Tab",
           background=[("selected", tok["accent.softer"])],
           foreground=[("selected", INK)])
    # 表格
    st.configure("Treeview", background=CARD, fieldbackground=CARD,
                 foreground=INK, bordercolor=LINE, rowheight=28, font=FONT_BODY)
    st.configure("Treeview.Heading", background=HEAD, foreground=INK_DIM,
                 bordercolor=LINE, relief="flat", font=FONT_BOLD, padding=(8, 5))
    st.map("Treeview",
           background=[("selected", SEL)],
           foreground=[("selected", INK)])
    st.map("Treeview.Heading", background=[("active", HEAD)])
    # 滚动条
    st.configure("TScrollbar", background=WIN, troughcolor=WIN, bordercolor=WIN,
                 arrowcolor=INK_DIM, relief="flat")
    st.map("TScrollbar", background=[("active", _lighten(WIN, 10) if _is_dark(tok) else _darken(WIN, 8))])
    # 进度条 / 分隔线 / 分组框（TProgressbar 在下方状态栏遮罩段统一配置）
    st.configure("Separator", background=LINE)
    st.configure("TLabelframe", background=WIN, bordercolor=LINE, relief="solid", borderwidth=1)
    # v3.13.0 分组标题去强调色化：层级靠字重不靠颜色——强调色只留给主操作。
    # 标题 = 深色粗体；说明文字用 Caption.TLabel（灰小字）另起一行。
    st.configure("TLabelframe.Label", background=WIN, foreground=INK,
                 font=FONT_SUBTITLE, padding=(PAD_MD, 0, PAD_MD, 0))
    # v3.13.0 分组标题语义样式（非 Labelframe 场景用）
    st.configure("SectionHeader.TLabel", background=WIN, foreground=INK,
                 font=FONT_SUBTITLE)
    st.configure("SectionHeaderDim.TLabel", background=WIN, foreground=INK_DIM,
                 font=FONT_SMALL)
    # v3.11.0 语义色标签（成功/警告/危险/信息）
    st.configure("Success.TLabel", background=WIN, foreground=tok["feedback.success"], font=FONT_BOLD)
    st.configure("Warning.TLabel", background=WIN, foreground=tok["feedback.warning"], font=FONT_BOLD)
    st.configure("Danger.TLabel", background=WIN, foreground=tok["action.danger"], font=FONT_BOLD)
    st.configure("Info.TLabel", background=WIN, foreground=tok["feedback.info"], font=FONT_BOLD)
    st.configure("Small.TLabel", background=WIN, foreground=INK_DIM, font=FONT_SMALL)
    st.configure("Mono.TLabel", background=WIN, foreground=INK, font=FONT_MONO)
    # v3.14.0 A1：卡片内次要说明（Card body 的 SURFACE 底上灰小字——
    # ScanTab 两卡说明行用；WIN 底场景请用 Small.TLabel）
    st.configure("Dim.TLabel", background=tok["surface.card"],
                 foreground=INK_DIM, font=FONT_SMALL)
    # 卡片式 Frame（卡片底背景，用于内容区突出）
    st.configure("Card.TFrame", background=CARD, relief="solid", borderwidth=1, bordercolor=LINE)
    # v3.12.1 状态栏遮罩带（accent.soft 底 —— 功能板块不再全是纯色背景）
    st.configure("Status.TFrame", background=tok["accent.soft"])
    st.configure("Status.TLabel", background=tok["accent.soft"], foreground=INK,
                 font=FONT_SMALL)
    st.configure("StatusDim.TLabel", background=tok["accent.soft"],
                 foreground=INK_DIM, font=FONT_SMALL)
    st.configure("StatusAccent.TLabel", background=tok["accent.soft"],
                 foreground=ACT, font=FONT_BOLD)
    # v3.13.0 C2.5 玻璃档案：壳层卡（Card/Status）玻璃面板化。
    # 内容区（Treeview/Entry/Text/日志）不在覆盖名单里，恒实心——
    # Liquid Glass 纪律：玻璃只用于导航与控件层，不用于内容层。
    if bstyle == "glass":
        if _is_dark(tok):
            panel = _lighten(CARD, 16)
            stroke = _lighten(WIN, 46)
        else:
            panel = _blend(CARD, "#ffffff", 0.45)
            stroke = _blend(WIN, "#ffffff", 0.65)
        st.configure("Card.TFrame", background=panel, relief="solid",
                     borderwidth=1, bordercolor=stroke)
        st.configure("Status.TFrame", background=panel)
        st.configure("Status.TLabel", background=panel, foreground=INK,
                     font=FONT_SMALL)
        st.configure("StatusDim.TLabel", background=panel, foreground=INK_DIM,
                     font=FONT_SMALL)
        st.configure("StatusAccent.TLabel", background=panel, foreground=ACT,
                     font=FONT_BOLD)
    # v3.12.1 进度条槽用 surface.alt、条身用三色中间色（过渡感）
    st.configure("TProgressbar", background=tok["transition.mid1"],
                 troughcolor=tok["surface.alt"], bordercolor=WIN)
    # 页签内容区（带内边距）
    st.configure("Tab.TFrame", background=WIN)
    # Checkbutton / Radiobutton
    st.configure("TCheckbutton", background=WIN, foreground=INK)
    st.configure("TRadiobutton", background=WIN, foreground=INK)
    st.map("TCheckbutton", background=[("active", WIN)])
    st.map("TRadiobutton", background=[("active", WIN)])

    try:
        root.configure(background=WIN)
    except Exception:
        pass

    # v3.13.0 T2：缓存完整色板（primitive + 派生 + 语义别名超集）
    global _full_pal
    _full_pal = dict(tok)

    # 运行时切换：递归重着色原生 tk 控件（Text / Listbox / Canvas / Entry 等）
    _recolor_native(root, tok)
    return st

def set_theme(root, theme_name):
    """运行时切换主题。ttk 控件自动响应；原生 tk 控件递归重着色。

    切换后建议把 theme_name 写进 cfg["theme"] 并持久化，下次启动自动恢复。
    返回实际应用的主题 key（未知 key 回落默认）。
    """
    name, _ = _resolve_theme(theme_name)
    apply(root, theme_name=name)
    return name


def set_button_style(root, style_name):
    """v3.12.1：运行时切换按钮风格（rounded 圆润 / pixel 像素）。

    重跑 apply()（沿用当前主题），ttk 按钮样式全局生效；
    原生控件不受按钮风格影响，无需重着色。
    切换后建议把 style_name 写进 cfg["button_style"] 并持久化。
    返回实际应用的风格 key（rounded 自动迁移 glass；未知 key 回落默认 pixel）。
    """
    style_name = normalize_button_style(style_name)
    if style_name not in BUTTON_STYLES:
        style_name = DEFAULT_BUTTON_STYLE
    _state["button_style"] = style_name
    apply(root)
    return style_name


def recolor(root):
    """v3.13.0 B1：对「apply 之后才建」的原生控件补跑重着色。

    apply()/_recolor_native 只在装配时跑一次；若 UI 在 apply 之后才建
    （剪映/rename 的 Listbox、Text 等都是 _build_ui 中段才创建），
    后建控件会保留 Windows 默认色（Listbox 选中蓝/白底穿帮）。
    建完 UI 后调一次本函数即可补齐。幂等无害。
    """
    try:
        _recolor_native(root, get_colors())
    except Exception:
        pass


# ── 原生控件重着色（运行时切换的关键）────────────────────────────

_NATIVE_BG_KINDS = (tk.Text, tk.Listbox, tk.Entry, tk.Spinbox, tk.Canvas)
_NATIVE_FG_KINDS = (tk.Text, tk.Listbox, tk.Entry, tk.Spinbox)


def _recolor_native(widget, tok):
    """递归遍历 widget 树，把原生 tk 控件的背景/前景刷成当前主题色。

    v3.13.0 T2：component 层语义化——只引用语义键。
    ttk 控件由 Style 全局驱动，不需碰；只处理 tk.* 原生控件。
    v3.14.0 P0-4：控件带 ``_fixed_colors = True`` 属性 = 「恒色」承诺
    （如剪映运行日志的深底终端风 Text），重着色整棵子树跳过——
    注释不算数，显式标记才算数。
    """
    try:
        if getattr(widget, "_fixed_colors", False):
            return
        cls = widget.winfo_class()
    except Exception:
        return
    # 原生控件类名首字母大写（Text / Listbox / Entry / Canvas / Spinbox）
    # v3.13.0 B1 修复：Listbox 没有 insertbackground 选项（Text/Entry/Spinbox 才有），
    # 旧代码四类共用一套 configure → Listbox 必抛 TclError 被吞 → 从未主题化
    # （Windows 默认白底/蓝选中一直穿帮）。拆开两组。
    if cls == "Listbox":
        try:
            widget.configure(background=tok["surface.card"], foreground=tok["text.primary"],
                             selectbackground=tok["state.selected.bg"],
                             selectforeground=tok["text.primary"],
                             highlightcolor=tok["border.default"],
                             highlightbackground=tok["border.default"])
        except Exception:
            pass
    elif cls in ("Text", "Entry", "Spinbox"):
        try:
            widget.configure(background=tok["surface.card"], foreground=tok["text.primary"],
                             insertbackground=tok["text.primary"],
                             selectbackground=tok["state.selected.bg"],
                             selectforeground=tok["text.primary"],
                             highlightcolor=tok["border.default"],
                             highlightbackground=tok["border.default"])
        except Exception:
            pass
    elif cls == "Canvas":
        try:
            widget.configure(background=tok["surface.window"])
        except Exception:
            pass
    elif cls in ("Frame", "Labelframe", "Toplevel"):
        # 原生 Frame（非 ttk）也刷底色
        try:
            widget.configure(background=tok["surface.window"])
        except Exception:
            pass
    # 递归子控件
    try:
        for child in widget.winfo_children():
            _recolor_native(child, tok)
    except Exception:
        pass


# ── 颜色工具（内部）───────────────────────────────────────────────

def _hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _rgb_to_hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(v))) for v in rgb)


def _lighten(hex_color, amount):
    """向白色靠拢 amount（0-255）。"""
    r, g, b = _hex_to_rgb(hex_color)
    return _rgb_to_hex((r + amount, g + amount, b + amount))


def _darken(hex_color, amount):
    """向黑色靠拢 amount（0-255）。"""
    r, g, b = _hex_to_rgb(hex_color)
    return _rgb_to_hex((r - amount, g - amount, b - amount))


def _is_dark(pal):
    """用 FG 亮度判断主题深浅（FG 亮 = 深色主题）。"""
    r, g, b = _hex_to_rgb(pal["FG"])
    return (0.299 * r + 0.587 * g + 0.114 * b) > 128


def _dim(color, bg):
    """禁用态：把 color 向 bg 混合 55%。"""
    cr, cg, cb = _hex_to_rgb(color)
    br, bg_, bb = _hex_to_rgb(bg)
    return _rgb_to_hex((cr * 0.45 + br * 0.55,
                         cg * 0.45 + bg_ * 0.55,
                         cb * 0.45 + bb * 0.55))


# ── v3.12.0 派生色系统（多层背景，解决配色层次/比例问题）──────────

def _blend(c1, c2, t):
    """公开颜色混合：t=0 全 c1，t=1 全 c2。"""
    a, b = _hex_to_rgb(c1), _hex_to_rgb(c2)
    return _rgb_to_hex(tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3)))


def derived_colors(pal):
    """由基础色板派生多层背景色，返回 {色键: #hex}。

    层次（从底到高）：
      BG → BG_ALT（交替区块）→ SURFACE（卡片）→ SURFACE_ALT（卡片内嵌套）
      → ELEVATED（悬浮/弹窗）；HOVER 为交互悬停层；ACCENT_SOFT 淡强调。
    深色/浅色主题自动取正确方向。
    """
    dark = _is_dark(pal)
    bg, fg = pal["BG"], pal["FG"]
    surf, acc = pal["SURFACE"], pal["ACCENT"]
    # v3.12.1 三色系统：ACCENT_2/ACCENT_3 缺省回落到 ACCENT（老主题兼容）
    a2 = pal.get("ACCENT_2", acc)
    a3 = pal.get("ACCENT_3", a2)
    if dark:
        bg_alt = _blend(bg, fg, 0.045)
        surf_alt = _blend(surf, fg, 0.06)
        elevated = _blend(surf, fg, 0.10)
        hover = _blend(surf, fg, 0.12)
    else:
        bg_alt = _blend(bg, fg, 0.035)
        surf_alt = _blend(surf, fg, 0.045)
        elevated = _blend(surf, "#ffffff", 0.5)
        hover = _blend(surf, acc, 0.10)
    return {
        "BG_ALT": bg_alt,
        "SURFACE_ALT": surf_alt,
        "ELEVATED": elevated,
        "HOVER": hover,
        "ACCENT_SOFT": _blend(acc, bg, 0.85),
        "ACCENT_SOFTER": _blend(acc, bg, 0.92),
        "BORDER_STRONG": _blend(pal["BORDER"], fg, 0.25),
        # v3.12.1 三色过渡：主强调 → 第二强调的中间色 / 第二 → 第三的中间色
        "MID_1": _blend(acc, a2, 0.5),
        "MID_2": _blend(a2, a3, 0.5),
        "ACCENT_2_SOFT": _blend(a2, bg, 0.85),
        "ACCENT_3_SOFT": _blend(a3, bg, 0.88),
    }


# ── v3.13.0 T2：三层 Token 体系（primitive → semantic → component）────
# 设计表：知识库项目12 27号文档。三层分工：
#   primitive  = THEMES 原始色键（16 键，设计师选值，不改名不搬家）
#   semantic   = 下方 SEMANTIC_ALIASES 语义键——组件层只准引用这一层
#   component  = apply() 里的 ttk 样式块（tok["action.primary"] 式引用）
# 层级卫生由 test_theme_geometry 静态断言守护（apply 源码禁现 pal["..."] 直引）。
SEMANTIC_ALIASES = {
    "text.primary":        "FG",
    "text.secondary":      "FG_DIM",
    "surface.window":      "BG",
    "surface.card":        "SURFACE",
    "surface.alt":         "BG_ALT",
    "surface.nested":      "SURFACE_ALT",
    "surface.elevated":    "ELEVATED",
    "surface.hover":       "HOVER",
    "border.default":      "BORDER",
    "border.strong":       "BORDER_STRONG",
    "action.primary":      "ACCENT",
    "action.primary.hover": "ACCENT_HV",
    "action.danger":       "DANGER",
    "action.danger.hover": "DANGER_HV",
    "accent.a2":           "ACCENT_2",
    "accent.a3":           "ACCENT_3",
    "accent.soft":         "ACCENT_SOFT",
    "accent.softer":       "ACCENT_SOFTER",
    "accent2.soft":        "ACCENT_2_SOFT",
    "accent3.soft":        "ACCENT_3_SOFT",
    "transition.mid1":     "MID_1",
    "transition.mid2":     "MID_2",
    "state.selected.bg":   "SELECT_BG",
    "state.header.bg":     "HEAD_BG",
    "feedback.success":    "SUCCESS",
    "feedback.warning":    "WARNING",
    "feedback.info":       "INFO",
}


def tokens(theme_name=None):
    """v3.13.0 T2：取语义 token 全集（primitive + 派生 + 语义别名，扁平 dict）。

    未 apply 过 → 用默认主题。语义键与旧键同值共存（别名），
    widgets.py 等旧调用零改动。text.on.accent 恒白（强调底上的文字）。
    """
    name, pal = _resolve_theme(theme_name or _state["current"])
    tok = dict(pal)
    tok.update(derived_colors(pal))
    for sem, base in SEMANTIC_ALIASES.items():
        if base and base in tok:
            tok[sem] = tok[base]
    tok.setdefault("text.on.accent", "#ffffff")
    return tok


# 全局当前完整色板（primitive + 派生 + 语义别名），供 widgets/界面随时取用
_full_pal = {}


def get_colors():
    """取当前主题完整色板（v3.13.0 T2 起为超集）。

    旧 16 色键 + 11 派生键 + 语义别名键全部在场且同值（别名共存），
    未 apply 时用默认主题。旧调用（widgets.py 等）零改动。
    """
    if not _full_pal:
        return tokens(DEFAULT_THEME)
    return dict(_full_pal)


def color(key, default=None):
    """按色键取当前主题颜色（含派生色）。"""
    return get_colors().get(key, default)


# ── S12：窗口几何（记住上次 + 首次自适应）─────────────────────

def initial_geometry(saved=None, root=None, min_w=MIN_W, min_h=MIN_H):
    """cfg 有记录 → 用记录（钳到 minsize）；无记录 → 按屏幕自适应。

    1920x1080 屏 → 1180x842（比例 1.40）；更大屏幕封顶 1180x860，
    避免 4K 上开出一个占不满也用不上的巨窗。
    """
    if saved:
        m = re.match(r"^\s*(\d+)x(\d+)\s*$", str(saved))
        if m:
            w, h = int(m.group(1)), int(m.group(2))
            return "%dx%d" % (max(w, min_w), max(h, min_h))
    try:
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    except Exception:
        sw, sh = 1920, 1080
    w = min(int(sw * 0.62), 1180)
    h = min(int(sh * 0.78), 860)
    return "%dx%d" % (max(w, min_w), max(h, min_h))


def window_size(win):
    """关闭前取当前尺寸 "WxH"（去掉 "+x+y" 位置部分），失败返回空串。"""
    try:
        return win.geometry().split("+")[0]
    except Exception:
        return ""


# ── 按钮交互增强（S13-v2：图形按钮 + 鼠标交互）──────────────────

def buttonize(root):
    """递归给所有 ttk.Button 加 hand2 光标（悬停变手型）。

    ttk.Button 默认是箭头光标，悬停没有反馈。调用一次后所有按钮
    （含动态创建的子窗口按钮）悬停时变手型，提升可点击感。
    幂等：重复调用无害（已绑定的按钮跳过）。
    """
    def _walk(w):
        try:
            cls = w.winfo_class()
        except Exception:
            return
        if cls in ("TButton", "TCheckbutton", "TRadiobutton", "TMenubutton"):
            try:
                if not getattr(w, "_btn_hand_cursor", False):
                    w.configure(cursor="hand2")
                    w._btn_hand_cursor = True
            except Exception:
                pass
        try:
            for c in w.winfo_children():
                _walk(c)
        except Exception:
            pass
    try:
        root.after(100, lambda: _walk(root))
    except Exception:
        pass


# 常用图标（Unicode 符号，微软雅黑下单色渲染，不引第三方库）
ICON_PLAY = "\u25b6"   # ▶ 播放/导出/执行
ICON_STOP = "\u25a0"   # ■ 停止/中止
ICON_DOWN = "\u2193"   # ↓ 导入/下载
ICON_GEAR = "\u2699"   # ⚙ 设置
ICON_CHECK = "\u2713"  # ✓ 确认/完成
ICON_CROSS = "\u2717"  # ✗ 删除/清空/取消
ICON_PLUS = "\uff0b"   # ＋ 新增/添加
ICON_REFRESH = "\u21bb"  # ↻ 刷新/重新识别
ICON_FOLDER = "\U0001f4c2"  # 📂 打开目录（emoji，Windows 下单色）
ICON_SCAN = "\U0001f50d"    # 🔍 扫描（emoji）
ICON_SAVE = "\U0001f4be"    # 💾 保存（emoji）


def icon(label):
    """给按钮文字加图标前缀。用法：text=theme.icon(theme.ICON_PLAY)+"开始导出" """
    return label + " "



# ── 动态像素粒子背景（S13-v3：视觉增强）──────────────────────────

class ParticleCanvas(tk.Canvas):
    """窗口底层动态背景（v3.14.0 A1 升级：风格分档双模式）。

    mode="pixel"（默认）——像素粒子：
      · 粒子是 2~4px 的小方块（不是圆点），契合"像素粒子"需求
      · 低干扰——粒子用主题色的低饱和变体，慢速漂浮 + 渐入渐出，不抢内容视线
      · 默认 30 粒子 / 25fps
    mode="glass" —— 水波纹（裁决 14-6④：玻璃 UI 用液态动效表达，替代调色模拟）：
      · 低对比波纹圈从随机点缓慢扩散、渐隐（≈16fps）
      · 波纹色 = 强调色低干扰变体（浅色主题压暗 / 深色主题提亮）

    共有纪律：
      · 性能友好——窗口最小化时自动暂停；cfg["particle_bg"]=False 可整体关闭
      · 主题感知——深浅主题自动切换前景色
    用法（在 _build_ui 最开始、所有控件之前）：
        self.particle = ParticleCanvas(self, enabled=cfg.get("particle_bg", True),
                                       mode=cfg.get("particle_mode", "pixel"))
        self.particle.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.particle.lower()
    切风格档案时：self.particle.set_mode("glass" | "pixel")
    """

    PARTICLE_COUNT = 30      # 粒子数量（pixel 模式）
    TICK_MS = 40             # 25fps（pixel 模式）
    SIZE_MIN, SIZE_MAX = 2, 4  # 粒子尺寸（px，像素方块）
    SPEED_MAX = 0.6          # 最大漂移速度（px/tick）
    LIFE_MIN, LIFE_MAX = 120, 300  # 生命周期（tick 数）
    WAVE_MS = 80             # ≈12.5fps（glass 模式；15-6b：60→80 更缓）
    WAVE_MAX = 3             # 同屏波纹圈上限（15-6b：6→3，背景只留隐约水影）
    WAVE_R0, WAVE_R1 = 6, 140      # 波纹圈半径起止
    WAVE_GROW = 1.4          # 每帧扩散像素（15-6b：2.2→1.4 慢速液态感）

    def __init__(self, master, enabled=True, theme_name=None, mode=None):
        super().__init__(master, highlightthickness=0, bd=0)
        self._enabled = enabled
        self._theme_name = theme_name or DEFAULT_THEME
        self._mode = mode or "pixel"
        self._particles = []
        self._waves = []
        self._job = None
        self._paused = False
        if enabled:
            self._configure_bg()
            if self._mode == "glass":
                self._spawn_wave_initial()
            else:
                self._spawn_initial()
            self._start()
            # 窗口最小化/恢复时暂停/继续
            try:
                self.bind("<Unmap>", lambda _e: self._pause())
                self.bind("<Map>", lambda _e: self._resume())
            except Exception:
                pass

    def set_mode(self, mode):
        """切换背景动效模式（pixel=方块粒子 / glass=水波纹）。幂等安全。"""
        mode = "glass" if mode == "glass" else "pixel"
        if mode == self._mode:
            return
        self._mode = mode
        # 清空旧内容
        for p in self._particles:
            try:
                self.delete(p["id"])
            except Exception:
                pass
        self._particles = []
        for w in self._waves:
            try:
                self.delete(w["id"])
            except Exception:
                pass
        self._waves = []
        if not self._enabled:
            return
        self._configure_bg()
        if mode == "glass":
            self._spawn_wave_initial()
        else:
            self._spawn_initial()
        # 重启帧循环（两模式帧率不同）
        if self._job:
            try:
                self.after_cancel(self._job)
            except Exception:
                pass
            self._job = None
        if not self._paused:
            self._start()

    def _configure_bg(self):
        """根据主题设置画布背景色和前景调色板。"""
        pal = THEMES.get(self._theme_name, THEMES[DEFAULT_THEME])
        try:
            self.configure(background=pal["BG"])
        except Exception:
            pass
        dark = _is_dark(pal)
        if self._mode == "glass":
            # 15-6b：背景波纹改「近底色中性水痕」——波纹主舞台在卡片头部条
            # （GlassCard._tick），背景只留一层隐约水影；accent 红圈压文字
            # （横幅/页签/状态栏上飞弧）的历史到此为止
            base = pal["BG"]
            if dark:
                self._colors = [
                    _lighten(base, 10),
                    _lighten(base, 18),
                ]
            else:
                self._colors = [
                    _darken(base, 7),
                    _darken(base, 12),
                ]
        elif dark:
            self._colors = [
                _lighten(pal["ACCENT"], 30),
                _lighten(pal["FG_DIM"], 20),
                _lighten(pal["SELECT_BG"], 10),
            ]
        else:
            self._colors = [
                _darken(pal["ACCENT"], 10),
                pal["FG_DIM"],
                _darken(pal["SELECT_BG"], 5),
            ]

    def set_theme(self, theme_name):
        """切换主题时更新背景色和前景颜色。"""
        self._theme_name = theme_name
        self._configure_bg()
        # 更新已有粒子颜色
        for p in self._particles:
            try:
                self.itemconfig(p["id"], fill=p["color"])
            except Exception:
                pass
        # glass 模式：波纹圈直接清空重铺（颜色随新主题）
        if self._mode == "glass":
            for w in self._waves:
                try:
                    self.delete(w["id"])
                except Exception:
                    pass
            self._waves = []
            self._spawn_wave_initial()

    def _spawn_initial(self):
        """初始生成粒子（随机位置和生命周期）。"""
        try:
            w = max(self.winfo_width(), 800)
            h = max(self.winfo_height(), 600)
        except Exception:
            w, h = 800, 600
        import random
        for _ in range(self.PARTICLE_COUNT):
            self._spawn_one(x=random.uniform(0, w), y=random.uniform(0, h),
                            initial_life=True)

    def _spawn_one(self, x=None, y=None, initial_life=False):
        """生成一个新粒子。"""
        import random
        try:
            w = max(self.winfo_width(), 800)
            h = max(self.winfo_height(), 600)
        except Exception:
            w, h = 800, 600
        if x is None:
            x = random.uniform(0, w)
        if y is None:
            y = random.uniform(0, h)
        size = random.randint(self.SIZE_MIN, self.SIZE_MAX)
        color = random.choice(self._colors)
        max_life = random.randint(self.LIFE_MIN, self.LIFE_MAX)
        life = random.randint(0, max_life) if initial_life else 0
        # 速度：慢速漂浮，带轻微向上倾向
        angle = random.uniform(0, 6.283)
        speed = random.uniform(0.1, self.SPEED_MAX)
        vx = speed * 0.4  # 水平漂移慢
        vy = -speed * 0.6  # 轻微向上飘
        item = self.create_rectangle(x, y, x + size, y + size,
                                      fill=color, outline="", width=0)
        self._particles.append({
            "id": item, "x": x, "y": y, "vx": vx, "vy": vy,
            "size": size, "color": color, "life": life, "max_life": max_life,
        })

    def _tick(self):
        """动画帧：更新所有粒子位置和生命周期。"""
        if not self._enabled or self._paused:
            return
        if self._mode == "glass":
            self._wave_tick()
            return
        try:
            w = max(self.winfo_width(), 100)
            h = max(self.winfo_height(), 100)
        except Exception:
            w, h = 800, 600

        alive = []
        for p in self._particles:
            p["life"] += 1
            if p["life"] >= p["max_life"]:
                # 粒子死亡：删除并在底部生成新的
                try:
                    self.delete(p["id"])
                except Exception:
                    pass
                continue
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            # 边界环绕
            if p["x"] < -10:
                p["x"] = w + 5
            elif p["x"] > w + 10:
                p["x"] = -5
            if p["y"] < -10:
                p["y"] = h + 5
            elif p["y"] > h + 10:
                p["y"] = -5
            # 渐入渐出：生命前 15% 和后 15% 改变透明度（用颜色深浅模拟）
            fade_ratio = 1.0
            fade_in = int(p["max_life"] * 0.15)
            fade_out = int(p["max_life"] * 0.85)
            if p["life"] < fade_in:
                fade_ratio = p["life"] / max(fade_in, 1)
            elif p["life"] > fade_out:
                fade_ratio = (p["max_life"] - p["life"]) / max(p["max_life"] - fade_out, 1)
            # 用 move 移动（比 coords 快）
            try:
                self.move(p["id"], p["vx"], p["vy"])
            except Exception:
                pass
            alive.append(p)

        self._particles = alive
        # 补充死亡的粒子
        while len(self._particles) < self.PARTICLE_COUNT:
            self._spawn_one(y=max(self.winfo_height() - 10, 100))

        self._job = self.after(self.TICK_MS, self._tick)

    def _start(self):
        if self._job is None and self._enabled:
            self._job = self.after(
                self.WAVE_MS if self._mode == "glass" else self.TICK_MS, self._tick)

    # ── glass 模式：水波纹扩散圈（裁决 14-6④）──

    def _wave_bounds(self):
        try:
            return (max(self.winfo_width(), 800), max(self.winfo_height(), 600))
        except Exception:
            return (800, 600)

    def _spawn_wave_initial(self):
        """初始铺 2 个不同进度的波纹圈（避免开局全空白）。"""
        import random
        w, h = self._wave_bounds()
        for _ in range(2):
            self._spawn_wave(x=random.uniform(0.1 * w, 0.9 * w),
                             y=random.uniform(0.1 * h, 0.9 * h))

    def _spawn_wave(self, x=None, y=None):
        import random
        w, h = self._wave_bounds()
        if x is None:
            x = random.uniform(0.05 * w, 0.95 * w)
        if y is None:
            y = random.uniform(0.05 * h, 0.95 * h)
        color = random.choice(self._colors)
        # 15-6b：width 2→1 细线水痕（1px 才有「隐约」感）
        oid = self.create_oval(x, y, x, y, outline=color, width=1)
        self._waves.append({"id": oid, "x": x, "y": y, "r": self.WAVE_R0,
                            "color": color})

    def _wave_tick(self):
        alive = []
        for wv in self._waves:
            wv["r"] += self.WAVE_GROW
            if wv["r"] >= self.WAVE_R1:
                try:
                    self.delete(wv["id"])
                except Exception:
                    pass
                continue
            r = wv["r"]
            try:
                self.coords(wv["id"], wv["x"] - r, wv["y"] - r,
                            wv["x"] + r, wv["y"] + r)
            except Exception:
                pass
            alive.append(wv)
        self._waves = alive
        # 补圈：同屏上限内，稀疏生成（15-6b：0.20→0.10 更疏）
        if len(self._waves) < self.WAVE_MAX:
            import random
            if random.random() < 0.10:
                self._spawn_wave()
        self._job = self.after(self.WAVE_MS, self._wave_tick)

    def _pause(self):
        self._paused = True
        if self._job:
            try:
                self.after_cancel(self._job)
            except Exception:
                pass
            self._job = None

    def _resume(self):
        if self._paused and self._enabled:
            self._paused = False
            self._start()

    def destroy(self):
        self._pause()
        self._particles = []
        try:
            super().destroy()
        except Exception:
            pass
