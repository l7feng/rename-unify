# -*- coding: utf-8 -*-
"""v4 HTML 壳打包（阶段 E）：onedir + web/api/shell 资源内嵌

产物：<out-root>/<01至03-中文工具名>/<英文名-H>-v<仓库VERSION>/<中文名-H版>.exe
用法：python tools/v4_pack/build_v4.py [pt|jy|re|all] [--out-root DIR] [--py PY]
"""
from __future__ import annotations
import argparse
import json
import re
import datetime
import os
import shutil
import subprocess
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

REPO = Path(__file__).resolve().parent.parent.parent
V4 = REPO / "src" / "v4"
WEB = Path(os.environ.get("PT_WEB_ROOT", str(REPO / "web")))
PACK = REPO / "tools" / "v4_pack"
sys.path.insert(0, str(REPO / "tools"))
from build import default_out_root

TOOLS = {
    "pt": {
        "entry": "shell.desktop_app",
        "name": "pt-tools-v4",
        "zh": "Pro Tools工具箱-H版",
        "folder": "01-ProTools工具箱/pt-tools-H",
        "hidden": ["api.pt_api", "shell.httpd", "ptools.core.settings", "ptools.core.config",
                   "ptools.core.i18n", "ptools.core.naming", "ptools.core.scanner"],
    },
    "jy": {
        "entry": "shell.jy_desktop",
        "name": "jianying-draft-toolkit-v4",
        "zh": "剪映工程工具包-H版",
        "folder": "02-剪映工程工具包/jianying-draft-toolkit-H",
        # ptools.core.config 为模块级依赖（界面偏好复用 pt C2 层），
        # 2026-09-30 真启动冒烟实锤：缺 --paths src/pt-tools 会运行时 ModuleNotFoundError
        "hidden": ["api.jy_api", "shell.httpd", "ptools.core.config"],
    },
    "re": {
        "entry": "shell.re_desktop",
        "name": "rename-unify-v4",
        "zh": "统一命名工具",
        "folder": "03-统一命名工具/rename-unify",
        "hidden": ["api.re_api", "shell.httpd", "ptools.core.config"],
    },
}

# This independent distribution only builds its own application.
TOOLS = {"re": TOOLS["re"]}

ENTRY_TMPL = '''# -*- coding: utf-8 -*-
"""v4 壳打包入口（{zh}）——源码直跑与打包后双兼容。

frozen 时 sys._MEIPASS 已在 sys.path，web/ 与 api/、shell/ 由 --add-data 落在那里，
故 httpd.WEB_DIR 解析（上级目录/web）自然命中内嵌资源，无需改 v4 源码。
"""
import os
import sys

if getattr(sys, "frozen", False):
    BASE = sys._MEIPASS
else:
    BASE = r"{v4}"

if BASE not in sys.path:
    sys.path.insert(0, BASE)

from {entry} import main

if __name__ == "__main__":
    main()
'''


def tool_version(key: str) -> str:
    version = json.loads((WEB / "app-versions.json").read_text(encoding="utf-8"))[key]
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Invalid tool version")
    return version


def tool_out_dir(key: str, out_root: Path) -> Path:
    version = tool_version(key)
    return Path(out_root) / (TOOLS[key]["folder"] + "-v" + version)


