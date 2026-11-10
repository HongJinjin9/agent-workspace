#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第 03 期《AI 时代最贵的债，是判断力》程序化纹理生成
====================================================
输出（assets/textures/，全部可由本脚本复现）：
  paper_white.png   2400x3400  冷白纸面：纸纤维、轻微污渍斑点、边缘压痕
  paper_warm.png    2400x3400  暖纸黄纸面（台灯下 / 旧账单 / 欠条用纸）
  desk_wood.png     2400x3400  深色木纹桌面，带木纹走向与拼板缝
  paper_stack.png   2400x3400  一叠纸的侧边（纸张厚度质感）
  seal_red.png      1600x1600  朱红方形印章：外双线框 + 中央「判断力」，做旧残缺，透明底
  stamp_wait.png    1400x1400  圆形「待核验」印，透明底
  stamp_paid.png    1400x1400  圆形「已核验」印，透明底

视觉基调：暗调、低饱和；纸=暖纸黄，屏幕=靛蓝冷青，朱红只用于印章/关键标记。
生成后会把 textures 段合并进 assets/manifest.json。

用法：
    python3 gen_textures.py
    python3 gen_textures.py --force   # 覆盖已有文件
依赖：numpy、scipy、Pillow，字体 NotoSerif/NotoSans CJK SC（系统自带）
"""
import os
import time
import json
import argparse

import numpy as np
from scipy.ndimage import gaussian_filter
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = "/app/vedio/ep03-judgment"
ASSETS = os.path.join(ROOT, "assets")
TEX = os.path.join(ASSETS, "textures")

FONT_SERIF = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc"
FONT_SANS = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
FONT_INDEX_SC = 2  # TTC 内简体中文索引

PAPER_W, PAPER_H = 2400, 3400
SEAL_SIZE = 1600
STAMP_SIZE = 1400

RED = np.array([0.66, 0.115, 0.095], dtype=np.float32)  # 朱红（略旧）


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def font(size, serif=True):
    return ImageFont.truetype(FONT_SERIF if serif else FONT_SANS, size, index=FONT_INDEX_SC)


# ---------------------------------------------------------------- 噪声工具


def smooth_noise(shape, sigma, rng):
    """大尺度平滑噪声：低分辨率随机格 + 双三次放大，避免大 sigma 高斯滤波过慢。"""
    h, w = shape
    sy, sx = (sigma, sigma) if not isinstance(sigma, (tuple, list)) else sigma
    ch = max(2, int(round(h / max(1.0, sy / 2.0))) + 2)
    cw = max(2, int(round(w / max(1.0, sx / 2.0))) + 2)
    grid = rng.standard_normal((ch, cw)).astype(np.float32)
    im = Image.fromarray(grid, mode="F").resize((w, h), Image.BICUBIC)
    n = np.asarray(im, dtype=np.float32).copy()
    n -= n.mean()
    n /= n.std() + 1e-6
    return n


def fine_noise(shape, sigma, rng):
    """小尺度噪声：全分辨率高斯滤波。"""
    n = rng.standard_normal(shape).astype(np.float32)
    n = gaussian_filter(n, sigma, mode="reflect")
    n -= n.mean()
    n /= n.std() + 1e-6
    return n


def fbm(shape, sigma, octaves=3, persistence=0.5, rng=None, aniso=None):
    """分形平滑噪声，均值≈0、std≈1。sigma 可为标量或 (sy, sx)。"""
    rng = rng or np.random.default_rng(0)
    sig = sigma if isinstance(sigma, (tuple, list)) else (sigma, sigma)
    total = np.zeros(shape, np.float32)
    amp = 1.0
    norm = 0.0
    for _ in range(octaves):
        if max(sig) >= 3.0:
            n = smooth_noise(shape, sig, rng)
        else:
            n = fine_noise(shape, sig, rng)
        total += amp * n
        norm += amp
        amp *= persistence
        sig = (max(0.55, sig[0] / 2.3), max(0.55, sig[1] / 2.3))
    return total / norm


def clamp01(x):
    return np.clip(x, 0.0, 1.0)


def smoothstep(e0, e1, x):
    t = clamp01((x - e0) / (e1 - e0 + 1e-9))
    return t * t * (3 - 2 * t)


def sparse_blobs(shape, count, sigma, rng, amp=1.0):
    """稀疏随机点高斯模糊 → 平滑斑块场（均值≈0）。"""
    h, w = shape
    z = np.zeros((h, w), np.float32)
    ys = rng.integers(0, h, count)
    xs = rng.integers(0, w, count)
    z[ys, xs] = rng.uniform(0.4, 1.0, count).astype(np.float32) * amp
    z = gaussian_filter(z, sigma, mode="reflect")
    return z / (z.std() + 1e-6)


def to_img(arr):
    return Image.fromarray((clamp01(arr) * 255.0 + 0.5).astype(np.uint8), "RGB")


# ---------------------------------------------------------------- 纸张


def make_paper(warm=False, seed=7):
    h, w = PAPER_H, PAPER_W
    rng = np.random.default_rng(seed)
    if warm:
        base = np.array([0.925, 0.845, 0.700], dtype=np.float32)  # 暖纸黄
    else:
        base = np.array([0.955, 0.947, 0.922], dtype=np.float32)  # 冷白纸（干净、可被灯光染色）

    # 大尺度不匀（受潮/受光不均） + 中尺度云斑
    lowfreq = fbm((h, w), 170, 3, rng=rng)
    midfreq = fbm((h, w), 26, 3, rng=rng)
    # 纸纤维（横向拉伸）+ 细颗粒
    fiber = fbm((h, w), (1.0, 5.0), 3, persistence=0.6, rng=rng)
    grain = fbm((h, w), 0.7, 2, rng=rng)

    luma = 1.0 + (0.026 if warm else 0.016) * lowfreq + (0.014 if warm else 0.009) * midfreq + 0.008 * fiber + 0.006 * grain
    c = base[None, None, :] * luma[..., None]

    # 轻微污渍斑点（3-7 个，黄褐/灰褐）
    n_stains = int(rng.integers(3, 8))
    stain_field = np.zeros((h, w), np.float32)
    for _ in range(n_stains):
        cy, cx = rng.uniform(0.05, 0.95) * h, rng.uniform(0.05, 0.95) * w
        ry, rx = rng.uniform(60, 260), rng.uniform(60, 260)
        Y = np.arange(h, dtype=np.float32)[:, None]
        X = np.arange(w, dtype=np.float32)[None, :]
        g = np.exp(-(((Y - cy) / ry) ** 2 + ((X - cx) / rx) ** 2) * 0.5)
        stain_field += g * rng.uniform(0.10, 0.30)
    stain_field = gaussian_filter(stain_field, 18, mode="reflect")
    stain_field /= stain_field.max() + 1e-6
    stain_col = np.array([0.62, 0.52, 0.36], np.float32) if warm else np.array([0.60, 0.55, 0.45], np.float32)
    st = (stain_field * (0.15 if warm else 0.09))[..., None]
    c = c * (1 - st) + stain_col[None, None, :] * st

    # 极细墨点/杂点（旧纸的微尘）
    speck = np.zeros((h, w), np.float32)
    k = int(h * w / 9000)
    ys = rng.integers(0, h, k)
    xs = rng.integers(0, w, k)
    speck[ys, xs] = rng.uniform(0.2, 1.0, k)
    speck = gaussian_filter(speck, 0.55, mode="reflect")
    c = c * (1 - np.clip(speck * 1.5, 0, 1) * 0.10)[..., None]

    # 边缘压痕：四边向内缓慢变暗 + 极边缘一道细暗线（纸边磨脏）
    Y = np.arange(h, dtype=np.float32)[:, None]
    X = np.arange(w, dtype=np.float32)[None, :]
    d_edge = np.minimum(np.minimum(X, w - 1 - X), np.minimum(Y, h - 1 - Y))
    edge_wobble = fbm((h, w), 90, 2, rng=rng) * 5.0
    dd = np.maximum(d_edge + edge_wobble, 0)
    edge_shade = 1.0 - 0.11 * np.exp(-dd / 55.0) - 0.10 * np.exp(-dd / 3.0)
    c = c * edge_shade[..., None]

    # 轻微整体暗角（贴近实拍纸面）
    r = np.sqrt(((X - w / 2) / (w / 2)) ** 2 + ((Y - h / 2) / (h / 2)) ** 2)
    vig = 1.0 - 0.10 * clamp01(r) ** 2.2
    c = c * vig[..., None]

    # 暖纸加一点横向帘纹（旧账本纸感）
    if warm:
        lay = 1.0 + 0.0045 * np.sin(Y * (2 * np.pi / 11.0) + lowfreq * 2.0)
        c = c * lay[..., None]

    return to_img(c)


# ---------------------------------------------------------------- 木桌


def make_desk_wood(seed=11):
    h, w = PAPER_H, PAPER_W
    rng = np.random.default_rng(seed)
    dark = np.array([0.070, 0.052, 0.038], np.float32)
    mid = np.array([0.225, 0.150, 0.098], np.float32)
    warm = np.array([0.300, 0.200, 0.120], np.float32)

    lowfreq = fbm((h, w), 210, 3, rng=rng)
    t = clamp01(0.5 + 0.16 * lowfreq)
    c = dark[None, None, :] + (mid - dark)[None, None, :] * t[..., None]

    # 木纹走向：基本沿水平，带 4° 倾斜
    ang = np.deg2rad(4.0)
    Y = np.arange(h, dtype=np.float32)[:, None]
    X = np.arange(w, dtype=np.float32)[None, :]
    u = X * np.cos(ang) + Y * np.sin(ang)   # 顺纹方向
    v = -X * np.sin(ang) + Y * np.cos(ang)  # 跨纹方向

    warp = fbm((h, w), 150, 3, rng=rng) * 11.0 + fbm((h, w), 9, 2, rng=rng) * 2.2
    rings = np.sin((v + warp) * (2 * np.pi / 28.0))
    fine = fbm((h, w), (1.2, 22.0), 3, persistence=0.55, rng=rng)  # 长条细纹
    pores = fbm((h, w), (0.8, 2.6), 2, rng=rng)

    grain = 0.5 + 0.5 * rings
    c = c * (0.70 + 0.46 * grain)[..., None]
    c = c + (warm - mid)[None, None, :] * (0.26 * clamp01(fine * 0.5 + 0.5))[..., None]
    c = c * (1.0 + 0.04 * pores)[..., None]

    # 拼板缝（两条横向暗缝 + 一条竖向短缝）
    def seam(y, thickness=2.2, strength=0.55):
        nonlocal c
        yy = np.abs(Y - y)
        line = np.exp(-(yy ** 2) / (2 * thickness ** 2))
        line = line * (1.0 + 0.5 * fbm((h, w), (0.6, 30.0), 2, rng=rng))
        c = c * (1.0 - strength * line)[..., None]
        # 缝旁高光
        hi = np.exp(-((yy - 3.0) ** 2) / (2 * 1.6 ** 2))
        c = c + np.array([0.020, 0.012, 0.006], np.float32)[None, None, :] * hi[..., None] * 0.5

    seam(h * 0.36)
    seam(h * 0.72)
    # 竖缝（x≈0.63，仅下半段）
    xseam = np.exp(-((X - w * 0.63) ** 2) / (2 * 2.0 ** 2)) * smoothstep(h * 0.52, h * 0.62, Y)
    c = c * (1.0 - 0.35 * xseam)[..., None]

    # 划痕/裂纹若干
    scratch = np.zeros((h, w), np.float32)
    for _ in range(7):
        x = rng.uniform(0.05, 0.95) * w
        y = rng.uniform(0.05, 0.95) * h
        length = rng.uniform(80, 420)
        dy = rng.uniform(-0.25, 0.25)
        ys = np.linspace(0, length, int(length))
        xs = x + ys * rng.uniform(-0.08, 0.08)
        yy = y + ys
        ok = (yy > 1) & (yy < h - 2) & (xs > 1) & (xs < w - 2)
        scratch[yy[ok].astype(int), xs[ok].astype(int)] = rng.uniform(0.4, 0.9)
    scratch = gaussian_filter(scratch, 0.8, mode="reflect")
    c = c * (1.0 - 0.30 * clamp01(scratch))[..., None]

    # 从左上方来的柔和桌面高光
    sheen = 0.10 * smoothstep(1.25, 0.15, np.sqrt(((X - w * 0.18) / (w * 0.85)) ** 2 + ((Y - h * 0.10) / (h * 0.75)) ** 2))
    c = c + sheen[..., None] * np.array([0.9, 0.65, 0.42], np.float32)[None, None, :] * 0.35

    # 暗角
    r = np.sqrt(((X - w / 2) / (w / 2)) ** 2 + ((Y - h / 2) / (h / 2)) ** 2)
    c = c * (1.0 - 0.30 * clamp01(r) ** 1.8)[..., None]
    return to_img(c)


# ---------------------------------------------------------------- 纸叠侧边


def make_paper_stack(seed=23):
    h, w = PAPER_H, PAPER_W
    rng = np.random.default_rng(seed)
    Y = np.arange(h, dtype=np.float32)[:, None]
    X = np.arange(w, dtype=np.float32)[None, :]

    sheet = 26.0  # 每张纸侧面厚度（px）→ 全高约 130 张，视频尺寸下仍可读出层次
    phase = Y / sheet
    idx = np.floor(phase).astype(np.int64)
    frac = phase - idx
    n_sheets = int(phase.max()) + 8
    # 每张纸亮度略有差异（相邻纸张相关，像真实纸叠）
    sheet_var = rng.normal(0.0, 1.0, n_sheets).astype(np.float32)
    sheet_var = gaussian_filter(sheet_var, 1.5, mode="reflect")
    luma = 0.93 + 0.06 * np.take(sheet_var, idx, axis=0)
    # 每张纸的剖面：上缘受光、下缘进阴影
    prof = 0.76 + 0.28 * (1.0 - frac) ** 1.1
    base_col = np.array([0.930, 0.900, 0.840], np.float32)  # 暖白纸边
    c = base_col[None, None, :] * (luma * prof)[..., None]

    # 纸纤维（沿水平方向拉伸）+ 细颗粒
    fiber = fbm((h, w), (0.8, 7.0), 3, persistence=0.55, rng=rng)
    fine = fbm((h, w), (0.6, 1.8), 2, rng=rng)
    c = c * (1.0 + 0.035 * fiber + 0.012 * fine)[..., None]
    # 纸与纸之间的阴影缝（每张纸顶部一条细暗线）
    gap = np.exp(-((frac * sheet) ** 2) / (2 * 1.2 ** 2))
    c = c * (1.0 - 0.34 * gap)[..., None]
    # 个别纸张更暗（旧纸/夹层）
    dark_map = np.take((rng.random(n_sheets) < 0.10).astype(np.float32), idx, axis=0)
    c = c * (1.0 - 0.15 * dark_map)[..., None]
    # 横向轻微起伏（纸堆不齐）
    bulge = 1.0 + 0.055 * np.cos((X / w - 0.5) * np.pi * 1.35)
    c = c * bulge[..., None]
    # 底部进阴影
    c = c * (1.0 - 0.18 * smoothstep(0.50, 1.0, Y / h))[..., None]
    # 顶部 7.5% 为叠层顶面（暖亮），再往上渐隐到暗背景
    top = smoothstep(0.075, 0.030, Y / h)
    c = c * (1 - top[..., None]) + np.array([0.80, 0.755, 0.675], np.float32)[None, None, :] * (top * 0.95)[..., None]
    c = c * (1.0 - 0.90 * smoothstep(0.020, 0.0, Y / h))[..., None]
    # 左右两侧暗部
    c = c * (1.0 - 0.22 * smoothstep(0.55, 1.0, np.abs(X / w - 0.5) * 2)[..., None])
    return to_img(c)


# ---------------------------------------------------------------- 印章工具


def rough_circle_mask(size, radius, width, rng, irregular=4.0):
    """粗糙圆环（手刻/印泥边缘不规则），L 模式。"""
    big = 4
    im = Image.new("L", (size * big, size * big), 0)
    d = ImageDraw.Draw(im)
    n = 720
    th = np.linspace(0, 2 * np.pi, n, endpoint=False)
    k = 12
    knots = rng.normal(0, irregular, k)
    jit = np.interp(
        np.linspace(0, 1, n, endpoint=False),
        np.linspace(0, 1, k, endpoint=False),
        knots,
        period=1.0,
    )
    ctr = size * big / 2.0
    pts = [
        (ctr + (radius + jit[i]) * big * np.cos(th[i]),
         ctr + (radius + jit[i]) * big * np.sin(th[i]))
        for i in range(n)
    ]
    pts.append(pts[0])
    d.line(pts, fill=255, width=int(width * big), joint="curve")
    return im.resize((size, size), Image.LANCZOS)


def rough_rect_mask(size, frames, rng, irregular=1.3):
    """粗糙矩形框（frames：[(边距px, 线宽px), ...]），L 模式。"""
    big = 4
    im = Image.new("L", (size * big, size * big), 0)
    d = ImageDraw.Draw(im)
    for mgn, wd in frames:
        step = 9
        x0 = y0 = mgn * big
        x1 = y1 = (size - mgn) * big
        pts = []
        for x in np.arange(x0, x1, step):
            pts.append((x, y0 + rng.normal(0, irregular * big)))
        for y in np.arange(y0, y1, step):
            pts.append((x1 + rng.normal(0, irregular * big), y))
        for x in np.arange(x1, x0, -step):
            pts.append((x, y1 + rng.normal(0, irregular * big)))
        for y in np.arange(y1, y0, -step):
            pts.append((x0 + rng.normal(0, irregular * big), y))
        pts.append(pts[0])
        d.line(pts, fill=255, width=int(wd * big), joint="curve")
    return im.resize((size, size), Image.LANCZOS)


def glyph_mask(ch, size, stroke=0, rotate=0.0, jitter=(0, 0)):
    """渲染文字（单字或短句）到 L 掩膜，裁到墨迹边界。"""
    f = font(size, serif=True)
    probe = ImageDraw.Draw(Image.new("L", (8, 8)))
    bbox = probe.textbbox((0, 0), ch, font=f, stroke_width=stroke, anchor="mm")
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad = int(size * 0.55) + 8
    cw = max(size * 2, tw + 2 * pad)
    chh = max(size * 2, th + 2 * pad)
    im = Image.new("L", (cw, chh), 0)
    d = ImageDraw.Draw(im)
    d.text((cw // 2, chh // 2), ch, font=f, fill=255, anchor="mm",
           stroke_width=stroke, stroke_fill=255)
    if rotate:
        im = im.rotate(rotate, resample=Image.BICUBIC)
    arr = np.asarray(im)
    ys, xs = np.where(arr > 8)
    if len(xs) == 0:
        return im
    return im.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))


def paste_centered(dst_mask, glyph, cx, cy):
    dst_mask.paste(glyph, (int(cx - glyph.width / 2), int(cy - glyph.height / 2)), glyph)


def inkify(mask, rng, wear=1.0):
    """把干净掩膜变成印泥：浓淡不均、残缺、边缘毛糙。返回 (alpha uint8, density)。"""
    m = np.asarray(mask, np.float32) / 255.0
    h, w = m.shape
    # 印泥浓淡（大块斑驳，像印泥蘸得不匀）
    mottle = 0.5 + 0.5 * np.tanh(fbm((h, w), 18.0, 3, rng=rng) * 1.25)
    density = clamp01(0.63 + 0.45 * mottle) * wear
    # 细颗粒（纸面吃墨不匀，颗粒稍粗以免变成数字噪点）
    fine = 0.5 + 0.5 * np.tanh(fbm((h, w), 3.2, 2, rng=rng) * 1.4)
    alpha = m * density * (0.93 + 0.07 * fine)
    # 残缺：低频空洞 + 极少量针孔
    holes_low = fbm((h, w), 20.0, 2, rng=rng)
    alpha = alpha * (1.0 - 0.45 * smoothstep(1.0, 2.4, holes_low))
    pin = fbm((h, w), 1.8, 1, rng=rng)
    alpha = alpha * np.where(pin < -2.9, 0.0, 1.0).astype(np.float32)
    # 边缘毛糙：轻度模糊后再乘掩膜，保留断口
    soft = gaussian_filter(alpha, 1.5, mode="reflect")
    alpha = np.maximum(alpha * 0.93, soft * 0.32)
    alpha = clamp01(alpha)
    density = clamp01(density)
    return (alpha * 255).astype(np.uint8), density


def ink_color(alpha, density, rng, base=RED):
    """印泥颜色：浓处偏暗朱红，淡处偏砖红；带轻微色不均。"""
    h, w = alpha.shape
    var = 0.5 + 0.5 * np.tanh(fbm((h, w), 3.0, 2, rng=rng) * 1.5)
    d = clamp01(0.45 * density + 0.55 * var)
    dark = np.array([0.455, 0.055, 0.045], np.float32)
    light = np.array([0.700, 0.145, 0.115], np.float32)
    rgb = dark[None, None, :] + (light - dark)[None, None, :] * d[..., None]
    rgb = rgb * (0.90 + 0.18 * d[..., None])
    out = np.zeros((h, w, 4), np.uint8)
    out[..., :3] = (clamp01(rgb) * 255).astype(np.uint8)
    out[..., 3] = alpha
    return Image.fromarray(out, "RGBA")


def make_seal(seed=31):
    size = SEAL_SIZE
    rng = np.random.default_rng(seed)
    # 外双线框（外粗内细）
    frames = [(size * 0.055, size * 0.026), (size * 0.115, size * 0.012)]
    mask = rough_rect_mask(size, frames, rng)

    # 中央竖排「判断力」，字号按版面分配
    chars = "判断力"
    fsize = int(size * 0.215)
    glyphs = []
    for i, ch in enumerate(chars):
        g = glyph_mask(ch, fsize, stroke=max(2, int(fsize * 0.045)),
                       rotate=float(rng.normal(0, 2.2)))
        glyphs.append(g)
    total_h = sum(g.height for g in glyphs) + int(fsize * 0.28) * (len(glyphs) - 1)
    y = (size - total_h) / 2
    for g in glyphs:
        paste_centered(mask, g, size / 2 + rng.normal(0, 2.0), y + g.height / 2)
        y += g.height + int(fsize * 0.28)

    # 右下角小字「鉴」点缀（做旧方印的边款感）
    small = glyph_mask("鉴", int(size * 0.055), stroke=1, rotate=2.0)
    paste_centered(mask, small, size - int(size * 0.195), size - int(size * 0.195))

    alpha, density = inkify(mask, rng, wear=1.0)
    img = ink_color(alpha, density, rng)
    # 轻微旋转，模拟手盖章的歪斜
    img = img.rotate(-2.2, resample=Image.BICUBIC, expand=False)
    return img


def make_circle_stamp(text, sub, seed=41):
    size = STAMP_SIZE
    rng = np.random.default_rng(seed)
    c = size / 2
    ring1 = rough_circle_mask(size, size * 0.435, size * 0.020, rng, irregular=3.2)
    ring2 = rough_circle_mask(size, size * 0.385, size * 0.009, rng, irregular=2.4)
    mask = Image.fromarray(np.maximum(np.asarray(ring1), np.asarray(ring2)), "L")

    # 顶部弧形文字（从左到右沿弧排布，字随弧线旋转）
    n = len(text)
    arc_r = size * 0.315
    spread = np.deg2rad(32.0)
    fsize = int(size * 0.150)
    for i, ch in enumerate(text):
        a = (i - (n - 1) / 2) * (2 * spread / max(1, n - 1))  # 0 = 正上方
        cx = c + arc_r * np.sin(a)
        cy = c - arc_r * np.cos(a)
        g = glyph_mask(ch, fsize, stroke=max(2, int(fsize * 0.05)),
                       rotate=float(np.rad2deg(a)))
        paste_centered(mask, g, cx, cy)

    # 底部小字
    sub_f = int(size * 0.052)
    g = glyph_mask(sub, sub_f, stroke=1)
    paste_centered(mask, g, c, c + size * 0.285)

    # 中央细横线 + 小菱形装饰
    d = ImageDraw.Draw(mask)
    d.line([(c - size * 0.10, c + size * 0.225), (c + size * 0.10, c + size * 0.225)],
           fill=255, width=max(2, int(size * 0.005)))
    d.polygon([(c, c - size * 0.055), (c + size * 0.033, c),
               (c, c + size * 0.055), (c - size * 0.033, c)], fill=255)

    alpha, density = inkify(mask, rng, wear=1.0)
    return ink_color(alpha, density, rng)


# ---------------------------------------------------------------- 主流程

TEXTURE_META = [
    ("paper_white.png", "冷白纸面（纸纤维/污渍/边缘压痕）", "生成账单、核验账单的纸面底纹；冷白纸用于屏幕光环境"),
    ("paper_warm.png", "暖纸黄纸面（旧纸/帘纹/边缘压痕）", "判断力欠条、旧账单、台灯下纸面；暖纸黄 = 人的判断"),
    ("desk_wood.png", "深色木纹桌面（木纹走向 + 拼板缝）", "3D 桌面/纸张投影的背景板，承载暖色台灯区域"),
    ("paper_stack.png", "一叠纸的侧边（纸张厚度）", "3D 纸张/账本堆叠的侧面质感，做纸张厚度与体积感"),
    ("seal_red.png", "朱红方形「判断力」印章（做旧残缺）", "欠条落印/关键结论落印；全片唯一的高饱和朱红来源"),
    ("stamp_wait.png", "圆形「待核验」印（做旧）", "核验账单未结状态（待核验）"),
    ("stamp_paid.png", "圆形「已核验」印（做旧）", "核验完成/结清状态（已核验）"),
]

TASKS = {
    "paper_white.png": lambda: make_paper(warm=False, seed=7),
    "paper_warm.png": lambda: make_paper(warm=True, seed=19),
    "desk_wood.png": lambda: make_desk_wood(seed=11),
    "paper_stack.png": lambda: make_paper_stack(seed=23),
    "seal_red.png": lambda: make_seal(seed=31),
    "stamp_wait.png": lambda: make_circle_stamp("待核验", "2026.11", seed=41),
    "stamp_paid.png": lambda: make_circle_stamp("已核验", "2026.11", seed=57),
}


def update_manifest(entries):
    path = os.path.join(ASSETS, "manifest.json")
    m = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                m = json.load(f)
        except Exception:
            m = {}
    m.setdefault("episode", "第 03 期《AI 时代最贵的债，是判断力》")
    m["textures"] = entries
    with open(path, "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False, indent=2)
    log(f"manifest 更新 textures：{len(entries)} 项")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only", default=None, help="只生成指定文件名，逗号分隔")
    args = ap.parse_args()
    os.makedirs(TEX, exist_ok=True)
    only = set(args.only.split(",")) if args.only else None

    entries = []
    for fn, cn, use in TEXTURE_META:
        path = os.path.join(TEX, fn)
        if only and fn not in only:
            if os.path.exists(path):
                im = Image.open(path)
                entries.append({"file": f"assets/textures/{fn}", "name_cn": cn,
                                "source": "程序化生成（gen_textures.py）", "license": "自制",
                                "width": im.width, "height": im.height,
                                "mode": im.mode, "use_hint": use})
            continue
        if os.path.exists(path) and not args.force:
            im = Image.open(path)
            log(f"= {fn} 已存在 {im.size}")
        else:
            t0 = time.time()
            im = TASKS[fn]()
            im.save(path)
            log(f"✓ {fn} {im.size} {im.mode}  {time.time()-t0:.1f}s")
            im = Image.open(path)
        entries.append({
            "file": f"assets/textures/{fn}",
            "name_cn": cn,
            "source": "程序化生成（gen_textures.py，numpy/scipy/PIL）",
            "license": "自制",
            "width": im.width,
            "height": im.height,
            "mode": im.mode,
            "use_hint": use,
        })
    update_manifest(entries)
    log("textures 全部完成")


if __name__ == "__main__":
    main()
