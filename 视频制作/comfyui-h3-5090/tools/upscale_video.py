#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 ComfyUI 生成的 768p 级短片超分到 1080p（或任意目标分辨率）。

思路：不做 H3 latent 二段采样（那条链路要重建子图、风险高），而是走
「解码后的帧 → 4x ESRGAN 超分 → lanczos 缩到目标尺寸 → 带原音轨重新封装」，
也就是影视后期常见的「超分 + 下采样」管线。好处是任何来源的视频都能用，
坏处是不会增加生成细节，只提升锐度与压缩前的有效分辨率。

用法：
  export H3_USER=... H3_PASS=...
  python3 tools/upscale_video.py in.mp4 --out out/ \
      --width 1920 --height 1080 --model 4x-UltraSharp.pth
"""

import argparse
import json
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comfy_client import ComfyClient  # noqa: E402


def upload_video(c, path: Path) -> str:
    r = c.s.post(
        c.base + "/upload/image",
        files={"image": (path.name, path.open("rb"), "video/mp4")},
        data={"overwrite": "true", "type": "input"},
        timeout=300,
    )
    r.raise_for_status()
    return r.json()["name"]


def build_graph(video_name, width, height, model, prefix):
    return {
        "1": {"class_type": "LoadVideo", "inputs": {"file": video_name}},
        "2": {"class_type": "GetVideoComponents", "inputs": {"video": ["1", 0]}},
        "3": {"class_type": "UpscaleModelLoader", "inputs": {"model_name": model}},
        "4": {"class_type": "ImageUpscaleWithModel",
              "inputs": {"upscale_model": ["3", 0], "image": ["2", 0]}},
        "5": {"class_type": "ImageScale",
              "inputs": {"image": ["4", 0], "upscale_method": "lanczos",
                         "width": width, "height": height, "crop": "disabled"}},
        "6": {"class_type": "CreateVideo",
              "inputs": {"images": ["5", 0], "fps": 24.0, "audio": ["2", 1],
                         "bit_depth": 8, "color_space": "sRGB", "codec": "none"}},
        "7": {"class_type": "SaveVideo",
              "inputs": {"video": ["6", 0], "filename_prefix": prefix,
                         "format": "auto", "codec": "auto"}},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--out", default="out")
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--model", default="4x-UltraSharp.pth")
    ap.add_argument("--prefix", default="upscale/h3_up")
    ap.add_argument("--timeout", type=int, default=1800)
    args = ap.parse_args()

    c = ComfyClient()
    c.login()
    src = Path(args.video)
    name = upload_video(c, src)
    print(f"[up] 已上传 {name}")

    g = build_graph(name, args.width, args.height, args.model, args.prefix)
    pid = c.submit(g)
    print(f"[up] prompt_id={pid} 目标 {args.width}x{args.height} 超分模型 {args.model}")
    t0 = time.time()
    entry = c.wait(pid, timeout=args.timeout, quiet=True)
    el = time.time() - t0
    print(f"[up] 完成，用时 {el:.1f}s")

    outs = c.outputs_of(entry)
    outdir = Path(args.out)
    for o in outs:
        data = c.download(o["filename"], o["subfolder"], o["type"])
        outdir.mkdir(parents=True, exist_ok=True)
        p = outdir / o["filename"]
        p.write_bytes(data)
        print(f"[up] saved {p} ({len(data)/1048576:.2f} MB)")

    print(json.dumps({"prompt_id": pid, "elapsed": round(el, 1), "outputs": outs},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
