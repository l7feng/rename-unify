# -*- coding: utf-8 -*-
"""自绘组件库（v3.12.0）—— Canvas 矢量图标 + 现代控件，突破 tkinter 原生视觉瓶颈。

同源三副本（与 theme.py 相同规则）：
  ① src/pt-tools/ptools/gui/widgets.py     ← 权威源
  ② src/rename-unify/code/widgets.py        ← 整文件复制
  ③ src/jianying-draft-toolkit/code/widgets.py ← 整文件复制

组件清单：
  · draw_icon()      矢量图标绘制（30+ 图标，24x24 线条风格，主题感知）
  · IconButton       Canvas 图标按钮（图标+文字，hover/press 反馈）
  · ToggleSwitch     iOS 风格开关（滑动动画）
  · StatusLED        状态指示灯（呼吸动画）
  · Badge            徽章标签
  · ProgressRing     圆形进度环
  · Tooltip          工具提示气泡
  · CollapsibleFrame 可折叠面板（chevron 旋转）
  · HoverCard        可点击卡片（hover 高亮 + hand2）
  · SideNav          侧边垂直导航栏（图标+文字，选中态）
  · Segmented        分段控制器（v3.14.0 升级：按钮/悬浮/选中三态）
  · GlassCard        玻璃卡（壳混白+白描边+顶缘高光+圆角，内容恒实心）
  · PixelCard        像素卡（直角+1.5px 描边+顶缘 4px 高光，无阴影）
  · PixelButton      像素按钮（直角+深描边+顶缘高光条，primary/danger/次级）
  · attach_tree_hover()  Treeview 行 hover 高亮
  · attach_drop_highlight() 拖拽区域高亮
"""
import tkinter as tk
from tkinter import ttk
try:
    from theme import current_theme_name, current_button_style, THEMES, FONT_BODY, \
        FONT_BOLD, FONT_SMALL, FONT_SUBTITLE, FONT_TITLE, \
        PAD_XS, PAD_SM, PAD_MD, PAD_LG, PAD_XL
except ImportError:  # pt-tools 包结构
    from ptools.gui.theme import (current_theme_name, current_button_style, THEMES,
        FONT_BODY, FONT_BOLD, FONT_SMALL, FONT_SUBTITLE, FONT_TITLE,
        PAD_XS, PAD_SM, PAD_MD, PAD_LG, PAD_XL)


# ══════════════════════════════════════════════════════════════════
# 配色辅助（跟随当前主题）
# ══════════════════════════════════════════════════════════════════

def _measure_text(font_desc, text):
    """测量文字像素宽度（不依赖可见窗口）。"""
    if not text:
        return 0
    try:
        from tkinter import font as _tkfont
        return int(_tkfont.Font(font=font_desc).measure(text))
    except Exception:
        return len(text) * 8


def _pal():
    """取当前主题完整色板（基础 + 派生色），未 apply 时回落 warm。"""
    try:
        try:
            from theme import get_colors
        except ImportError:
            from ptools.gui.theme import get_colors
        return get_colors()
    except Exception:
        name = current_theme_name() or "warm"
        return dict(THEMES.get(name, THEMES["warm"]))


def _mix(c1, c2, t):
    """颜色混合：t=0 全 c1，t=1 全 c2。"""
    def hx(h):
        h = h.lstrip("#")
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
    a, b = hx(c1), hx(c2)
    return "#%02x%02x%02x" % tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


# ══════════════════════════════════════════════════════════════════
# 矢量图标系统（24x24 线条风格，参考 Lucide/Feather）
# ══════════════════════════════════════════════════════════════════
# 每个 _ic_xxx(cv, x, y, s, color, w) 在 cv 的 (x,y) 处绘制尺寸 s 的图标，
# 返回 item id 列表。坐标基于 0..24，绘制时按 s/24 缩放。

def _pts(points, x, y, s):
    """把 24 网格坐标点缩放到实际像素。"""
    k = s / 24.0
    return [x + p * k if i % 2 == 0 else y + p * k
            for i, p in enumerate(points)]


def _ic_play(cv, x, y, s, c, w):
    return [cv.create_polygon(_pts([7, 5, 19, 12, 7, 19], x, y, s),
                              fill=c, outline=c, width=w)]


def _ic_square(cv, x, y, s, c, w):
    p = _pts([7, 7, 17, 7, 17, 17, 7, 17], x, y, s)
    return [cv.create_polygon(p, fill=c, outline=c)]


def _ic_pause(cv, x, y, s, c, w):
    p1 = _pts([8, 6, 10, 6, 10, 18, 8, 18], x, y, s)
    p2 = _pts([14, 6, 16, 6, 16, 18, 14, 18], x, y, s)
    return [cv.create_polygon(p1, fill=c), cv.create_polygon(p2, fill=c)]


def _ic_folder(cv, x, y, s, c, w):
    k = s / 24.0
    items = [cv.create_polygon(
        _pts([3, 7, 9, 7, 11, 9, 21, 9, 21, 18, 3, 18], x, y, s),
        outline=c, fill="", width=w, joinstyle=tk.ROUND)]
    return items


def _ic_search(cv, x, y, s, c, w):
    k = s / 24.0
    r = 6 * k
    cx, cy = x + 10 * k, y + 10 * k
    items = [cv.create_oval(cx - r, cy - r, cx + r, cy + r, outline=c, width=w),
             cv.create_line(x + 15 * k, y + 15 * k, x + 20 * k, y + 20 * k,
                            fill=c, width=w, capstyle=tk.ROUND)]
    return items


def _ic_gear(cv, x, y, s, c, w):
    import math
    k = s / 24.0
    cx, cy = x + 12 * k, y + 12 * k
    items = []
    # 8 齿
    teeth = []
    for i in range(16):
        ang = math.pi / 8 * i
        rr = (9 if i % 2 == 0 else 7) * k
        teeth.extend([cx + rr * math.cos(ang), cy + rr * math.sin(ang)])
    items.append(cv.create_polygon(teeth, outline=c, fill="", width=w,
                                   smooth=False))
    items.append(cv.create_oval(cx - 3.5 * k, cy - 3.5 * k,
                                cx + 3.5 * k, cy + 3.5 * k, outline=c, width=w))
    return items


def _ic_plus(cv, x, y, s, c, w):
    k = s / 24.0
    return [cv.create_line(x + 12 * k, y + 5 * k, x + 12 * k, y + 19 * k,
                           fill=c, width=w, capstyle=tk.ROUND),
            cv.create_line(x + 5 * k, y + 12 * k, x + 19 * k, y + 12 * k,
                           fill=c, width=w, capstyle=tk.ROUND)]


def _ic_minus(cv, x, y, s, c, w):
    k = s / 24.0
    return [cv.create_line(x + 5 * k, y + 12 * k, x + 19 * k, y + 12 * k,
                           fill=c, width=w, capstyle=tk.ROUND)]


def _ic_trash(cv, x, y, s, c, w):
    k = s / 24.0
    items = [
        cv.create_line(x + 4 * k, y + 7 * k, x + 20 * k, y + 7 * k,
                       fill=c, width=w, capstyle=tk.ROUND),
        cv.create_polygon(_pts([7, 7, 17, 7, 16, 20, 8, 20], x, y, s),
                          outline=c, fill="", width=w, joinstyle=tk.ROUND),
        cv.create_line(x + 10 * k, y + 4 * k, x + 14 * k, y + 4 * k,
                       fill=c, width=w, capstyle=tk.ROUND),
        cv.create_line(x + 10 * k, y + 11 * k, x + 10 * k, y + 17 * k, fill=c, width=w),
        cv.create_line(x + 14 * k, y + 11 * k, x + 14 * k, y + 17 * k, fill=c, width=w)]
    return items


def _ic_refresh(cv, x, y, s, c, w):
    k = s / 24.0
    items = [cv.create_arc(x + 4 * k, y + 4 * k, x + 20 * k, y + 20 * k,
                           start=30, extent=280, style=tk.ARC, outline=c, width=w)]
    # 箭头
    items.append(cv.create_polygon(
        _pts([19, 3, 21, 8, 16, 8], x, y, s), fill=c))
    return items


def _ic_download(cv, x, y, s, c, w):
    k = s / 24.0
    return [
        cv.create_line(x + 12 * k, y + 4 * k, x + 12 * k, y + 15 * k,
                       fill=c, width=w, capstyle=tk.ROUND),
        cv.create_line(x + 7 * k, y + 11 * k, x + 12 * k, y + 16 * k,
                       x + 17 * k, y + 11 * k, fill=c, width=w,
                       capstyle=tk.ROUND, joinstyle=tk.ROUND),
        cv.create_line(x + 5 * k, y + 20 * k, x + 19 * k, y + 20 * k,
                       fill=c, width=w, capstyle=tk.ROUND)]


def _ic_upload(cv, x, y, s, c, w):
    k = s / 24.0
    return [
        cv.create_line(x + 12 * k, y + 15 * k, x + 12 * k, y + 4 * k,
                       fill=c, width=w, capstyle=tk.ROUND),
        cv.create_line(x + 7 * k, y + 8 * k, x + 12 * k, y + 3 * k,
                       x + 17 * k, y + 8 * k, fill=c, width=w,
                       capstyle=tk.ROUND, joinstyle=tk.ROUND),
        cv.create_line(x + 5 * k, y + 20 * k, x + 19 * k, y + 20 * k,
                       fill=c, width=w, capstyle=tk.ROUND)]


def _ic_check(cv, x, y, s, c, w):
    k = s / 24.0
    return [cv.create_line(x + 5 * k, y + 12.5 * k, x + 10 * k, y + 18 * k,
                           x + 19 * k, y + 6 * k, fill=c, width=w,
                           capstyle=tk.ROUND, joinstyle=tk.ROUND)]


def _ic_x(cv, x, y, s, c, w):
    k = s / 24.0
    return [cv.create_line(x + 6 * k, y + 6 * k, x + 18 * k, y + 18 * k,
                           fill=c, width=w, capstyle=tk.ROUND),
            cv.create_line(x + 18 * k, y + 6 * k, x + 6 * k, y + 18 * k,
                           fill=c, width=w, capstyle=tk.ROUND)]


def _ic_chevron_down(cv, x, y, s, c, w):
    k = s / 24.0
    return [cv.create_line(x + 6 * k, y + 10 * k, x + 12 * k, y + 16 * k,
                           x + 18 * k, y + 10 * k, fill=c, width=w,
                           capstyle=tk.ROUND, joinstyle=tk.ROUND)]


def _ic_chevron_right(cv, x, y, s, c, w):
    k = s / 24.0
    return [cv.create_line(x + 10 * k, y + 6 * k, x + 16 * k, y + 12 * k,
                           x + 10 * k, y + 18 * k, fill=c, width=w,
                           capstyle=tk.ROUND, joinstyle=tk.ROUND)]


