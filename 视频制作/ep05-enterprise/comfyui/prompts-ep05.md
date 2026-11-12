# 第 05 期 ComfyUI H3 提示词（C1–C8，T2V 5s，8 步 turbo LoRA）

> 机器可读源：`shots-ep05.json`（本文件由 `gen_prompts_md.py` 生成，勿手改）。
> 入口 `https://wp08.unicorn.org.cn:24909`（凭据只走 env `H3_USER`/`H3_PASS`，不入库）。
> 工作流 `workflows/t2v_api.json`：prompt/width/height 在 `140:131`，时长 `140:133`，
> seed `140:129`，8 步 turbo LoRA 开关 `140:139=true`，SaveVideo `92`。
> 生成规格：C1/C3 hero 1280×736，其余 864×480；5s（124 帧@24fps，约 5.167s）；
> 音轨为 H3 原生环境声（可选保留，成片按需替换）。
> 风格：cinematic 实拍质感，35/85/100mm，浅景深，teal-orange，胶片颗粒；无文字/无 logo/无正脸（只出手）。

## 分镜映射（SPEC / shots.json 锚点）

| 镜头 | 段落/锚点 | 内容 | 生成分辨率 | 时长 | seed |
| --- | --- | --- | --- | --- | --- |
| c1 | s1a / s1f / s2g / s6e | Corridor slow push-in, folder handed along | 1280×736 | 5.0s | 202611120501 |
| c2 | s1b | Hands passing a document folder, close-up | 864×480 | 5.0s | 202611120502 |
| c3 | s1c | Rubber stamp pressing onto paper, red mark lands | 1280×736 | 5.0s | 202611120503 |
| c4 | s3c | Elevator doors slide open, floor buttons light up | 864×480 | 5.0s | 202611120504 |
| c5 | s3a / s3d | Looking up through a high-rise atrium, stacked floors | 864×480 | 5.0s | 202611120505 |
| c6 | s4a | Top-down meeting table, papers and hands, no faces | 864×480 | 5.0s | 202611120506 |
| c7 | s5a | Empty office corridor, lights switch on row by row | 864×480 | 5.0s | 202611120507 |
| c8 | s2e / s6b | Venetian-blind grid of dusk light on wall and papers | 864×480 | 5.0s | 202611120508 |

## C1 · Corridor slow push-in, folder handed along

- 用途：`S1`（s1a / s1f / s2g / s6e）；生成 1280×736 / 5.0s / seed 202611120501

```text
integrated_multimodal_description:
[Shot 1] Cinematic live-action dolly shot inside a modern high-rise office corridor at dusk, 35mm lens, shallow depth of field: the camera pushes slowly forward along the corridor. On the right side of frame a slim light-grey document folder is handed from one hand to the next and travels away from camera down a line of people; only hands, shirt sleeves and a shoulder edge are in frame, no faces. Ceiling strip lights slide their reflections along the polished floor, warm desk-lamp orange against cool teal shadows, fine film grain, subtle handheld steadiness, natural motion blur.
overall_soundscape: quiet ventilation hum, soft footsteps on polished floor, the crisp rustle and faint slap of a paper folder changing hands, a distant door latch clicking.
non_diegetic_music: low sustained synth pad, sparse piano notes, restrained and slightly tense.
No readable text, no letters, no signage, no company logos, no faces, no watermark, no flicker, no strobing, no extra fingers or limbs. No people faces, no full bodies.
```

## C2 · Hands passing a document folder, close-up

- 用途：`S1`（s1b）；生成 864×480 / 5.0s / seed 202611120502

```text
integrated_multimodal_description:
[Shot 1] Cinematic extreme close-up, 85mm lens, very shallow depth of field: a hand on the left pushes a slim manila document folder across a dark wooden desk toward a hand that enters from the right; the receiving hand closes on the folder edge, fingers tightening, and draws it out of frame. Warm tungsten desk lamp from upper left, cool window light rimming the fingers, teal-orange grade, fine film grain, crisp skin texture, realistic hand physics.
overall_soundscape: soft paper and thick cardstock friction, a faint desk creak, a quiet exhale of cloth.
non_diegetic_music: single low piano note, room tone settling.
No readable text, no letters, no signage, no company logos, no faces, no watermark, no flicker, no strobing, no extra fingers or limbs.
```

## C3 · Rubber stamp pressing onto paper, red mark lands

- 用途：`S1`（s1c）；生成 1280×736 / 5.0s / seed 202611120503

```text
integrated_multimodal_description:
[Shot 1] Cinematic macro close-up, 100mm lens, shallow depth of field: a hand grips a dark wooden rubber stamp and presses it firmly down onto a sheet of paper, holds for a beat, then lifts it; a clean round red ink mark with no readable characters is left on the paper, its edges sharpening as the ink meets the paper fibres. Warm desk lamp light, cool shadow falloff on the desk, saturated red ink against warm off-white paper, floating dust motes, fine film grain, realistic paper compression and ink transfer.
overall_soundscape: a firm muffled thud as the stamp meets paper, the small wooden click of it lifting, a soft paper settling rustle.
non_diegetic_music: low cello swell, held breath.
No readable text, no letters, no signage, no company logos, no faces, no watermark, no flicker, no strobing, no extra fingers or limbs. No characters or numbers inside the stamp mark.
```

