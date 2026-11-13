# 第 06 期 · MotionHarness（帧驭）可编辑动画工程（v2）

《他们说，这是最糟糕的方案》重制版：用 **MotionHarness** 制作的**可编辑动画工程**（数据驱动分镜 + 图形场景 + 2.35:1 遮幅），导出 1920×1080 / 24fps / 3:50.22 成片。

> 设计说明与模块契约见 [`SPEC.md`](./SPEC.md)。本目录只保存可复现的工程源码与数据；**H3 镜头、静帧、混音等大素材不入库**。

## 工程结构

| 路径 | 内容 |
| --- | --- |
| `mh.json` / `document.json` | MotionHarness 工程设置（1920×1080 / 24fps / 230.2056s / 混音轨） |
| `src/scene.js` | 工程入口：时间驱动引擎（46 镜切换、相机、叠加层、遮幅、颗粒、字幕） |
| `src/core/` | 引擎工具、相机缓动、素材 URL 解析 |
| `src/modules/` | footage / still / chrome / subtitles 基础层 |
| `src/graphics/` | 10 个图形场景 + 时间轴叠加层 + 公共图元（卷宗体视觉系统） |
| `src/data/shots.json` | 46 个镜头的分镜数据（时间、素材、相机、图形参数） |
| `src/data/srt.json` | 72 条字幕 |
| `src/data/overlays.json` | 印章/胜负标记/标注等时间轴叠加事件 |
| `src/data/facts.js` | 事实、数字与引述（画面数字唯一数据源） |
| `src/theme.js` | 色板 / 字体 / 遮幅 / 字号 |
| `src/style.css` / `src/graphics/graphics.css` | 全局与图形样式 |

## 重建素材（大素材不入库）

```bash
# 依赖已有的第 06 期工程（H3 镜头、静帧、成品混音；源目录默认 /app/vedio/ep06-dialogue，可用 SRC= 覆盖）
bash scripts/prepare-assets.sh
# 或从 Release 的 ep06-motionharness-project.zip 直接解压（含 assets/）
```

## 预览 / 导出

```bash
export PATH=/home/admin/.nvm/versions/node/v24.21.0/bin:/home/admin/.local/bin:$PATH
export MH_BROWSER_PATH=/home/admin/.cache/mh-chrome/chrome-nosandbox   # 无沙箱包装脚本
export MH_FFPROBE=/home/admin/.local/bin/ffprobe-real

cd "视频制作/ep06-motionharness"   # 或在 /app/vedio/ep06-mh 的副本上工作
mh preview --time 22.5 --output .tmp/review/f225.png
mh preview --times '[0,22.5,61,137,214.5]' --contact-sheet --output-dir .tmp/review/set1
mh render out/ep06-mh-v2.mp4 --json '{"quality":"master","fps":24}'
```

## 怎么改

- 改文案/数字：`src/data/facts.js`（事实）、`src/data/shots.json`（镜头参数、引述卡/数据卡内容）、`src/data/overlays.json`（印章与标记）。
- 改分镜时间/素材/相机：`src/data/shots.json`（`start/end/dur`、`asset`、`camera.from/to`、`in`、`rate`、`look`）。
- 改视觉：`src/theme.js`（色板/字号/遮幅）；图形场景在 `src/graphics/`。
- 改字幕：`src/data/srt.json`（或重新从 SRT 生成）。
- 时间基准来自 `src/data/timeline_audio.json`（58 句三声部配音 + 幕结构），改配音后需同步 `shots.json`/`srt.json`。

## 合规

- 两位角色为 **AI 生成的虚构形象**，不代表任何真实人物；片尾卡与旁白均有「虚构形象 + AI 辅助制作」双声明。
- 公开引述（冯思翰 2020-09-08 / 李想 2021-12-22）与数据（上险量、乘联会口径）在片尾卡标注来源。

## 成片（v2，Release 资产）

- `ep06-mh-v2.mp4`：1920×1080 / 24fps / 2.35:1 遮幅（上下各 132px）/ **230.217s（5525 帧）** / H.264 High + AAC 192k 48kHz / 397.9 MB；全片解码无错误
- `ep06-mh-v2-web.mp4`：发布用 H.264 CRF20 压缩版（同片）
- 响度：**I = −14.31 LUFS / TP = −1.68 dBTP / LRA = 7.50**（与第 06 期母带一致；工程 `assets/audio.wav` 即该母带的 48kHz/24bit 副本）
- 关键帧/封面/联系表：Release 资产（contact-sheet.jpg、cover-16x9/1x1/3x4.jpg、10 张关键静帧）
- 片尾卡：虚构 AI 人物声明 + AI 辅助制作声明 + 「选题、核实与判断，由人完成」+ 参考资料；旁白同期口播声明

## 验证

- 引擎：46 镜全量 mid-time 预览与关键时间点联系表；同一时间重复渲染字节级一致；回退 seek 校验通过
- 成片：全片解码 0 错误；1920×1080 / 24fps / 5525 帧 / 230.217s；H.264+AAC；2.35:1 遮幅像素校验（上下黑边均值 <1）；字幕逐条覆盖且不与画面元素重叠；片尾双声明可读；`bar_compare` 数值 13,438 : 12,445 / +993 与 `data_curve` 数值逐一核对
- 数据准确性：所有数字来自 `src/data/facts.js`，与发言稿 §5 一致

## 已知限制

- 本片为动效/图形叙事（MotionHarness 擅长方式），不是真人表演或 3D 角色动画；人物镜头为首期 H3 素材的再剪辑（侧影/背影/过肩/手部为主，正脸不清晰）
- 素材固定为 14 条 5.2s H3 片段 + 14 张静帧，部分镜头通过裁切/冻结/慢放复用
- 字幕为本工程内置绘制，发布前建议在目标平台预览一次
- 成片为横屏 2.35:1 主版；9:16 竖屏版未出
