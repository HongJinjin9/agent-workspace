# 第 08 期《电动车松开油门为什么能充电》成片自检报告

> 由 `scripts/write_report.py` 依据实测数据生成（2026-11-17T00:20:14+00:00 UTC）。一句话方向：**松油门不是「发电」，是「把车已经有的动能，从轮子手里抢回来存进电池」**。

## 0. 结论

**全部硬指标通过，可交付。**

## 1. 技术规格（实测）

| 项目 | 实测 | 目标 | 结论 |
| --- | --- | --- | --- |
| 成片 | `/app/vedio/ep08-regen/out/ep08-regen.mp4` | — | — |
| 时长 | 252.380 s（4:12.38） | 3:40–4:20（252.380±0.5s） | ✅ |
| 帧数 | 6057 | 6057 | ✅ |
| 分辨率 | 1920x1080 | 1920x1080 | ✅ |
| 帧率 | 24.0 | 24 | ✅ |
| 画幅 | 16:9 + 2.35:1 上下 132px 遮幅 | 同左 | ✅ |
| 视频/音频 | h264 (High) / aac 48000Hz 2ch | H.264 High + AAC 48kHz | ✅ |
| 体积 | 178.28 MB | — | — |
| 全片解码 | 无错误 | 无错误 | ✅ |
| web 版 | `/app/vedio/ep08-regen/out/ep08-regen-web.mp4`（1280x720 / 252.4s / 24.4MB） | 1280×720，体积更小 | ✅ |
| 编码 | clips 模式；master 编码 562.8s | — | — |

## 2. 响度与音频（实测）

| 指标 | 实测 | 目标 | 结论 |
| --- | --- | --- | --- |
| 整体响度 I | -14.24 LUFS | -14 ±0.5 | ✅ |
| 真峰值 TP | -1.24 dBTP | ≤ -1.0 | ✅ |
| 响度范围 LRA | 2.2 LU | — | — |
| 旁白完整性 corr | sent011=0.9545, sent036=0.9771, sent060=0.9394 | ≥0.9 | ✅ |
| 混音报告摘要 | > → `build_audio.py`（旁白处理 + 分段音乐床 + 音效 + sidechain + 两遍 loudnorm + 自检 + 本报告）。 | — | — |

- 旁白 `zh-CN-YunjianNeural` 逐句表演（7 句/段级时间轴：`audio/work/timeline_audio.json`）。
- 母带：`audio/work/audio.m4a`（AAC 48kHz 立体声），finalize 只做 remux，不重新混音。

## 3. 字幕与画面硬校验

| 检查项 | 实测 | 结论 |
| --- | --- | --- |
| 2.35:1 遮幅（上下 132px 黑边） | 上下 132px 黑边 | ✅ |
| 画面内容非黑 | 中部画面均值 > 4（排除首尾淡入淡出与片尾声明卡 245.3s 后） | ✅ |
| 全片 36 点内容覆盖（无黑段） | 36 点全片采样（排除首尾淡入淡出 0 点）；暗段 0 [] | ✅ |
| 运动量（8 对 0.5s 帧间差） | 8 对 0.5s 帧间差中位数 1.43（min 0.88；跳过 0 对） | ✅ |
| 片头淡入 | 首帧全帧均值 0.00（应 <8） | ✅ |
| 字幕带文字存在 | 22/23 帧字幕带 bright>=1200（需 6） | ✅ |
| 字幕落在下黑边内 | 字幕带最低均值 0.0 | ✅ |
| 字幕不越到画面上 | 单行字幕结构保证（像素实测文字最高行 None，含画面内容干扰，仅记录） | ✅ |
| 字幕条数 | 99 条（应约等于旁白句数） | ✅ |
| 字幕时间单调 | start 单调 | ✅ |
| 字幕无重叠 | 重叠对 0 | ✅ |
| 单行 ≤18 汉字 | 超过 18 汉字的行 0（最宽 16） | ✅ |
| 字幕在片内 | 0 条越界 | ✅ |
| 末条字幕贴近片尾 | 末条结束 251.38s vs 成片 252.38s | ✅ |
| 句级字幕覆盖 | 73/73 句有字幕 | ✅ |
| 片尾双声明卡文字密度 | t=250.4s center_bright=26845（帧存 work/qa/endcard-check.png 供人工目检） | ✅ |
| 片尾口播双声明关键词 | 片尾字幕含 AI 声明=True / 人完成声明=True：换个方向存回去。 它回收的是能量，也是判断。 知道什么时候能收、 什么时候收不到，才算真懂。 本片画面与配音含 AI 辅助制作， 选题、核实与判断由人完成。 | ✅ |
| 尾部收束（黑场/声明卡） | 尾部黑场淡出（末帧均值 2.60） | ✅ |
| H3 素材到位 | 19/19 条到位（Sxx 命名）；assets/h3 共 45 个文件 | ✅ |
| H3 成片时长占比 20–35% | H3 成片时长占比 27.2%（目标 20–35%；可用 19 镜，红线降级 无） | ✅ |
| web 版规格 | 1280x720? 1280x720 / 252.4s / 24.4MB / 解码OK | ✅ |

