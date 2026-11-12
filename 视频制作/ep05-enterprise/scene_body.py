#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第 05 期《为什么公司越大，越容易自己绊自己》渲染编排
=====================================================
镜头发两类（SPEC §2）：
- pil：全画幅程序化场景（scenes_pil.py），逐帧渲染后直接管道进 ffmpeg；
       若该镜还带 overlay（s4c/s5c/s5e），先把 overlays.py 的 RGBA 数据层
       alpha_composite 到场景帧上再编码（SPEC §3.1/§3.2 双重点名）。
- broll：本地 B-roll 或 ComfyUI H3 实拍质感镜头（assets/comfy/cN.mp4）+ 可选数据层
         叠加（overlays.py）；先生成 RGBA PNG 序列，再与底片一次 ffmpeg 合成。
         ComfyUI 片段只有 ~5.17s，长于片长的镜头按「慢放 → 双循环交叉淡化」补足，
         并用极缓的横向漂移/推近运动掩盖循环点。

所有镜头输出到 work/clips/<id>.mp4（1920×1080 / 24fps / x264 crf16 / 无声），
最终由 finalize.py 统一调色、2.35:1 遮幅、颗粒、字幕与音轨。

用法：
  python3 scene_body.py --prep                     # 预抽底片（PIL 场景用）
  python3 scene_body.py --list
  python3 scene_body.py --status
  python3 scene_body.py --shot s2e                 # 渲染单镜
  python3 scene_body.py --all --jobs 2             # 渲染全部（2 进程；已存在则跳过）
  python3 scene_body.py --all --jobs 2 --force     # 全量重渲
  python3 scene_body.py --only s1a,s1b --jobs 2    # 只渲指定镜头
  python3 scene_body.py --preview s2e 3.2          # 单帧预览
