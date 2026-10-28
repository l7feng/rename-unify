# -*- coding: utf-8 -*-
"""pt-audio-toolkit 统一打包入口（三工具 → PyInstaller onedir + windowed）。

用法
----
    python tools/build.py                          # 构建全部三个工具
    python tools/build.py pt-tools rename-unify    # 只构建指定工具
    python tools/build.py --date 20260928
    python tools/build.py --out-root D:\\somewhere\\exe
    python tools/build.py --py C:\\path\\to\\python.exe

出口布局（2026-10-14 人类指定）：
    <out-root>/01-ProTools工具箱/pt-tools-T-v<工具版本>/
    <out-root>/02-剪映工程工具包/jianying-draft-toolkit-T-v<工具版本>/
    <out-root>/03-统一命名工具/rename-unify-T-v<工具版本>/
exe 与 _internal 同级；版本读各工具 APP_VERSION，日期仅用于构建记录。
PyInstaller --name 保持 ASCII，完成后 exe 加中文 T版名。
同版本重建前包完整移入 <out-root>/00-归档/<原目录名>-重建前-<时间戳>/。
H版由 tools/v4_pack/build_v4.py 构建到工具外层编号01至03，独立仓剧本工具外层编号04。

为什么不用各目录的 build.ps1
----------------------------
PowerShell 把原生程序的 stderr 当错误流，配 ``$ErrorActionPreference=Stop`` 时，
PyInstaller 打出第一行 ``INFO:`` 就会触发 NativeCommandError 而**静默中断**
（表现为只输出 "building ..." 就退出）。四个 build.ps1 里有三份都在跟这个坑搏斗
（rename-unify 那份还专门写了一段注释解释它，并单独把 ErrorActionPreference
降级成 Continue 绕过）。

本脚本一律直调 ``python -m PyInstaller``，逐工具取 returncode，
失败时打印「工具名 + 返回码 + 关键 stderr 行」，**绝不静默**。

各目录的 build.ps1 已降级为转发本脚本的薄壳，既有调用方式（``.\\build.ps1``）不变。
"""
import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# 控制台默认 GBK，打印 ⚠/✅ 之类字符会 UnicodeEncodeError 把构建中断
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

REPO = Path(__file__).resolve().parent.parent

# 每个工具：入口 / PyInstaller --name（= 出口文件夹名 ASCII 前缀）/ 额外参数 /
#          后置动作 / 中文展示名（= exe 文件名）/ 版本定义文件
TARGETS = [
    {
        "key": "pt-tools",
        "entry": "src/pt-tools/pt_tools_gui.py",
        "name": "pt-tools",
        "args": ["--hidden-import", "tkinterdnd2", "--collect-data", "tkinterdnd2"],
        "post": "pt_tools_skills",
        "cn": "Pro Tools工具箱-T版",
        "folder": "01-ProTools工具箱/pt-tools-T",
        "version_file": "src/pt-tools/ptools/core/settings.py",
    },
    {
        "key": "jianying-draft-toolkit",
        "entry": "src/jianying-draft-toolkit/code/gui.py",
        "name": "jianying-draft-toolkit",
        "args": ["--hidden-import", "tkinterdnd2", "--collect-data", "tkinterdnd2"],
        "post": "jianying_tools",
        "cn": "剪映工程工具包-T版",
        "folder": "02-剪映工程工具包/jianying-draft-toolkit-T",
        "version_file": "src/jianying-draft-toolkit/code/main.py",
    },
    {
        "key": "rename-unify",
        "entry": "src/rename-unify/code/main.py",
        "name": "rename-unify",
        "args": ["--paths", "src/rename-unify/code",
                 "--hidden-import", "tkinterdnd2", "--collect-data", "tkinterdnd2"],
        "post": None,
        "cn": "统一命名工具-T版",
        "folder": "03-统一命名工具/rename-unify-T",
        "version_file": "src/rename-unify/code/config.py",
    },
]

LOG = []


def say(msg=""):
    print(msg, flush=True)
    LOG.append(msg)


# ── 版本 ─────────────────────────────────────────────────────
_VERSION_RE = re.compile(r"""^APP_VERSION\s*=\s*["']([^"']+)["']""", re.M)