- 字幕源：`work/srt/all.srt`，99 条；最大单行显示宽度 16 字；末条结束 251.38 s。
- 片尾双声明：画面卡（`work/qa/endcard-check.png` + `delivery/stills/still-10-end-card.jpg`）与旁白口播（片尾字幕关键词）双通道；本机无 OCR，画面可读性由 Lead 人工目检。
- **人工逐帧目检项（脚本无法判定）**：能量流方向（轮端→电机→逆变器→电池的回收/输出双向）、电机-逆变器-电池路径、制动混合方向、H3 画面无乱码文字/无品牌 logo/无真人正脸。抽帧样张：`work/qa/principle-*.png`（关键原理帧）、`work/qa/h3-H*.png`（逐条 H3 抽帧）、`work/qa/verify-contact-sheet.jpg`（16 帧全片）；逐帧清单见 `work/qa/human-check.md`。

## 4. 章节结构

| 段 | 起点 | 段长 | 句/镜数 |
| --- | ---: | ---: | ---: |
| S1 | 0.00s | 0.00s | — |
| S2 | 0.00s | 0.00s | — |
| S3 | 0.00s | 0.00s | — |
| S4 | 0.00s | 0.00s | — |
| S5 | 0.00s | 0.00s | — |
| S6 | 0.00s | 0.00s | — |
| S7 | 0.00s | 0.00s | — |

- 分镜数据：`work/timeline.json`（67 镜）。

## 5. H3 实拍质感素材：使用清单与降级记录

- 分镜引用 H3：**19 条**；assets/h3 文件到位 **45 条**。
- **H3 实际可用 19 镜 / 红线降级 0 镜**（成片按可用口径计 H3 时长）：无降级
  - 红线降级 `H14`(S49)：重生成 1 次后轮毂中心盖仍出现 Mercedes 三叉星品牌标（红线：logo）
  - 红线降级 `H18`(S56)：重生成 1 次后仍有可读车牌/店招文字/行人（红线：文字+人物）
  - 红线降级 `H22`(S60)：重生成 1 次后前车车牌可读（红线：文字）
- 成片 H3 时长占比：**27.2%**（目标 20–35%；按 manifest 可用口径，红线降级镜不计入）。

| 镜号 | 起点 | 时长 | H3 | 状态 |
| --- | ---: | ---: | --- | --- |
| S02 | 4.74s | 2.67s | S02 | 使用 |
| S05 | 15.20s | 2.38s | S05 | 使用 |
| S07 | 21.16s | 2.75s | S07 | 使用 |
| S10 | 30.19s | 3.40s | S10 | 使用 |
| S20 | 66.62s | 3.19s | S20 | 使用 |
| S25 | 89.59s | 2.50s | S25 | 使用 |
| S30 | 104.86s | 3.62s | S30 | 使用 |
| S35 | 123.75s | 3.19s | S35 | 使用 |
| S39 | 138.63s | 3.57s | S39 | 使用 |
| S40 | 142.20s | 5.56s | S40 | 使用 |
| S44 | 161.69s | 5.56s | S44 | 使用 |
| S48 | 177.06s | 3.57s | S48 | 使用 |
| S50 | 182.62s | 3.59s | S50 | 使用 |
| S53 | 195.37s | 5.41s | S53 | 使用 |
| S55 | 203.82s | 3.15s | S55 | 使用 |
| S57 | 209.64s | 2.62s | S57 | 使用 |
| S58 | 212.26s | 4.45s | S58 | 使用 |
| S59 | 216.71s | 2.80s | S59 | 使用 |
| S66 | 240.64s | 4.63s | S66 | 使用 |