def build_one(key: str, out_root: Path, py: str, date: str) -> int:
    cfg = TOOLS[key]
    work = Path(out_root) / ("_build_" + key)
    if work.exists():
        raise FileExistsError("Build workspace already exists: %s" % work)
    work.mkdir(parents=True, exist_ok=True)
    entry_file = work / ("entry_%s.py" % key)
    entry_file.write_text(
        ENTRY_TMPL.format(zh=cfg["zh"], v4=str(V4).replace("\\", "\\\\"), entry=cfg["entry"]),
        encoding="utf-8")

    version = tool_version(key)
    version_file = work / "version-info.txt"
    version_tuple = tuple(int(part) for part in version.split(".")) + (0,)
    metadata = "VSVersionInfo(ffi=FixedFileInfo(filevers=%r, prodvers=%r, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0,0)), kids=[StringFileInfo([StringTable('040904B0', [StringStruct('FileDescription', %r), StringStruct('FileVersion', %r), StringStruct('ProductName', %r), StringStruct('ProductVersion', %r)])]), VarFileInfo([VarStruct('Translation', [1033,1200])])])" % (version_tuple, version_tuple, cfg['zh'], version, cfg['zh'], version)
    version_file.write_text(metadata, encoding="utf-8")
    dist = work / "dist"
    cmd = [
        py, "-m", "PyInstaller",
        "--noconfirm", "--onedir", "--windowed", "--version-file", str(version_file),
        "--name", cfg["name"],
        "--distpath", str(dist),
        "--workpath", str(work / "work"),
        "--specpath", str(work),
        "--paths", str(V4),
        "--add-data", str(WEB) + os.pathsep + "web",
        "--add-data", str(V4 / "api") + os.pathsep + "api",
        "--add-data", str(V4 / "shell") + os.pathsep + "shell",
    ]
    letter = {'pt':'p','jy':'j','re':'r'}[key]
    cmd += ['--icon', str(WEB / 'assets' / 'logos' / (letter + '.ico'))]
    for h in cfg["hidden"]:
        cmd += ["--hidden-import", h]
    # 工具核心源码（同进程直调，非 pip 包）；ptools 家族级依赖三个工具都带上
    cmd += ["--paths", str(REPO / "src" / "pt-tools")]
    if key == "jy":
        cmd += ["--paths", str(REPO / "src" / "jianying-draft-toolkit" / "code")]
    if key == "re":
        cmd += ["--paths", str(REPO / "src" / "rename-unify" / "code")]
    cmd += ["--exclude-module", "tkinter", "--exclude-module", "PyQt5",
            "--exclude-module", "IPython", "--exclude-module", "pytest"]
    cmd.append(str(entry_file))

    print("[v4-pack] %s: %s" % (key, " ".join(cmd[:6]) + " ..."))
    r = subprocess.run(cmd, cwd=str(work), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print("[v4-pack] FAIL %s rc=%d" % (key, r.returncode))
        tail = (r.stderr or "").strip().split("\n")[-25:]
        print("\n".join(tail))
        return r.returncode

    src_dir = dist / cfg["name"]
    if not src_dir.is_dir():
        print("[v4-pack] FAIL %s: dist dir missing %s" % (key, src_dir))
        return 2
    if not (src_dir / (cfg["name"] + ".exe")).is_file():
        print("[v4-pack] FAIL %s: built exe missing" % key)
        return 2
    final = tool_out_dir(key, out_root)
    final.parent.mkdir(parents=True, exist_ok=True)
    if final.exists():
        archive = final.parent.parent / "00-归档"
        archive.mkdir(parents=True, exist_ok=True)
        previous = archive / (final.name + "-重建前-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
        final.rename(previous)
    shutil.move(str(src_dir), str(final))
    exe = final / (cfg["name"] + ".exe")
    zh_exe = final / (cfg["zh"] + ".exe")
    if exe.is_file():
        exe.rename(zh_exe)
        print("[v4-pack] OK %s -> %s" % (key, zh_exe))
    else:
        print("[v4-pack] WARN %s: exe not found at %s" % (key, exe))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="v4 HTML 壳打包（阶段 E）")
    ap.add_argument("tools", nargs="*", default=["all"], choices=list(TOOLS) + ["all"])
    ap.add_argument("--out-root", default=str(REPO / "build" / "output"))
    ap.add_argument("--py", default=sys.executable)
    ap.add_argument("--date", default=datetime.datetime.now().strftime("%Y%m%d"))
    args = ap.parse_args()

    keys = list(TOOLS) if "all" in args.tools else args.tools
    out = Path(args.out_root)
    out.mkdir(parents=True, exist_ok=True)
    rc = 0
    for k in keys:
        rc |= build_one(k, out, args.py, args.date)
    print("[v4-pack] DONE rc=%d" % rc)
    return rc


if __name__ == "__main__":
    sys.exit(main())
