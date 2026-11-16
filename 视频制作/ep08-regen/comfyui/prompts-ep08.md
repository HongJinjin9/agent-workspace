# 第 08 期 ComfyUI H3 提示词（23 条，864×480 / 5.0s / 8 步 turbo LoRA）

> 本文件由 `make_prompts_ep08.py` 从机器可读源 `shots-ep08-run.json` 生成，勿手改。
> 入口/凭据只走环境变量（`H3_USER`/`H3_PASS`/`H3_BASE` 或 `/home/admin/.h3.env`），绝不写入仓库、日志或消息。
> 工作流 `workflows/t2v_api.json`（API 格式，实测直提）；变量节点：
> prompt/width/height/length = `140:131`，时长秒 = `140:133`，帧数表达式 = `140:132`，seed = `140:129`，
> 8 步 turbo LoRA 开关 = `140:139`（true→`140:138`=8），SaveVideo = `92`；
> 首帧/尾帧走 FL2VA：`LoadImage 900/910` → `ImageScale 901/911` → `MiniMaxH3ImageToVideo.first_frame/last_frame`。
> 提示词规范（PDF §4）：分阶段时间轴、一次一种运镜、声音显式描述、末尾固定禁止事项；单条 ≤15s（本期 5s）。

## 分镜映射

| 镜头 | 段落/锚点 | 内容 | 生成分辨率 | 时长 | 模式 | seed | 首帧 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| H02 | S1 | 车内侧窗：长下坡，护栏后退，光斑流动 | 864×480 | 5.0s | FL2VA | 202611160103 | S02_first.png |
| H03 | S2 | 长下坡全景：山路连续下坡，远处谷底 | 864×480 | 5.0s | FL2VA | 202611160104 | S05_first.png |
| H04 | S2 | 轮毂与底盘：车轮旋转、悬挂轻微起伏 | 864×480 | 5.0s | FL2VA | 202611160105 | S07_first.png |
| H05 | S2 | 刹车盘红热：盘面由暗转红，热浪微微扭曲 | 864×480 | 5.0s | FL2VA | 202611160106 | S10_first.png |
| H06 | S3 | 电池包外观与 BMS 屏：冷光、线束、指示灯 | 864×480 | 5.0s | FL2VA | 202611160107 | S20_first.png |
| H07 | S4 | 刹车踏板：脚掌下压、踏板行程 | 864×480 | 5.0s | T2V | 202611160108 | — |
| H08 | S4 | 刹车盘热浪：红热区域扩大、颗粒逸出 | 864×480 | 5.0s | T2V | 202611160109 | — |
| H09 | S4 | 城市道路底图：车流稀疏，路面反光 | 864×480 | 5.0s | FL2VA | 202611160110 | S35_first.png |
| H10 | S4 | 城市车流横移：走走停停，刹车灯明灭 | 864×480 | 5.0s | FL2VA | 202611160111 | S39_first.png |
| H11 | S4 | 山路俯拍下坡：连续弯道，谷底可见（hero 候选，可选尾帧） | 864×480 | 5.0s | FL2VA | 202611160112 | S40_first.png |
| H12 | S5 | 低温霜冻路面/车窗：白霜、冷光 | 864×480 | 5.0s | FL2VA | 202611160113 | S44_first.png |
| H13 | S5 | 高速低机位跟拍：车头切风、路面高速流动（纯 H3） | 864×480 | 5.0s | FL2VA | 202611160114 | S48_first.png |
| H14 | S5 | 雨雪路面与轮胎：胎面碾过水膜，抓地环反光 | 864×480 | 5.0s | FL2VA | 202611160115 | S49_first.png |
| H15 | S5 | 湿滑路面急刹：轮速抖动、车身微沉 | 864×480 | 5.0s | FL2VA | 202611160116 | S50_first.png |
| H16 | S6 | 踏板机构：加速踏板回弹、刹车踏板待命（hero 候选，可选尾帧） | 864×480 | 5.0s | T2V | 202611160117 | — |
| H17 | S6 | 车内水杯水面：液面随减速轻晃 | 864×480 | 5.0s | T2V | 202611160118 | — |
| H18 | S6 | 城市车流（续航段）：路口多车减速 | 864×480 | 5.0s | FL2VA | 202611160119 | S56_first.png |
| H19 | S6 | 高速行驶（续航段）：匀速巡航，前景模糊 | 864×480 | 5.0s | FL2VA | 202611160120 | S57_first.png |
| H20 | S6 | 刹车片/卡钳微距：摩擦片厚度、金属光泽 | 864×480 | 5.0s | T2V | 202611160121 | — |
| H21 | S6 | 刹车盘锈蚀：盘面锈斑、边缘氧化物（纯 H3） | 864×480 | 5.0s | FL2VA | 202611160122 | S59_first.png |
| H22 | S6 | 车流跟拍（驾驶习惯段）：前车减速、距离变化（可选尾帧） | 864×480 | 5.0s | FL2VA | 202611160123 | S60_first.png |
| H23 | S7 | 城市黄昏远景：长焦压缩车流，暖光（纯 H3） | 864×480 | 5.0s | FL2VA | 202611160124 | S66_first.png |
| H24 | SPARE | 备用：充电口/插枪，充电枪插入、指示灯亮（片尾空镜/顶替） | 864×480 | 5.0s | FL2VA | 202611161100 | H24_first.png |

