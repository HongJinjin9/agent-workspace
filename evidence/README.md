# V视听（VStudio）— UI Before / After 视觉证据

- **Ticket**：VCP 系统的「V视听」功能开发（GitHub issue HongJinjin9/agent-workspace#3）
- **应用**：VCPChat Electron（xvfb 虚拟显示器运行；CDP 调试端口 `127.0.0.1:9222`）
- **证据性质**：全部为**真实运行中应用窗口的 CDP 截图**（`Page.captureScreenshot`），不是 mockup / 设计稿 / 合成图。点击、播放、批注选中均通过 CDP `Input.dispatchMouseEvent` 真实鼠标事件或页面内真实 API 完成，截图反映采集瞬间的实际画面。
- **采集工具**：`tools/cdp.js`、`tools/capture-after.js`、`tools/capture-interactions.js`、`tools/resize-main-window.sh`（Node ≥18 + `/app/VCPChat/node_modules/ws`，无需安装依赖）。
- **采集人**：vstudio-evidence（Team Lead: lead）
- **窗口/主题一致性**：前后主窗口均为 **2300 × 843 @ dpr1** 整窗截图、同一浅色主题（`light-theme`），未裁剪/未缩放。VStudio 子窗口为设计尺寸 **1440 × 900**（before 阶段不存在该窗口）。

> 尺寸说明（如实记录）：before 采集时主窗口 X 窗口为 2300×843。应用重启后主窗口恢复默认 1300×800，本证据在 after 采集前用 `xdotool` 将 X 窗口设置为 2308×847（Chromium 8px 边框 → 内容区 innerWidth 2300 × innerHeight 843），与 before 完全一致；截图实际为 2300×843。会话期间 xvfb 屏幕为 1600×1000，窗口大于屏幕不影响 CDP 全视口截图。方法脚本见 `tools/resize-main-window.sh`。

---

## BEFORE（改动前：当前运行实例中尚无「视听」）

采集时间：**2026-11-02T10:40Z**（UTC）。应用为引入 VStudio 之前的源码运行实例。

| 文件 | 尺寸 | 说明 |
| --- | --- | --- |
| `before-main.png` | 2300×843 | 主窗口整窗。左侧群聊对话 + 底部聊天输入框 `#messageInput`（占位「输入消息... (Shift+Enter 换行)」），右侧 VCP 侧栏（工作区侧栏）。浅色主题。 |
| `before-tray.png` | 2300×843 | 同窗口同尺寸，右侧 VCP 侧栏「首页」launcher 切到**「应用」标签页**（该版本实际可见的应用托盘入口；旧 `#appTrayDrawer`+「更多」按钮是 `display:none` 的遗留实现，见 `before/apps-before.json`）。显示全部 **23 个 App** 图标网格，**没有「视听」**。 |
| `before-apps-grid.png` | 640×404 | 应用网格裁剪细节。23 个 App：游戏/笔记/便签/翻译/音乐/协同/图表/文坊/记忆/论坛/日志/骰子/监听/主题/Loom/工具/数据/任务/插件/工程/终端/桌面/UI 组件库——**无「视听」**。 |
| `before/apps-before.json` | — | DOM 快照：应用名列表、`hasAudiovisual:false`、viewport 2300×843、launcher 当前 tab、旧托盘 DOM 状态、聊天输入框存在性。 |
| `before/targets-before.json` | — | CDP `/json` 目标快照：VCPChat 主窗口、ProjectForge、划词助手 3 个页面，**无 VStudio 窗口**。 |

复现（before）：

```bash
curl -s http://127.0.0.1:9222/json                     # 主窗口 main.html
node tools/cdp.js shot main.html before-main.png
node tools/cdp.js click main.html '#sidePaneViewLauncher .side-pane-launcher-tab[data-launcher-tab="apps"]'
node tools/cdp.js shot main.html before-tray.png
node tools/cdp.js shot main.html before-apps-grid.png --clipsel='#sidePaneViewLauncher .side-pane-launcher-app-grid'
```

---

## AFTER（改动后：真实 VStudio 功能）

采集时间：**2026-11-02T11:05Z**（UTC）。应用已于 10:52Z 重启并加载集成 VStudio 的最新代码；VStudio 窗口由本证据从「应用」托盘点击「视听」重新打开（窗口不存在重启，加载最新前端文件）。
演示工程：`proj_mvz5fnozzwxuh`「V视听演示 · AI 协同剪辑」，1280×720 @30fps，43.0s，5 场景 / 6 音轨 / 3 条批注；成片 `renders/final.mp4`（H.264+AAC，43.00s，1280×720，30fps）。

### 1) 主窗口 / 应用托盘入口

