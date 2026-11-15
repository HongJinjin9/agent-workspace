# 第 07 期 MotionHarness Pro 工程 · 技术契约（SPEC · v2 动效/数据主导版）

> 场景与镜头设计依据：仓库 [`视频制作/ep07-scene-design/SCENE-DESIGN.md`](../ep07-scene-design/SCENE-DESIGN.md)。
> 本文件补充工程/验收契约，不重复场景设计内容。冻结哈希见交付报告。

## 1. 目标与规格

| 项目 | 契约 |
| --- | --- |
| 成片 | `out/ep07-mh.mp4`，1920×1080 / 24fps / **208.9664s**（5015 帧） |
| 画幅 | 16:9 全幅 + **上下 132px 2.35:1 纯黑遮幅**（内容区 1920×816） |
| 主视觉 | **motion-graphics / 数据动画主导**：`data` 38 镜 + `split` 1 + `end` 1；H3 作为强关联证据插入（`h3` 27 镜 / 17 条 clips）；3D 评估室为暗场空间背景 |
| 节奏 | 67 镜 / 平均 3.10s（对齐旁白数据落点；CLOSE 收束段保留声明卡） |
| 影调 | 冷灰 `#0b0e11` / 纸白 `#e9e4d8` / 琥珀 `#d9a441` / 批注红 `#b3392e`；统一颗粒 + 暗角 + 遮幅 |
| 声音 | 第 07 期母带：I=-14.43 LUFS / TP=-1.62 dBTP / LRA=2.40；声明口播 198.523–208.166s |
| 字幕 | `srt.json` 98 条，单条活动、0.12s 淡入淡出、零重叠；落于下黑边内（46px 纸白） |
| 导出 | 720p master 8 段（flock 单实例、`MH_EXPORT_WORKERS=2`）→ concat → lanczos 1080p+unsharp → 母带 remux（1080p 直出在本机 4CPU 有确定性 capture deadline 超时） |
| 交付 | 成片 + 10 静帧 + 联系表 + 16:9/1:1/3:4 封面 + `work/final-report.md` + `assets-manifest.json` |

## 2. 图层栈契约（`src/Stage.tsx`，自下而上）

1. `ThreeCanvas` 3D 评估室暗场背景（`src/three/World.tsx`）：A–E 五区、程序化几何/材质、相机由 `shots.json.space/cam/spaceMotion` 驱动。
2. `FootageLayer`（H3 证据影像，仅 `kind=h3|split`）：运镜处理 `treat`（push_in/push_out/pan_l/pan_r/punch_in/mirror/panel/fill）；24fps 帧格量化 seek；缺失/解码失败自动隐藏（3D 兜底）。
3. `scrim` 压暗层：H3 镜头只压底/左，数据镜头把 3D 压成暗场，保证**一屏一个第一视觉重点**。
4. `GraphicsLayer`（`src/graphics/index.tsx`）：读 `graphics_cues.json`，在窗口内挂载对应图形块（data/split/end 镜头的主视觉）。
5. `LowerThird`：H3 镜头的动态下三分之一信息条。
6. `Chrome`：132px 遮幅 + 暗角 + 确定性胶片颗粒 + 幕标签；`Subtitles`。

## 3. 数据契约

- `shots.json`：67 条，覆盖 1.0–208.966s；字段 `id,n,start,end,dur,seg,kind,block,clip,treat,headline,sub,space,cam,spaceMotion`；`kind` ∈ {data(38), h3(27), split(1), end(1)}。
- `graphics_cues.json`：40 条图形事件（`block` + from/to + props），覆盖 17 类块。
- `h3_manifest.json`：H3 素材用途映射（20 条素材；v2 引用 17 条：H01–H03,H05–H14,H16,H17,H19,H20）。
- `srt.json`：98 条字幕（TTS 实测时间轴，与 `audio/work/timeline_audio.json` 对齐）。
- `facts.ts`：数字/引述/声明唯一数据源；`theme.ts`/`types.ts`：色板/字号/遮幅/六幕实测边界/类型定义。
- `timeline.json`：发言稿 v0.2 设计时间轴（仅参考，不参与最终时长）。

## 4. 验收（`scripts/verify_ep07.py`，全 PASS 才交付）

分辨率/帧率/时长（±0.5s）/帧数（±2）/解码 0 错/响度 I∈[-14.81,-13.81]、TP≤-1.0/上下 132px 黑边/字幕带文字/SRT 98 条（单调、无重叠、不越界、显示宽≤20）/H3 引用 clips 全到位/**全片 36 点内容覆盖（无黑段）**/运动量（帧间差中位数>0.8）/片尾双声明卡文字密度/尾部收束（黑场或声明卡）+ 16 帧抽帧联系表。

## 5. 风险与降级

| 风险 | 降级 |
| --- | --- |
| MH Pro 1080p 直出 capture deadline 超时（实测 85–90s 段确定性失败） | **720p master 分段渲染 + lanczos 1080p 上采样**（本片实际方案，报告注明） |
| 单段失败/内存不足 | 段级重试 + `mh daemon stop` 释放内存；必要时 13s 子段 |
| H3 素材缺失 | FootageLayer 隐藏该镜证据窗回 3D 兜底（不黑帧） |
| 图形块缺失（cues 未实现 block） | 交付前用全片内容覆盖检查发现空白段；补块或改 cue（需 freeze 前完成） |