## H02 · 车内侧窗：长下坡，护栏后退，光斑流动

- 用途：`S1`；864×480 / 5.0s / seed 202611160103 / FL2VA/i2v（首帧锁定构图）
- 首帧：`keyframes/S02_first.png`

```text
integrated_multimodal_description:
Cinematic live-action shot from inside a car through the side window on a long downhill road, cold grey grade with moving light pools and a stable guardrail line. Animate from the locked first frame; keep its composition, camera height, lighting and colour grade unchanged. [0-2s] the guardrail posts slide past at a constant speed, sunlight shifting across the glass, a dark sleeve only at the very edge of frame; [2-5s] the lateral drift continues smoothly as the valley opens beyond the rail.
Camera: one slow lateral drift, shallow depth of field.
overall_soundscape: wind buffeting at the glass, tyre hiss on asphalt, quiet motor whine, no voice, no dialogue, no music.
No readable text, no letters, no numbers, no signs, no logos, no brand badges, no people, no human faces (only a hand or sleeve where stated), no watermark, no flicker, no strobing, no scene cuts. Keep the first frame's structure and colour palette unchanged.
```

## H03 · 长下坡全景：山路连续下坡，远处谷底

- 用途：`S2`；864×480 / 5.0s / seed 202611160104 / FL2VA/i2v（首帧锁定构图）
- 首帧：`keyframes/S05_first.png`

```text
integrated_multimodal_description:
Cinematic live-action wide aerial shot of a long mountain road descending in repeated switchbacks toward a valley, cold grey grade with teal mist in the distance, road occupying the lower two thirds. Animate from the locked first frame; keep its composition and colour grade unchanged. [0-3s] the camera tilts slowly downward following the road as it drops away; [3-5s] the tilt settles and holds on the valley floor.
Camera: one slow downward tilt, no pan, no zoom.
overall_soundscape: distant mountain wind, a faint far tyre roll, no voice, no dialogue, no music.
No readable text, no letters, no numbers, no signs, no logos, no brand badges, no people, no human faces, no watermark, no flicker, no strobing, no scene cuts. Keep the first frame's structure and colour palette unchanged.
```

## H04 · 轮毂与底盘：车轮旋转、悬挂轻微起伏

- 用途：`S2`；864×480 / 5.0s / seed 202611160105 / FL2VA/i2v（首帧锁定构图）
- 首帧：`keyframes/S07_first.png`

```text
integrated_multimodal_description:
Cinematic live-action low-angle close-up of a modern car wheel and suspension on a cold grey road, alloy rim centred, shallow depth of field. Animate from the locked first frame; keep its framing, camera height and colour grade unchanged. [0-2s] the wheel spins steadily, tread and spokes turning; [2-5s] the suspension compresses a few millimetres over road texture, dust motes drifting past.
Camera: one low tracking drift alongside the wheel.
overall_soundscape: tyre rumble on asphalt, faint motor whine, no voice, no dialogue, no music.
No readable text, no letters, no numbers, no logos on the rim, no brand badges, no people, no human faces, no watermark, no flicker, no strobing, no scene cuts. Keep the first frame's structure and colour palette unchanged.
```

