# 第 06 期 · MotionHarness（帧驭）重制版 SPEC

目标：用 **MotionHarness（帧驭）CLI** 把第 06 期《他们说，这是最糟糕的方案》重做成一个**可编辑的动画工程**，并导出新的成片（v2）。
基准素材沿用已有第 06 期成果：三声部配音 + 原创配乐 + 6 个音效的成品混音（230.2056s）、14 条 ComfyUI H3 镜头、14 张 AI 静帧、稿件 §4 逐字文本与事实数据。
风格：**「卷宗体」影像论文**（dossier / evidence film）——冷灰底 + 暖金 + 墨红印章，纸页、案卷标签、打字机引述、证据标注、数据图版、2.35:1 遮幅、胶片颗粒；人物镜头作为“案卷影像”慢推/裁切/冻结，配合强节奏的版面与字体运动。

## 0. 运行环境（已就绪，勿改）

- MotionHarness CLI：`mh`（npm `@motionharness/cli@0.1.5`，Node v24.21.0）
- 必须显式设置：`MH_BROWSER_PATH=/home/admin/.cache/mh-chrome/chrome-nosandbox`（Chrome 155 + `--no-sandbox` 包装脚本）、`MH_FFPROBE=/home/admin/.local/bin/ffprobe-real`；`PATH` 含 `/home/admin/.nvm/versions/node/v24.21.0/bin:/home/admin/.local/bin`
- 本机 4 CPU / 6GB cgroup：一次只允许跑一个 mh render；preview 可以小并发。
- **资源纪律**：只在制作/检查视频时启动 mh；同一时刻禁止两个 render；离开前 `mh daemon stop`；不要把 Studio 页面当常驻服务。
- 所有显示字号按 1920×1080 逻辑像素写；字体用系统 `Noto Serif CJK SC` / `Noto Sans CJK SC` / `DejaVu Sans Mono`。

## 1. 工程结构（当前已生成）

```
/app/vedio/ep06-mh/
  mh.json                  # 1920x1080 / 24fps / duration 230.2056 / audio assets/audio.wav
  assets/audio.wav         # 第06期成品混音（三声部+配乐+音效，230.2056s）
  assets/footage/c1..c14.mp4   # H3 镜头（1920x1080/24fps/5.18s，无项目音轨依赖）
  assets/stills/c1..c14.jpg    # 静帧 1920x1080
  assets/stills/f1,f2,f3,f6,f7,f10,f11,f12,f13,f14.jpg  # 关键帧冻结帧
  src/data/timeline_audio.json # 原始时间轴（6 段 / 58 句，含 speaker 与起止）
  src/data/shots.json          # 46 个镜头（data-driven，已生成，Lead 所有）
  src/data/overlays.json       # 9 个时间轴叠加事件（stamp / tally / label）
  src/data/srt.json            # 72 条字幕
  src/data/facts.js            # 事实/数字/引述常量（唯一数据源）
  src/theme.js                 # 色板/字体/遮幅/字号（唯一视觉常量）
  src/scene.js                 # 入口（mh-motion 所有）
  src/core/*                   # 引擎、相机、资源、工具（mh-motion 所有）
  src/modules/*                # footage / still / chrome / subtitles（mh-motion 所有）
  src/graphics/*               # 10 个图形场景 + overlays + primitives（mh-graphics 所有）
  src/style.css                # 全局骨架样式（mh-motion 所有）
  src/graphics/graphics.css    # 图形场景样式（mh-graphics 所有）
  SPEC.md / README.md
```

## 2. 数据契约（勿改结构，只读）

`shots.json` 每项：

```js
{
  id: "a1_quote", kind: "graphic" | "footage" | "still",
  asset: "c1" | "c12" | sceneName,          // footage/still 用 cN；graphic 用场景名
  seg: "COLD"|"ACT1"|"ACT2"|"ACT3"|"ACT4"|"CLOSE",
  start, end, dur,                          // 秒（全局时间；首尾相接无空隙）
  // footage: in(素材起点秒) rate(播放倍率) look("cool"|"warm") camera{from,to}
  // still: look camera{from,to} caption
  // graphic: 场景参数（text/speaker/stage/value/lines/years/decls/sources/cta/...）
}
```

`camera`：`{from:{s,x,y}, to:{s,x,y}}`（s 缩放，x/y 像素偏移，从镜头首帧缓动到末帧）。

`overlays.json` 每项：`{type:"stamp"|"tally"|"label", at, dur, ...}`（type 专属字段：stamp 有 text/x/y/rot；tally 有 stage/counts/note；label 有 text/x/y）。

`facts.js` 导出 `FACTS`、`DECLARATIONS`、`HUMAN_LINE`；图形场景的数字/引述**必须**从这里取，不得硬编码。

## 3. 模块接口（所有模块必须遵守）

时间：`t` = 镜头内局部秒；`dur` = 镜头时长；`prepareFrame(globalT)` 里由引擎调用，返回值可以是 Promise。

**基础层模块（mh-motion）**

```js
// src/modules/footage.js
export function mountFootage({ el, shot, assetUrl, theme, assets }) {
  // 创建/复用一个 <video>（muted/preload=auto），按 target = shot.in + t*shot.rate 定位
  return { async update(t, dur) {...}, dispose() {...} };
}
// src/modules/still.js  export function mountStill({ el, shot, assetUrl, theme }) -> {update, dispose}
```

**图形场景模块（mh-graphics）**

```js
// src/graphics/<scene>.js
export function mount(ctx) {   // ctx:{el,width,height,shot,theme,facts,helpers}
  return { update(t, dur) {...}, dispose() {...} };
}
```

