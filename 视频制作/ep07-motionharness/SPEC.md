# 第 07 期 MotionHarness Pro 工程 · 技术契约（SPEC）

> 场景与镜头设计唯一依据：仓库 [`视频制作/ep07-scene-design/SCENE-DESIGN.md`](../ep07-scene-design/SCENE-DESIGN.md)。
> 本文件只补充**工程/验收契约**，不重复场景设计内容。

## 1. 目标与规格

| 项目 | 契约 |
| --- | --- |
| 成片 | `out/ep07-mh.mp4`，1920×1080 / 24fps / **208.9664s**（逐句 TTS 实测；设计稿 3:17 仅作节奏参考） |
| 画幅 | 16:9 全幅 + **上下 132px 2.35:1 纯黑遮幅**（`Chrome.tsx`，`THEME.letterbox=132`） |
| 影调 | 冷灰 `#0e1216` / 纸白 `#e9e4d8` / 琥珀 `#d9a441` / 批注红 `#b3392e`；全片统一颗粒 + 暗角（DOM 层，不污染 3D） |
| 声音 | 旁白 + 原创 BGM + ≤6 处音效；母带 I=-14.31±0.5 LUFS / TP≤-1.0 dBTP；片尾声明口播 198.52–208.17s |
| 字幕 | 98 条（`srt.json` 实测时间轴），单条活动、0.12s 淡入淡出、零重叠；落在下黑边内 |
| 交付 | 成片 + 10 静帧 + 联系表 + 16:9/1:1/3:4 封面 + `work/final-report.md` + `assets-manifest.json` |

## 2. 图层栈契约（`src/Stage.tsx`，自下而上）

1. `ThreeCanvas` 3D 世界（`src/three/World.tsx`）：评估室 A–E 五区、程序化几何与材质、相机路径 `camera-rig.ts` 由 `shots.json` 驱动；确定性（同一时间同一画面）。
2. `FootageLayer`（H3 证据影像）：`bg` 全幅压底（opacity 0.55）/ `pip` 画中画（720×405，红角标 EVIDENCE）；**不进 3D 贴图**；按镜头局部时间 seek，素材缺失时静默隐藏（不黑屏）。
3. 图形/排版层（`src/graphics/`）：标题钩子、报告封面、评估单纸面、印章、大数字、数字堆、章节标签、片尾声明卡；所有数字/文案来自 `facts.ts` / `shots.json.headline`。
4. `Chrome`：遮幅 / 暗角 / 确定性颗粒（SVG turbulence）/ 幕标签。
5. `Subtitles`：`srt.json` 单条活动 cue。

## 3. 数据契约

- `shots.json`：50 条，字段 `id, n, start, end, dur, seg, space, cam, motion, h3, h3mode, headline, sub`；`start/end` 与 TTS 实测时间轴一致（总长 208.966），`h3` ∈ {H01…H14, null}。
- `timeline.json`：发言稿 v0.2 设计时间轴（197.18s，参考）；**不参与最终时长**。
- `srt.json`：98 条字幕（start/end/text），与音频母带逐句对齐。
- `facts.ts`：所有数字/引述/声明的唯一数据源；任何画面数字改动必须改这里。
- `graphics_cues.json`：图形场景时间轴事件（`graphics/index.tsx` 调度）。

## 4. 导出与验收（交付 owner 执行）

```bash
bash scripts/mh-render.sh        # out/ep07-mh.raw.mp4（MH 内嵌音频，仅同步预览/兜底）
bash scripts/finalize_audio.sh   # out/ep07-mh.mp4 = 视频流 copy + 音频母带 remux（交付主路径）
python3 scripts/verify_ep07.py   # 硬校验；全 PASS 才交付
python3 scripts/prepare_delivery.py --from-shots
python3 scripts/write_report.py
```

硬校验（`verify_ep07.py`）：分辨率/帧率/时长（±0.5s）/帧数（±2）/解码 0 错/响度 I∈[-14.81,-13.81] LUFS、TP≤-1.0/上下 132px 黑边/字幕带文字像素/片尾双声明卡文字密度/尾部黑场 + 16 帧抽帧联系表。

## 5. 风险与降级

| 风险 | 降级 |
| --- | --- |
| MH Pro 全片导出失败/掉帧 | 分段导出片段（`--json '{"start":s,"duration":d}'`）→ ffmpeg 拼接 → 母带 remux；如实写入 final-report |
| 3D/WebGL 不稳定 | 2.5D：关键帧 `mh render out/frame.png` 序列 + 2D 合成，保持时间轴/字幕/遮幅不变 |
| H3 素材缺失/迟到 | `FootageLayer` 自动隐藏该镜证据窗，3D 与图形层照常；final-report 记录实际使用清单 |
| 音频母带迟到 | 先用 MH 内嵌音频交付预览版（`finalize_audio.sh` fallback 分支），母带到后重跑 remux + verify |