def _ic_music(cv, x, y, s, c, w):
    k = s / 24.0
    return [
        cv.create_line(x + 9 * k, y + 18 * k, x + 9 * k, y + 6 * k,
                       x + 18 * k, y + 4 * k, x + 18 * k, y + 15 * k,
                       fill=c, width=w, capstyle=tk.ROUND, joinstyle=tk.ROUND),
        cv.create_oval(x + 6 * k, y + 16 * k, x + 10 * k, y + 20 * k,
                       outline=c, width=w),
        cv.create_oval(x + 15 * k, y + 13 * k, x + 19 * k, y + 17 * k,
                       outline=c, width=w)]


def _ic_scissors(cv, x, y, s, c, w):
    k = s / 24.0
    items = [
        cv.create_line(x + 6 * k, y + 9 * k, x + 20 * k, y + 18 * k, fill=c, width=w),
        cv.create_line(x + 6 * k, y + 15 * k, x + 20 * k, y + 6 * k, fill=c, width=w),
        cv.create_oval(x + 4 * k, y + 7 * k, x + 8 * k, y + 11 * k, outline=c, width=w),
        cv.create_oval(x + 4 * k, y + 13 * k, x + 8 * k, y + 17 * k, outline=c, width=w)]
    return items


def _ic_database(cv, x, y, s, c, w):
    k = s / 24.0
    items = [
        cv.create_oval(x + 5 * k, y + 5 * k, x + 19 * k, y + 9 * k, outline=c, width=w),
        cv.create_line(x + 5 * k, y + 7 * k, x + 5 * k, y + 18 * k, fill=c, width=w),
        cv.create_line(x + 19 * k, y + 7 * k, x + 19 * k, y + 18 * k, fill=c, width=w),
        cv.create_oval(x + 5 * k, y + 14 * k, x + 19 * k, y + 18 * k, outline=c, width=w)]
    return items


def _ic_home(cv, x, y, s, c, w):
    k = s / 24.0
    return [cv.create_polygon(
        _pts([4, 11, 12, 4, 20, 11, 20, 20, 4, 20], x, y, s),
        outline=c, fill="", width=w, joinstyle=tk.ROUND)]


def _ic_file(cv, x, y, s, c, w):
    k = s / 24.0
    return [cv.create_polygon(
        _pts([6, 3, 14, 3, 18, 7, 18, 21, 6, 21], x, y, s),
        outline=c, fill="", width=w, joinstyle=tk.ROUND),
        cv.create_line(x + 14 * k, y + 3 * k, x + 14 * k, y + 7 * k,
                       x + 18 * k, y + 7 * k, fill=c, width=w)]


def _ic_alert(cv, x, y, s, c, w):
    k = s / 24.0
    return [
        cv.create_polygon(_pts([12, 3, 22, 20, 2, 20], x, y, s),
                          outline=c, fill="", width=w, joinstyle=tk.ROUND),
        cv.create_line(x + 12 * k, y + 10 * k, x + 12 * k, y + 14 * k,
                       fill=c, width=w, capstyle=tk.ROUND),
        cv.create_oval(x + 12 * k - 0.5, y + 17 * k - 0.5,
                       x + 12 * k + 0.5, y + 17 * k + 0.5, fill=c)]


def _ic_info(cv, x, y, s, c, w):
    k = s / 24.0
    return [
        cv.create_oval(x + 3 * k, y + 3 * k, x + 21 * k, y + 21 * k,
                       outline=c, width=w),
        cv.create_line(x + 12 * k, y + 11 * k, x + 12 * k, y + 17 * k,
                       fill=c, width=w, capstyle=tk.ROUND),
        cv.create_oval(x + 12 * k - 0.5, y + 7.5 * k - 0.5,
                       x + 12 * k + 0.5, y + 7.5 * k + 0.5, fill=c)]


def _ic_sun(cv, x, y, s, c, w):
    import math
    k = s / 24.0
    cx, cy = x + 12 * k, y + 12 * k
    items = [cv.create_oval(cx - 4 * k, cy - 4 * k, cx + 4 * k, cy + 4 * k,
                            outline=c, width=w)]
    for i in range(8):
        a = math.pi / 4 * i
        items.append(cv.create_line(
            cx + 6 * k * math.cos(a), cy + 6 * k * math.sin(a),
            cx + 9 * k * math.cos(a), cy + 9 * k * math.sin(a),
            fill=c, width=w, capstyle=tk.ROUND))
    return items


def _ic_moon(cv, x, y, s, c, w):
    k = s / 24.0
    return [cv.create_polygon(
        _pts([20, 14, 13, 20, 6, 18, 12, 12, 8, 4, 16, 6, 20, 10], x, y, s),
        outline=c, fill="", width=w, smooth=True, joinstyle=tk.ROUND)]


def _ic_eye(cv, x, y, s, c, w):
    k = s / 24.0
    return [
        cv.create_polygon(_pts([2, 12, 7, 6, 12, 5, 17, 6, 22, 12, 17, 18, 12, 19, 7, 18], x, y, s),
                          outline=c, fill="", width=w, smooth=True),
        cv.create_oval(x + 9.5 * k, y + 9.5 * k, x + 14.5 * k, y + 14.5 * k,
                       outline=c, width=w)]


def _ic_edit(cv, x, y, s, c, w):
    k = s / 24.0
    return [
        cv.create_polygon(_pts([15, 4, 20, 9, 9, 20, 4, 20, 4, 15], x, y, s),
                          outline=c, fill="", width=w, joinstyle=tk.ROUND),
        cv.create_line(x + 13 * k, y + 6 * k, x + 18 * k, y + 11 * k,
                       fill=c, width=w)]


def _ic_zap(cv, x, y, s, c, w):
    return [cv.create_polygon(_pts([13, 2, 4, 14, 11, 14, 10, 22, 20, 10, 13, 10], x, y, s),
                              fill=c, outline=c)]


def _ic_clock(cv, x, y, s, c, w):
    k = s / 24.0
    return [
        cv.create_oval(x + 4 * k, y + 4 * k, x + 20 * k, y + 20 * k,
                       outline=c, width=w),
        cv.create_line(x + 12 * k, y + 12 * k, x + 12 * k, y + 7 * k, fill=c, width=w),
        cv.create_line(x + 12 * k, y + 12 * k, x + 16 * k, y + 12 * k, fill=c, width=w)]


def _ic_layers(cv, x, y, s, c, w):
    k = s / 24.0
    return [
        cv.create_polygon(_pts([12, 3, 21, 8, 12, 13, 3, 8], x, y, s),
                          outline=c, fill="", width=w, joinstyle=tk.ROUND),
        cv.create_polygon(_pts([3, 12, 12, 17, 21, 12], x, y, s),
                          outline=c, fill="", width=w, joinstyle=tk.ROUND),
        cv.create_polygon(_pts([3, 16, 12, 21, 21, 16], x, y, s),
                          outline=c, fill="", width=w, joinstyle=tk.ROUND)]


def _ic_grid(cv, x, y, s, c, w):
    k = s / 24.0
    return [
        cv.create_rectangle(x + 4 * k, y + 4 * k, x + 10 * k, y + 10 * k, outline=c, width=w),
        cv.create_rectangle(x + 14 * k, y + 4 * k, x + 20 * k, y + 10 * k, outline=c, width=w),
        cv.create_rectangle(x + 4 * k, y + 14 * k, x + 10 * k, y + 20 * k, outline=c, width=w),
        cv.create_rectangle(x + 14 * k, y + 14 * k, x + 20 * k, y + 20 * k, outline=c, width=w)]


def _ic_list(cv, x, y, s, c, w):
    k = s / 24.0
    items = []
    for i, yy in enumerate([6, 12, 18]):
        items.append(cv.create_oval(x + 5 * k - 1, y + yy * k - 1,
                                    x + 5 * k + 1, y + yy * k + 1, fill=c))
        items.append(cv.create_line(x + 9 * k, y + yy * k, x + 19 * k, y + yy * k,
                                    fill=c, width=w, capstyle=tk.ROUND))
    return items


def _ic_filter(cv, x, y, s, c, w):
    return [cv.create_polygon(_pts([3, 5, 21, 5, 14, 13, 14, 20, 10, 18, 10, 13], x, y, s),
                              outline=c, fill="", width=w, joinstyle=tk.ROUND)]


def _ic_save(cv, x, y, s, c, w):
    k = s / 24.0
    return [
        cv.create_polygon(_pts([4, 4, 17, 4, 20, 7, 20, 20, 4, 20], x, y, s),
                          outline=c, fill="", width=w, joinstyle=tk.ROUND),
        cv.create_rectangle(x + 8 * k, y + 4 * k, x + 16 * k, y + 10 * k,
                            outline=c, width=w),
        cv.create_rectangle(x + 8 * k, y + 14 * k, x + 16 * k, y + 20 * k,
                            outline=c, width=w)]


def _ic_wand(cv, x, y, s, c, w):
    k = s / 24.0
    items = [cv.create_line(x + 5 * k, y + 19 * k, x + 15 * k, y + 9 * k,
                            fill=c, width=w, capstyle=tk.ROUND)]
    for dx, dy in [(17, 5), (19, 9), (14, 3), (9, 3)]:
        items.append(cv.create_line(x + (dx - 1.5) * k, y + dy * k,
                                    x + (dx + 1.5) * k, y + dy * k, fill=c, width=w))
        items.append(cv.create_line(x + dx * k, y + (dy - 1.5) * k,
                                    x + dx * k, y + (dy + 1.5) * k, fill=c, width=w))
    return items


# 图标名 → 绘制函数
ICONS = {
    "play": _ic_play, "square": _ic_square, "pause": _ic_pause,
    "folder": _ic_folder, "search": _ic_search, "gear": _ic_gear,
    "plus": _ic_plus, "minus": _ic_minus, "trash": _ic_trash,
    "refresh": _ic_refresh, "download": _ic_download, "upload": _ic_upload,
    "check": _ic_check, "x": _ic_x,
    "chevron-down": _ic_chevron_down, "chevron-right": _ic_chevron_right,
    "music": _ic_music, "scissors": _ic_scissors, "database": _ic_database,
    "home": _ic_home, "file": _ic_file, "alert": _ic_alert, "info": _ic_info,
    "sun": _ic_sun, "moon": _ic_moon, "eye": _ic_eye, "edit": _ic_edit,
    "zap": _ic_zap, "clock": _ic_clock, "layers": _ic_layers,
    "grid": _ic_grid, "list": _ic_list, "filter": _ic_filter,
    "save": _ic_save, "wand": _ic_wand,
}


