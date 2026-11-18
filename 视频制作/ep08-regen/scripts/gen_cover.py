#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 08 期封面：16:9（1920×1080）+ 1:1（1080×1080）+ 3:4（1080×1440）。

视觉母题：能量流。可逆通道「轮端 → 电机 → 逆变器 → 电池」的环，青=回收/电，琥珀=输出/损耗。
底片优先用成片静帧（默认 delivery/stills/still-01-cover.jpg 或 --source 指定）；没有静帧时
用程序化底（冷灰 #0e1216 + 能量环 + 颗粒），保证封面不依赖任何外部素材。

文字：
  KICKER   VIBE 知识共赏 · 第 08 期
  主标题   电动车松开油门 / 为什么能充电
  副标题   松油门不是发电，是把动能收回来
  脚注     动能回收 · 轮端 / 电机 / 逆变器 / 电池 的可逆通道

用法：
  python3 scripts/gen_cover.py                                  # 自动找静帧 → delivery/
  python3 scripts/gen_cover.py --source delivery/stills/still-03-motor.png --motif
  python3 scripts/gen_cover.py --config work/cover-config.json  # Lead 可覆盖文案
输出：delivery/cover-16x9.jpg / cover-1x1.jpg / cover-3x4.jpg
"""
import argparse
import json
import math
import os
import sys

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DELIVERY = os.path.join(ROOT, "delivery")
STILLS = os.path.join(DELIVERY, "stills")

F_SERIF_BOLD = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc"   # index 2 = SC
F_SANS_REG = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"   # index 2 = SC
F_SANS_BOLD = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
F_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"

INK = (14, 18, 22)            # #0e1216 冷灰
BONE = (233, 228, 216)        # #e9e4d8 纸白
MUTED = (150, 158, 166)
DIM = (104, 112, 120)
TEAL = (47, 211, 197)         # #2fd3c5 能量青（回收/电）
AMBER = (217, 164, 65)        # #d9a441 动力琥珀（输出/损耗）
RED = (179, 57, 46)           # #b3392e 批注红

DEFAULT_TEXT = {
    "kicker": "VIBE 知识共赏 · 第 08 期",
    "title1": "电动车松开油门",
    "title2": "为什么能充电",
    "subtitle": "松油门不是发电，是把动能收回来",
    "foot": "动能回收 · 轮端 / 电机 / 逆变器 / 电池 的可逆通道",
}
DEFAULT_SOURCES = [
    os.path.join(STILLS, "still-01-cover.jpg"),
    os.path.join(STILLS, "still-03-motor.png"),
    os.path.join(STILLS, "still-03-motor.jpg"),
    os.path.join(STILLS, "still-02-energy-flow.jpg"),
]


def font(path, size, index=2):
    try:
        return ImageFont.truetype(path, size, index=index)
    except Exception:
        try:
            return ImageFont.truetype(path, size, index=0)
        except Exception:
            return ImageFont.load_default()


def text_w(draw, s, f):
    try:
        return draw.textlength(s, font=f)
    except Exception:
        return len(s) * f.size * 0.6


def draw_tracked(draw, xy, s, f, fill, track=0.0, alpha=255):
    """带字距的文字（PIL 无 track 参数，逐字绘制）。"""
    x, y = xy
    for ch in s:
        if ch != " ":
            draw.text((x, y), ch, font=f, fill=fill + (alpha,) if len(fill) == 3 else fill)
        x += text_w(draw, ch if ch != " " else " ", f) + track
    return x


def glow_layer(size, draw_fn, blur=18, strength=0.55):
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    draw_fn(layer)
    gl = layer.filter(ImageFilter.GaussianBlur(blur))
    from PIL import ImageEnhance
    gl = ImageEnhance.Brightness(gl).enhance(1.0 + strength)
    return gl, layer


def crop_fill(im, tw, th, focus_y=0.45):
    w, h = im.size
    target = tw / th
    if w / h > target:
        nw = int(h * target)
        box = ((w - nw) // 2, 0, (w + nw) // 2, h)
    else:
        nh = int(w / target)
        y0 = max(0, min(h - nh, int((h - nh) * focus_y)))
        box = (0, y0, w, y0 + nh)
    return im.crop(box).resize((tw, th), Image.LANCZOS)


def strip_letterbox(im):
    """若底片是 2.35:1 成片帧（上下黑边），裁掉黑边，只留画面。"""
    g = np.asarray(im.convert("L"), np.float32)
    h = g.shape[0]
    bar = int(h * 0.122)  # 132/1080
    if bar > 6 and g[:bar].mean() < 6 and g[h - bar:].mean() < 8:
        return im.crop((0, bar, im.width, h - bar))
    return im


def scrim(rgb, cw, ch, side="left"):
    yy, xx = np.ogrid[:ch, :cw]
    if side == "left":
        g = np.exp(-(((xx - cw * 0.24) / (cw * 0.42)) ** 2)) * 0.80
    else:
        g = np.exp(-(((xx - cw * 0.5) / (cw * 0.60)) ** 2)) * 0.62
    ink = np.array(INK, np.float32) / 255.0
    return rgb * (1 - g[..., None]) + ink * g[..., None]


def procedural_bg(cw, ch):
    """冷灰底 + 能量环 + 颗粒（无外部素材时的封面底）。"""
    yy, xx = np.mgrid[0:ch, 0:cw].astype(np.float32)
    ny, nx = yy / ch, xx / cw
    rgb = np.zeros((ch, cw, 3), np.float32)
    rgb[..., 0] = 0.014 + 0.016 * (1 - ny)
    rgb[..., 1] = 0.020 + 0.020 * (1 - ny)
    rgb[..., 2] = 0.030 + 0.026 * (1 - ny)
    # 中心偏右的椭圆光
    cx, cy = 0.70 * cw, 0.40 * ch
    r = np.sqrt(((xx - cx) / (0.36 * cw)) ** 2 + ((yy - cy) / (0.42 * ch)) ** 2)
    halo = np.exp(-(r ** 2) * 2.2) * 0.20
    rgb[..., 1] += halo * 0.55
    rgb[..., 2] += halo * 0.50
    rgb[..., 0] += halo * 0.10
    im = Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8)).convert("RGBA")
    # 能量环：四站可逆通道（轮端↔电机↔逆变器↔电池）——确定性几何，不手摆装饰
    layer = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    ew, eh = 0.25 * cw, 0.25 * ch
    box = [cx - ew, cy - eh, cx + ew, cy + eh]
    d.ellipse(box, outline=TEAL + (150,), width=max(2, cw // 420))
    d.ellipse([box[0] + ew * 0.12, box[1] + eh * 0.12,
               box[2] - ew * 0.12, box[3] - eh * 0.12], outline=TEAL + (55,), width=1)
    labels = ["轮端", "电机", "逆变器", "电池"]
    # (px, py, 标签位置：below/above/left/right)
    pts = [(cx, cy + eh, "below", "轮端"),
           (cx - ew, cy, "left", "电机"),
           (cx + ew, cy, "right", "逆变器"),
           (cx, cy - eh, "above", "电池")]
    f_lab = font(F_SANS_REG, max(14, int(cw * 0.018)))
    for px, py, side, lab in pts:
        rr = max(4, cw // 250)
        d.ellipse([px - rr, py - rr, px + rr, py + rr], fill=BONE + (235,))
        d.ellipse([px - rr * 2.2, py - rr * 2.2, px + rr * 2.2, py + rr * 2.2],
                  outline=TEAL + (70,), width=1)
        tw_ = text_w(d, lab, f_lab)
        if side == "below":
            tx_, ty_ = px - tw_ / 2, py + rr * 2.6
        elif side == "above":
            tx_, ty_ = px - tw_ / 2, py - rr * 2.6 - f_lab.size
        elif side == "left":
            tx_, ty_ = px + rr * 2.6, py - f_lab.size / 2      # 标签放环内，避免出画
        else:
            tx_, ty_ = px - tw_ - rr * 2.6, py - f_lab.size / 2
        d.text((tx_, ty_), lab, font=f_lab, fill=MUTED + (220,))
    # 环上方向箭头（回收流向：轮端→电机→逆变器→电池），青=回收
    for a in (math.pi * -0.5, 0.0, math.pi * 0.5, math.pi):
        ax, ay = cx + ew * math.cos(a), cy + eh * math.sin(a)
        tang = a + math.pi / 2
        L = max(7, cw // 140)
        p1 = (ax + L * math.cos(tang), ay + L * math.sin(tang) * (eh / ew))
        p2 = (ax - L * 0.6 * math.cos(tang + 0.5), ay - L * 0.6 * math.sin(tang + 0.5))
        p3 = (ax - L * 0.6 * math.cos(tang - 0.5), ay - L * 0.6 * math.sin(tang - 0.5))
        d.polygon([p1, p2, p3], fill=TEAL + (190,))
    # 琥珀色反向箭头（电池→轮端=输出），提示「可逆」
    for a in (math.pi * -0.25, math.pi * 0.75):
        ax, ay = cx + ew * math.cos(a), cy + eh * math.sin(a)
        d.line([(ax, ay), (ax + 4 * math.cos(a + 0.4), ay + 4 * math.sin(a + 0.4))],
               fill=AMBER + (160,), width=max(1, cw // 700))
    glow = layer.filter(ImageFilter.GaussianBlur(max(2, cw / 300)))
    im = Image.alpha_composite(im, glow)
    im = Image.alpha_composite(im, layer)
    return im.convert("RGB")


def base_canvas(cw, ch, source):
    if source and os.path.isfile(source):
        im = Image.open(source).convert("RGB")
        im = strip_letterbox(im)
        im = crop_fill(im, cw, ch)
        rgb = np.asarray(im, np.float32) / 255.0
        # 与正片一致的轻微调色（冷暗部/暖高光）
        rgb[..., 0] *= 0.97
        rgb[..., 2] *= 1.06
        return Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8))
    return procedural_bg(cw, ch)


def draw_motif(im, cw, ch):
    """把能量环叠到底片上（--motif；底片已有原理图时可不开）。"""
    layer = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, cy = 0.68 * cw, 0.46 * ch
    ew, eh = 0.30 * cw, 0.24 * ch
    box = [cx - ew, cy - eh, cx + ew, cy + eh]
    d.ellipse(box, outline=TEAL + (140,), width=max(2, cw // 420))
    for i, lab in enumerate(["轮端", "电机", "逆变器", "电池"]):
        a = math.pi * (0.25 + 0.5 * i)
        px, py = cx + ew * math.cos(a), cy + eh * math.sin(a)
        rr = max(3, cw // 320)
        d.ellipse([px - rr, py - rr, px + rr, py + rr], fill=BONE + (230,))
        f = font(F_SANS_REG, max(12, int(cw * 0.013)))
        d.text((px + rr + 4, py - f.size * 0.6), lab, font=f, fill=MUTED + (180,))
    gl = layer.filter(ImageFilter.GaussianBlur(max(2, cw // 240)))
    im = Image.alpha_composite(im.convert("RGBA"), gl)
    return Image.alpha_composite(im, layer).convert("RGB")


def compose(cw, ch, title_size, outfile, layout, text, source, motif=False):
    im = base_canvas(cw, ch, source)
    rgb = np.asarray(im, np.float32) / 255.0
    rgb = scrim(rgb, cw, ch, "left" if layout != "square" else "center")
    # 底部再压一层，保证字底干净
    yy = np.linspace(0, 1, ch, dtype=np.float32)[:, None, None]
    mask = np.clip((yy - 0.40) / 0.52, 0, 1) ** 1.6
    ink = np.array(INK, np.float32) / 255.0
    rgb = rgb * (1 - 0.74 * mask) + ink * (0.74 * mask)
    im = Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8))
    if motif:
        im = draw_motif(im, cw, ch)
    im = im.convert("RGBA")

    if layout == "wide":
        tx, ty = cw * 0.070, ch * 0.46
    elif layout == "square":
        tx, ty = cw * 0.075, ch * 0.55
    else:
        tx, ty = cw * 0.075, ch * 0.57

    kicker = text["kicker"]
    t1, t2 = text["title1"], text["title2"]
    sub = text["subtitle"]
    foot = text["foot"]
    f_kick = font(F_SANS_REG, int(title_size * 0.24))
    f_title = font(F_SERIF_BOLD, title_size)
    f_sub = font(F_SANS_REG, int(title_size * 0.315))
    # 脚注含中文，用 Noto Sans CJK（DejaVu Mono 无 CJK 字形，会显示方框）
    f_foot = font(F_SANS_REG, int(title_size * 0.165))

    # 辉光层（标题）
    def paint(txt_layer):
        dl = ImageDraw.Draw(txt_layer)
        draw_tracked(dl, (tx, ty), kicker, f_kick, MUTED, track=title_size * 0.055, alpha=230)
        draw_tracked(dl, (tx, ty + title_size * 1.02), t1, f_title, BONE,
                     track=title_size * 0.030, alpha=248)
        draw_tracked(dl, (tx, ty + title_size * 2.12), t2, f_title, BONE,
                     track=title_size * 0.030, alpha=248)
        draw_tracked(dl, (tx, ty + title_size * 3.28), sub, f_sub, MUTED,
                     track=title_size * 0.014, alpha=235)
        draw_tracked(dl, (tx, ty + title_size * 3.98), foot, f_foot, DIM,
                     track=title_size * 0.008, alpha=210)

    glow, layer = glow_layer(im.size, paint, blur=int(title_size * 0.16), strength=0.45)
    im = Image.alpha_composite(im, glow)
    im = Image.alpha_composite(im, layer)

    # 左侧竖线（系列视觉记号）+ 底部一条细能量线
    d = ImageDraw.Draw(im)
    d.rectangle([tx - title_size * 0.36, ty + title_size * 0.04,
                 tx - title_size * 0.30, ty + title_size * 2.30],
                fill=TEAL + (210,))
    y_base = ty + title_size * 4.55
    if y_base < ch * 0.94:
        d.line([(tx, y_base), (min(cw - tx, tx + cw * 0.44), y_base)],
               fill=TEAL + (90,), width=max(1, cw // 900))
        d.line([(tx, y_base + 6), (min(cw - tx, tx + cw * 0.16), y_base + 6)],
               fill=AMBER + (120,), width=max(1, cw // 900))

    out = im.convert("RGB")
    os.makedirs(os.path.dirname(outfile) or ".", exist_ok=True)
    out.save(outfile, quality=92)
    print("%-22s %dx%d  <- %s" % (os.path.basename(outfile), cw, ch,
                                  os.path.basename(source) if source else "procedural"))


def pick_source(explicit=None):
    if explicit:
        return explicit if os.path.isfile(explicit) else None
    for c in DEFAULT_SOURCES:
        if os.path.isfile(c):
            return c
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=None)
    ap.add_argument("--out", default=DELIVERY)
    ap.add_argument("--config", default=os.path.join(ROOT, "work", "cover-config.json"))
    ap.add_argument("--motif", action="store_true", help="在底片上再叠能量环")
    ap.add_argument("--no-motif", action="store_true")
    ap.add_argument("--title1", default=None)
    ap.add_argument("--title2", default=None)
    ap.add_argument("--subtitle", default=None)
    ap.add_argument("--kicker", default=None)
    args = ap.parse_args()

    text = dict(DEFAULT_TEXT)
    if os.path.isfile(args.config):
        try:
            cfg = json.load(open(args.config, encoding="utf-8"))
            for k in text:
                if cfg.get(k):
                    text[k] = str(cfg[k])
        except Exception:
            pass
    for k in text:
        v = getattr(args, k, None)
        if v:
            text[k] = v

    source = pick_source(args.source)
    motif = args.motif
    os.makedirs(args.out, exist_ok=True)
    compose(1920, 1080, 112, os.path.join(args.out, "cover-16x9.jpg"), "wide",
            text, source, motif)
    compose(1080, 1080, 88, os.path.join(args.out, "cover-1x1.jpg"), "square",
            text, source, motif)
    compose(1080, 1440, 94, os.path.join(args.out, "cover-3x4.jpg"), "tall",
            text, source, motif)
    if not source:
        print("（无成片静帧可用，使用程序化能量环底）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
