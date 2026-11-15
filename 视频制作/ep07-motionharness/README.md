# 第 07 期 · MotionHarness **Pro** 可编辑 3D 工程

《三年之后，你的车还值多少钱》—— 一份刚发布的保值率报告，如何给电动车重新定价。

本目录保存**可复现的工程源码与数据**：MotionHarness Pro（`@motionharness/sdk` + `@motionharness/sdk/three` / ThreeCanvas）搭一间"会自己重估价值"的 3D 评估室，H3 生成的证据影像以 DOM 层嵌在系统里，最终由 MH 一次合成导出 **1920×1080 / 24fps / 208.9664s** 成片。

> 场景与镜头设计依据：仓库 [`视频制作/ep07-scene-design/SCENE-DESIGN.md`](../ep07-scene-design/SCENE-DESIGN.md) + 发言稿 `自媒体稿/第07期-三年之后你的车还值多少钱.md`（v0.2 快节奏版）。
> 本仓库只存源码与数据；**H3 视频、音频母带、成片等大素材不入库**（provenance 见 `assets-manifest.json`）。

## 工程结构

| 路径 | 内容 |
| --- | --- |
| `mh.json` | MotionHarness 工程设置（Pro；entry `src/project.tsx`） |
| `src/project.tsx` | 合成入口：`defineComposition`（1920×1080 / 24fps / **duration 208.9664s**）+ 可编辑参数（背景色 / H3 不透明度 / 颗粒强度 / 字幕开关） |
| `src/Stage.tsx` | 图层栈：`ThreeCanvas` 3D 世界 → H3 证据影像层 → 图形/排版层 → chrome（遮幅/颗粒/暗角/幕标签）→ 字幕 |
| `src/three/` | 3D 空间与相机：`World.tsx`（评估室 A–E 五区、程序化资产）、`camera-rig.ts`（关键帧路径）、`materials.ts`（纸/车漆/金属/玻璃）、`text-texture.ts`（CanvasTexture 中文排版）、`math.ts` / `pose.ts` |
| `src/layers/` | `FootageLayer.tsx`（H3 bg/pip 证据窗，局部时间 seek）、`Subtitles.tsx`（单条活动 cue、0.12s 淡入淡出、绝不重叠）、`Chrome.tsx`（**132px 2.35:1 遮幅** + 暗角 + 确定性胶片颗粒 + 幕标签） |
| `src/graphics/` | 图形场景：`title_hook` / `report_cover` / `paper_sheet` / `stamp` / `big_number` / `number_stack` / `section_label` / `end_card` / `prims` + `index.tsx` 调度器 + `graphics.css` |
| `src/data/shots.json` | **50 个分镜**（start/end/seg/space/cam/motion/H3 编号/headline），由逐句实测时间轴驱动 |
| `src/data/timeline.json` / `srt.json` | 发言稿 v0.2 设计时间轴（197.18s 参考）与 **98 条字幕**（以 TTS 实测 208.9664s 为准） |
| `src/data/facts.ts` | 事实与数字唯一数据源（45.1% / 42.2% / 50.6% / 20→9 万 / 3.7 万/年 等）+ 片尾声明文案 |
| `src/data/theme.ts` / `types.ts` | 色板（冷灰/纸白/琥珀/批注红）、字号、遮幅与类型定义 |
| `scripts/verify_ep07.py` | 成片硬校验（规格/帧数/解码/响度/遮幅/字幕带/片尾双声明卡/黑场）+ 抽帧联系表 → `work/final-check.json` |
| `scripts/prepare_delivery.py` | 10 张静帧 + 联系表 + 16:9 / 1:1 / 3:4 封面 + `delivery/delivery-manifest.json` |
| `scripts/write_report.py` | 生成 `work/final-report.md` + `assets-manifest.json` |
| `scripts/mh-render.sh` | 单实例最终导出（`flock /tmp/mh-ep07.lock`）：`out/ep07-mh.raw.mp4`（含 MH 内嵌音频，仅同步预览/兜底） |
| `scripts/finalize_audio.sh` | **交付主路径**：MH 导出视频流 copy + 音频母带 remux → `out/ep07-mh.mp4` |
| `scripts/sync_repo.sh` | 源码同步进 ticket 仓库 worktree（素材不入库） |

## 重建素材（大素材不入库）

```bash
# H3 证据影像：由 comfyui-operator 生成后放入（1080p / 24fps / 约 5s，命名 H01–H14）
#   /app/vedio/ep07-mh/assets/h3/H01.mp4 … H14.mp4（provenance: assets/h3/manifest.json）
# 音频母带：由 audio-narration 输出
#   /app/vedio/ep07-mh/audio/work/audio.m4a（I≈-14.31 LUFS / TP≤-1.0；逐句时间轴 audio/work/timeline_audio.json）
# 3D 资产全部程序化（Three.js 几何 + CanvasTexture），无外部模型/贴图依赖。
```

## 预览 / 导出

```bash
export PATH=/home/admin/.nvm/versions/node/v24.21.0/bin:/home/admin/.local/bin:$PATH
export MH_BROWSER_PATH=/home/admin/.cache/mh-chrome/chrome-nosandbox   # 无沙箱 Chrome 包装脚本
export MH_FFPROBE=/home/admin/.local/bin/ffprobe-real

cd /app/vedio/ep07-mh
mh preview --time 12.5 --output .tmp/review/f125.png            # 单帧预览
mh preview --times '[0,12.5,40,80,120,160,200]' --contact-sheet --output-dir .tmp/review/set1

# 最终导出（单实例，避免与其他 render 并发；4CPU/6GB）
bash scripts/mh-render.sh                                        # -> out/ep07-mh.raw.mp4
bash scripts/finalize_audio.sh                                   # -> out/ep07-mh.mp4（视频 copy + 母带音频）
python3 scripts/verify_ep07.py                                   # 硬校验 -> work/final-check.json
python3 scripts/prepare_delivery.py --from-shots                 # 10 静帧 + 联系表 + 三版封面
python3 scripts/write_report.py                                  # final-report.md + assets-manifest.json
```

## 数据与合规

- 全部数字来自 `src/data/facts.ts`（单一数据源）：中国汽车流通协会《2026 年 10 月中国汽车保值率报告》（2026-11-10）及公开报道；片中不点评具体车型好坏。
- 片尾卡 `end_card` 含声明：数据来自公开报告与公开报道 / 本片为知识与观点内容，不构成购买建议 / **本片画面与配音含 AI 辅助制作**；旁白片尾口播同声明。
- 两位角色与所有实拍质感影像由 AI 生成（虚构），不指向任何真实人物；画面无品牌 Logo/车标特写。
- H3 素材商用授权以 MiniMax 许可为准，发布前确认。

## 已知限制与备选

- **片尾双声明卡可读性**：本机无 OCR，`verify_ep07.py` 以中心区文字像素密度 + 保存静帧（`work/qa/endcard-check.png`）供人工目检；交付前人工复核一次。
- **MH Pro 导出稳定性**：若全片导出失败/掉帧，降级为分段导出（`mh render` 按 `--json '{"start":..,"duration":..}'` 出片段）→ ffmpeg 无缝拼接 → 再用母带 remux；3D 若不可用则降级 2.5D（关键帧序列帧合成）。实际采用方案会写入 `work/final-report.md`。
- 本工程不使用外部 3D 模型/物理/指针交互；近景质感由 H3 证据影像承担。