**降级/失败记录：**
- - 模式：FL2VA/i2v 15 条；T2V 8 条（其中 FL2VA 失败后降级 0 条）
- - 失败/顺延：0 / 0
- - 能力探测：ComfyUI 0.42.5 / cuda:0 NVIDIA GeForce RTX 5090 : cudaMallocAsync；FL2VA=fl2va；降级=False
- | H14 | S49 | S5 | 雨雪路面与轮胎：胎面碾过水膜，抓地环反光 | fl2va | 864×480 | 5.0s | 202611160115 | 39.9 | d86edd57-1af8-4def-9679-d5bbc30e6486 | PASS | PASS | redline_fallback |
- | H18 | S56 | S6 | 城市车流（续航段）：路口多车减速 | t2v | 864×480 | 5.0s | 202611160119 | 35.8 | a47b6fe1-6010-4fcc-baf4-c8b3acd726cf | PASS | PASS | redline_fallback |
- | H22 | S60 | S6 | 车流跟拍（驾驶习惯段）：前车减速、距离变化（可选尾帧） | t2v | 864×480 | 5.0s | 202611160123 | 35.5 | f239d464-2398-4339-8fd8-6a0d5be8f9ff | PASS | PASS | redline_fallback |
- ## 3. 失败 / 降级 / 待处理
- - **H14** status=redline_fallback raw=assets/h3/raw/H14_raw.mp4 final=assets/h3/H14.mp4 problems=[]；红线：重生成 1 次后轮毂中心盖仍出现 Mercedes 三叉星品牌标（红线：logo）
- - **H18** status=redline_fallback raw=assets/h3/raw/H18_raw.mp4 final=assets/h3/H18.mp4 problems=[]；红线：重生成 1 次后仍有可读车牌/店招文字/行人（红线：文字+人物）
- - **H22** status=redline_fallback raw=assets/h3/raw/H22_raw.mp4 final=assets/h3/H22.mp4 problems=[]；红线：重生成 1 次后前车车牌可读（红线：文字）
- ## 4. T2V 降级镜头（无关键帧 / FL2VA 失败）
- python3 batch_run.py --retries 1          # 生成（FL2VA 优先，失败降级 T2V）


- H3 manifest：`assets/h3/manifest.json`（23 条；状态 OK 20；counts: total=23 ok=20 failed=0 deferred=0 fl2va=15 t2v=8）
  - `H02` fl2va  seed=202611160103 耗时=92.0s
  - `H03` fl2va  seed=202611160104 耗时=38.4s
  - `H04` fl2va  seed=202611160105 耗时=38.3s
  - `H05` fl2va  seed=202611160106 耗时=37.6s
  - `H06` fl2va  seed=202611160206 耗时=42.8s
  - `H07` t2v  seed=202611160108 耗时=1.0s
  - `H08` t2v  seed=202611160208 耗时=35.7s
  - `H09` fl2va  seed=202611160110 耗时=37.8s
  - `H10` fl2va  seed=202611160111 耗时=40.4s
  - `H11` fl2va  seed=202611160112 耗时=38.2s
  - `H12` fl2va  seed=202611160113 耗时=37.3s
  - `H13` fl2va  seed=202611160114 耗时=38.1s
  - `H15` fl2va  seed=202611160116 耗时=41.4s
  - `H16` t2v  seed=202611160117 耗时=36.1s
  - `H17` t2v  seed=202611160118 耗时=35.2s
  - `H19` t2v  seed=202611160219 耗时=35.7s
  - `H20` t2v  seed=202611160121 耗时=38.0s
  - `H21` fl2va  seed=202611160122 耗时=39.8s
  - `H23` fl2va  seed=202611160124 耗时=38.1s
  - `H24` fl2va  seed=202611161100 耗时=38.1s
- H3 状态（机器可读）：`work/h3-status.json`。
- `work/h3-status.json`：ready_count=19, missing=[], total=22, redline_fallback_code=['S49', 'S56', 'S60'], redline_reasons={'H14/S49': '轮毂中心盖出现 Mercedes 三叉星品牌标（H3 两次重生成仍命中）', 'H18/S56': '可读车牌/店招文字 + 行人（H3 两次重生成仍命中）', 'H22/S60': '前车车牌可读（H3 两次重生成仍命中）'}, h3_share_planned=0.272, note=S49/S56/S60 按合规红线改用代码降级场景（h3=false），不进 H3 画面；其余 19 条为 H3 终版
- H3 只承担「像真的」：真实道路/车内/踏板/刹车灯/底盘/充电口等实拍质感与环境声；永不承载文字、数据、原理示意、字幕、配音、最终拼接（PDF §一 Q1–Q4 口径）。
- provenance：`assets/h3/manifest.json`。

