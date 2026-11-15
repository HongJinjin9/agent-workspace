# 第 07 期《三年之后，你的车还值多少钱》成片自检报告

> 由 `scripts/write_report.py` 依据实测数据生成（2026-11-15T07:27:55+00:00 UTC）；MotionHarness Pro 工程导出。

## 1. 技术规格

| 项目 | 实测 | 目标 | 结论 |
| --- | --- | --- | --- |
| 成片 | `/app/vedio/ep07-mh/out/ep07-mh.mp4` | — | — |
| 时长 | 208.966 s | 208.966 s（设计 3:17，按 TTS 实测） | ✅ |
| 帧数 | 5015 | 5015 | ✅ |
| 分辨率 | 1920x1080 | 1920x1080 | ✅ |
| 帧率 | 24.0 | 24 | ✅ |
| 体积 | 72.46 MB | — | — |
| 视频/音频 | h264 / aac 48000Hz 2ch | H.264 + AAC | ✅ |
| 全片解码 | 无错误 | 无错误 | ✅ |

## 2. 响度与音频

| 指标 | 实测 | 目标 | 结论 |
| --- | --- | --- | --- |
| 整体响度 I | -14.43 LUFS | -14 ±0.5 | ✅ |
| 真峰值 TP | -1.62 dBTP | ≤ -1.0 | ✅ |
| 响度范围 LRA | 2.4 LU | — | — |
| 混音报告 | > → `build_audio.py`（旁白处理 + 分段音乐床 + 音效 + sidechain + 两遍 loudnorm + 自检 + 本报告）。 | — | — |

## 3. 画面与字幕

| 检查项 | 实测 | 结论 |
| --- | --- | --- |
| 2.35:1 遮幅（上下 132px 黑边） | 上下 132px 黑边 | ✅ |
| 画面内容 | 中部画面均值 > 4 | ✅ |
| 字幕带文字存在 | 8/20 帧字幕带 bright>=1200（需 6） | ✅ |
| 字幕落在下黑边内 | 字幕带最低均值 0.0 | ✅ |
| 片尾双声明卡文字密度 | t=203.0s center_bright=19275 (帧存 work/qa/endcard-check.png，供人工目检) | ✅ |

- 片尾双声明（画面）：「本片人物/画面由 AI 生成或含 AI 辅助制作」类声明由工程 `end_card` 保证；片尾静帧见 `delivery/stills/still-10-end-card.jpg`，供人工复核可读性（本机无 OCR，脚本以中心区文字像素密度 + 静帧目检判定）。
- 字幕：`work/srt/all.srt`（或 `src/data/srt.json`）驱动；脚本按下黑边文字像素抽检覆盖。

## 4. 素材使用（H3 / 3D / 声音）

- MotionHarness Pro 3D 程序化场景：本片空间、相机、3D 图表、排版、遮幅、颗粒、字幕与最终合成。
- ComfyUI H3 证据影像：20 条（provenance 见 `assets-manifest.json`）
  - `H01`  
  - `H02`  
  - `H03`  
  - `H04`  
  - `H05`  
  - `H06`  
  - `H07`  
  - `H08`  
  - `H09`  
  - `H10`  
  - `H11`  
  - `H12`  
  - `H13`  
  - `H14`  
  - `H15`  
  - `H16`  
  - `H17`  
  - `H18`  
  - `H19`  
  - `H20`  
- 声音：旁白 + BGM + 音效（6 段/句级时间轴见 `audio/work/timeline_audio.json`）；混音目标 I=-14 LUFS / TP≤-1.0。

## 5. 交付物

- 成片：`out/ep07-mh.mp4`（sha256 `d9f3591d18da1ac114e97491fc7bc8d84c332c8b2dc5fb86d775c1ae0fec1ff8`）
- 静帧：`delivery/stills/` 7 张（still-01-cover, still-02-appraisal-sheet, still-04-data-wall, still-06-three-ledgers, still-08-price-tag-forest, still-09-lists, still-10-end-card）
- 联系表：`delivery/contact-sheet.jpg`
- 封面：cover-16x9.jpg, cover-1x1.jpg, cover-3x4.jpg
- 工程：`/app/vedio/ep07-mh`（MotionHarness Pro）；仓库同步目录 `视频制作/ep07-motionharness/`（仅源码，素材不入库）
- 导出：`mh render out/ep07-mh.raw.mp4 --json {"quality":"master","fps":24}`（quality=master, fps=24, 耗时 87 s）
- 校验抽帧联系表：`work/qa/verify-contact-sheet.jpg`

## 6. 结论

**全部硬指标通过，可交付。**

