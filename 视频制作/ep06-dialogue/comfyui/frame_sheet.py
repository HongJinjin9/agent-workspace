#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tile the 3 verification frames (10/50/90%) of each clip into one horizontal sheet.

Gives one image per clip for quick visual inspection (motion + content + any text/faces),
instead of opening 24 separate PNGs.

usage:
  python3 frame_sheet.py --frames-dir ../assets/comfy/frames --out-dir ../assets/comfy/frames/sheets
  python3 frame_sheet.py c1 c2 --frames-dir ../assets/comfy/frames
"""
import argparse
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def sheet_for(stem, frames_dir, out_dir, tile_w=640):
    files = [frames_dir / f"{stem}_{tag}.png" for tag in ("p10", "p50", "p90")]
    if not all(f.exists() for f in files):
        return None
    out = out_dir / f"{stem}_sheet.png"
    cmd = ["ffmpeg", "-v", "error", "-y",
           "-i", str(files[0]), "-i", str(files[1]), "-i", str(files[2]),
           "-filter_complex",
           f"[0:v]scale={tile_w}:-2[a];[1:v]scale={tile_w}:-2[b];[2:v]scale={tile_w}:-2[c];"
           f"[a][b][c]hstack=inputs=3[v]",
           "-map", "[v]", "-frames:v", "1", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not out.exists():
        return None
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*", default=[])
    ap.add_argument("--frames-dir", default=str(ROOT / "assets" / "comfy" / "frames"))
    ap.add_argument("--out-dir", default=str(ROOT / "assets" / "comfy" / "frames" / "sheets"))
    ap.add_argument("--tile-w", type=int, default=640)
    args = ap.parse_args()
    frames_dir, out_dir = Path(args.frames_dir), Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ids = args.ids or [f"c{i}" for i in range(1, 15)]
    for sid in ids:
        for stem in (sid, f"{sid}_raw"):
            p = sheet_for(stem, frames_dir, out_dir, args.tile_w)
            if p:
                print(p)


if __name__ == "__main__":
    main()