def draw_icon(cv, name, x, y, size=18, color=None, width=2):
    """在 Canvas 上绘制矢量图标。
    cv: Canvas；name: ICONS 中的图标名；x,y: 左上角；size: 像素尺寸。
    返回 item id 列表（图标未注册返回空列表）。
    """
    fn = ICONS.get(name)
    if fn is None:
        return []
    c = color or _pal()["FG"]
    try:
        return fn(cv, x, y, size, c, width)
    except Exception:
        return []


# ══════════════════════════════════════════════════════════════════
# IconButton —— Canvas 图标按钮
# ══════════════════════════════════════════════════════════════════

class IconButton(tk.Canvas):
    """Canvas 自绘图标按钮（图标 + 可选文字），带 hover/press 视觉反馈。

    用法：
        btn = IconButton(parent, icon="play", text="开始", command=fn,
                         primary=True)
        btn.pack()
    primary=True 时用强调色填充（主按钮）；否则透明/浅底（次按钮）。
    danger=True 时红色填充。
    """

    def __init__(self, master, icon=None, text="", command=None,
                 primary=False, danger=False, icon_size=16,
                 bg=None, fg=None, font=None, padx=12, pady=7, **kw):
        pal = _pal()
        self._bg_base = bg or pal["BG"]
        self._primary = primary
        self._danger = danger
        if primary:
            self._fill = pal["ACCENT"]
            self._fill_hv = pal["ACCENT_HV"]
            self._fg = "#ffffff"
        elif danger:
            self._fill = pal["DANGER"]
            self._fill_hv = pal["DANGER_HV"]
            self._fg = "#ffffff"
        else:
            self._fill = pal["SURFACE"]
            self._fill_hv = _mix(pal["SURFACE"], pal["FG"], 0.08)
            self._fg = fg or pal["FG"]
        self._icon_name = icon
        self._icon_size = icon_size
        self._text = text
        self._command = command
        self._font = font or FONT_BOLD
        self._px, self._py = padx, pady
        self._pressed = False
        self._hover = False

        # 先测量文字宽度
        tw = _measure_text(self._font, text)

        iw = icon_size + (6 if text else 0) if icon else 0
        w = self._px * 2 + iw + tw
        h = self._py * 2 + max(icon_size, 16)
        tk.Canvas.__init__(self, master, width=w, height=h,
                          bg=self._bg_base, highlightthickness=0, bd=0, **kw)
        self._cw, self._h = w, h
        self._draw()
        self.configure(cursor="hand2")
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)

    def _draw(self):
        self.delete("all")
        fill = self._fill_hv if (self._hover or self._pressed) else self._fill
        if self._pressed:
            fill = self._fill_hv
        r = 8
        # 按钮背景（圆角矩形，用多边形近似）
        if self._primary or self._danger or self._hover:
            self._round_rect(1, 1, self._cw - 1, self._h - 1, r,
                             fill=fill, outline="")
        else:
            self._round_rect(1, 1, self._cw - 1, self._h - 1, r,
                             fill=fill, outline=_pal()["BORDER"])
        cx = self._px
        cy = (self._h - self._icon_size) / 2
        if self._icon_name:
            draw_icon(self, self._icon_name, cx, cy,
                      size=self._icon_size, color=self._fg, width=2)
            cx += self._icon_size + 6
        if self._text:
            ty = self._h / 2
            self.create_text(cx, ty, text=self._text, fill=self._fg,
                             font=self._font, anchor="w")

    def _round_rect(self, x1, y1, x2, y2, r, **kw):
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
               x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2, x1, y2,
               x1, y2 - r, x1, y1 + r, x1, y1]
        return self.create_polygon(pts, smooth=True, **kw)

    def _on_enter(self, e):
        self._hover = True
        self._draw()

    def _on_leave(self, e):
        self._hover = False
        self._pressed = False
        self._draw()

    def _on_press(self, e):
        self._pressed = True
        self._draw()

    def _on_release(self, e):
        was = self._pressed
        self._pressed = False
        self._draw()
        if was and self._command:
            self._command()

    def set_command(self, fn):
        self._command = fn

    def configure_text(self, text=None, icon=None):
        if text is not None:
            self._text = text
        if icon is not None:
            self._icon_name = icon
        self._draw()


# ══════════════════════════════════════════════════════════════════
# ToggleSwitch —— iOS 风格开关（滑动动画）
# ══════════════════════════════════════════════════════════════════

class ToggleSwitch(tk.Canvas):
    """iOS 风格开关，点击平滑滑动。sw.get() / sw.set(bool)。"""

    def __init__(self, master, value=False, command=None, bg=None,
                 width=44, height=24, **kw):
        pal = _pal()
        self._bg = bg or pal["BG"]
        self._on_color = pal["SUCCESS"]
        self._off_color = _mix(pal["FG"], pal["BG"], 0.7)
        self._value = bool(value)
        self._command = command
        self._cw, self._h = width, height
        tk.Canvas.__init__(self, master, width=width, height=height,
                           bg=self._bg, highlightthickness=0, bd=0, **kw)
        self.configure(cursor="hand2")
        self.bind("<ButtonRelease-1>", self._toggle)
        self._knob_x = self._knob_target()
        self._draw()

    def _knob_target(self):
        pad, d = 3, self._h - 6
        return self._cw - pad - d if self._value else pad

    def _draw(self):
        self.delete("all")
        track_c = self._on_color if self._value else self._off_color
        self._round_rect(0, 0, self._cw, self._h, self._h / 2,
                         fill=track_c, outline="")
        pad, d = 3, self._h - 6
        kx = self._knob_x
        self.create_oval(kx, pad, kx + d, pad + d, fill="#ffffff", outline="")

    def _round_rect(self, x1, y1, x2, y2, r, **kw):
        pts = [x1+r, y1, x2-r, y1, x2, y1, x2, y1+r, x2, y2-r, x2, y2,
               x2-r, y2, x1+r, y2, x1, y2, x1, y2-r, x1, y1+r, x1, y1]
        return self.create_polygon(pts, smooth=True, **kw)

    def _toggle(self, e=None):
        self._value = not self._value
        self._animate()
        if self._command:
            self._command(self._value)

    def _animate(self):
        target = self._knob_target()
        def step():
            cur = self._knob_x
            diff = target - cur
            if abs(diff) < 1:
                self._knob_x = target; self._draw(); return
            self._knob_x = cur + diff * 0.35
            self._draw(); self.after(12, step)
        step()

    def get(self):
        return self._value

    def set(self, value, fire=False):
        if self._value != bool(value):
            self._value = bool(value); self._animate()
            if fire and self._command:
                self._command(self._value)


# ══════════════════════════════════════════════════════════════════
# StatusLED —— 状态指示灯（呼吸动画）
# ══════════════════════════════════════════════════════════════════

class StatusLED(tk.Canvas):
    """圆形状态指示灯。state: ok(绿)/warn(橙)/err(红闪)/off(灰)。"""

    def __init__(self, master, state="off", size=14, bg=None, pulse=True, **kw):
        import math
        pal = _pal()
        self._bg = bg or pal["BG"]
        self._size, self._state, self._pulse_on = size, state, pulse
        self._phase = 0.0
        tk.Canvas.__init__(self, master, width=size, height=size,
                           bg=self._bg, highlightthickness=0, bd=0, **kw)
        self._colors = {
            "ok": pal["SUCCESS"], "warn": pal["WARNING"],
            "err": pal["DANGER"], "off": _mix(pal["FG"], pal["BG"], 0.65)}
        self._tick()

    def _tick(self):
        import math
        self.delete("all")
        base = self._colors.get(self._state, self._colors["off"])
        if self._state == "err":
            alpha = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(self._phase))
        elif self._state == "ok" and self._pulse_on:
            alpha = 0.8 + 0.2 * (0.5 + 0.5 * math.sin(self._phase))
        else:
            alpha = 1.0
        d = self._size
        glow = _mix(base, self._bg, 1 - alpha * 0.5)
        self.create_oval(0, 0, d, d, fill=glow, outline="")
        inset = d * 0.22
        inner = _mix(base, "#ffffff", 0.25 * alpha)
        self.create_oval(inset, inset, d - inset, d - inset, fill=inner, outline="")
        self._phase += 0.18
        self.after(60, self._tick)

    def set_state(self, state):
        self._state = state


# ══════════════════════════════════════════════════════════════════
# Badge —— 徽章标签
# ══════════════════════════════════════════════════════════════════

class Badge(tk.Canvas):
    """彩色徽章。variant: accent/success/warning/danger/neutral。"""

    def __init__(self, master, text="", variant="neutral", bg=None,
                 font=None, padx=7, pady=2, **kw):
        pal = _pal()
        self._bg = bg or pal["BG"]
        cmap = {"accent": pal["ACCENT"], "success": pal["SUCCESS"],
                "warning": pal["WARNING"], "danger": pal["DANGER"],
                "neutral": pal["FG_DIM"]}
        self._color = cmap.get(variant, pal["FG_DIM"])
        self._text = text
        self._font = font or ("Microsoft YaHei UI", 8, "bold")
        self._px, self._py = padx, pady
        tw = _measure_text(self._font, text)
        self._cw = padx * 2 + tw
        self._h = pady * 2 + 13
        tk.Canvas.__init__(self, master, width=self._cw, height=self._h,
                           bg=self._bg, highlightthickness=0, bd=0, **kw)
        self._draw()

    def _round_rect(self, x1, y1, x2, y2, r, **kw):
        pts = [x1+r, y1, x2-r, y1, x2, y1, x2, y1+r, x2, y2-r, x2, y2,
               x2-r, y2, x1+r, y2, x1, y2, x1, y2-r, x1, y1+r, x1, y1]
        return self.create_polygon(pts, smooth=True, **kw)

    def _draw(self):
        self.delete("all")
        soft = _mix(self._color, self._bg, 0.82)
        self._round_rect(0, 0, self._cw, self._h, self._h / 2, fill=soft, outline="")
        self.create_text(self._cw / 2, self._h / 2, text=self._text,
                         fill=self._color, font=self._font)

    def set_text(self, text):
        self._text = text; self._draw()


# ══════════════════════════════════════════════════════════════════
# ProgressRing —— 圆形进度环
# ══════════════════════════════════════════════════════════════════