## H05 · 刹车盘红热：盘面由暗转红，热浪微微扭曲

- 用途：`S2`；864×480 / 5.0s / seed 202611160106 / FL2VA/i2v（首帧锁定构图）
- 首帧：`keyframes/S10_first.png`

```text
integrated_multimodal_description:
Cinematic live-action macro close-up of a brake disc seen at a slight angle behind an alloy wheel, cold grey grade with fine metal texture, shallow depth of field. Animate from the locked first frame; keep its framing and colour grade unchanged. [0-2s] the dark metal surface slowly heats from the edges inward, turning a dull ember red; [2-5s] the red area spreads and a faint heat shimmer rises, the camera holding micro with a tiny vibration.
Camera: one nearly static micro shot with a very slight drift.
overall_soundscape: high-frequency friction hiss, the faint tick of cooling metal, no voice, no dialogue, no music.
No readable text, no letters, no numbers, no logos, no brand badges, no people, no human faces, no watermark, no flicker, no strobing, no scene cuts. Keep the first frame's structure and colour palette unchanged.
```

## H06 · 电池包外观与 BMS 屏：冷光、线束、指示灯

- 用途：`S3`；864×480 / 5.0s / seed 202611160107 / FL2VA/i2v（首帧锁定构图）
- 首帧：`keyframes/S20_first.png`

```text
integrated_multimodal_description:
Cinematic live-action close-up of a flat EV battery pack under the car on a workshop lift, cold grey grade with teal under-light and an amber practical lamp, a small BMS display glowing softly at the lower right but completely out of focus. Animate from the locked first frame; keep its composition and colour grade unchanged. [0-2s] the camera pushes in slowly across the pack casing, bolts and cooling lines catching the light; [2-5s] a few status LEDs blink once and settle, fine dust drifting in the beam.
Camera: one slow push-in across the pack, shallow depth of field.
overall_soundscape: low electrical hum, workshop room tone, a distant compressor, no voice, no dialogue, no music.
No readable text, no letters, no numbers, no digits, no labels, no UI content, no logos, no brand badges, no people, no human faces, no watermark, no flicker, no strobing, no scene cuts. Keep the first frame's structure and colour palette unchanged; any screen stays soft bokeh and never legible.
```

## H07 · 刹车踏板：脚掌下压、踏板行程

- 用途：`S4`；864×480 / 5.0s / seed 202611160108 / T2V（无关键帧降级）

```text
integrated_multimodal_description:
Cinematic live-action macro close-up of a driver's foot on a dark rubber brake pedal inside a modern car footwell, cold grey grade with soft teal ambient light, only the foot and pedal in frame. [0-2s] the foot presses the pedal down smoothly through its travel; [2-5s] it eases back up and the pedal returns a little, a faint spring motion.
Camera: one micro static shot with a very slight drift.
overall_soundscape: pedal spring motion, a soft mechanical click, quiet cabin room tone, no voice, no dialogue, no music.
No readable text, no letters, no numbers, no labels, no logos, no brand badges, no people, no human faces (only the foot and hand), no watermark, no flicker, no strobing, no scene cuts. Keep a consistent cold-grey palette and composition throughout.
```

## H08 · 刹车盘热浪：红热区域扩大、颗粒逸出

- 用途：`S4`；864×480 / 5.0s / seed 202611160109 / T2V（无关键帧降级）

```text
integrated_multimodal_description:
Cinematic live-action extreme macro close-up of a glowing brake disc surface, cold grey grade with a hot ember core, shallow depth of field. [0-2s] the red-hot area expands slowly across the metal, heat shimmer distorting the background; [2-5s] tiny sparks of dust drift upward and fade as the glow settles.
Camera: one micro static shot with a tiny drift.
overall_soundscape: friction hiss fading, a faint metallic tick, no voice, no dialogue, no music.
No readable text, no letters, no numbers, no logos, no brand badges, no people, no human faces, no watermark, no flicker, no strobing, no scene cuts. Keep a consistent cold-grey palette and composition throughout.
```

