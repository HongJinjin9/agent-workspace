#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 06 期封面：16:9（1920×1080）+ 1:1（1080×1080）+ 3:4（1080×1440）。

视觉母题：一张长桌、一本手册、一本账本，两根数据柱 —— 13,438 对 12,445（+993）。
冷灰底 + 暖金柱 + 银色对手柱；标题压在左侧暗部。
"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import ep06assets as A
try:
    import ep06viz as V
except ImportError:  # pragma: no cover
    import ep05viz as V
from ep06viz import (BONE, MUTED, DIM, TEAL, AMBER, EMBER, ICE, GOLD,
                     F_SERIF, F_SANS_R, F_MONO, W, H)

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "delivery")

TITLE1 = "他们说，"
TITLE2 = "这是最糟糕的方案"
SUBTITLE = "一场持续六年的技术判决，和它自己的判决"
KICKER = "VIBE 知识共赏 · 第 06 期"
FOOT = "13,438  vs  12,445   ·   2021-11 上险   ·   +993"
SILVER = (176, 190, 196)


def base_canvas(cw, ch, zoom=1.06):
    """冷灰会议桌/旧手册底片，压暗做封面底。"""
    arr = None
    for key, sec in (("ep05_meeting", 1.0), ("desk_night_2", 2.0), ("old_books", 2.0)):
        try:
            path, kind = A.resolve(key)
            if kind != "video":
                continue
            arr = V.load_plate(path, max_w=2560)
            break
        except Exception:
            continue
    if arr is None:
        arr = np.zeros((1080, 1920, 3), np.float32) + np.array((0.02, 0.025, 0.03), np.float32)
    sh, sw = arr.shape[:2]
    z = max(zoom * cw / sw, zoom * ch / sh)
    nw, nh = max(1, int(sw * z)), max(1, int(sh * z))
    im = Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8)).resize(
        (nw, nh), Image.LANCZOS)
    x0, y0 = (nw - cw) // 2, int((nh - ch) * 0.46)
    im = im.crop((x0, y0, x0 + cw, y0 + ch))
    rgb = np.asarray(im, np.float32) / 255.0
    gray = rgb.mean(axis=2, keepdims=True)
    rgb = gray * 0.55 + rgb * 0.45
    rgb = rgb * 0.50 + np.array((0.010, 0.014, 0.020), np.float32)
    rgb[..., 2] *= 1.05
    rgb[..., 0] *= 0.97
    return rgb