class ProgressRing(tk.Canvas):
    """圆形进度环。ring.set(0.65)；ring.indeterminate(True) 旋转。"""

    def __init__(self, master, size=44, thickness=4, bg=None, **kw):
        pal = _pal()
        self._bg = bg or pal["BG"]
        self._size, self._th = size, thickness
        self._value, self._indet, self._angle = 0.0, False, 0
        tk.Canvas.__init__(self, master, width=size, height=size,
                           bg=self._bg, highlightthickness=0, bd=0, **kw)
        self._tick()

    def _tick(self):
        self.delete("all")
        pal = _pal()
        pad = self._th / 2 + 1
        x1 = y1 = pad; x2 = y2 = self._size - pad
        self.create_oval(x1, y1, x2, y2,
                         outline=_mix(pal["FG"], pal["BG"], 0.8), width=self._th)
        if self._indet:
            self.create_arc(x1, y1, x2, y2, start=self._angle, extent=90,
                            style=tk.ARC, outline=pal["ACCENT"], width=self._th)
            self._angle = (self._angle + 12) % 360
        elif self._value > 0:
            self.create_arc(x1, y1, x2, y2, start=90, extent=-360 * self._value,
                            style=tk.ARC, outline=pal["ACCENT"], width=self._th)
        self.after(40, self._tick)

    def set(self, v):
        self._value = max(0.0, min(1.0, v))

    def indeterminate(self, on):
        self._indet = on
        if on:
            self._value = 0


# ══════════════════════════════════════════════════════════════════
# Tooltip —— 工具提示气泡
# ══════════════════════════════════════════════════════════════════

class Tooltip:
    """鼠标悬停显示的小气泡提示。

    用法：Tooltip(widget, text="这是说明文字")
    也可 widget.tooltip_text = "..." 后 attach_tooltip(widget)。
    """

    def __init__(self, widget, text="", delay=450, wraplength=240):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.wraplength = wraplength
        self.tipwin = None
        self._id = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, e=None):
        self._cancel()
        self._id = self.widget.after(self.delay, self._show)

    def _cancel(self):
        if self._id:
            try:
                self.widget.after_cancel(self._id)
            except Exception:
                pass
            self._id = None

    def _show(self):
        if self.tipwin or not self.text:
            return
        pal = _pal()
        x = self.widget.winfo_rootx() + 14
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        win = tk.Toplevel(self.widget)
        win.wm_overrideredirect(True)
        win.wm_geometry("+%d+%d" % (x, y))
        try:
            win.attributes("-topmost", True)
        except Exception:
            pass
        frame = tk.Frame(win, bg=pal["FG"], bd=0, highlightthickness=0)
        frame.pack()
        lbl = tk.Label(frame, text=self.text, bg=pal["FG"], fg=pal["BG"],
                       font=FONT_SMALL, justify="left", wraplength=self.wraplength,
                       padx=9, pady=5)
        lbl.pack()
        self.tipwin = win

    def _hide(self, e=None):
        self._cancel()
        if self.tipwin:
            try:
                self.tipwin.destroy()
            except Exception:
                pass
            self.tipwin = None

    def set_text(self, text):
        self.text = text


def attach_tooltip(widget, text):
    """便捷函数：给控件挂 Tooltip。"""
    widget._tooltip = Tooltip(widget, text)
    return widget._tooltip


# ══════════════════════════════════════════════════════════════════
# CollapsibleFrame —— 可折叠面板
# ══════════════════════════════════════════════════════════════════

class CollapsibleFrame(tk.Frame):
    """点击标题栏展开/折叠的面板，chevron 图标指示方向。

    用法：
        cf = CollapsibleFrame(parent, title="高级选项", open=False)
        ttk.Checkbutton(cf.body, text="...").pack(anchor="w")
    """

    def __init__(self, master, title="", open=False, bg=None, command=None, **kw):
        pal = _pal()
        self._bg = bg or pal["BG"]
        tk.Frame.__init__(self, master, bg=self._bg, **kw)
        self._open = open
        self._command = command
        self._title = title
        # 标题栏
        self.header = tk.Canvas(self, height=30, bg=self._bg,
                                highlightthickness=0, bd=0)
        self.header.pack(fill="x")
        self.header.configure(cursor="hand2")
        self.header.bind("<Button-1>", self.toggle)
        # 内容容器
        self.body = tk.Frame(self, bg=self._bg)
        self._draw_header()
        if open:
            self.body.pack(fill="x", padx=6)

    def _draw_header(self):
        pal = _pal()
        self.header.delete("all")
        w = max(self.winfo_width(), 120)
        # 底色 hover
        self.header.create_rectangle(0, 0, w, 30, fill=pal["HEAD_BG"], outline="")
        # chevron
        icon_name = "chevron-down" if self._open else "chevron-right"
        draw_icon(self.header, icon_name, 8, 7, size=16,
                  color=pal["ACCENT"], width=2)
        self.header.create_text(32, 15, text=self._title, fill=pal["FG"],
                                font=FONT_BOLD, anchor="w")

    def toggle(self, e=None):
        self._open = not self._open
        if self._open:
            self.body.pack(fill="x", padx=6)
        else:
            self.body.pack_forget()
        self._draw_header()
        if self._command:
            self._command(self._open)

    def open(self):
        if not self._open:
            self.toggle()

    def collapse(self):
        if self._open:
            self.toggle()


# ══════════════════════════════════════════════════════════════════
# HoverCard —— 可点击卡片
# ══════════════════════════════════════════════════════════════════

class HoverCard(tk.Frame):
    """整块可点击的卡片，hover 时边框/背景高亮。

    用法：
        card = HoverCard(parent, command=on_click)
        ttk.Label(card.body, text="...").pack()
    """

    def __init__(self, master, command=None, bg=None, **kw):
        pal = _pal()
        self._bg_default = bg or pal["SURFACE"]
        self._bg_hover = _mix(pal["SURFACE"], pal["ACCENT"], 0.10)
        self._command = command
        tk.Frame.__init__(self, master, bg=self._bg_default,
                          highlightbackground=pal["BORDER"],
                          highlightthickness=1, bd=0, **kw)
        self.body = tk.Frame(self, bg=self._bg_default)
        self.body.pack(fill="both", expand=True, padx=12, pady=10)
        if command:
            self.configure(cursor="hand2")
            for w in (self, self.body):
                w.bind("<Enter>", self._enter)
                w.bind("<Leave>", self._leave)
                w.bind("<Button-1>", self._click)
            self._bind_children(self.body)

    def _bind_children(self, parent):
        for c in parent.winfo_children():
            try:
                c.bind("<Enter>", self._enter)
                c.bind("<Leave>", self._leave)
                c.bind("<Button-1>", self._click)
            except Exception:
                pass
            self._bind_children(c)

    def _enter(self, e=None):
        pal = _pal()
        self.configure(bg=self._bg_hover, highlightbackground=pal["ACCENT"])
        self.body.configure(bg=self._bg_hover)

    def _leave(self, e=None):
        pal = _pal()
        self.configure(bg=self._bg_default, highlightbackground=pal["BORDER"])
        self.body.configure(bg=self._bg_default)

    def _click(self, e=None):
        if self._command:
            self._command()


# ══════════════════════════════════════════════════════════════════
# Segmented —— 分段控制器
# ══════════════════════════════════════════════════════════════════

class Segmented(tk.Canvas):
    """iOS/Mac 风格分段选择器。

    用法：
        seg = Segmented(parent, options=[("a","选项A"),("b","选项B")],
                        value="a", command=on_change)
    """

    def __init__(self, master, options, value=None, command=None, bg=None,
                 font=None, padx=14, pady=6, **kw):
        pal = _pal()
        self._bg = bg or pal["BG"]
        self._opts = options   # [(key, label), ...]
        # ⚠️ v3.14.0 P0-A3：原名 _options 与 tkinter.Widget 内部方法
        #    Widget._options() 撞名 —— Canvas.__init__ 里 self._options(cnf)
        #    打到 list 上直接 TypeError，而调用方都包在 try/except 里静默
        #    吞掉 → 分段器自诞生起在三工具从未建成功过（实拍 hero 右侧
        #    只剩一个小点）。改名 _opts 根治。
        self._value = value or (options[0][0] if options else None)
        self._command = command
        self._font = font or FONT_BOLD
        self._px, self._py = padx, pady
        widths = [_measure_text(self._font, lbl) for _, lbl in options]
        self._seg_w = [w + padx * 2 for w in widths]
        total_w = sum(self._seg_w)
        self._h = pady * 2 + 16
        tk.Canvas.__init__(self, master, width=total_w, height=self._h,
                           bg=self._bg, highlightthickness=0, bd=0, **kw)
        self._total_w = total_w
        # v3.14.0 A1（裁决 14-6）：三态升级 —— 悬浮/按压/选中 完整可辨
        self._hover_i = None
        self._press_i = None
        self.bind("<Motion>", self._on_motion)
        self.bind("<Leave>", lambda e: self._set_hover(None))
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.configure(cursor="hand2")
        self._draw()

    def _seg_at(self, x):
        acc = 0
        for i in range(len(self._opts)):
            acc += self._seg_w[i]
            if x < acc:
                return i
        return None

    def _set_hover(self, i):
        if self._hover_i != i:
            self._hover_i = i
            self._draw()

    def _on_motion(self, e):
        self._set_hover(self._seg_at(e.x))

    def _on_press(self, e):
        self._press_i = self._seg_at(e.x)
        self._draw()

    def _on_release(self, e):
        i = self._seg_at(e.x)
        self._press_i = None
        if i is not None:
            key = self._opts[i][0]
            if key != self._value:
                self._value = key
                self._draw()
                if self._command:
                    self._command(key)
                return
        self._draw()

    def _draw(self):
        pal = _pal()
        self.delete("all")
        track = _mix(pal["FG"], pal["BG"], 0.85)
        self._round_rect(0, 0, self._total_w, self._h, 7, fill=track, outline="")
        edge = _mix(pal["BORDER"], pal["FG"], 0.30)
        x = 0
        for i, (key, lbl) in enumerate(self._opts):
            w = self._seg_w[i]
            if key == self._value:            # 选中态：实心底 + 描边
                self._round_rect(x + 2, 2, x + w - 2, self._h - 2, 6,
                                 fill=pal["SURFACE"], outline=edge)
                c = pal["FG"]
            elif i == self._press_i:          # 按压态：更深一档
                self._round_rect(x + 2, 2, x + w - 2, self._h - 2, 6,
                                 fill=_mix(pal["FG"], pal["BG"], 0.78), outline="")
                c = pal["FG"]
            elif i == self._hover_i:          # 悬浮态：浅一档
                self._round_rect(x + 2, 2, x + w - 2, self._h - 2, 6,
                                 fill=_mix(pal["FG"], pal["BG"], 0.90), outline="")
                c = pal["FG"]
            else:
                c = pal["FG_DIM"]
            self.create_text(x + w / 2, self._h / 2, text=lbl, fill=c,
                             font=self._font)
            x += w

    def _round_rect(self, x1, y1, x2, y2, r, **kw):
        pts = [x1+r, y1, x2-r, y1, x2, y1, x2, y1+r, x2, y2-r, x2, y2,
               x2-r, y2, x1+r, y2, x1, y2, x1, y2-r, x1, y1+r, x1, y1]
        return self.create_polygon(pts, smooth=True, **kw)

    def get(self):
        return self._value

    def set(self, key):
        if any(k == key for k, _ in self._opts):
            self._value = key; self._draw()

    def refresh(self):
        """主题切换后重绘（配色取自 _pal() 当前值）。幂等无害。"""
        self._draw()


