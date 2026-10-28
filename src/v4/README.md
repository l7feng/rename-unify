> 2026-10-22：剪映EXE v4.3.0新增OFX管理及精简工作流；界面仍在已登记的库外Web真源，管理实现为api/ofx_manager.py。项目72维护本轮验收，其他工具版本未改。

> 2026-10-14现行Web源：D:/Ai-Files/Tools/Html/pt-audio-toolkit/source。src/v4仅保留API与shell；PT_WEB_ROOT可覆盖开发/打包Web根，冻结包仍使用内嵌web。人类明确选择源码迁出，后文原目录说明按历史保留。

# v4 · H版桌面工具

当前页面版本 v4.1.1（2026-10-12），三个完整 EXE 入口见仓库 README。共用材质控制检查与隔离启动已通过；以下阶段 A 说明作为历史实现记录保留。

> 真源 = 知识库项目 12 `30-2026-09-29-HTML版换壳-实施方案.md`（五阶段 A-E）；本目录只放代码。
> 双线并行：本目录 = HTML 线；tkinter 线 = 31 号交接提示词（另窗口），互不碰对方文件。

## 结构

```
src/v4/
├─ shell/
│  ├─ httpd.py          # 127.0.0.1 固定端口静态服务（26789，占用+1 自愈）
│  └─ desktop_app.py    # 壳入口：pywebview(WebView2) 优先 / --shell edge 回退
├─ api/
│  └─ pt_api.py         # js_api 桥：配置读写（复用 C2 双文件层）/ 目录选择 / run_scan 子进程+流式进度
└─ web/
   └─ index.html        # pt-tools 扫描建档页（双风格×双模式，CSS 稿色值 1:1 平移）
```

## 跑法

```bash
# 浏览器演示态（无桥，看视觉）
python shell/httpd.py            # → http://127.0.0.1:26789/index.html

# 壳内全功能（pywebview）
python shell/desktop_app.py

# Edge 回退（WebView2 渲染异常时）
python shell/desktop_app.py --shell edge
```

## 阶段 A 闸门（30 号 §三）

实拍 vs CSS 稿并排对比 + 人类真机双击点头。