| 文件 | 尺寸 | 说明 |
| --- | --- | --- |
| `after-main.png` | 2300×843 | 重启后主窗口整窗，尺寸/主题与 `before-main.png` 完全一致；底部聊天输入框 `#messageInput` 仍存在且可见（placeholder 一致）。 |
| `after-tray.png` | 2300×843 | 同尺寸，「应用」标签页应用网格：**24 个 App，含「视听」**（film 胶片图标，位于「工程」右侧）。与 `before-tray.png` 直接对比：23 → 24，新增「视听」。 |
| `after-apps-grid.png` | 640×404 | 应用网格裁剪细节，可见「视听」图标与文字。 |

### 2) VStudio 窗口（点击「视听」后新开，1440×900 整窗）

| 文件 | 尺寸 | 说明 |
| --- | --- | --- |
| `after-vstudio.png` | 1440×900 | **VStudio 整窗（打开后的初始状态）**：顶栏「V视听 · VCP 视频协同工坊」+ 工程名 + 渲染状态 chip「已渲染」+ 时间码；左栏工程列表（1 个演示工程，海报缩略图、00:43 · 30fps、「已渲染」badge）与素材库（11 个素材）；中央 **16:9 画面预览**（1280×720 · 30fps · 43.0s，标题卡画面，叠加 3 个批注 pin 与虚线框选区域）+ 传输控制（播放/逐帧/±1s/时间码/帧号）；底部**多轨时间线**（5 场景视频轨 + 6 条音频轨 + 3 个批注 marker，播放头）；右栏**帧级批注** 3 条与「交给 AI」面板。 |
| `after-vstudio-project.png` | 1440×900 | 选中/加载演示工程后的整窗（与上一张同为真实窗口状态，用于工程列表细节对照）。 |
| `after-vstudio-projects.png` | 264×360 | 左栏工程列表细节：工程名、poster 缩略图、时长/帧率、更新时间、「已渲染」状态。 |
| `after-vstudio-preview.png` | 800×498 | 中央预览面板细节：`画面预览 1280×720 · 30fps · 43.0s`、16:9 画面、批注 pin/框、传输控制与时间码。 |
| `after-vstudio-timeline.png` | 800×286 | 多轨时间线细节：标尺（秒/帧）、5 个视频场景 clip（含缩略图/名称/时长）、4 条「旁白」音轨 + BGM 音轨 + SFX 音轨（含波形与音量）、3 个批注 marker 落在标尺上、播放头。 |
| `after-vstudio-annotations.png` | 336×546 | 帧级批注面板初始状态：3 条（#1 已解决 / #2 进行中 / #3 待处理）。 |
| `after-vstudio-agent.png` | 336×238 | 「交给 AI」面板（工程/帧/目标上下文 chip、快捷指令、输入框、发送按钮）。 |

### 3) 播放中画面（真实播放，非静态截图摆拍）

| 文件 | 尺寸 | 说明 |
| --- | --- | --- |
| `after-vstudio-playing.png` | 1440×900 | **播放中的整窗**：`video.readyState=4`，seek 到 15.05s 后点击播放，截图时 `currentTime=16.38s`（已前进 >1.3s）、`paused=false`；顶栏时间码 `00:00:16:17`、传输区 `帧 497 / 1290`、播放按钮显示暂停图标、时间线播放头位于 ~16s；画面为成片真实帧（「AI 剪辑流程」标题卡 + 01/02/03 步骤列表）。 |
| `after-vstudio-playing-preview.png` | 800×498 | 播放中预览面板细节（16:9 画面 + 时间码 + 暂停图标）。 |

### 4) 帧级批注：pin 高亮 + 批注列表（含 resolved）

| 文件 | 尺寸 | 说明 |
| --- | --- | --- |
| `after-vstudio-annotation.png` | 1440×900 | 点击批注 **#1（frame 45 / 00:00:01:15，target=画面元素，状态=已解决，AI 已回复）** 后整窗：画面跳转到 frame 45，**pin #1 高亮（放大圆环选中态）**，对应虚线框选区域高亮；右侧批注卡片 #1 选中态显示 `已解决`、区域坐标 `38% 34% 40%×30%` 与 AI 回复原文；「交给 AI」面板同步带出所选批注上下文（帧 45 · 画面元素 · 批注 #1 · 已解决）。 |
| `after-vstudio-annotation-pin.png` | 800×498 | 预览面板细节：高亮 pin #1 + 框选区域 + 其他 2 个批注 pin/框，画面为该批注对应帧。 |
| `after-vstudio-annotation-list.png` | 336×546 | 批注列表面板细节：3 条批注卡片，含状态徽标、帧号/时间码、区域坐标、文字、AI 回复（#1 已解决）、操作按钮（定位/标记/删除）。 |

