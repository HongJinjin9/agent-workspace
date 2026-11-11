#!/usr/bin/env python3
"""第 03 期成片收尾：等帧渲染完成 → 1080×1920 H.264 + AAC 编码 → 静帧/封面 → 基础校验。

用法：python3 finalize.py
输出：out/ep03-judgment.mp4（1080×1920 / 24fps），delivery/stills/*.jpg，delivery/cover-*.jpg
"""
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
FF = "/home/admin/.local/bin/ffmpeg"
# 本机 6 GB cgroup：编码线程同样要压住（默认 2，EP03_FFMPEG_THREADS 可覆盖）。
ENC_THREADS = max(1, int(os.environ.get("EP03_FFMPEG_THREADS", "2")))
TL = json.load(open(os.path.join(ROOT, "work", "timeline.json"), encoding="utf-8"))
TOTAL = float(TL["total"])
FPS = int(TL.get("fps", 24))
N = int(round(TOTAL * FPS))
FRAMES = os.path.join(ROOT, "work", "frames")
AUDIO = os.path.join(ROOT, "work", "audio.m4a")
OUT = os.path.join(ROOT, "out", "ep03-judgment.mp4")

STILLS = [
    (2.2, "still-01-iou"),
    (8.0, "still-02-answer"),
    (17.0, "still-03-first-judgment"),
    (23.0, "still-04-debt-seal"),
    (33.0, "still-05-cost-curves"),
    (38.0, "still-06-generation-bill"),
    (40.5, "still-07-verify-bill"),
    (49.0, "still-08-my-name"),
    (62.0, "still-09-citation"),
    (78.0, "still-10-mit"),
    (98.0, "still-11-boundary"),
    (112.0, "still-12-three-debts"),
    (128.0, "still-13-use-first"),
    (140.0, "still-14-high-risk"),
    (150.0, "still-15-tools"),
    (160.0, "still-16-exec-judgment"),
    (168.0, "still-17-magnifier"),
    (180.0, "still-18-q1"),
    (192.0, "still-19-q3"),
    (205.0, "still-20-flip"),
    (215.0, "still-21-standards"),
    (222.0, "still-22-title"),
    (228.0, "still-23-endcard"),
    (233.5, "still-24-declaration"),
]


def count_frames():
    try:
        return len([f for f in os.listdir(FRAMES) if f.endswith(".jpg")])
    except FileNotFoundError:
        return 0


def wait_frames():
    last, stable = -1, 0
    while True:
        c = count_frames()
        if c >= N and c == last:
            stable += 1
        else:
            stable = 0
        if c >= N and stable >= 3:
            return c
        if c != last:
            print(f"waiting frames {c}/{N}", flush=True)
        last = c
        time.sleep(4)


def run(cmd, **kw):
    print(" ".join(cmd) if isinstance(cmd, list) else cmd, flush=True)
    subprocess.run(cmd, check=True, **kw)


def main():
    if "--no-wait" not in sys.argv:
        c = wait_frames()
        print("frames ready", c)
    if not os.path.exists(AUDIO):
        raise SystemExit(f"缺少音频：{AUDIO}（等 ep03-audio 交付）")
    os.makedirs(os.path.join(ROOT, "out"), exist_ok=True)
    run([FF, "-hide_banner", "-loglevel", "error", "-y",
         "-framerate", str(FPS), "-i", os.path.join(FRAMES, "f%05d.jpg"),
         "-i", AUDIO,
         "-vf", "scale=1080:1920:flags=lanczos,unsharp=5:5:0.35:5:5:0.0",
         "-c:v", "libx264", "-preset", "medium", "-crf", "22", "-pix_fmt", "yuv420p",
         "-threads", str(ENC_THREADS),
         "-profile:v", "high", "-level", "4.1",
         "-c:a", "copy",
         "-movflags", "+faststart", "-t", f"{TOTAL:.3f}", OUT])
    size = os.path.getsize(OUT)
    print("encoded", OUT, size)

    os.makedirs(os.path.join(ROOT, "delivery", "stills"), exist_ok=True)
    for t, name in STILLS:
        run([FF, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{t:.2f}", "-i", OUT,
             "-frames:v", "1", "-q:v", "2", os.path.join(ROOT, "delivery", "stills", name + ".jpg")])
    subprocess.run([sys.executable, os.path.join(ROOT, "gen_cover.py")], check=True)
    # 快速自检：时长/帧数
    p = subprocess.run([FF, "-hide_banner", "-i", OUT, "-map", "0:v:0", "-c", "copy",
                        "-f", "null", "-"], capture_output=True, text=True)
    tail = p.stderr.strip().splitlines()
    print("ffmpeg summary tail:", tail[-1] if tail else "(none)")
    open("/tmp/ep03-judgment.done", "w").write(f"OK {size}")


if __name__ == "__main__":
    main()
