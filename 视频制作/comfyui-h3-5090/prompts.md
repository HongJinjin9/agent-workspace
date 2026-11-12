# 提示词库：第 04 期可用镜头（H3 视频版实测格式）

> 每条都能直接粘进 ComfyUI 的 `prompt` 输入框（T2V / 首帧 I2V 都适用）。
> 写法约定：**镜头语言 + 物理后果（为什么会动）+ 声音**；英文出片更稳，中文也实测可用。
> 不要写「4K、8K、超高清」这类空话；H3 对**运动因果**和**景别**敏感，对形容词堆砌不敏感。

## 〇、通用模板

### 0.1 官方结构化写法（推荐，模板库里就是这么写的）

H3 官方模板（`video_fastvideo_fasth3_t2v` 等）用的是**一体化多模态描述**格式，分三段：

```text
integrated_multimodal_description:
  [Shot 1] 镜头/机位 + 主体 + 这一段发生的变化
  [Shot 2] At 00:02.400, 切镜后的内容（时间码精确到毫秒）
  …
overall_soundscape: 环境声 + 关键动作音效（一段话）
non_diegetic_music: 配乐风格/节奏/情绪（一段话）
```

要点：

- **`[Shot N]` 可以写在一条 5 秒里**：`At 00:02.400,` 之后的描述会在该时间点切镜，等于一次生成里带剪辑点；
- `overall_soundscape` 单独负责**音效/环境声**，写「什么时候响什么」比堆形容词有用；
- `non_diegetic_music` 是**画外配乐**，不写就没有音乐层（只留环境声）；
- 也可以用简写版（本文下面那些单段提示词），实测同样能出片，只是**多镜头时序和声音分层不如结构化写法可控**。

> 结构化写法实测过一次：FastH3 8 步，5 秒内含 2 个镜头（测试片按仓库惯例不入库）。

### 0.2 简写模板

```text
[镜头/机位] + [主体与场景] + [这一段里发生了什么变化（物理后果）] +
[焦段/景深/色调/颗粒] + no text, no people, no watermark.
Audio: [环境声] + [关键动作音效].
```

三条硬规则：

1. **一条只做一个动作**。H3 单次 5–15 秒，动作太多会糊成一片。
2. **写清"变化"而不是"画面"**。「雨滴被甩向后方」比「下雨的挡风玻璃」有用得多。
3. **避开文字**。车牌、路牌、仪表数字都会乱码；需要文字就后期贴。

> 实测备注：9:16 竖屏把 `aspect_ratio` 设成 `9:16 (Portrait Widescreen)` 即可（见 README 测试 8）；
> 有明确起止状态的镜头，用**首尾帧双控**比纯文字可靠（见 README 测试 9）——首帧放「开始时的样子」，尾帧放「结束时的样子」，中间交给模型。

---

## 一、S1｜困惑：参数一样，感觉不一样

**S1-1 参数表与真车的并置**

```text
Cinematic side-by-side idea shot: on the left a glowing spreadsheet of car specifications floats
in dark space, on the right the same car sits on a wet road at night, its headlights illuminating
rain. Slow push-in, 50mm lens, teal-orange grading, shallow depth of field, film grain,
no readable text, no people. Audio: a low synth pad and distant rain.
```

> 提示：表格里的文字一定会乱码，**只当光斑用**，真正的参数表后期贴。

**S1-2 手抓住扶手（不出镜）**

```text
Close-up of a hand gripping a car door armrest, knuckles tightening slightly as the car goes over
a rough patch, interior at night lit by dashboard glow, 85mm lens, shallow depth of field, film
grain, no face, no text. Audio: muffled road noise, a soft leather creak.
```

---

## 二、S2｜减速带：频率与阻尼

**S2-1 积水倒影（已实测）**

```text
Cinematic live-action night shot: a dark grey sedan drives slowly over a speed bump on a wet
suburban road right after rain. Foreground: a shallow puddle on the asphalt reflecting the car
body and red tail lights; the reflection ripples outward in circular waves as the car passes,
then gradually settles. Low camera almost at ground level, 35mm lens, shallow depth of field,
teal-and-orange cinematic grading, subtle film grain, realistic physics, no text, no people
visible. Audio: one low deep thud as the wheel hits the bump, then a soft water splash and tire
hiss on wet asphalt.
```

**S2-2 对照组：阻尼不足（「咣当」）**

```text
Same shot and same road as before, but this time the car's body keeps rocking back and forth three
times after the rear wheel drops off the bump; the puddle water is thrown into a longer, messier
splash and the reflection keeps shaking. Low ground camera, 35mm lens, shallow depth of field,
teal-orange grading, film grain, realistic physics, no text, no people. Audio: a sharp clang
followed by three soft body rocks and a heavier water splash.
```