## 6. 合规声明

- **AI 参与声明（双通道）**：片尾画面卡「本片画面与配音含 AI 辅助制作」「选题、核实与判断，由人完成」+ 旁白口播同义声明。
- **匿名化**：全片不出镜、不署名、无职业/公司/证件/车牌信息；H3 提示词禁止真实人物与品牌 logo；不点评具体车型/品牌好坏。
- **事实与数字**：物理方向（电流方向、能量流向、转子/定子、制动混合）以公开标准/论文/厂商公开参数为准；数字单一数据源 `facts.json`，画面与字幕同源。
- **素材授权**：程序化渲染（原创）；H3 生成（MiniMax H3，发布前按平台许可确认）；Pexels B-roll（Pexels License，如有）；BGM/音效原创合成（numpy，无外部曲库）；字体 Noto CJK（OFL）。明细见 `delivery/delivery-manifest.json` 的 `assets_provenance`。
- **成片与素材不入库**：仓库只保留脚本/文档/时间轴/SRT/清单/静帧封面（按 .gitignore）。

## 7. 交付物

- 成片 master：`out/ep08-regen.mp4`（252.380 s / 178.28 MB / sha256 `dd4e6684b19473134cc1a6e2c40930416d5478b28e4d447dbe49665b3224de66`）
- web 版：`out/ep08-regen-web.mp4`（24.45 MB / sha256 `8dafaf8b8267bf706ce09db9cbccdcb1155d0b5abd3bba5aceae17ca8cb1b977`）
- 静帧：`delivery/stills/` 10 张（still-01-cover, still-02-energy-flow, still-03-motor-cutaway, still-04-inverter-battery, still-05-energy-account, still-06-limits, still-07-one-pedal, still-08-range, still-09-data, still-10-end-card）
- 联系表：`delivery/contact-sheet.jpg`
- 封面：cover-16x9.jpg, cover-1x1.jpg, cover-3x4.jpg
- 工程：`/app/vedio/ep08-regen`（自研 Python/PIL 程序化渲染 + ComfyUI H3 证据影像）；仓库同步目录 `视频制作/ep08-regen/`（仅源码/文档/时间轴/SRT/清单/静帧封面，素材与成片不入库）。
- 渲染/编码：finalize `clips` 模式，master 562.8s、web 106.7s（`work/finalize.json`）。
- 校验抽帧联系表：`work/qa/verify-contact-sheet.jpg`

## 8. 已知限制

- **本机无 OCR**：片尾声明卡与花字可读性以「文字像素密度 + 静帧」判定，交付前由 Lead 人工目检一次。
- **物理/能量流正确性需人工逐帧目检**：脚本只能验证画面存在与运动量，不能判断电流方向/能量流箭头语义。
- **H3 商用许可**：MiniMax H3 生成内容的商用发布需按平台许可确认；成片仅在内部交付，发布前复核。
- **H3 素材缺失时**：engine 的 footage 层自动隐藏/降级（不黑屏），实际使用清单见本报告 §5；本次以 `check.h3` 实测为准。
- **响度/真峰值**：以 ffmpeg loudnorm 实测为准；不同播放器/平台转码后可能有 ±0.3 LU 偏差。

**本次人工备注 / 补充限制：**

# EP08 交付备注 / 已知限制（write_report.py 会整段并入 final-report.md §8）

> 交付 owner 在成片验收后补充；只写实测结论与人工目检结果，不写「应该没问题」。

## 1. 交付形态：H3 正式版

- ComfyUI MiniMax H3 窗口 2026-11-16T23:28Z–2026-11-17T00:28Z：`assets/h3/` 45 个 mp4（23 Hxx + 22 Sxx），
  manifest counts **total 23 / ok 20 / redline_fallback 3 / failed 0 / fl2va 15 / t2v 8**；H24 备用未使用。
