# V视听（VStudio）— 人类与 AI Agent 协同视频工坊

> 自动交付说明 · 对应原工作 Issue #3
> 交付时间：2026-11-02（21:00 前暂停点） · **本机已实际应用并验证**

## 1. 需求对照

| Issue #3 需求 | 交付内容 |
| --- | --- |
| 借鉴 VCPChat 的 V工程（ProjectForge）与文坊（Scriptorium）协同模式 | 「V视听」窗口沿用同样的「工程 / 变更 / 批注 / 协作」模型：视频工程化、帧级批注、AI 通过工具读写同一工程、窗口订阅变更自动刷新（与文坊的 agent control、V工程的工程化同源） |
| 人给出视频内容，AI agent 用视频制作工具制作视频 | VCPToolBox 新插件 `VStudio`（22 个 agent 工具命令）负责工程/场景/音轨/素材/配音/渲染；**真实接入 MotionGit 模板包**（[motiontemplates/385712](https://github.com/motiontemplates/385712)）产出科技风动态片段；edge-tts 中文旁白；ffmpeg 合成 H.264 成片 |
| 人可预览视频，并在任意帧、画面任意元素、画面布局提修改意见，AI 执行 | 16:9 预览 + 帧级定位 + 「画面内容 / 画面元素 / 画面布局」三类批注（点选打点或拖拽框选区域）+ DAW 多轨时间线 + 批注列表；「交给 AI」把工程 id、帧号、区域、target、批注内容与指令注入主窗口聊天输入框；agent 处理后可回写批注状态与回复并重新渲染 |
| 语音方面借鉴 Logic Pro / Cubase | 多轨音频时间线（旁白 / BGM / SFX 多轨，每轨 start/duration/volume/fadeIn/fadeOut），ffmpeg amix 混音；UI 以 DAW 方式呈现：标尺、轨道行、播放头、音量滑杆、波形 |

## 2. 交付物总览

**VCPChat（前端 + Electron 接线，共 5 新增 + 5 修改）**

| 文件 | 说明 |
| --- | --- |
| `VStudioModules/vstudio.html` / `vstudio.css` / `vstudio.js` / `vstudio-api.js` / `vstudio-timeline.js` | 「V视听」窗口（新增） |
| `preloads/api/vstudio.js` | 15 个 `vstudio*` invoke + 变更订阅（utility/chat 角色） |
| `modules/ipc/vstudioHandlers.js` | IPC 主进程桥：懒 require 后端核心、媒体 URL 补全、写操作广播、选文件、打开目录、「交给 AI」注入 |
| `modules/ipc/desktopHandlers.js`、`modules/services/windowAppIds.js` | 窗口注册 / 动作路由（`open-vstudio-window` → `vstudio`） |
| `modules/trayManager.js`、`modules/ui-system/next-shell/launchpad-icons.js`、`launchpad-icon-art.js` | 应用网格新增「视听」入口 + 彩色胶片图标 |

**VCPToolBox（后端，新增目录 `Plugin/VStudio/`）**

| 文件 | 说明 |
| --- | --- |
| `VStudioCore.js` | 共享核心（纯 Node 零依赖）：工程 CRUD / 场景 / 多轨音轨 / 帧级批注 / 素材导入 / edge-tts 配音 / ffmpeg 渲染管线 / 渲染锁 / 原子写 / 进度写回 |
| `VStudio.js` + `plugin-manifest.json` | VCP 同步 stdio 插件入口 + 22 个 `invocationCommands`（AI agent 可见工具） |
| `README.md` / `config.env.example` / `test/smoke.mjs` / `test/robustness.mjs` | 文档、配置模板、冒烟与健壮性测试 |

数据目录：`/app/VCPChat/AppData/VStudio/projects/<projectId>/{project.json, assets/, renders/final.mp4, renders/poster.jpg}`

## 3. 架构

```
┌────────────────────────── VCPChat (Electron) ──────────────────────────┐
│ VStudioModules/  「V视听」窗口（1440×900 独立子窗口）                   │
│   vstudio.html/css/js / vstudio-api.js / vstudio-timeline.js           │
│        │ window.utilityAPI.vstudio*（15 个 invoke + 变更订阅）          │
│ preloads/api/vstudio.js ── modules/ipc/vstudioHandlers.js              │
│        │ require()（同机直连，无进程间序列化开销）                       │
├────────┼───────────────────────────────────────────────────────────────┤
│        ▼                                                              │
│ /app/VCPToolBox/Plugin/VStudio/VStudioCore.js  ← 共享核心              │
│   VStudio.js（stdio 同步插件入口，AI agent 工具调用）                    │
│   plugin-manifest.json（22 个 invocationCommands）                      │
│        │                                                              │
│        ├── 工程数据  /app/VCPChat/AppData/VStudio/projects/<id>/        │
│        │      project.json / assets/ / renders/final.mp4 + poster.jpg  │
│        └── ffmpeg（H.264/AAC、ASS 中文字幕、Ken Burns、xfade、画中画、   │
│                   amix 多轨混音）+ edge-tts（中文旁白）+ MotionGit 片段 │
└────────────────────────────────────────────────────────────────────────┘
```

数据流（人机协同闭环）：

1. 人在 VStudio 窗口打开/新建工程 → 预览成片 → 暂停到任意帧 → 点选或框选画面元素 → 写批注（画面内容/画面元素/画面布局）。
2. 点「交给 AI」→ 主进程把结构化转交文本（工程名/id、帧号+时间码、区域、target、批注内容、指令）注入主窗口聊天输入框并聚焦（不自动发送，用户回车确认）。
3. AI agent 收到后调用 `VStudio` 工具命令（`get_project` / `update_scene` / `reorder_scenes` / `update_audio_track` / `update_annotation` / `render` …）修改工程并重新渲染。
4. VStudio 窗口通过 `vstudio:changed` 推送 + 轮询自动刷新工程、批注状态与视频预览（渲染中显示进度）。

## 4. 本机应用状态（已生效）

- **后端插件已被运行中的 VCPToolBox 自动热加载**（未重启 vcp-main）：
  ```
  [PluginManager] Manifest state changed (1 path(s)). Hot-reloading plugins...
  [PluginManager] Loaded manifest: V「视听」视频工程 (VStudio, Type: synchronous)
    - Generated description for {{VCPVStudio}} (Length: 8024)
  [PluginManager] Hot-reload complete.
  ```
  `GET /admin_api/plugins` 也确认：`VStudio / V「视听」视频工程 / enabled:true / synchronous / 22 commands`。
- **VCPChat 已重启应用改动**（pm2 `vcpchat-desktop`，重启后 CDP 6s 恢复，无 error 日志）：
  - 右侧「首页 → 应用」网格由 23 个变 **24 个**，新增彩色胶片图标 **「视听」**；
  - 点击打开独立子窗口「V视听 · VCP 视频协同工坊」（1440×900）；
  - 窗口内 `window.utilityAPI.vstudio*` 全部就绪，`vstudioListProjects` 直连真实后端；
  - 主窗口 `chatAPI.vstudio*` 就绪，「交给 AI」注入验证通过。
- **真实 LLM agent 已能调用该工具**（通过运行中的 VCP 服务 `/v1/chat/completions`，注入 `{{VCPVStudio}}`）：模型输出 `TOOL_REQUEST` → VCP 执行 `VStudio list_projects` → 返回「VStudio 调用成功 (记录ID: tcr-… )」与真实工程列表。

## 5. 使用说明

**人：**
1. 右下角应用托盘/侧栏「首页 → 应用」→ 点「视听」。
2. 左侧选工程或「新建工程」；等待/点击「渲染」生成成片，中间 16:9 预览可播放、逐帧（±1 帧）查看。
3. 暂停后点「批注模式」：在画面上单击打点，或拖拽框选一个元素/区域；选择「画面内容 / 画面元素 / 画面布局」，写下修改意见 → 保存。批注会出现在右侧列表、时间线 marker 和画面 pin 上。
4. 选中批注 → 「交给 AI」，主窗口聊天输入框会填入含工程 id/帧号/区域/target/批注/指令的转交文本；按回车发送给 agent。
5. agent 完成后重新渲染：预览自动刷新，批注状态变为「已解决」并可见 agent 回复。

**AI agent（工具方式）：**

插件清单 `capabilities.invocationCommands` 中的 22 个命令（`list_projects`、`get_project`、`create_project`、`update_project`、`save_project`、`add_scene`、`update_scene`、`remove_scene`、`reorder_scenes`、`add_audio_track`、`update_audio_track`、`remove_audio_track`、`import_asset`、`list_assets`、`add_annotation`、`update_annotation`、`remove_annotation`、`tts_voiceover`、`render`、`render_status`、`probe_media`、`get_plugin_info`）。调用示例（与 agent 收到的工具描述一致）：

```
<<<[TOOL_REQUEST]>>>
tool_name:「始」VStudio「末」,
command:「始」add_scene「末」,
projectId:「始」proj_xxx「末」,
scene:「始」{"type":"title","title":"标题","subtitle":"副标题","duration":3}「末」
<<<[END_TOOL_REQUEST]>>>
```

## 6. 验证记录

完整原始输出见 `evidence/verification-log.txt`。关键结论：

**后端（VCPToolBox 插件 / VStudioCore）**
- `node test/smoke.mjs` → 1.91s 通过（4 类场景 + 转场 + 画中画 + 中文 ASS + 2 音轨 + 批注生命周期 + 渲染锁 + 产物断言，320×180 H.264+AAC + poster）。
- `node test/robustness.mjs` → 10/10 通过（非法 ID、目录穿越、缺素材、损坏工程、渲染锁/中断修复、无音频流音轨防御、参数校验等）。
- 8 场景混合压力测试：5.95s 时间线渲染 5158ms 成功，逐场景抽帧 8/8 有效；显式 start 空隙自动黑场补位；时长返回值与 ffmpeg 实测一致。
- 多轨真实旁白混音：3 场景 7.3s（BGM + 2 段真人配音 + fade），volumedetect 无削波、各段均真实出声。
- 并发：两工程 Promise.all 均成功；同工程二次 render 被渲染锁拒绝；进度 1%→31%→60%→64%→100% 实时写回。
- 插件 stdio（agent 执行路径）：`echo '{"command":"list_projects"}' | node VStudio.js` 返回标准 `{status,result:{content,details},messageForAI}`。

**真实 LLM agent 调用工具（端到端）**
- 通过运行中的 VCP 服务 `/v1/chat/completions`（system prompt 注入 `{{VCPVStudio}}`，model=deepseek-flash）发送「请调用 VStudio 工具列出所有视频工程」→ 模型输出合法 `TOOL_REQUEST`，服务执行 `VStudio list_projects` 并返回「VStudio 调用成功（记录ID `tcr-…`）」+ 真实工程列表。响应原文见 `evidence/agent-tool-call-e2e.json`。

**前端 / Electron 真实应用**
- 主窗口 preload：`chatAPI.vstudio*` 全部 function，`composer.insert-text` 可用。
- 应用托盘：24 个应用（含「视听」，film 彩色图标）；VStudio 窗口：标题/URL 正确，`utilityAPI.vstudio*` 全部 function，`apiAdapterReady=true`。
- 「交给 AI」：`{success:true, inserted:true, mode:'command'}`，转交文本含工程名/id、帧号+时间码、区域、target、批注内容、指令与「改完调用 vstudioSaveProject」；注入后输入框已还原。
- 媒体路径修复后：`rendered.videoUrl` 为工程内绝对 `file://`，`<video>` `readyState=4`、无 `MEDIA_ELEMENT_ERROR`，真实画面可播。
- 仓库自带测试 `tests/preload-registry.test.js` + `tests/launchpad-icons.test.js`：14/14 pass（未破坏既有窗口/图标清单）。

## 7. Before / After 视觉证据

真实应用截图（同一 xvfb 屏幕；主窗口恢复为与改动前一致的 2300×843；同一主题/视图状态）。

| 证据 | 文件 | 说明 |
| --- | --- | --- |
| Before · 应用网格 | `evidence/before-apps-grid.png` | 改动前：「首页 → 应用」网格 23 个应用，**无「视听」入口** |
| Before · 主窗口 | `evidence/before-main.png` | 改动前主窗口整窗 |
| After · 应用网格 | `evidence/after-apps-grid.png` | 改动后：24 个应用，新增彩色胶片图标「视听」 |
| After · VStudio 窗口 | `evidence/after-vstudio.png` | 「V视听 · VCP 视频协同工坊」整窗（工程列表/预览/时间线/批注/交给 AI） |
| After · 预览播放中 | `evidence/after-vstudio-playing.png` | 演示工程成片播放中的真实画面 |
| After · 批注 pin + 列表 | `evidence/after-vstudio-annotation.png`、`evidence/after-vstudio-annotation-pin.png`、`evidence/after-vstudio-annotation-list.png` | 帧级批注 pin、列表（含 resolved/进行中/open 状态）与时间线 marker |
| After · 时间线 | `evidence/after-vstudio-timeline.png` | DAW 多轨：场景 clip + 旁白/BGM/SFX 音轨 + 波形 + 播放头 |
| After · 交给 AI | `evidence/after-vstudio-agent.png` | 批注上下文 + 转交指令面板 |
| 演示成片抽帧 | `evidence/demo/final-0*.png` | 成片 6 个代表性画面（含 agent 按批注修订后的标题卡） |
| 批注修订前后 | `evidence/demo/title-v1-before.png` vs `final-01-title.png` | 人提「标题上移、副标题补字」→ agent 执行后的画面差异 |

完整索引与复现步骤见 `evidence/README.md`。

## 8. 演示工程与真实制作链路

- 工程：`proj_mvz5fnozzwxuh`「V视听演示 · AI 协同剪辑」1280×720@30fps，43.0s，5 场景、6 音轨、3 批注
- 成片：`/app/VCPChat/AppData/VStudio/projects/proj_mvz5fnozzwxuh/renders/final.mp4`
  （ffmpeg -i：Duration 00:00:43.00，H.264 High 1280×720 30fps + AAC 48kHz stereo；整片解码无错误；响度 -19.1 LUFS、max -3.3dB）
- 审阅版（批注修订前）：`.../renders/review-v1.mp4`（25.5s 渲染）
- 制作链路：人写中文内容 → AI agent 用 MotionGit 模板真实渲染 40s 1080p60 中文母版（HTML/Canvas 逐帧 + Chrome 截图 + ffmpeg 编码）并切 4 段场景素材 → agent 通过 VStudio 工具组装工程（36 次工具调用）→ 渲染审阅版 → 人逐帧批注 → agent 执行 frame 45 批注（标题上移 6% + 副标题补字）→ resolved + reply → 重新渲染最终成片（43.0s）
- 复现与素材来源：`evidence/demo/media-README.md`、`evidence/demo/MOTIONGIT-NOTES.md`、`evidence/demo/agent-tool-calls.log`、`evidence/demo/project-snapshot.json`

## 9. 已知限制

- 「交给 AI」为「填入聊天输入框 + 聚焦 + toast，用户回车发送」的降级实现（不自动发送，避免与流式会话/禁用状态竞争，且不改既有发送逻辑）；VCPChat 原生发送路径在 P1 后续可改为可配置自动发送。
- `VStudioCore.render()` 为阻塞式 Promise（大工程渲染期间 UI 用 `renderStatus` 轮询进度）；1-2s 首帧解码前用 poster 兜底。
- MotionGit 模板渲染目前是独立步骤（用模板自带 adapter.py/prepare/render 出素材后导入工程），尚未内嵌为 VStudio 的「motion 场景类型」；模板在本机需一处 ffmpeg 7 编码参数兼容修改（记录在 `evidence/demo/MOTIONGIT-NOTES.md`）。
- 演示成片为 1280×720（为保证 21:00 前交付按时渲染）；工程支持 1920×1080，后端实测可出 1080p（约 2 分钟/43s），改工程 width/height 重渲染即可。
- TTS（edge-tts）需要联网；本机 ffmpeg 无 `drawtext`（全部走 libass/ASS 中文字幕）、`ffprobe` 是伪软链（统一用 `ffmpeg -i` 解析）——均已在实现中适配。
- 演示工程中的 frame 830 批注仅作「进行中」状态流转示例，agent 未再做第二次 MotionGit 重渲染。
- 本机两个仓库是上游项目的本地副本，未配置可推送的上游 fork，故代码提交保存在本地 `feat/vstudio` 分支 + 本 PR 的 patch。
- 交付时应用已用最终代码重启并再次验证（VCPChat pm2 restarts=53；应用网格 24 App、VStudio 窗口正常、演示工程 3 条批注/已渲染）；VCPToolBox 无需重启（插件按调用拉起子进程 + 目录热加载）。

## 10. 文件清单 / Patch / 回滚

**本地提交（feature 分支，未推送上游仓库——两个仓库是上游项目的本地副本，未配置可推送的 fork）：**

| 仓库 | 分支 | commit |
| --- | --- | --- |
| `/app/VCPChat` | `feat/vstudio` | `a7898938` feat(vstudio): V视听 人机协同视频工坊（VCPChat 前端窗口 + Electron 接线） |
| `/app/VCPToolBox` | `feat/vstudio` | `fee71876` feat(vstudio): V「视听」视频工程后端插件（共享核心 + VCP 同步插件） |

Patch 见 `patches/`（`git apply` 可复现）。

**回滚（一条命令恢复改动前状态）：**

```bash
git -C /app/VCPChat checkout main -- \
  modules/ipc/desktopHandlers.js modules/services/windowAppIds.js modules/trayManager.js \
  modules/ui-system/next-shell/launchpad-icons.js modules/ui-system/next-shell/launchpad-icon-art.js
rm -rf /app/VCPChat/VStudioModules \
  /app/VCPChat/preloads/api/vstudio.js /app/VCPChat/modules/ipc/vstudioHandlers.js
git -C /app/VCPToolBox checkout main -- Plugin/VStudio   # 若 Plugin/VStudio 已提交
rm -rf /app/VCPToolBox/Plugin/VStudio
pm2 restart vcpchat-desktop   # VCPToolBox 插件目录变更会自动热加载移除
```

数据目录 `/app/VCPChat/AppData/VStudio/` 为运行数据（已被 .gitignore 忽略），回滚功能时可按需保留或删除。