# ══════════════════════════════════════════════════════════════════
# SideNav —— 侧边垂直导航栏
# ══════════════════════════════════════════════════════════════════

class SideNav(tk.Canvas):
    """垂直侧边导航（图标+文字），现代 App 风格，替代水平页签。

    用法：
        nav = SideNav(parent, items=[("scan","扫描","search"),
                                      ("export","导出","download")],
                      value="scan", command=on_nav)
    items: [(key, 文字, 图标名), ...]
    """

    def __init__(self, master, items, value=None, command=None, bg=None,
                 width=168, item_h=42, **kw):
        pal = _pal()
        self._nav_bg = _mix(pal["BG"], pal["FG"], 0.03)
        self._items = items
        self._value = value or (items[0][0] if items else None)
        self._command = command
        self._cw, self._ih = width, item_h
        self._h = item_h * len(items) + 24
        tk.Canvas.__init__(self, master, width=width, height=self._h,
                           bg=self._nav_bg, highlightthickness=0, bd=0, **kw)
        self._hover_key = None
        self.bind("<Motion>", self._on_motion)
        self.bind("<Leave>", lambda e: self._set_hover(None))
        self.bind("<Button-1>", self._on_click)
        self._draw()

    def _set_hover(self, key):
        if self._hover_key != key:
            self._hover_key = key
            self._draw()

    def _on_motion(self, e):
        idx = (e.y - 12) // self._ih
        if 0 <= idx < len(self._items):
            self._set_hover(self._items[idx][0])
        else:
            self._set_hover(None)
        self.configure(cursor="hand2" if self._hover_key else "arrow")

    def _on_click(self, e):
        idx = (e.y - 12) // self._ih
        if 0 <= idx < len(self._items):
            key = self._items[idx][0]
            if key != self._value:
                self._value = key; self._draw()
                if self._command:
                    self._command(key)

    def _draw(self):
        pal = _pal()
        self.delete("all")
        for i, (key, label, icon) in enumerate(self._items):
            y = 12 + i * self._ih
            if key == self._value:
                self._round_rect(8, y, self._cw - 8, y + self._ih - 4,
                                 9, fill=pal["ACCENT"], outline="")
                tc, ic = "#ffffff", "#ffffff"
            elif key == self._hover_key:
                self._round_rect(8, y, self._cw - 8, y + self._ih - 4,
                                 9, fill=_mix(pal["FG"], self._nav_bg, 0.88),
                                 outline="")
                tc, ic = pal["FG"], pal["FG"]
            else:
                tc, ic = pal["FG_DIM"], pal["FG_DIM"]
            draw_icon(self, icon, 20, y + (self._ih - 4 - 18) / 2,
                      size=18, color=ic, width=2)
            self.create_text(46, y + (self._ih - 4) / 2, text=label,
                             fill=tc, font=FONT_BODY, anchor="w")

    def _round_rect(self, x1, y1, x2, y2, r, **kw):
        pts = [x1+r, y1, x2-r, y1, x2, y1, x2, y1+r, x2, y2-r, x2, y2,
               x2-r, y2, x1+r, y2, x1, y2, x1, y2-r, x1, y1+r, x1, y1]
        return self.create_polygon(pts, smooth=True, **kw)

    def set_value(self, key):
        if any(k == key for k, _, _ in self._items):
            self._value = key; self._draw()


# ══════════════════════════════════════════════════════════════════
# 辅助：Treeview 行 hover 高亮 / 拖拽区域高亮
# ══════════════════════════════════════════════════════════════════

def attach_tree_hover(tree):
    """给 Treeview 加鼠标行 hover 高亮（<Motion> 跟踪行）。"""
    state = {"hover": ""}
    def on_motion(e):
        if tree.identify("region", e.x, e.y) == "cell" or \
           tree.identify("region", e.x, e.y) == "tree":
            item = tree.identify_row(e.y)
            if item and item != state["hover"]:
                if state["hover"]:
                    tree.item(state["hover"], tags=())
                pal = _pal()
                tree.item(item, tags=("hoverrow",))
                tree.tag_configure("hoverrow",
                                   background=_mix(pal["ACCENT"], pal["BG"], 0.85))
                state["hover"] = item
        else:
            if state["hover"]:
                tree.item(state["hover"], tags=())
                state["hover"] = ""
    tree.bind("<Motion>", on_motion, add="+")
    tree.bind("<Leave>", lambda e: (
        tree.item(state["hover"], tags=()) if state["hover"] else None,
        state.update(hover="")), add="+")
    return tree


def attach_drop_highlight(widget, on_drop_check=None):
    """拖拽文件进入时给 widget 加高亮边框，离开/放下后恢复。

    需 tkinterdnd2；widget 已绑定 DND_FILES 时调用。视觉层用
    highlightthickness 切换。
    """
    pal = _pal()
    old = widget.cget("highlightthickness") or 0
    old_bg = widget.cget("highlightbackground")
    def enter(e):
        try:
            widget.configure(highlightthickness=3,
                             highlightbackground=pal["ACCENT"])
        except Exception:
            pass
    def leave(e):
        try:
            widget.configure(highlightthickness=old, highlightbackground=old_bg)
        except Exception:
            pass
    widget.bind("<DragEnter>", enter, add="+")
    widget.bind("<DragLeave>", leave, add="+")
    widget.bind("<Drop>", leave, add="+")
    return widget


# ══════════════════════════════════════════════════════════════════
# auto_tooltip —— 按按钮文字智能批量挂载 Tooltip
# ══════════════════════════════════════════════════════════════════

_TOOLTIP_RULES = [
    (("扫描", "识别", "检测工程"), "扫描当前打开的 Pro Tools 工程，读取轨道、采样率等信息"),
    (("导出", "开始导出", "批量导出"), "按勾选的导出模式（整轨/分轨/总线）导出音频文件"),
    (("浏览", "选择文件", "选择目录"), "打开文件/文件夹选择对话框"),
    (("删除", "清空", "清理", "移除"), "删除选中项，操作不可恢复，请确认"),
    (("刷新", "重新识别", "重新检测"), "重新检测 Pro Tools / 剪映运行状态"),
    (("保存全部", "保存配置"), "把所有页签的配置写入配置文件"),
    (("全选",), "勾选列表中的全部轨道"),
    (("取消全选", "全不选", "清空选择"), "取消列表中所有轨道的勾选"),
    (("打开目录", "打开文件夹", "打开所在"), "在 Windows 资源管理器中打开对应目录"),
    (("导入",), "从外部文件 / 其他工程导入数据"),
    (("执行", "开始重命名", "重命名"), "按规则执行批量重命名，可在撤销页回溯"),
    (("撤销", "回溯", "还原"), "恢复到重命名操作之前的文件名"),
    (("交付", "打包交付"), "把素材整理成标准交付包结构"),
    (("停止", "中止"), "中止当前正在运行的任务"),
    (("新增", "添加", "新建"), "添加一个新条目"),
    (("生成", "创建文件夹"), "按命名规则批量生成工程文件夹结构"),
    (("解密",), "解密剪映草稿文件以便读取内容"),
    (("人声分离", "分离"), "调用 Demucs 对音频做人声 / 伴奏分离（耗时较长）"),
    (("预览",), "按当前规则预演结果，不会实际修改文件"),
    (("设置", "配置"), "调整工具参数与偏好"),
]


def auto_tooltip(root):
    """遍历所有按钮，按文字关键词自动挂载 Tooltip。

    无法匹配的按钮跳过；已挂 Tooltip 的不重复挂载。
    """
    def _tip_for(text):
        if not text:
            return None
        for keys, tip in _TOOLTIP_RULES:
            for k in keys:
                if k in text:
                    return tip
        return None

    def walk(w):
        try:
            cls = w.winfo_class()
        except Exception:
            cls = ""
        if cls in ("TButton", "Button"):
            try:
                if not getattr(w, "_tooltip", None):
                    txt = w.cget("text")
                    tip = _tip_for(txt)
                    if tip:
                        Tooltip(w, tip)
            except Exception:
                pass
        try:
            for c in w.winfo_children():
                walk(c)
        except Exception:
            pass
    walk(root)
    return root


# ══════════════════════════════════════════════════════════════════
# HeroHeader —— 顶部横幅（大图标色块 + 标题 + 状态区）
# ══════════════════════════════════════════════════════════════════

