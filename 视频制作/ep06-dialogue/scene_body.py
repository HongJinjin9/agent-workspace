#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第 06 期《他们说，这是最糟糕的方案》渲染编排（三幕对话剧 / 三声部）
=====================================================================
镜头发三类：
- pil：全画幅程序化场景（scenes_pil.py，8 个：cold_title/bar_compare/quote_feng/quote_li/
       data_curve/blank_manual/end_card/outro_black），逐帧渲染后直接管道进 ffmpeg；
       若该镜带 overlay 则先 alpha_composite。
- broll：ComfyUI H3 角色/物件镜头（assets/comfy/c1..c14.mp4，1920×1080/24fps/~5.17s）
       或本地 B-roll（ep03/ep05/ep02 stock）；可选 1-N 个数据层叠加（overlays.py）。
       ComfyUI 片段短于镜头时用「慢放 + 末帧凝结（tpad clone）+ 极缓漂移」补足，
       不做循环硬切（4CPU/6GB 内存约束）。
- 每镜进链前按 look（cool / neutral / warm / cool2）做影调：冷灰基底 + 暖金点缀，
  按幕色温偏移（第一幕冷、第二幕中性、第三幕暖、第四幕回冷、收束中性）。

输出：work/clips/<id>.mp4（1920×1080 / 24fps / x264 crf16 / 无声），finalize.py 统一
调色/2.35:1 遮幅/颗粒/48px ASS 字幕/音轨。

用法：
  python3 scene_body.py --prep | --list | --status
  python3 scene_body.py --shot a1c
  python3 scene_body.py --all --jobs 2 [--only id1,id2] [--force] [--allow-missing]
  python3 scene_body.py --preview a2c 8.0
