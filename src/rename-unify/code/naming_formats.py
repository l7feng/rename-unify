# -*- coding: utf-8 -*-
"""目录命名格式：字段白名单、补零及Windows单层名称校验。"""
import re
from string import Formatter

FIELDS = {"片名", "等级", "集数", "日期", "版本", "用户"}
DEFAULT_EPISODE = "{片名} {集数}集"
DEFAULT_PROJECT = "{片名}{等级}_{日期}_{用户}"

def render_folder(template, values, padding=0, require_episode=False):
    template = str(template or "").strip()
    if not template:
        raise ValueError("命名格式不能为空")
    try:
        parts = list(Formatter().parse(template))
    except ValueError as exc:
        raise ValueError("命名格式的大括号不完整") from exc
    used = set()
    for literal, field, spec, conversion in parts:
        if field is not None:
            if field not in FIELDS or spec or conversion:
                raise ValueError("命名格式含未知字段或不支持的格式: " + str(field))
            used.add(field)
    if require_episode and "集数" not in used:
        raise ValueError("集数文件夹格式必须包含{集数}")
    width = int(padding or 0)
    if width not in (0, 2, 3):
        raise ValueError("集数位数仅支持不补零、两位或三位")
    data = {k: str(values.get(k, "") or "").strip() for k in FIELDS}
    if "集数" in used:
        if not data["集数"].isdigit():
            raise ValueError("无法取得有效集数")
        data["集数"] = str(int(data["集数"])).zfill(width)
    result = re.sub(r"\s+", " ", template.format(**data)).strip()
    if (not result or result in (".", "..") or re.search(r'[<>:"/\\|?*\x00-\x1f]', result)
            or result.endswith((".", " ")) or len(result) > 200
            or re.fullmatch(r"(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", result)):
        raise ValueError("命名结果不是有效的Windows文件夹名")
    return result