"""
import argparse
import json
import math
import os
import subprocess
import sys
import time

import numpy as np
from PIL import Image

import ep05assets as A
try:  # 过渡期：scene-designer 的 ep05viz.py 落地前先用 ep04viz 保证编排可联调
    import ep05viz as V
except ImportError:  # pragma: no cover
    import ep04viz as V
    print("[scene] 警告: ep05viz.py 未就绪，暂用 ep04viz 联调", flush=True)
import overlays
import scenes_pil

ROOT = os.path.dirname(os.path.abspath(__file__))
FFMPEG = "/home/admin/.local/bin/ffmpeg"
W, H, FPS = 1920, 1080, 24

WORK = os.path.join(ROOT, "work")
CLIPS = os.path.join(WORK, "clips")
OVERLAYS_DIR = os.path.join(WORK, "overlays")
PREVIEW = os.path.join(WORK, "previews")

# 镜头调色（在最终统一调色之前先把 B-roll 拉进同一个影调世界）——SPEC §3.3
LOOKS = {
    # 冷白 / 低饱和：走廊、会议室、电梯、中庭（空间层）
    "office": ("eq=contrast=1.10:brightness=-0.075:saturation=0.62:gamma=0.94,"
               "colorbalance=rs=-0.05:gs=-0.005:bs=0.075:rh=0.02:bh=-0.03"),
    # 文件 / 印章 / 桌面暖：S1 的物件与手
    "warm": ("eq=contrast=1.06:brightness=-0.035:saturation=0.92:gamma=1.0,"
             "colorbalance=rs=0.05:gs=0.008:bs=-0.045:rh=0.045:bh=-0.05"),
    # 片尾暖光：光从缝里透进来
    "dawn": ("eq=contrast=1.06:brightness=-0.03:saturation=0.90:gamma=1.02,"
             "colorbalance=rs=0.055:gs=0.018:bs=-0.05:rh=0.06:bh=-0.06"),
    # 冷暗、压掉情绪：变革疲劳 / 空走廊 / 空椅
    "mood": ("eq=contrast=1.12:brightness=-0.135:saturation=0.52:gamma=0.86,"
             "colorbalance=rs=-0.045:gs=-0.02:bs=0.085:rh=0.015:bh=-0.02"),
    # 兼容 ep04 旧名称（程序化场景/退路素材可能沿用）
    "night": ("eq=contrast=1.10:brightness=-0.09:saturation=0.85:gamma=0.92,"
              "colorbalance=rs=-0.06:gs=-0.01:bs=0.10:rm=-0.01:bm=0.03:rh=0.03:bh=-0.04"),
    "dusk": ("eq=contrast=1.08:brightness=-0.035:saturation=0.92:gamma=0.96,"
             "colorbalance=rs=0.03:bs=0.05:rm=0.02:bh=-0.02"),
    "mud": ("eq=contrast=1.10:brightness=-0.15:saturation=0.50:gamma=0.80,"
            "colorbalance=rs=-0.03:gs=-0.02:bs=0.11:rh=0.02:bh=-0.03"),
    "aerial": ("eq=contrast=1.10:brightness=-0.115:saturation=0.56:gamma=0.84,"
               "colorbalance=rs=-0.02:gs=-0.012:bs=0.10:rh=0.02:bh=-0.025"),
    "hand": ("eq=contrast=1.09:brightness=-0.125:saturation=0.46:gamma=0.84,"
             "colorbalance=rs=0.045:gs=-0.012:bs=0.035:rh=0.05:bh=-0.03"),
}

TL = None
SHOTS = {}


def load_timeline():
    global TL, SHOTS
    p = os.path.join(WORK, "timeline.json")
    if not os.path.isfile(p):
        raise SystemExit("缺少 work/timeline.json，请先运行 python3 build_timeline.py "
                         "（或 --provisional）")
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
    """预览用：模拟 finalize 的统一调色 + 暗角 + 2.35:1 遮幅。"""
    arr = V.color_grade(np.clip(arr, 0, 1), contrast=1.05, sat=1.05)
    arr = arr * (1 - vig * V._vignette())[..., None]
    arr = np.clip(arr, 0, 1)
    arr[:V.BAR] = 0.0
    arr[H - V.BAR:] = 0.0
    return arr


# ------------------------------------------------------------------ overlay
_OVERLAYS = None


def overlay_fn(name):
    return overlays.OVERLAYS[name]


def _overlay_rgba(name, t, dur, shot):
    o = V.OverlayPainter()
    overlay_fn(name)(t, dur, o, shot)
    return o.image()


def composite_overlay(img, name, t, dur, shot):
    """pil + overlay 双重点名镜头（s4c/s5c/s5e）：场景帧上叠 RGBA 数据层。"""
    base = img.convert("RGBA")
    ov = _overlay_rgba(name, t, dur, shot)
    return Image.alpha_composite(base, ov).convert("RGB")


# ------------------------------------------------------------------ encoding
def encode_pil_frames(shot):
    sid = shot["id"]
    dur = float(shot["dur"])
    n = n_frames(dur)
    scene = scenes_pil.SCENES[shot["scene"]]
    ovl = shot.get("overlay")
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
        sid, dur, n, time.time() - t0, "  +overlay:" + ovl if ovl else ""))
    return out


def _overlay_stamp(name):
    try:
        return "%.3f" % os.path.getmtime(os.path.abspath(overlays.__file__))
    except OSError:
        return "0"


def render_overlay_frames(shot):
    """渲染 overlay PNG 序列；同一 overlay 版本/时长/帧数的完整序列可直接复用。

    ComfyUI 片段到货后要重渲 base，但 overlay 序列与 base 无关：预渲染一次后
    重渲只需 ffmpeg 合成，能把 pass3 的等待时间压掉 4—6 分钟。
    """
    sid = shot["id"]
    dur = float(shot["dur"])
    n = n_frames(dur)
    d = os.path.join(OVERLAYS_DIR, sid)
    marker = os.path.join(d, "ready.json")
    want = {"overlay": shot["overlay"], "dur": round(dur, 3), "n": n,
            "overlays_mtime": _overlay_stamp(shot["overlay"])}
    if os.path.isfile(marker) and os.path.isfile(os.path.join(d, "o%05d.png" % (n - 1))):
        try:
            got = json.load(open(marker, encoding="utf-8"))
        except Exception:
            got = None
        if got == want and len([f for f in os.listdir(d) if f.startswith("o") and f.endswith(".png")]) == n:
            log("ovl  %-6s %5.2fs %4d frames  reused" % (sid, dur, n))
            return d
    os.makedirs(d, exist_ok=True)
    t0 = time.time()
    for i in range(n):
        t = i / float(FPS)
        img = _overlay_rgba(shot["overlay"], t, dur, shot)
        img.save(os.path.join(d, "o%05d.png" % i), compress_level=1)
    json.dump(want, open(marker, "w", encoding="utf-8"))
    log("ovl  %-6s %5.2fs %4d frames  %6.1fs" % (sid, dur, n, time.time() - t0))
    return d


# ------------------------------------------------------------------ comfy (H3) 实拍片段
def plan_comfy(dur, usable, min_speed=0.55):
    """ComfyUI 片段只有 ~5.17s，长镜头用「慢放 + 末帧凝结（tpad clone）」。

    返回 (speed, moving_len, freeze_len)：
    - 先以最多 1/min_speed ≈1.8x 的慢放吃掉原片，让运动有机械重量；
    - 剩余时长把最后一帧凝结（tpad=stop_mode=clone）+ 极缓漂移，不做循环硬切，
      内存只占单帧，规避 1080p xfade 的多帧缓冲（4 CPU/6GB cgroup 下的硬约束）。
    """
    if dur <= usable * 1.02:
        return 1.0, dur, 0.0
    moving_len = min(dur, usable / min_speed)
    speed = usable / moving_len
    freeze = max(0.0, dur - moving_len)
    return round(speed, 4), round(moving_len, 3), round(freeze, 3)


def _comfy_chain(shot, cinfo):
    """构造 ComfyUI 片段的 ffmpeg filter_complex；[base] 为加影调/漂移后的底片。"""
    dur = float(shot["dur"])
    in_t = float(shot.get("in", 0.0))
    usable = max(0.6, min(cinfo["duration"] - in_t, 5.0))  # 原片可用长度（秒）
    speed, moving, freeze = plan_comfy(dur, usable)
    pre = ("[0:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,"
           "setsar=1,fps=24")
    chain = pre
    if abs(speed - 1.0) > 1e-3:
        chain += ",setpts=PTS/%.4f,fps=24" % speed  # setpts 后重建 CFR
    if freeze > 0.02:
        chain += ",tpad=stop_mode=clone:stop_duration=%.3f" % freeze
    look = LOOKS.get(shot.get("look", "office"))
    # 极缓横向漂移：凝结段也保留一丝"呼吸"，并掩盖 AI 片段起幅/落幅的生硬
    drift = ("scale=2036:1146,crop=1920:1080:"
             "x='(iw-ow)/2+(iw-ow)/2*0.5*sin(2*PI*t/13+0.6)':"
             "y='(ih-oh)/2+(ih-oh)/2*0.4*sin(2*PI*t/17+1.7)'")
    # 末尾补 0.25s 克隆帧：保证 -frames:v 一定拿满精确帧数（帧数错 1 帧会让 concat 后
    # 所有镜头整体平移，13 个 comfy 镜头会累积成 0.5s 的字幕漂移）
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
        "-pix_fmt", "yuv420p", "-x264-params", "rc-lookahead=10:sync-lookahead=0",
        "-threads", "2", "-an", out]
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg broll failed %s\n%s" % (sid, r.stderr[-1500:]))
    log("brol %-6s %5.2fs %4d frames  %6.1fs  %s" % (sid, dur, n, time.time() - t0,
                                                     os.path.basename(path)))
    return out


# ------------------------------------------------------------------ shot dispatch
def check_interfaces(shot, allow_missing=False):
    """scene/overlay 名必须存在；允许 --allow-missing 时给占位帧（仅联调用）。"""
    missing = []
    if shot["kind"] == "pil" and shot.get("scene") not in scenes_pil.SCENES:
        missing.append("scene:" + str(shot.get("scene")))
    if shot.get("overlay") and shot["overlay"] not in overlays.OVERLAYS:
        missing.append("overlay:" + shot["overlay"])
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
        # 联调期：缺接口不阻断渲染，缺 overlay 时只出底片
        if shot.get("scene") not in scenes_pil.SCENES:
            scenes_pil.SCENES[shot["scene"]] = placeholder_scene(sid)
        if shot.get("overlay") and shot["overlay"] not in overlays.OVERLAYS:
            log("%s 缺少 overlay:%s → 联调期只出底片" % (sid, shot["overlay"]))
            shot.pop("overlay", None)
    if shot["kind"] == "pil":
        return encode_pil_frames(shot)
    if shot["kind"] == "broll":
        ovl = None
        if shot.get("overlay"):
            ovl = render_overlay_frames(shot)
        return ffmpeg_broll(shot, ovl)
    raise SystemExit("unknown shot kind " + shot["kind"])


def preview(sid_or_scene, t, allow_missing=False):
    ensure_dirs()
    if sid_or_scene in SHOTS:
        sh = SHOTS[sid_or_scene]
        dur = float(sh["dur"])
        if sh["kind"] == "pil":
            img = scenes_pil.SCENES[sh["scene"]](t, dur, sh)
            if sh.get("overlay"):
                img = composite_overlay(img, sh["overlay"], t, dur, sh)
            arr = finalize_preview(np.asarray(img, np.float32) / 255.0)
            out = os.path.join(PREVIEW, "pv_%s_%05.2f.jpg" % (sid_or_scene, t))
            Image.fromarray((arr * 255).astype(np.uint8)).save(out, quality=90)
            print(out)
        elif sh["kind"] == "broll":
            path, kind = A.resolve(sh["asset"])
            look = LOOKS.get(sh.get("look", "night"))
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
            if sh.get("overlay"):
                op = V.OverlayPainter()
                overlays.OVERLAYS[sh["overlay"]](t, dur, op, sh)
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
                  s.get("scene") or s.get("asset"), s.get("overlay", ""),
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
