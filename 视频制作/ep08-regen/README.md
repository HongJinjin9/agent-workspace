# 第 08 期《电动车松开油门为什么能充电》视频工程

> 自媒体稿：`自媒体稿/第08期-电动车松开油门为什么能充电.md`（v1.0，Lead 2026-11-16 锁定）
> 场景设计：`视频制作/ep08-scene-design/SCENE-DESIGN.md`（v1.0，67 镜 / 24 条 H3 / 7 段）
> 系列：`vibe 知识共赏`｜16:9 横屏电影感物理机制短片｜单声部旁白 `zh-CN-YunjianNeural`
> 分工总原则（PDF《代码与 ComfyUI 分工详解》§一 Q1–Q4）：**代码负责「是真的」（时间轴/事实/原理图/数据/文字/字幕/最终合成）；ComfyUI MiniMax H3 只负责「像真的」（实拍质感运动与环境声）**。H3 永不承载文字、数字、原理示意、字幕、配音与最终拼接。

**一句话方向**：松油门不是「发电」，是「把车已经有的动能，从轮子手里抢回来存进电池」——有方向、有损耗、有条件。

---

## 一、规格与结构

| 项 | 契约 | 实测 |
| --- | --- | --- |
| 成片 | `out/ep08-regen.mp4`（交付 master，不入库） | <!-- FILL: film-path --> |
| 画幅 | 1920×1080 / 24fps / 2.35:1（上下各 132px 黑边） | <!-- FILL: spec --> |
| 时长 | 锁定稿设计 **252.24s（4:12.24，约 6054 帧）**，按 TTS 实测回填；交付窗口 3:40–4:20 | <!-- FILL: duration --> |
| 编码 | H.264 High + AAC 48kHz；`-movflags +faststart` | <!-- FILL: codec --> |
| 声音 | 母带 I=-14±0.5 LUFS / TP≤-1.0 dBTP | <!-- FILL: loudness --> |
| 影调 | 冷灰 `#0e1216` / 纸白 `#e9e4d8` / 能量青 `#2fd3c5`（回收/电）/ 动力琥珀 `#d9a441`（输出/损耗）/ 批注红 `#b3392e`（危险/限制）；统一调色 + 胶片颗粒 + 暗角 | — |
| 字幕 | 句级 SRT（TTS 实测时间轴），单行 ≤18 汉字，白字 + 60% 黑描边，落在下黑边内 | <!-- FILL: srt --> |
| 片尾 | 画面卡 + 旁白口播双声明（「本片画面与配音含 AI 辅助制作」「选题、核实与判断，由人完成」） | <!-- FILL: endcard --> |
| 交付 | master + web 版（1280×720）+ 联系表 + 10 静帧 + 16:9/1:1/3:4 封面 + 工程包 | — |

### 段落结构（设计值，实测以 `work/timeline.json` 为准）

| 段 | 时间 | 镜数 | H3 镜数 | 核心动作 |
| --- | --- | ---: | ---: | --- |
| 4.1 冷开场 | 0:00.00–0:15.31 | 4 | 2 | 松油门在充电（钩子）→ 可逆能量通道亮相 |
| 4.2 立判 | 0:15.31–0:47.56 | 9 | 3 | 能量守恒；电机可逆；不是永动机 |
| 4.3 拆解 | 0:47.56–1:28.80 | 11 | 1 | 电机/逆变器/电池三件套；双向四站 |
| 4.4 能量账 | 1:28.80–2:31.09 | 17 | 5 | 动能计算 → 效率 → 损耗 → Sankey → 下坡估算 |
| 4.5 四条限制 | 2:31.09–3:14.83 | 11 | 4 | 满电/低温/高速/抓地力/充电功率 |
| 4.6 再判 | 3:14.83–3:51.12 | 10 | 7 | 单踏板/混合制动/续航/刹车片/驾驶习惯 |
| 4.7 收束 | 3:51.12–4:12.11 | 5 | 1 | 金句 + 边界 + 双声明 |

### 核心视觉母题

**可逆能量通道：轮端 → 电机 → 逆变器 → 电池（四站、双向）**。能量点是「主角」，它往哪流，观众就看哪：
- 回收（松油门/制动）：轮端 → 电机（发电）→ 逆变器 → 电池；
- 驱动（踩油门）：电池 → 逆变器 → 电机 → 轮端；
- 损耗（热）：刹车盘、逆变器、电池内阻、风阻/滚阻。

---

