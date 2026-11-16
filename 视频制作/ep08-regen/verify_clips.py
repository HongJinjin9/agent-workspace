#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""逐镜 clip 自检：时长/帧数/分辨率/解码，与 work/timeline.json 对照。"""
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
FFMPEG = "/home/admin/.local/bin/ffmpeg"
CLIPS = os.path.join(ROOT, "work", "clips")
TL = json.load(open(os.path.join(ROOT, "work", "timeline.json"), encoding="utf-8"))


def probe(path):
    r = subprocess.run([FFMPEG, "-hide_banner", "-i", path], capture_output=True, text=True)
    e = r.stderr or ""
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", e)
    dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0
    m = re.search(r"Video: .*?, (\d+)x(\d+)", e)
    wh = (int(m.group(1)), int(m.group(2))) if m else (0, 0)
    m = re.search(r"(\d+(?:\.\d+)?) fps", e)
    fps = float(m.group(1)) if m else 0.0
    dec = subprocess.run([FFMPEG, "-v", "error", "-i", path, "-f", "null", "-"],
                         capture_output=True, text=True).stderr or ""
    return dur, wh, fps, dec.strip()


def main():
    bad = []
    miss = []
    for sh in TL["shots"]:
        sid = sh["id"]
        p = os.path.join(CLIPS, sid + ".mp4")
        if not os.path.isfile(p) or os.path.getsize(p) < 20000:
            miss.append(sid)
            continue
        dur, wh, fps, dec = probe(p)
        want = round(sh["dur"], 2)
        ok = (wh == (1920, 1080) and abs(dur - want) <= 0.13 and abs(fps - 24) < 0.1
              and not dec)
        if not ok:
            bad.append((sid, want, round(dur, 3), wh, fps, dec[:80]))
        print("%-4s %s dur=%.3f/%.3f %s %sfps %s" % (
            sid, "OK " if ok else "BAD", dur, want, "x".join(map(str, wh)), fps,
            dec[:60]))
    print("\nclips %d/%d  bad=%d missing=%d" % (
        len(TL["shots"]) - len(miss), len(TL["shots"]), len(bad), len(miss)))
    if bad:
        print("BAD:", bad)
    if miss:
        print("MISSING:", " ".join(miss))
    return 0 if not bad and not miss else 1


if __name__ == "__main__":
    raise SystemExit(main())
