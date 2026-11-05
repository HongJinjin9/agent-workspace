#!/usr/bin/env python3
"""Cinematic remake of the Vibe speech video.

Pipeline:
  1. edge-tts narration for 12 beats (male cinematic voice)
  2. shot clips: AI-generated stills (Ken Burns / pan) + Pexels stock footage
  3. hard-cut montage on beat, 2.35:1 letterbox, teal-orange grade, film grain,
     animated kinetic typography + light flashes (ASS/libass)
  4. sound design: narration + cinematic BGM + whooshes/riser/impacts
  5. final 1920x1080 24fps H.264 delivery + verification frames

Usage:
  python3 build.py [--render-only] [--fresh]
"""
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
A = lambda *p: os.path.join(ROOT, "assets", *p)
W = lambda *p: os.path.join(ROOT, "work", *p)
OUT = os.path.join(ROOT, "out")
FRAMES = os.path.join(ROOT, "frames")
FFMPEG = "/home/admin/.local/bin/ffmpeg"
FFPROBE = "/tmp/vstudio-media/bin/ffprobe"
EDGE_TTS = "/home/admin/.local/bin/edge-tts"
FONTS_DIR = "/home/admin/.fonts"

WIDTH, HEIGHT, FPS = 1920, 1080, 24
BAR = 132  # 2.35:1 letterbox: (1080 - 2*132) / 1920 = 2.35
GAP = 0.40
GAP_AFTER = [0.40, 0.40, 0.40, 0.40, 0.90, 0.40, 0.40, 0.40, 0.40, 0.40, 0.60, 0.40]
LEAD = 0.60
OUTRO = 2.6

VOICE = "zh-CN-YunxiNeural"
RATE = "+8%"

BEATS = [
    ("2026 年，不会写代码的人，正在用「感觉」编程。"),
    ("而你，可能已经是个 vibe coder 了，只是还不知道。"),
    ("Vibe Coding，中文叫「氛围编程」——你不再需要写代码，只需要告诉 AI，你想要什么。"),
    ("代码，从「必须掌握的技能」，变成了「可以描述的感觉」。"),
    ("知识也一样：记忆在贬值，提问在升值。"),
    ("但这不是乌托邦。门槛降低了，不等于人人成功。"),
    ("以前是「技术壁垒」挡着你，现在是「品味壁垒」卡着你。描述力、判断力、察觉力，成了新的稀缺资源。"),
    ("所以 2026 年，普通人要练三件事：练描述力，练判断力，练跨界力。"),
    ("技术可以外包，但「你觉得什么是对的」，永远外包不了。"),
    ("最大的风险，不是被 AI 取代，而是失去自己的感觉。"),
    ("消费者永远被收割，创作者才有定价权。"),
    ("今天，试着用你的感觉，让 AI 帮你做一件小事。那个「不满意」的瞬间，就是你作为创作者的起点。"),
]