class HeroHeader(tk.Frame):
    """现代 App 顶部横幅，制造视觉焦点。

    用法：
        hdr = HeroHeader(parent, title="剪映工程工具包",
                         subtitle="v2.15.0 · 2026-09-28", icon="music")
        hdr.pack(fill="x")
        # 右侧放状态灯/设置：hdr.right 容器
        StatusLED(hdr.right, ...).pack(side="left", padx=4)
    """

    def __init__(self, master, title="", subtitle="", icon=None,
                 bg=None, accent=None, height=54, **kw):
        # v3.13.0 C1（裁决 13-4）：头部卡 90→54px —— 图标块 44→36、副标题
        # 从标题下方移到右侧状态区（左侧单行标题，内容高=图标 36），pady 8；
        # 实测渲染高 = 36+8*2+2 = 54。底部三色渐变退役改单色强调细线
        # （渐变含 ACCENT_2 第二强调，与「主按钮唯一赤陶」冲突）。
        pal = _pal()
        self._bg = bg or pal.get("ELEVATED", pal["SURFACE"])
        self._accent = accent or pal["ACCENT"]
        self._fg = pal["FG"]
        self._dim_c = pal["FG_DIM"]
        tk.Frame.__init__(self, master, bg=self._bg, **kw)
        pad = 14
        inner = tk.Frame(self, bg=self._bg)
        inner.pack(fill="x", padx=pad, pady=8)
        # 存引用（v3.14.0 P0-2：refresh() 分件恢复用）
        self._inner = inner

        # 左侧大图标色块
        self._icon_canvas = None
        self._icon_name = None
        if icon:
            ib = tk.Canvas(inner, width=36, height=36, bg=self._bg,
                           highlightthickness=0, bd=0)
            ib.pack(side="left", padx=(0, 10))
            self._icon_canvas = ib
            self._icon_name = icon
            # 强调色圆角方块
            self._icon_block(ib, 0, 0, 36, 10, fill=self._accent)
            draw_icon(ib, icon, 9, 9, size=18, color="#ffffff", width=2)

        # 单行标题（v3.13.0 C1：副标题移右侧，头部卡压到 54px）
        txt_box = tk.Frame(inner, bg=self._bg)
        txt_box.pack(side="left", fill="y")
        self._txt_box = txt_box
        self._title_label = tk.Label(txt_box, text=title, bg=self._bg,
                                     fg=self._fg, font=FONT_TITLE,
                                     anchor="w")
        self._title_label.pack(anchor="w")

        # 右侧容器（副标题/状态灯/设置）
        self.right = tk.Frame(inner, bg=self._bg)
        self.right.pack(side="right")
        self._sub_label = None
        if subtitle:
            self._sub_label = tk.Label(self.right, text=subtitle, bg=self._bg,
                                       fg=self._dim_c, font=FONT_SMALL,
                                       anchor="e")
            self._sub_label.pack(side="left", padx=(0, 10))

        # 底部强调色细线（单色；v3.13.0 C1：三色渐变退役）
        line = tk.Frame(self, bg=self._accent, height=2)
        line.pack(fill="x", side="bottom")
        self._line = line

    def refresh(self):
        """主题切换后重取色（v3.14.0 P0-2）。幂等无害。

        _recolor_native 会把本类（tk.Frame）与内部 Frame/Canvas 一律刷成
        窗底色、而 tk.Label 不在名单——不刷新就会强调线消失/图标块变色/
        文字停旧主题。此处按构造时存好的引用整体恢复；right 内的第三方
        小件（状态灯/徽章/分段器）尽力刷底色，各自带 refresh 的组件
        （如 Segmented）由调用方另行联动。
        """
        pal = _pal()
        self._bg = pal.get("ELEVATED", pal["SURFACE"])
        self._accent = pal["ACCENT"]
        self._fg = pal["FG"]
        self._dim_c = pal["FG_DIM"]
        self.configure(bg=self._bg)
        for ref in (self._inner, self._txt_box, self.right):
            if ref is not None:
                try:
                    ref.configure(bg=self._bg)
                except Exception:
                    pass
        if self._icon_canvas is not None:
            try:
                self._icon_canvas.configure(bg=self._bg)
                self._icon_canvas.delete("all")
                self._icon_block(self._icon_canvas, 0, 0, 36, 10,
                                 fill=self._accent)
                draw_icon(self._icon_canvas, self._icon_name, 9, 9, size=18,
                          color="#ffffff", width=2)
            except Exception:
                pass
        if self._title_label is not None:
            try:
                self._title_label.configure(bg=self._bg, fg=self._fg)
            except Exception:
                pass
        if self._sub_label is not None:
            try:
                self._sub_label.configure(bg=self._bg, fg=self._dim_c)
            except Exception:
                pass
        if self._line is not None:
            try:
                self._line.configure(bg=self._accent)
            except Exception:
                pass
        # right 内第三方小件（StatusLED/Badge 等 Canvas/Frame 底色）尽力恢复
        try:
            for w in self.right.winfo_children():
                if w is self._sub_label:
                    continue
                try:
                    w.configure(bg=self._bg)
                except Exception:
                    pass
        except Exception:
            pass

    def _icon_block(self, cv, x1, y1, d, r, fill):
        pts = [x1+r, y1, x1+d-r, y1, x1+d, y1, x1+d, y1+r,
               x1+d, y1+d-r, x1+d, y1+d, x1+d-r, y1+d, x1+r, y1+d,
               x1, y1+d, x1, y1+d-r, x1, y1+r, x1, y1]
        return cv.create_polygon(pts, smooth=True, fill=fill)


# ══════════════════════════════════════════════════════════════════
# v3.14.0 A1（裁决 14-6）—— 自绘卡片 + 像素按钮体系
# ══════════════════════════════════════════════════════════════════
# 设计规格对齐 双风格预览矩阵.html（CSS 稿）：
#   玻璃 = 壳混白 + 白描边 + 顶缘高光 + 圆角，头部条水波纹动画（液态感），
#          内容区恒实心（Liquid Glass 纪律: Do Not Use For content）
#   像素 = 直角 + 描边 + 顶缘 4px 高光条，无阴影无动画（硬边静态美学）
# 可感知度硬指标（31 号文档）：同主题两风格实拍并排，壳层与内容层亮度差
#   ΔL >= 6 —— luma() 就是给测试断言用的（test_widgets_a1.py 守护）。


def luma(hex_color):
    """感知亮度（0-255，Rec.601 加权）。测试断言 ΔL>=6 用。"""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i+2], 16) for i in (0, 2, 4))
    return 0.299 * r + 0.587 * g + 0.114 * b


def _pal_dark(pal=None):
    """当前主题是否深色（按窗口底亮度判定）。"""
    pal = pal or _pal()
    return luma(pal["BG"]) < 128


