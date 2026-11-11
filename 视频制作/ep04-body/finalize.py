#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 04 期成片收尾：拼镜 → 统一调色/遮幅/颗粒/字幕/音轨 → 静帧/封面 → 自检。

用法：python3 finalize.py [--no-wait]
输出：out/ep04-body.mp4（1920×1080 / 24fps / 2.35:1 遮幅），delivery/stills/*.jpg
"""
import json
import os
import re
import subprocess
import sys
import time

import numpy as np

ROOT = "/app/vedio/ep04-body"
FFMPEG = "/home/admin/.local/bin/ffmpeg"
WORK = os.path.join(ROOT, "work")
CLIPS = os.path.join(WORK, "clips")
OUT_DIR = os.path.join(ROOT, "out")
DELIVERY = os.path.join(ROOT, "delivery")
TL = json.load(open(os.path.join(WORK, "timeline.json"), encoding="utf-8"))
TOTAL = float(TL["total"])
FPS = int(TL.get("fps", 24))
N = int(round(TOTAL * FPS))
AUDIO = os.path.join(WORK, "audio.m4a")
SRT = os.path.join(WORK, "srt", "all.srt")
ASS = os.path.join(WORK, "srt", "all.ass")
OUT = os.path.join(OUT_DIR, "ep04-body.mp4")
ENC_THREADS = max(1, int(os.environ.get("EP04_FFMPEG_THREADS", "2")))

STILLS = [
    (1.6, "still-01-cold-open"),
    (6.6, "still-02-parameter-sheet"),
    (13.4, "still-03-grip"),
    (21.0, "still-04-three-quantities"),
    (25.8, "still-05-speed-bump"),
    (29.6, "still-06-dong"),
    (35.2, "still-07-wobble"),
    (42.0, "still-08-suspension-body"),
    (50.2, "still-09-suspension-wheel"),
    (56.4, "still-10-frequency-bands"),
    (64.6, "still-11-damping-curves"),
    (69.6, "still-12-damped-settle"),
    (76.2, "still-13-body-sway"),
    (83.0, "still-14-winding-road"),
    (95.1, "still-15-channels"),
    (104.2, "still-16-smooth-info"),
    (113.8, "still-17-broken-line"),
    (121.6, "still-18-lead-time"),
    (131.4, "still-19-ev"),
    (143.6, "still-20-jerk-definition"),
    (157.0, "still-21-rain-jerk"),
    (169.5, "still-22-research-card"),
    (175.5, "still-23-two-sides"),
    (199.2, "still-24-converge"),
    (213.4, "still-25-merge-ecg"),
    (218.0, "still-26-question"),
    (225.6, "still-27-end-card"),
    (233.4, "still-28-declaration"),
]


def log(*a):
    print("[finalize] " + " ".join(str(x) for x in a), flush=True)


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def probe_duration(path):
    p = run([FFMPEG, "-hide_banner", "-i", path])
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", p.stderr)
    if not m:
        return 0.0
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def wait_clips():
    last, stable = -1, 0
    while True:
        missing = [s["id"] for s in TL["shots"]
                   if not (os.path.isfile(os.path.join(CLIPS, s["id"] + ".mp4"))
                           and os.path.getsize(os.path.join(CLIPS, s["id"] + ".mp4")) > 10000)]
        if not missing:
            if stable >= 1:
                return
            stable += 1
        else:
            stable = 0
            log("waiting %d clips, missing: %s" % (len(missing), " ".join(missing[:8])))
        time.sleep(5)


def srt_to_ass():
    """SRT → ASS：2.35 遮幅下把字幕放进底部黑边内（字号 46、白字 + 60% 黑描边）。"""
    def ts(t):
        h = int(t // 3600)
        m = int((t % 3600) // 60)
        s = t % 60
        return "%d:%02d:%05.2f" % (h, m, s)

    entries = []
    raw = open(SRT, encoding="utf-8").read().strip().split("\n\n")
    for block in raw:
        lines = [x for x in block.splitlines() if x.strip()]
        if len(lines) < 2:
            continue
        m = re.match(r"(\d+):(\d+):(\d+),(\d+) --> (\d+):(\d+):(\d+),(\d+)", lines[1])
        if not m:
            continue
        g = [int(x) for x in m.groups()]
        a = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000.0
        b = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000.0
        text = "\\N".join(lines[2:])
        entries.append((a, b, text))

    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,Noto Sans CJK SC,46,&H00F2EEE5,&H00FFFFFF,&H50000000,&H64000000,0,0,0,0,100,100,0.5,0,1,2.4,1.2,2,120,120,56,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    out = [header]
    for a, b, text in entries:
        out.append("Dialogue: 0,%s,%s,Sub,,0,0,0,,%s" % (ts(max(0, a)), ts(max(a + 0.05, b)), text))
    open(ASS, "w", encoding="utf-8").write("\n".join(out) + "\n")
    log("ass written", len(entries), "lines")
    return len(entries)


def build_concat():
    lst = os.path.join(WORK, "concat.txt")
    lines = []
    for s in TL["shots"]:
        p = os.path.join(CLIPS, s["id"] + ".mp4")
        lines.append("file '%s'" % p)
    open(lst, "w").write("\n".join(lines) + "\n")
    concat = os.path.join(WORK, "video-concat.mp4")
    r = run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
             "-i", lst, "-c", "copy", concat])
    if r.returncode != 0:
        raise SystemExit("concat failed: " + r.stderr[-1000:])
    log("concat done %.2fs" % probe_duration(concat))
    return concat


def encode(concat):
    os.makedirs(OUT_DIR, exist_ok=True)
    # 统一影调（轻）+ 暗角 + 胶片颗粒 + 2.35:1 遮幅 + ASS 字幕 + 片头/片尾淡入淡出
    vf = (
        "eq=contrast=1.045:brightness=0.012:saturation=1.06:gamma=1.003,"
        "colorbalance=rs=-0.012:gs=0.0:bs=0.022:rh=0.012:bh=-0.012,"
        "vignette=PI/5.2,"
        "noise=alls=5:allf=t+u,"
        "drawbox=x=0:y=0:w=iw:h=132:color=black:t=fill,"
        "drawbox=x=0:y=ih-132:w=iw:h=132:color=black:t=fill,"
        "ass=filename=%s:fontsdir=/usr/share/fonts/opentype/noto,"
        "fade=t=in:st=0:d=0.6,fade=t=out:st=%.3f:d=1.2,"
        "format=yuv420p" % (ASS, TOTAL - 1.25)
    )
    cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
           "-i", concat, "-i", AUDIO,
           "-filter_complex", "[0:v]%s[v]" % vf,
           "-map", "[v]", "-map", "1:a",
           "-t", "%.3f" % TOTAL,
           "-c:v", "libx264", "-preset", "fast", "-crf", "20",
           "-profile:v", "high", "-level", "4.1",
           "-threads", str(ENC_THREADS),
           "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
           "-movflags", "+faststart", OUT]
    t0 = time.time()
    r = run(cmd)
    if r.returncode != 0:
        raise SystemExit("encode failed:\n" + r.stderr[-2000:])
    log("encoded %s  %.1f MB  %.1fs" % (OUT, os.path.getsize(OUT) / 1e6, time.time() - t0))


def stills_and_cover():
    d = os.path.join(DELIVERY, "stills")
    os.makedirs(d, exist_ok=True)
    for t, name in STILLS:
        run([FFMPEG, "-v", "error", "-y", "-ss", "%.2f" % t, "-i", OUT,
             "-frames:v", "1", "-q:v", "2", os.path.join(d, name + ".jpg")])
    cover = os.path.join(ROOT, "gen_cover.py")
    if os.path.isfile(cover):
        subprocess.run([sys.executable, cover], check=False)


def check():
    results = {}
    # 全片解码
    p = run([FFMPEG, "-hide_banner", "-v", "error", "-i", OUT, "-f", "null", "-"])
    results["decode_errors"] = (p.stderr or "").strip()
    # 流信息
    p = run([FFMPEG, "-hide_banner", "-i", OUT])
    info = p.stderr
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", info)
    results["duration"] = (int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))) if m else 0
    m = re.search(r"Video: .*?, (\d+)x(\d+)", info)
    results["resolution"] = m.groups() if m else None
    m = re.search(r"(\d+(?:\.\d+)?) fps", info)
    results["fps"] = m.group(1) if m else None
    # 响度
    p = run([FFMPEG, "-hide_banner", "-nostats", "-i", OUT, "-af",
             "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"])
    tail = p.stderr
    vals = {}
    try:
        j = json.loads(tail[tail.rindex("{"):])
        vals = {k: j.get(k) for k in ("input_i", "input_tp", "input_lra")}
    except Exception:
        pass
    results["loudness"] = vals
    # 帧数
    p = run([FFMPEG, "-hide_banner", "-v", "error", "-i", OUT, "-map", "0:v:0", "-c", "copy",
             "-f", "null", "-"])
    results["size_mb"] = round(os.path.getsize(OUT) / 1e6, 2)
    print(json.dumps(results, ensure_ascii=False, indent=1))
    open(os.path.join(WORK, "final-check.json"), "w", encoding="utf-8").write(
        json.dumps(results, ensure_ascii=False, indent=2))
    return results


def main():
    if "--no-wait" not in sys.argv:
        wait_clips()
    if not os.path.isfile(AUDIO):
        raise SystemExit("缺少音频: " + AUDIO)
    srt_to_ass()
    concat = build_concat()
    encode(concat)
    stills_and_cover()
    check()


if __name__ == "__main__":
    main()