"""
import argparse
import json
import os
import subprocess
import sys
import time

import numpy as np
from PIL import Image

import ep06assets as A
try:  # scene-designer 的 ep06viz.py 未落地前，用 ep05viz 保证编排可联调
    import ep06viz as V
except ImportError:  # pragma: no cover
    import ep05viz as V
    print("[scene] 警告: ep06viz.py 未就绪，暂用 ep05viz 联调", flush=True)
import overlays
import scenes_pil

ROOT = os.path.dirname(os.path.abspath(__file__))
FFMPEG = "/home/admin/.local/bin/ffmpeg"
W, H, FPS = 1920, 1080, 24

WORK = os.path.join(ROOT, "work")
CLIPS = os.path.join(WORK, "clips")
OVERLAYS_DIR = os.path.join(WORK, "overlays")
PREVIEW = os.path.join(WORK, "previews")

# 镜头调色：冷灰基底 + 暖金点缀，按幕色温偏移（SPEC §2.2「每次改判色温偏移一档」）
LOOKS = {
    # 第一幕 / 冷开场：冷灰、低饱和、青暗部
    "cool": ("eq=contrast=1.10:brightness=-0.055:saturation=0.62:gamma=0.93,"
             "colorbalance=rs=-0.045:gs=-0.008:bs=0.075:rm=-0.01:bm=0.02:rh=0.025:bh=-0.035"),
    # 第二幕：中性（数字说话）
    "neutral": ("eq=contrast=1.06:brightness=-0.03:saturation=0.80:gamma=0.97,"
                "colorbalance=rs=-0.012:gs=0.0:bs=0.03:rh=0.02:bh=-0.02"),
    # 第三幕（改判）：转暖，暖金高光
    "warm": ("eq=contrast=1.06:brightness=-0.025:saturation=0.90:gamma=1.0,"
             "colorbalance=rs=0.045:gs=0.012:bs=-0.045:rh=0.055:bh=-0.055"),
    # 第四幕（再判）/ 收束部分：回冷，比 cool 更冷更暗
    "cool2": ("eq=contrast=1.11:brightness=-0.075:saturation=0.55:gamma=0.92,"
              "colorbalance=rs=-0.055:gs=-0.012:bs=0.09:rm=-0.012:bm=0.025:rh=0.02:bh=-0.03"),
    # 兼容 ep05 旧 look 名（退路素材/调试用）
    "office": ("eq=contrast=1.10:brightness=-0.075:saturation=0.62:gamma=0.94,"
               "colorbalance=rs=-0.05:gs=-0.005:bs=0.075:rh=0.02:bh=-0.03"),
    "mood": ("eq=contrast=1.12:brightness=-0.135:saturation=0.52:gamma=0.86,"
             "colorbalance=rs=-0.045:gs=-0.02:bs=0.085:rh=0.015:bh=-0.02"),
    "dawn": ("eq=contrast=1.06:brightness=-0.03:saturation=0.90:gamma=1.02,"
             "colorbalance=rs=0.055:gs=0.018:bs=-0.05:rh=0.06:bh=-0.06"),
    "night": ("eq=contrast=1.10:brightness=-0.09:saturation=0.85:gamma=0.92,"
              "colorbalance=rs=-0.06:gs=-0.01:bs=0.10:rm=-0.01:bm=0.03:rh=0.03:bh=-0.04"),
}

TL = None
SHOTS = {}


def load_timeline():
    global TL, SHOTS
    p = os.path.join(WORK, "timeline.json")
    if not os.path.isfile(p):
        raise SystemExit("缺少 work/timeline.json，请先运行 python3 build_timeline.py")
    TL = json.load(open(p, encoding="utf-8"))
    SHOTS = {s["id"]: s for s in TL["shots"]}
    return TL


def n_frames(dur):
    return max(1, int(round(dur * FPS)))


def log(*a):
    print("[scene] " + " ".join(str(x) for x in a), flush=True)


def ensure_dirs():
    for d in (CLIPS, OVERLAYS_DIR, PREVIEW, os.path.join(WORK, "plates")):
        os.makedirs(d, exist_ok=True)


def finalize_preview(arr, vig=0.24):
    arr = V.color_grade(np.clip(arr, 0, 1), contrast=1.05, sat=1.05)
    arr = arr * (1 - vig * V._vignette())[..., None]
    arr = np.clip(arr, 0, 1)
    arr[:V.BAR] = 0.0
    arr[H - V.BAR:] = 0.0
    return arr


# ------------------------------------------------------------------ overlays
def shot_overlays(shot):
    ov = shot.get("overlays") or shot.get("overlay")
    if not ov:
        return []
    return ov if isinstance(ov, list) else [ov]


def _overlay_rgba(names, t, dur, shot):
    """把 1..N 个叠加器合成为一张 RGBA（按顺序 alpha_composite）。"""
    canvas = None
    for name in names:
        o = V.OverlayPainter()
        overlays.OVERLAYS[name](t, dur, o, shot)
        img = o.image()
        canvas = img if canvas is None else Image.alpha_composite(canvas, img)
    return canvas


def composite_overlay(img, names, t, dur, shot):
    base = img.convert("RGBA")
    for name in names:
        base = Image.alpha_composite(base, _overlay_rgba([name], t, dur, shot))
    return base.convert("RGB")


# ------------------------------------------------------------------ encoding
def encode_pil_frames(shot):
    sid = shot["id"]
    dur = float(shot["dur"])
    n = n_frames(dur)
    scene = scenes_pil.SCENES[shot["scene"]]
    ovl = shot_overlays(shot)
    out = os.path.join(CLIPS, sid + ".mp4")
    cmd = [FFMPEG, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", "%dx%d" % (W, H), "-r", str(FPS), "-i", "-",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p",
           "-x264-params", "rc-lookahead=10:sync-lookahead=0",
           "-threads", "2", "-an", out]
    t0 = time.time()
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        for i in range(n):
            t = i / float(FPS)
            img = scene(t, dur, shot)
            if ovl:
                img = composite_overlay(img, ovl, t, dur, shot)
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
    log("pil  %-6s %5.2fs %4d frames  %6.1fs%s" % (
        sid, dur, n, time.time() - t0, "  +overlay:" + "+".join(ovl) if ovl else ""))
    return out


def _overlay_stamp(names, shot):
    try:
        base = "%.3f" % os.path.getmtime(os.path.abspath(overlays.__file__))
    except OSError:
        base = "0"
    return {"overlays": list(names), "overlays_mtime": base,
            "stage": shot.get("stage")}


def render_overlay_frames(shot):
    """渲染 overlay PNG 序列（支持 1..N 个叠加器）；同一版本/时长/帧数可复用。"""
    sid = shot["id"]
    dur = float(shot["dur"])
    n = n_frames(dur)
    names = shot_overlays(shot)
    d = os.path.join(OVERLAYS_DIR, sid)
    marker = os.path.join(d, "ready.json")
    want = dict(_overlay_stamp(names, shot), dur=round(dur, 3), n=n)
    if os.path.isfile(marker) and os.path.isfile(os.path.join(d, "o%05d.png" % (n - 1))):
        try:
            got = json.load(open(marker, encoding="utf-8"))
        except Exception:
            got = None
        if got == want and len([f for f in os.listdir(d)
                                if f.startswith("o") and f.endswith(".png")]) == n:
            log("ovl  %-6s %5.2fs %4d frames  reused" % (sid, dur, n))
            return d
    os.makedirs(d, exist_ok=True)
    t0 = time.time()
    for i in range(n):
        t = i / float(FPS)
        img = _overlay_rgba(names, t, dur, shot)
        img.save(os.path.join(d, "o%05d.png" % i), compress_level=1)
    json.dump(want, open(marker, "w", encoding="utf-8"))
    log("ovl  %-6s %5.2fs %4d frames  %6.1fs  [%s]" % (
        sid, dur, n, time.time() - t0, "+".join(names)))
    return d


# ------------------------------------------------------------------ comfy (H3) 角色/物件镜头
def plan_comfy(dur, usable, min_speed=0.55):
    """ComfyUI 片段只有 ~5.17s：慢放（≤1.82x）+ 末帧凝结补足，不做循环硬切。"""
    if dur <= usable * 1.02:
        return 1.0, dur, 0.0
    moving_len = min(dur, usable / min_speed)
    speed = usable / moving_len
    freeze = max(0.0, dur - moving_len)
    return round(speed, 4), round(moving_len, 3), round(freeze, 3)


def _comfy_chain(shot, cinfo):
    dur = float(shot["dur"])
    in_t = float(shot.get("in", 0.0))
    usable = max(0.6, min(cinfo["duration"] - in_t, 5.0))
    speed, moving, freeze = plan_comfy(dur, usable)
    pre = ("[0:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,"
           "setsar=1,fps=24")
    chain = pre
    if abs(speed - 1.0) > 1e-3:
        chain += ",setpts=PTS/%.4f,fps=24" % speed
    if freeze > 0.02:
        chain += ",tpad=stop_mode=clone:stop_duration=%.3f" % freeze
    look = LOOKS.get(shot.get("look", "cool"))
    drift = ("scale=2036:1146,crop=1920:1080:"
             "x='(iw-ow)/2+(iw-ow)/2*0.5*sin(2*PI*t/13+0.6)':"
             "y='(ih-oh)/2+(ih-oh)/2*0.4*sin(2*PI*t/17+1.7)'")
    # 末尾补 0.25s 克隆帧：保证 -frames:v 拿满精确帧数（错 1 帧会让 concat 后整体平移）
    filt = [chain + ",%s,%s,tpad=stop_mode=clone:stop_duration=0.25,format=rgb24[base]"
            % (look, drift)]
    inputs = ["-ss", "%.3f" % in_t, "-t", "%.3f" % (usable + 0.2), "-i", shot["_path"]]
    return inputs, filt, "[base]", ("slow+freeze", round(speed, 2), moving, freeze)


def ffmpeg_comfy(shot, ovl_dir=None):
    sid = shot["id"]
    dur = float(shot["dur"])
    n = n_frames(dur)
    path, kind = A.resolve(shot["asset"])
    shot = dict(shot, _path=path)
    cinfo = A.comfy_info(path)
    if cinfo is None or cinfo["duration"] <= 0:
        raise RuntimeError("comfy 片段规格异常: %s" % path)
    inputs, filters, base, plan = _comfy_chain(shot, cinfo)
    out = os.path.join(CLIPS, sid + ".mp4")
    if ovl_dir:
        inputs += ["-framerate", "24", "-i", os.path.join(ovl_dir, "o%05d.png")]
        filters.append("%s[1:v]overlay=0:0:format=auto,format=yuv420p[v]" % base)
    else:
        filters.append("%sformat=yuv420p[v]" % base)
    cmd = [FFMPEG, "-v", "error", "-y"] + inputs + [
        "-filter_complex", ";".join(filters), "-map", "[v]", "-frames:v", str(n),
        "-t", "%.3f" % dur,
        "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast", "-crf", "16",
        "-pix_fmt", "yuv420p", "-x264-params", "rc-lookahead=10:sync-lookahead=0",
        "-threads", "2", "-an", out]
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg comfy failed %s (%.1fs, in=%.1f)\n%s" % (
            sid, cinfo["duration"], float(shot.get("in", 0.0)), r.stderr[-1800:]))
    log("comfy %-6s %5.2fs %4d frames %6.1fs %s in=%.1f plan=%s speed=%.2f move=%.2fs freeze=%.2fs" % (
        sid, dur, n, time.time() - t0, os.path.basename(path),
        float(shot.get("in", 0.0)), plan[0], plan[1], plan[2], plan[3]))
    return out


def ffmpeg_broll(shot, ovl_dir=None):
    sid = shot["id"]
    dur = float(shot["dur"])
    n = n_frames(dur)
    path, kind = A.resolve(shot["asset"])
    if A.is_comfy_path(path):
        return ffmpeg_comfy(dict(shot, _path=path), ovl_dir)
    out = os.path.join(CLIPS, sid + ".mp4")
    look = LOOKS.get(shot.get("look", "cool"))
    in_t = float(shot.get("in", 0.6))
    inputs = []
    filters = []
    if kind == "video":
        inputs += ["-stream_loop", "-1", "-ss", "%.3f" % in_t, "-i", path]
        filters.append("[0:v]scale=1920:1080:force_original_aspect_ratio=increase,"
                       "crop=1920:1080,setsar=1,fps=24,%s,format=rgb24[b]" % look)
    else:
        # AI 静态图兜底：按 shot["still_mode"] 选择运动（in/out/pan_l/pan_r/close）
        mode = shot.get("still_mode", "in")
        nm = max(1, n - 1)
        ztpl = {"in": "1.0+0.06*on/%d",
                "out": "1.06-0.06*on/%d",
                "close": "1.14+0.05*on/%d",
                "pan_l": "1.05",
                "pan_r": "1.05"}[mode]
        z = ztpl % nm if "%d" in ztpl else ztpl
        if mode == "pan_l":
            x = "(iw-iw/zoom)*(1-on/%d)" % nm
            y = "(ih-ih/zoom)/2"
        elif mode == "pan_r":
            x = "(iw-iw/zoom)*on/%d" % nm
            y = "(ih-ih/zoom)/2"
        else:
            x = "iw/2-(iw/zoom/2)+(iw*0.012)*sin(2*PI*on/%d)" % (2 * n)
            y = "ih/2-(ih/zoom/2)+(ih*0.006)*sin(2*PI*on/%d+1.3)" % (3 * n)
        src = "scale=2560:1440:force_original_aspect_ratio=increase,crop=2560:1440"
        if mode == "close":
            src = "scale=3072:1728:force_original_aspect_ratio=increase,crop=3072:1728"
        inputs += ["-loop", "1", "-t", "%.3f" % dur, "-i", path]
        filters.append("[0:v]%s,zoompan=z='%s':x='%s':y='%s':d=%d:s=1920x1080:fps=24,"
                       "setsar=1,%s,format=rgb24[b]" % (src, z, x, y, n, look))
        log("still-mode %s: %s" % (mode, sid))
    if ovl_dir:
        inputs += ["-framerate", "24", "-i", os.path.join(ovl_dir, "o%05d.png")]
        filters.append("[b][1:v]overlay=0:0:format=auto,format=yuv420p[v]")
    else:
        filters.append("[b]format=yuv420p[v]")
    cmd = [FFMPEG, "-v", "error", "-y"] + inputs + [
        "-filter_complex", ";".join(filters), "-map", "[v]", "-frames:v", str(n),
        "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast", "-crf", "16",
        "-pix_fmt", "yuv420p", "-x264-params", "rc-lookahead=10:sync-lookahead=0",
        "-threads", "2", "-an", out]
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg broll failed %s\n%s" % (sid, r.stderr[-1500:]))
    log("brol %-6s %5.2fs %4d frames  %6.1fs  %s%s" % (
        sid, dur, n, time.time() - t0, os.path.basename(path),
        "  [AI-still 缓推]" if kind == "image" else ""))
    return out


# ------------------------------------------------------------------ dispatch
def check_interfaces(shot, allow_missing=False):
    missing = []
    if shot["kind"] == "pil" and shot.get("scene") not in scenes_pil.SCENES:
        missing.append("scene:" + str(shot.get("scene")))
    for name in shot_overlays(shot):
        if name not in overlays.OVERLAYS:
            missing.append("overlay:" + name)
    if missing and not allow_missing:
        raise SystemExit("%s 缺少接口 %s（scenes_pil.SCENES / overlays.OVERLAYS 未就位；"
                         "联调可加 --allow-missing）" % (shot["id"], ", ".join(missing)))
    return missing


def placeholder_scene(sid):
    def fn(t, dur, sh):
        rgb = np.zeros((H, W, 3), np.float32) + np.array((0.03, 0.04, 0.05), np.float32)
        rgb[int(H * 0.45):int(H * 0.55), int(W * 0.3):int(W * 0.7)] = 0.12
        try:
            V.draw_text(rgb, sid, (960, 540), 64, (240, 236, 228), V.F_SANS_R, anchor="mm")
        except Exception:
            pass
        return Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8))
    return fn


def render_shot(sid, allow_missing=False):
    shot = dict(SHOTS[sid])
    ensure_dirs()
    missing = check_interfaces(shot, allow_missing)
    if missing and allow_missing:
        if shot.get("scene") not in scenes_pil.SCENES:
            scenes_pil.SCENES[shot["scene"]] = placeholder_scene(sid)
        keep = [n for n in shot_overlays(shot) if n in overlays.OVERLAYS]
        if keep:
            shot["overlays"] = keep
            shot.pop("overlay", None)
        else:
            shot.pop("overlays", None)
            shot.pop("overlay", None)
    if shot["kind"] == "pil":
        return encode_pil_frames(shot)
    if shot["kind"] == "broll":
        ovl = render_overlay_frames(shot) if shot_overlays(shot) else None
        return ffmpeg_broll(shot, ovl)
    raise SystemExit("unknown shot kind " + shot["kind"])


def preview(sid_or_scene, t, allow_missing=False):
    ensure_dirs()
    if sid_or_scene in SHOTS:
        sh = SHOTS[sid_or_scene]
        dur = float(sh["dur"])
        if sh["kind"] == "pil":
            img = scenes_pil.SCENES[sh["scene"]](t, dur, sh)
            if shot_overlays(sh):
                img = composite_overlay(img, shot_overlays(sh), t, dur, sh)
            arr = finalize_preview(np.asarray(img, np.float32) / 255.0)
            out = os.path.join(PREVIEW, "pv_%s_%05.2f.jpg" % (sid_or_scene, t))
            Image.fromarray((arr * 255).astype(np.uint8)).save(out, quality=90)
            print(out)
        elif sh["kind"] == "broll":
            path, kind = A.resolve(sh["asset"])
            look = LOOKS.get(sh.get("look", "cool"))
            base = os.path.join(PREVIEW, "pvbase_%s.jpg" % sid_or_scene)
            if kind == "video":
                subprocess.run([FFMPEG, "-v", "error", "-y",
                                "-ss", "%.2f" % (float(sh.get("in", 0.6)) + t),
                                "-i", path, "-frames:v", "1", "-vf",
                                "scale=1920:1080:force_original_aspect_ratio=increase,"
                                "crop=1920:1080," + look, base], check=True)
            else:
                subprocess.run([FFMPEG, "-v", "error", "-y", "-i", path, "-frames:v", "1",
                                "-vf", "scale=1920:1080:force_original_aspect_ratio=increase,"
                                "crop=1920:1080," + look, base], check=True)
            img = np.asarray(Image.open(base).convert("RGB"), np.float32) / 255.0
            if shot_overlays(sh):
                op = V.OverlayPainter()
                for name in shot_overlays(sh):
                    overlays.OVERLAYS[name](t, dur, op, sh)
                ovr = np.asarray(op.image(), np.float32) / 255.0
                a = ovr[..., 3:4]
                img = img * (1 - a) + ovr[..., :3] * a
            arr = finalize_preview(np.clip(img, 0, 1))
            out = os.path.join(PREVIEW, "pv_%s_%05.2f.jpg" % (sid_or_scene, t))
            Image.fromarray((arr * 255).astype(np.uint8)).save(out, quality=90)
            print(out)
    elif sid_or_scene in scenes_pil.SCENES:
        for sh in TL["shots"]:
            if sh.get("scene") == sid_or_scene:
                preview(sh["id"], t, allow_missing)
                return
        print("scene not used:" + sid_or_scene)
    else:
        raise SystemExit("unknown shot/scene " + sid_or_scene)


def render_all(jobs=2, only=None, force=False, allow_missing=False):
    ensure_dirs()
    A.prep_plates()
    ids = [s["id"] for s in TL["shots"]]
    if only:
        keep = set(x.strip() for x in only.split(",") if x.strip())
        ids = [i for i in ids if i in keep]
    todo = []
    for sid in ids:
        out = os.path.join(CLIPS, sid + ".mp4")
        if not force and os.path.isfile(out) and os.path.getsize(out) > 10000:
            continue
        todo.append(sid)
    log("todo %d/%d shots (jobs=%d): %s" % (len(todo), len(ids), jobs, " ".join(todo)))
    running = []
    rc = 0
    t0 = time.time()
    while todo or running:
        while todo and len(running) < jobs:
            sid = todo.pop(0)
            cmd = [sys.executable, os.path.abspath(__file__), "--shot", sid]
            if allow_missing:
                cmd.append("--allow-missing")
            env = dict(os.environ, OMP_NUM_THREADS="2", OPENBLAS_NUM_THREADS="2",
                       MKL_NUM_THREADS="2")
            p = subprocess.Popen(cmd, cwd=ROOT, env=env)
            running.append((sid, p, time.time()))
        for sid, p, ts in list(running):
            code = p.poll()
            if code is not None:
                running.remove((sid, p, ts))
                if code != 0:
                    rc = 1
                    log("FAILED", sid, "rc=%d" % code)
                else:
                    log("done %-6s (%.1fs)" % (sid, time.time() - ts))
        time.sleep(0.4)
    log("render_all finished rc=%d elapsed=%.1fs" % (rc, time.time() - t0))
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
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--allow-missing", action="store_true")
    args = ap.parse_args()
    load_timeline()
    if args.prep:
        A.prep_plates()
        return
    if args.list:
        for s in TL["shots"]:
            print(s["id"], s["kind"], s["start"], s["dur"],
                  s.get("scene") or s.get("asset"), shot_overlays(s),
                  s.get("look", ""), "in=%s" % s.get("in", ""))
        return
    if args.status:
        raise SystemExit(status())
    if args.preview:
        preview(args.preview[0], float(args.preview[1]), args.allow_missing)
        return
    if args.shot:
        render_shot(args.shot, args.allow_missing)
        return
    if args.all:
        raise SystemExit(render_all(args.jobs, args.only, args.force, args.allow_missing))
    ap.print_help()


if __name__ == "__main__":
    main()
