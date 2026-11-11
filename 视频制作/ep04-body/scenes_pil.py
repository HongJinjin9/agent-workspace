#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 04 期全画幅程序化场景（数据/英雄镜头）。

每个场景签名 `def scene_xxx(t, dur, sh) -> PIL.Image`，t 为镜头内局部时间。
底片来自 assets（Pexels 实拍抽帧），数据图形用真实数学函数生成：
- S2 阻尼：1/4 车二自由度模型 RK4 积分（车身 ≈1.4Hz、车轮 ≈12.7Hz、ζ≈0.24）；
- S3 信息线：一阶平滑 + 断崖；
- S4 jerk：加速度阶跃/斜坡的解析导数；
- S5 合流：三条曲线 → 合成心跳（P-QRS-T 高斯叠加）。
"""
import math
import os
import subprocess

import cv2
import numpy as np

import ep04assets as A
import ep04viz as V
from ep04viz import (W, H, BAR, SAFE_T, SAFE_B, INK, INK2, BONE, MUTED, DIM, TEAL, TEAL_D,
                     AMBER, GOLD, EMBER, ICE, WHITE, F_SERIF, F_SERIF_R, F_SANS, F_SANS_R,
                     F_MONO, clamp, lerp, ease_in_out, ease_out_cubic, ease_in_cubic,
                     smoothstep, window, damped_osc, two_dof_quarter_car)

ROOT = "/app/vedio/ep04-body"
FFMPEG = "/home/admin/.local/bin/ffmpeg"

_GRID = None


def grid():
    global _GRID
    if _GRID is None:
        yy, xx = np.ogrid[:H, :W]
        _GRID = ((xx.astype(np.float32) / W), (yy.astype(np.float32) / H))
    return _GRID


# ------------------------------------------------------------------ backgrounds
def studio_bg(t, dur, tint=(0.42, 0.78, 0.86), strength=0.10, glow_xy=(0.5, 0.48),
              base=(0.026, 0.034, 0.044), drift=0.012):
    nx, ny = grid()
    gx = glow_xy[0] + drift * math.sin(t * 0.35 + 0.6)
    gy = glow_xy[1] + drift * 0.4 * math.cos(t * 0.27)
    g = np.exp(-(((nx - gx) ** 2) / (0.62 ** 2) + ((ny - gy) ** 2) / (0.52 ** 2))) * strength
    rgb = np.array(base, np.float32)[None, None, :] + g[..., None] * np.array(tint, np.float32)
    return rgb


def plate_bg(t, dur, key, sec, dark=0.62, tint=(0.70, 0.86, 1.05), blur=6.0,
             zoom0=1.05, drift=0.05, cx=0.5, cy=0.5):
    path = A.ensure_plate(key, sec)
    zoom = zoom0 + drift * clamp(t / max(dur, 1e-3))
    return V.plate_frame(path, zoom=zoom, cx=cx, cy=cy, dark=dark, tint=tint, blur=blur)


# ------------------------------------------------------------------ primitives
def leader(p, a, b, color=MUTED, alpha=0.55, width=1.0, elbow=None):
    pts = [a]
    if elbow:
        pts.append(elbow)
    pts.append(b)
    p.stroke(pts, color, width, alpha, 4, 0.25)
    p.dot(b, 2.4, color, alpha)


def draw_wheel(p, cx, cy, r, alpha=1.0, rim_color=MUTED, tire_color=DIM, spokes=5,
               stationary=False):
    """侧视轮胎：厚胎壁 + 胎面纹 + 轮辋 + 轮辐 + 弧面高光。"""
    p.fill_circle((cx, cy), r, (24, 29, 35), 0.97 * alpha)
    p.fill_circle((cx, cy), r * 0.88, (34, 40, 48), 0.97 * alpha)
    # 胎壁高光弧（左上）
    arc = np.linspace(math.pi * 1.02, math.pi * 1.42, 40)
    p.stroke(np.stack([cx + r * 0.95 * np.cos(arc), cy + r * 0.95 * np.sin(arc)], 1),
             (96, 108, 120), 2.0, 0.55 * alpha, 8, 0.3)
    # 胎面纹（径向短线）
    for k in range(40):
        ang = 2 * math.pi * k / 40
        p.stroke([(cx + r * 0.885 * math.cos(ang), cy + r * 0.885 * math.sin(ang)),
                  (cx + r * 0.985 * math.cos(ang), cy + r * 0.985 * math.sin(ang))],
                 (52, 58, 66), 1.8, 0.55 * alpha)
    # 轮辋
    p.fill_circle((cx, cy), r * 0.63, (14, 18, 24), 0.96 * alpha)
    p.stroke([(cx + r * 0.63 * math.cos(a), cy + r * 0.63 * math.sin(a))
              for a in np.linspace(0, 2 * math.pi, 90)], rim_color, 2.4, 0.8 * alpha)
    p.stroke([(cx + r * 0.55 * math.cos(a), cy + r * 0.55 * math.sin(a))
              for a in np.linspace(0, 2 * math.pi, 80)], rim_color, 1.0, 0.30 * alpha)
    # 轮辐
    for k in range(spokes):
        ang = 2 * math.pi * k / spokes + 0.25
        p.stroke([(cx + r * 0.16 * math.cos(ang), cy + r * 0.16 * math.sin(ang)),
                  (cx + r * 0.60 * math.cos(ang), cy + r * 0.60 * math.sin(ang))],
                 rim_color, 2.4, 0.55 * alpha, 4, 0.2)
    p.fill_circle((cx, cy), r * 0.15, (10, 13, 17), 0.95 * alpha)
    p.stroke([(cx + r * 0.15 * math.cos(a), cy + r * 0.15 * math.sin(a))
              for a in np.linspace(0, 2 * math.pi, 40)], rim_color, 2.0, 0.7 * alpha)


def draw_spring(p, x, y0, y1, coil=34, coils=9, color=TEAL, alpha=1.0, width=2.0):
    n = coils * 18
    ys = np.linspace(y0, y1, n)
    xs = x + coil * np.sin(np.linspace(0, coils * 2 * math.pi, n))
    p.stroke(np.stack([xs, ys], 1), color, width, alpha, 8, 0.5)
    # 上下座
    p.stroke([(x - coil - 6, y0), (x + coil + 6, y0)], color, 2.4, alpha)
    p.stroke([(x - coil - 6, y1), (x + coil + 6, y1)], color, 2.4, alpha)


def draw_damper(p, x, y0, y1, w=16, color=TEAL, alpha=1.0):
    p.stroke([(x - w, y0), (x - w, y1)], color, 2.2, alpha)
    p.stroke([(x + w, y0), (x + w, y1)], color, 2.2, alpha)
    p.stroke([(x - w, y0 + (y1 - y0) * 0.55), (x + w, y0 + (y1 - y0) * 0.55)],
             color, 2.2, alpha * 0.8)
    p.stroke([(x, y0 - 8), (x, y0)], color, 2.0, alpha)


def body_poly(cx, cy, w, h):
    r = min(w, h) * 0.16
    x0, x1 = cx - w / 2, cx + w / 2
    y0, y1 = cy - h / 2, cy + h / 2
    return [(x0 + r, y0), (x1 - r, y0), (x1, y0 + r), (x1, y1 - r), (x1 - r, y1),
            (x0 + r, y1), (x0, y1 - r), (x0, y0 + r)]


def draw_body_block(p, cx, cy, w, h, alpha=1.0, rim=BONE, glass=TEAL):
    poly = body_poly(cx, cy, w, h)
    p.fill_poly(poly, (34, 40, 48), 0.95 * alpha)
    # 顶部高光/底部暗边
    p.stroke([(cx - w / 2 + 8, cy - h / 2 + 2), (cx + w / 2 - 8, cy - h / 2 + 2)],
             rim, 2.2, 0.55 * alpha, 10, 0.35)
    p.stroke([(cx - w / 2 + 10, cy + h / 2 - 2), (cx + w / 2 - 10, cy + h / 2 - 2)],
             (60, 70, 80), 1.6, 0.6 * alpha)
    # 侧窗/反光条
    p.stroke([(cx - w * 0.28, cy - h * 0.08), (cx + w * 0.22, cy - h * 0.10)],
             glass, 1.6, 0.30 * alpha, 8, 0.3)


def draw_person(p, cx, base_y, hgt, alpha=1.0, rim=TEAL, fill=(8, 12, 17),
                ghost=False):
    """抽象坐姿人体侧影（无面部）：座椅 + 坐姿人形，侧向朝左。"""
    h = hgt
    hip = (cx - 0.02 * h, base_y - 0.44 * h)
    # 座椅：靠背（略后倾）+ 坐垫 + 支脚
    seat_col = (26, 31, 38) if not ghost else (14, 17, 21)
    p.fill_poly([(cx + 0.055 * h, base_y - 0.10 * h), (cx + 0.145 * h, base_y - 0.10 * h),
                 (cx + 0.115 * h, base_y - 0.86 * h), (cx + 0.055 * h, base_y - 0.82 * h)],
                seat_col, 0.95 * alpha)
    p.fill_poly([(cx - 0.20 * h, base_y - 0.38 * h), (cx + 0.14 * h, base_y - 0.38 * h),
                 (cx + 0.13 * h, base_y - 0.48 * h), (cx - 0.19 * h, base_y - 0.46 * h)],
                seat_col, 0.95 * alpha)
    p.stroke([(cx + 0.10 * h, base_y - 0.10 * h), (cx + 0.10 * h, base_y)], (44, 50, 58),
             2.0, 0.7 * alpha)
    # 人体：头 / 躯干 / 手臂 / 大腿 / 小腿
    head_r = 0.072 * h
    head = (cx - 0.035 * h, base_y - 0.955 * h)
    p.fill_circle(head, head_r, fill, 0.98 * alpha)
    p.fill_poly([(cx - 0.085 * h, base_y - 0.885 * h), (cx + 0.02 * h, base_y - 0.885 * h),
                 (cx + 0.055 * h, base_y - 0.46 * h), (cx - 0.09 * h, base_y - 0.44 * h)],
                fill, 0.98 * alpha)  # 躯干
    p.fill_poly([(cx + 0.005 * h, base_y - 0.86 * h), (cx + 0.045 * h, base_y - 0.80 * h),
                 (cx - 0.03 * h, base_y - 0.46 * h), (cx - 0.075 * h, base_y - 0.50 * h)],
                fill, 0.98 * alpha)  # 手臂
    p.fill_poly([(cx - 0.075 * h, base_y - 0.47 * h), (cx + 0.07 * h, base_y - 0.47 * h),
                 (cx - 0.14 * h, base_y - 0.30 * h), (cx - 0.18 * h, base_y - 0.34 * h)],
                fill, 0.98 * alpha)  # 大腿
    p.fill_poly([(cx - 0.18 * h, base_y - 0.34 * h), (cx - 0.13 * h, base_y - 0.30 * h),
                 (cx - 0.12 * h, base_y), (cx - 0.17 * h, base_y)], fill, 0.98 * alpha)  # 小腿
    p.fill_poly([(cx - 0.20 * h, base_y), (cx - 0.10 * h, base_y - 0.01 * h),
                 (cx - 0.10 * h, base_y - 0.045 * h), (cx - 0.205 * h, base_y - 0.035 * h)],
                fill, 0.95 * alpha)  # 足
    if not ghost:
        # 轮廓光：头-肩-背-腿（右缘/后缘）
        p.stroke([(head[0] + head_r * 0.9, head[1] - head_r * 0.3),
                  (cx + 0.02 * h, base_y - 0.885 * h),
                  (cx + 0.055 * h, base_y - 0.46 * h),
                  (cx + 0.07 * h, base_y - 0.47 * h),
                  (cx - 0.13 * h, base_y - 0.30 * h),
                  (cx - 0.12 * h, base_y - 0.02 * h)],
                 rim, 1.5, 0.42 * alpha, 10, 0.35)
        # 地面接触阴影
        p.stroke([(cx - 0.26 * h, base_y + 4), (cx + 0.16 * h, base_y + 4)], (30, 36, 42),
                 3.0, 0.5 * alpha)


def axis(p, x0, y0, x1, y1, color=MUTED, alpha=0.4):
    p.stroke([(x0, y0), (x1, y0)], color, 1.0, alpha)
    p.stroke([(x0, y0), (x0, y1)], color, 1.0, alpha)
    return p


def dashed_hline(p, x0, x1, y, color=EMBER, alpha=0.5):
    for seg in V.dashed(np.array([[x0, y], [x1, y]]), 16, 11):
        p.stroke(seg, color, 1.1, alpha, 4, 0.25)


def _gauss(x, mu, sig):
    return np.exp(-((x - mu) ** 2) / (2 * sig * sig))


# ------------------------------------------------------------------ S1 cold / intro
def scene_cold_title(t, dur, sh):
    bg = plate_bg(t, dur, "car_interior_night", 2.0, dark=0.52,
                  tint=(0.62, 0.84, 1.08), blur=2.4, zoom0=1.03, drift=0.05)
    p = V.Painter(bg)
    # 三条预示曲线（低透明度）
    for k, (col, fn) in enumerate([
            (TEAL, lambda x: 18 * math.exp(-1.3 * x) * math.sin(3.6 * x * math.pi)),
            (AMBER, lambda x: -20 * smoothstep(0.1, 0.8, x))]):
        grow = clamp((t - 1.25 - k * 0.18) / 1.3)
        if grow <= 0:
            continue
        n = max(2, int(160 * grow))
        xs = np.linspace(0, 1, n)
        px = 300 + 1320 * xs
        py = 800 - np.array([fn(x) for x in xs])
        p.stroke(np.stack([px, py], 1), col, 1.5, 0.38, 10, 0.4)
    p.flush()
    # 文案
    a = window(t, 0.35, dur - 0.05, 0.5, 0.45)
    V.draw_text(p.rgb, "VIBE 知识共赏 · 第 04 期", (960, 392), 26, MUTED, F_SANS_R,
                anchor="mm", alpha=0.75 * a, track=4)
    a2 = window(t, 0.5, dur - 0.05, 0.65, 0.45)
    rise = 16 * (1 - ease_out_cubic(clamp((t - 0.5) / 0.8)))
    V.draw_text(p.rgb, "你的身体，比参数表更懂车", (960, 486 - rise), 78, BONE, F_SERIF,
                anchor="mm", alpha=0.96 * a2, track=4, glow=16, glow_strength=0.42)
    a3 = window(t, 1.15, dur - 0.05, 0.7, 0.45)
    V.draw_text(p.rgb, "三个说不清的体感，和它们背后的物理", (960, 592), 32, MUTED, F_SANS_R,
                anchor="mm", alpha=0.85 * a3, track=3)
    p.bloom(threshold=0.66, strength=0.5)
    return p.to_image()


def scene_three_intro(t, dur, sh):
    bg = studio_bg(t, dur, tint=(0.40, 0.70, 0.82), strength=0.12, glow_xy=(0.5, 0.52))
    base_plate = plate_bg(t, dur, "city_night_aerial", 1.0, dark=0.70,
                          tint=(0.6, 0.8, 1.0), blur=9.0, zoom0=1.06, drift=0.03)
    bg = bg * 0.45 + base_plate * 0.55
    p = V.Painter(bg)
    p.halo((1000, 690), 560, TEAL, 0.06)
    p.flush()
    lanes = [
        ("阻尼", TEAL, lambda x: 62 * math.exp(-1.35 * x) * math.sin(2 * math.pi * 2.1 * x),
         632, 0.35, 1.7),
        ("信息", AMBER, lambda x: -52 * smoothstep(0.05, 0.78, x) + 6 * math.sin(4 * x),
         710, 1.35, 2.9),
        ("jerk", EMBER, lambda x: 42 * _gauss(x, 0.32, 0.06) - 54 * _gauss(x, 0.70, 0.08),
         782, 2.45, 3.95),
    ]
    # 车道基准线 + 左侧标签
    for name, col, fn, base, t0, t1 in lanes:
        a0 = clamp((t - 0.15) / 0.8) * 0.35
        p.stroke([(300, base), (1660, base)], (70, 84, 96), 1.0, a0)
        V.draw_text(p.rgb, name, (300, base - 40), 26, col, F_SANS_R, anchor="lm",
                    alpha=0.9 * clamp((t - 0.1) / 0.6), track=3)
    xs = np.linspace(0, 1, 200)
    for name, col, fn, base, t0, t1 in lanes:
        grow = clamp((t - t0) / (t1 - t0))
        if grow <= 0:
            continue
        pe = ease_out_cubic(grow)
        n = max(2, int(len(xs) * pe))
        px = 470 + 1180 * xs[:n]
        py = base + np.array([fn(x) for x in xs[:n]])
        p.stroke(np.stack([px, py], 1), col, 2.3, 0.94, 15, 0.7)
    p.flush()
    a = window(t, 4.0, dur - 0.15, 0.7, 0.5)
    if a > 0:
        V.draw_text(p.rgb, "三个物理量", (960, 380), 52, BONE, F_SERIF, anchor="mm",
                    alpha=0.9 * a, track=5, glow=18, glow_strength=0.45)
        V.draw_text(p.rgb, "三种「说不清」", (960, 448), 28, MUTED, F_SANS_R, anchor="mm",
                    alpha=0.7 * a, track=3)
    p.bloom(threshold=0.64, strength=0.55)
    return p.to_image()


# ------------------------------------------------------------------ S2 suspension
_DOF_BODY = None
_DOF_WHEEL = None


def _dof():
    global _DOF_BODY, _DOF_WHEEL
    if _DOF_BODY is None:
        t, zs, zu = two_dof_quarter_car(dt=1 / 480.0, dur=24.0, ms=320.0, mu=42.0,
                                        ks=26000.0, kt=240000.0, cs=1400.0,
                                        bump_h=0.11, bump_t=0.16)
        _DOF_BODY, _DOF_WHEEL = zs, zu
    return _DOF_BODY, _DOF_WHEEL


def _dof_at(sim_t):
    zs, zu = _dof()
    if sim_t <= 0:
        return 0.0, 0.0
    i = int(sim_t * 480)
    if i >= len(zs):
        return 0.0, 0.0
    return float(zs[i]), float(zu[i])


def _road_curve(impact_t, t):
    """路面：静态减速带剖面（车轮处）。"""
    xs = np.linspace(140, 1780, 260)
    bump = 34 * np.exp(-((xs - 960) ** 2) / (2 * 78 ** 2))
    return xs, 900 - bump


def scene_susp_body(t, dur, sh):
    bg = studio_bg(t, dur, tint=(0.34, 0.68, 0.78), strength=0.11, glow_xy=(0.46, 0.55))
    p = V.Painter(bg)
    p.halo((960, 660), 540, TEAL, 0.075)
    IMPACT = 1.55
    sim_t = t - IMPACT
    body_off, wheel_off = _dof_at(sim_t)
    body_px = -body_off * 1500.0
    wheel_px = -wheel_off * 620.0

    # 路面 + 地面反光
    xs, road_y = _road_curve(IMPACT, t)
    p.stroke(np.stack([xs, road_y], 1), (92, 104, 114), 2.6, 0.9, 14, 0.35)
    for k in range(5):
        y = 908 + k * 9
        a = 0.13 * (1 - k / 5.0)
        p.stroke([(220, y), (1700, y)], (64, 78, 90), 1.0, a)

    cx = 960
    body_cy = 560 + body_px
    wheel_cy = 786 + wheel_px
    # 运动残影（表现「正在晃」）
    for gk in range(1, 4):
        off, woff = _dof_at(sim_t - gk * 0.033)
        ga = 0.14 * (1 - gk / 5.0)
        draw_body_block(p, cx, 560 - off * 1500.0, 580, 152, ga)
        draw_wheel(p, cx, 786 - woff * 620.0, 118, ga)
    # 车身 / 悬架 / 车轮
    draw_body_block(p, cx, body_cy, 580, 152, 1.0)
    # 车身倒影（地面以下轻微）
    p.stroke([(cx - 250, 916), (cx + 250, 916)], (60, 74, 86), 1.4, 0.35, 8, 0.3)
    draw_spring(p, 895, body_cy + 80, wheel_cy - 40, coil=32, coils=8, color=TEAL, alpha=0.95)
    draw_damper(p, 1030, body_cy + 82, wheel_cy - 26, w=14, color=TEAL, alpha=0.9)
    p.stroke([(680, body_cy + 74), (cx, wheel_cy)], (124, 140, 154), 3.2, 0.85)
    p.stroke([(1240, body_cy + 74), (cx, wheel_cy)], (124, 140, 154), 3.2, 0.85)
    draw_wheel(p, cx, wheel_cy, 118, 1.0)
    p.flush()
    # 标注
    a = clamp((t - 0.9) / 0.7)
    if a > 0:
        leader(p, (640, 500), (730, body_cy - 44), MUTED, 0.5 * a, 1.1, elbow=(690, 500))
        V.draw_text(p.rgb, "车身 · 簧上质量", (628, 500), 26, MUTED, F_SANS_R, anchor="rm",
                    alpha=0.82 * a, track=2)
        leader(p, (1230, 850), (1082, wheel_cy + 70), MUTED, 0.5 * a, 1.1, elbow=(1205, 850))
        V.draw_text(p.rgb, "车轮 · 簧下质量", (1244, 850), 26, MUTED, F_SANS_R, anchor="lm",
                    alpha=0.82 * a, track=2)
        leader(p, (600, 706), (848, (body_cy + wheel_cy) / 2), TEAL, 0.45 * a, 1.1, elbow=(690, 706))
        V.draw_text(p.rgb, "弹簧 + 阻尼器", (588, 706), 26, TEAL, F_SANS_R, anchor="rm",
                    alpha=0.78 * a, track=2)
    # 挂在车身上的位移指针（1—2Hz 可见）
    if t > 1.9:
        px0, py0 = 340, 600
        p.stroke([(px0, py0 - 110), (px0, py0 + 110)], DIM, 1.0, 0.45, 4, 0.2)
        for k in range(-2, 3):
            yy = py0 + k * 55
            p.stroke([(px0 - 6, yy), (px0 + 6, yy)], DIM, 1.0, 0.35)
        p.stroke([(px0, py0), (px0 + 120, py0)], DIM, 1.0, 0.3)
        p.dot((px0, py0 + body_px * 0.9), 4.5, TEAL, 0.9, 14, 0.65)
        p.stroke([(px0 + 6, py0 + body_px * 0.9), (cx - 290, body_cy)], TEAL, 1.0, 0.22)
    # 花字 1—2 Hz
    if 3.9 <= t <= 6.6:
        a = window(t, 3.9, 6.6, 0.3, 0.55)
        V.draw_text(p.rgb, "1—2 Hz", (500, 292), 92, BONE, F_SERIF, anchor="mm",
                    alpha=0.95 * a, track=2, glow=24, glow_strength=0.5)
        V.draw_text(p.rgb, "一秒晃 1 到 2 下", (500, 378), 28, MUTED, F_SANS_R, anchor="mm",
                    alpha=0.75 * a, track=2)
    p.flush()
    p.bloom(threshold=0.62, strength=0.5)
    return p.to_image()


def scene_susp_wheel(t, dur, sh):
    bg = studio_bg(t, dur, tint=(0.34, 0.68, 0.78), strength=0.11, glow_xy=(0.56, 0.58))
    p = V.Painter(bg)
    p.halo((1080, 640), 520, TEAL, 0.07)
    sim_t = t + 1.2
    body_off, wheel_off = _dof_at(sim_t)
    # 车身下缘（大幅裁切，电影感）
    p.fill_poly([(0, 0), (W, 0), (W, 292), (0, 292)], (20, 25, 31), 0.98)
    p.fill_poly([(0, 250), (W, 250), (W, 292), (0, 292)], (30, 36, 44), 0.9)
    p.stroke([(0, 292), (W, 292)], (96, 108, 120), 2.6, 0.85, 12, 0.3)
    p.stroke([(0, 300), (W, 300)], (44, 52, 60), 1.4, 0.6)
    # 弹簧 / 阻尼 / 下摆臂
    draw_spring(p, 1080, 306, 452, coil=44, coils=6, color=TEAL, alpha=0.95)
    draw_damper(p, 1196, 306, 486, w=20, color=TEAL, alpha=0.9)
    p.stroke([(700, 320), (1080, 688)], (124, 140, 154), 4.2, 0.85)
    p.stroke([(1460, 320), (1080, 688)], (124, 140, 154), 4.2, 0.85)
    # 车轮（大幅特写）+ 12Hz 运动残影（多帧采样合成，避免 24fps 混叠）
    cx, cy, r = 1080, 688, 250
    for gk in range(1, 6):
        off, _ = _dof_at(sim_t + gk * 0.0018)
        p.fill_circle((cx, cy - off * 700.0), r, (44, 50, 58), 0.07)
    draw_wheel(p, cx, cy - wheel_off * 620.0, r, 1.0, rim_color=(152, 166, 178),
               tire_color=(50, 56, 64), spokes=6)
    # 路面 + 接触点涟漪（高频闪烁）
    p.stroke([(180, 938), (1720, 938)], (92, 104, 114), 2.4, 0.82, 12, 0.3)
    for k in range(5):
        ph = ((t * 12.7) + k * 0.2) % 1.0
        rr = 22 + 130 * ph
        a = (1 - ph) ** 1.5 * 0.32
        p.stroke([(1080 + rr * math.cos(aa), 938 + rr * 0.16 * math.sin(aa))
                  for aa in np.linspace(0, 2 * math.pi, 60)], ICE, 1.3, a, 6, 0.3)
    p.flush()
    # 一秒 = 12 次（左侧刻度：逐格点亮）
    rx0, ry = 250, 800
    V.draw_text(p.rgb, "1 秒", (rx0 - 10, ry - 46), 26, MUTED, F_SANS_R, anchor="lm",
                alpha=0.8, track=2)
    lit = int((t * 12.0) % 12)
    for i in range(12):
        x = rx0 + i * 30
        on = 1.0 if i == lit else 0.22
        p.stroke([(x, ry - 14), (x, ry + 14)], TEAL, 2.2, 0.85 * on, 8, 0.4)
    p.flush()
    V.draw_text(p.rgb, "约 12 次 / 秒", (rx0, ry + 46), 26, TEAL, F_SANS_R, anchor="lm",
                alpha=0.85, track=2)
    # 花字 10—15 Hz
    if 0.9 <= t <= 3.9:
        a = window(t, 0.9, 3.9, 0.3, 0.55)
        V.draw_text(p.rgb, "10—15 Hz", (470, 320), 92, BONE, F_SERIF, anchor="mm",
                    alpha=0.95 * a, track=2, glow=24, glow_strength=0.5)
        V.draw_text(p.rgb, "更轻、更硬，晃得更快", (470, 406), 28, MUTED, F_SANS_R, anchor="mm",
                    alpha=0.75 * a, track=2)
    p.bloom(threshold=0.62, strength=0.5)
    return p.to_image()


def scene_freq_bands(t, dur, sh):
    bg = studio_bg(t, dur, tint=(0.36, 0.70, 0.82), strength=0.13, glow_xy=(0.42, 0.48))
    p = V.Painter(bg)
    p.halo((680, 620), 420, TEAL, 0.07)
    # 人体侧影（坐姿）：4—8Hz 的细微抖动 + 残影
    cx, base_y, hgt = 700, 760, 460
    for gk in range(1, 4):
        off = 9 * math.sin(2 * math.pi * 6.0 * (t - gk * 0.004))
        draw_person(p, cx, base_y + off, hgt, alpha=0.13)
    vib = 9 * math.sin(2 * math.pi * 6.0 * t)
    draw_person(p, cx, base_y + vib, hgt, alpha=1.0)
    # 上下振动示意
    ax = 460
    p.stroke([(ax, 470), (ax, 660)], DIM, 1.0, 0.5)
    p.stroke([(ax - 8, 486), (ax, 470), (ax + 8, 486)], DIM, 1.2, 0.5)
    p.stroke([(ax - 8, 644), (ax, 660), (ax + 8, 644)], DIM, 1.2, 0.5)
    V.draw_text(p.rgb, "上下振动", (ax - 20, 565), 22, DIM, F_SANS_R, anchor="rm",
                alpha=0.65, track=2)
    # 频率轴 + 三个频段
    ax0, ax1, ay = 320, 1700, 822
    p.stroke([(ax0, ay), (ax1, ay)], MUTED, 1.2, 0.45)
    bands = [
        (380, 540, "1—2 Hz", "车身", 0.55, False),
        (820, 1100, "4—8 Hz", "人体最敏感", 1.0, True),
        (1420, 1600, "10—15 Hz", "车轮", 0.55, False),
    ]
    hl = clamp((t - 0.55) / 0.8)
    for (x0, x1, lab, sub, base_a, is_hl) in bands:
        a = base_a + (1 - base_a) * hl if is_hl else base_a
        p.stroke([(x0, ay - 10), (x1, ay - 10)], TEAL if is_hl else MUTED,
                 2.2 + 2.2 * (hl if is_hl else 0), 0.55 * a,
                 18 if is_hl else 6, 0.6)
        p.stroke([(x0, ay - 18), (x0, ay + 18)], MUTED, 1.2, 0.5)
        p.stroke([(x1, ay - 18), (x1, ay + 18)], MUTED, 1.2, 0.5)
        V.draw_text(p.rgb, lab, ((x0 + x1) / 2, ay + 50), 28,
                    TEAL if is_hl else MUTED, F_SANS_R, anchor="mm",
                    alpha=0.55 + 0.4 * (a - base_a) / max(1e-3, 1 - base_a) if is_hl else 0.7,
                    track=2)
        V.draw_text(p.rgb, sub, ((x0 + x1) / 2, ay + 90), 24,
                    MUTED, F_SANS_R, anchor="mm", alpha=0.4 + 0.45 * a if is_hl else 0.5,
                    track=2)
    p.flush()
    # 敏感带向上连线到身体
    if hl > 0.2:
        for k in range(3):
            xx = 870 + k * 70
            for seg in V.dashed(np.array([[xx, ay - 26], [xx - 30 + k * 24, base_y - 120]]), 10, 14):
                p.stroke(seg, TEAL, 1.0, 0.22 * hl, 4, 0.2)
    p.flush()
    # 花字 4—8 Hz
    if 0.8 <= t <= 3.6:
        a = window(t, 0.8, 3.6, 0.3, 0.6)
        V.draw_text(p.rgb, "4—8 Hz", (1300, 320), 100, BONE, F_SERIF, anchor="mm",
                    alpha=0.95 * a, track=2, glow=24, glow_strength=0.5)
        V.draw_text(p.rgb, "人体对上下振动最敏感", (1300, 418), 28, MUTED, F_SANS_R,
                    anchor="mm", alpha=0.75 * a, track=2)
    p.flush()
    p.bloom(threshold=0.62, strength=0.5)
    return p.to_image()


def scene_not_form(t, dur, sh):
    bg = studio_bg(t, dur, tint=(0.34, 0.66, 0.78), strength=0.09, glow_xy=(0.5, 0.42))
    p = V.Painter(bg)
    V.draw_text(p.rgb, "悬架形式", (960, 330), 38, MUTED, F_SERIF, anchor="mm",
                alpha=0.85 * clamp((t - 0.2) / 0.5) * (1 - 0.45 * smoothstep(1.6, 2.2, t)),
                track=4)
    types = ["麦弗逊", "双叉臂", "多连杆"]
    centers = [520, 960, 1400]
    strike = clamp((t - 0.95) / 0.55)
    fade_icons = 1.0 - 0.66 * smoothstep(1.5, 2.2, t)
    for i, (cx, name) in enumerate(zip(centers, types)):
        a = clamp((t - 0.15 - i * 0.12) / 0.45) * fade_icons
        if a <= 0:
            continue
        cy = 700
        draw_wheel(p, cx + 46, cy + 86, 32, 0.7 * a, rim_color=(140, 152, 164),
                   tire_color=(52, 58, 66), spokes=4)
        draw_spring(p, cx - 10, cy + 6, cy + 46, coil=15, coils=4,
                    color=MUTED, alpha=0.55 * a, width=1.4)
        p.stroke([(cx - 56, cy + 34), (cx + 46, cy + 86)], MUTED, 2.0, 0.5 * a)
        p.stroke([(cx + 52, cy + 6), (cx + 46, cy + 86)], MUTED, 2.0, 0.5 * a)
        V.draw_text(p.rgb, name, (cx, cy + 152), 28, MUTED, F_SANS_R, anchor="mm",
                    alpha=0.72 * a, track=2)
        if strike > 0:
            p.stroke([(cx - 110, cy + 110), (cx - 110 + 220 * strike, cy - 10)],
                     EMBER, 2.6, 0.85 * strike, 10, 0.4)
    # 转折：信息
    if t > 2.0:
        a = clamp((t - 2.0) / 0.55)
        p.halo((960, 470), 300, TEAL, 0.09 * a)
        p.flush()
        V.draw_text(p.rgb, "信息", (960, 470), 112, BONE, F_SERIF, anchor="mm",
                    alpha=0.96 * a, track=8, glow=24, glow_strength=0.5)
        V.draw_text(p.rgb, "它给不给你提前量", (960, 568), 30, TEAL, F_SANS_R, anchor="mm",
                    alpha=0.8 * clamp((t - 2.45) / 0.5), track=3)
        p.stroke([(700, 640), (1220, 640)], TEAL, 1.4, 0.5 * a, 10, 0.4)
    p.flush()
    p.bloom(threshold=0.62, strength=0.5)
    return p.to_image()


# ------------------------------------------------------------------ S4 jerk
def scene_jerk_def(t, dur, sh):
    bg = studio_bg(t, dur, tint=(0.30, 0.58, 0.72), strength=0.08, glow_xy=(0.5, 0.4))
    plate = plate_bg(t, dur, "steering_night", 1.0, dark=0.88, tint=(0.6, 0.8, 1.0),
                     blur=14.0, zoom0=1.05, drift=0.03)
    bg = bg * 0.65 + plate * 0.35
    p = V.Painter(bg)
    x0, x1 = 380, 1520
    xs = np.linspace(0, 1, 220)
    # —— Panel A：加速度
    ay = 520
    axis(p, x0, ay, x1, ay, MUTED, 0.45)
    axis(p, x0, ay, x0, 300, MUTED, 0.45)
    V.draw_text(p.rgb, "加速度 a", (x0, 268), 28, MUTED, F_SANS_R, anchor="lm", alpha=0.8, track=2)
    py_fuel = ay - 120 * (1 - np.exp(-3.0 * xs))
    py_ev = ay - np.where(xs < 0.42, 8, 128)
    gy = clamp((t - 0.55) / 1.0)
    if gy > 0:
        n = max(2, int(len(xs) * ease_out_cubic(gy)))
        p.stroke(np.stack([x0 + (x1 - x0) * xs[:n], py_fuel[:n]], 1), AMBER, 2.3, 0.95, 12, 0.65)
    ge = clamp((t - 1.35) / 0.75)
    if ge > 0:
        n = max(2, int(len(xs) * ease_out_cubic(ge)))
        p.stroke(np.stack([x0 + (x1 - x0) * xs[:n], py_ev[:n]], 1), TEAL, 2.4, 0.95, 12, 0.65)
    p.flush()
    a = clamp((t - 0.9) / 0.5)
    if a > 0:
        V.draw_text(p.rgb, "燃油车", (x1 - 20, 306), 24, AMBER, F_SANS_R, anchor="rm",
                    alpha=0.85 * a, track=2)
        V.draw_text(p.rgb, "电动车", (x1 - 20, 352), 24, TEAL, F_SANS_R, anchor="rm",
                    alpha=0.85 * a, track=2)
    if t > 1.75:
        aa = clamp((t - 1.75) / 0.4)
        V.draw_text(p.rgb, "突然出现", (x0 + (x1 - x0) * 0.50, 390), 28, TEAL, F_SANS_R,
                    anchor="lm", alpha=0.85 * aa, track=2)
        p.stroke([(x0 + (x1 - x0) * 0.44, 400), (x0 + (x1 - x0) * 0.46, py_ev[100])],
                 TEAL, 1.0, 0.4 * aa)
    # —— Panel B：jerk
    by = 850
    axis(p, x0, by, x1, by, MUTED, 0.45)
    axis(p, x0, by, x0, 640, MUTED, 0.45)
    V.draw_text(p.rgb, "jerk = da/dt", (x0, 618 - 16), 28, MUTED, F_SANS_R, anchor="lm",
                alpha=0.8, track=2)
    jy_fuel = by - 74 * np.exp(-3.4 * xs)
    jy_ev = by - 215 * _gauss(xs, 0.42, 0.018)
    gb = clamp((t - 2.2) / 1.1)
    if gb > 0:
        n = max(2, int(len(xs) * ease_out_cubic(gb)))
        p.stroke(np.stack([x0 + (x1 - x0) * xs[:n], jy_fuel[:n]], 1), AMBER, 2.1, 0.9, 10, 0.55)
    gj = clamp((t - 2.75) / 0.8)
    if gj > 0:
        n = max(2, int(len(xs) * ease_out_cubic(gj)))
        p.stroke(np.stack([x0 + (x1 - x0) * xs[:n], jy_ev[:n]], 1), EMBER, 2.4, 0.95, 14, 0.7)
    p.flush()
    # 花字 jerk
    if 3.2 <= t <= 5.6:
        a = window(t, 3.2, 5.6, 0.3, 0.6)
        V.draw_text(p.rgb, "jerk", (1265, 660), 104, BONE, F_SERIF, anchor="mm",
                    alpha=0.95 * a, track=2, glow=26, glow_strength=0.55)
    if t > 4.4:
        a = clamp((t - 4.4) / 0.6)
        V.draw_text(p.rgb, "你感知的不是加速度，是加速度的变化率", (960, 943), 24, MUTED,
                    F_SANS_R, anchor="mb", alpha=0.7 * a, track=2)
    p.flush()
    p.bloom(threshold=0.62, strength=0.5)
    return p.to_image()


# ------------------------------------------------------------------ S4 research card
def scene_umtri_card(t, dur, sh):
    bg = plate_bg(t, dur, "city_night_aerial", 1.0, dark=0.74,
                  tint=(0.58, 0.78, 1.0), blur=7.0, zoom0=1.04, drift=0.04)
    # 左侧压暗渐变（保证文字可读，不是独立卡片）
    nx, ny = grid()
    scrim = np.exp(-(((nx - 0.28) / 0.30) ** 2)) * 0.62
    bg = bg * (1 - scrim[..., None]) + np.array(INK, np.float32) / 255.0 * scrim[..., None]
    p = V.Painter(bg)
    lx = 240
    a1 = clamp((t - 0.2) / 0.5)
    V.draw_text(p.rgb, "研究 · 乘车不适", (lx, 300), 22, MUTED, F_SANS_R, anchor="lm",
                alpha=0.7 * a1, track=5)
    a2 = clamp((t - 0.45) / 0.6)
    V.draw_text(p.rgb, "密歇根大学", (lx, 372), 48, BONE, F_SERIF, anchor="lm",
                alpha=0.95 * a2, track=3)
    V.draw_text(p.rgb, "UMTRI · 交通研究所", (lx, 420), 22, MUTED, F_SANS_R, anchor="lm",
                alpha=0.75 * a2, track=2)
    if t > 1.0:
        p.stroke([(lx, 458), (lx + 260, 458)], DIM, 1.2, 0.6)
    a3 = clamp((t - 1.25) / 0.6)
    if a3 > 0:
        V.draw_text(p.rgb, "纵向 jerk", (lx, 522), 36, AMBER, F_SANS_R, anchor="lm",
                    alpha=0.95 * a3, track=2)
        V.draw_text(p.rgb, "尤其动能回收松开油门那一下", (lx, 566), 26, MUTED, F_SANS_R,
                    anchor="lm", alpha=0.8 * a3, track=2)
        V.draw_text(p.rgb, "被识别为晕车的关键触发因素", (lx, 636), 36, BONE, F_SERIF,
                    anchor="lm", alpha=0.95 * a3, track=2)
        V.draw_text(p.rgb, "（经媒体报道与综述转引）", (lx, 682), 20, DIM, F_SANS_R,
                    anchor="lm", alpha=0.7 * a3, track=1)
    # 右侧：速度 / jerk 动效
    x0, x1 = 1080, 1720
    by = 700
    ap = clamp((t - 1.9) / 0.6)
    if ap > 0:
        axis(p, x0, by, x1, by, MUTED, 0.4 * ap)
        axis(p, x0, by, x0, 430, MUTED, 0.4 * ap)
        V.draw_text(p.rgb, "速度", (x0 - 6, 408), 22, MUTED, F_SANS_R, anchor="lm",
                    alpha=0.7 * ap, track=2)
        V.draw_text(p.rgb, "jerk", (x0 - 6, 736), 22, EMBER, F_SANS_R, anchor="lm",
                    alpha=0.7 * ap, track=2)
    xs = np.linspace(0, 1, 200)
    v = np.where(xs < 0.45, 60, 60 - 26 * smoothstep(0.45, 0.95, xs))
    vs = (v - 20) / 50.0
    gv = clamp((t - 2.2) / 1.2)
    if gv > 0:
        n = max(2, int(len(xs) * ease_out_cubic(gv)))
        py = by - 200 * vs[:n]
        p.stroke(np.stack([x0 + (x1 - x0) * xs[:n], py], 1), ICE, 2.2, 0.9, 12, 0.6)
    gj = clamp((t - 3.0) / 0.7)
    if gj > 0:
        n = max(2, int(len(xs) * ease_out_cubic(gj)))
        jv = 150 * _gauss(xs, 0.45, 0.03)
        p.stroke(np.stack([x0 + (x1 - x0) * xs[:n], by - 10 - jv[:n]], 1), EMBER, 2.4, 0.95, 14, 0.7)
        if gj > 0.75:
            xx = x0 + (x1 - x0) * 0.45
            p.stroke([(xx, by), (xx, by - 10 - 150)], EMBER, 1.0, 0.4, 6, 0.3)
    p.flush()
    if t > 3.3:
        aa = clamp((t - 3.3) / 0.5)
        V.draw_text(p.rgb, "动能回收介入", (x0 + (x1 - x0) * 0.47, 470), 24, EMBER, F_SANS_R,
                    anchor="lm", alpha=0.8 * aa, track=2)
    # 底部边界
    a4 = clamp((t - 5.2) / 0.7)
    if a4 > 0:
        p.stroke([(240, 858), (1700, 858)], DIM, 1.0, 0.5 * a4)
        V.draw_text(p.rgb, "特定实验条件 · 样本有限 · 不作普遍化断言", (960, 898), 24, MUTED,
                    F_SANS_R, anchor="mm", alpha=0.8 * a4, track=2)
    p.flush()
    p.bloom(threshold=0.64, strength=0.45)
    return p.to_image()


def scene_two_sides(t, dur, sh):
    bg = studio_bg(t, dur, tint=(0.6, 0.55, 0.45), strength=0.06, glow_xy=(0.5, 0.5))
    p = V.Painter(bg)
    p.halo((560, 560), 260, AMBER, 0.10)
    p.halo((1360, 660), 260, EMBER, 0.10)
    p.flush()
    base = 620
    xs = np.linspace(0, 1, 260)
    ys = (155 * _gauss(xs, 0.30, 0.055) - 155 * _gauss(xs, 0.72, 0.075))
    grow = clamp((t - 0.25) / 1.25)
    if grow > 0:
        n = max(3, int(len(xs) * ease_in_out(grow)))
        px = 340 + 1200 * xs[:n]
        py = base - ys[:n]
        # 正/负分段着色
        k = 0
        while k < n:
            sgn = ys[k] >= 0
            j = k
            while j < n and (ys[j] >= 0) == sgn:
                j += 1
            if j - k >= 2:
                p.stroke(np.stack([px[k:j], py[k:j]], 1), AMBER if sgn else EMBER,
                         2.6, 0.95, 16, 0.7)
            k = j
    dashed_hline(p, 340, 1540, base, MUTED, 0.35)
    p.flush()
    a = clamp((t - 1.1) / 0.6)
    if a > 0:
        V.draw_text(p.rgb, "推背感", (650, 420), 44, AMBER, F_SERIF, anchor="mm",
                    alpha=0.9 * a, track=3, glow=12, glow_strength=0.4)
        V.draw_text(p.rgb, "晕车感", (1290, 790), 44, EMBER, F_SERIF, anchor="mm",
                    alpha=0.9 * a, track=3, glow=12, glow_strength=0.4)
        p.stroke([(650, 462), (650, 520)], AMBER, 1.4, 0.6 * a, 6, 0.3)
        p.stroke([(1290, 744), (1290, 700)], EMBER, 1.4, 0.6 * a, 6, 0.3)
    if t > 2.2:
        aa = clamp((t - 2.2) / 0.7)
        V.draw_text(p.rgb, "同一个物理量的两面", (960, 878), 40, BONE, F_SERIF, anchor="mm",
                    alpha=0.9 * aa, track=4, glow=14, glow_strength=0.4)
    p.bloom(threshold=0.62, strength=0.5)
    return p.to_image()


# ------------------------------------------------------------------ S5 merge
def scene_converge(t, dur, sh):
    bg = studio_bg(t, dur, tint=(0.5, 0.6, 0.55), strength=0.07, glow_xy=(0.5, 0.5))
    plate = plate_bg(t, dur, "car_interior_night", 5.0, dark=0.84,
                     tint=(0.6, 0.8, 1.0), blur=10.0, zoom0=1.05, drift=0.03)
    bg = bg * 0.55 + plate * 0.45
    p = V.Painter(bg)
    xs = np.linspace(0, 1, 220)
    morph = smoothstep(1.5, 3.15, t)
    target = 690 - 26 * smoothstep(0.15, 0.85, xs)
    curves = [
        (TEAL, 600, lambda x: 22 * math.exp(-1.4 * x) * math.sin(3.4 * x * math.pi)),
        (AMBER, 660, lambda x: -16 * smoothstep(0.1, 0.8, x) + 6 * math.sin(3 * x)),
        (EMBER, 720, lambda x: 14 * _gauss(x, 0.35, 0.05) - 16 * _gauss(x, 0.7, 0.06)),
    ]
    grow = clamp((t - 0.25) / 1.6)
    if grow > 0:
        n = max(2, int(len(xs) * ease_out_cubic(grow)))
        for col, base_y, fn in curves:
            y0 = base_y + np.array([fn(x) for x in xs[:n]])
            y = y0 * (1 - morph) + target[:n] * morph
            px = 300 + 1320 * xs[:n]
            p.stroke(np.stack([px, y], 1), col, 2.2, 0.9, 14, 0.65)
    if morph > 0.45:
        a = clamp((morph - 0.45) / 0.35)
        p.stroke(np.stack([300 + 1320 * xs, target], 1), GOLD, 2.8, 0.55 + 0.4 * a, 20, 0.85)
    p.flush()
    a = window(t, 2.7, dur - 0.1, 0.7, 0.5)
    if a > 0:
        V.draw_text(p.rgb, "AI 时代最稀缺的东西", (960, 400), 44, BONE, F_SERIF, anchor="mm",
                    alpha=0.92 * a, track=4, glow=16, glow_strength=0.45)
    p.bloom(threshold=0.62, strength=0.5)
    return p.to_image()


def _ecg(x, period=0.17):
    beat = np.zeros_like(x)
    for c, w, amp in ((0.20, 0.018, 0.10), (0.32, 0.007, -0.16), (0.355, 0.006, 1.0),
                      (0.39, 0.008, -0.26), (0.55, 0.030, 0.20)):
        beat += amp * _gauss(x, c, w)
    return beat


def scene_merge_ecg(t, dur, sh):
    bg = studio_bg(t, dur, tint=(0.62, 0.58, 0.42), strength=0.08, glow_xy=(0.5, 0.52))
    p = V.Painter(bg)
    # 1) 三条线合流
    settle = clamp((t - 0.15) / 1.5)
    xs = np.linspace(0, 1, 240)
    if settle > 0:
        se = ease_out_cubic(settle)
        for col, d in ((TEAL, -34), (AMBER, 0), (EMBER, 34)):
            y = 640 + d * (1 - se)
            px = 300 + 1320 * xs
            p.stroke(np.stack([px, np.full_like(px, y)], 1), col, 2.0, 0.55 * (1 - se) + 0.2,
                     12, 0.5)
    p.flush()
    # 2) 心跳线
    t_start = 1.15
    p_ecg = clamp((t - t_start) / (dur - t_start - 0.2))
    if p_ecg > 0:
        pe = ease_in_out(p_ecg)
        n = max(3, int(260 * pe))
        x = np.linspace(0, 1, n)
        y = 640 - 120 * _ecg((x * 5.2) % 1.0) ** 1.0
        px = 300 + 1320 * x
        p.stroke(np.stack([px, y], 1), GOLD, 2.5, 0.95, 18, 0.8)
        p.flush()
        # 心跳脉冲光晕（按显示进度节拍）
        prog = pe
        for k in range(10):
            center = (k + 0.2) / 5.2
            if abs(center - prog) < 0.16:
                xxx = 300 + 1320 * center
                amp = (1 - abs(center - prog) / 0.16) * 0.22
                p.halo((xxx, 640), 90, GOLD, amp)
    p.flush()
    a = clamp((t - 2.9) / 0.8)
    if a > 0:
        V.draw_text(p.rgb, "心跳 · 身体的记忆", (330, 830), 26, MUTED, F_SANS_R, anchor="lm",
                    alpha=0.7 * a, track=3)
    p.bloom(threshold=0.60, strength=0.6)
    return p.to_image()


# ------------------------------------------------------------------ end card
def _end_card_layers(p, t):
    plate = plate_bg(t, 8.35, "car_interior_night", 8.0, dark=0.82,
                     tint=(0.62, 0.82, 1.0), blur=9.0, zoom0=1.05, drift=0.02)
    p.add(plate, alpha=1.0)
    V.draw_text(p.rgb, "VIBE 知识共赏 · 第 04 期", (960, 300), 24, MUTED, F_SANS_R,
                anchor="mm", alpha=0.7 * clamp((t - 0.1) / 0.6), track=5)
    a = clamp((t - 0.25) / 0.8)
    if a > 0:
        V.draw_text(p.rgb, "你的身体，比参数表更懂车", (960, 382), 72, BONE, F_SERIF,
                    anchor="mm", alpha=0.96 * a, track=3, glow=16, glow_strength=0.4)
    a = clamp((t - 0.75) / 0.7)
    if a > 0:
        V.draw_text(p.rgb, "三个说不清的体感，和它们背后的物理", (960, 452), 28, MUTED,
                    F_SANS_R, anchor="mm", alpha=0.8 * a, track=3)
    a = clamp((t - 1.15) / 0.6)
    if a > 0:
        p.stroke([(700, 500), (1220, 500)], GOLD, 1.2, 0.55 * a, 8, 0.35)
        p.flush()
    # AI 声明块（片尾必须可见）
    a = clamp((t - 3.0) / 0.7)
    if a > 0:
        V.draw_text(p.rgb, "本片画面与配音含 AI 参与制作", (960, 566), 40, BONE, F_SANS,
                    anchor="mm", alpha=0.96 * a, track=2, glow=12, glow_strength=0.35)
        V.draw_text(p.rgb, "选题、核实与判断，由人完成", (960, 620), 30, AMBER, F_SANS_R,
                    anchor="mm", alpha=0.85 * a, track=3)
    a = clamp((t - 4.2) / 0.7)
    if a > 0:
        V.draw_text(p.rgb, "参考资料：ISO 2631-1 · FSAE 减振器章节 · UMTRI 晕车研究（经媒体报道与综述转引）",
                    (960, 762), 21, DIM, F_SANS_R, anchor="mm", alpha=0.75 * a, track=1)
        V.draw_text(p.rgb, "点赞 · 关注，一起把感觉留住", (960, 812), 26, MUTED, F_SANS_R,
                    anchor="mm", alpha=0.6 * a, track=3)
    p.bloom(threshold=0.66, strength=0.4)
    return p


def scene_end_card(t, dur, sh):
    p = V.Painter()
    _end_card_layers(p, t)
    return p.to_image()


def scene_end_hold(t, dur, sh):
    p = V.Painter()
    _end_card_layers(p, t + 8.35)
    # 最后 1.3s 淡出到黑
    fade = 1.0 - smoothstep(dur - 1.4, dur - 0.15, t)
    p.rgb *= fade
    return p.to_image()


SCENES = {
    "cold_title": scene_cold_title,
    "three_intro": scene_three_intro,
    "susp_body": scene_susp_body,
    "susp_wheel": scene_susp_wheel,
    "freq_bands": scene_freq_bands,
    "not_form": scene_not_form,
    "jerk_def": scene_jerk_def,
    "umtri_card": scene_umtri_card,
    "two_sides": scene_two_sides,
    "converge": scene_converge,
    "merge_ecg": scene_merge_ecg,
    "end_card": scene_end_card,
    "end_hold": scene_end_hold,
}