## H09 · 城市道路底图：车流稀疏，路面反光

- 用途：`S4`；864×480 / 5.0s / seed 202611160110 / FL2VA/i2v（首帧锁定构图）
- 首帧：`keyframes/S35_first.png`

```text
integrated_multimodal_description:
Cinematic live-action long-lens shot of a sparse city road in cold grey weather, wet asphalt reflecting a pale sky, road filling the lower half of frame. Animate from the locked first frame; keep its composition, lens and colour grade unchanged. [0-2s] a distant car moves away down the lane; [2-5s] the camera pans slowly to follow it while the reflections slide across the asphalt.
Camera: one slow lateral pan.
overall_soundscape: distant traffic, light tyre roll, a faint gust of wind, no voice, no dialogue, no music.
No readable text, no letters, no numbers, no signs, no readable plates, no logos, no brand badges, no people, no human faces, no watermark, no flicker, no strobing, no scene cuts. Keep the first frame's structure and colour palette unchanged.
```

## H10 · 城市车流横移：走走停停，刹车灯明灭

- 用途：`S4`；864×480 / 5.0s / seed 202611160111 / FL2VA/i2v（首帧锁定构图）
- 首帧：`keyframes/S39_first.png`

```text
integrated_multimodal_description:
Cinematic live-action side shot of city traffic at a stop-and-go pace, cold grey grade with dull wet reflections, cars in the mid-ground. Animate from the locked first frame; keep its composition and colour grade unchanged. [0-2s] the camera moves laterally with the traffic while brake lights pulse on and off; [2-5s] the flow eases forward and the red glows ripple down the line, a gentle handheld feel.
Camera: one lateral tracking move with a slight vibration.
overall_soundscape: city traffic wash, tyres on wet asphalt, a distant horn, no voice, no dialogue, no music.
No readable text, no letters, no numbers, no signs, no readable plates, no logos, no brand badges, no people, no human faces, no watermark, no flicker, no strobing, no scene cuts. Keep the first frame's structure and colour palette unchanged.
```

## H11 · 山路俯拍下坡：连续弯道，谷底可见（hero 候选，可选尾帧）

- 用途：`S4`；864×480 / 5.0s / seed 202611160112 / FL2VA/i2v（首帧锁定构图）
- 首帧：`keyframes/S40_first.png`

```text
integrated_multimodal_description:
Cinematic live-action elevated shot looking down on a winding mountain road descending toward a valley in cold grey dusk light, teal mist low in the gorge, the road forming an S shape. Animate from the locked first frame; keep its composition and colour grade unchanged. [0-2s] the camera drifts slowly forward down the slope following the switchbacks; [2-5s] it tilts gently as the road opens toward the valley floor, no cuts.
Camera: one slow forward aerial drift with a gentle tilt.
overall_soundscape: mountain wind over the ridges, a faint tyre roll far below, no voice, no dialogue, no music.
No readable text, no letters, no numbers, no signs, no logos, no brand badges, no people, no human faces, no watermark, no flicker, no strobing, no scene cuts. Keep the first frame's structure and colour palette unchanged.
```

## H12 · 低温霜冻路面/车窗：白霜、冷光

- 用途：`S5`；864×480 / 5.0s / seed 202611160113 / FL2VA/i2v（首帧锁定构图）
- 首帧：`keyframes/S44_first.png`

```text
integrated_multimodal_description:
Cinematic live-action macro close-up of frost crystals on a car window on a freezing morning, cold grey-blue grade, fine white frost patterns catching a pale light. Animate from the locked first frame; keep its framing and colour grade unchanged. [0-2s] the frost crystals glint as the light shifts across the glass and the camera drifts microscopically; [2-5s] a thin breath-like mist forms on the glass and fades, no person visible.
Camera: one micro slow drift, extremely shallow depth of field.
overall_soundscape: cold wind outside, a faint creak of metal, no voice, no dialogue, no music.
No readable text, no letters, no numbers, no signs, no logos, no brand badges, no people, no human faces, no watermark, no flicker, no strobing, no scene cuts. Keep the first frame's structure and cold palette unchanged.
```

## H13 · 高速低机位跟拍：车头切风、路面高速流动（纯 H3）

