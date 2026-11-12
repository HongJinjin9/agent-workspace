#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 05 期封面：16:9（1920×1080）+ 1:1（1080×1080）+ 3:4（1080×1440）。

视觉母题：一张越织越密的网——20 个节点、n(n−1)/2 = 190 条连线，压在夜办公底片上；
标题右上/左侧排字，副标题一行。所有线由组合数学生成，不是手摆的装饰。
"""
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import ep05assets as A
try:  # 过渡期兼容
    import ep05viz as V
except ImportError:  # pragma: no cover
    import ep04viz as V
from ep05viz import (BONE, MUTED, DIM, TEAL, AMBER, EMBER, ICE, GOLD,
                     F_SERIF, F_SANS_R, F_MONO, W, H)

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "delivery")

TITLE1 = "为什么公司越大"
TITLE2 = "越容易自己绊自己"
SUBTITLE = "一条逃不掉的数学，和三种不同的应对"
KICKER = "VIBE 知识共赏 · 第 05 期"
FOOT = "n(n-1)/2  ·  NODES 3 / 10 / 20  ·  EDGES 3 / 45 / 190"


def base_canvas(cw, ch, zoom=1.08):
    """夜办公底片（桌面 / 城市）压暗 + 冷调，作为网的底。"""
    for key, sec in (("desk_night_2", 2.0), ("desk_night", 1.5), ("city_night", 1.0)):
        try:
            path, kind = A.resolve(key)
            if kind == "image":
                continue
            arr = V.load_plate(path, max_w=2560)
            break
        except Exception:
            arr = None
    else:
        arr = np.zeros((1080, 1920, 3), np.float32)
    sh, sw = arr.shape[:2]
    z = max(zoom * cw / sw, zoom * ch / sh)
    nw, nh = max(1, int(sw * z)), max(1, int(sh * z))
    im = Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8)).resize(
        (nw, nh), Image.LANCZOS)
    x0, y0 = (nw - cw) // 2, int((nh - ch) * 0.42)
    im = im.crop((x0, y0, x0 + cw, y0 + ch))
    rgb = np.asarray(im, np.float32) / 255.0
    rgb = rgb * 0.52 + np.array((0.012, 0.018, 0.024), np.float32)
    # 冷暗部 / 暖高光，与正片调色一致
    rgb[..., 2] *= 1.06
    rgb[..., 0] *= 0.97
    return rgb


def draw_network(rgb, cw, ch, cx=0.66, cy=0.46, r=None, n=20, alpha=1.0):
    """n 个节点按确定性布局（黄金角螺旋）→ 全部 C(n,2) 条线；强调「密」。"""
    r = r or (0.40 * ch)
    nodes = []
    for i in range(n):
        ang = i * 2.399963229728653  # 黄金角
        rad = r * math.sqrt((i + 0.5) / n)
        nodes.append((cw * cx + rad * math.cos(ang),
                      ch * cy + rad * math.sin(ang) * 0.86))
    layer = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    edges = [(i, j) for i in range(n) for j in range(i + 1, n)]
    for k, (i, j) in enumerate(edges):
        x0, y0 = nodes[i]
        x1, y1 = nodes[j]
        # 少数边给琥珀/朱红，作为数据层的「信息热点」
        if k % 37 == 0:
            col = AMBER + (int(120 * alpha),)
            wdt = 2
        elif k % 53 == 0:
            col = EMBER + (int(90 * alpha),)
            wdt = 2
        else:
            col = TEAL + (int(56 * alpha),)
            wdt = 1
        d.line([(x0, y0), (x1, y1)], fill=col, width=wdt)
    # 节点：小圆点 + 辉光
    for i, (x, y) in enumerate(nodes):
        rr = 4 if i % 3 else 6
        col = BONE if i % 3 else ICE
        d.ellipse([(x - rr, y - rr), (x + rr, y + rr)], fill=col + (int(235 * alpha),))
    gl = layer.filter(ImageFilter.GaussianBlur(14))
    base = Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8)).convert("RGBA")
    im = Image.alpha_composite(base, gl)
    im = Image.alpha_composite(im, layer)
    return np.asarray(im.convert("RGB"), np.float32) / 255.0


def scrim(rgb, cw, ch, side="left"):
    yy, xx = np.ogrid[:ch, :cw]
    if side == "left":
        g = np.exp(-(((xx - cw * 0.26) / (cw * 0.40)) ** 2)) * 0.72
    elif side == "bottom":
        g = np.exp(-(((yy - ch * 0.70) / (ch * 0.40)) ** 2)) * 0.66
    else:
        g = np.exp(-(((xx - cw * 0.5) / (cw * 0.55)) ** 2) -
                   ((yy - ch * 0.5) / (ch * 0.55)) ** 2) * 0.45
    ink = np.array((0.012, 0.017, 0.023), np.float32)
    return rgb * (1 - g[..., None]) + ink * g[..., None]


def compose(cw, ch, title_size, outfile, layout="wide"):
    rgb = base_canvas(cw, ch)
    rgb = scrim(rgb, cw, ch, "left" if layout != "square" else "center")
    if layout == "wide":
        rgb = draw_network(rgb, cw, ch, cx=0.70, cy=0.46, r=0.44 * ch, alpha=0.9)
        tx, top = cw * 0.075, ch * 0.40
    elif layout == "square":
        rgb = draw_network(rgb, cw, ch, cx=0.62, cy=0.40, r=0.48 * ch, alpha=0.8)
        tx, top = cw * 0.075, ch * 0.52
    else:  # tall 1080x1440
        rgb = draw_network(rgb, cw, ch, cx=0.62, cy=0.30, r=0.40 * ch, alpha=0.85)
        tx, top = cw * 0.075, ch * 0.55
    r = scrim(rgb, cw, ch, "bottom")
    # 底部再压一层，保证字底干净
    yy = np.linspace(0, 1, ch, dtype=np.float32)[:, None, None]
    mask = np.clip((yy - 0.42) / 0.5, 0, 1) ** 1.5
    rgb = r * (1 - 0.72 * mask) + np.array((0.012, 0.017, 0.023), np.float32) * (0.72 * mask)

    V.draw_text(rgb, KICKER, (tx, top - title_size * 1.02), int(title_size * 0.235),
                MUTED, F_SANS_R, anchor="lm", alpha=0.85, track=5)
    V.draw_text(rgb, TITLE1, (tx, top), title_size, BONE, F_SERIF,
                anchor="lm", alpha=0.97, track=3, glow=20, glow_strength=0.45)
    V.draw_text(rgb, TITLE2, (tx, top + title_size * 1.12), title_size, BONE, F_SERIF,
                anchor="lm", alpha=0.97, track=3, glow=20, glow_strength=0.45)
    V.draw_text(rgb, SUBTITLE, (tx, top + title_size * 2.32), int(title_size * 0.31),
                MUTED, F_SANS_R, anchor="lm", alpha=0.9, track=2)
    V.draw_text(rgb, FOOT, (tx, top + title_size * 3.02), int(title_size * 0.175),
                DIM, F_MONO, anchor="lm", alpha=0.8, track=0.5)
    img = Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8))
    os.makedirs(OUT, exist_ok=True)
    img.save(outfile, quality=92)
    print(outfile, img.size)


def main():
    compose(1920, 1080, 108, os.path.join(OUT, "cover-16x9.jpg"), "wide")
    compose(1080, 1080, 86, os.path.join(OUT, "cover-1x1.jpg"), "square")
    compose(1080, 1440, 92, os.path.join(OUT, "cover-3x4.jpg"), "tall")


if __name__ == "__main__":
    main()
