# 第 07 期 · MotionHarness **Pro** 可编辑工程（v2 · 动效/数据主导版）

《三年之后，你的车还值多少钱》—— 一份刚发布的保值率报告，如何给电动车重新定价。

本目录保存**可复现的工程源码与数据**：MotionHarness Pro（`@motionharness/sdk` + `@motionharness/sdk/three` / ThreeCanvas）以**动态图形与数据动画为主视觉**，3D 评估室作为暗场空间背景，ComfyUI H3 证据影像仅作**强关联插入**；导出 **1920×1080 / 24fps / 208.9664s** 成片。

> 场景与镜头设计依据：仓库 [`视频制作/ep07-scene-design/SCENE-DESIGN.md`](../ep07-scene-design/SCENE-DESIGN.md) + 发言稿 `自媒体稿/第07期-三年之后你的车还值多少钱.md`（v0.2）。
> 本仓库只存源码与数据；**H3 视频、音频母带、成片等大素材不入库**（provenance 见 `assets-manifest.json`）。

## v2 构图（动效/数据主导）

| 图层/镜头 | 内容 |
| --- | --- |
| **分镜节奏** | **67 镜 / 平均 3.1s**（v1：50 镜 / ~4.2s）：`data` 38 镜（图形/数据动画主视觉）+ `h3` 27 镜（H3 强关联证据插入）+ `split` 1（H3+图形分屏）+ `end` 1（片尾声明卡） |
| **图形/数据层** | 40 条 `graphics_cues.json` 事件驱动 17 类块：title_hook / report_cover / big_number / number_stack / category_bars / compare_bars / ledger_books / tech_params / price_tag / brand_matrix / ranking_board / paper_sheet / red_annotation / statement / section_label / split_screen / end_card（`graphics/index.tsx` 调度） |
| **H3 证据影像** | 27 镜引用 **17 条 clips**（H01–H03,H05–H14,H16,H17,H19,H20），带运镜处理（push_in/push_out/pan_l/pan_r/punch_in/mirror/panel/fill）；只在"证据"落点插入，不与数据动画抢第一视觉 |
| **3D 空间** | 评估室 A–E 五区程序化背景（暗场），提供空间/相机/景别与氛围；图形镜头下 3D 压暗，排版成为第一视觉 |
| **chrome** | 132px 上下 2.35:1 遮幅 + 暗角 + 确定性胶片颗粒 + 幕标签 |
| **字幕** | `srt.json` **98 条**，单条活动、0.12s 淡入淡出、零重叠，落在下黑边内（46px 纸白） |

## 工程结构

| 路径 | 内容 |
| --- | --- |
| `mh.json` / `document.json` | MotionHarness 工程设置（Pro；1920×1080 / 24fps / **208.9664s**） |
| `src/project.tsx` | 合成入口 `defineComposition` + 可编辑参数（背景色/H3 不透明度/颗粒强度/字幕开关） |
| `src/Stage.tsx` | 图层栈：ThreeCanvas 3D 暗场背景 → H3 证据影像（h3/split 镜头）→ scrim → 图形层（data/split/end）或动态 lower-third（h3）→ chrome → 字幕 |
| `src/three/` | 3D 空间与相机：`World.tsx`（评估室 A–E 五区）、`camera-rig.ts`、`materials.ts`、`text-texture.ts`、`math.ts` / `pose.ts` |
| `src/layers/` | `FootageLayer.tsx`（H3 证据窗口 + 运镜处理，24fps 帧格量化 seek + 超时兜底）、`LowerThird.tsx`（H3 镜头动态下三分之一）、`Chrome.tsx`（遮幅/暗角/颗粒/幕标签）、`Subtitles.tsx` |
| `src/graphics/` | 图形块与调度器：`index.tsx` + 17 类块（title_hook/report_cover/big_number/number_stack/category_bars/brand_matrix/price_tag/ranking_board/red_annotation/stamp/paper_sheet/statement/section_label/end_card + prims） |
| `src/data/shots.json` | **67 个分镜**（`kind/block/clip/treat/space/cam/spaceMotion/headline/sub`），覆盖 1.0–208.966s |
| `src/data/graphics_cues.json` | **40 条图形事件**（cue → block + 时段 + props） |
| `src/data/srt.json` | **98 条字幕**（TTS 实测时间轴） |
| `src/data/h3_manifest.json` | H3 clip → 用途映射（20 条素材；v2 实际引用 17 条） |
| `src/data/facts.ts` | 事实/数字/声明唯一数据源（45.1% / 42.2% / 50.6% / 20→9 万 / 3.7 万/年 等 + 3 条片尾声明 + 来源） |
| `src/data/theme.ts` / `types.ts` | 色板、字号、遮幅、六幕实测边界与分镜类型定义 |
| `scripts/verify_ep07.py` | 成片硬校验（规格/帧数/解码/响度/遮幅/字幕带/SRT 结构/H3 clips/片尾双声明卡/尾部收束）+ 抽帧联系表 |
| `scripts/probe_h3_assets.py` | H3 素材探针 |
| `scripts/mh-render.sh` | 单实例导出（flock）→ `out/ep07-mh.raw.mp4` |
| `scripts/finalize_audio.sh` | **交付主路径**：视频流 copy + 音频母带 remux → `out/ep07-mh.mp4` |
| `scripts/prepare_delivery.py` | 10 静帧 + 联系表 + 16:9/1:1/3:4 封面 |
| `scripts/write_report.py` | `work/final-report.md` + `assets-manifest.json` |
| `scripts/sync_repo.sh` | 源码同步进 ticket 仓库 worktree（素材不入库） |

## 渲染/交付（与 v1 同工艺）

- MotionHarness Pro 1080p 直出在本机 4CPU 于 ~85–90s 段出现确定性 capture deadline 超时 → **720p master 8 段（flock 单实例，`MH_EXPORT_WORKERS=2`）→ ffmpeg concat → lanczos 1920×1080 + unsharp 0.35** → 母带 remux。
- 硬校验：`python3 scripts/verify_ep07.py`（22 项，全部 PASS 才交付）。
- 交付：`out/ep07-mh.mp4` + 10 静帧/联系表/三封面 + `work/final-report.md` + `assets-manifest.json`。

## 数据与合规

- 数字来自 `src/data/facts.ts`：中国汽车流通协会《2026 年 10 月中国汽车保值率报告》（2026-11-10）及公开报道；不构成购买建议。
- 片尾 `end_card` 含 3 条声明（数据来源 / 非购买建议 / **AI 辅助制作**）+「选题、核实与判断，由人完成」+ 来源 + CTA；旁白片尾口播同声明（198.523–208.166s）。
- H3 素材商用授权以 MiniMax 许可为准，发布前确认。