- 用途：`S5`；864×480 / 5.0s / seed 202611160114 / FL2VA/i2v（首帧锁定构图）
- 首帧：`keyframes/S48_first.png`

```text
integrated_multimodal_description:
Cinematic live-action low-angle tracking shot of a car at highway speed, cold grey grade, the road surface streaming toward camera and filling the lower two thirds of frame. Animate from the locked first frame; keep its composition, camera height and colour grade unchanged. [0-2s] the road streams toward the camera, lane markings rushing past; [2-5s] the frame vibrates slightly with speed and the car's nose holds steady against the wind.
Camera: one low tracking shot, small vibration, no pan.
overall_soundscape: strong wind roar, tyre noise, no voice, no dialogue, no music.
No readable text, no letters, no numbers, no signs, no logos, no brand badges, no people, no human faces, no watermark, no flicker, no strobing, no scene cuts. Keep the first frame's structure and colour palette unchanged.
```

## H14 · 雨雪路面与轮胎：胎面碾过水膜，抓地环反光

- 用途：`S5`；864×480 / 5.0s / seed 202611160115 / FL2VA/i2v（首帧锁定构图）
- 首帧：`keyframes/S49_first.png`

```text
integrated_multimodal_description:
Cinematic live-action macro close-up of a tyre rolling through a thin film of water on a cold asphalt road, cold grey grade with bright water highlights, shallow depth of field. Animate from the locked first frame; keep its framing and colour grade unchanged. [0-2s] the tread rolls through the water film and a fine spray lifts behind it; [2-5s] the spray settles as the wheel continues, a wet sheen sliding along the rubber.
Camera: one micro tracking drift with the wheel.
overall_soundscape: wet tyre hiss, water spray, no voice, no dialogue, no music.
No readable text, no letters, no numbers, no logos, no brand badges, no people, no human faces, no watermark, no flicker, no strobing, no scene cuts. Keep the first frame's structure and colour palette unchanged.
```

## H15 · 湿滑路面急刹：轮速抖动、车身微沉

- 用途：`S5`；864×480 / 5.0s / seed 202611160116 / FL2VA/i2v（首帧锁定构图）
- 首帧：`keyframes/S50_first.png`

```text
integrated_multimodal_description:
Cinematic live-action low shot of a car braking hard on a wet road, seen from a rear three-quarter angle, cold grey grade with mirrored reflections on the asphalt. Animate from the locked first frame; keep its composition and colour grade unchanged. [0-2s] the car nose dips and the body settles as the brakes bite; [2-5s] the wheel speed stutters in a rapid ABS rhythm and water sprays out from the tyres.
Camera: one low lateral drift alongside the car.
overall_soundscape: rapid ABS ticks, tyre scrub on wet asphalt, water spray, no voice, no dialogue, no music.
No readable text, no letters, no numbers, no signs, no logos, no brand badges, no people, no human faces, no watermark, no flicker, no strobing, no scene cuts. Keep the first frame's structure and colour palette unchanged.
```

## H16 · 踏板机构：加速踏板回弹、刹车踏板待命（hero 候选，可选尾帧）

- 用途：`S6`；864×480 / 5.0s / seed 202611160117 / T2V（无关键帧降级）

```text
integrated_multimodal_description:
Cinematic live-action macro close-up of the pedal box inside a modern EV footwell, cold grey grade with soft teal ambient light, both the accelerator and brake pedals in frame with only a foot visible. [0-2s] the accelerator pedal returns slowly upward as the toe lifts away from it; [2-5s] the foot hovers between the pedals and the brake pedal stays untouched, the camera holding micro.
Camera: one micro static shot with a tiny drift.
overall_soundscape: pedal return spring, a soft mechanical settle, quiet cabin room tone, no voice, no dialogue, no music.
No readable text, no letters, no numbers, no labels, no logos, no brand badges, no people, no human faces (only the foot and hand), no watermark, no flicker, no strobing, no scene cuts. Keep a consistent cold-grey palette and composition throughout.
```

## H17 · 车内水杯水面：液面随减速轻晃

- 用途：`S6`；864×480 / 5.0s / seed 202611160118 / T2V（无关键帧降级）