# shot: id, asset, kind, beat index, split fraction (of beat span), overlay spec
SHOTS = [
    dict(id="s01", asset="stock/city-night", kind="stock", beat=0, split=None,
         texts=[("hero", 0.35, "2026", "accent"), ("hero", 0.45, "不会写代码的人", "white"),
                ("hero", 0.55, "正在用「感觉」编程", "white")], flash=False),
    dict(id="s02", asset="stock/phone-dark", kind="stock", beat=1, split=None,
         texts=[("hero", 0.30, "你可能已经是个", "white"), ("hero", 0.40, "vibe coder", "accent"),
                ("caption", 0.55, "只是你还不知道", "white")], flash=True),
    dict(id="s03", asset="ai/abstract-network", kind="still", beat=2, split=0.52,
         texts=[("kicker", 0.15, "01 / VIBE CODING", "accent"), ("hero", 0.25, "Vibe Coding", "white"),
                ("caption", 0.45, "氛围编程 · 直觉编程", "white")], chapter="01 / VIBE CODING"),
    dict(id="s04", asset="stock/tech-abstract", kind="stock", beat=2, split=0.48,
         texts=[("hero", 0.20, "不用写代码", "white"), ("hero", 0.30, "只要告诉 AI 你想要什么", "accent")], flash=True),
    dict(id="s05", asset="stock/night-work", kind="stock", beat=3, split=None,
         texts=[("hero", 0.20, "从「必须掌握的技能」", "white"), ("hero", 0.35, "到「可以描述的感觉」", "accent")], flash=False),
    dict(id="s06", asset="stock/coffee", kind="stock", beat=4, split=0.55,
         texts=[("hero", 0.20, "记忆贬值", "white"), ("hero", 0.32, "提问升值", "accent")], flash=True),
    dict(id="s07", asset="stock/camera", kind="stock", beat=4, split=0.45,
         texts=[("hero", 0.22, "学 3 年摄影", "white"), ("caption", 0.40, "现在只要「知道什么算好」", "white")], flash=False),
    dict(id="s08", asset="ai/door-light", kind="still", beat=5, split=0.48,
         texts=[("kicker", 0.15, "02 / THE HARD TRUTH", "accent"), ("hero", 0.25, "但这不是乌托邦", "white")], chapter="02 / THE HARD TRUTH"),
    dict(id="s09", asset="stock/crowd", kind="stock", beat=5, split=0.52,
         texts=[("hero", 0.18, "门槛降低", "white"), ("hero", 0.30, "≠ 人人成功", "accent")], flash=True),
    dict(id="s10", asset="ai/barrier", kind="still", beat=6, split=0.46,
         texts=[("hero", 0.20, "技术壁垒 → 品味壁垒", "accent")], flash=False),
    dict(id="s11", asset="ai/three-pillars", kind="still", beat=6, split=0.54,
         texts=[("hero", 0.18, "描述力", "white"), ("hero", 0.28, "判断力", "accent"),
                ("hero", 0.38, "察觉力", "white"), ("caption", 0.55, "新的稀缺资源", "white")], flash=True),
    dict(id="s12", asset="ai/creator-desk", kind="still", beat=7, split=None,
         texts=[("hero", 0.18, "2026，练三件事", "white"),
                ("caption", 0.42, "描述力 · 判断力 · 跨界力", "accent")], flash=False),
    dict(id="s13", asset="ai/hand-ai", kind="still", beat=8, split=None,
         texts=[("hero", 0.18, "技术可以外包", "white"), ("hero", 0.34, "「什么是对的」", "accent"),
                ("hero", 0.46, "外包不了", "white")], flash=True),
    dict(id="s14", asset="ai/eye", kind="still", beat=9, split=None, hero_base=760,
         texts=[("hero", 0.22, "最大的风险", "white"), ("hero", 0.34, "是失去自己的感觉", "accent")], flash=True),
    dict(id="s15a", asset="stock/crowd", kind="stock", beat=10, split=0.5,
         texts=[("hero", 0.18, "消费者永远被收割", "white")], flash=True),
    dict(id="s15b", asset="stock/window-night", kind="stock", beat=10, split=0.5,
         texts=[("hero", 0.22, "创作者才有定价权", "accent")], flash=False),
    dict(id="s16", asset="stock/sunrise", kind="stock", beat=11, split=0.55,
         texts=[("hero", 0.20, "今天，做一件小事", "white"), ("caption", 0.42, "用你的感觉，让 AI 帮你完成", "white")], flash=False),
    dict(id="s17", asset="ai/city-future", kind="still", beat=11, split=0.45,
         texts=[("end", 0.28, "那个「不满意」的瞬间", "white"), ("end", 0.42, "就是你作为创作者的起点", "accent"),
                ("credit", 0.62, "《Vibe 时代的生活革命》· 发言稿 Nova · 视频 VCP 视听 出品", "muted"),
                ("credit", 0.74, "点赞 · 关注，一起做 Vibe 时代的创作者", "muted")], flash=True, tail=2.6),
]

FALLBACKS = {
    "stock/city-night": ["ai/city-future"],
    "stock/tech-abstract": ["ai/abstract-network"],
    "stock/night-work": ["ai/creator-desk"],
    "stock/coffee": ["ai/door-light"],
    "stock/camera": ["ai/hand-ai"],
    "stock/crowd": ["ai/barrier"],
    "stock/walk-street": ["stock/crowd", "ai/city-future"],
    "stock/sunrise": ["stock/city-night"],
}
def ass_color(hex_rgb):
    h = hex_rgb.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"&H00{b:02X}{g:02X}{r:02X}&"

