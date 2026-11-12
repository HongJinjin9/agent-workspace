#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 04 期封面：1920×1080（16:9）主封面 + 1080×1080 方图。"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import ep04assets as A
import ep04viz as V
from ep04viz import BONE, MUTED, TEAL, AMBER, EMBER, F_SERIF, F_SANS_R, F_MONO, W, H

ROOT = "/app/vedio/ep04-body"
OUT = os.path.join(ROOT, "delivery")


def base_canvas(cw, ch, zoom=1.08):
    path = A.ensure_plate("car_interior_night", 8.0)
    arr = V.load_plate(path)
    sh, sw = arr.shape[:2]
    z = max(zoom * W / sw, zoom * H / sh)
    nw, nh = int(sw * z), int(sh * z)
    im = Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8)).resize(
        (nw, nh), Image.LANCZOS)
    x0, y0 = (nw - cw) // 2, int((nh - ch) * 0.42)
    im = im.crop((x0, y0, x0 + cw, y0 + ch))
    rgb = np.asarray(im, np.float32) / 255.0
    rgb = rgb * 0.72 + np.array((0.02, 0.03, 0.04), np.float32)
    return rgb


def compose(cw, ch, title_size, outfile, square=False):
    rgb = base_canvas(cw, ch)
    # 左侧压暗，保证文字可读
    yy, xx = np.ogrid[:ch, :cw]
    scrim = np.exp(-(((xx - cw * 0.32) / (cw * 0.42)) ** 2)) * 0.55
    rgb = rgb * (1 - scrim[..., None]) + np.array((0.02, 0.026, 0.034), np.float32) * scrim[..., None]
    top = ch * (0.40 if not square else 0.34)

    def glow_line(pts, color, width=2.0, alpha=0.5, glow=10):
        nonlocal rgb
        layer = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.line([tuple(p) for p in pts], fill=tuple(color) + (int(255 * alpha),), width=int(width))
        gl = layer.filter(ImageFilter.GaussianBlur(glow))
        rr = (rgb * 255).astype(np.uint8)
        im = Image.alpha_composite(Image.fromarray(rr, "RGB").convert("RGBA"), gl)
        im = Image.alpha_composite(im, layer)
        rgb = np.asarray(im.convert("RGB"), np.float32) / 255.0

    # 三条曲线母题
    for k, (col, fn) in enumerate([
            (TEAL, lambda x: 26 * np.exp(-1.3 * x) * np.sin(3.4 * x * np.pi)),
            (AMBER, lambda x: -22 * V.smoothstep(0.1, 0.8, x)),
            (EMBER, lambda x: 14 * np.exp(-((x - 0.35) ** 2) / 0.004)
             - 18 * np.exp(-((x - 0.72) ** 2) / 0.006))]):
        xs = np.linspace(0, 1, 120)
        px = cw * 0.10 + cw * 0.80 * xs
        py = ch * 0.80 - np.array([fn(x) for x in xs])
        glow_line(np.stack([px, py], 1), col, 1.8, 0.45, 8)
    V.draw_text(rgb, "VIBE 知识共赏 · 第 04 期", (cw * 0.09, top - title_size * 0.95),
                26, MUTED, F_SANS_R, anchor="lm", alpha=0.8, track=5)
    V.draw_text(rgb, "你的身体", (cw * 0.09, top), title_size, BONE, F_SERIF,
                anchor="lm", alpha=0.97, track=4, glow=18, glow_strength=0.45)
    V.draw_text(rgb, "比参数表更懂车", (cw * 0.09, top + title_size * 1.12), title_size,
                BONE, F_SERIF, anchor="lm", alpha=0.97, track=4, glow=18, glow_strength=0.45)
    V.draw_text(rgb, "三个说不清的体感，和它们背后的物理", (cw * 0.09, top + title_size * 2.28),
                int(title_size * 0.30), MUTED, F_SANS_R, anchor="lm", alpha=0.85, track=2)
    img = Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8))
    os.makedirs(OUT, exist_ok=True)
    img.save(outfile, quality=92)
    print(outfile, img.size)


def main():
    compose(1920, 1080, 112, os.path.join(OUT, "cover-16x9.jpg"))
    compose(1080, 1080, 88, os.path.join(OUT, "cover-1x1.jpg"), square=True)


if __name__ == "__main__":
    main()