## 二、两套影像体系

| 层 | 承担 | 边界 |
| --- | --- | --- |
| **代码层**（自研 Python/PIL/numpy 程序化渲染 + ffmpeg） | 全片唯一时间轴；可逆能量通道图、电机+逆变器+电池剖面、能量账 Sankey、四条限制四联卡、单踏板/混合制动分配图、数据曲线与数字、片头钩子、片尾声明卡、花字、字幕、最终合成 | 原理/数字/术语/方向/因果关系一律代码；画面数字与 `facts.json` 同源 |
| **H3 层**（ComfyUI + MiniMax H3，云端 RTX 5090） | 真实道路/车内/踏板/刹车灯/底盘/电池包/充电口/雨雪等实拍质感镜头 + 环境声；单条 5s 生成、剪辑取 2.5–4s | 永不承载文字/可读数字/原理箭头/字幕/配音/最终拼接；无品牌 logo、无真人正脸；物理方向由代码层校验与叠加 |
| **混合镜** | H3 底 + 代码叠加层（标注/箭头/数字） | 叠加层由代码渲染，H3 只做质感 |

影调/字幕/合成链（`scripts/finalize.py` 统一施加，逐镜 clip 不烘焙遮幅/字幕/调色）：

```
eq(contrast 1.045 / brightness +0.012 / sat 1.06) → colorbalance(冷暗部/暖高光)
→ vignette(PI/5.2) → noise(alls=5, temporal+uniform 胶片颗粒)
→ 2.35:1 drawbox(上下各 132px) → ASS 字幕(Noto Sans CJK SC 48px, 白字+60%黑描边, 下黑边内)
→ 首尾淡入淡出(0.6s / 1.2s) → yuv420p
```

---

## 三、工程结构

| 路径 | 内容 | 归属 |
| --- | --- | --- |
| `PLAN.md` | 制作总纲（Lead 权威） | Lead |
| `自媒体稿/第08期-电动车松开油门为什么能充电.md` | 锁定稿（仓库根） | story-writer |
| `视频制作/ep08-scene-design/SCENE-DESIGN.md` | 场景设计稿 v1.0（67 镜 / 24 H3 / facts 表） | story-writer |
| `shots.json` / `work/timeline.json` / `work/shots.json` | 分镜与实测时间轴（以 `audio/work/timeline_audio.json` 为唯一时间基准） | engine-dev |
| `scene_body.py` / `scenes_pil.py` / `overlays.py` / `ep08viz.py` / `ep08assets.py` / `build_timeline.py` / `preview_scene.py` | 程序化场景/叠加层/渲染编排/素材解析 | engine-dev |
| `ep08viz.py` / `scenes_pil.py` / `overlays.py` | 可复现的代码层英雄镜头与叠加器 | engine-dev |
| `narration/` / `tts_perf.py` / `music.py` / `sfx.py` / `build_audio.py` | 逐句表演 TTS 谱、原创 BGM、音效、混音母带 | audio-engineer |
| `audio/work/` | `timeline_audio.json`（唯一时间基准）、`audio.m4a` 母带、`audio-report.md`、句级 SRT | audio-engineer |
| `comfyui/` | H3 工单/提示词/工作流/批处理/窗口 runbook/逐镜报告 | h3-operator |
| `assets/h3/` | H3 成片素材 `H01..H24.mp4`（大文件不入库，provenance 见 manifest） | h3-operator |
| `scripts/` | **交付/验收脚本**：`finalize.py`（成片收尾）、`verify_ep08.py`（硬校验）、`prepare_delivery.py`（静帧/联系表/封面/manifest）、`gen_cover.py`、`make_contact_sheet.py`、`write_report.py`（报告/清单）、`render_all.sh`（渲染编排）、`deliver_all.sh`（一键链）、`sync_repo.sh`、`make_engine_package.sh` | delivery-engineer |
| `work/` | 时间轴/字幕/QA/`final-check.json`/`final-report.md`/`audio-report.md`/`RUNBOOK.md` | engine / audio / delivery |
| `delivery/` | 10 静帧 + 联系表 + 三版封面 + `delivery-manifest.json` | delivery-engineer |
| `assets-manifest.json` | 素材 provenance（H3/Pexels/程序化/合成/字体） | delivery-engineer |
| 生产根目录脚本 | engine-dev 的场景/时间轴/渲染编排脚本（`scene_body.py` 等）；**交付/验收以 `scripts/` 为准** | engine-dev |

