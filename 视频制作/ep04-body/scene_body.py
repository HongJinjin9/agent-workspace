#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第 04 期《你的身体，比参数表更懂车》渲染编排
=============================================
镜头发两类：
- pil：全画幅程序化场景（scenes_pil.py），逐帧渲染后直接管道进 ffmpeg；
- broll：真实 B-roll（assets/stock）+ 可选数据层叠加（overlays.py），
         先生成 RGBA PNG 序列，再与底片一次 ffmpeg 合成。

所有镜头输出到 work/clips/<id>.mp4（1920×1080 / 24fps / x264 crf16 / 无声），
最终由 finalize.py 统一调色、2.35:1 遮幅、颗粒、字幕与音轨。

用法：
  python3 scene_body.py --prep                     # 预抽底片（PIL 场景用）
  python3 scene_body.py --list
  python3 scene_body.py --shot s2e                 # 渲染单镜
  python3 scene_body.py --all --jobs 2             # 渲染全部（2 进程）
  python3 scene_body.py --preview s2e 3.2          # 单帧预览
"""
import argparse
import json
import os
import subprocess
import sys
import time

import numpy as np
from PIL import Image

import ep04assets as A
import ep04viz as V
import overlays
import scenes_pil

ROOT = "/app/vedio/ep04-body"
FFMPEG = "/home/admin/.local/bin/ffmpeg"
FFPROBE = "/home/admin/.local/bin/ffprobe"
W, H, FPS = 1920, 1080, 24

WORK = os.path.join(ROOT, "work")
CLIPS = os.path.join(WORK, "clips")
OVERLAYS_DIR = os.path.join(WORK, "overlays")
PREVIEW = os.path.join(WORK, "previews")
TL = json.load(open(os.path.join(WORK, "timeline.json"), encoding="utf-8"))
TOTAL = float(TL["total"])
SHOTS = {s["id"]: s for s in TL["shots"]}

# 镜头调色（在最终统一调色之前先把 B-roll 拉进同一个影调世界）
LOOKS = {
    "night": ("eq=contrast=1.10:brightness=-0.045:saturation=0.94:gamma=0.92,"
              "colorbalance=rs=-0.06:gs=-0.01:bs=0.10:rm=-0.01:bm=0.03:rh=0.03:bh=-0.04"),
    "warm": ("eq=contrast=1.07:brightness=-0.03:saturation=1.02:gamma=0.97,"
             "colorbalance=rs=0.06:gs=0.01:bs=-0.05:rh=0.05:bh=-0.06"),
    "dusk": ("eq=contrast=1.08:brightness=-0.035:saturation=0.92:gamma=0.96,"
             "colorbalance=rs=0.03:bs=0.05:rm=0.02:bh=-0.02"),
    # 日间素材压成黄昏/阴郁影调（泥土路、航拍山路），统一进夜片世界
    "mud": ("eq=contrast=1.10:brightness=-0.15:saturation=0.50:gamma=0.80,"
            "colorbalance=rs=-0.03:gs=-0.02:bs=0.11:rh=0.02:bh=-0.03"),
    "aerial": ("eq=contrast=1.10:brightness=-0.115:saturation=0.56:gamma=0.84,"
               "colorbalance=rs=-0.02:gs=-0.012:bs=0.10:rh=0.02:bh=-0.025"),
    # 日间手部/方向盘素材压成黄昏车内（去绿、压暗、冷影暖高光）
    "hand": ("eq=contrast=1.09:brightness=-0.125:saturation=0.46:gamma=0.84,"
             "colorbalance=rs=0.045:gs=-0.012:bs=0.035:rh=0.05:bh=-0.03"),
}


def n_frames(dur):
    return max(1, int(round(dur * FPS)))


def finalize_preview(arr, vig=0.24):
    """预览用：模拟 finalize 的统一调色 + 暗角 + 2.35:1 遮幅。"""
    arr = V.color_grade(np.clip(arr, 0, 1), contrast=1.05, sat=1.05)
    arr = arr * (1 - vig * V._vignette())[..., None]
    arr = np.clip(arr, 0, 1)
    arr[:V.BAR] = 0.0
    arr[H - V.BAR:] = 0.0
    return arr


def log(*a):
    print("[scene] " + " ".join(str(x) for x in a), flush=True)


def ensure_dirs():
    for d in (CLIPS, OVERLAYS_DIR, PREVIEW, os.path.join(WORK, "plates")):
        os.makedirs(d, exist_ok=True)


# ------------------------------------------------------------------ ffmpeg glue
def encode_pil_frames(shot):
    sid = shot["id"]
    dur = float(shot["dur"])
    n = n_frames(dur)
    scene = scenes_pil.SCENES[shot["scene"]]
    out = os.path.join(CLIPS, sid + ".mp4")
    cmd = [FFMPEG, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", "%dx%d" % (W, H), "-r", str(FPS), "-i", "-",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p",
           "-threads", "2", "-an", out]
    t0 = time.time()
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        for i in range(n):
            t = i / float(FPS)
            img = scene(t, dur, shot)
            arr = np.asarray(img, dtype=np.uint8)
            if arr.shape != (H, W, 3):
                raise RuntimeError("bad frame shape %s" % (arr.shape,))
            proc.stdin.write(arr.tobytes())
            if i % 40 == 0:
                img.save(os.path.join(PREVIEW, "%s_%02d.jpg" % (sid, int(t))), quality=82)
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
        rc = proc.wait()
    if rc != 0:
        raise RuntimeError("ffmpeg encode failed for %s rc=%d" % (sid, rc))
    log("pil %-6s %5.2fs %4d frames  %6.1fs" % (sid, dur, n, time.time() - t0))
    return out


def render_overlay_frames(shot):
    sid = shot["id"]
    dur = float(shot["dur"])
    n = n_frames(dur)
    fn = overlays.OVERLAYS[shot["overlay"]]
    d = os.path.join(OVERLAYS_DIR, sid)
    os.makedirs(d, exist_ok=True)
    t0 = time.time()
    for i in range(n):
        t = i / float(FPS)
        op = V.OverlayPainter()
        fn(t, dur, op, shot)
        img = op.image()
        img.save(os.path.join(d, "o%05d.png" % i), compress_level=1)
    log("ovl %-6s %5.2fs %4d frames  %6.1fs" % (sid, dur, n, time.time() - t0))
    return d


def ffmpeg_broll(shot, ovl_dir=None):
    sid = shot["id"]
    dur = float(shot["dur"])
    n = n_frames(dur)
    path, kind = A.resolve(shot["asset"])
    out = os.path.join(CLIPS, sid + ".mp4")
    look = LOOKS.get(shot.get("look", "night"))
    in_t = float(shot.get("in", 0.6))
    inputs = []
    filters = []
    if kind == "video":
        inputs += ["-stream_loop", "-1", "-ss", "%.3f" % in_t, "-i", path]
        filters.append("[0:v]scale=1920:1080:force_original_aspect_ratio=increase,"
                       "crop=1920:1080,setsar=1,fps=24,%s,format=rgb24[b]" % look)
    else:
        inputs += ["-loop", "1", "-t", "%.3f" % dur, "-i", path]
        filters.append("[0:v]scale=2400:1350:force_original_aspect_ratio=increase,"
                       "crop=2400:1350,zoompan=z='1.02+0.08*on/%d':"
                       "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=%d:s=1920x1080:fps=24,"
                       "setsar=1,%s,format=rgb24[b]" % (n, n, look))
    if ovl_dir:
        inputs += ["-framerate", "24", "-i", os.path.join(ovl_dir, "o%05d.png")]
        filters.append("[b][1:v]overlay=0:0:format=auto,format=yuv420p[v]")
    else:
        filters.append("[b]format=yuv420p[v]")
    cmd = [FFMPEG, "-v", "error", "-y"] + inputs + [
        "-filter_complex", ";".join(filters), "-map", "[v]", "-frames:v", str(n),
        "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast", "-crf", "16",
        "-pix_fmt", "yuv420p", "-threads", "2", "-an", out]
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg broll failed %s\n%s" % (sid, r.stderr[-1500:]))
    log("brol %-6s %5.2fs %4d frames  %6.1fs  %s" % (sid, dur, n, time.time() - t0,
                                                     os.path.basename(path)))
    return out


def render_shot(sid):
    shot = SHOTS[sid]
    ensure_dirs()
    if shot["kind"] == "pil":
        return encode_pil_frames(shot)
    if shot["kind"] == "broll":
        ovl = None
        if shot.get("overlay"):
            ovl = render_overlay_frames(shot)
        return ffmpeg_broll(shot, ovl)
    raise SystemExit("unknown shot kind " + shot["kind"])


def preview(sid_or_scene, t):
    """渲染单帧预览（供人工检查构图）。"""
    ensure_dirs()
    if sid_or_scene in SHOTS:
        sh = SHOTS[sid_or_scene]
        dur = float(sh["dur"])
        if sh["kind"] == "pil":
            img = scenes_pil.SCENES[sh["scene"]](t, dur, sh)
            arr = finalize_preview(np.asarray(img, np.float32) / 255.0)
            out = os.path.join(PREVIEW, "pv_%s_%05.2f.jpg" % (sid_or_scene, t))
            Image.fromarray((arr * 255).astype(np.uint8)).save(out, quality=90)
            print(out)
        elif sh["kind"] == "broll":
            path, kind = A.resolve(sh["asset"])
            look = LOOKS.get(sh.get("look", "night"))
            base = os.path.join(PREVIEW, "pvbase_%s.jpg" % sid_or_scene)
            if kind == "video":
                subprocess.run([FFMPEG, "-v", "error", "-y", "-ss", "%.2f" % (float(sh.get("in", 0.6)) + t),
                                "-i", path, "-frames:v", "1", "-vf",
                                "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080," + look,
                                base], check=True)
            else:
                subprocess.run([FFMPEG, "-v", "error", "-y", "-i", path, "-frames:v", "1",
                                "-vf", "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080," + look,
                                base], check=True)
            img = np.asarray(Image.open(base).convert("RGB"), np.float32) / 255.0
            if sh.get("overlay"):
                op = V.OverlayPainter()
                overlays.OVERLAYS[sh["overlay"]](t, float(sh["dur"]), op, sh)
                ovr = np.asarray(op.image(), np.float32) / 255.0
                a = ovr[..., 3:4]
                img = img * (1 - a) + ovr[..., :3] * a
            arr = finalize_preview(np.clip(img, 0, 1))
            out = os.path.join(PREVIEW, "pv_%s_%05.2f.jpg" % (sid_or_scene, t))
            Image.fromarray((arr * 255).astype(np.uint8)).save(out, quality=90)
            print(out)
    elif sid_or_scene in scenes_pil.SCENES:
        # 场景名 + 默认镜头
        for sh in TL["shots"]:
            if sh.get("scene") == sid_or_scene:
                img = scenes_pil.SCENES[sid_or_scene](t, float(sh["dur"]), sh)
                arr = finalize_preview(np.asarray(img, np.float32) / 255.0)
                out = os.path.join(PREVIEW, "pv_%s_%05.2f.jpg" % (sid_or_scene, t))
                Image.fromarray((arr * 255).astype(np.uint8)).save(out, quality=90)
                print(out)
                return
        print("scene not used:" + sid_or_scene)
    else:
        raise SystemExit("unknown shot/scene " + sid_or_scene)


def render_all(jobs=2, only=None):
    ensure_dirs()
    A.prep_plates()
    ids = [s["id"] for s in TL["shots"]]
    if only:
        keep = set(only.split(","))
        ids = [i for i in ids if i in keep]
    todo = []
    for sid in ids:
        out = os.path.join(CLIPS, sid + ".mp4")
        if os.path.isfile(out) and os.path.getsize(out) > 10000:
            continue
        todo.append(sid)
    log("todo %d shots (jobs=%d): %s" % (len(todo), jobs, " ".join(todo)))
    running = []
    rc = 0
    while todo or running:
        while todo and len(running) < jobs:
            sid = todo.pop(0)
            p = subprocess.Popen([sys.executable, os.path.abspath(__file__), "--shot", sid],
                                 cwd=ROOT)
            running.append((sid, p))
        for sid, p in list(running):
            code = p.poll()
            if code is not None:
                running.remove((sid, p))
                if code != 0:
                    rc = 1
                    log("FAILED", sid)
        time.sleep(0.4)
    return rc


def status():
    ok = 0
    for s in TL["shots"]:
        out = os.path.join(CLIPS, s["id"] + ".mp4")
        good = os.path.isfile(out) and os.path.getsize(out) > 10000
        ok += 1 if good else 0
        print("%-6s %-5s %5.2fs %s" % (s["id"], s["kind"], s["dur"], "OK" if good else "MISSING"))
    print("clips %d/%d" % (ok, len(TL["shots"])))
    return 0 if ok == len(TL["shots"]) else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prep", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--shot")
    ap.add_argument("--scene")
    ap.add_argument("--preview", nargs=2, metavar=("SHOT", "T"))
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--only", default=None)
    args = ap.parse_args()
    if args.prep:
        A.prep_plates()
        return
    if args.list:
        for s in TL["shots"]:
            print(s["id"], s["kind"], s["start"], s["dur"], s.get("scene") or s.get("asset"),
                  s.get("overlay", ""))
        return
    if args.status:
        raise SystemExit(status())
    if args.preview:
        preview(args.preview[0], float(args.preview[1]))
        return
    if args.shot:
        render_shot(args.shot)
        return
    if args.all:
        raise SystemExit(render_all(args.jobs, args.only))
    ap.print_help()


if __name__ == "__main__":
    main()