def draw_bars(rgb, cw, ch, cx=0.74, base_y=0.80, max_h=0.52, w_ratio=0.085):
    """两根柱：左=13,438（暖金，更高），右=12,445（冷银）；差值 +993。"""
    h_l = max_h * ch
    h_r = h_l * (12445.0 / 13438.0)
    bw = int(cw * w_ratio)
    gap = int(bw * 0.9)
    x_l = int(cw * cx) - bw - gap // 2
    x_r = int(cw * cx) + gap // 2
    y_b = int(ch * base_y)
    layer = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rectangle([x_l, y_b - h_l, x_l + bw, y_b], fill=AMBER + (235,))
    d.rectangle([x_r, y_b - h_r, x_r + bw, y_b], fill=SILVER + (215,))
    d.rectangle([x_l, y_b - h_l, x_l + bw, y_b - h_l + 5], fill=BONE + (255,))
    d.rectangle([x_r, y_b - h_r, x_r + bw, y_b - h_r + 5], fill=BONE + (230,))
    y_diff = int(y_b - h_l - ch * 0.035)
    d.line([(x_l + bw // 2, y_diff), (x_r + bw // 2, y_diff)], fill=GOLD + (170,), width=2)
    d.line([(x_l + bw // 2, y_diff - 8), (x_l + bw // 2, y_diff + 8)], fill=GOLD + (150,), width=2)
    d.line([(x_r + bw // 2, y_diff - 8), (x_r + bw // 2, y_diff + 8)], fill=GOLD + (150,), width=2)
    gl = layer.filter(ImageFilter.GaussianBlur(16))
    base = Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8)).convert("RGBA")
    im = Image.alpha_composite(base, gl)
    im = Image.alpha_composite(im, layer)
    rgb = np.asarray(im.convert("RGB"), np.float32) / 255.0
    V.draw_text(rgb, "13,438", (x_l + bw / 2, y_b - h_l - 40), max(18, int(ch * 0.045)), AMBER,
                F_MONO, anchor="mm", alpha=0.95, track=0)
    V.draw_text(rgb, "12,445", (x_r + bw / 2, y_b - h_r - 40), max(18, int(ch * 0.045)), SILVER,
                F_MONO, anchor="mm", alpha=0.95, track=0)
    V.draw_text(rgb, "+993", (cw * cx, y_diff - int(ch * 0.032)), max(14, int(ch * 0.030)), GOLD,
                F_MONO, anchor="mm", alpha=0.95, track=1)
    V.draw_text(rgb, "理想 ONE 上险", (x_l + bw / 2, y_b + int(ch * 0.028)), max(12, int(ch * 0.022)),
                MUTED, F_SANS_R, anchor="mm", alpha=0.8, track=1)
    V.draw_text(rgb, "大众五款 SUV 上险", (x_r + bw / 2, y_b + int(ch * 0.028)),
                max(12, int(ch * 0.022)), MUTED, F_SANS_R, anchor="mm", alpha=0.8, track=1)
    return rgb


def scrim(rgb, cw, ch):
    yy, xx = np.ogrid[:ch, :cw]
    g = np.exp(-(((xx - cw * 0.28) / (cw * 0.46)) ** 2) -
               ((yy - ch * 0.52) / (ch * 0.62)) ** 2) * 0.78
    ink = np.array((0.010, 0.014, 0.020), np.float32)
    return rgb * (1 - g[..., None]) + ink * g[..., None]


def compose(cw, ch, title_size, outfile, layout="wide"):
    rgb = base_canvas(cw, ch)
    if layout == "wide":
        rgb = draw_bars(rgb, cw, ch, cx=0.735, base_y=0.82, max_h=0.50)
        tx, top = cw * 0.065, ch * 0.40
    elif layout == "square":
        rgb = draw_bars(rgb, cw, ch, cx=0.70, base_y=0.74, max_h=0.32)
        tx, top = cw * 0.065, ch * 0.30
    else:  # tall 1080x1440
        rgb = draw_bars(rgb, cw, ch, cx=0.66, base_y=0.64, max_h=0.28)
        tx, top = cw * 0.065, ch * 0.42
    rgb = scrim(rgb, cw, ch)
    V.draw_text(rgb, KICKER, (tx, top - title_size * 1.05), int(title_size * 0.235),
                MUTED, F_SANS_R, anchor="lm", alpha=0.85, track=5)
    V.draw_text(rgb, TITLE1, (tx, top), title_size, BONE, F_SERIF,
                anchor="lm", alpha=0.97, track=3, glow=20, glow_strength=0.45)
    V.draw_text(rgb, TITLE2, (tx, top + title_size * 1.12), title_size, BONE, F_SERIF,
                anchor="lm", alpha=0.97, track=3, glow=20, glow_strength=0.45)
    V.draw_text(rgb, SUBTITLE, (tx, top + title_size * 2.32), int(title_size * 0.31),
                MUTED, F_SANS_R, anchor="lm", alpha=0.9, track=2)
    V.draw_text(rgb, FOOT, (tx, top + title_size * 3.02), int(title_size * 0.175),
                DIM, F_MONO, anchor="lm", alpha=0.8, track=0.5)
    V.draw_text(rgb, "2020 → 2026", (cw * 0.945, ch * 0.10), int(title_size * 0.19),
                GOLD, F_MONO, anchor="rm", alpha=0.75, track=2)
    img = Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8))
    os.makedirs(OUT, exist_ok=True)
    img.save(outfile, quality=92)
    print(outfile, img.size)


def main():
    compose(1920, 1080, 106, os.path.join(OUT, "cover-16x9.jpg"), "wide")
    compose(1080, 1080, 84, os.path.join(OUT, "cover-1x1.jpg"), "square")
    compose(1080, 1440, 92, os.path.join(OUT, "cover-3x4.jpg"), "tall")


if __name__ == "__main__":
    main()
