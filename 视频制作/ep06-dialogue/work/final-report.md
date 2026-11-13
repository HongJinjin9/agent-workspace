# 第 06 期《他们说，这是最糟糕的方案》成片自检报告

> 由 `finalize.py` 自动生成；全部结论来自实测（本 Agent 无法人耳盲听）。

## 1. 技术规格

| 项目 | 实测 | 目标 | 结论 |
| --- | --- | --- | --- |
| 时长 | 230.220s（3:50.22） | 230.206s（timeline） | ✅ |
| 帧数 | 5524 | 5525 | ✅ |
| 分辨率 | 1920x1080 | 1920x1080 | ✅ |
| 帧率 | 24.0 | 24 | ✅ |
| 体积 | 56.0 MB | — | — |
| 全片解码 | 无错误 | 无错误 | ✅ |

## 2. 响度与旁白完整性

| 指标 | 实测 | 目标 | 结论 |
| --- | --- | --- | --- |
| 整体响度 I | -14.31 LUFS | -14 ±0.5 | ✅ |
| 真峰值 TP | -1.68 dBTP | ≤ -1.0 | ✅ |
| 响度范围 LRA | 7.50 LU | — | — |
| 旁白完整性 corr | ACT1_2=0.9394, ACT3_2=0.9232, CLOSE_7=0.9203 | ≥0.9 | ✅ |

## 3. 字幕

| 指标 | 实测 | 目标 | 结论 |
| --- | --- | --- | --- |
| 字幕条数 | 72 | 覆盖 58 句 | ✅ |
| 句覆盖 | 58/58 | 58/58 | ✅ |
| 时间单调 | True | 是 | ✅ |
| 重叠对 | 0 | 0 | ✅ |
| 超 18 字行 | 0 | 0 | ✅ |
| 落在句区间外 | 无 | 0 | ✅ |
| 首/末条 | 2.80s / 228.49s | 片内 | ✅ |
| 字号 | 48px 白字 60% 黑描边，下方黑边内 | 46–48px | ✅ |

## 4. 画面检查（2.35:1 遮幅 / 片尾卡 / 淡出）

| 检查点 | 上黑边均值 | 下黑边均值 | 画面均值 | 结论 |
| --- | ---: | ---: | ---: | --- |
| subtitle-check | 0.01 | 3.79 | 63.76 | ✅ |
| end-declaration | 0.01 | 2.47 | 21.38 | ✅ |
| quote-card | 0.00 | 3.59 | 19.20 | ✅ |
| data-curve | 0.00 | 1.81 | 14.93 | ✅ |
| fade-out | 0.00 | 0.00 | 0.00 | ✅ |

- 遮幅：✅；字幕在黑边内：✅；片尾 AI 声明卡可读：✅；尾部淡出：✅

- 影调：统一调色链（eq/colorbalance/vignette/noise）+ 每镜 look 按幕偏移：冷开场/第一幕冷灰（cool）、第二幕中性（neutral）、第三幕转暖（warm）、第四幕回冷（cool2）、收束中性；引述卡（quote_feng/quote_li）自带打字机与出处小字。

## 5. 素材使用

- 两位角色（老规矩 M / 小账本 L）为 **AI 生成的虚构形象**，不代表、不影射任何真实人物；正脸不清晰（侧影/背影/过肩/手部），对话为创作内容；引述均由旁白转述并标注时间出处。
- **真实 ComfyUI H3 视频**：28/28 空间层镜位（comfy_c1, comfy_c10, comfy_c11, comfy_c12, comfy_c13, comfy_c14, comfy_c2, comfy_c3, comfy_c4, comfy_c5, comfy_c6, comfy_c7, comfy_c8, comfy_c9）
- AI 静帧兜底（仅渲染期间占位；最终成片 未使用）：0 镜（无）
- 本地 B-roll 退路：0 镜（无）
- 程序化场景（PIL）：8 镜；H3 视频镜位：28 镜

## 6. 交付物

- 成片：`out/ep06-dialogue.mp4`
- 静帧：`delivery/stills/`（9 张：still-01-cold-open, still-02-quote-feng, still-03-bar-compare, still-04-quote-li, still-05-distance-close, still-06-data-curve, still-07-blank-manual, still-08-end-card, still-09-end-declaration）
- 封面：cover-16x9.jpg, cover-1x1.jpg, cover-3x4.jpg
- 联系表：delivery/contact-sheet.jpg
- 时间轴：`work/timeline.json`（36 镜 / 58 句）

- 片尾双声明（画面卡）：「本片人物为 AI 生成的虚构形象，不代表任何真实人物」 + 「本片画面与配音含 AI 辅助制作」；旁白 outro_voice 口播 AI 声明同期覆盖。

## 7. 结论

**全部硬指标通过，可交付。**
