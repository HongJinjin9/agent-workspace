#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 05 期全画幅程序化场景（数据/英雄镜头）。

每个场景签名 `def scene_xxx(t, dur, sh) -> PIL.Image`，t 为镜头内局部时间。
所有图形由 ep05viz.py 的**真实模型**生成：
- S2 网：组合数 n(n−1)/2 + 确定性力导向布局（Fruchterman–Reingold），
        节点 3→10→20 逐个加入、连线逐条生长，坐标跨镜头不重排；
- S3 层级：楼层 3→5→8 逐层升起；停靠次数 / 路径长度 = 层数函数；
- S4 箭头：黄金角 + 确定性种子的离心场，中央被逐渐腾空；
- S5 曲线：底线下移 + 几何衰减脉冲串（峰值 74%→…→43%），最后拉不动；
- S6 网松开：同一张网沿一条缝被“松”开，光从缝里透进来，不是剪断。

风格约束：一屏一个第一视觉重点；运动必须回答“为什么现在动”；
无进度条 / 常驻章节卡 / 闪白 / 逐镜 whoosh；文字在 2.35:1 遮幅安全区内。
"""
import math

import numpy as np
from PIL import Image

import ep05viz as V
from ep05viz import (W, H, BAR, SAFE_T, SAFE_B, INK, INK2, BONE, MUTED, DIM, TEAL,
                     TEAL_D, AMBER, GOLD, EMBER, ICE, WHITE, F_SERIF, F_SERIF_R,
                     F_SANS, F_SANS_R, F_MONO, clamp, lerp, ease_in_out,
                     ease_out_cubic, ease_in_cubic, smoothstep, window, comb_edges,
                     net_state, net_positions, net_positions_screen,
                     net_growth_order, arrow_screen, ARROW_PHASE,
                     floor_path_len, floor_stop_time, elevator_journey,
                     FLOOR_H_M, WALK_M_PER_STOP, SEC_PER_STOP,
                     fatigue_support, fatigue_peaks, fatigue_mark, fatigue_xy,
                     fatigue_points, FATIGUE_T, FATIGUE_N, FATIGUE_YEARS,
                     FATIGUE_VMIN, FATIGUE_VMAX, FLOORS_PLAN)

ROOT = "/app/vedio/ep05-enterprise"

_GRID = None


def grid():
    global _GRID
    if _GRID is None:
        yy, xx = np.ogrid[:H, :W]
        _GRID = (xx.astype(np.float32) / W, yy.astype(np.float32) / H)
    return _GRID


# ---------------------------------------------------------------- backgrounds
def studio_bg(t, dur, tint=(0.42, 0.78, 0.86), strength=0.11, glow_xy=(0.5, 0.5),
              base=(0.024, 0.032, 0.042), drift=0.010):
    nx, ny = grid()
    gx = glow_xy[0] + drift * math.sin(t * 0.33 + 0.6)
    gy = glow_xy[1] + drift * 0.4 * math.cos(t * 0.27)
    g = np.exp(-(((nx - gx) ** 2) / (0.60 ** 2) + ((ny - gy) ** 2) / (0.48 ** 2))) * strength
    rgb = np.array(base, np.float32)[None, None, :] + g[..., None] * np.array(tint, np.float32)
    return rgb


def warm_bg(t, dur, base=(0.030, 0.026, 0.022), glow=(0.18, 0.13, 0.08)):
    """片尾卡：暖色 bokeh 背景（程序化，不依赖素材）。"""
    nx, ny = grid()
    rgb = np.zeros((H, W, 3), np.float32) + np.array(base, np.float32)
    g1 = np.exp(-(((nx - 0.28) ** 2) / 0.10 + ((ny - 0.72) ** 2) / 0.14))
    g2 = np.exp(-(((nx - 0.78) ** 2) / 0.16 + ((ny - 0.18) ** 2) / 0.10))
    g3 = np.exp(-(((nx - 0.55) ** 2) / 0.40 + ((ny - 0.55) ** 2) / 0.30))
    rgb += g1[..., None] * np.array(glow, np.float32) * 0.9
    rgb += g2[..., None] * np.array([0.05, 0.09, 0.11], np.float32) * 0.8
    rgb += g3[..., None] * np.array([0.04, 0.06, 0.07], np.float32) * 0.5
    rgb *= 1.0 + 0.02 * math.sin(t * 0.5)
    return rgb


def light_room_bg(t, dur):
    """冷色室内底：一条窗光斜带 + 缓慢漂移（用于冷开场 / 网镜头）。"""
    nx, ny = grid()
    rgb = np.full((H, W, 3), 0.022, np.float32)
    rgb += np.array([0.012, 0.020, 0.026], np.float32)[None, None, :]
    shaft = np.exp(-((nx - (0.68 + 0.01 * math.sin(t * 0.25))) ** 2) / 0.012) * \
        np.exp(-((ny - 0.42) ** 2) / 0.30)
    rgb += shaft[..., None] * np.array([0.10, 0.13, 0.14], np.float32) * 0.5
    g = np.exp(-(((nx - 0.46) ** 2) / 0.30 + ((ny - 0.50) ** 2) / 0.24)) * 0.05
    rgb += g[..., None] * np.array([0.35, 0.62, 0.66], np.float32)
    return rgb


# ---------------------------------------------------------------- primitives
def leader(p, a, b, color=MUTED, alpha=0.55, width=1.0, elbow=None, dot=2.2):
    pts = [a]
    if elbow:
        pts.append(elbow)
    pts.append(b)
    p.stroke(pts, color, width, alpha, 4, 0.25)
    p.dot(b, dot, color, alpha)


def arrow_head(p, x, y, dx, dy, size=10.0, color=TEAL, alpha=1.0, width=2.0, glow=0.0):
    """朝向 (dx,dy) 的箭头：杆 + 两笔箭头。"""
    x0, y0 = x - dx * size, y - dy * size
    p.stroke([(x0, y0), (x, y)], color, width, alpha, glow, 0.55)
    for sgn in (-1, 1):
        ca = math.cos(sgn * 0.46)
        sa = math.sin(sgn * 0.46)
        hx = -(dx * ca - dy * sa)
        hy = -(dx * sa + dy * ca)
        p.stroke([(x, y), (x + hx * size * 0.62, y + hy * size * 0.62)],
                 color, width, alpha * 0.95)


def dashed_line(p, a, b, color=MUTED, alpha=0.5, width=1.1, dash=14, gap=10, glow=0.0):
    for seg in V.dashed(np.array([a, b], np.float64), dash, gap):
        p.stroke(seg, color, width, alpha, glow, 0.3)


def draw_mixed(p, parts, xy, size, anchor="lm", alpha=1.0, track=0.0, glow=0.0,
               glow_strength=0.35, stroke=0, stroke_color=(0, 0, 0)):
    """混排一行文字：parts = [(text, color, font), ...]，按顺序横向排布。

    等宽数字（F_MONO）不含中文字形，凡含中文的片段必须走 F_SANS_R / F_SERIF。
    """
    total = 0.0
    sizes = []
    for text, color, font in parts:
        w = V.text_size(text, size, font, stroke, track)[0]
        sizes.append(w)
        total += w
    x = xy[0]
    if anchor == "rm":
        x -= total
    elif anchor == "mm":
        x -= total * 0.5
    for (text, color, font), w in zip(parts, sizes):
        V.draw_text(p.rgb, text, (x, xy[1]), size, color, font, anchor="lm",
                    alpha=alpha, track=track, glow=glow, glow_strength=glow_strength,
                    stroke=stroke, stroke_color=stroke_color)
        x += w
    return total


def draw_net(p, t, dur, n_from, n_to, cx=960.0, cy=540.0, rx=690.0, ry=372.0,
             node_r=4.6, edge_w=1.35, glow=9.0, base_alpha=0.30, new_alpha=0.95,
             node_alpha=1.0, full_alpha=None):
    """按真实生长排程画网：已有边压暗、新边逐条亮起；节点逐个出现。

    full_alpha 给定时（如 net_full），所有边使用同一透明度。
    """
    pos, node_a, ep = net_state(t, dur, n_from, n_to)
    n_to = int(n_to)
    xs = cx + rx * pos[:, 0]
    ys = cy + ry * pos[:, 1]
    edges = net_growth_order(n_to)
    e_pre = comb_edges(int(n_from))
    for e, (i, j) in enumerate(edges):
        pr = float(ep[e])
        if pr <= 0.0:
            continue
        grow_new = e >= e_pre
        a = (full_alpha if full_alpha is not None
             else (new_alpha if grow_new else base_alpha))
        a *= min(1.0, 0.35 + 0.65 * pr) if grow_new else 1.0
        if a <= 0.01:
            continue
        x0, y0 = float(xs[i]), float(ys[i])
        x1, y1 = float(xs[j]), float(ys[j])
        xm = x0 + (x1 - x0) * pr
        ym = y0 + (y1 - y0) * pr
        col = TEAL if grow_new else TEAL_D
        p.stroke([(x0, y0), (xm, ym)], col, edge_w if grow_new else edge_w * 0.9,
                 a, glow if grow_new else 0.0, 0.55)
    for k in range(n_to):
        na = float(node_a[k]) * node_alpha
        if na <= 0.01:
            continue
        r = node_r * (0.5 + 0.5 * na)
        p.dot((xs[k], ys[k]), r + 2.2, TEAL, 0.25 * na, 12, 0.5)
        p.dot((xs[k], ys[k]), r, ICE, 0.92 * na, 10, 0.7)
        p.dot((xs[k], ys[k]), r * 0.42, BONE, 0.95 * na)
    return xs, ys, node_a


def draw_floor_slab(p, x0, x1, y, h=18.0, depth=26.0, color=(118, 138, 150),
                    alpha=0.85, top_color=(150, 176, 188), glow=0.0):
    """2.5D 楼板：前缘 + 顶面平行四边形 + 两侧短墙。"""
    dy = depth * 0.55
    dx = depth
    p.stroke([(x0, y), (x1, y), (x1 + dx, y - dy), (x0 + dx, y - dy), (x0, y)],
             top_color, 1.5, alpha, glow, 0.35)
    p.stroke([(x0, y), (x1, y)], color, max(2.0, h * 0.10), alpha * 0.9)
    p.stroke([(x0, y + h), (x1, y + h)], (58, 72, 84), 1.0, alpha * 0.55)
    p.stroke([(x0, y), (x0, y + h)], (70, 86, 98), 1.0, alpha * 0.5)
    p.stroke([(x1, y), (x1, y + h)], (70, 86, 98), 1.0, alpha * 0.5)


def slab_y(base_y, floor_i, floor_h):
    """第 floor_i 层（1=地面层之上第一层）的楼板高度。"""
    return base_y - floor_i * floor_h


# ---------------------------------------------------------------- cold open
def scene_cold_title(t, dur, sh=None):
    bg = light_room_bg(t, dur)
    p = V.Painter(bg)
    pos = net_positions(20)
    xs = 960 + 700 * pos[:, 0]
    ys = 545 + 340 * pos[:, 1]
    grow = clamp((t - 0.05) / 1.4)
    n_vis = int(round(20 * ease_out_cubic(grow)))
    for k in range(1, n_vis):
        for i in range(k):
            p.stroke([(xs[i], ys[i]), (xs[k], ys[k])], TEAL_D, 1.0,
                     0.10 * clamp((t - 0.05) / 0.9), 0, 0)
    for k in range(n_vis):
        p.dot((xs[k], ys[k]), 2.2, TEAL, 0.18)
    lp = ease_in_out(clamp(t / 0.36))
    if lp > 0:
        x_end = lerp(300, 1620, lp)
        p.stroke([(300, 512), (x_end, 512)], GOLD, 1.5, 0.75, 12, 0.5)
        if lp > 0.98:
            p.dot((1620, 512), 3.0, GOLD, 0.8, 10, 0.6)
    p.flush()
    a0 = window(t, 0.02, dur - 0.02, 0.28, 0.3)
    V.draw_text(p.rgb, "VIBE 知识共赏 · 第 05 期", (960, 372), 24, MUTED, F_SANS_R,
                anchor="mm", alpha=0.72 * a0, track=5)
    a1 = window(t, 0.30, dur - 0.02, 0.45, 0.3)
    if a1 > 0:
        rise = 14 * (1 - ease_out_cubic(clamp((t - 0.30) / 0.6)))
        V.draw_text(p.rgb, "为什么公司越大，越容易自己绊自己", (960, 462 - rise), 66,
                    BONE, F_SERIF, anchor="mm", alpha=0.97 * a1, track=2,
                    glow=16, glow_strength=0.4)
    a2 = window(t, 0.72, dur - 0.02, 0.4, 0.3)
    if a2 > 0:
        V.draw_text(p.rgb, "一条逃不掉的数学，和三种不同的应对", (960, 560), 30, MUTED,
                    F_SANS_R, anchor="mm", alpha=0.86 * a2, track=3)
    p.bloom(threshold=0.64, strength=0.5)
    return p.to_image()


# ---------------------------------------------------------------- S2 关系网
def _net_labels(p, n, t, dur, live_edges=None, x=252, y=800, alpha=1.0,
                show_equation=True):
    """左下角小型数据刻度：n 人 / 关系数（中文走 F_SANS_R，数字走 F_MONO）。"""
    n = int(n)
    V.draw_text(p.rgb, "n = %d 人" % n, (x, y - 44), 32, MUTED, F_SANS_R, anchor="lm",
                alpha=0.8 * alpha, track=2)
    if show_equation:
        draw_mixed(p, [("关系 = ", TEAL, F_SANS_R),
                       ("%d × %d / 2 = %d" % (n, n - 1, comb_edges(n)), TEAL, F_MONO)],
                   (x, y), 34, alpha=0.9 * alpha, glow=8)
    ticks = min(comb_edges(n), 20)
    for k in range(ticks):
        xx = x + 6 + k * 13
        yy = y - 72
        p.stroke([(xx, yy), (xx, yy - 7)], TEAL_D, 1.0,
                 0.55 * alpha * (0.35 + 0.65 * clamp((t - 0.3 - k * 0.02) / 0.4)))


def scene_net_seed(t, dur, sh=None):
    """S1 s5：第一张网开始生长（3 节点 / 3 条线），不加标签。"""
    bg = light_room_bg(t, dur)
    p = V.Painter(bg)
    p.halo((960, 545), 520, TEAL, 0.05)
    draw_net(p, t, dur, 0, 3, cx=960, cy=545, rx=250, ry=170, node_r=6.0,
             edge_w=2.0, glow=14, base_alpha=0.5, new_alpha=1.0)
    p.flush()
    p.bloom(threshold=0.6, strength=0.55)
    return p.to_image()


def _net_scene(t, dur, n_from, n_to):
    bg = studio_bg(t, dur, tint=(0.38, 0.72, 0.80), strength=0.10, glow_xy=(0.5, 0.52))
    p = V.Painter(bg)
    p.halo((960, 540), 560, TEAL, 0.055)
    xs, ys, na = draw_net(p, t, dur, n_from, n_to)
    p.flush()
    n_vis = int(np.count_nonzero(na > 0.5))
    n_edges = V.net_edge_count(t, dur, n_from, n_to)
    a = clamp((t - 0.15) / 0.5)
    if a > 0:
        _net_labels(p, n_vis if n_vis else n_to, t, dur, live_edges=n_edges, alpha=a,
                    show_equation=(n_from == 0))
        draw_mixed(p, [("连线 ", TEAL, F_SANS_R), ("%d / %d" % (n_edges, comb_edges(n_to)), TEAL, F_MONO)],
                   (1668, 800), 30, anchor="rm", alpha=0.85 * a, glow=8)
        V.draw_text(p.rgb, "n(n−1)/2", (1668, 758), 24, MUTED, F_SANS_R,
                    anchor="rm", alpha=0.6 * a, track=2)
    p.bloom(threshold=0.62, strength=0.55)
    return p.to_image()


def scene_net_grow_n3(t, dur, sh=None):
    """S2 s2：管 3 个人 —— 3 点 / 3 线（慢，让观众先认“关系”）。"""
    return _net_scene(t, dur, 0, 3)


def scene_net_grow_n10(t, dur, sh=None):
    """S2 s3：管 10 个人 —— 从 3 节点长到 10 节点 / 45 条线。"""
    return _net_scene(t, dur, 3, 10)


def scene_net_grow_n20(t, dur, sh=None):
    """S2 s4：管 20 个人 —— 10→20 节点，190 条线按真实顺序生长到填满画面。"""
    return _net_scene(t, dur, 10, 20)


def scene_net_math(t, dur, sh=None):
    """S2 s5：加法 vs 乘法 —— 两条曲线用同一坐标系生长。"""
    bg = studio_bg(t, dur, tint=(0.34, 0.66, 0.74), strength=0.09, glow_xy=(0.46, 0.55))
    p = V.Painter(bg)
    p.halo((1180, 480), 620, TEAL, 0.05)
    x0, x1 = 360.0, 1640.0
    y_base, y_top = 792.0, 300.0
    max_rel = 190.0
    p.stroke([(x0, y_base), (x1 + 20, y_base)], (84, 100, 112), 1.2, 0.55)
    p.stroke([(x0, y_base + 8), (x0, y_top - 16)], (84, 100, 112), 1.2, 0.55)
    for nn in range(1, 21):
        xx = x0 + (x1 - x0) * (nn - 1) / 19.0
        p.stroke([(xx, y_base - 5), (xx, y_base + 5)], (70, 86, 98), 1.0, 0.45)
    p.flush()
    for nn in (1, 5, 10, 15, 20):
        xx = x0 + (x1 - x0) * (nn - 1) / 19.0
        V.draw_text(p.rgb, str(nn), (xx, y_base + 30), 22, DIM, F_MONO, anchor="mm",
                    alpha=0.6, track=0)
    grow = ease_out_cubic(clamp((t - 0.25) / max(0.6, dur * 0.52)))
    n_draw = max(2, int(round(lerp(2, 21, grow))))
    ns = np.linspace(1, 20, n_draw)
    add = ns
    mul = ns * (ns - 1) / 2.0
    px = x0 + (x1 - x0) * (ns - 1) / 19.0
    py_add = y_base - (add / max_rel) * (y_base - y_top)
    py_mul = y_base - (mul / max_rel) * (y_base - y_top)
    p.stroke(np.stack([px, py_add], 1), AMBER, 2.4, 0.9, 12, 0.6)
    p.stroke(np.stack([px, py_mul], 1), TEAL, 2.8, 0.96, 16, 0.75)
    p.flush()
    if grow > 0.5:
        a = clamp((grow - 0.5) / 0.35)
        p.dot((px[-1], py_add[-1]), 4.5, AMBER, 0.9 * a, 10, 0.6)
        p.dot((px[-1], py_mul[-1]), 6.0, TEAL, 0.95 * a, 14, 0.8)
        p.flush()
    a = clamp((t - 0.6) / 0.7)
    if a > 0:
        V.draw_text(p.rgb, "加法 · 人数 n", (x0 + 40, 420), 30, AMBER, F_SANS_R,
                    anchor="lm", alpha=0.85 * a, track=2)
        V.draw_text(p.rgb, "乘法 · 关系数 n(n−1)/2", (1000, 316), 30, TEAL, F_SANS_R,
                    anchor="lm", alpha=0.9 * a, track=2)
    a2 = clamp((grow - 0.55) / 0.4)
    if a2 > 0:
        V.draw_text(p.rgb, "20", (px[-1] + 24, py_add[-1] - 4), 34, AMBER, F_MONO,
                    anchor="lm", alpha=0.9 * a2)
        V.draw_text(p.rgb, "190", (px[-1] + 24, py_mul[-1] - 6), 44, TEAL, F_MONO,
                    anchor="lm", alpha=0.95 * a2, glow=10, glow_strength=0.35)
        V.draw_text(p.rgb, "× 9.5", (px[-1] - 120, py_mul[-1] + 60), 32, GOLD, F_MONO,
                    anchor="rm", alpha=0.85 * a2, glow=8, glow_strength=0.3)
    a3 = clamp((t - dur * 0.62) / 0.9)
    if a3 > 0:
        V.draw_text(p.rgb, "下属人数按加法涨，关系数按乘法涨", (960, 862), 32, BONE,
                    F_SANS, anchor="mm", alpha=0.8 * a3, track=2)
    p.bloom(threshold=0.62, strength=0.55)
    return p.to_image()


def scene_net_full(t, dur, sh=None):
    """S2 s8：20 人 / 190 条关系 —— 网密到屏息，沟通开始漏。"""
    bg = studio_bg(t, dur, tint=(0.30, 0.60, 0.70), strength=0.08, glow_xy=(0.5, 0.5))
    p = V.Painter(bg)
    p.halo((960, 540), 600, TEAL_D, 0.07)
    pos, node_a, ep = net_state(t, dur, 20, 20)
    cx, cy, rx, ry = 960.0, 538.0, 700.0, 372.0
    xs = cx + rx * pos[:, 0]
    ys = cy + ry * pos[:, 1]
    breath = 1.0 + 0.006 * math.sin(t * 0.9)
    xs = cx + (xs - cx) * breath
    ys = cy + (ys - cy) * breath
    edges = net_growth_order(20)
    rng = np.random.default_rng(7)
    leak = set(rng.choice(len(edges), 9, replace=False).tolist())
    for e, (i, j) in enumerate(edges):
        x0, y0 = float(xs[i]), float(ys[i])
        x1, y1 = float(xs[j]), float(ys[j])
        mid = ((x0 + x1) * 0.5 - 960) / 700.0
        wave = 0.5 + 0.5 * math.sin(t * 1.1 - 3.0 + mid * 2.2)
        a = 0.30 + 0.22 * wave
        if e in leak:
            ph = (t * 0.32 + e * 0.137) % 1.0
            a *= 0.15 + 0.85 * clamp((ph - 0.55) / 0.25) * clamp((1.05 - ph) / 0.2)
        p.stroke([(x0, y0), (x1, y1)], TEAL, 1.25, a, 0.0, 0)
    for k in range(20):
        r = 4.4 + (0.6 * math.sin(t * 1.3 + k) if k % 3 == 0 else 0.0)
        p.dot((xs[k], ys[k]), r, ICE, 0.85, 10, 0.6)
        p.dot((xs[k], ys[k]), r * 0.4, BONE, 0.9)
    for e in list(leak)[:5]:
        i, j = edges[e]
        mx = (xs[i] + xs[j]) * 0.5
        my = (ys[i] + ys[j]) * 0.5
        ph = (t * 0.32 + e * 0.137) % 1.0
        if ph > 0.45:
            fall = clamp((ph - 0.45) / 0.5)
            p.dot((mx + 6 * math.sin(e + t), my + 26 * fall), 2.6, EMBER,
                  0.55 * (1 - fall))
    p.flush()
    a = clamp((t - 0.3) / 0.8)
    if a > 0:
        V.draw_text(p.rgb, "20 个人 · 190 条关系", (252, 800), 30, MUTED, F_SANS_R,
                    anchor="lm", alpha=0.72 * a, track=2)
        V.draw_text(p.rgb, "沟通开始漏", (252, 846), 34, AMBER, F_SANS_R, anchor="lm",
                    alpha=0.75 * a, track=3)
        for k in range(10):
            xx = 252 + 6 + k * 12
            p.stroke([(xx, 746), (xx, 739)], TEAL_D, 1.0, 0.4 * a)
    p.flush()
    p.bloom(threshold=0.60, strength=0.55)
    return p.to_image()


# ---------------------------------------------------------------- S3 层级 / 电梯
F_BASE_Y = 856.0        # 地面
F_H = 64.0              # 层高（像素）
F_X0, F_X1 = 566.0, 1042.0
F_DEPTH = 30.0
SHAFT_X = 998.0


def _floor_y(i):
    """第 i 层（1 = 最底层）楼板 y。"""
    return F_BASE_Y - (i - 1) * F_H


def _draw_building(p, n_present, rise_anim, alpha=1.0):
    """楼板自下而上堆叠；rise_anim 为正在升起楼层的进度。"""
    for i in range(1, n_present + 1):
        prog = float(rise_anim.get(i, 1.0))
        ease = ease_out_cubic(clamp(prog))
        y = _floor_y(i) + (1.0 - ease) * 48.0
        a = alpha * (0.18 + 0.82 * ease)
        draw_floor_slab(p, F_X0, F_X1, y, h=13.0, depth=F_DEPTH, alpha=a,
                        top_color=(146, 172, 184))
        # 层内走廊（每层都要绕的通道）
        for k in range(3):
            xx0 = F_X0 + 42 + k * 150
            for seg in V.dashed(np.array([[xx0, y - 15], [xx0 + 92, y - 15]]), 10, 9):
                p.stroke(seg, (92, 112, 124), 1.0, 0.26 * a)
        # 侧墙
        if i < n_present:
            y_up = _floor_y(i + 1)
            p.stroke([(F_X0, y), (F_X0, y_up)], (78, 96, 108), 1.3, 0.5 * a)
            p.stroke([(F_X1, y), (F_X1, y_up)], (78, 96, 108), 1.3, 0.5 * a)
        if ease < 0.999:
            # 落位时的短促亮线（“咔哒”上锁，不是弹卡）
            p.stroke([(F_X0, y), (F_X1, y)], GOLD, 2.4, (1.0 - ease) * 0.7, 12, 0.5)


def _draw_shaft(p, n_present, u, t, glow_on=True):
    """电梯井 + 停靠刻度 + 轿厢 + 已停靠点。返回 (car_y, stop_idx, pos)。"""
    if n_present < 2:
        return _floor_y(n_present), 0, 0.0
    y_top = _floor_y(n_present)
    y_bot = F_BASE_Y
    p.stroke([(SHAFT_X, y_top - 10), (SHAFT_X, y_bot)], (96, 116, 128), 1.2, 0.5)
    p.stroke([(SHAFT_X + 26, y_top - 10), (SHAFT_X + 26, y_bot)], (60, 76, 88), 1.0, 0.28)
    pos, stop, dwell, travel = elevator_journey(u, n_present)
    car_y = y_top + pos * (y_bot - y_top)
    # 停靠刻度 + 已停靠亮起
    for k in range(n_present):
        yy = _floor_y(k + 1)
        p.stroke([(SHAFT_X - 4, yy), (SHAFT_X + 22, yy)], (110, 130, 142), 1.0, 0.5)
        # 刻度从下往上编号；电梯 journey 的 stop 从顶层向下编号（0=顶层）
        top_idx = n_present - 1 - k
        visited = (top_idx <= stop)
        if top_idx == 0:
            visited = True
        if visited and glow_on:
            p.dot((SHAFT_X + 44, yy), 3.6, AMBER, 0.9, 10, 0.6)
        else:
            p.dot((SHAFT_X + 44, yy), 2.6, DIM, 0.45)
    # 轿厢
    p.stroke([(SHAFT_X - 16, car_y - 17), (SHAFT_X + 12, car_y - 17),
              (SHAFT_X + 12, car_y + 17), (SHAFT_X - 16, car_y + 17)],
             ICE, 1.8, 0.9, 10, 0.5, closed=True)
    p.stroke([(SHAFT_X - 12, car_y), (SHAFT_X + 8, car_y)], ICE, 1.0, 0.45)
    return car_y, stop, pos


def _stats_panel(p, n, t_since_change, alpha=1.0):
    """右侧数据：层数 / 停靠 / 路径 / 耗时（等宽数字，随 n 变化）。"""
    x = 1180.0
    exp = clamp(t_since_change / 0.28)
    flash = 1.0 - clamp(t_since_change / 0.9)
    col_n = AMBER if flash > 0.02 else TEAL
    y = 316.0
    V.draw_text(p.rgb, "层数", (x, y), 26, MUTED, F_SANS_R, anchor="lm", alpha=0.7 * alpha,
                track=3)
    draw_mixed(p, [("%d" % n, col_n, F_MONO), (" 层", BONE, F_SANS_R)],
               (x, y + 56), 66, alpha=alpha, glow=12)
    p.stroke([(x, y + 104), (x + 470, y + 104)], (92, 108, 120), 1.0, 0.42 * alpha)
    rows = [("电梯停靠", "%d 次" % n, 34),
            ("下楼路径", "%.1f m" % floor_path_len(n), 34),
            ("下楼耗时", "≈ %d s" % floor_stop_time(n), 34)]
    for k, (label, val, sz) in enumerate(rows):
        yy = y + 156 + k * 72
        V.draw_text(p.rgb, label, (x, yy), 24, MUTED, F_SANS_R, anchor="lm",
                    alpha=0.68 * alpha, track=2)
        draw_mixed(p, [(val, TEAL if k else AMBER, F_MONO)], (x, yy + 34), sz,
                   alpha=0.92 * alpha, glow=8 if k == 0 else 0)
    aa = clamp((t_since_change - 0.15) / 0.4) * alpha
    if aa > 0:
        V.draw_text(p.rgb, "路径 = 3.6 m × 层 + 12 m × 停靠", (x, y + 430), 22, DIM,
                    F_SANS_R, anchor="lm", alpha=0.62 * aa, track=1)


def scene_floors_rise(t, dur, sh=None):
    """S3 s3：楼板一层层升起（3→5→8）；每次加层，下楼多停一次、路径更长、更慢。"""
    bg = studio_bg(t, dur, tint=(0.36, 0.64, 0.70), strength=0.09, glow_xy=(0.40, 0.5))
    p = V.Painter(bg)
    p.halo((760, 780), 520, TEAL_D, 0.05)
    # 时间轴（4.22s）：A 段 3 层下楼 → 加到 5 层 → B 段 5 层下楼 → 加到 8 层 → C 段未下完
    marks = [(0.10, "A"), (1.06, "+4"), (1.32, "+5"), (1.58, "B"), (3.02, "+6"),
             (3.24, "+7"), (3.46, "+8"), (3.66, "C")]
    t_marks = [m[0] for m in marks]
    n = 3
    if t >= 1.32:
        n = 4
    if t >= 1.58:
        n = 5
    if t >= 3.24:
        n = 6
    if t >= 3.46:
        n = 7
    if t >= 3.66:
        n = 8
    rise_anim = {}
    for fl, t0 in ((4, 1.06), (5, 1.32), (6, 3.02), (7, 3.24), (8, 3.46)):
        if t >= t0:
            rise_anim[fl] = clamp((t - t0) / 0.24)
    # 电梯循环：每停靠一次 0.30 s（层数越多，一次完整下楼越久）
    loops = [(0.10, 3), (1.58, 5), (3.66, 8)]
    u, n_loop = 0.0, 3
    for t0, nn in loops:
        if t >= t0:
            u = (t - t0) / (0.30 * nn)
            n_loop = nn
    u = clamp(u)
    if t < 0.10:
        u, n_loop = 0.0, 3
    # 地面
    p.stroke([(300, F_BASE_Y), (1700, F_BASE_Y)], (88, 104, 116), 1.4, 0.6, 12, 0.3)
    p.stroke([(300, F_BASE_Y + 8), (1700, F_BASE_Y + 8)], (54, 68, 80), 1.0, 0.35)
    _draw_building(p, n, rise_anim)
    car_y, stop, pos = _draw_shaft(p, n, u, t)
    p.flush()
    # 已走路径（轿厢轨迹，越走越长；下一循环重置）
    y_top = _floor_y(n)
    if pos > 0.02:
        p.stroke([(SHAFT_X - 8, y_top), (SHAFT_X - 8, car_y)], AMBER, 1.2, 0.28)
    # 左侧竖向主张（一屏一个第一视觉重点：楼与“慢”）
    a = clamp((t - 0.2) / 0.7)
    if a > 0:
        V.draw_text(p.rgb, "楼越高", (286, 440), 46, BONE, F_SERIF, anchor="lm",
                    alpha=0.92 * a, track=3, glow=12, glow_strength=0.3)
        V.draw_text(p.rgb, "下楼越慢", (286, 504), 46, AMBER, F_SERIF, anchor="lm",
                    alpha=0.92 * a, track=3, glow=12, glow_strength=0.3)
        V.draw_text(p.rgb, "加一层 · 多停一次", (286, 578), 24, MUTED, F_SANS_R,
                    anchor="lm", alpha=0.72 * a, track=2)
        V.draw_text(p.rgb, "路径更长", (286, 614), 24, MUTED, F_SANS_R,
                    anchor="lm", alpha=0.62 * a, track=2)
        V.draw_text(p.rgb, "审批更多", (286, 650), 24, MUTED, F_SANS_R,
                    anchor="lm", alpha=0.62 * a, track=2)
    # 右侧数据（n 变化时数字跳一下）
    t_change = 0.0
    for fl, t0 in ((4, 1.32), (5, 1.58), (6, 3.24), (7, 3.46), (8, 3.66)):
        if t >= t0:
            t_change = t - t0
    _stats_panel(p, n, t_change)
    p.flush()
    p.bloom(threshold=0.62, strength=0.5)
    return p.to_image()


# ---------------------------------------------------------------- S3 循环
def scene_loop_complex(t, dur, sh=None):
    """S3 s10：闭环 —— 复杂→加层→更复杂→再加层；每转一圈，中间多一层、外圈更密。"""
    bg = studio_bg(t, dur, tint=(0.34, 0.60, 0.64), strength=0.08,
                   glow_xy=(0.5, 0.48))
    p = V.Painter(bg)
    p.halo((960, 520), 560, TEAL_D, 0.06)
    cx, cy = 960.0, 505.0
    rx, ry = 430.0, 232.0
    lap = t / 2.55
    lap_i = int(math.floor(lap))
    phase = (lap % 1.0)
    levels = min(8, 3 + lap_i)
    # 中心塔：每圈加一层（“加了层”）
    for i in range(1, levels + 1):
        y = 706.0 - (i - 1) * 30.0
        appear = 1.0 if i <= levels - 1 else clamp(lap * levels / max(1e-3, levels))
        draw_floor_slab(p, cx - 140, cx + 140, y, h=9.0, depth=18.0,
                        alpha=0.62 * appear, top_color=(150, 172, 182))
    # 外圈随圈数变密：内嵌 0、1、2 圈
    for ring in range(0, min(2, lap_i) + 1):
        scale = 1.0 - ring * 0.22
        th = np.linspace(0, 2 * math.pi, 240)
        p.stroke(np.stack([cx + rx * scale * np.cos(th),
                           cy + ry * scale * np.sin(th)], 1),
                 TEAL_D, 1.4, 0.26 if ring else 0.52, 8 if not ring else 0, 0.35)
    # 四个节点 + 标签
    labels = [("复杂", -math.pi / 2), ("加层", 0.0), ("更复杂", math.pi / 2),
              ("再加层", math.pi)]
    for (txt, ang) in labels:
        nx = cx + rx * math.cos(ang)
        ny = cy + ry * math.sin(ang)
        p.dot((nx, ny), 5.5, ICE, 0.9, 12, 0.6)
        lx = nx + (0 if abs(math.cos(ang)) < 0.2 else (34 if math.cos(ang) > 0 else -34))
        ly = ny + (-30 if math.sin(ang) < -0.2 else (30 if math.sin(ang) > 0.2 else 0))
        anchor = "mm" if abs(math.cos(ang)) < 0.2 else ("lm" if math.cos(ang) > 0 else "rm")
        V.draw_text(p.rgb, txt, (lx, ly), 46, BONE, F_SERIF, anchor=anchor,
                    alpha=0.9, track=2, glow=10, glow_strength=0.35)
    # 环上追逐的箭头：每圈 +2 支
    n_arrow = 4 + 2 * lap_i
    for k in range(n_arrow):
        ang = 2 * math.pi * k / n_arrow - math.pi / 2 + phase * 2 * math.pi
        x = cx + rx * math.cos(ang)
        y = cy + ry * math.sin(ang)
        dx = -rx * math.sin(ang)
        dy = ry * math.cos(ang)
        nrm = math.hypot(dx, dy) + 1e-9
        p.stroke([(x - dx / nrm * 40, y - dy / nrm * 40), (x, y)], GOLD, 2.6, 0.92, 14, 0.6)
        for sgn in (-1, 1):
            ca, sa = math.cos(sgn * 0.5), math.sin(sgn * 0.5)
            hx = -(dx / nrm * ca - dy / nrm * sa)
            hy = -(dx / nrm * sa + dy / nrm * ca)
            p.stroke([(x, y), (x + hx * 17, y + hy * 17)], GOLD, 2.6, 0.9)
    p.flush()
    # 角落小刻度：第几圈 / 中间几层
    a = clamp((t - 0.25) / 0.6)
    if a > 0:
        draw_mixed(p, [("循环 ", MUTED, F_SANS_R), ("%d" % (lap_i + 1), TEAL, F_MONO)],
                   (252, 806), 28, alpha=0.7 * a)
        draw_mixed(p, [("中央 ", MUTED, F_SANS_R), ("%d" % levels, AMBER, F_MONO),
                       (" 层", MUTED, F_SANS_R)], (252, 852), 26, alpha=0.62 * a)
    p.bloom(threshold=0.62, strength=0.5)
    return p.to_image()


# ---------------------------------------------------------------- S4 离心箭头
ARROW_CX, ARROW_CY = 960.0, 556.0
ARROW_RX, ARROW_RY = 760.0, 330.0


def _arrows_bg(t, phase):
    bg = studio_bg(t, 8.0, tint=(0.30, 0.62, 0.70), strength=0.10,
                   glow_xy=(0.5, 0.46))
    nx, ny = grid()
    void = smoothstep(7.0, 22.0, phase)
    r2 = ((nx - 0.5) / 0.30) ** 2 + ((ny - 0.515) / 0.34) ** 2
    bg *= (1.0 - 0.40 * void * np.exp(-r2))[..., None]
    return bg


def _draw_lone_doc(p, t, alpha=0.8):
    """中央“事情”本身：一张很小的纸，被所有箭头的离心力留在原地。"""
    cx, cy = ARROW_CX, ARROW_CY
    w, h = 44.0, 58.0
    ang = math.radians(7.0 + 3.0 * math.sin(t * 0.45))
    ca, sa = math.cos(ang), math.sin(ang)

    def rot(dx, dy):
        return (cx + dx * ca - dy * sa, cy + dx * sa + dy * ca)
    corners = [rot(-w / 2, -h / 2), rot(w / 2, -h / 2), rot(w / 2, h / 2),
               rot(-w / 2, h / 2), rot(-w / 2, -h / 2)]
    p.stroke(corners, BONE, 1.6, 0.72 * alpha, 10, 0.35)
    p.stroke([rot(-w / 2 + 7, -h / 2 + 12), rot(w / 2 - 7, -h / 2 + 12)],
             (170, 186, 196), 1.1, 0.5 * alpha)
    p.stroke([rot(-w / 2 + 7, -h / 2 + 21), rot(w / 2 - 7, -h / 2 + 21)],
             (150, 166, 178), 1.1, 0.42 * alpha)
    p.stroke([rot(-w / 2 + 7, -h / 2 + 30), rot(w / 2 - 18, -h / 2 + 30)],
             (130, 146, 158), 1.1, 0.36 * alpha)
    p.halo((cx, cy), 46, GOLD, 0.10 * alpha)


def _draw_arrows(p, phase, alpha_mul=1.0):
    st = arrow_screen(phase, ARROW_CX, ARROW_CY, ARROW_RX, ARROW_RY)
    for i in range(V.ARROW_N):
        act = float(st["active"][i]) * alpha_mul
        if act <= 0.02:
            continue
        x, y = float(st["xs"][i]), float(st["ys"][i])
        dx, dy = float(st["dx"][i]), float(st["dy"][i])
        sz = float(st["size"][i])
        depth = 0.60 + 0.40 * float(st["r"][i])
        col = AMBER if (i % 9 == 0) else (ICE if i % 3 == 0 else TEAL)
        L = (13.0 + 12.0 * sz) * depth
        # 拖动残影：说明“正在向外逃”
        p.stroke([(x - dx * L * 2.3, y - dy * L * 2.3), (x - dx * L * 0.5, y - dy * L * 0.5)],
                 col, 1.6, 0.20 * act, 0, 0)
        p.stroke([(x - dx * L * 4.2, y - dy * L * 4.2), (x - dx * L * 2.2, y - dy * L * 2.2)],
                 col, 1.2, 0.09 * act, 0, 0)
        arrow_head(p, x, y, dx, dy, size=L, color=col,
                   alpha=0.62 + 0.38 * act * depth, width=2.2)


def _arrow_count(p, phase, t, dur):
    st = arrow_screen(phase, ARROW_CX, ARROW_CY, ARROW_RX, ARROW_RY)
    vis = int(np.count_nonzero(st["active"] > 0.5))
    a = clamp((t - 0.2) / 0.7)
    if a <= 0:
        return
    draw_mixed(p, [("离心 ", MUTED, F_SANS_R), ("%d" % vis, TEAL, F_MONO),
                   (" / %d" % V.ARROW_N, MUTED, F_MONO)], (252, 858), 26, alpha=0.6 * a)
    V.draw_text(p.rgb, "各自朝外 · 理性自保", (252, 806), 28, MUTED, F_SANS_R,
                anchor="lm", alpha=0.62 * a, track=2)


def scene_arrows_swarm(t, dur, sh=None):
    """S4 s3：箭头逐个向外自保，密度上升（慢，全片最重的一锤开始）。"""
    phase = ARROW_PHASE["swarm"] + t
    bg = _arrows_bg(t, phase)
    p = V.Painter(bg)
    _draw_arrows(p, phase)
    p.flush()
    _arrow_count(p, phase, t, dur)
    p.bloom(threshold=0.60, strength=0.55)
    return p.to_image()


def scene_arrows_blank(t, dur, sh=None):
    """S4 s7：中央被腾空 —— 谁都不越界，事情卡在缝里。"""
    phase = ARROW_PHASE["blank"] + t
    bg = _arrows_bg(t, phase)
    p = V.Painter(bg)
    _draw_arrows(p, phase, alpha_mul=0.92)
    _draw_lone_doc(p, t, alpha=0.55 + 0.35 * clamp(t / max(dur, 1e-3)))
    p.flush()
    p.bloom(threshold=0.60, strength=0.5)
    return p.to_image()


def scene_arrows_still(t, dur, sh=None):
    """S4 s9：定格 —— 整体不理性；几乎不动，只剩中央一点微弱呼吸。"""
    phase = ARROW_PHASE["still"] + t * 0.12
    bg = _arrows_bg(t, phase)
    p = V.Painter(bg)
    _draw_arrows(p, phase, alpha_mul=0.82)
    _draw_lone_doc(p, t, alpha=0.72 + 0.12 * math.sin(t * 0.7))
    p.flush()
    p.bloom(threshold=0.60, strength=0.5)
    return p.to_image()


# ---------------------------------------------------------------- S5 变革疲劳
FAT_X0, FAT_X1, FAT_YTOP, FAT_YBOT = 320.0, 1600.0, 300.0, 780.0


def _fat_xy(s, x0=FAT_X0, x1=FAT_X1, ytop=FAT_YTOP, ybot=FAT_YBOT):
    return fatigue_xy(s, x0, x1, ytop, ybot)


def _fat_axes(p, y_axis=True, y_label=True, years=True):
    p.stroke([(FAT_X0, FAT_YBOT), (FAT_X1, FAT_YBOT)], (88, 104, 116), 1.2, 0.55)
    if y_axis:
        p.stroke([(FAT_X0, FAT_YBOT + 6), (FAT_X0, FAT_YTOP - 8)], (88, 104, 116), 1.2, 0.5)
        for v in (40, 50, 60, 70):
            y = FAT_YBOT - (v - FATIGUE_VMIN) / (FATIGUE_VMAX - FATIGUE_VMIN) * (FAT_YBOT - FAT_YTOP)
            p.stroke([(FAT_X0 - 5, y), (FAT_X0 + 5, y)], (74, 90, 102), 1.0, 0.4)
            V.draw_text(p.rgb, "%d" % v, (FAT_X0 - 14, y), 20, DIM, F_MONO,
                        anchor="rm", alpha=0.55)
        if y_label:
            V.draw_text(p.rgb, "支持意愿 %", (FAT_X0 + 12, FAT_YTOP + 18), 21, MUTED,
                        F_SANS_R, anchor="lm", alpha=0.5, track=1)
    for s, lab in ((0.0, "2016"), (1.0, "2022")):
        x = FAT_X0 + (FAT_X1 - FAT_X0) * s
        p.stroke([(x, FAT_YBOT), (x, FAT_YBOT + 7)], (74, 90, 102), 1.0, 0.45)
        if years:
            V.draw_text(p.rgb, lab, (x, FAT_YBOT + 34), 24, MUTED, F_MONO, anchor="mm",
                        alpha=0.6, track=1)
    p.stroke([(FAT_X1 + 14, FAT_YBOT + 40), (FAT_X1 + 64, FAT_YBOT + 40)], (60, 74, 86),
             1.0, 0.35)
    V.draw_text(p.rgb, "年", (FAT_X1 + 72, FAT_YBOT + 40), 20, DIM, F_SANS_R,
                anchor="lm", alpha=0.5)


def scene_fatigue_curve(t, dur, sh=None):
    """S5 s3：一条被反复拉起的曲线 —— 每次拉高，峰值一次比一次矮。"""
    bg = studio_bg(t, dur, tint=(0.40, 0.52, 0.48), strength=0.08, glow_xy=(0.46, 0.58))
    p = V.Painter(bg)
    p.halo((980, 640), 560, TEAL_D, 0.05)
    _fat_axes(p)
    pr = ease_in_out(clamp((t - 0.35) / max(0.8, dur * 0.60)))
    if pr > 0:
        pts = fatigue_points(0.0, pr, max(3, int(240 * max(pr, 0.02))))
        p.stroke(pts, TEAL, 2.7, 0.96, 16, 0.75)
        if pr < 0.999:
            p.dot(tuple(pts[-1]), 5.0, ICE, 0.95, 12, 0.7)
    # 峰值：被拉起的地方（点 + 短刻度）
    for (s, v) in fatigue_peaks():
        if pr >= s:
            x, y = _fat_xy(s)
            p.dot((x, y), 4.2, AMBER, 0.9, 10, 0.6)
            p.stroke([(x, y - 8), (x, y - 22)], AMBER, 1.0, 0.45)
    p.flush()
    a = clamp((t - 0.25) / 0.7)
    if a > 0:
        V.draw_text(p.rgb, "变革疲劳", (252, 224), 52, BONE, F_SERIF, anchor="lm",
                    alpha=0.92 * a, track=3, glow=12, glow_strength=0.35)
        V.draw_text(p.rgb, "反复重组 · 下一次更难", (252, 276), 26, MUTED, F_SANS_R,
                    anchor="lm", alpha=0.68 * a, track=2)
    if pr > 0.88:
        aa = clamp((pr - 0.88) / 0.1)
        draw_mixed(p, [("被拉起 ", MUTED, F_SANS_R), ("6", TEAL, F_MONO),
                       (" 次 · 峰值一次比一次低", MUTED, F_SANS_R)],
                   (1668, 864), 26, anchor="rm", alpha=0.66 * aa)
    p.bloom(threshold=0.62, strength=0.55)
    return p.to_image()


def scene_fatigue_data(t, dur, sh=None):
    """S5 s6：74% → 43% —— 两个数字落在同一条曲线的两端。"""
    bg = studio_bg(t, dur, tint=(0.38, 0.50, 0.46), strength=0.07, glow_xy=(0.5, 0.55))
    p = V.Painter(bg)
    p.halo((980, 620), 560, TEAL_D, 0.045)
    _fat_axes(p, y_label=False)
    pts = fatigue_points(0.0, 1.0, 240)
    p.stroke(pts, TEAL, 2.6, 0.90, 14, 0.7)
    s16, v16 = fatigue_mark(2016)
    s22, v22 = fatigue_mark(2022)
    x16, y16 = _fat_xy(s16)
    x22, y22 = _fat_xy(s22)
    m1 = clamp((t - 1.35) / 0.55)
    m2 = clamp((t - 3.10) / 0.55)
    if m1 > 0:
        a = m1
        p.dot((x16, y16), 6.5, AMBER, 0.95 * a, 18, 0.8)
        p.stroke([(x16, y16), (x16, FAT_YBOT)], AMBER, 1.1, 0.35 * a,
                 0, 0)
        for rr in (12, 20):
            p.stroke([(x16 + rr * math.cos(a0), y16 + rr * math.sin(a0))
                      for a0 in np.linspace(0, 2 * math.pi, 36)],
                     AMBER, 1.0, 0.30 * a, 0, 0)
        p.flush()
    if m2 > 0:
        a = m2
        p.dot((x22, y22), 6.5, TEAL, 0.95 * a, 18, 0.8)
        p.stroke([(x22, y22), (x22, FAT_YBOT)], TEAL, 1.1, 0.5 * a, 0, 0)
        # 落差：细虚线（数字由 overlay data_74_43 压上）
        lp = ease_in_out(clamp((t - 3.5) / 1.4))
        if lp > 0:
            xm = x16 + (x22 - x16) * lp
            ym = y16 + (y22 - y16) * lp
            p.dot((xm, ym), 3.2, GOLD, 0.85, 8, 0.5)
            p.stroke([(x16, y16), (xm, ym)], GOLD, 1.4, 0.55, 8, 0.4)
        p.flush()
    # 首尾留出的数据标签空间（overlay 会压 74% / 43%）
    a = clamp((t - 0.3) / 0.8)
    if a > 0:
        V.draw_text(p.rgb, "支持变革的意愿", (252, 232), 46, BONE, F_SERIF, anchor="lm",
                    alpha=0.9 * a, track=3, glow=12, glow_strength=0.32)
    p.bloom(threshold=0.62, strength=0.55)
    return p.to_image()


def scene_fatigue_pull(t, dur, sh=None):
    """S5 s10：最后一次拉不动 —— 峰值只抬了一点点，然后继续往下走。"""
    bg = studio_bg(t, dur, tint=(0.40, 0.48, 0.42), strength=0.07, glow_xy=(0.52, 0.56))
    p = V.Painter(bg)
    p.halo((1000, 640), 540, TEAL_D, 0.04)
    _fat_axes(p, y_axis=False)
    pts = fatigue_points(0.0, 1.0, 280)
    # 早先的峰值压暗（已经发生的），最后一段提亮
    cut = int(len(pts) * 0.74)
    p.stroke(pts[:cut], TEAL_D, 2.4, 0.34, 0, 0)
    p.stroke(pts[cut - 1:], TEAL, 2.8, 0.92, 16, 0.7)
    peaks = fatigue_peaks()
    for (s, v) in peaks[:-1]:
        x, y = _fat_xy(s)
        p.dot((x, y), 3.2, AMBER, 0.35, 0, 0)
    # 最后一次拉动：峰值与前面的谷底（真实模型里测量，不手填）
    s_last, v_last = peaks[-1]
    s_trough = FATIGUE_T[4] if len(FATIGUE_T) > 4 else 0.68
    ss = np.linspace(FATIGUE_T[4], s_last, 200)
    vs = np.array([fatigue_support(x) for x in ss])
    j = int(np.argmin(vs))
    s_tr, v_tr = float(ss[j]), float(vs[j])
    lift = v_last - v_tr
    xl, yl = _fat_xy(s_last)
    xt, yt = _fat_xy(s_tr)
    a = clamp((t - 1.2) / 0.8)
    if a > 0:
        p.dot((xl, yl), 6.0, GOLD, 0.95 * a, 18, 0.8)
        p.stroke([(xl, yl + 8), (xl, yl + 34)], GOLD, 1.2, 0.7 * a, 8, 0.4)
        p.stroke([(xl - 16, yl + 34), (xl + 16, yl + 34)], GOLD, 1.2, 0.7 * a)
        # 抬升幅度（真实测量值）
        p.stroke([(xt - 26, yt), (xt - 26, yl)], (150, 166, 178), 1.0, 0.4 * a)
        p.stroke([(xt - 32, yt), (xt - 20, yt)], (150, 166, 178), 1.0, 0.4 * a)
        p.stroke([(xt - 32, yl), (xt - 20, yl)], (150, 166, 178), 1.0, 0.4 * a)
        p.flush()
    aa = clamp((t - 2.0) / 0.8)
    if aa > 0:
        draw_mixed(p, [("最后一次 · 只抬 ", MUTED, F_SANS_R),
                       ("+%.1f" % lift, GOLD, F_MONO), (" pp", MUTED, F_SANS_R)],
                   (1668, 864), 28, anchor="rm", alpha=0.7 * aa,
                   glow=8)
        V.draw_text(p.rgb, "拉不动了", (1668, 764), 34, AMBER, F_SANS_R, anchor="rm",
                    alpha=0.85 * aa, track=3)
    p.bloom(threshold=0.62, strength=0.55)
    return p.to_image()


# ---------------------------------------------------------------- S6 网松开
def scene_net_loosen(t, dur, sh=None):
    """S6 s1：同一张网被慢慢松开一条缝，光从缝里透进来（不是剪断，是留出通路）。"""
    loosen = smoothstep(0.10, 0.80, clamp(t / max(dur, 1e-3)))
    nx, ny = grid()
    seam_x = 0.552 + 0.018 * np.sin((ny - 0.5) * 3.2)
    sigma = 0.010 + 0.034 * loosen
    inten = 0.30 + 0.70 * loosen
    light = np.exp(-((nx - seam_x) ** 2) / (2 * sigma ** 2)) * inten
    bg = studio_bg(t, dur, tint=(0.36, 0.60, 0.64), strength=0.08, glow_xy=(0.5, 0.5))
    bg += light[..., None] * np.array([0.55, 0.62, 0.52], np.float32) * 0.35
    p = V.Painter(bg)
    cx, cy, rx, ry = 960.0, 540.0, 760.0, 340.0
    pos = net_positions(20)
    sx = pos[:, 0].copy()
    sy = pos[:, 1].copy()
    d = sx - (0.052 + 0.018 * np.sin((sy - 0.5) * 3.2))
    disp = np.sign(d) * loosen * 0.155 * np.exp(-(d / 0.26) ** 2)
    sx = sx + disp
    xs = cx + rx * sx
    ys = cy + ry * sy
    edges = net_growth_order(20)
    for e, (i, j) in enumerate(edges):
        x0, y0 = float(xs[i]), float(ys[i])
        x1, y1 = float(xs[j]), float(ys[j])
        seam_hits = (d[i] * d[j] < 0)
        if seam_hits:
            # 跨越缝的线被拉长、变松（不是剪断）
            a = 0.30 * (1.0 - 0.55 * loosen)
            col = (120, 150, 158)
            p.stroke([(x0, y0), (x1, y1)], col, 1.1, a, 0, 0)
        else:
            p.stroke([(x0, y0), (x1, y1)], TEAL_D, 1.2, 0.20, 0, 0)
    for k in range(20):
        p.dot((xs[k], ys[k]), 4.0, ICE, 0.72, 10, 0.5)
        p.dot((xs[k], ys[k]), 1.8, BONE, 0.8)
    p.flush()
    # 通行的路：从画面下缘穿过缝，到上方光里
    pp = clamp((t - dur * 0.50) / (dur * 0.38))
    if pp > 0:
        n = max(3, int(90 * pp))
        u = np.linspace(0, 1, n)
        px = 960 + 64 * np.sin(u * 3.0) + 46 * u
        py = 906 - 760 * u
        seg_pts = np.stack([px, py], 1)
        for seg in V.dashed(seg_pts, 16, 11):
            p.stroke(seg, ICE, 1.6, 0.55, 8, 0.4)
        p.dot((px[-1], py[-1]), 4.0, BONE, 0.85, 12, 0.7)
        p.flush()
    a = clamp((t - dur * 0.58) / 0.9)
    if a > 0:
        draw_mixed(p, [("松开一条缝 ", MUTED, F_SANS_R), ("·", GOLD, F_SANS_R),
                       (" 路才通", MUTED, F_SANS_R)], (252, 858), 28,
                   alpha=0.66 * a)
    p.bloom(threshold=0.60, strength=0.6)
    return p.to_image()


# ---------------------------------------------------------------- S6 桥 / 节奏
B_BASE, B_H = 838.0, 52.0
B_X0, B_X1 = 300.0, 720.0
B_GOAL = (1478.0, 700.0)


def _polyline_clip(pts, frac):
    pts = np.asarray(pts, np.float64)
    if frac <= 0:
        return pts[:1]
    if frac >= 1:
        return pts
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    total = seg.sum()
    target = total * frac
    acc = 0.0
    for k in range(len(seg)):
        if acc + seg[k] >= target:
            f = (target - acc) / max(1e-9, seg[k])
            head = pts[:k + 1]
            tip = pts[k] + f * (pts[k + 1] - pts[k])
            return np.vstack([head, tip])
        acc += seg[k]
    return pts


def _draw_building_small(p, n_present, alpha=1.0):
    for i in range(1, n_present + 1):
        y = B_BASE - (i - 1) * B_H
        draw_floor_slab(p, B_X0, B_X1, y, h=11.0, depth=24.0, alpha=0.8 * alpha,
                        top_color=(142, 166, 178))
        if i < n_present:
            y_up = B_BASE - i * B_H
            p.stroke([(B_X0, y), (B_X0, y_up)], (78, 96, 108), 1.2, 0.45 * alpha)
            p.stroke([(B_X1, y), (B_X1, y_up)], (78, 96, 108), 1.2, 0.45 * alpha)


def scene_bridges(t, dur, sh=None):
    """S6 s7：少加层、多加桥 —— 绕行 121.2 m vs 桥上 26.8 m。"""
    bg = studio_bg(t, dur, tint=(0.40, 0.62, 0.58), strength=0.08, glow_xy=(0.42, 0.5))
    p = V.Painter(bg)
    p.halo((1000, 620), 580, TEAL_D, 0.05)
    p.stroke([(240, B_BASE), (1700, B_BASE)], (86, 102, 114), 1.3, 0.55, 10, 0.3)
    _draw_building_small(p, 8)
    y_top = B_BASE - 7 * B_H
    # 目标
    gx, gy = B_GOAL
    p.stroke([(gx - 26, gy), (gx + 26, gy), (gx + 26, gy + 34), (gx - 26, gy + 34),
              (gx - 26, gy)], ICE, 1.4, 0.75, 8, 0.4)
    p.stroke([(gx - 18, gy + 12), (gx + 18, gy + 12)], (120, 140, 152), 1.0, 0.4)
    # 长路径：在每一层里绕一圈 → 121.2 m（7×3.6m 下行 + 8×12m 走廊）
    long_pts = [(430.0, y_top)]
    for i in range(8, 1, -1):
        y_i = B_BASE - (i - 1) * B_H
        y_dn = B_BASE - (i - 2) * B_H
        long_pts += [(640.0, y_i), (640.0, y_dn - B_H * 0.5), (380.0, y_dn - B_H * 0.5),
                     (380.0, y_dn)]
    long_pts += [(640.0, B_BASE), (B_GOAL[0] - 40, B_BASE)]
    long_p = _polyline_clip(long_pts, ease_in_out(clamp(t / max(0.8, dur * 0.26))))
    p.stroke(long_p, (206, 158, 100), 2.0, 0.78, 8, 0.35)
    if 0 < t < dur * 0.26:
        p.dot(tuple(long_p[-1]), 4.0, AMBER, 0.9, 10, 0.6)
    p.flush()
    # 桥：两段直连（先开 A，再开 B），然后短路径沿线跑过去
    A = (B_X1 + 26.0, y_top)
    Bm = (1200.0, B_BASE - 3 * B_H)
    C = (B_GOAL[0] - 30, B_GOAL[1])
    b1 = ease_in_out(clamp((t - dur * 0.27) / max(0.4, dur * 0.10)))
    b2 = ease_in_out(clamp((t - dur * 0.37) / max(0.4, dur * 0.10)))
    if b1 > 0:
        p.stroke([A, (A[0] + (Bm[0] - A[0]) * b1, A[1] + (Bm[1] - A[1]) * b1)],
                 GOLD, 2.6, 0.9, 14, 0.6)
    if b2 > 0:
        p.stroke([Bm, (Bm[0] + (C[0] - Bm[0]) * b2, Bm[1] + (C[1] - Bm[1]) * b2)],
                 GOLD, 2.6, 0.9, 14, 0.6)
    short_pts = np.array([A, Bm, C], np.float64)
    sp = ease_in_out(clamp((t - dur * 0.45) / max(0.6, dur * 0.16)))
    if sp > 0:
        p.stroke(_polyline_clip(short_pts, sp), TEAL, 2.4, 0.95, 14, 0.65)
        if sp < 1:
            p.dot(tuple(_polyline_clip(short_pts, sp)[-1]), 4.5, ICE, 0.95, 12, 0.7)
    p.flush()
    a = clamp((t - 0.25) / 0.8)
    if a > 0:
        V.draw_text(p.rgb, "少加层 · 多加桥", (252, 226), 44, BONE, F_SERIF, anchor="lm",
                    alpha=0.92 * a, track=3, glow=12, glow_strength=0.32)
        V.draw_text(p.rgb, "第二，不是砍掉层级，是让层级之间能走", (252, 276), 24,
                    MUTED, F_SANS_R, anchor="lm", alpha=0.62 * a, track=2)
        V.draw_text(p.rgb, "目标", (gx, gy - 26), 24, MUTED, F_SANS_R, anchor="mm",
                    alpha=0.6 * a, track=2)
    # 数据：绕行 vs 桥上（都来自明示的模型：3.6m/层，12m/走廊，8m/桥）
    a2 = clamp((t - dur * 0.30) / 0.8)
    if a2 > 0:
        draw_mixed(p, [("绕行 ", MUTED, F_SANS_R), ("121.2", AMBER, F_MONO), (" m", MUTED, F_SANS_R)],
                   (252, 858), 26, alpha=0.6 * a2)
    a3 = clamp((t - dur * 0.52) / 0.8)
    if a3 > 0:
        draw_mixed(p, [("桥上 ", MUTED, F_SANS_R), ("26.8", TEAL, F_MONO), (" m", MUTED, F_SANS_R)],
                   (252, 902), 30, alpha=0.85 * a3, glow=8)
        draw_mixed(p, [("× ", GOLD, F_MONO), ("4.5", GOLD, F_MONO), (" 更短", MUTED, F_SANS_R)],
                   (1668, 620), 38, anchor="rm", alpha=0.9 * a3, glow=10)
    p.bloom(threshold=0.62, strength=0.55)
    return p.to_image()


RHY_X0, RHY_X1, RHY_YB, RHY_YT = 340.0, 1620.0, 792.0, 300.0
RHY_CAP = 0.78


def _rhythm_load(s):
    """变革负荷：前半段过密（撞上限），后半段有节奏（留白）。"""
    v = 0.0
    if s < 0.46:
        for k in range(14):
            c = 0.015 + 0.0315 * k
            v += 0.42 * math.exp(-((s - c) / 0.0105) ** 2) + 0.30 * math.exp(-((s - c) / 0.030) ** 2)
    else:
        for k in range(4):
            c = 0.54 + 0.112 * k
            v += 0.34 * math.exp(-((s - c) / 0.026) ** 2) + 0.20 * math.exp(-((s - c) / 0.075) ** 2)
    return v


def _rhy_xy(s, v):
    x = RHY_X0 + (RHY_X1 - RHY_X0) * clamp(s)
    y = RHY_YB - (RHY_YB - RHY_YT) * clamp(v)
    return x, y


def scene_rhythm(t, dur, sh=None):
    """S6 s10：变革要有节奏 —— 过密会撞上限；留白才走得下去。"""
    bg = studio_bg(t, dur, tint=(0.42, 0.58, 0.50), strength=0.08, glow_xy=(0.48, 0.55))
    p = V.Painter(bg)
    p.halo((1000, 600), 560, TEAL_D, 0.045)
    p.stroke([(RHY_X0, RHY_YB), (RHY_X1, RHY_YB)], (88, 104, 116), 1.2, 0.55)
    p.stroke([(RHY_X0, RHY_YB + 6), (RHY_X0, RHY_YT - 6)], (88, 104, 116), 1.2, 0.45)
    # 上限
    ycap = RHY_YB - (RHY_YB - RHY_YT) * RHY_CAP
    for seg in V.dashed(np.array([[RHY_X0, ycap], [RHY_X1 + 10, ycap]]), 18, 12):
        p.stroke(seg, EMBER, 1.2, 0.55, 0, 0)
    p.flush()
    V.draw_text(p.rgb, "上限", (RHY_X1 + 22, ycap), 26, EMBER, F_SANS_R, anchor="lm",
                alpha=0.78, track=2)
    # 曲线生长（按真实负荷函数，超上限处被截平 —— 视觉上“撞上限”）
    pr = ease_in_out(clamp((t - 0.3) / max(0.8, dur * 0.62)))
    if pr > 0.002:
        ss = np.linspace(0.0, pr, 320)
        vv = np.array([_rhythm_load(s) for s in ss])
        vclip = np.minimum(vv, RHY_CAP)
        xs = np.array([_rhy_xy(s, v)[0] for s, v in zip(ss, vclip)])
        ys = np.array([_rhy_xy(s, v)[1] for s, v in zip(ss, vclip)])
        # 前半（过密）琥珀，后半（有节奏）青
        m = ss < 0.46
        p.stroke(np.stack([xs[m], ys[m]], 1), AMBER, 2.5, 0.9, 12, 0.6)
        p.stroke(np.stack([xs[~m], ys[~m]], 1), TEAL, 2.5, 0.95, 14, 0.65)
        if pr < 0.999:
            p.dot((xs[-1], ys[-1]), 4.5, GOLD, 0.95, 12, 0.7)
        # 每次变革：底部小刻度（过密 14 次 / 有节奏 4 次）
        for k in range(14):
            c = 0.015 + 0.0315 * k
            if pr >= c:
                xx = RHY_X0 + (RHY_X1 - RHY_X0) * c
                p.stroke([(xx, RHY_YB - 2), (xx, RHY_YB - 9)], AMBER, 1.2, 0.55)
        for k in range(4):
            c = 0.54 + 0.112 * k
            if pr >= c:
                xx = RHY_X0 + (RHY_X1 - RHY_X0) * c
                p.stroke([(xx, RHY_YB - 2), (xx, RHY_YB - 11)], TEAL, 1.4, 0.7)
        p.flush()
    a = clamp((t - 0.3) / 0.7)
    if a > 0:
        V.draw_text(p.rgb, "变革要有节奏", (252, 226), 46, BONE, F_SERIF, anchor="lm",
                    alpha=0.92 * a, track=3, glow=12, glow_strength=0.32)
        V.draw_text(p.rgb, "不是越多越好", (252, 276), 26, MUTED, F_SANS_R, anchor="lm",
                    alpha=0.66 * a, track=2)
    a1 = clamp((t - 1.2) / 0.8)
    if a1 > 0:
        V.draw_text(p.rgb, "过密 · 撞上限", (RHY_X0 + 46, 362), 26, AMBER, F_SANS_R,
                    anchor="lm", alpha=0.8 * a1, track=2)
    a2 = clamp((t - dur * 0.55) / 0.8)
    if a2 > 0:
        V.draw_text(p.rgb, "有节奏 · 留白", (1240, 346), 28, TEAL, F_SANS_R,
                    anchor="lm", alpha=0.85 * a2, track=2)
    p.bloom(threshold=0.62, strength=0.55)
    return p.to_image()


# ---------------------------------------------------------------- 片尾 / 黑场
def scene_end_card(t, dur, sh=None):
    """片尾卡：标题 + AI 声明（画面通道）+ 参考来源 + 系列落款。"""
    bg = warm_bg(t, dur)
    p = V.Painter(bg)
    # 背景：同一张网的余影（母题收束）
    pos = net_positions(20)
    xs = 960 + 900 * pos[:, 0]
    ys = 540 + 430 * pos[:, 1]
    a_bg = (0.055 + 0.012 * math.sin(t * 0.45)) * clamp((t - 0.1) / 1.2)
    for k in range(1, 20):
        for i in range(k):
            p.stroke([(xs[i], ys[i]), (xs[k], ys[k])], TEAL_D, 1.0, a_bg, 0, 0)
    p.flush()
    V.draw_text(p.rgb, "VIBE 知识共赏 · 第 05 期", (960, 238), 24, MUTED, F_SANS_R,
                anchor="mm", alpha=0.7 * clamp((t - 0.1) / 0.6), track=5)
    a = clamp((t - 0.18) / 0.75)
    if a > 0:
        rise = 14 * (1 - ease_out_cubic(clamp((t - 0.18) / 0.7)))
        V.draw_text(p.rgb, "为什么公司越大，越容易自己绊自己", (960, 320 - rise), 62,
                    BONE, F_SERIF, anchor="mm", alpha=0.97 * a, track=2,
                    glow=14, glow_strength=0.38)
    a = clamp((t - 0.62) / 0.65)
    if a > 0:
        V.draw_text(p.rgb, "一条逃不掉的数学，和三种不同的应对", (960, 386), 28, MUTED,
                    F_SANS_R, anchor="mm", alpha=0.82 * a, track=3)
    a = clamp((t - 0.95) / 0.5)
    if a > 0:
        p.stroke([(760, 426), (760 + 400 * a, 426)], GOLD, 1.2, 0.55, 8, 0.35)
        p.flush()
    # AI 声明（画面通道，必须可见；字号按 390px 宽可读性取 48/44px）
    a = clamp((t - 1.30) / 0.6)
    if a > 0:
        V.draw_text(p.rgb, "本片画面与配音含 AI 辅助制作", (960, 500), 48, BONE, F_SANS,
                    anchor="mm", alpha=0.97 * a, track=1, glow=10, glow_strength=0.3)
    a2 = clamp((t - 1.55) / 0.6)
    if a2 > 0:
        V.draw_text(p.rgb, "选题、核实与判断，由人完成", (960, 556), 44, AMBER, F_SANS_R,
                    anchor="mm", alpha=0.9 * a2, track=2)
    # 来源（细字，作为片尾资料行）
    a3 = clamp((t - 2.35) / 0.7)
    if a3 > 0:
        V.draw_text(p.rgb, "参考：Graicunas 管理幅度理论 · 周雪光《中国国家治理的制度逻辑》",
                    (960, 686), 27, MUTED, F_SANS_R, anchor="mm", alpha=0.82 * a3, track=1)
        V.draw_text(p.rgb, "Wilson / Downs 官僚组织理论 · Gartner / Gallup / Prosci（经媒体报道与综述转引）",
                    (960, 724), 27, MUTED, F_SANS_R, anchor="mm", alpha=0.74 * a3, track=1)
    a4 = clamp((t - 3.15) / 0.7)
    if a4 > 0:
        V.draw_text(p.rgb, "点赞 · 关注，下期见", (960, 812), 28, MUTED, F_SANS_R,
                    anchor="mm", alpha=0.6 * a4, track=4)
    # 长片尾（实测 11.5s）：最后 1.2s 缓缓收黑，接 outro 黑场
    if dur > 8.0:
        fade = 1.0 - smoothstep(dur - 1.2, dur - 0.05, t)
        p.rgb *= fade
    p.bloom(threshold=0.66, strength=0.4)
    return p.to_image()


def scene_outro_black(t, dur, sh=None):
    """片尾黑场：把最后一点光收掉。"""
    nx, ny = grid()
    glow = np.exp(-(((nx - 0.5) ** 2) / 0.10 + ((ny - 0.35) ** 2) / 0.18))
    fade = 1.0 - smoothstep(0.0, min(3.2, dur * 0.5), t)
    rgb = np.full((H, W, 3), 0.004, np.float32)
    rgb += glow[..., None] * np.array([0.05, 0.045, 0.035], np.float32) * fade
    p = V.Painter(rgb)
    # 细颗粒（统一后期还会加，这里只给一点底纹，避免纯数字黑）
    p.grain(seed=5, amt=0.004)
    return p.to_image()


SCENES = {
    "cold_title": scene_cold_title,
    "net_seed": scene_net_seed,
    "net_grow_n3": scene_net_grow_n3,
    "net_grow_n10": scene_net_grow_n10,
    "net_grow_n20": scene_net_grow_n20,
    "net_math": scene_net_math,
    "net_full": scene_net_full,
    "floors_rise": scene_floors_rise,
    "loop_complex": scene_loop_complex,
    "arrows_swarm": scene_arrows_swarm,
    "arrows_blank": scene_arrows_blank,
    "arrows_still": scene_arrows_still,
    "fatigue_curve": scene_fatigue_curve,
    "fatigue_data": scene_fatigue_data,
    "fatigue_pull": scene_fatigue_pull,
    "net_loosen": scene_net_loosen,
    "bridges": scene_bridges,
    "rhythm": scene_rhythm,
    "end_card": scene_end_card,
    "outro_black": scene_outro_black,
}
