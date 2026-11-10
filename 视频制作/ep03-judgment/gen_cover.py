#!/usr/bin/env python3
"""第 03 期封面（9:16 1080×1920 与 3:4 1200×1600）。

沿用片内的纸张/印章/影调语言：暗桌面 + 暖纸 + 朱印 + 大标题。
"""
import os
import sys
import math
import random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import scene_judgment as S

ROOT = os.path.dirname(os.path.abspath(__file__))
F_SERIF_B = S.F_SERIF_B
F_SANS_B = S.F_SANS_B
F_SANS = S.F_SANS
WHITE = (240, 244, 248)
GOLD = (214, 178, 112)
RED = (176, 54, 46)


def ft(p, s):
    from PIL import ImageFont
    return ImageFont.truetype(p, int(s))


def make_cover(w, h, path):
    rng = random.Random(11)
    # 背景：暗桌面 + 暖光斑
    yy, xx = np.ogrid[:h, :w]
    nx = (xx - w * 0.5) / (w * 0.5)
    ny = (yy - h * 0.45) / (h * 0.5)
    warm = np.exp(-(((xx - w * 0.22) ** 2) / (2 * (w * 0.46) ** 2) +
                    ((yy - h * 0.34) ** 2) / (2 * (h * 0.42) ** 2)))
    cool = np.exp(-(((xx - w * 0.90) ** 2) / (2 * (w * 0.36) ** 2) +
                    ((yy - h * 0.18) ** 2) / (2 * (h * 0.30) ** 2)))
    base = np.zeros((h, w, 3), dtype=np.float32)
    base[..., 0] = 10 + warm * 66 + cool * 12
    base[..., 1] = 9 + warm * 44 + cool * 22
    base[..., 2] = 9 + warm * 24 + cool * 40
    noise = np.random.default_rng(3).normal(0, 3.4, (h, w))
    base += noise[..., None]
    im = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8)).convert("RGBA")

    # 桌面上的欠条（右下，做旧）
    paper = S.tex_title_judgment()
    pw = int(w * 0.62)
    ph = int(pw * paper.height / paper.width)
    pim = paper.resize((pw, ph), Image.LANCZOS)
    # 暖光与压暗
    arr = np.asarray(pim.convert("RGB"), dtype=np.float32) * 0.9
    pim = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGBA")
    pim = pim.rotate(-7, expand=True, resample=Image.BICUBIC)
    px = int(w * 0.52 - pim.width / 2)
    py = int(h * 0.52 - pim.height / 2)
    sh = Image.new("RGBA", pim.size, (0, 0, 0, 255))
    sh.putalpha(pim.getchannel("A").point(lambda v: int(v * 0.55)))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(26)), (px + 10, py + 18))
    im.alpha_composite(pim, (px, py))
    # 欠条上的朱印
    st = S.seal().resize((int(pw * 0.34), int(pw * 0.34)), Image.LANCZOS).rotate(-9, expand=True)
    st.putalpha(st.getchannel("A").point(lambda v: int(v * 0.9)))
    im.alpha_composite(st, (px + int(pim.width * 0.50), py + int(pim.height * 0.58)))

    d = ImageDraw.Draw(im)
    # 顶部压暗，保证标题可读
    grad = Image.new("RGBA", (w, int(h * 0.62)), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for i in range(grad.height):
        a = int(200 * (1 - i / grad.height) ** 1.2)
        gd.line((0, i, w, i), fill=(3, 4, 6, a))
    im.alpha_composite(grad, (0, 0))

    # 标题
    title1 = "AI 时代最贵的债"
    title2 = "是判断力"
    f1 = ft(F_SERIF_B, int(w * 0.092))
    f2 = ft(F_SERIF_B, int(w * 0.135))
    f3 = ft(F_SANS, int(w * 0.038))
    tw1 = d.textlength(title1, font=f1)
    tw2 = d.textlength(title2, font=f2)
    ty = int(h * 0.085)
    d.text(((w - tw1) / 2, ty), title1, font=f1, fill=WHITE + (255,), stroke_width=3,
           stroke_fill=(0, 0, 0, 255))
    d.text(((w - tw2) / 2, ty + int(h * 0.052)), title2, font=f2, fill=GOLD + (255,),
           stroke_width=4, stroke_fill=(0, 0, 0, 255))
    sub = "答案越来越便宜，核验却越来越贵"
    tw3 = d.textlength(sub, font=f3)
    d.text(((w - tw3) / 2, ty + int(h * 0.158)), sub, font=f3, fill=(212, 208, 200, 235),
           stroke_width=2, stroke_fill=(0, 0, 0, 255))

    # 底部系列标签 + AI 声明
    f4 = ft(F_SANS, int(w * 0.030))
    label = "第 03 期 · 判断力债务"
    d.text(((w - d.textlength(label, font=f4)) / 2, int(h * 0.935)), label, font=f4,
           fill=(190, 186, 178, 235), stroke_width=2, stroke_fill=(0, 0, 0, 255))

    # 颗粒与暗角
    arr = np.asarray(im.convert("RGB"), dtype=np.float32) / 255.0
    yy2, xx2 = np.ogrid[:h, :w]
    nx2 = (xx2 - w / 2) / (w / 2)
    ny2 = (yy2 - h / 2) / (h / 2)
    dd = np.sqrt(nx2 ** 2 + ny2 ** 2) / 1.414
    arr *= np.clip(1 - 0.55 * dd ** 2.1, 0, 1)[:, :, None]
    out = Image.fromarray(np.clip(arr * 255, 0, 255).astype(np.uint8))
    out.save(path, quality=94)
    print("cover", path, out.size)


def main():
    os.makedirs(os.path.join(ROOT, "delivery"), exist_ok=True)
    make_cover(1080, 1920, os.path.join(ROOT, "delivery", "cover-9x16.jpg"))
    make_cover(1200, 1600, os.path.join(ROOT, "delivery", "cover-3x4.jpg"))


if __name__ == "__main__":
    main()