ACCI = {
    "white": ass_color("#F8FAFC"),
    "muted": ass_color("#9AA7B8"),
}
# accent color per section: teal -> amber -> pink -> purple -> warm gold
SECTION_ACCENTS = ["#67E8F9", "#FBBF24", "#F472B6", "#A78BFA", "#FDE68A"]


def log(*a):
    line = "[" + __import__("datetime").datetime.now().strftime("%H:%M:%S") + "] " + " ".join(str(x) for x in a)
    print(line)
    open(os.path.join(ROOT, "build.log"), "a").write(line + "\n")


def run(cmd, quiet=True):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("cmd failed: " + " ".join(cmd)[:400] + "\n" + (r.stderr or "")[-1200:])
    return r


def probe(path):
    out = subprocess.run([FFMPEG, "-hide_banner", "-i", path], capture_output=True, text=True).stderr
    dur = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", out)
    vid = re.search(r"Video: .*?, (\d+)x(\d+)", out)
    fps = re.search(r"(\d+(?:\.\d+)?) fps", out)
    return {
        "duration": round(int(dur.group(1)) * 3600 + int(dur.group(2)) * 60 + float(dur.group(3)), 3) if dur else 0,
        "width": int(vid.group(1)) if vid else 0,
        "height": int(vid.group(2)) if vid else 0,
        "fps": float(fps.group(1)) if fps else 24,
    }


def resolve_asset(name):
    cands = [name] + FALLBACKS.get(name, [])
    for c in cands:
        for ext in (".mp4", ".png", ".jpg"):
            p = A(c + ext)
            if os.path.exists(p) and os.path.getsize(p) > 50000:
                if c != name:
                    log("fallback", name, "->", c)
                return p, ("stock" if p.endswith(".mp4") else "still")
    raise FileNotFoundError("asset not found: " + name)


def tts_beats(force=False):
    out = []
    for i, text in enumerate(BEATS):
        mp3 = A("tts", f"b{i+1:02d}.mp3")
        if force or not (os.path.exists(mp3) and os.path.getsize(mp3) > 1000):
            run([EDGE_TTS, "--voice", VOICE, "--rate", RATE, "--text", text, "--write-media", mp3])
        out.append({"i": i, "text": text, "file": mp3, "duration": probe(mp3)["duration"]})
        log("tts b%02d" % (i + 1), "%.2fs" % out[-1]["duration"])
    return out


def plan_timeline(narr):
    gap = GAP
    lead = LEAD
    beats = []
    t = lead
    for i, n in enumerate(narr):
        beats.append({"start": round(t, 3), "duration": n["duration"], "text": n["text"], "file": n["file"]})
        t += n["duration"] + (GAP_AFTER[i] if i < len(GAP_AFTER) else gap)
    # assign shots
    fps = FPS
    shots = []
    for sh in SHOTS:
        b = beats[sh["beat"]]
        span = b["duration"] + gap
        split = sh.get("split")
        if split is None:
            dur = span
        else:
            dur = span * split
        # find start: shots within same beat accumulate
        sh = dict(sh)
        shots.append(sh)
    # compute starts: iterate, group by beat
    from collections import defaultdict
    groups = defaultdict(list)
    for idx, sh in enumerate(shots):
        groups[sh["beat"]].append(idx)
    t = 0.0
    starts = {}
    for bidx in sorted(groups):
        b = beats[bidx]
        span = b["duration"] + (GAP_AFTER[bidx] if bidx < len(GAP_AFTER) else gap)
        # beat group starts at previous end
        idxs = groups[bidx]
        durs = []
        for sh in (shots[i] for i in idxs):
            split = sh.get("split")
            durs.append(span * (split if split is not None else 1.0))
        # normalize to span (if only one no-split shot -> span)
        total = sum(durs)
        for i, d in zip(idxs, durs):
            starts[i] = (round(t, 3), round(d, 3))
            t += d
        # if split durations sum != span (single shot no split gives span) fine
    for i in starts:
        shots[i]["start"], shots[i]["duration"] = starts[i]
    # last shot tail
    last = len(shots) - 1
    if shots[last].get("tail"):
        shots[last]["duration"] = round(shots[last]["duration"] + shots[last]["tail"], 3)
    total = round(shots[-1]["start"] + shots[-1]["duration"], 3)
    return beats, shots, total


