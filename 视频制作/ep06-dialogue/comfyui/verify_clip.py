#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ffprobe + 3-frame extraction + motion heuristic for ComfyUI H3 clips.

For every clip:
  - probe duration / resolution / fps / frames / codecs / audio
  - extract frames at 10%, 50%, 90% of duration into <frames-dir>/<stem>_p{10,50,90}.png
    (these are what the operator visually inspects with read_image)
  - decode grey 96x54 frames and compute frame-to-frame mean abs diff + first/last diff
    as a cheap "is it frozen / did anything move" signal

Exit 0 = all hard checks pass; 1 = at least one hard failure (details in JSON on stdout).

usage:
  python3 verify_clip.py ../assets/comfy/raw/c1_raw.mp4
  python3 verify_clip.py ../assets/comfy/c*.mp4 --frames-dir ../assets/comfy/frames
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np


from probe_util import probe_video  # ffmpeg-based probe (no real ffprobe on this box)


def extract_frames(path, outdir, name):
    outdir.mkdir(parents=True, exist_ok=True)
    info = probe_video(path)
    dur = info.get("duration_s") or 5.0
    frames = {}
    for tag, frac in (("p10", 0.10), ("p50", 0.50), ("p90", 0.90)):
        t = max(0.0, dur * frac)
        out = outdir / f"{name}_{tag}.png"
        p = subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(path),
             "-frames:v", "1", "-q:v", "2", str(out)],
            capture_output=True, text=True)
        frames[tag] = {"t": round(t, 3), "file": str(out),
                       "ok": p.returncode == 0 and out.exists()}
    return frames


def motion_metric(path):
    """Decode tiny grey frames, return motion stats (0-255 scale)."""
    p = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path),
         "-vf", "scale=96:54,format=gray", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
        capture_output=True)
    if p.returncode != 0 or not p.stdout:
        return {"ok": False, "error": (p.stderr[:200].decode(errors="replace"))}
    arr = np.frombuffer(p.stdout, dtype=np.uint8)
    n = arr.size // (96 * 54)
    if n < 2:
        return {"ok": False, "error": "too few decoded frames"}
    fr = arr[: n * 96 * 54].reshape(n, 54, 96).astype(np.int16)
    d_consec = np.abs(np.diff(fr, axis=0)).mean(axis=(1, 2))
    d_span = float(np.abs(fr[-1] - fr[0]).mean())
    return {
        "ok": True,
        "decoded_frames": int(n),
        "mean_consec_diff": round(float(d_consec.mean()), 3),
        "max_consec_diff": round(float(d_consec.max()), 3),
        "first_last_diff": round(d_span, 3),
        "frames_moving_over_2": int((d_consec > 2.0).sum()),
        "frozen": bool(d_consec.mean() < 0.35 and d_span < 1.0),
    }


def check(path, frames_dir, expect_w=None, expect_h=None, min_s=4.0, max_s=6.6):
    info = probe_video(path)
    info["motion"] = motion_metric(path)
    info["frames"] = extract_frames(path, frames_dir, Path(path).stem)
    problems = []
    if not info.get("video"):
        problems.append("no video stream")
    if not info.get("duration_s") or not (min_s <= info["duration_s"] <= max_s):
        problems.append(f"duration {info['duration_s']}s outside [{min_s},{max_s}]")
    if not info.get("fps") or not (20 <= info["fps"] <= 30):
        problems.append(f"fps {info['fps']} outside [20,30]")
    if expect_w and info.get("width") != expect_w:
        problems.append(f"width {info['width']} != expected {expect_w}")
    if expect_h and info.get("height") != expect_h:
        problems.append(f"height {info['height']} != expected {expect_h}")
    if info.get("size_mb", 0) < 0.2:
        problems.append(f"file too small: {info['size_mb']} MB")
    m = info["motion"]
    if m.get("ok") and m.get("frozen"):
        problems.append(f"FROZEN/motionless (consec={m['mean_consec_diff']}, "
                        f"span={m['first_last_diff']})")
    info["problems"] = problems
    info["pass"] = not problems
    return info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--frames-dir", default=str(Path(__file__).resolve().parent.parent /
                                               "assets" / "comfy" / "frames"))
    ap.add_argument("--expect", default="", help="WxH e.g. 864x480 (optional, all files)")
    ap.add_argument("--min-s", type=float, default=4.0)
    ap.add_argument("--max-s", type=float, default=6.6)
    args = ap.parse_args()
    ew = eh = None
    if args.expect:
        w, h = args.expect.lower().split("x")
        ew, eh = int(w), int(h)
    results = []
    for f in args.files:
        paths = sorted(Path().glob(f)) if any(c in f for c in "*?[") else [Path(f)]
        for p in paths:
            if not p.exists():
                results.append({"path": str(p), "pass": False, "problems": ["missing file"]})
                continue
            try:
                results.append(check(p, Path(args.frames_dir), ew, eh, args.min_s, args.max_s))
            except Exception as e:  # noqa: BLE001
                results.append({"path": str(p), "pass": False,
                                "problems": [f"{type(e).__name__}: {e}"]})
    print(json.dumps(results, ensure_ascii=False, indent=1))
    npass = sum(1 for r in results if r.get("pass"))
    print(f"\nVERIFY: {npass}/{len(results)} pass", file=sys.stderr)
    raise SystemExit(0 if npass == len(results) else 1)


if __name__ == "__main__":
    main()