> 本仓库**只存可复现的脚本/文档/时间轴/SRT/清单/静帧封面**；成片（`out/`）、素材（`assets/`）、音频大文件、逐帧中间产物不入库（`.gitignore`）。

---

## 四、流水线 / 复现命令

生产目录 `/app/vedio/ep08-regen`（本机 cgroup 实测 **4 CPU / 6GB**：ffmpeg 统一 `-threads 2`，x264 `-threads 4`，Python `OMP_NUM_THREADS=2`；同一时刻只允许一个全片渲染/编码）。

```bash
cd /app/vedio/ep08-regen
export PATH=/home/admin/.local/bin:$PATH

# 1) 声音：逐句表演 TTS → 旁白/时间轴；原创 BGM/音效；混音母带 + 句级 SRT
python3 tts_perf.py && python3 music.py && python3 sfx.py && python3 build_audio.py
#   产物：narration/narration.wav、audio/work/timeline_audio.json、audio/work/audio.m4a、audio/work/srt/all.srt

# 2) 时间轴/分镜（以 audio/work/timeline_audio.json 为唯一基准）
python3 build_timeline.py
#   产物：work/timeline.json、work/shots.json、work/srt/all.srt

# 3) H3 交接包 + 窗口生成（人工开机，1 小时计费窗口；详见 comfyui/RUNBOOK.md）
#   python3 comfyui/... （见 comfyui/README.md）
#   产物：comfyui/keyframes/*、comfyui/shots-ep08-run.json、assets/h3/H01..H24.mp4、comfyui/report.md

# 4) 逐镜渲染（flock 单实例；先与 delivery 的 finalize 锁互斥）
scripts/render_all.sh --cmd "python3 scene_body.py --all --jobs 2"
#   产物：work/clips/<shot-id>.mp4（1920×1080/24fps，不烘焙遮幅/字幕/调色）

# 5) 成片收尾 + 交付链（finalize → 硬校验 → 静帧/封面 → 报告 → 仓库同步 → 工程包）
scripts/deliver_all.sh
#   等价于分步执行：
#   python3 scripts/finalize.py --wait 900          # out/ep08-regen.mp4 + out/ep08-regen-web.mp4
#   python3 scripts/verify_ep08.py                  # -> work/final-check.json + QA 静帧 + 联系表
#   python3 scripts/prepare_delivery.py             # -> delivery/（10 静帧/联系表/三版封面/manifest）
#   python3 scripts/write_report.py --notes work/notes.md   # -> work/final-report.md + assets-manifest.json
#   scripts/sync_repo.sh && scripts/make_engine_package.sh --with-stills
```

finalize 的双模式（与 engine 渲染入口解耦）：

```bash
# A) 逐镜 clips（默认，engine 入口 python3 scene_body.py --all --jobs 2）
python3 scripts/finalize.py --wait 900

# B) engine 整合渲染全片（如启用）：未烘焙遮幅/字幕时走同一滤镜链；已烘焙则视频流 copy + 母带 remux
python3 scripts/finalize.py --input work/film-raw.mp4
python3 scripts/finalize.py --input work/film-raw.mp4 --baked
```

---

## 五、实测数据（交付后回填）

| 项 | 实测 | 目标 |
| --- | --- | --- |
| 时长 / 帧数 | <!-- FILL: dur-frames --> | 252.24s（±0.5s）/ 6054（±2） |
| 分辨率 / 帧率 | <!-- FILL: res --> | 1920×1080 / 24fps |
| 体积（master / web） | <!-- FILL: size --> | web 体积更小 |
| 全片解码 | <!-- FILL: decode --> | 0 错误 |
| 整体响度 I | <!-- FILL: I --> | -14 ±0.5 LUFS |
| 真峰值 TP | <!-- FILL: TP --> | ≤ -1.0 dBTP |
| LRA | <!-- FILL: LRA --> | 0–20 LU |
| 旁白完整性 corr | <!-- FILL: corr --> | ≥0.9 |
| 2.35:1 遮幅 | <!-- FILL: bars --> | 上下 132px |
| 字幕 | <!-- FILL: subs --> | 句覆盖 100% / 无重叠 / 单行≤18 汉字 / 下黑边内 |
| 内容覆盖 / 运动量 | <!-- FILL: coverage --> | 36 点无黑段 / 8 对帧间差中位数 >0.8 |
| H3 时长占比 | <!-- FILL: h3 --> | 20–35% |
| 片尾双声明 | <!-- FILL: endcard --> | 画面卡 + 旁白口播 |