def build_ass(beats, shots, total):
    def ts(t):
        h = int(t // 3600)
        m = int((t % 3600) // 60)
        sec = t % 60
        return f"{h}:{m:02d}:{sec:05.2f}"

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {WIDTH}
PlayResY: {HEIGHT}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Hero,SimHei,112,&H00FCFAF8&,&H00FFFFFF,&H00101014,&H78000000,0,0,0,0,100,100,2,0,1,4,3,5,80,80,80,1
Style: Accent,SimHei,118,&H00F9E867&,&H00FFFFFF,&H00101014,&H78000000,0,0,0,0,100,100,2,0,1,4,3,5,80,80,80,1
Style: Kicker,Noto Sans CJK SC,34,&H00F9E867&,&H00FFFFFF,&H00101014,&H00000000,0,0,0,0,100,100,6,0,1,0,0,7,96,96,96,1
Style: Caption,Noto Sans CJK SC,46,&H00F7EDE6&,&H00FFFFFF,&H00101014,&H78000000,0,0,0,0,100,100,2,0,1,3,2,2,80,80,80,1
Style: End,SimHei,100,&H00FCFAF8&,&H00FFFFFF,&H00101014,&H78000000,0,0,0,0,100,100,2,0,1,4,3,5,80,80,80,1
Style: Credit,Noto Sans CJK SC,32,&H00B8A39A&,&H00FFFFFF,&H00101014,&H00000000,0,0,0,0,100,100,4,0,1,2,2,2,80,80,96,1
Style: Flash,DejaVu Sans,10,&H00FFFFFF&,&H00FFFFFF,&H00FFFFFF&,&H00FFFFFF&,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
Style: Sweep,DejaVu Sans,10,&H00FFFFFF&,&H00FFFFFF,&H00FFFFFF&,&H00FFFFFF&,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = []

    def section_color(shot_i):
        return ass_color(SECTION_ACCENTS[min(len(SECTION_ACCENTS) - 1, shot_i // 4)])

    def esc(t):
        return t.replace("{", "｛").replace("}", "｝")

    KICKER_ANIM = "{\\fad(260,240)\\move(96,166,112,166,0,500)%COLOR%}"
    HERO_ANIM = "{\\fad(300,260)\\move(960,566,960,540,0,650)\\fscx94\\fscy94\\t(0,540,\\fscx100\\fscy100)}"
    CAP_ANIM = "{\\fad(340,280)\\move(960,766,960,742,0,600)%COLOR%}"
    FLASH = "{\\an7\\p1\\fad(30,120)\\c&H00FFFFFF&\\alpha&H28&}m 0 0 l 1920 0 1920 1080 0 1080"
    SWEEP = "{\\an7\\p1\\fad(50,160)%COLOR%\\alpha&H50&\\move(-80,0,2000,0,0,430)}m 0 0 l 34 0 34 1080 0 1080"

    for si, sh in enumerate(shots):
        st = sh["start"]
        dur = sh["duration"]
        col = section_color(si)
        texts = sh.get("texts", [])
        hero_items = [t for t in texts if t[0] in ("hero", "end")]
        cap_items = [t for t in texts if t[0] == "caption"]
        for hi, (kind, off, text, color) in enumerate(hero_items):
            if kind == "end":
                style = "End"
            else:
                style = "Accent" if color == "accent" else "Hero"
            fill = col if color == "accent" else ACCI.get(color, ACCI["white"])
            # stack hero lines around vertical center with 156px leading
            base = sh.get("hero_base", 470 if kind == "end" else 520)
            y = int(base + (hi - (len(hero_items) - 1) / 2.0) * 158)
            y = max(300, min(860, y))
            anim = ("{\\fad(300,260)\\move(960,%d,960,%d,0,680)"
                    "\\fscx94\\fscy94\\t(0,560,\\fscx100\\fscy100)}") % (y + 30, y)
            anim = anim[:-1] + "%COLOR%}"
            t0 = st + off
            t1 = st + dur - 0.02
            body = anim.replace("%COLOR%", "\\c" + fill) + esc(text)
            ev.append((t0, t1, style, body))
        for ci, (kind, off, text, color) in enumerate(cap_items):
            fill = ACCI.get(color, ACCI["muted"])
            y = 806 - ci * 62
            anim = "{\\fad(340,280)\\move(960,%d,960,%d,0,620)}" % (y + 24, y)
            anim = anim[:-1] + "%COLOR%}"
            t0 = st + off
            t1 = st + dur - 0.02
            body = anim.replace("%COLOR%", "\\c" + fill) + esc(text)
            ev.append((t0, t1, "Caption", body))
        credit_items = [t for t in texts if t[0] == "credit"]
        for kind, off, text, color in texts:
            if kind == "credit":
                ci = credit_items.index((kind, off, text, color))
                cy = 822 + ci * 46
                t0 = st + off
                t1 = st + dur - 0.02
                anim = "{\\fad(400,300)\\move(960,%d,960,%d,0,700)%%COLOR%%}" % (cy + 20, cy)
                body = anim.replace("%COLOR%", "\\c" + ACCI.get(color, ACCI["muted"])) + esc(text)
                ev.append((t0, t1, "Credit", body))
            elif kind == "kicker":
                t0 = st + 0.18
                t1 = st + dur - 0.05
                body = KICKER_ANIM.replace("%COLOR%", "\\c" + col) + esc(text)
                ev.append((t0, t1, "Kicker", body))
        if sh.get("flash"):
            t0 = st + 0.02
            ev.append((t0, t0 + 0.15, "Flash", FLASH))
        if sh.get("kind_used") == "still" and len(sh.get("texts", [])) > 0:
            # soft moving light streak on still shots (adds motion to Ken Burns stills)
            for frac, dur_l in ((0.22, 0.5), (0.62, 0.45)):
                a0 = st + dur * frac
                ev.append((a0, a0 + dur_l, "Sweep", SWEEP.replace("%COLOR%", "\\c" + col)))
        if si in (8, 10, 16):
            ev.append((st + 0.02, st + 0.52, "Sweep", SWEEP.replace("%COLOR%", "\\c" + col)))

    ev.sort(key=lambda e: (e[0], e[2]))
    lines = []
    for t0, t1, style, text in ev:
        text = text.replace("\n", "\\N")
        lines.append("Dialogue: 0,%s,%s,%s,,0,0,0,,%s" % (ts(max(0, t0)), ts(max(t0 + 0.05, t1)), style, text))
    return header + "\n".join(lines) + "\n"


def make_clip(idx, sh, total):
    """Render one normalized 1920x1080@24 clip of exact duration."""
    d = sh["duration"]
    n = max(1, int(round(d * FPS)))
    out = W(f"clip_{idx:02d}.mp4")
    if os.path.exists(out) and os.path.getsize(out) > 20000:
        got = probe(out)
        if abs(got["duration"] - n / FPS) < 0.06:
            src, kind = resolve_asset(sh["asset"])
            sh["resolved"] = src
            sh["kind_used"] = kind
            log("clip", sh["id"], "reuse %.2fs" % got["duration"], "src", os.path.basename(src))
            return out
    src, kind = resolve_asset(sh["asset"])
    sh["resolved"] = src
    sh["kind_used"] = kind
    if kind == "stock":
        info = probe(src)
        inpoint = min(max(0.4, info["duration"] * 0.12), max(0, info["duration"] - d - 0.4))
        vf = (f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
              f"crop={WIDTH}:{HEIGHT},fps={FPS},format=yuv420p")
        cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{inpoint:.3f}", "-i", src,
               "-vf", vf, "-r", str(FPS), "-frames:v", str(n), "-an", "-c:v", "libx264",
               "-preset", "medium", "-crf", "16", out]
    else:
        # still: slow push-in / pan with eased zoom
        zi = idx % 3
        if zi == 0:
            z = f"'1.0+0.10*on/{n}'"
            x, y = "'iw/2-(iw/zoom/2)'", "'ih/2-(ih/zoom/2)'"
        elif zi == 1:
            z = f"'1.12-0.10*on/{n}'"
            x, y = "'iw/2-(iw/zoom/2)'", "'ih/2-(ih/zoom/2)'"
        else:
            z = "'1.06'"
            x = f"'iw/2-(iw/zoom/2)+(0.5*on/{n})*(iw*0.06)'"
            y = "'ih/2-(ih/zoom/2)'"
        vf = (f"scale={WIDTH*2}:{HEIGHT*2}:force_original_aspect_ratio=increase,"
              f"crop={WIDTH*2}:{HEIGHT*2},zoompan=z={z}:x={x}:y={y}:d={n}:s={WIDTH}x{HEIGHT}:fps={FPS},"
              f"format=yuv420p")
        cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-loop", "1", "-i", src,
               "-vf", vf, "-r", str(FPS), "-frames:v", str(n), "-an", "-c:v", "libx264",
               "-preset", "medium", "-crf", "16", out]
    run(cmd)
    got = probe(out)
    log("clip", sh["id"], "%.2fs" % got["duration"], "frames", n, "src", os.path.basename(src))
    return out


def build_audio(beats, shots, total):
    """Narration at beat starts + cinematic BGM + whoosh/riser/impact sound design."""
    tts_files = [n["file"] for n in beats]
    inputs = []
    for f in tts_files:
        inputs += ["-i", f]
    music = A("music", "the-journey.mp3") if os.path.exists(A("music", "the-journey.mp3")) else A("music", "vastness.mp3")
    inputs += ["-i", music]
    bgm_idx = len(tts_files)
    n_tts = len(tts_files)

    whooshes = [A("sfx", "whoosh-1.mp3"), A("sfx", "whoosh-2.mp3"), A("sfx", "whoosh-3.mp3")]
    riser = A("sfx", "riser-1.mp3")
    impact = A("sfx", "impact-1.mp3")

    # sound design plan: (file, absolute_time, volume)
    plan = []
    for i, sh in enumerate(shots[1:], start=1):
        plan.append((whooshes[i % len(whooshes)], max(0, sh["start"] - 0.06), 0.22 + (0.06 if i % 3 == 0 else 0.0)))
    # riser + impact into the "biggest risk" beat (b10 = first shot with beat index 9)
    b10_shots = [sh for sh in shots if sh["beat"] == 9]
    if b10_shots:
        t_b10 = b10_shots[0]["start"]
        plan.append((riser, max(0, t_b10 - 0.9), 0.30))
        plan.append((impact, max(0, t_b10 - 0.35), 0.38))
    # impact on end card
    last = shots[-1]["start"]
    plan.append((impact, last, 0.30))

    sfx_start = bgm_idx + 1
    for f, at, vol in plan:
        inputs += ["-i", f]

    fc = []
    for i, b in enumerate(beats):
        delay = int(round(b["start"] * 1000))
        fc.append(f"[{i}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
                  f"adelay={delay}|{delay},volume=1.0[n{i}]")
    fc.append("".join(f"[n{i}]" for i in range(n_tts)) + f"amix=inputs={n_tts}:normalize=0:dropout_transition=0[narr]")
    fc.append(f"[{bgm_idx}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
              f"atrim=0:{total:.3f},volume=0.125,afade=t=in:st=0:d=2.5,afade=t=out:st={max(0,total-3.5):.3f}:d=3.5[bgm]")
    for i, (f, at, vol) in enumerate(plan):
        delay = int(round(max(0, at) * 1000))
        fc.append(f"[{sfx_start+i}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
                  f"adelay={delay}|{delay},volume={vol}[x{i}]")
    fc.append(f"[narr][bgm]" + "".join(f"[x{i}]" for i in range(len(plan))) +
              f"amix=inputs={2+len(plan)}:normalize=0:dropout_transition=0,"
              f"alimiter=limit=0.95:level=false,loudnorm=I=-15:TP=-1.5:LRA=11[aout]")
    cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y"] + inputs + \
          ["-filter_complex", ";".join(fc), "-map", "[aout]", "-t", f"{total:.3f}",
           "-c:a", "aac", "-b:a", "192k", "-ar", "48000", W("audio.m4a")]
    run(cmd)
    log("audio built", W("audio.m4a"), "sfx events", len(plan))


def main():
    os.makedirs(W(), exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(FRAMES, exist_ok=True)
    if "--fresh" in sys.argv:
        for f in os.listdir(W()):
            os.remove(W(f))
    render_only = "--render-only" in sys.argv

    narr = tts_beats(force="--retimed" in sys.argv)
    beats, shots, total = plan_timeline(narr)
    log("timeline total %.2fs" % total, "beats", len(beats), "shots", len(shots))
    for sh in shots:
        log("shot", sh["id"], "beat", sh["beat"] + 1, "start %.2f" % sh["start"], "dur %.2f" % sh["duration"])

    # 1. clips
    clips = []
    for i, sh in enumerate(shots):
        clips.append(make_clip(i, sh, total))
    # 2. concat (stream copy)
    lst = W("concat.txt")
    with open(lst, "w") as f:
        for c in clips:
            f.write(f"file '{c}'\n")
    run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst,
         "-c", "copy", W("video-concat.mp4")])
    log("concat done", "%.2fs" % probe(W("video-concat.mp4"))["duration"])

    # 3. ASS
    ass = build_ass(beats, shots, total)
    open(W("overlay.ass"), "w", encoding="utf-8").write(ass)
    log("ass written", len(ass), "chars")

    # 4. audio
    build_audio(beats, shots, total)

    # 5. final grade + letterbox + ass + grain + fades
    T = total
    vf = (
        f"eq=contrast=1.08:saturation=1.12:gamma=0.98,"
        f"colorbalance=rs=-0.02:gs=0.015:bs=0.05:rm=0.02:bm=-0.04:rh=0.05:bh=-0.03,"
        f"vignette=PI/4.6,"
        f"noise=alls=7:allf=t+u,"
        f"drawbox=x=0:y=0:w=iw:h={BAR}:color=black:t=fill,"
        f"drawbox=x=0:y=ih-{BAR}:w=iw:h={BAR}:color=black:t=fill,"
        f"ass=filename={W('overlay.ass')}:fontsdir={FONTS_DIR},"
        f"fade=t=in:st=0:d=0.55,fade=t=out:st={T-1.1:.3f}:d=1.1,"
        f"format=yuv420p"
    )
    final = os.path.join(OUT, "vibe-cinematic.mp4")
    run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-i", W("video-concat.mp4"), "-i", W("audio.m4a"),
         "-filter_complex", f"[0:v]{vf}[v]", "-map", "[v]", "-map", "1:a", "-t", f"{T:.3f}",
         "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-profile:v", "high",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", final])
    info = probe(final)
    log("FINAL", final, "duration %.2fs" % info["duration"], info["width"], "x", info["height"],
        "size %.1fMB" % (os.path.getsize(final) / 1e6))

    # 6. frames
    times = [0.8, 3, 7, 12, 18, 26, 34, 42, 50, 58, 66, 74, T - 2]
    for t in times:
        if t >= T:
            continue
        run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{t:.2f}", "-i", final,
             "-frames:v", "1", "-q:v", "2", os.path.join(FRAMES, f"f{t:05.1f}.jpg")])
    meta = {
        "final": final, "duration": info["duration"], "width": info["width"], "height": info["height"],
        "fps": FPS, "size": os.path.getsize(final), "voice": VOICE,
        "beats": [{"text": b["text"], "start": b["start"], "duration": b["duration"]} for b in beats],
        "shots": [{"id": s["id"], "asset": os.path.basename(s.get("resolved", "")), "start": s["start"],
                   "duration": s["duration"]} for s in shots],
        "music": os.path.basename(A("music", "the-journey.mp3")) if os.path.exists(A("music", "the-journey.mp3")) else "vastness.mp3",
    }
    json.dump(meta, open(os.path.join(OUT, "report.json"), "w"), ensure_ascii=False, indent=2)
    log("report written")


if __name__ == "__main__":
    main()