class GlassCard(tk.Canvas):
    """玻璃卡：壳混白 + 白描边 + 顶缘高光 + 圆角；头部条水波纹动画；
    .body 为内容容器（恒实心 SURFACE，直角）。

    用法：
        card = GlassCard(parent, title="扫描设置")
        ttk.Label(card.body, ...).pack(...)      # body 内随意 pack/grid
        card.pack(fill="both", expand=True)
    """

    HEADER_H = 34      # 头部条高（15-6b：26→34，波纹的「水面」舞台加宽）
    INSET = 8          # body 距壳边距（四周露壳色边，15-6b：6→8 让渐变可见）
    SHADOW = 8         # 右下柔和阴影深度（15-6 苹果向：卡体让出右下，画羽化阴影）
    RIPPLE_MS = 90     # 波纹帧间隔（≈11fps，慢动效省 CPU）
    RIPPLE_MAX = 3     # 同屏波纹圈上限（15-6b：4→3，少而精）

    def __init__(self, master, title="", bg=None, radius=16, **kw):
        pal = _pal()
        dark = _pal_dark(pal)
        self._radius = radius
        self._title = title
        # 壳层取色收口（style_palette 单一真源；ΔL>=6 由测试守护）
        sp = style_palette()
        self._shell, self._border = sp["shell"], sp["border"]
        self._hl, self._content_bg = sp["hl"], sp["content"]
        # 15-6 苹果向：渐变两端 + 柔和阴影色
        self._shell_top = sp["shell_top"]
        self._shell_bottom = sp["shell_bottom"]
        self._shadow = sp["shadow"]
        self._fg = pal["FG"]
        # 15-6b：波纹色弃用赤陶accent——红圈满窗太吵；改低干扰中性灰
        # （浅色=壳底向 FG 混，深色=壳向白混），苹果向的「静」
        self._ripple = (_mix(self._shell_bottom, pal["FG"], 0.28) if not dark
                        else _mix(sp["shell"], "#ffffff", 0.30))
        tk.Canvas.__init__(self, master, bg=bg or pal["BG"],
                           highlightthickness=0, bd=0, **kw)
        self.body = tk.Frame(self, bg=self._content_bg)
        self._ripples = []          # [(cx, r, id), ...]
        self._job = None
        self._paused = False
        self.bind("<Configure>", lambda e: self._on_cfg())
        self.bind("<Unmap>", lambda e: self._pause())
        self.bind("<Map>", lambda e: self._resume())
        self._on_cfg()
        self._start()

    # —— 壳绘制 ——
    def _on_cfg(self):
        try:
            w, h = self.winfo_width(), self.winfo_height()
        except Exception:
            return
        if w < 20 or h < 20:
            return
        self._draw_shell(w, h)
        self.body.place(x=self.INSET, y=self.HEADER_H,
                        width=w - self.INSET * 2 - self.SHADOW,
                        height=h - self.HEADER_H - self.INSET - self.SHADOW)

    def _draw_shell(self, w, h):
        self.delete("all")
        r = self._radius
        cw, ch = w - self.SHADOW, h - self.SHADOW     # 卡体区（右下让给阴影）
        # —— 柔和阴影（15-6 苹果向：两层淡色圆角外扩模拟羽化）——
        self._round_rect(4, 4, w - 1, h - 1, r, fill=self._shadow, outline="")
        self._round_rect(2, 2, w - 2, h - 2, r, fill=self._shadow, outline="")
        # —— 渐变壳（垂直：顶部反光亮 → 底部厚度暗，玻璃透光感）——
        step = 3
        n = max(int(ch // step), 1)
        for i in range(n):
            y0 = i * step
            y1 = min(y0 + step + 1, ch)
            c = _mix(self._shell_top, self._shell_bottom, i / max(n - 1, 1))
            self._round_rect(0, y0, cw, y1, r, fill=c, outline="")
        # 头部条底（比壳深半档）——标题与波纹的容器
        header_bg = _mix(self._shell, self._fg, 0.05)
        self.create_rectangle(1, 1, cw - 1, self.HEADER_H,
                              fill=header_bg, outline="")
        # 顶缘高光条（圆角内测，玻璃反光线）
        self._round_rect(2, 1, cw - 2, 1 + 4, max(r - 2, 4),
                         fill=self._hl, outline="")
        # 外描边（1px 低对比，最后画压住渐变毛边）
        self._round_rect(0, 0, cw, ch, r, fill="", outline=self._border, width=1)
        # 头部标题（item id 留存：波纹圈生成后抬标题，保证文字恒在波纹之上）
        self._title_id = self.create_text(14, self.HEADER_H / 2 + 1,
                                          text=self._title, fill=self._fg,
                                          font=FONT_BOLD, anchor="w")

    def _round_rect(self, x1, y1, x2, y2, r, **kw):
        return self.create_polygon(_rr_pts(x1, y1, x2, y2, r), smooth=True, **kw)

    # —— 水波纹动画（头部条内扩散圈，v3.14.0 裁决 14-6④）——
    def _start(self):
        if self._job is None:
            self._job = self.after(self.RIPPLE_MS, self._tick)

    def _pause(self):
        self._paused = True
        if self._job:
            try:
                self.after_cancel(self._job)
            except Exception:
                pass
            self._job = None

    def _resume(self):
        self._paused = False
        self._start()

    def _tick(self):
        self._job = None
        if self._paused:
            return
        try:
            w = max(self.winfo_width(), 40)
            h = max(self.winfo_height(), 40)
        except Exception:
            w = h = 40
        cw, ch = w - self.SHADOW, h - self.SHADOW
        if cw < 60 or ch < 60:
            self._job = self.after(self.RIPPLE_MS, self._tick)
            return
        # 15-6b 重设计：波纹圈心固定在头部条中线（cy=HEADER_H/2）——
        # 「水面」在标题栏里荡开，半径超过头部条的部分被 body 窗口件
        # 自然裁掉（tkinter 窗口件恒在 canvas 项之上，15-6 第一版把圈
        # 心撒在全卡 body 底下，只露出边缝断弧＝满窗碎红圈的根因）。
        import random
        if len(self._ripples) < self.RIPPLE_MAX and random.random() < 0.30:
            cx = random.uniform(40, max(cw - 40, 41))
            cy = self.HEADER_H / 2.0
            oid = self.create_oval(cx, cy, cx, cy, outline=self._ripple, width=1)
            self._ripples.append({"cx": cx, "cy": cy, "r": 5.0, "id": oid})
        # 推进：扩散 + 到头删除（线宽恒 1：细线才有玻璃静感）
        rmax = self.HEADER_H * 1.7          # ≈58：荡满整条头部条
        alive = []
        for rp in self._ripples:
            rp["r"] += 1.8
            if rp["r"] >= rmax:
                try:
                    self.delete(rp["id"])
                except Exception:
                    pass
                continue
            try:
                self.coords(rp["id"], rp["cx"] - rp["r"], rp["cy"] - rp["r"],
                            rp["cx"] + rp["r"], rp["cy"] + rp["r"])
            except Exception:
                pass
            alive.append(rp)
        self._ripples = alive
        # 标题恒在最上（波纹圈空心、扫过无碍，但标题别被圈线切过）
        try:
            self.tag_raise(getattr(self, "_title_id", None))
        except Exception:
            pass
        self._job = self.after(self.RIPPLE_MS, self._tick)

    def refresh(self):
        """主题/风格切换后重绘（重取色板）。幂等无害。"""
        pal = _pal()
        dark = _pal_dark(pal)
        sp = style_palette()
        self._shell = sp["shell"]
        self._border = sp["border"]
        self._hl = sp["hl"]
        self._shell_top = sp["shell_top"]
        self._shell_bottom = sp["shell_bottom"]
        self._shadow = sp["shadow"]
        self._content_bg = pal["SURFACE"]
        self._fg = pal["FG"]
        self._ripple = (_mix(self._shell_bottom, pal["FG"], 0.28) if not dark
                        else _mix(sp["shell"], "#ffffff", 0.30))
        self.configure(bg=pal["BG"])
        self.body.configure(bg=self._content_bg)
        self._on_cfg()

    def destroy(self):
        self._pause()
        self._ripples = []
        try:
            super().destroy()
        except Exception:
            pass


def _darken_hex(c, t):
    """把颜色向黑压暗 t 比例（t=0.25 → 暗一档）。"""
    return _mix(c, "#000000", t)


def _rr_pts(x1, y1, x2, y2, r):
    """圆角矩形 polygon 点集（smooth=True 用）—— GlassCard / PixelButton
    玻璃分档共用（v3.14.0 A2 提为模块级，几何单一真源）。"""
    r = max(min(r, (x2 - x1) / 2, (y2 - y1) / 2), 0)
    return [x1+r, y1, x2-r, y1, x2, y1, x2, y1+r, x2, y2-r, x2, y2,
            x2-r, y2, x1+r, y2, x1, y2, x1, y2-r, x1, y1+r, x1, y1]


def style_palette():
    """卡片壳层取色收口（v3.14.0 A1，裁决 14-6）。

    GlassCard / PixelCard 构造与刷新一律从这里取色；test_style_profile.py
    以本函数为单一真源跑 ΔL>=6 可感知度断言（防「做了但看不见」）。
      shell    卡片壳色（glass=窗底混白系；pixel=SURFACE 实心）
      content  内容区恒实心（恒 = SURFACE，不受档案影响——Liquid Glass 纪律）
      border   卡片描边（像素档加深一档保描边存在感）
      hl       顶缘高光条（glass 2px / pixel 4px）
    """
    pal = _pal()
    dark = _pal_dark(pal)
    if current_button_style() == "glass":
        if dark:
            shell = _mix(pal["BG"], "#ffffff", 0.08)      # CSS 稿深色同值
            border = _mix(pal["BG"], "#ffffff", 0.22)
            hl = _mix(pal["BG"], "#ffffff", 0.30)
            # v3.14.0 裁决 15-6 苹果向：渐变两端 + 柔和阴影（羽化模拟）
            shell_top = _mix(pal["BG"], "#ffffff", 0.16)
            shell_bottom = _mix(pal["BG"], "#ffffff", 0.02)
            shadow = _mix(pal["BG"], "#000000", 0.40)
        else:
            # 浅色玻璃 = 比窗底暗一层的雾面（向 FG 混）：emerald 等
            # 近白主题向 SURFACE 靠会贴死。v3.14.0 P0-A2 实拍治理：
            # 0.045 实拍不可辨（玻璃感为零），加深到 0.10（ΔL≈9）。
            shell = _mix(pal["BG"], pal["FG"], 0.10)
            border = _mix(shell, "#ffffff", 0.90)
            hl = "#ffffff"
            # 15-6：顶部提亮（玻璃反光）→ 底部压暗（厚度感）
            shell_top = _mix(pal["BG"], "#ffffff", 0.60)
            shell_bottom = _mix(pal["BG"], pal["FG"], 0.17)
            # 15-6b：0.20→0.26（实拍 0.20 的阴影在暖米白窗底上不可辨）
            shadow = _mix(pal["BG"], pal["FG"], 0.26)
        corner = hl          # glass 不用像素角块（给个无害值）
        hl2 = hl
    else:  # pixel（rounded 经 normalize 已并入 glass，此处恒为像素硬边语义）
        shell = pal["SURFACE"]
        # v3.14.0 P0-A2/C4 实拍治理：浅色档描边 0.35→0.55（emerald 下
        # 白卡融进窗底靠描边救）；高光条 0.40→0.15（品牌色浓一档，
        # 4px 条实拍可辨）。
        border = _mix(pal["BORDER"], pal["FG"], 0.55)
        if dark:
            hl = _mix(pal["SURFACE"], "#ffffff", 0.30)
        else:
            hl = _mix(pal["ACCENT"], "#ffffff", 0.15)
        # 15-6 像素元素三件：8-bit 硬阴影 + 对角像素角块 + 高光分段淡块
        # （15-6b：shadow 0.45→0.55，浅底实拍 0.45 灰得没存在感）
        shadow = _mix(pal["BORDER"], pal["FG"], 0.55)
        corner = _mix(pal["ACCENT"], pal["FG"], 0.10)
        hl2 = _mix(hl, "#ffffff", 0.45)
        shell_top = shell
        shell_bottom = shell
    return {"shell": shell, "content": pal["SURFACE"],
            "border": border, "hl": hl,
            "shell_top": shell_top, "shell_bottom": shell_bottom,
            "shadow": shadow, "corner": corner, "hl2": hl2}


class PixelCard(tk.Frame):
    """像素卡：直角 + 描边 + 顶缘 4px 高光条，无阴影无动画（硬边静态）。
    .body 为内容容器（SURFACE 实心）。

    用法：
        card = PixelCard(parent, title="扫描设置")
        ttk.Label(card.body, ...).pack(...)
        card.pack(fill="both", expand=True)
    """

    HL_H = 4          # 顶缘高光条（CSS 稿 4px 签名元素）

    def __init__(self, master, title="", bg=None, **kw):
        pal = _pal()
        # 取色收口（style_palette 单一真源；描边存在感 ΔL>=6 由测试守护）
        sp = style_palette()
        self._surface = sp["content"]
        self._edge = sp["border"]
        self._hl = sp["hl"]
        self._fg = pal["FG"]
        self._dim = pal["FG_DIM"]
        # 15-6 像素元素三件：8-bit 硬阴影 / 对角像素角块 / 高光分段淡块
        self._shadow = sp["shadow"]
        self._corner = sp["corner"]
        self._hl2 = sp["hl2"]
        tk.Frame.__init__(self, master, bg=bg or pal["BG"],
                          highlightthickness=1,
                          highlightbackground=self._edge, bd=0, **kw)
        self._title = title
        # —— 8-bit 硬阴影：右/下 4px 实心条（无羽化，先 pack 占边；
        #      15-6b：3→4px，实拍 3px 在浅底上不可辨）——
        self._shadow_r = tk.Frame(self, bg=self._shadow, width=4)
        self._shadow_r.pack(side="right", fill="y")
        self._shadow_b = tk.Frame(self, bg=self._shadow, height=4)
        self._shadow_b.pack(side="bottom", fill="x")
        # 顶缘高光条（存引用：refresh 分件恢复，见 v3.14.0 P0-3）
        self._hl_bar = tk.Frame(self, bg=self._hl, height=self.HL_H)
        self._hl_bar.pack(fill="x")
        # 高光分段淡块（像素分段感：条右端一截更亮）
        self._hl_seg = tk.Frame(self._hl_bar, bg=self._hl2, width=16,
                                height=self.HL_H)
        self._hl_seg.place(relx=1.0, x=-16, y=0)
        # 标题行（存引用同上）
        self._title_bar = None
        self._title_label = None
        if title:
            bar = tk.Frame(self, bg=self._surface)
            bar.pack(fill="x")
            self._title_bar = bar
            self._title_label = tk.Label(bar, text=title, bg=self._surface,
                                         fg=self._fg, font=FONT_BOLD,
                                         anchor="w")
            self._title_label.pack(anchor="w", padx=10, pady=(5, 2))
        # 内容区（恒实心）
        self.body = tk.Frame(self, bg=self._surface)
        self.body.pack(fill="both", expand=True, padx=1, pady=(0, 1))
        # 对角像素角块（8-bit 签名：左上/右下各一枚 8x8 实心块；15-6b：6→8）
        self._corner_tl = tk.Frame(self, bg=self._corner, width=8, height=8)
        self._corner_tl.place(x=0, y=0)
        self._corner_br = tk.Frame(self, bg=self._corner, width=8, height=8)
        self._corner_br.place(relx=1.0, x=-12, rely=1.0, y=-12)

    def refresh(self):
        """主题切换后重取色。幂等无害。

        v3.14.0 P0-3 修复：旧实现遍历直接子控件一律刷 _surface，会把高光条
        （应为 _hl）误刷成卡面色——接上主题切换 refresh 链后必现。改为按
        构造时存好的引用分件恢复（高光条=hl、标题行/卡面=surface、标题字=fg）。
        15-6 扩：硬阴影条/像素角块/高光分段块一并分件恢复。
        """
        pal = _pal()
        sp = style_palette()
        self._edge = sp["border"]
        self._hl = sp["hl"]
        self._surface = sp["content"]
        self._fg = pal["FG"]
        self._shadow = sp["shadow"]
        self._corner = sp["corner"]
        self._hl2 = sp["hl2"]
        self.configure(bg=pal["BG"], highlightbackground=self._edge)
        if self._hl_bar is not None:
            self._hl_bar.configure(bg=self._hl)
        if getattr(self, "_hl_seg", None) is not None:
            self._hl_seg.configure(bg=self._hl2)
        if getattr(self, "_shadow_r", None) is not None:
            self._shadow_r.configure(bg=self._shadow)
        if getattr(self, "_shadow_b", None) is not None:
            self._shadow_b.configure(bg=self._shadow)
        if getattr(self, "_corner_tl", None) is not None:
            self._corner_tl.configure(bg=self._corner)
        if getattr(self, "_corner_br", None) is not None:
            self._corner_br.configure(bg=self._corner)
        if self._title_bar is not None:
            self._title_bar.configure(bg=self._surface)
        if self._title_label is not None:
            self._title_label.configure(bg=self._surface, fg=self._fg)
        self.body.configure(bg=self._surface)


def refresh_cards(widget):
    """主题切换后的轻量换色链（v3.14.0 P0-1）：递归找 GlassCard/PixelCard
    调 refresh() 重取色。

    与 rebuild_cards（换壳，风格切换用）不同：主题切换不换类，refresh 幂等
    且不销毁任何控件、不丢输入——这是主题链该走的轻路。
    幂等无害；找不到卡片时纯空转。
    """
    try:
        children = widget.winfo_children()
    except Exception:
        return
    if isinstance(widget, (GlassCard, PixelCard)):
        try:
            widget.refresh()
        except Exception:
            pass
    for child in children:
        refresh_cards(child)


class PixelButton(tk.Canvas):
    """像素按钮：直角 + 2px 深描边 + 顶缘 4px 高光条（CSS 稿签名按钮）。

    用法：
        btn = PixelButton(parent, text="开始扫描", icon="play",
                          command=fn, primary=True)
        btn.pack()
        btn.set_enabled(False)          # 取代 ttk 的 state(["disabled"])
        btn.configure_text(text="...")  # 运行时改文案
    primary=True 主按钮（唯一赤陶）；danger=True 删除类；
    都不选 = 次级按钮（浅底描边）。
    """

    HL_H = 4
    PAD_X, PAD_Y = 14, 6

    def __init__(self, master, text="", icon=None, command=None,
                 primary=False, danger=False, font=None,
                 icon_size=14, **kw):
        pal = _pal()
        self._command = command
        self._text = text
        self._icon = icon
        self._icon_size = icon_size
        self._font = font or FONT_BOLD
        self._enabled = True
        self._hover = False
        self._pressed = False
        if primary:
            self._fill = pal["ACCENT"]
            self._fill_hv = pal["ACCENT_HV"]
            self._edge = _mix(pal["ACCENT"], "#000000", 0.35)
            self._fg = "#ffffff"
        elif danger:
            self._fill = pal["DANGER"]
            self._fill_hv = pal["DANGER_HV"]
            self._edge = _mix(pal["DANGER"], "#000000", 0.35)
            self._fg = "#ffffff"
        else:
            self._fill = pal["SURFACE"]
            self._fill_hv = _mix(pal["SURFACE"], pal["FG"], 0.08)
            self._edge = _mix(pal["BORDER"], pal["FG"], 0.30)
            self._fg = pal["FG"]
        # v3.14.0 A2（14-6 遗留③）：玻璃档案下按钮分档 —— 圆角 + 白描边 +
        # 雾面/实底，不再像素直角深描边（rounded 兜底仍走像素硬边）。
        self._glass = (current_button_style() == "glass")
        if self._glass:
            sp = style_palette()
            dark = _pal_dark(pal)
            if primary:
                self._fill, self._fill_hv = pal["ACCENT"], pal["ACCENT_HV"]
                self._edge = _mix(pal["ACCENT"], "#ffffff", 0.55)
                self._fg = "#ffffff"
                self._hl = _mix("#ffffff", pal["ACCENT"], 0.15)
            elif danger:
                self._fill, self._fill_hv = pal["DANGER"], pal["DANGER_HV"]
                self._edge = _mix(pal["DANGER"], "#ffffff", 0.55)
                self._fg = "#ffffff"
                self._hl = _mix("#ffffff", pal["DANGER"], 0.15)
            else:
                self._fill = sp["shell"]            # 雾面壳（浅=压暗/深=混白）
                self._fill_hv = _mix(sp["shell"], pal["FG"], 0.08)
                self._edge = sp["border"]
                self._fg = pal["FG"]
                self._hl = (sp["hl"] if dark
                            else _mix(sp["shell"], "#ffffff", 0.50))
        # 禁用态色（底/字都向窗底收敛）
        self._fill_dis = _mix(pal["FG"], pal["BG"], 0.88)
        self._fg_dis = _mix(pal["FG"], pal["BG"], 0.55)
        if not getattr(self, "_hl", None):
            self._hl = "#ffffff" if not _pal_dark(pal) else _mix(self._fill, "#ffffff", 0.30)
        self._bg_master = pal["BG"]
        # 15-6：8-bit 硬阴影色（像素档专用；玻璃档走 _draw_glass 不用）
        self._shadow_c = style_palette()["shadow"]
        # 尺寸：描边 2 + 高光 4 + 内容 + 右下 3px 硬阴影余量
        icon_w = (icon_size + 6) if icon else 0
        tw = _measure_text(self._font, text)
        w = self.PAD_X * 2 + icon_w + tw + 4 + 3
        h = self.HL_H + 16 + self.PAD_Y * 2 + 3
        tk.Canvas.__init__(self, master, width=w, height=h,
                           bg=self._bg_master, highlightthickness=0, bd=0, **kw)
        self._kind = "danger" if danger else ("primary" if primary else "secondary")
        self._cw, self._h = w, h
        self.configure(cursor="hand2")
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self._draw()

    def _set_hover(self, on):
        if self._enabled and self._hover != on:
            self._hover = on
            self._draw()

    def _on_press(self, e):
        if self._enabled:
            self._pressed = True
            self._draw()

    def _on_release(self, e):
        was = self._pressed
        self._pressed = False
        self._draw()
        if was and self._enabled and self._command:
            self._command()

    def _round_rect(self, x1, y1, x2, y2, r, **kw):
        return self.create_polygon(_rr_pts(x1, y1, x2, y2, r), smooth=True, **kw)

    def _draw(self):
        self.delete("all")
        w, h = self._cw, self._h
        if self._glass:
            self._draw_glass(w, h)
            return
        if not self._enabled:
            fill, fg, edge = self._fill_dis, self._fg_dis, self._fill_dis
            hl_h = self.HL_H
        elif self._pressed:
            fill, fg, edge = self._fill_hv, self._fg, self._edge
            hl_h = max(self.HL_H - 2, 1)          # 按压：高光收短 = 下沉感
        elif self._hover:
            fill, fg, edge = self._fill_hv, self._fg, self._edge
            hl_h = self.HL_H
        else:
            fill, fg, edge = self._fill, self._fg, self._edge
            hl_h = self.HL_H
        # —— 15-6：8-bit 硬阴影（右下 3px 实心，无羽化）——
        # 按压时按钮位移 (2,2) 吞掉阴影 = 经典 8-bit 下沉反馈
        if not self._enabled:
            bx1, by1, bx2, by2 = 0, 0, w, h
        elif self._pressed:
            bx1, by1, bx2, by2 = 2, 2, w, h
        else:
            self.create_rectangle(3, 3, w, h, fill=self._shadow_c, outline="")
            bx1, by1, bx2, by2 = 0, 0, w - 3, h - 3
        # 主体 + 2px 深描边
        self.create_rectangle(bx1, by1, bx2, by2, fill=fill, outline=edge, width=2)
        # 顶缘高光条（描边内测）
        self.create_rectangle(bx1 + 2, by1 + 2, bx2 - 2, by1 + 2 + hl_h,
                              fill=self._hl, outline="")
        # 内容（按压整体下沉 2px）
        dy = 2 if self._pressed else 0
        cx = self.PAD_X + 2 + bx1
        cy = by1 + (by2 - by1 - self._icon_size) / 2 + hl_h / 2 + dy
        if self._icon:
            draw_icon(self, self._icon, cx, cy, size=self._icon_size,
                      color=fg, width=2)
            cx += self._icon_size + 6
        if self._text:
            self.create_text(cx, by1 + (by2 - by1) / 2 + hl_h / 4 + dy,
                             text=self._text, fill=fg, font=self._font,
                             anchor="w")

    def _draw_glass(self, w, h):
        """玻璃档案按钮：圆角 + 白系描边 + 顶缘 3px 高光（按压高光消失=下沉）。
        v3.14.0 A2（14-6 遗留③）：玻璃风格不再像素直角。"""
        r = 10
        if not self._enabled:
            fill, fg, edge, hl = self._fill_dis, self._fg_dis, self._fill_dis, ""
        elif self._pressed:
            fill, fg, edge, hl = self._fill_hv, self._fg, self._edge, ""
        else:
            fill, fg, edge, hl = self._fill, self._fg, self._edge, self._hl
        self._round_rect(1, 1, w - 1, h - 1, r, fill=fill, outline=edge, width=2)
        if hl:
            self._round_rect(3, 2, w - 3, 2 + 3, max(r - 3, 4),
                             fill=hl, outline="")
        dy = 1 if self._pressed else 0
        cx = self.PAD_X + 2
        cy = (h - self._icon_size) / 2 + dy
        if self._icon:
            draw_icon(self, self._icon, cx, cy, size=self._icon_size,
                      color=fg, width=2)
            cx += self._icon_size + 6
        if self._text:
            self.create_text(cx, h / 2 + dy, text=self._text,
                             fill=fg, font=self._font, anchor="w")

    def set_enabled(self, on):
        self._enabled = bool(on)
        self.configure(cursor="hand2" if on else "arrow")
        self._hover = False
        self._pressed = False
        self._draw()

    def is_enabled(self):
        return self._enabled

    def invoke(self):
        if self._enabled and self._command:
            self._command()

    def configure_text(self, text=None, icon=None):
        if text is not None:
            self._text = text
        if icon is not None:
            self._icon = icon
        self._draw()

    def refresh(self):
        """主题切换后按 kind 重取色。幂等无害。"""
        pal = _pal()
        if self._kind == "primary":
            self._fill = pal["ACCENT"]
            self._fill_hv = pal["ACCENT_HV"]
            self._edge = _mix(pal["ACCENT"], "#000000", 0.35)
            self._fg = "#ffffff"
        elif self._kind == "danger":
            self._fill = pal["DANGER"]
            self._fill_hv = pal["DANGER_HV"]
            self._edge = _mix(pal["DANGER"], "#000000", 0.35)
            self._fg = "#ffffff"
        else:
            self._fill = pal["SURFACE"]
            self._fill_hv = _mix(pal["SURFACE"], pal["FG"], 0.08)
            self._edge = _mix(pal["BORDER"], pal["FG"], 0.30)
            self._fg = pal["FG"]
        self._fill_dis = _mix(pal["FG"], pal["BG"], 0.88)
        self._fg_dis = _mix(pal["FG"], pal["BG"], 0.55)
        self._hl = "#ffffff" if not _pal_dark(pal) else _mix(self._fill, "#ffffff", 0.30)
        self._bg_master = pal["BG"]
        self.configure(bg=pal["BG"])
        self._draw()
