# 第 08 期 代码层质检清单（engine-dev 自检，供 Lead/delivery 引用）

> 时间：2026-11-16 12:00 UTC；成片 code-only 版（H3 未开机）。

## A. 时间轴 / 帧数
- [x] `work/timeline.json`：total **252.380s**、67 镜、fps 24、7 段（S1–S7）
- [x] 帧边界口径：每镜 = round(end*24) − round(start*24)；**逐镜解码合计 6057 帧 = round(252.380×24)**，0 偏差
- [x] 首镜起点 0.0（片头 0.6s 留白归入 S01），与 audio 252.373s 对齐
- [x] `work/srt/all.srt` = audio 侧最新版（md5 3dfdc812fd9ec6178fb9d195103d422d，99 条，≤18 汉字/行）

## B. 逐镜 clips
- [x] `work/clips/<shot>.mp4` 67/67；1920×1080 / 24.0fps / x264 crf16 / 无声
- [x] 未烘焙遮幅/字幕/统一调色/淡入淡出（由 delivery finalize 统一做）
- [x] `verify_clips.py`：clips 67/67 bad=0 missing=0；时长误差 ≤0.04s；解码 0 错
- [x] H3 缺失镜像（22）：fallback 代码场景（不黑屏/信息完整），记录 `engine-report.md §9/§10` + `work/h3-status.json`

## C. 事实与数字（锁定稿 §7.2 F01–F18 单一数据源）
- [x] `facts.json` 与 §7.2 逐项对齐；场景内不手写数字（除动画逐帧数值外均从 facts 读取）
- [x] S01 钩子：无具体 kW/kWh 数字（口径 §7.1-5）
- [x] S02：无 SOC 百分比（改「电量↑/回收中·示意」）
- [x] S28：落定 0.160 kWh + 「1.5 t 示例车 · 物理估算，非实测（F01）」角标
- [x] S41：0.20/0.14 kWh/<1km + 「物理估算，非实测（F02）」角标
- [x] S32 70–87%（F03）/ S33 87–89%（F04）/ S35 78%（F05）/ S38 <5%（F06）
- [x] S51 无百分比读数（三滑块定性「收紧/放宽」）
- [x] S56/S57 无具体占比数字（S57 用 <5%，F06）
- [x] S62 无 78%/42%（相对比例条 + 示意非实测）

## D. 物理方向契约（逐帧人工复核项）
- [x] 布局：轮端(左) → 电机 → 逆变器 → 电池(右)
- [x] 回收/刹车（S04/S21/S24/S31/S63/S64）：能量点/箭头 **左→右**（青）
- [x] 驱动（S06）：**右→左**（琥珀）；S22 双向双色；S23 由驱动（朝左）翻到回收（朝右）
- [x] 电机剖面：定子/转子/气隙标注；逆变器 DC 母线+三桥臂+三相；电池包+BMS 门禁
- [ ] **H3 版复检**：H3 运动方向 vs 代码箭头（待 H3 到货后人工逐帧，PDF §六）

## E. 视觉规范
- [x] 一屏一重点：每镜有明确信息落点（数字/方向反转/逐站高亮/曲线对比）
- [x] 无匀速推拉、无「会动的静图」（字数卡/图表的动效均绑定语义变化）
- [x] 字幕安全区不放置内容（场景内容 y∈[132,948]）
- [x] 片尾 S67 双声明卡：两行声明文字 + 黑底白字
- [ ] finalize 后复核：2.35:1 上下 132px、ASS 落位、首尾淡入淡出（delivery 硬校验）

## F. 证据路径
- 预览静帧：`work/previews/pv_<shot>_<t>.png`（67 镜中段帧）
- QA 汇总：`.tmp/review/code-previews-v2.jpg`、`qa-fix-check.jpg`、`qa3-endframes.jpg`、`qa3-fixes-v2.jpg`、`qa4-fixes.jpg`、`h3-keyframes-FINAL.jpg`
- 自检：`work/clips-check.log`、`/tmp/qa4_verify.log`（本地）、`work/engine-report.md`
- H3 交接：`comfyui/shots-ep08.json`（23 条）+ `comfyui/keyframes/`（18 张）+ `work/h3-keyframes.json`