**S2-3 车轮与弹簧（结构解释的实拍质感替代）**

```text
Extreme close-up of a car wheel crossing a speed bump at night, wet asphalt, the tire compresses
and the fender dips then rebounds; water sprays out from the tread. Slow motion feel, 100mm macro
lens, shallow depth of field, rim light from a street lamp, teal-orange grading, film grain,
no text. Audio: rubber thump and water spray.
```

---

## 三、S3｜敢不敢踩：提前量

**S3-1 后视镜 · 侧倾**

```text
Cinematic shot from the driver's seat at night: the rear-view mirror fills the frame, showing the
car body and the horizon behind; the car enters a long right-hand bend at speed, the horizon in
the mirror tilts slowly and steadily, the body rolls outward, then settles as the steering unwinds.
Smooth continuous motion, no cuts, 50mm lens, shallow depth of field, dashboard glow, teal-orange
grading, film grain, no faces, no text. Audio: tire roll on asphalt, a faint wind rush rising
through the corner.
```

**S3-2 方向盘微调（第一人称）**

```text
First-person shot over a steering wheel at night: hands make small continuous corrections through
a sweeping curve, the dashboard lights reflect on the windscreen, the road ahead bends smoothly.
Handheld feel with subtle shake, 35mm lens, shallow depth of field, teal-orange grading, film
grain, no face, no text. Audio: tire hum, indicator tick, soft engine drone.
```

---

## 四、S4｜电车：jerk

**S4-1 雨滴被甩出（已实测）**

```text
Cinematic macro shot from inside a car at night: rain droplets on the windshield, out-of-focus
city lights bokeh behind. The car accelerates smoothly; the raindrops suddenly slide and streak
sideways across the glass, water beads whipping upward with the acceleration, then settle into a
slow drift as speed becomes constant. Shallow depth of field, 85mm lens, teal-orange grading,
film grain, realistic fluid physics, no people, no text. Audio: muffled rain patter on glass,
a low electric motor whine rising, a subtle water swipe.
```

**S4-2 起步瞬间的车外视角**

```text
Cinematic low tracking shot beside a dark electric sedan at night on a wet city street: the car
launches forward instantly, water sprayed up from the tires, the camera lags slightly then catches
up, street lights streak across the glossy body. 35mm lens, motion blur, teal-orange grading, film
grain, no text, no people. Audio: instant tire chirp, electric motor whine, whoosh of passing air.
```

**S4-3 副驾视角的"身体后仰"**

```text
Interior shot from the passenger seat at night, camera fixed: an empty seat with a jacket, the
scene outside the window accelerates abruptly, the jacket slides back into the seat, dashboard
lights flicker across the windscreen. 35mm lens, shallow depth of field, film grain, no people,
no text. Audio: electric motor rising, a soft fabric rustle.
```

---

## 五、S5｜收束：身体记忆

**S5-1 心电图式三线合流（建议程序化，不用生成）**

> 三条曲线必须与数学函数严格对应，生成模型会把曲线"画飘"。这一条**留给 PIL/numpy**，H3 只负责它的背景（暗场里的车窗光斑）。

**S5-2 停车后的静默**

```text
Static cinematic night shot: a dark sedan parked on a wet suburban street after rain, engine off,
rain dripping from the roof rack, the puddle beside it perfectly still and mirror-like, street
lamp glow on the bonnet. 50mm lens, shallow depth of field, teal-orange grading, film grain,
no text, no people. Audio: sparse dripping water, distant city hum, one car passing far away.
```

---

## 六、通用"氛围 B-roll"（可批量生成，补空镜）

| 用途 | 提示词要点 |
| --- | --- |
| 雨夜车窗 | `rain streaks on a car window at night, city bokeh, slow drift, 85mm, shallow DOF` |
| 轮胎特写 | `tire rolling through shallow water, spray, 100mm macro, backlit by headlights` |
| 仪表盘 | `dashboard glow at night, needles moving, no readable numbers, 50mm, shallow DOF` |
| 路面水膜 | `wet asphalt reflecting street lights, slow dolly, no cars, no people` |
| 减速带空镜 | `empty speed bump on a wet road at night, street lamp, slow push-in, film grain` |

---

## 七、负向清单（写进 prompt 末尾）

```text
no text, no watermark, no logo, no license plate characters, no faces, no extra limbs,
no flicker, no jitter
```

> H3 没有独立的 negative prompt 输入；负向要求只能写在正向描述末尾，或用工作流里的 `MiniMaxH3AddGuide` 约束关键帧。
