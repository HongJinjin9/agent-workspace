#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 08 期逐镜渲染编排：pil 程序化场景 / broll = H3 实拍 + 代码叠加层。

产物：`work/clips/<shot>.mp4`（1920×1080 / 24fps / x264 crf16 / 无声），
由 delivery 的 finalize 统一加 2.35:1 遮幅/调色/字幕/音轨（本脚本不烘焙这些）。

H3 缺失时：不黑屏、不中断 —— 该镜渲染 `fallback` 代码场景（信息与数字不丢，损失实景质感）。

用法：
  python3 scene_body.py --preview S04 1.5       # 单帧预览（含遮幅模拟）
  python3 scene_body.py --preview-all           # 每镜取中点出一张预览（分批，低占用）
  python3 scene_body.py --shot S04              # 渲染单镜
  python3 scene_body.py --all --jobs 2          # 渲染全片（2 进程，4 核 cgroup 安全）
  python3 scene_body.py --only S04,S06 --force  # 指定镜重渲
  python3 scene_body.py --status                # 查看进度
"""
import argparse
import json
import os
import subprocess
import sys
import time

import numpy as np
from PIL import Image

import ep08assets as A
import ep08viz as V
import overlays
import scenes_pil

ROOT = os.path.dirname(os.path.abspath(__file__))
FFMPEG = "/home/admin/.local/bin/ffmpeg"
W, H, FPS = 1920, 1080, 24
WORK = os.path.join(ROOT, "work")
CLIPS = os.path.join(WORK, "clips")
OVLDIR = os.path.join(WORK, "overlays")
PREVIEW = os.path.join(WORK, "previews")
LOCK = "/tmp/ep08-render.lock"
TL = None
SHOTS = {}
BYID = {}


def log(*a):
    print("[scene] " + " ".join(str(x) for x in a), flush=True)


def load_timeline():
    global TL, SHOTS, BYID
    p = os.path.join(WORK, "timeline.json")
    if not os.path.isfile(p):
        raise SystemExit("缺少 work/timeline.json，请先运行 python3 build_timeline.py")
    TL = json.load(open(p, encoding="utf-8"))
    SHOTS = TL["shots"]
    BYID = {s["id"]: s for s in SHOTS}
    return TL


def n_frames(dur, shot=None):
    return max(1, int(round(dur * FPS)))


def shot_frames(shot):
    """按 timeline 的累计帧边界取整，保证 67 镜帧数之和恰等于 round(total*fps)。"""
    start = float(shot.get("start", 0.0))
    end = float(shot.get("end", start + float(shot["dur"])))
    return max(1, int(round(end * FPS)) - int(round(start * FPS)))


def ensure_dirs():
    for d in (CLIPS, OVLDIR, PREVIEW):
        os.makedirs(d, exist_ok=True)


def finalize_preview(rgb, vig=0.30):
    arr = V.color_grade(np.clip(rgb, 0, 1), contrast=1.045, sat=1.05)
    arr = arr * (1 - vig * V._vignette())[..., None]
    arr = np.clip(arr, 0, 1)
    arr[:V.BAR] = 0.0
    arr[H - V.BAR:] = 0.0
    return arr


# ---------------------------------------------------------------- overlay frames
def _overlay_rgba(name, t, dur, shot):
    o = V.OverlayPainter()
    overlays.OVERLAYS[name](t, dur, o, shot)
    return o.image()


def render_overlay_frames(shot):
    sid, dur = shot["id"], float(shot["dur"])
    n = shot_frames(shot)
    d = os.path.join(OVLDIR, sid)
    marker = os.path.join(d, "ready.json")
    want = {"overlay": shot["overlay"], "dur": round(dur, 3), "n": n}
    if os.path.isfile(marker) and os.path.isfile(os.path.join(d, "o%05d.png" % (n - 1))):
        try:
            if json.load(open(marker, encoding="utf-8")) == want:
                return d
        except Exception:
            pass
    os.makedirs(d, exist_ok=True)
    t0 = time.time()
    for i in range(n):
        _overlay_rgba(shot["overlay"], i / float(FPS), dur, shot).save(
            os.path.join(d, "o%05d.png" % i), compress_level=1)
    json.dump(want, open(marker, "w", encoding="utf-8"))
    log("ovl  %-4s %5.2fs %4d frames %6.1fs" % (sid, dur, n, time.time() - t0))
    return d


# ---------------------------------------------------------------- encode
def encode_pil(shot):
    sid, dur = shot["id"], float(shot["dur"])
    n = shot_frames(shot)
    scene = scenes_pil.SCENES[shot.get("scene") or shot.get("fallback")]
    out = os.path.join(CLIPS, sid + ".mp4")
    cmd = [FFMPEG, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", "%dx%d" % (W, H), "-r", str(FPS), "-i", "-",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p",
           "-x264-params", "rc-lookahead=10:sync-lookahead=0", "-threads", "2", "-an", out]
    t0 = time.time()
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        for i in range(n):
            img = scene(i / float(FPS), dur, shot)
            arr = np.asarray(img, np.uint8)
            if arr.shape != (H, W, 3):
                raise RuntimeError("bad frame %s %s" % (sid, arr.shape))
            proc.stdin.write(arr.tobytes())
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
        rc = proc.wait()
    if rc != 0:
        raise RuntimeError("ffmpeg encode failed %s rc=%d" % (sid, rc))
    log("pil  %-4s %5.2fs %4d frames %6.1fs  %s" % (sid, dur, n, time.time() - t0,
                                                    shot.get("scene")))
    return out


def _look_filter():
    """H3 片段进片前的统一 look：冷灰、轻颗粒、暗角（与 finalize 链不冲突，只做素材归化）。"""
    return ("scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,setsar=1,"
            "fps=24,eq=contrast=1.06:brightness=-0.045:saturation=0.60:gamma=0.96,"
            "colorbalance=rs=-0.045:gs=-0.008:bs=0.08:rh=0.02:bh=-0.045")


def encode_broll(shot):
    sid, dur = shot["id"], float(shot["dur"])
    n = shot_frames(shot)
    path, _kind = A.resolve(shot["asset"])
    if not path:
        raise RuntimeError("H3 缺失且未配置 fallback: %s" % sid)
    ovl_dir = render_overlay_frames(shot) if shot.get("overlay") else None
    out = os.path.join(CLIPS, sid + ".mp4")
    # H3 片段固定 ~5s：短镜直接截取；>5.05s 的混合镜按设计稿用 0.82-0.9x 慢放适配
    if dur > 5.05:
        speed = max(0.80, min(0.92, 5.0 / dur))
        in_t = min(4.95, max(0.2, 5.0 - 0.05))
    else:
        speed = 1.0
        in_t = min(5.4, dur + 0.6)
    cmd = [FFMPEG, "-v", "error", "-y", "-stream_loop", "-1", "-t", "%.3f" % in_t,
           "-i", path]
    if speed < 0.999:
        filt = ["[0:v]%s,setpts=PTS/%.4f,fps=24,trim=duration=%.3f,"
                "setpts=PTS-STARTPTS,format=rgb24[b]" % (_look_filter(), speed, dur)]
    else:
        filt = ["[0:v]%s,trim=duration=%.3f,setpts=PTS-STARTPTS,format=rgb24[b]"
                % (_look_filter(), dur)]
    if ovl_dir:
        cmd += ["-framerate", "24", "-i", os.path.join(ovl_dir, "o%05d.png")]
        filt.append("[b][1:v]overlay=0:0:format=auto,format=yuv420p[v]")
    else:
        filt.append("[b]format=yuv420p[v]")
    cmd += ["-filter_complex", ";".join(filt), "-map", "[v]", "-frames:v", str(n),
            "-t", "%.3f" % dur, "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast",
            "-crf", "16", "-pix_fmt", "yuv420p",
            "-x264-params", "rc-lookahead=10:sync-lookahead=0", "-threads", "2", "-an", out]
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg broll failed %s\n%s" % (sid, (r.stderr or "")[-1200:]))
    log("h3   %-4s %5.2fs %4d frames %6.1fs  %s%s" % (
        sid, dur, n, time.time() - t0, shot["asset"],
        " +ovl:" + shot["overlay"] if ovl_dir else ""))
    return out


def render_shot(sid, force=False):
    if sid not in BYID:
        raise SystemExit("未知镜号 " + sid)
    shot = BYID[sid]
    out = os.path.join(CLIPS, sid + ".mp4")
    if not force and os.path.isfile(out) and os.path.getsize(out) > 20000:
        log("skip %-4s (exists)" % sid)
        return out
    if shot["kind"] == "pil":
        return encode_pil(shot)
    p, _ = A.resolve(shot["asset"])
    if p:
        return encode_broll(shot)
    # H3 缺失：降级为 fallback 代码场景（不黑屏、信息不丢）
    return encode_pil(dict(shot, scene=shot.get("fallback")))


# ---------------------------------------------------------------- preview
def preview(sid, t=None, bars=True):
    shot = BYID[sid]
    dur = float(shot["dur"])
    t = float(t) if t is not None else dur * 0.55
    t = max(0.0, min(dur - 1.0 / FPS, t))
    p, _ = A.resolve(shot["asset"]) if shot["kind"] == "broll" else (None, None)
    if shot["kind"] == "pil":
        img = scenes_pil.SCENES[shot["scene"]](t, dur, shot)
        arr = np.asarray(img, np.float32) / 255.0
    elif p:
        # H3 底帧 + 叠加层预览
        base = os.path.join(PREVIEW, "_base_%s.jpg" % sid)
        subprocess.run([FFMPEG, "-v", "error", "-y", "-ss", "%.3f" % min(t, 5.0),
                        "-i", p, "-frames:v", "1", "-vf", _look_filter(), base],
                       check=True)
        arr = np.asarray(Image.open(base).convert("RGB"), np.float32) / 255.0
        if shot.get("overlay"):
            ovr = np.asarray(_overlay_rgba(shot["overlay"], t, dur, shot), np.float32) / 255.0
            a = ovr[..., 3:4]
            arr = arr * (1 - a) + ovr[..., :3] * a
    else:
        img = scenes_pil.SCENES[shot.get("fallback")](t, dur, shot)
        arr = np.asarray(img, np.float32) / 255.0
    if bars:
        arr = finalize_preview(arr)
    out = os.path.join(PREVIEW, "pv_%s_%05.2f.png" % (sid, t))
    Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8)).save(out)
    print(out)
    return out


def render_all(jobs=2, only=None, force=False):
    ensure_dirs()
    ids = [s["id"] for s in SHOTS]
    if only:
        keep = set(x.strip() for x in only.split(",") if x.strip())
        ids = [i for i in ids if i in keep]
    todo = [i for i in ids
            if force or not (os.path.isfile(os.path.join(CLIPS, i + ".mp4"))
                             and os.path.getsize(os.path.join(CLIPS, i + ".mp4")) > 20000)]
    log("todo %d/%d (jobs=%d)" % (len(todo), len(ids), jobs))
    with open(LOCK, "w") as f:
        f.write(str(os.getpid()))
    rc = 0
    t0 = time.time()
    running = []
    try:
        while todo or running:
            while todo and len(running) < jobs:
                sid = todo.pop(0)
                cmd = [sys.executable, os.path.abspath(__file__), "--shot", sid]
                if force:
                    cmd.append("--force")
                env = dict(os.environ, OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1",
                           MKL_NUM_THREADS="1")
                running.append((sid, subprocess.Popen(cmd, cwd=ROOT, env=env), time.time()))
            for sid, pr, ts in list(running):
                code = pr.poll()
                if code is not None:
                    running.remove((sid, pr, ts))
                    if code != 0:
                        rc = 1
                        log("FAILED", sid, "rc=%d" % code)
                    else:
                        log("done  %-4s %.1fs" % (sid, time.time() - ts))
            time.sleep(0.4)
    finally:
        try:
            os.remove(LOCK)
        except OSError:
            pass
    log("render finished rc=%d elapsed=%.1fs" % (rc, time.time() - t0))
    return rc


def status():
    ok = 0
    for s in SHOTS:
        p = os.path.join(CLIPS, s["id"] + ".mp4")
        good = os.path.isfile(p) and os.path.getsize(p) > 20000
        ok += 1 if good else 0
        print("%-4s %-5s %6.2fs %s" % (s["id"], s["kind"], s["dur"], "OK" if good else "MISSING"))
    print("clips %d/%d" % (ok, len(SHOTS)))
    return 0 if ok == len(SHOTS) else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", nargs=2, metavar=("SHOT", "T"))
    ap.add_argument("--preview-all", action="store_true")
    ap.add_argument("--shot")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--only", default=None)
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    load_timeline()
    if a.status:
        return status()
    ensure_dirs()
    if a.preview:
        preview(a.preview[0], a.preview[1])
        return 0
    if a.preview_all:
        for s in SHOTS:
            try:
                preview(s["id"], float(s["dur"]) * 0.55)
            except Exception as e:
                log("preview FAIL", s["id"], repr(e)[:160])
        return 0
    if a.shot:
        render_shot(a.shot, force=a.force)
        return 0
    if a.all:
        return render_all(jobs=a.jobs, only=a.only, force=a.force)
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