def tool_version(t):
    """工具自己的版本：从其源码里的 `APP_VERSION = "x.y.z"` 解析。

    出口目录名带自己的版本号，必须与窗口标题里显示的一致，所以这里**读源码**
    而不是在打包脚本里另抄一份（抄一份必然漂移）。
    """
    p = REPO / t["version_file"]
    try:
        m = _VERSION_RE.search(p.read_text(encoding="utf-8"))
        if m:
            return m.group(1)
    except OSError:
        pass
    say("[WARN] %s 读不到版本（%s），出口目录版本号回落 0.0.0" % (t["key"], t["version_file"]))
    return "0.0.0"


def tool_out_dir(t, out_root, date):
    """该工具的出口目录：<out-root>/<序号-中文名-T版>-v<tool-version>/。

    每个工具独立一个文件夹，版本读各自源码里的 APP_VERSION（不再共用仓库版本）。
    """
    ver = tool_version(t)
    return Path(out_root) / ("%s-v%s" % (t["folder"], ver))


# ── 构建解释器自检 ───────────────────────────────────────────
def check_builder(py):
    """返回问题列表（空 = 通过）。不静默回落。"""
    problems = []
    if not os.path.isfile(py):
        problems.append("解释器不存在：%s" % py)
        return problems
    r = subprocess.run([py, "-c", "import tkinter"], capture_output=True)
    if r.returncode != 0:
        problems.append("解释器缺少 tkinter（GUI 打包必需）：%s" % py)
    r = subprocess.run([py, "-m", "PyInstaller", "--version"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        problems.append("解释器未安装 PyInstaller：%s\n      安装：%s -m pip install pyinstaller"
                        % (py, py))
    # v3.1.0：pyaaf2 必查 —— 它只被 aaf_writer 的函数内 import 引用，
    # 打包环境缺它时 PyInstaller 不报错、exe 照样出炉，但 AAF 导出
    # 必然失败且旧版不写文件日志，用户只会看到「AAF 不见了」
    #（2026-09-27 实锤：v2.7.0~v3.0.1 全部已发布 exe 都没打进 pyaaf2）。
    r = subprocess.run([py, "-c", "import aaf2"], capture_output=True, text=True)
    if r.returncode != 0:
        problems.append("打包环境缺少 pyaaf2（剪映 AAF 导出必需）\n      安装：%s -m pip install pyaaf2"
                        % py)
    return problems


# ── 后置动作（只对构建成功的工具做）──────────────────────────
def post_pt_tools_skills(out_root, t):
    """把四个技能脚本内置到 _internal/skills/<skill>/scripts/（PathResolver 的查找布局）。

    来源取**仓库内** `src/pt-tools/skills/`（唯一真源）。
    外部 `%USERPROFILE%\\Ai-Files\\Skills\\protools-skills\\` 是**技能生效区**，
    2026-09-23 已逐文件核对 MD5，脚本与仓内完全一致 —— 因此从仓内复制不会引入旧版。

    注意：venv（含 py-ptsl）**不打包** —— 体积大且属运行时环境。
    故 exe 自带脚本、但运行仍需一个含 venv 的技能目录（见 pt-tools 的「设置 > 技能目录」）。
    """
    dst_root = Path(out_root) / "_internal" / "skills"
    src_root = REPO / "src" / "pt-tools" / "skills"
    copied = []
    for sk in ("pt-scanner", "pt-exporter", "pt-cleaner", "pt-clips"):
        s = src_root / sk / "scripts"
        if not s.is_dir():
            continue
        d = dst_root / sk / "scripts"
        d.mkdir(parents=True, exist_ok=True)
        for f in sorted(s.iterdir()):
            if f.suffix == ".py":
                shutil.copy2(f, d / f.name)
                copied.append("%s/%s" % (sk, f.name))
            elif f.is_dir():
                # v3.1.0：子目录（如 pt-clips/scripts/core/，技能自洽的 host
                # 副本）也要带 —— 旧版只平铺 *.py，导致技能副本 import
                # `core.host` 时 ModuleNotFoundError，「生成交付包」必挂。
                # 2026-09-28：**必须排除 __pycache__**。源码改名脱敏后，
                # 仓里遗留的旧 .pyc 里仍烤着改名前的字面量（打包产物字节级
                # 复扫实测命中），cpython-313 那种更久远的缓存同理。
                # .pyc 既不参与运行（源码在即），只会把旧内容带进 exe。
                shutil.copytree(f, d / f.name, dirs_exist_ok=True,
                                ignore=shutil.ignore_patterns(
                                    "__pycache__", "*.pyc", "*.pyo"))
    say("[post] pt-tools 内置技能脚本 %d 个 -> %s" % (len(copied), dst_root))
    for c in copied:
        say("       · %s" % c)
    return len(copied) > 0


def post_jianying_tools(out_root, t):
    """复制 tools/（jy-draftc 解密器）到 exe 同级。

    onedir 而非 onefile 的原因就在这里：jy-draftc 运行时要把剪映安装路径
    写进 .env，需要 exe 旁有**真实目录**（onefile 会解到临时目录且被清理）。
    """
    src = REPO / "src" / "jianying-draft-toolkit" / "tools"
    dst = Path(out_root) / "tools"
    if dst.is_dir():
        shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(src, dst)
    exe = dst / "jy-draftc" / "jy-draftc-amd64-windows" / "jy-draftc.exe"
    say("[post] jianying tools/ 已复制，解密器存在=%s" % exe.is_file())
    return exe.is_file()


POST = {
    "pt_tools_skills": post_pt_tools_skills,
    "jianying_tools": post_jianying_tools,
}


# ── v3.12.0 更新日志部署 ─────────────────────────────────────
CHANGELOG_PATH = REPO / "CHANGELOG.md"
UPDATE_BAT_SRC = REPO / "tools" / "更新日志.bat"


def latest_changelog_section():
    """取 CHANGELOG.md 最新一个版本小节（第一个 '## ' 到下一个 '---'）。"""
    text = CHANGELOG_PATH.read_text(encoding="utf-8")
    m = re.search(r"^## .+$", text, re.M)
    if not m:
        return None
    nxt = text.find("\n---", m.end())
    body = text[m.start():nxt if nxt != -1 else len(text)]
    return body.strip()


def deploy_update_notes(out_root, out_roots, results):
    """各成功工具包内部部署 更新日志.bat + UPDATES.txt。

    UPDATES.txt = CHANGELOG.md 最新版本小节（UTF-8）；bat 为纯 ASCII 逻辑，
    chcp 65001 后 type 中文内容，避开 bat 内嵌中文的代码页坑。
    同时给每个构建成功的工具目录塞一份 UPDATES.txt（自包含）。
    """
    section = latest_changelog_section()
    if not section:
        say("[WARN] CHANGELOG.md 未解析到版本小节，跳过 UPDATES.txt 生成")
        return
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    content = ("pt-audio-toolkit 更新内容\n"
               "（由 tools/build.py 于 %s 打包时自动生成，源：CHANGELOG.md 最新小节）\n"
               % stamp) + "=" * 60 + "\n\n" + section + "\n"
    for key, d in out_roots.items():
        if results.get(key) and Path(d).is_dir():
            dest = Path(d)
            (dest / "UPDATES.txt").write_text(content, encoding="utf-8")
            if UPDATE_BAT_SRC.is_file():
                shutil.copy2(str(UPDATE_BAT_SRC), str(dest / UPDATE_BAT_SRC.name))
    say("更新日志已部署到各构建成功的完整包内")



# ── 单工具构建 ───────────────────────────────────────────────
def build_one(py, t, out_root, work_root, spec_dir, staging_root, run_id):
    name = t["name"]
    entry = REPO / t["entry"]
    say()
    say("=" * 72)
    say("[build] %s  ← %s" % (name, t["entry"]))
    say("=" * 72)

    if not entry.is_file():
        say("[FAIL] 入口不存在：%s" % entry)
        return False

    # ⚠️ --distpath 指向**每次全新的 staging 目录**，而不是最终出口。
    # 原因：PyInstaller 的 --noconfirm 会删除 --distpath 下已有的同名目录；
    # 出口在受保护路径（如 D:\）下、文件数超过批量阈值时会被安全策略拦截并中断构建
    # （实测：「Removing dir …」→ SAFE_DELETE_BULK_CONFIRM_REQUIRED，count=945）。
    # 改为先建到 staging，再把旧产物**改名保留**、新产物**移入** —— 全程无删除。
    cmd = [py, "-m", "PyInstaller", "--noconfirm", "--clean",
           "--windowed", "--onedir", "--name", name,
           "--distpath", str(staging_root),
           "--workpath", str(work_root / name),
           "--specpath", str(spec_dir)]
    # args 里的仓库相对路径（如 --paths src/rename-unify/code）转绝对路径：
    # PyInstaller 以**当前工作目录**解析这些参数，脚本从别处调用时会找不到
    cmd += [str(REPO / x) if x.startswith("src/") else x for x in t["args"]]
    cmd.append(str(entry))

    t0 = datetime.datetime.now()
    p = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    dt = (datetime.datetime.now() - t0).total_seconds()

    built = staging_root / name
    ok = (p.returncode == 0) and (built / (name + ".exe")).is_file()
    dst = Path(out_root)
    if ok:
        if dst.exists():
            archive = dst.parent.parent / "00-归档"
            archive.mkdir(parents=True, exist_ok=True)
            prev = archive / (dst.name + ".重建前-" + run_id + "-" + datetime.datetime.now().strftime("%f"))
            dst.rename(prev)
            say("[keep] 旧产物已完整归档：%s" % prev)
        # dst 此时不存在，move 即把 staging 产物目录整体改名到最终出口
        shutil.move(str(built), str(dst))
        # 打包后把 exe 改名为中文T版展示名
        old_exe = dst / (name + ".exe")
        new_exe = dst / (t["cn"] + ".exe")
        if old_exe.is_file():
            if new_exe.exists():
                new_exe.unlink()
            old_exe.rename(new_exe)
            say("[cn] exe 已改名：%s -> %s" % (old_exe.name, new_exe.name))
    exe = dst / (t["cn"] + ".exe")
    say("[%s] %s（%.0f 秒）" % ("OK" if ok else "FAIL", exe if ok else "未产出 exe", dt))
    if not ok:
        # 关键：打印工具名 + 返回码 + 末尾 stderr，绝不静默
        say("[FAIL] 工具=%s 返回码=%s" % (name, p.returncode))
        tail = (p.stdout or "").strip().splitlines() + (p.stderr or "").strip().splitlines()
        for line in tail[-18:]:
            say("       | %s" % line)
    return ok


def default_out_root():
    """出口根解析链（2026-09-28 裁决 10-9 甲案，跨机通用）：

    PT_EXE_ROOT 环境变量
        → tools/build.local.json 的 out_root（本机覆盖文件，*.local.json 不入库）
        → %USERPROFILE%\\pt-toolkit\\exe（中性兜底，任何机器成立）。
    作者机器请用前两级保持原出口（本机已建 build.local.json）。
    """
    env = os.environ.get("PT_EXE_ROOT")
    if env:
        # 当前环境可能仍继承退役出口；只兼容已确定的旧路径。
        if Path(env) == Path(r"D:\Ai-Files\Agent-Preset\exe"):
            return r"D:\Ai-Files\Tools\Exe"
        return env
    try:
        # utf-8-sig：兼容带 BOM 的本机配置（2026-09-29 实测教训——公司机写入的
        # build.local.json 带 BOM，"utf-8" 解析抛异常被静默吞，出口根悄悄兜底 C 盘）
        local = json.loads((REPO / "tools" / "build.local.json")
                           .read_text(encoding="utf-8-sig"))
        if local.get("out_root"):
            return local["out_root"]
    except Exception:
        pass
    return str(Path.home() / "pt-toolkit" / "exe")


def main():
    ap = argparse.ArgumentParser(
        description="pt-audio-toolkit 三工具统一打包",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tools", nargs="*", help="要构建的工具名（缺省=全部）")
    ap.add_argument("--out-root", default=default_out_root(),
                    help="exe 出口根目录")
    ap.add_argument("--date", default=datetime.date.today().strftime("%Y%m%d"),
                    help="发布日期 YYYYMMDD（缺省今天）")
    ap.add_argument("--py", default=sys.executable,
                    help="构建用解释器（必须带 tkinter 与 PyInstaller）")
    ap.add_argument("--work", default=os.path.join(
        os.environ.get("TEMP") or os.environ.get("TMP") or "/tmp", "pt-toolkit-build"),
        help="PyInstaller 中间产物目录")
    args = ap.parse_args()

    work_root = Path(args.work) / "work"
    spec_dir = Path(args.work) / "spec"

    say("pt-audio-toolkit 统一打包")
    say("  仓库     : %s" % REPO)
    say("  出口根   : %s" % args.out_root)
    say("  解释器   : %s" % args.py)
    say()

    problems = check_builder(args.py)
    if problems:
        say("构建前置检查未通过：")
        for x in problems:
            say("  ✗ %s" % x)
        say()
        say("提示：GUI 打包需要带 tkinter 的解释器（官方 Windows 安装版自带），")
        say("      且需 pip install pyinstaller；剪映工具另需 pip install tkinterdnd2。")
        return 2

    wanted = [t for t in TARGETS if not args.tools or t["key"] in args.tools]
    unknown = [k for k in args.tools if k not in [t["key"] for t in TARGETS]]
    if unknown:
        say("未知工具名：%s" % ", ".join(unknown))
        say("可用：%s" % ", ".join(t["key"] for t in TARGETS))
        return 2
    if not wanted:
        say("没有匹配到任何工具。")
        return 2

    # 每个工具独立一个中文编号T版出口目录，日期仅保留在构建记录
    out_roots = {}
    for t in wanted:
        out_roots[t["key"]] = tool_out_dir(t, args.out_root, args.date)
    for d in sorted({str(v) for v in out_roots.values()}):
        Path(d).parent.mkdir(parents=True, exist_ok=True)
        say("  出口目录：%s" % d)
    say()

    spec_dir.mkdir(parents=True, exist_ok=True)

    # 每次构建用全新的 staging：PyInstaller 会删除 --distpath 下的同名目录，
    # staging 是唯一且位于系统临时区，既避开批量删除保护，也不会误删已有产物。
    run_id = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    staging_root = Path(args.work) / "staging" / run_id
    staging_root.mkdir(parents=True, exist_ok=True)

    results = {}
    for t in wanted:
        try:
            results[t["key"]] = build_one(args.py, t, out_roots[t["key"]],
                                          work_root, spec_dir, staging_root, run_id)
        except Exception as e:
            say("[FAIL] %s 构建异常：%s" % (t["key"], e))
            results[t["key"]] = False

    # 后置动作（只对构建成功的工具做）
    for t in wanted:
        if results.get(t["key"]) and t.get("post"):
            try:
                results[t["key"] + ":post"] = POST[t["post"]](out_roots[t["key"]], t)
            except Exception as e:
                say("[FAIL] %s 后置异常：%s" % (t["key"], e))
                results[t["key"] + ":post"] = False

    # v3.12.0：更新日志部署 —— 每次打包自动刷新出口根的 UPDATES.txt +
    # 更新日志.bat（用户双击即可看到「这次更新改了什么」）
    if any(results.get(t["key"]) for t in wanted):
        try:
            deploy_update_notes(args.out_root, out_roots, results)
        except Exception as e:
            say("[FAIL] 更新日志部署异常：%s" % e)

    say()
    say("=" * 72)
    say("打包汇总")
    say("=" * 72)
    for k, v in results.items():
        say("  %-32s %s" % (k, "OK" if v else "FAIL"))
    say()
    for t in wanted:
        d = out_roots[t["key"]]
        if d.is_dir():
            n = sum(len(fs) for _r, _dd, fs in os.walk(d))
            mb = sum(os.path.getsize(os.path.join(r, f))
                     for r, _dd, fs in os.walk(d) for f in fs) / 1048576.0
            say("  %-32s %6.1f MB  %4d 文件" % (d.name + "/", mb, n))
    say()
    say("  剧本双语拆分工具不在本仓 —— 由 %USERPROFILE%\\Ai-Files\\Repos\GitHub\\script-splitter")
    say("  的 build_exe.py 自行构建到 04-剧本双语拆分工具/script-splitter-v<版本>\\ 。")

    log_path = Path(args.work) / "build.log"
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("\n".join(LOG), encoding="utf-8")
        say()
        say("日志：%s" % log_path)
    except Exception:
        pass

    # 清理本轮 staging（位于系统临时区，不涉及出口目录）
    shutil.rmtree(staging_root, ignore_errors=True)

    say()
    say("⚠️ 分发时把整个工具文件夹一起给 —— _internal/ 必须与 exe 同级。")
    return 0 if all(v for v in results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