## C4 · Elevator doors slide open, floor buttons light up

- 用途：`S3`（s3c）；生成 864×480 / 5.0s / seed 202611120504

```text
integrated_multimodal_description:
[Shot 1] Cinematic interior shot facing a brushed stainless-steel elevator, 35mm lens, shallow depth of field: the elevator doors slide apart smoothly from the centre, revealing a warm-lit empty car; on the foreground panel beside the doors one round floor button lights up amber, then the next, then the next in a slow sequence. Cool fluorescent corridor light from behind camera mixes with warm amber button glow, teal-orange grade, soft reflections sliding across the metal, fine film grain, smooth mechanical motion.
overall_soundscape: a soft electric motor whirr, the metallic slide and rubber seal of opening doors, quiet relay clicks as the buttons illuminate, distant building hum.
non_diegetic_music: pulsing low synth, one note per button.
No readable text, no letters, no signage, no company logos, no faces, no watermark, no flicker, no strobing, no extra fingers or limbs. No readable floor numbers.
```

## C5 · Looking up through a high-rise atrium, stacked floors

- 用途：`S3`（s3a / s3d）；生成 864×480 / 5.0s / seed 202611120505

```text
integrated_multimodal_description:
[Shot 1] Cinematic low-angle shot looking straight up through a tall office atrium, 35mm lens: stacked floors, glass balustrades and walkways rise in layers toward a skylight, and the camera slowly tilts upward, revealing one more floor, then another, until the skylight fills the top of frame. Pale daylight from above, cool teal shadows in the concrete, warm orange light from a few lit offices, faint dust in the air, gentle lens vignette, fine film grain, smooth handheld drift.
overall_soundscape: a vast airy room tone, distant faint office murmur, a soft low whoosh of air rising.
non_diegetic_music: wide ambient pad, slow rising chord.
No readable text, no letters, no signage, no company logos, no faces, no watermark, no flicker, no strobing, no extra fingers or limbs.
```

## C6 · Top-down meeting table, papers and hands, no faces

- 用途：`S4`（s4a）；生成 864×480 / 5.0s / seed 202611120506

```text
integrated_multimodal_description:
[Shot 1] Cinematic top-down overhead shot straight down onto a long wooden meeting table, 50mm lens, shallow depth of field: sheets of paper, a slim folder and a pen lie on the table; two pairs of hands slide documents toward each other and align them, the pen rolling slightly, while the camera drifts slowly laterally above the table. Warm office ceiling light, cool shadow patches, teal-orange grade, fine film grain, subtle motion blur at the frame edges.
overall_soundscape: paper sliding on wood, a pen rolling, muffled room tone, a distant chair creak.
non_diegetic_music: sparse muted piano, even pulse.
No readable text, no letters, no signage, no company logos, no faces, no watermark, no flicker, no strobing, no extra fingers or limbs. No heads, no faces from above.
```

## C7 · Empty office corridor, lights switch on row by row

- 用途：`S5`（s5a）；生成 864×480 / 5.0s / seed 202611120507

```text
integrated_multimodal_description:
[Shot 1] Cinematic wide shot down a long empty office corridor at night, 35mm lens, deep one-point perspective: the strip lights along the ceiling switch on one by one, starting from the far end and advancing toward the camera, each panel blooming briefly before settling into steady white; the corridor floor reflects each new line of light. No people anywhere. Cool white light with warm door-frame accents, teal-orange grade, gentle atmospheric haze, fine film grain, locked-off camera with a very slow push.
overall_soundscape: a relay click and electric hum for each light switching on, receding down the corridor, then a long quiet room tone.
non_diegetic_music: ticking synth pulse, cold and minimal.
No readable text, no letters, no signage, no company logos, no faces, no watermark, no flicker, no strobing, no extra fingers or limbs. No people, no motionless static frame.
```

## C8 · Venetian-blind grid of dusk light on wall and papers

- 用途：`S2/S6`（s2e / s6b）；生成 864×480 / 5.0s / seed 202611120508

```text
integrated_multimodal_description:
[Shot 1] Cinematic close shot of a venetian blind casting a grid of hazy amber dusk light onto a pale office wall and a sheet of paper on a desk, 85mm lens, shallow depth of field: the slats shift a few degrees and the bright rectangular grid of light slides slowly across the wall and paper, sharpening and softening as it moves; dust motes drift in the beams. Warm amber sunset light from the window, deep teal shadow in the room, teal-orange grade, fine film grain, very slow drifting camera.
overall_soundscape: a soft wooden blind creak, faint evening city murmur far below, paper edge fluttering.
non_diegetic_music: warm sustained strings, quiet resolution.
No readable text, no letters, no signage, no company logos, no faces, no watermark, no flicker, no strobing, no extra fingers or limbs.
```

---

## 负向/避坑（H3 无独立 negative 输入，只能写在正向描述末尾）

- 文字、公司名、logo、工牌、楼层号、车票都必乱码：提示词里直接写 no readable text / no logos，成片仍要抽帧核查。
- 人脸不稳：全部镜头限定 hands only / no faces。
- 一个镜头只做一件事；运动变化写「物理后果」（递过去→手指收紧→抽走）。
- 音频层用 `overall_soundscape`（动作音效）与 `non_diegetic_music`（配乐）分开写。