**硬校验**：`python3 scripts/verify_ep08.py`（35 项，含 QA 静帧与 16 帧联系表），结果见 `work/final-check.json`，结论见 `work/final-report.md`。

---

## 六、素材与授权

| 素材 | 来源 | 授权 |
| --- | --- | --- |
| 程序化原理图/剖面/数据/排版/字幕/片头片尾/合成 | 自研 Python（PIL/numpy）程序化渲染 | 本仓库原创 |
| H3 实拍质感镜头 | ComfyUI + MiniMax H3（云端 RTX 5090），本机 lanczos 1080p | MiniMax H3 生成内容；商用发布前按平台许可确认 |
| Pexels B-roll（如使用） | Pexels（`assets/manifest.json` 记录 id/页面/作者） | Pexels License（免费商用、无需署名、不得转售原素材） |
| 旁白 | edge-tts `zh-CN-YunjianNeural` 逐句合成 | 生成式语音；逐句表演谱见 `narration/performance.json` |
| BGM / 音效 | numpy 原创合成（无外部曲库） | 原创合成，无版权分成 |
| 字体 | Noto Serif/Sans CJK | OFL 1.1 |

明细以 `delivery/delivery-manifest.json` 的 `assets_provenance` 与 `assets-manifest.json` 为准。

---

## 七、合规与匿名化

- **AI 参与双声明**：片尾画面卡「本片画面与配音含 AI 辅助制作」「选题、核实与判断，由人完成」+ 旁白口播同义声明。
- **匿名化**：全片不出镜、不署名、无职业/公司/证件/车牌信息；H3 提示词禁止真实人物与品牌 logo；不点评具体车型/品牌好坏。
- **事实与数字**：物理方向（电流方向、能量流向、转子/定子、制动混合）以公开标准/论文/厂商公开参数为准；所有硬数字单一数据源 `facts.json`，画面与字幕同源；估算类数字画面标注「估算」。
- **发布**：平台发布时勾选「含 AI 生成内容」声明（按平台要求）。

---

## 八、自检与已知限制

- 全片解码 0 错误、时长/帧数/分辨率/响度/真峰值/遮幅/字幕/片尾双声明/H3 占比等 35 项硬校验见 `work/final-check.json`。
- **人工逐帧目检（脚本查不出）**：能量流方向（轮端→电机→逆变器→电池，回收/输出不得混向）、电机-逆变器-电池剖面路径、制动混合方向、H3 物理细节（车轮转向/踏板行程/刹车盘热态/雨雪抓地/ABS 轮速）、无乱码文字/无品牌 logo/无真人正脸。抽帧样张：`work/qa/principle-*.png`、`work/qa/h3-H*.png`、`work/qa/verify-contact-sheet.jpg`。
- **本机无 OCR**：片尾声明卡可读性以「文字像素密度 + 静帧」判定，交付前人工目检一次（`work/qa/endcard-check.png`）。
- **H3 商用许可**：发布前按平台许可确认。
- **H3 缺失/失败**：code 层自动降级顶替（不黑屏），实际使用与降级记录见 `work/final-report.md` §5 与 `comfyui/report.md`。
- 其他本次限制见 `work/notes.md`（并入 `work/final-report.md` §8）。

---

## 九、交付物与发布记录

- 交付物（不入库，随 GitHub Release）：
  - `out/ep08-regen.mp4`（master，1920×1080 / 24fps / 2.35:1）
  - `out/ep08-regen-web.mp4`（web 版，1280×720）
  - `delivery/contact-sheet.jpg`、`delivery/stills/`（10 帧）
  - `delivery/cover-16x9.jpg` / `cover-1x1.jpg` / `cover-3x4.jpg`
  - `out/ep08-regen-engine-pack-*.tar.gz`（工程包：脚本/文档/时间轴/SRT/清单/静帧封面）
  - `delivery/delivery-manifest.json`（含 sha256 与素材授权）
- 仓库入库范围：本 README、`scripts/`、`work/`（时间轴/SRT/报告/清单）、`delivery/`（静帧/封面/联系表/manifest）、`comfyui/`（工单/提示词/工作流/RUNBOOK）、`assets-manifest.json`。
- 发布状态：<!-- FILL: release -->（Lead 在 PR/Release 环节回填：B 站 / 微信视频号链接、日期、AI 声明勾选情况）。