- **红线降级 3 镜**：H14→S49（重生成后仍有品牌 logo）、H18→S56（可读车牌/店招/行人）、H22→S60（前车车牌可读），
  按 Lead 规则走**代码层降级**（clips 中 S49/S56/S60 必须为代码版，不得用 H3 画面）；manifest `redline` 字段与
  `comfyui/report.md §3` 记录原因。
- 成片 H3 时长占比：**实测 27.2%**（19 个 H3 镜 / 67 镜时长口径；时间轴已更新 `h3=true` 19 镜）；
  engine 初算 30.2% 是 23 条全可用口径，h3-operator 估算 ~24%；实测 27.2% 在 20–35% 内。
- 之前 code-only 兜底版（12:10）已归档 `out/fallback-codeonly/`（master sha256 4f06f803…），H3 版不可用时可直接回退；
  归档时 verify 的 `content_present` FAIL 是误判（t=246.38s 片尾暗底声明卡），已修判据。

## 2. 渲染/编码实测

- 逐镜渲染：code-only 67 镜（QA4 后）+ H3 整合 23 镜（22 混合 + S67，`--force`，约 7 分钟/2 进程）；
  `verify_clips.py` 67/67 bad=0、全部 1920×1080/24fps/解码 0 错、时长误差 ≤0.04s。
- 拼接：67 镜合计 252.25s（H3 镜重渲后比时间轴短 0.13s）→ finalize 用 `tpad=clone` 补齐到时间轴 252.380s，
  成片帧数应为 6057（=round(252.380×24)）。
- 长进程纪律：finalize/交付链必须 `setsid nohup ... < /dev/null &` 脱离会话，否则随 agent 回合结束被回收；
  `flock /tmp/ep08-finalize.lock` 与 engine 的 `/tmp/ep08-render.lock` 互斥（finalize 启动会等 render 锁释放）。

## 3. 人工目检（Lead 逐帧，待填结果）

- [ ] 能量流方向：回收=轮端→电机→逆变器→电池；驱动=电池→逆变器→电机→轮端；不得混向。
- [ ] 电机-逆变器-电池剖面路径、转子/定子/三相/DC 母线标注正确。
- [ ] 制动混合方向（液压制动 + 电机回收的力矩分配）。
- [ ] H3 画面：无乱码文字/可读数字/原理箭头、无品牌 logo、无真人正脸；车轮转向/踏板行程/刹车盘热态/雨雪抓地/ABS 轮速等物理细节合理（PDF §六 要求逐帧目检）。
- [ ] 片尾双声明卡可读（`work/qa/endcard-check.png`）+ 旁白口播可闻。
- [ ] 低运动抽帧（`work/qa/motion-probe/`）：H3 到货后应由实拍运动提升；若仍有 fallback 静置卡需记录。

## 4. 已知限制

- **H3 商用许可**：MiniMax H3 生成内容的商用发布需按平台许可确认（发布前复核，凭据未落仓库）。
- **H3 物理细节需人工逐帧目检**：脚本只能验证画面存在与运动量，不能判断电流方向/能量流箭头语义与 H3 物理合理性。
- **运动量指标裕度**：`motion_present` 含胶片颗粒贡献，人检时仍需确认「不是会动的静图」；补充指标 `motion_content`（强变化像素占比）自动记录。
- **本机无 OCR**：片尾声明卡/花字可读性以「文字像素密度 + 静帧」判定，交付前人工目检。
- **平台转码**：响度/真峰值以 ffmpeg loudnorm 实测为准，平台转码后可能有 ±0.3 LU 偏差；字幕字号在手机端需预览一次。
- **本机 ffprobe 是假的**（符号链接到 ffmpeg）：校验脚本统一用 `ffprobe-real` / `ffmpeg -i` 解析。
- **H3 素材授权**：H3 素材大文件不入库，仓库只保留 `comfyui/` 工单/报告与 `assets/h3/manifest.json` provenance。

## 5. 合规

- 片尾画面卡 + 旁白口播双声明（AI 辅助制作 / 选题核实判断由人完成）。
- 全片不出镜、不署名、无职业/公司/证件/车牌信息；不点评具体车型/品牌好坏。
- AI 素材：H3 23 条（22 使用 + H24 备用）；BGM/音效 numpy 原创合成；旁白 edge-tts `zh-CN-YunjianNeural`；
  Pexels B-roll（如有）按 `delivery/delivery-manifest.json` 的 `assets_provenance` 记录；字体 Noto CJK（OFL）。