### 5) 原始报告 JSON

| 文件 | 说明 |
| --- | --- |
| `after/capture-report.json` | 托盘/主窗口截图流程报告：24 App 名单、点击的 `vchat-app-vstudio`、VStudio target/视口、DOM 快照、主窗口健康检查、console 事件。 |
| `after/interaction-report.json` | 交互采集报告：`videoState`（src/readyState=4/duration=43）、`loadedState`（3 批注/3 pin/3 框/1290 帧）、批注选中态、播放 `t1/t2` 与 `advanced:true`、console（0 error）。 |
| `after/console-and-dom-report.json` | 上述两份报告的合并版。 |
| `after/manifest.json` | 全部 PNG 的尺寸/字节清单。 |
| `after/targets-after.json` | after 采集时 CDP 目标列表（VStudio 窗口 + 主窗口 + 划词助手）。 |
| `before/apps-before.json`、`before/targets-before.json` | before 阶段 DOM/目标快照。 |

复现（after）：

```bash
# 0) 重启后把主窗口恢复为 before 尺寸（inner 2300×843）
tools/resize-main-window.sh

# 1) 托盘入口 → 应用网格（24 App 含「视听」）→ 点击「视听」新开 VStudio 窗口
node tools/capture-after.js --out /tmp/vstudio-evidence/after
#    内部动作：close 旧 VStudio 窗口 → shot after-main → 点「应用」tab → shot after-tray/apps-grid
#    → 找 data-launcher-app="vchat-app-vstudio" 真实鼠标点击 → 等新 CDP target → 整窗 + 各面板裁图
#    → 双窗口 Runtime/Log console 收集 → 校验 #messageInput

# 2) 工程选中 / 播放中 / 批注 pin 高亮
node tools/capture-interactions.js --out /tmp/vstudio-evidence/after
#    内部动作：等工程加载 → 等 video.readyState>=2 → seek 15.05s → 点 #play-btn → 等 1.4s
#    → shot after-vstudio-playing → 点 .ann-card 让 pin 高亮 → shot after-vstudio-annotation(+pin/list)
```

---

## Console / 运行健康检查

- **VStudio 窗口**：`Runtime.enable` + `Log.enable` 从新 target 出现即开始收集，全程 **0 条 error / 0 条 uncaught exception**（仅有 2 条 `[Preload][utility] loaded` info 日志）。视频加载正常（`readyState=4`），无 `net::ERR_FILE_NOT_FOUND`（此前相对路径 bug 已在重启后修复）。
- **主窗口**：console 事件中 **1 条 error（原文）**：
  `Digital clock, notification title, or date display element not found.`
  来源 `modules/uiManager.js:321`，为**本 ticket 未改动的既有代码**（与 VStudio 无关；启动/刷新 UI 时既有告警）。除此之外主窗口无 JS 异常。
- **主窗口可用性**：`#messageInput` 存在、可见，placeholder「输入消息... (Shift+Enter 换行)」，标题 `VCPChat`。

## 结论

1. 改动前应用托盘（「应用」tab 网格）23 个 App，无「视听」；改动后 24 个 App 且点击「视听」可打开独立 VStudio 窗口（标题「V视听 · VCP 视频协同工坊」）。
2. VStudio 真实数据可用：工程列表、16:9 预览、播放成片、帧级批注（pin/框选/列表/状态/AI 回复）、多轨时间线（5 场景 + 6 音轨 + 批注 marker）、交给 AI 面板全部呈现并可交互。
3. 前后主窗口截图同场景/同尺寸（2300×843）/同浅色主题；VStudio 窗口截图为整窗 1440×900。
4. 采集期间无 VStudio 侧 JS 报错；主窗口唯一 console error 为既有 `uiManager.js` 告警（与本功能无关，原文如上）。本证据采集**未修改任何应用源码**。

## 工具用法（cdp.js）

```bash
node tools/cdp.js list                                        # 列 CDP targets
node tools/cdp.js eval <targetMatch> '<js expression>'        # Runtime.evaluate
node tools/cdp.js shot <targetMatch> out.png [--clipsel=<sel>] # Page.captureScreenshot
node tools/cdp.js click <targetMatch> <css-selector>          # 真实鼠标点击
node tools/cdp.js wait <targetMatch> <selector> <timeoutMs>   # 等待选择器
node tools/cdp.js logs <targetMatch> <durationMs> out.jsonl   # 收集 console/异常
```

`targetMatch` 为页面 title/url 子串（如 `main.html`、`VStudioModules`）。