```text
integrated_multimodal_description:
Cinematic live-action close-up looking down into a cup of water in a car cup holder, cold grey grade with a soft teal reflection on the surface, shallow depth of field. [0-2s] the water surface tilts gently to one side as the car slows, the reflection sliding with it; [2-5s] it settles back level with a small slow ripple, no spill.
Camera: one very slow push-in, nearly static.
overall_soundscape: soft cabin hum, the faint tick of the cup in its holder, no voice, no dialogue, no music.
No readable text, no letters, no numbers, no logos, no brand badges, no people, no human faces (only a hand where stated), no watermark, no flicker, no strobing, no scene cuts. Keep a consistent cold-grey palette and composition throughout.
```

## H18 · 城市车流（续航段）：路口多车减速

- 用途：`S6`；864×480 / 5.0s / seed 202611160119 / FL2VA/i2v（首帧锁定构图）
- 首帧：`keyframes/S56_first.png`

```text
integrated_multimodal_description:
Cinematic live-action mid-shot of cars slowing into a city junction in cold grey daylight, wet asphalt and muted surroundings. Animate from the locked first frame; keep its composition and colour grade unchanged. [0-2s] the traffic ahead eases into the junction and brake lights ripple on; [2-5s] the camera holds while the line creeps forward and settles.
Camera: one nearly static hold with a very slow drift.
overall_soundscape: city ambience, tyre roll, a distant engine idle, no voice, no dialogue, no music.
No readable text, no letters, no numbers, no signs, no readable plates, no logos, no brand badges, no people, no human faces, no watermark, no flicker, no strobing, no scene cuts. Keep the first frame's structure and colour palette unchanged.
```

## H19 · 高速行驶（续航段）：匀速巡航，前景模糊

- 用途：`S6`；864×480 / 5.0s / seed 202611160120 / FL2VA/i2v（首帧锁定构图）
- 首帧：`keyframes/S57_first.png`

```text
integrated_multimodal_description:
Cinematic live-action long-lens shot of a car cruising at steady highway speed, cold grey grade, body occupying the left third of frame, foreground streaked by motion blur. Animate from the locked first frame; keep its composition, lens and colour grade unchanged. [0-2s] the car holds a steady speed, the foreground blurring past; [2-5s] the camera drifts gently with the car, a faint vibration through the long lens.
Camera: one gentle tracking hold with the car.
overall_soundscape: steady wind, tyre hum, no voice, no dialogue, no music.
No readable text, no letters, no numbers, no signs, no readable plates, no logos, no brand badges, no people, no human faces, no watermark, no flicker, no strobing, no scene cuts. Keep the first frame's structure and colour palette unchanged.
```

## H20 · 刹车片/卡钳微距：摩擦片厚度、金属光泽

- 用途：`S6`；864×480 / 5.0s / seed 202611160121 / T2V（无关键帧降级）

```text
integrated_multimodal_description:
Cinematic live-action extreme macro shot of a brake pad and caliper inside an alloy wheel, cold grey grade, fine metal grain and a faint amber reflection, shallow depth of field. [0-2s] the camera moves laterally across the friction material, metal highlights sliding over the surface; [2-5s] it settles on the caliper edge with a tiny drift.
Camera: one slow lateral micro move, no zoom.
overall_soundscape: a faint metallic tick, quiet workshop room tone, no voice, no dialogue, no music.
No readable text, no letters, no numbers, no logos, no brand badges, no people, no human faces, no watermark, no flicker, no strobing, no scene cuts. Keep a consistent cold-grey palette and composition throughout.
```

## H21 · 刹车盘锈蚀：盘面锈斑、边缘氧化物（纯 H3）

- 用途：`S6`；864×480 / 5.0s / seed 202611160122 / FL2VA/i2v（首帧锁定构图）
- 首帧：`keyframes/S59_first.png`

```text
integrated_multimodal_description:
Cinematic live-action macro close-up of a brake disc surface with patches of surface rust and oxidized edges, cold grey grade with dull brown-orange corrosion tones, shallow depth of field. Animate from the locked first frame; keep its framing and colour grade unchanged. [0-2s] the camera pans slowly sideways across the rust patches; [2-5s] it drifts to the disc edge as fine dust motes float in the light.
Camera: one slow lateral micro pan.
overall_soundscape: a faint metallic scrape, quiet workshop room tone, no voice, no dialogue, no music.
No readable text, no letters, no numbers, no logos, no brand badges, no people, no human faces, no watermark, no flicker, no strobing, no scene cuts. Keep the first frame's structure and colour palette unchanged.
```