需要实现的场景名：`cover, act_title, quote_feng, quote_li, bar_compare, data_curve, evidence_card, statement, year_montage, end_card`（对应 `src/graphics/` 同名文件，由 dispatcher `src/graphics/index.js` 注册）。
叠加层：`src/graphics/overlays.js` 导出 `mountOverlay(ctx)`（stamp/tally/label）。
公共图元：`src/graphics/prims.js`（纸纹、印章、墨迹、细线、打字机、计数、证据角标、目录标签）。

**全局层（mh-motion）**：`src/modules/chrome.js`（2.35:1 遮幅、暗角、胶片颗粒、镜头 caption/证据角标、光晕）、`src/modules/subtitles.js`（srt.json → 底部字幕，48px 白字 60% 黑影，淡入淡出，时间单调）。

## 4. 引擎职责（mh-motion）

- `src/scene.js`：`export default function ({root,width,height})` → 建立层级 `#stage(基础镜) → #overlays → #chrome → #subtitles`，读入三份 JSON，返回 `{prepareFrame, dispose}`。
- `prepareFrame(globalT)`：二分查到当前镜头；镜头切换时挂载/销毁（硬切；可选 0.2s 淡入）；按 `kind` 派发；调用 `update(t,dur)`；await 所有异步（视频 seek）；随后更新 overlays/chrome/subtitles；返回 Promise。
- 相机：`src/core/camera.js` 提供 `cameraTransform(cam, p, theme)`，缓动 easeInOutCubic；应用到 footage/still 的 stage wrapper。
- 资源：`src/core/assets.js` 提供 `footageUrl(name)`、`stillUrl(name)`（`new URL('../../assets/footage/'+name+'.mp4', import.meta.url).href`）。
- 性能：视频元素按 asset 池化（14 个，惰性创建）；只在激活时 seek；预加载下一个 footage 镜头（结束前 1.5s）；不要每帧重建 DOM；颗粒用 CSS 动画 + `animation-delay:-time` 暂停实现确定性。

## 5. 视觉与节奏要求（评分点）

1. **一屏一个第一视觉重点**；版面留白、字距与行距要克制；引述卡/数字/印章不要同屏抢。
2. **转场**：以硬切为主；允许 0.2–0.4s 淡入淡出；不要闪白、无意义 whoosh；印章落下要有“砸下 + 墨迹扩散”的重音。
3. **镜头运动**：footage/still 都带慢推/平移/裁切；相邻镜头运动方向不重复（推/拉/左移/右移交替）。
4. **证据语言**：纸页底纹、案卷标签（第一幕…）、年份章（2020/2021/2025/2026）、证据角标（四角短线+编号）、红线/下划线划重点、印章（判决/改判/再判/平）。
5. **数据准确**：13,438 / 12,445 / +993 / 123 万 / 41 万 / -9.7% / -24.9% / 10.3%→7.0% 全部来自 facts.js；柱高严格 ∝ 数值；曲线数值驱动。
6. **双声明**：片尾卡必须有「本片人物为 AI 生成的虚构形象，不代表任何真实人物」+「本片画面与配音含 AI 辅助制作」+「选题、核实与判断，由人完成」+ 参考资料；字幕覆盖全片。
7. **可编辑**：所有文案/数字在 data/theme 里；图形场景参数化；README 写清怎么改。
8. 静态检查须过：`mh preview --times` 关键帧检查 + `mh render` 3–5s 片段检查 + 最终全片导出校验（时长/帧数/分辨率/音频/字幕覆盖）。

## 6. 交付

- 工程源码（不含大素材）提交到仓库 `视频制作/ep06-motionharness/`；大素材通过 Release 打包（`mh pack` 或 assets zip）。
- 成片 v2：`ep06-mh-v2.mp4`（1920×1080/24fps/230.2056s，含混音，H.264 + AAC，master 质量）。
- 关键帧联系表 + README（工程说明/编辑指南/复现命令/素材清单/合规声明）。
- PR + Release；不启用 auto-merge，由人合并。

## 7. 分工与文件所有权

- **mh-motion**：`src/scene.js`、`src/core/*`、`src/modules/*`、`src/style.css`（可改）、mh CLI 运行与渲染、性能与导出、集成。
- **mh-graphics**：`src/graphics/*`（10 场景 + overlays + prims + `src/graphics/graphics.css`，由 `src/graphics/index.js` 里 `import './graphics.css'` 引入；不要改 `src/style.css`）。
- **Lead**：`mh.json`、`src/data/*`、`src/theme.js`、`SPEC.md`、资产、最终验收/PR/Release。
- 禁止改别人文件；接口变化必须先发消息。

## 8. mh 命令模板（所有命令加 flock 串行化）

```bash
export PATH=/home/admin/.nvm/versions/node/v24.21.0/bin:/home/admin/.local/bin:$PATH
export MH_BROWSER_PATH=/home/admin/.cache/mh-chrome/chrome-nosandbox
export MH_FFPROBE=/home/admin/.local/bin/ffprobe-real
cd /app/vedio/ep06-mh
flock /tmp/mh-ep06.lock -c "mh preview --time 12.5 --output .tmp/prev/f1.png"
flock /tmp/mh-ep06.lock -c "mh preview --times '[0,2.8,10]' --contact-sheet --output-dir .tmp/prev/set1"
flock /tmp/mh-ep06.lock -c "mh render .tmp/clip.mp4 --json '{\"start\":40,\"duration\":5,\"quality\":\"high\"}'"
```

预览/片段输出放 `.tmp/`（不提交）；最终成片渲染到 `out/`。
