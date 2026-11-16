#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 08 期 H3 交接包生成器（engine-dev，冻结版场景设计 §5/§6）。

产出（其余 comfyui/ 下文件归 h3-operator）：
  1) comfyui/keyframes/<Sxx>_first.png（+ H24_first.png 备用）—— FL2VA/T2V 首帧
  2) comfyui/shots-ep08.json —— H3 工单：id=H01..H24、shot=Sxx、首帧路径、prompt、
     seed/宽高/时长/workflow/fallback（h3-operator 按 shot=Sxx 回传 assets/h3/Sxx.mp4）

首帧来源：已授权 Pexels 视频抽帧 / Pexels Photos 静图（fetch_pexels_keyframes.py）；
无干净素材的镜 → first_frame=null（T2V 自动降级，prompt 含完整场景描述）。
首帧一律冷灰影调、16:9、无文字/UI/黑边/logo/人脸/可读车牌。

用法：python3 gen_h3_pack.py [--check] [--only H01,S01]
"""
import argparse, json, os, re, subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
FFMPEG = "/home/admin/.local/bin/ffmpeg"
KEYDIR = os.path.join(ROOT, "comfyui", "keyframes")
JOBFILE = os.path.join(ROOT, "comfyui", "shots-ep08.json")
SRCINFO = os.path.join(ROOT, "work", "h3-keyframes.json")
PEXELS_DIR = os.path.join(ROOT, "assets", "pexels", "keyframes")
STOCK_DIRS = ["/app/vedio/ep04-body/assets/stock", "/app/vedio/ep01-hybrid/assets/stock",
              "/app/vedio/ep02-flood/assets/stock", "/app/vedio/ep03-judgment/assets/stock"]

GRADE = ("eq=contrast=1.07:brightness={b}:saturation={s}:gamma={g},"
         "colorbalance=rs=-0.075:gs=-0.018:bs=0.12:rh=0.02:bh=-0.065,"
         "vignette=PI/4.6,noise=alls=5:allf=t+u")
SIZES = {"hero": (1280, 736), "standard": (864, 480)}

def log(*a): print("[h3pack] " + " ".join(str(x) for x in a), flush=True)

# id / shot / seg / 内容 / 时间锚 / 首帧来源 / prompt（按 PDF §4.1：分阶段、一次运镜、声音显式）
# stock=[文件, 秒, 取景中心]；photo=静图文件名；None=T2V
SHOTS = [
 dict(id="H02", shot="S02", seg="S1", hero=False, title="车内侧窗：长下坡，护栏后退、光斑流动",
      md="S02 0:04.64-0:07.11", src=("stock", "steering_night.mp4", 2.2),
      prompt="From the first frame, [0-5s] lateral camera drift along the side window; guardrail posts slide by at constant speed, street-light pools sweep across the glass. Sound: wind buffeting, tyre hiss, quiet motor whine. No text, no numbers, no logos, no faces; keep the palette and framing."),
 dict(id="H03", shot="S05", seg="S2", hero=False, title="长下坡全景：连续下坡，远处谷底",
      md="S05 0:15.31-0:17.55", src=("stock", "winding_road_03.mp4", 2.0),
      prompt="From the first frame, [0-3s] slow downward tilt following the mountain road; [3-5s] hold the wide valley view. Sound: distant wind over ridges, faint tyre roll far below. No text, no road signs, no logos, no faces; keep horizon angle and palette."),
 dict(id="H04", shot="S07", seg="S2", hero=False, title="轮毂与底盘：车轮旋转、悬挂轻微起伏",
      md="S07 0:21.39-0:24.77", src=("photo", "S07.jpg"),
      prompt="From the first frame, [0-5s] wheel spins steadily, suspension compresses slightly over road texture, dust motes drift in the side light; camera low and steady. Sound: tyre rumble, faint motor whine changing pitch. No text, no readable logos, no faces; keep framing."),
 dict(id="H05", shot="S10", seg="S2", hero=False, title="刹车盘红热：暗金属转红、热浪扭曲",
      md="S10 0:31.31-0:35.15", src=("photo", "S10.jpg"),
      prompt="From the first frame, [0-5s] the brake disc heats: dark metal turns dull red from the edge inward, heat shimmer rising; camera holds micro, very shallow depth of field. Sound: high-frequency friction, faint tick of cooling metal. No text, no logos, no faces; keep composition."),
 dict(id="H06", shot="S20", seg="S3", hero=False, title="电池包外观与 BMS 屏：冷光、线束、指示灯",
      md="S20 1:07.83-1:10.98", src=("photo", "S20.jpg"),
      prompt="From the first frame, [0-5s] slow push-in on the high-voltage battery components; a few status LEDs blink in sequence, thin cables curving out of frame, dust in the air. Sound: low electrical hum, one relay click. No readable text on any screen, no logos, no faces; keep palette."),
 dict(id="H07", shot="S25", seg="S4", hero=False, title="刹车踏板：脚掌下压、踏板行程",
      md="S25 1:28.80-1:31.05", src=None,
      prompt="Cinematic live-action close-up of a single dark brake pedal in a modern EV footwell at night, cold grey grade, one soft teal ambient light, dark carpet texture. [0-2s] the foot presses the pedal down smoothly and holds; [2-5s] it eases back slightly and the pedal returns a centimetre, shallow depth of field. Camera: micro shot on the pedal, one slow lateral drift. overall_soundscape: pedal spring, soft mechanism click, quiet cabin tone, no voice, no music. No text, no readable labels, no logos, no faces, no watermark, no flicker."),
 dict(id="H08", shot="S30", seg="S4", hero=False, title="刹车盘热浪：红热区域扩大、颗粒逸出",
      md="S30 1:44.37-1:47.98", src=None,
      prompt="Cinematic live-action extreme close-up of a brake disc glowing red-hot at night, cold grey grade with the red heat the only strong colour, heat shimmer rising. [0-2s] the disc edge glows dull red and the glow creeps inward; [2-5s] the red spreads across the friction surface, fine dust and sparks drift upward, air distorting. Camera: micro static shot with a very slow push-in, extremely shallow depth of field. overall_soundscape: high-frequency brake squeal, crackle of hot metal, faint hiss, no voice, no music. No text, no logos, no faces, no watermark, no flicker."),
 dict(id="H09", shot="S35", seg="S4", hero=False, title="城市道路底图：车流稀疏、路面反光",
      md="S35 2:02.87-2:06.03", src=("stock", "wet_road_night_01.mp4", 2.0),
      prompt="From the first frame, [0-5s] slow lateral pan following a distant car; wet asphalt reflects the sky and lights, sparse traffic. Sound: distant traffic wash, wet tyre hiss. No text, no readable plates, no logos, no faces; keep framing."),
 dict(id="H10", shot="S39", seg="S4", hero=False, title="城市车流横移：走走停停、刹车灯明灭",
      md="S39 2:17.08-2:20.24", src=("stock", "wet_road_night_01.mp4", 6.0),
      prompt="From the first frame, [0-5s] lateral camera move beside city traffic; cars slow and stop in sequence, brake lights pulsing, slight handheld feel. Sound: city traffic, occasional distant horn (no voice). No text, no readable plates, no logos, no faces; keep palette."),
 dict(id="H11", shot="S40", seg="S4", hero=False, title="山路俯拍下坡：连续弯道、谷底可见",
      md="S40 2:20.24-2:25.89", src=("stock", "winding_road_01.mp4", 4.5),
      prompt="From the first frame, [0-5s] slow forward drift down the mountain slope, camera tilting gently with the road; S-shaped switchbacks below, valley haze. Sound: mountain wind, distant tyre roll. No text, no road signs, no logos, no faces; keep road geometry and palette."),
 dict(id="H12", shot="S44", seg="S4", hero=False, title="低温霜冻路面/车窗：白霜、冷光",
      md="S44 2:39.87-2:45.95", src=("photo", "S44.jpg"),
      prompt="From the first frame, [0-5s] frost crystals glint as the light shifts, camera drifting micro; a breath-like mist crosses the glass, no person appears. Sound: cold wind, faint creak of cold materials. No text, no logos, no faces; keep cold palette."),
 dict(id="H13", shot="S48", seg="S4", hero=False, title="高速低机位跟拍：车头切风、路面高速流动",
      md="S48 2:55.87-3:00.16", src=("stock", "night_driving_02.mp4", 2.0),
      prompt="From the first frame, [0-5s] low tracking shot alongside the car; road surface streams toward camera, slight vibration, spray lifting from the front tyres. Sound: strong wind, tyre roar, faint motor whine. No text, no readable plates, no logos, no faces; keep speed feel."),
 dict(id="H14", shot="S49", seg="S4", hero=False, title="雨雪路面与轮胎：胎面碾过水膜",
      md="S49 3:00.16-3:02.18", src=("photo", "S49.jpg"),
      prompt="From the first frame, [0-5s] the tyre rolls through a thin water film, spray rising in slow sheets, camera micro and low. Sound: wet tyre hiss, water spray. No text, no logos, no faces; keep palette."),
 dict(id="H15", shot="S50", seg="S4", hero=False, title="湿滑路面急刹：轮速抖动、车身微沉",
      md="S50 3:02.18-3:06.02", src=("stock", "wet_road_night_02.mp4", 4.2),
      prompt="From the first frame, [0-5s] hard braking on the wet road: the body dips, the view judders slightly with rapid wheel-speed stutter, water sprays outward. Sound: rapid ABS-like ticks, tyre scrub, water. No text, no readable plates, no logos, no faces; keep framing."),
 dict(id="H16", shot="S53", seg="S5", hero=False, title="踏板机构：加速踏板回弹、刹车踏板待命",
      md="S53 3:14.83-3:20.91", src=None,
      prompt="Cinematic live-action close-up of a single dark accelerator pedal in a modern EV footwell, cold grey grade with soft teal ambient light, dark carpet texture. [0-2s] the pedal is pressed slightly with a foot resting on it; [2-5s] the toe eases off and the pedal returns upward with a soft spring motion while the foot hovers, the brake pedal untouched at the edge of frame. Camera: micro shot, one very slow lateral drift. overall_soundscape: pedal return spring, soft click, quiet cabin tone, no voice, no music. No text, no readable labels, no logos, no faces, no watermark, no flicker."),
 dict(id="H17", shot="S55", seg="S5", hero=False, title="车内水杯水面：液面随减速轻晃",
      md="S55 3:24.06-3:27.22", src=None,
      prompt="Cinematic live-action macro close-up of a cup of water resting in a car centre console at night, cold grey grade with teal instrument glow and a faint amber reflection, shallow depth of field. [0-2s] the water surface is almost still in the cup holder; [2-5s] the car eases to a smooth stop and the surface tilts gently then settles, one ripple crossing the water without spilling. Camera: one very slow push-in on the cup rim, extremely shallow depth of field. overall_soundscape: quiet cabin tone, faint motor whine fading, soft water ripple, no voice, no music. No text, no readable labels, no logos, no faces, no watermark, no flicker."),
 dict(id="H18", shot="S56", seg="S5", hero=False, title="城市车流（续航段）：路口多车减速",
      md="S56 3:27.22-3:29.92", src=("stock", "city_night_aerial.mp4", 1.8),
      prompt="From the first frame, [0-5s] traffic slows into the junction, brake lights rippling across the lanes; camera holds a mid-wide view. Sound: city ambience, distant engine wash. No text, no readable plates, no logos, no faces; keep palette."),
 dict(id="H19", shot="S57", seg="S5", hero=False, title="高速行驶（续航段）：匀速巡航、前景模糊",
      md="S57 3:29.92-3:32.62", src=("stock", "steering_night.mp4", 5.2),
      prompt="From the first frame, [0-5s] steady highway cruise, foreground light streaks blurring past, camera gentle and stable. Sound: steady wind and tyre hum, low motor whine. No text, no readable signs, no logos, no faces; keep speed feel."),
 dict(id="H20", shot="S58", seg="S5", hero=False, title="刹车片/卡钳微距：摩擦片厚度、金属光泽",
      md="S58 3:32.62-3:36.91", src=None,
      prompt="Cinematic live-action macro close-up through the spokes of an alloy wheel at a brake caliper and brake pad, cold grey grade, teal rim light, metal highlights. [0-2s] the camera holds on the caliper with the pad thickness visible inside; [2-5s] one slow lateral micro move reveals the pad surface and disc edge, fine dust in the air. Camera: micro lateral drift, extremely shallow depth of field. overall_soundscape: faint metallic tick, quiet workshop room tone, no voice, no music. No text, no readable logos, no faces, no watermark, no flicker."),
 dict(id="H21", shot="S59", seg="S5", hero=False, title="刹车盘锈蚀：盘面锈斑、边缘氧化物",
      md="S59 3:36.91-3:40.06", src=("photo", "S59.jpg"),
      prompt="From the first frame, [0-5s] micro lateral pan across rust patches on the brake disc, orange oxide creeping over the friction surface, dust motes drifting. Sound: faint metallic scrape, quiet room tone. No text, no logos, no faces; keep palette."),
 dict(id="H22", shot="S60", seg="S5", hero=False, title="车流跟拍（驾驶习惯）：前车减速、距离变化",
      md="S60 3:40.06-3:43.45", src=("stock", "wet_road_night_01.mp4", 9.0),
      prompt="From the first frame, [0-5s] follow shot behind a lead car; it slows and the gap opens, then closes gently as our car eases off; camera soft and handheld-light. Sound: traffic ambience, wet tyre roll. No text, no readable plates, no logos, no faces; keep framing."),
 dict(id="H23", shot="S66", seg="S6", hero=False, title="城市黄昏远景：长焦压缩车流，暖光",
      md="S66 4:00.81-4:05.33", src=("stock", "city_night_aerial.mp4", 3.2),
      prompt="From the first frame, [0-5s] long-lens compression of the city at dusk; car lights streak slowly along the roads, warm haze thickening. Sound: distant city hum, no voice. No text, no readable signage, no logos, no faces; keep palette."),
 dict(id="H24", shot="SPARE", seg="SPARE", hero=False, spare=True,
      title="备用：充电口/插枪：充电枪插入、指示灯亮",
      md="SPARE 备用镜（可顶替失败镜/片尾空镜）", src=("photo", "H24.jpg"),
      prompt="From the first frame, [0-5s] the charging gun slides into the port, a thin ring of indicator light pulses once and settles; camera micro on the connector, water droplets on paint. Sound: latch click, low electrical hum. No text, no readable labels, no logos, no faces; keep framing."),
]

def find_stock(name):
    for d in STOCK_DIRS:
        p = os.path.join(d, name)
        if os.path.isfile(p) and os.path.getsize(p) > 50000:
            return p
    return None

def probe_duration(path):
    r = subprocess.run([FFMPEG, "-hide_banner", "-i", path], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", r.stderr or "")
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0

def grade_for(mean):
    if mean < 0.055:   return 0.185, 1.32, 0.50
    if mean < 0.10:    return 0.12, 1.15, 0.48
    if mean < 0.20:    return 0.03, 1.00, 0.42
    return -0.115, 0.85, 0.34

def _size(shot): return SIZES["hero" if shot.get("hero") else "standard"]

def render_keyframe(shot):
    if not shot.get("src"):
        return None
    kind = shot["src"][0]
    if kind not in ("stock", "photo", "code"):
        return None
    w, h = _size(shot)
    out = os.path.join(KEYDIR, _fname(shot))
    os.makedirs(KEYDIR, exist_ok=True)
    base = "scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,setsar=1" % (w, h, w, h)
    if kind == "code":
        import keyframe_art
        im = keyframe_art.render(shot["src"][1], (w, h))
        im.save(out)
        from PIL import Image
        import numpy as np
        a = np.asarray(Image.open(out).convert("RGB"), np.float32) / 255.0
        return out, {"shot": shot["shot"], "source": "keyframe_art/" + shot["src"][1],
                     "license": "procedural (code-layer)", "size": [w, h],
                     "source_mean": None, "final_mean": round(float(a.mean()), 4),
                     "grade": {"note": "code-rendered composition, no readable text"}}
    if kind == "photo":
        src = os.path.join(PEXELS_DIR, shot["src"][1])
        if not os.path.isfile(src):
            log("!! 静图缺失", shot["id"], shot["src"][1]); return None
        t = 0.0
    else:
        name, t = shot["src"][1], float(shot["src"][2])
        src = find_stock(name)
        if not src:
            log("!! 素材缺失", shot["id"], name); return None
        t = max(0.05, min(t, max(0.05, probe_duration(src) - 0.1)))
    tmp = out + ".raw.png"
    pre = [] if kind == "photo" else ["-ss", "%.3f" % t]
    r = subprocess.run([FFMPEG, "-v", "error", "-y", "-threads", "1"] + pre +
                       ["-i", src, "-frames:v", "1", "-vf", base, "-pix_fmt", "rgb24", tmp],
                       capture_output=True, text=True)
    if r.returncode != 0 or not os.path.isfile(tmp):
        log("!! 抽帧失败", shot["id"], (r.stderr or "")[-240:]); return None
    from PIL import Image
    import numpy as np
    a = np.asarray(Image.open(tmp).convert("RGB"), np.float32) / 255.0
    mean = float(a.mean())
    b, g, s = grade_for(mean)
    grade = GRADE.format(b=b, s=s, g=g)
    r = subprocess.run([FFMPEG, "-v", "error", "-y", "-threads", "1"] + pre +
                       ["-i", src, "-frames:v", "1", "-vf", base + "," + grade,
                        "-pix_fmt", "rgb24", out], capture_output=True, text=True)
    try: os.remove(tmp)
    except OSError: pass
    if r.returncode != 0 or not os.path.isfile(out):
        log("!! 出图失败", shot["id"], (r.stderr or "")[-240:]); return None
    if shot["id"] in BLUR:
        apply_blur(out, BLUR[shot["id"]])
    a = np.asarray(Image.open(out).convert("RGB"), np.float32) / 255.0
    return out, {"shot": shot["shot"], "source": src, "source_t": round(t, 3),
                 "license": "Pexels License", "size": [w, h],
                 "source_mean": round(mean, 4), "final_mean": round(float(a.mean()), 4),
                 "grade": {"brightness": b, "gamma": g, "saturation": s}}

# 首帧上若存在会被 H3 糊成乱码的可读文字/UI/logo，用代码高斯模糊遮掉（首帧允许代码做的构图处理）
BLUR = {
    "H24": [(0.00, 0.00, 1.00, 0.20)],          # 车身可能的品牌标
    "S07": [(0.52, 0.00, 1.00, 0.42)],          # 车头品牌徽标/车型特征
    "S20": [(0.00, 0.00, 0.80, 0.60), (0.00, 0.45, 0.60, 1.00)],   # 部件小标签
}


def apply_blur(path, boxes, radius=14):
    from PIL import Image, ImageFilter
    im = Image.open(path).convert("RGB")
    w, h = im.size
    for (x0, y0, x1, y1) in boxes:
        box = (int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h))
        if box[2] <= box[0] or box[3] <= box[1]:
            continue
        patch = im.crop(box).filter(ImageFilter.GaussianBlur(radius))
        im.paste(patch, box)
    im.save(path)


def _fname(shot):
    return ("H24_first.png" if shot.get("spare") else shot["shot"] + "_first.png")

def validate_frame(path, shot):
    from PIL import Image
    import numpy as np
    im = Image.open(path).convert("RGB"); a = np.asarray(im, np.float32) / 255.0
    w, h = im.size; want = _size(shot)
    ok = (w, h) == want and 0.045 < float(a.mean()) < 0.34 and float(a.std()) > 0.03
    return ok, {"size": [w, h], "mean": round(float(a.mean()), 4), "std": round(float(a.std()), 4)}

def _seg_for(shot_id):
    """音频时间轴 7 段：S1 冷开场 / S2 立判 / S3 拆解 / S4 能量账 / S5 限制 / S6 再判 / S7 收束。"""
    if shot_id == "SPARE":
        return "SPARE"
    n = int(shot_id[1:])
    if n <= 4:  return "S1"
    if n <= 13: return "S2"
    if n <= 24: return "S3"
    if n <= 41: return "S4"
    if n <= 52: return "S5"
    if n <= 65: return "S6"
    return "S7"


def build_job(shot):
    w, h = _size(shot)
    key = os.path.join(KEYDIR, _fname(shot))
    has = bool(shot.get("src")) and os.path.isfile(key)
    j = {"id": shot["id"], "shot": shot["shot"], "seg": _seg_for(shot["shot"]),
         "title": shot["title"], "md": shot["md"], "width": w, "height": h,
         "duration": 5.0,
         "seed": 202611160101 + (999 if shot.get("spare") else int(shot["id"][1:])),
         "prompt": shot["prompt"],
         "mode": "FL2VA" if has else "T2V",
         "first_frame": ("keyframes/" + _fname(shot)) if has else None,
         "last_frame": None, "hero": bool(shot.get("hero")),
         "fallback": shot.get("fallback", "code")}
    if shot.get("spare"): j["spare"] = True
    return j

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--only", default=None)
    a = ap.parse_args()
    only = set(x.strip() for x in a.only.split(",")) if a.only else None
    os.makedirs(KEYDIR, exist_ok=True); os.makedirs(os.path.dirname(SRCINFO), exist_ok=True)
    srcinfo = {}
    if os.path.isfile(SRCINFO):
        try: srcinfo = json.load(open(SRCINFO, encoding="utf-8"))
        except Exception: srcinfo = {}
    fails = []
    for shot in SHOTS:
        if only and shot["id"] not in only and shot["shot"] not in only:
            continue
        key = os.path.join(KEYDIR, _fname(shot))
        if not a.check or not os.path.isfile(key):
            if shot.get("src") and shot["src"][0] in ("stock", "photo", "code"):
                res = render_keyframe(shot)
                if res:
                    srcinfo[shot["id"]] = res[1]
                    log("key", shot["id"], "→", _fname(shot), "←",
                        os.path.basename(res[1]["source"]),
                        ("@%.2fs" % res[1]["source_t"]) if "source_t" in res[1] else "")
            else:
                log("T2V", shot["id"], "first_frame=null")
        if os.path.isfile(key):
            ok, info = validate_frame(key, shot)
            log("chk", shot["id"], "OK" if ok else "FAIL", info)
            if not ok: fails.append((shot["id"], info))
    if only:
        return 1 if fails else 0
    jobs = {"series": "ep08-regen", "created_utc": "2026-11-16T11:05:00Z",
            "workflow": "workflows/t2v_api.json",
            "style": ("cinematic live-action, cold grey #0e1216 + paper white #e9e4d8 + energy "
                      "teal #2fd3c5 accent, film grain, no text/logos/faces"),
            "note": "id=设计稿 H 编号；shot=Sxx 为 timeline 镜号，h3-operator 按 shot 命名回传 assets/h3/Sxx.mp4",
            "defaults": {"width": 864, "height": 480, "duration": 5.0, "steps": 8, "fps": 24,
                         "enable_lightning_lora": True},
            "shots": [build_job(s) for s in SHOTS]}
    json.dump(jobs, open(JOBFILE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(srcinfo, open(SRCINFO, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    n = sum(1 for s in jobs["shots"] if s["first_frame"])
    log("工单写入", JOBFILE, "(%d shots, %d with first_frame)" % (len(jobs["shots"]), n))
    if fails: log("FAIL:", fails); return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