## H22 · 车流跟拍（驾驶习惯段）：前车减速、距离变化（可选尾帧）

- 用途：`S6`；864×480 / 5.0s / seed 202611160123 / FL2VA/i2v（首帧锁定构图）
- 首帧：`keyframes/S60_first.png`

```text
integrated_multimodal_description:
Cinematic live-action follow shot from inside a car at dusk, looking ahead through the windshield at a lead car in the distance, cold grey grade with faint red tail lights and wet asphalt reflections. Animate from the locked first frame; keep its composition and colour grade unchanged. [0-2s] the lead car slows and the gap opens slightly; [2-5s] the camera car eases forward and the gap closes again, the wipers still.
Camera: one gentle forward hold with the traffic flow.
overall_soundscape: traffic ambience, tyre roll, a faint wiper motor hum, no voice, no dialogue, no music.
No readable text, no letters, no numbers, no signs, no readable plates, no logos, no brand badges, no people, no human faces, no watermark, no flicker, no strobing, no scene cuts. Keep the first frame's structure and colour palette unchanged.
```

## H23 · 城市黄昏远景：长焦压缩车流，暖光（纯 H3）

- 用途：`S7`；864×480 / 5.0s / seed 202611160124 / FL2VA/i2v（首帧锁定构图）
- 首帧：`keyframes/S66_first.png`

```text
integrated_multimodal_description:
Cinematic live-action long-lens shot of city traffic at dusk from a high vantage point, cold grey grade with a band of warm amber low on the horizon and car lights streaking gently. Animate from the locked first frame; keep its composition, lens and colour grade unchanged. [0-2s] the compressed traffic stream flows slowly, light streaks stretching across the frame; [2-5s] the amber band deepens as the last light fades, the camera holding still.
Camera: one slow push-in with the long lens, no pan.
overall_soundscape: distant city hum, low traffic wash, no voice, no dialogue, no music.
No readable text, no letters, no numbers, no signage, no logos, no brand badges, no people, no human faces, no watermark, no flicker, no strobing, no scene cuts. Keep the first frame's structure and colour palette unchanged.
```

## H24 · 备用：充电口/插枪，充电枪插入、指示灯亮（片尾空镜/顶替）

- 用途：`SPARE`；864×480 / 5.0s / seed 202611161100 / FL2VA/i2v（首帧锁定构图）
- 首帧：`keyframes/H24_first.png`

```text
integrated_multimodal_description:
Cinematic live-action macro close-up of an EV charging port on a dark car body at night, cold grey grade with a thin teal indicator ring glowing around the rim, water droplets on the paint, shallow depth of field. [0-2s] a charging gun slides smoothly into the port; [2-5s] the latch clicks home and the teal ring pulses once, settling to a steady glow, a soft reflection sliding over the surrounding metal.
Camera: one slow push-in toward the port, micro drift.
overall_soundscape: latch click, low electrical hum, quiet night ambience, no voice, no dialogue, no music.
No readable text, no letters, no numbers, no labels, no logos, no brand badges, no people, no human faces, no watermark, no flicker, no strobing, no scene cuts. Keep a consistent cold-grey palette throughout.
```

---

## 负向/避坑（H3 无独立 negative 输入，只能写在正向描述末尾）

- 文字/数字/LOGO/车牌必乱码：一律写 no readable text / no logos，成片逐条抽帧核查；信息一律由代码字幕与叠加层承担。
- 真人正脸不稳：只出手、背影、侧影或过肩；关键帧已锁构图时提示词只写运动。
- 声音只允许环境音/音效，禁止人声台词与配乐（配乐由代码合成）；否则两条人声打架、与母带冲突。
- 一个镜头只做一件事；运动写「物理后果」，不堆形容词；运镜一次只写一种。
- 时长与帧数：5s→124 帧@24fps（17k+5 网格），由 `140:132` 表达式自动取整。
