#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 04 期数据层叠加器：压在实拍 B-roll 上的曲线 / 标注 / 花字。

约定：每个函数签名 `def ov_xxx(t, dur, o, sh)`，t 为镜头内局部时间（秒），
o 为 ep04viz.OverlayPainter，sh 为 shots.json 的镜头 dict。函数只画 RGBA 叠加层，
最终由 finalize 统一调色/颗粒/遮幅/字幕。
"""
import math

import numpy as np

import ep04viz as V
from ep04viz import (TEAL, AMBER, EMBER, BONE, MUTED, DIM, GOLD, ICE, WHITE,
                     F_SANS, F_SANS_R, F_SERIF, F_MONO, W, H, SAFE_T, SAFE_B,
                     clamp, ease_in_out, ease_out_cubic, smoothstep, window, lerp,
                     damped_osc, text_tex)

# 安全区（2.35:1 遮幅内）
L, R = 220, 1700
TOP, BOT = 190, 900


# ------------------------------------------------------------------ helpers
def hud_label(o, text, xy, size=30, color=MUTED, alpha=1.0, anchor="lm", track=1.5,
              uppercase=False):
    o.text(text, xy, size, color=color, font=F_SANS_R, anchor=anchor, alpha=alpha,
           track=track, stroke=1, stroke_color=(0, 0, 0))


def mono(o, text, xy, size=26, color=MUTED, alpha=1.0, anchor="lm", track=0.5):
    o.text(text, xy, size, color=color, font=F_MONO, anchor=anchor, alpha=alpha, track=track,
           stroke=1, stroke_color=(0, 0, 0))


def flicker(t, seed=0.0):
    return 1.0 - 0.06 * (math.sin(t * 37.0 + seed) * 0.5 + 0.5)


def plot_curve(o, xs, ys, color, width=2.0, alpha=1.0, glow=12, glow_a=0.7, dash=0):
    if len(xs) < 2:
        return
    pts = np.stack([xs, ys], axis=1)
    if dash:
        for seg in V.dashed(pts, dash, max(4, dash * 0.7)):
            o.stroke(seg, color, width, alpha * 0.85, glow * 0.4, glow_a * 0.5)
    else:
        o.stroke(pts, color, width, alpha, glow, glow_a)


def grow_curve(o, fn, x0, x1, t, t_start, t_end, color, width=2.2, glow=12, base=700,
               amp=90, y_scale=1.0, dash=0):
    """从左到右生长的曲线：fn(x) 返回 y 偏移（在 base 上），x∈[0,1]。"""
    p = clamp((t - t_start) / max(1e-3, (t_end - t_start)))
    if p <= 0:
        return 0.0
    pe = ease_out_cubic(p)
    n = max(2, int(220 * pe))
    xs = np.linspace(0, 1, n)
    px = x0 + (x1 - x0) * xs
    py = base + np.array([fn(x) for x in xs]) * amp * y_scale
    plot_curve(o, px, py, color, width, 0.95, glow, 0.7, dash)
    return pe


def bracket_h(o, x0, x1, y, color, alpha=0.9, width=1.6, tick=8):
    o.stroke([(x0, y), (x1, y)], color, width, alpha, 6, 0.5)
    o.stroke([(x0, y - tick), (x0, y + tick)], color, width, alpha)
    o.stroke([(x1, y - tick), (x1, y + tick)], color, width, alpha)


def cross(o, xy, size=18, color=EMBER, alpha=0.9, width=2.4, glow=8):
    x, y = xy
    o.stroke([(x - size, y - size), (x + size, y + size)], color, width, alpha, glow, 0.6)
    o.stroke([(x - size, y + size), (x + size, y - size)], color, width, alpha, glow, 0.6)


def 花字(o, text, xy, t, t0, t1, color=WHITE, size=104, font=F_SERIF, glow_color=None,
         appear=0.22):
    """大字花字：弹出 + 轻微上浮 + 淡出。"""
    if t < t0 or t > t1:
        return
    a = window(t, t0, t1, appear, appear * 1.6)
    p = clamp((t - t0) / appear)
    sc = 0.92 + 0.08 * ease_out_cubic(p)
    y = xy[1] - 8 * ease_out_cubic(clamp((t - t0) / 0.7))
    o.text(text, (xy[0], y), size, color=color, font=font, anchor="mm", alpha=a,
           track=2, glow=16, glow_strength=0.6)


# ------------------------------------------------------------------ S1
def ov_spec_sheet(t, dur, o, sh):
    """S1：参数表 HUD 行（不编造具体数值，只列维度 + 抽象量条）。"""
    x0, x1 = L + 40, L + 470
    rows = ["功率", "扭矩", "零百加速", "悬架形式", "轴距"]
    y0 = 360
    a0 = 0.9
    o.text("参 数 表", (x0, y0 - 66), 24, color=MUTED, font=F_SANS_R, anchor="lm",
           alpha=0.7 * a0, track=6)
    o.stroke([(x0, y0 - 40), (x0 + 250, y0 - 40)], MUTED, 1.0, 0.45)
    for i, row in enumerate(rows):
        t0 = 0.35 + i * 0.16
        a = clamp((t - t0) / 0.5)
        if a <= 0:
            continue
        y = y0 + i * 62
        hud_label(o, row, (x0, y), 30, MUTED, 0.85 * a, track=3)
        mono(o, "—", (x0 + 300, y), 26, DIM, 0.7 * a, anchor="mm")
        # 抽象量条
        wmax = 120
        w = wmax * (0.35 + 0.28 * math.sin(i * 2.1 + 0.8))
        o.bar((x0 + 330, y - 4), (x0 + 330 + w * a, y + 3), TEAL, 0.30 * a)
    # 收尾：整表被「同一张」框住
    if t > 3.2:
        a = window(t, 3.2, dur, 0.6, 0.6)
        o.rect((x0 - 26, y0 - 78), (x0 + 470, y0 + 5 * 62 - 12), MUTED, 0.35 * a, 1.0)


def ov_grip_hint(t, dur, o, sh):
    """S1：抓紧扶手——两道弧线在画面中部收紧。"""
    cx, cy = 960, 620
    a = window(t, 0.55, dur - 0.15, 0.5, 0.5)
    if a <= 0:
        return
    pinch = 1.0 - 0.18 * ease_in_out(clamp((t - 1.2) / 1.8))
    for sgn in (-1, 1):
        r = 260 * pinch
        th = np.linspace(-0.9, 0.9, 30)
        xs = cx + sgn * (r * np.cos(th) * 0.55 + 190)
        ys = cy + r * np.sin(th)
        o.stroke(np.stack([xs, ys], 1), AMBER, 1.8, 0.75 * a, 12, 0.6)
    if t > 1.7:
        aa = window(t, 1.7, dur, 0.45, 0.4)
        hud_label(o, "不自觉地 · 抓紧", (cx + 330, cy + 130), 30, AMBER, 0.8 * aa, track=3)


def ov_mystic(t, dur, o, sh):
    """S1：玄学——大字出现后被划掉（自我否定）。"""
    a = window(t, 0.5, dur, 0.45, 0.55)
    if a <= 0:
        return
    o.text("玄学？", (960, 560), 132, color=BONE, font=F_SERIF, anchor="mm",
           alpha=0.92 * a, track=6, glow=18, glow_strength=0.45)
    if t > 1.45:
        p = ease_out_cubic(clamp((t - 1.45) / 0.5))
        x0, x1 = 760, 760 + 400 * p
        o.stroke([(x0, 620), (x1, 500)], EMBER, 3.0, 0.9 * a, 14, 0.55)
    if t > 2.0:
        aa = window(t, 2.0, dur, 0.35, 0.4)
        hud_label(o, "后来才知道", (960, 720), 30, MUTED, 0.7 * aa, anchor="mm", track=4)


# ------------------------------------------------------------------ S2
def ov_impact_dong(t, dur, o, sh):
    """S2：好车「咚」——单次冲击、干净收住。用时由音效锚点决定。"""
    # 冲击环（与旁白/音效「咚」对齐：镜头内约 3.0s）
    t0 = 2.95
    if t >= t0:
        for k in range(3):
            p = clamp((t - t0 - k * 0.10) / 0.85)
            if p <= 0 or p >= 1:
                continue
            r = 60 + 560 * ease_out_cubic(p)
            a = (1 - p) ** 1.6 * 0.55
            th = np.linspace(0, 2 * math.pi, 90)
            o.stroke(np.stack([960 + r * np.cos(th), 640 + r * 0.42 * np.sin(th)], 1),
                     TEAL, 1.8, a, 10, 0.4)
    # 花字 咚（拟声，不算 §3.8 的 5 处花字）
    if 2.85 <= t <= 4.55:
        a = window(t, 2.85, 4.55, 0.18, 0.55)
        o.text("咚", (960, 430), 168, color=WHITE, font=F_SERIF, anchor="mm",
               alpha=0.95 * a, glow=26, glow_strength=0.6, track=4)
    # 已收住：一条快速衰减的曲线作为余振证据
    grow_curve(o, lambda x: -math.exp(-4.2 * x * 3) * math.sin(4 * math.pi * x * 1.5), 330, 1180,
               t, 3.5, 5.6, TEAL, 2.0, 10, base=830, amp=54)
    if t > 4.6:
        aa = clamp((t - 4.6) / 0.4) * clamp((dur - t) / 0.5)
        hud_label(o, "一次收住", (1195, 830), 30, TEAL, 0.85 * aa, track=3)


def ov_impact_wobble(t, dur, o, sh):
    """S2：差车「咣当」——余振不止，晃三晃。"""
    t0 = 0.8
    if t >= t0:
        for k in range(3):
            p = clamp((t - t0 - k * 0.24) / 1.35)
            if p <= 0 or p >= 1:
                continue
            r = 70 + 600 * ease_out_cubic(p)
            a = (1 - p) ** 1.1 * 0.5
            th = np.linspace(0, 2 * math.pi, 90)
            o.stroke(np.stack([960 + r * np.cos(th), 640 + r * 0.42 * np.sin(th)], 1),
                     AMBER, 1.9, a, 10, 0.45)
    if 0.75 <= t <= 2.55:
        a = window(t, 0.75, 2.55, 0.18, 0.7)
        o.text("咣当", (960, 410), 168, color=AMBER, font=F_SERIF, anchor="mm",
               alpha=0.95 * a, glow=26, glow_strength=0.6, track=4)
    # 余振曲线：衰减慢
    grow_curve(o, lambda x: math.exp(-1.1 * x * 3) * math.sin(2 * math.pi * x * 2.6),
               330, 1240, t, 1.6, 3.9, AMBER, 2.1, 12, base=838, amp=62)
    if t > 2.5:
        aa = window(t, 2.5, dur, 0.4, 0.4)
        hud_label(o, "还晃三晃", (1250, 838), 30, AMBER, 0.85 * aa, track=3)


def ov_soft_hard(t, dur, o, sh):
    """S2：关键不在软硬——两个词被划掉。"""
    a = window(t, 0.42, dur, 0.4, 0.45)
    if a <= 0:
        return
    o.text("软？", (560, 600), 116, color=BONE, font=F_SERIF, anchor="mm",
           alpha=0.9 * a, track=4, glow=14, glow_strength=0.4)
    o.text("硬？", (1360, 600), 116, color=BONE, font=F_SERIF, anchor="mm",
           alpha=0.9 * a, track=4, glow=14, glow_strength=0.4)
    if t > 1.35:
        p = ease_out_cubic(clamp((t - 1.35) / 0.55))
        for cx in (560, 1360):
            o.stroke([(cx - 120 * p, 660), (cx + 120 * p, 540)], EMBER, 3.0, 0.92 * a, 12, 0.5)
    if t > 1.95:
        aa = window(t, 1.95, dur, 0.35, 0.4)
        hud_label(o, "都不对", (960, 720), 32, MUTED, 0.8 * aa, anchor="mm", track=6)


def ov_damping_curves(t, dur, o, sh):
    """S2 核心：阻尼比——两条余振曲线长在水面倒影上（带倒影复制）。"""
    # 花字「阻尼比」
    花字(o, "阻尼比", (960, 300), t, 0.5, dur - 0.1, color=WHITE, size=100)
    # 冲击起点
    x0, x1 = 300, 1560
    if t > 1.2:
        p = clamp((t - 1.2) / 0.25)
        o.dot((x0, 720), 5 + 3 * (1 - p), TEAL, 0.8, 16, 0.7)
    # 欠阻尼（ζ 小，琥珀）：衰减慢
    pe1 = grow_curve(o, lambda x: math.exp(-0.85 * x * 4.2) * math.sin(2 * math.pi * x * 2.3),
                     x0, x1, t, 1.35, dur - 0.55, AMBER, 2.6, 16, base=678, amp=98)
    # 过阻尼（ζ 大，青）：快速收敛
    pe2 = grow_curve(o, lambda x: 1.15 * math.exp(-3.6 * x * 4.2) * math.sin(2 * math.pi * x * 1.55),
                     x0, x1, t, 2.0, dur - 0.55, TEAL, 2.6, 16, base=678, amp=98)
    # 倒影（依附水面）：下移+压缩+低透明度
    if pe1 > 0.3:
        grow_curve(o, lambda x: math.exp(-0.85 * x * 4.2) * math.sin(2 * math.pi * x * 2.3),
                   x0, x1, t, 1.35, dur - 0.55, AMBER, 1.8, 7, base=790, amp=36)
    if pe2 > 0.3:
        grow_curve(o, lambda x: 1.15 * math.exp(-3.6 * x * 4.2) * math.sin(2 * math.pi * x * 1.55),
                   x0, x1, t, 2.0, dur - 0.55, TEAL, 1.8, 7, base=790, amp=36)
    if t > dur - 1.4:
        a = window(t, dur - 1.4, dur, 0.35, 0.3)
        hud_label(o, "阻尼不足 · 余振", (x1 + 16, 678 - 96), 28, AMBER, 0.85 * a, track=2)
        hud_label(o, "阻尼够 · 收住", (x1 + 16, 678 + 78), 28, TEAL, 0.85 * a, track=2)


def ov_damped_trace(t, dur, o, sh):
    """S2：阻尼够——同一冲击，一步收住。"""
    grow_curve(o, lambda x: math.exp(-3.8 * x * 3.4) * math.sin(2 * math.pi * x * 2.0),
               280, 900, t, 0.3, dur - 0.7, TEAL, 2.2, 12, base=810, amp=58)
    if t > 1.5:
        a = window(t, 1.5, dur, 0.4, 0.4)
        hud_label(o, "一步收住", (930, 810), 28, TEAL, 0.8 * a, track=2)
    if t > 2.4:
        a = window(t, 2.4, dur, 0.35, 0.4)
        hud_label(o, "「咚」", (1150, 560), 52, BONE, 0.85 * a, track=3)


def ov_undamped_trace(t, dur, o, sh):
    """S2：阻尼不够——能量没吃完，一直晃。"""
    grow_curve(o, lambda x: math.exp(-0.55 * x * 3.2) * math.sin(2 * math.pi * x * 2.9),
               280, 980, t, 0.25, dur - 0.4, AMBER, 2.2, 12, base=812, amp=66)
    if t > 1.1:
        a = window(t, 1.1, dur, 0.4, 0.4)
        hud_label(o, "能量没吃完", (1010, 812), 28, AMBER, 0.8 * a, track=2)


def ov_body_sway(t, dur, o, sh):
    """S2：身体也跟着晃——水平仪/侧倾线随余振摇摆。"""
    cx, cy = 960, 640
    sway = 3.2 * math.exp(-0.55 * t) * math.cos(2 * math.pi * 1.55 * t)
    a = clamp((t - 0.15) / 0.6) * 0.8
    if a <= 0:
        return
    L2 = 430
    dx = math.sin(math.radians(sway)) * L2
    dy = math.cos(math.radians(sway)) * L2
    o.stroke([(cx - dx, cy - dy), (cx + dx, cy + dy)], AMBER, 1.7, 0.55 * a, 10, 0.45)
    o.stroke([(cx - 12, cy), (cx + 12, cy)], AMBER, 2.2, 0.9 * a)
    o.stroke([(cx, cy - 12), (cx, cy + 12)], AMBER, 2.2, 0.9 * a)
    if t > 1.1:
        aa = window(t, 1.1, dur, 0.4, 0.4)
        hud_label(o, "身体也跟着晃", (cx, cy + 200), 30, AMBER, 0.8 * aa, anchor="mm", track=3)


# ------------------------------------------------------------------ S3
def ov_channels3(t, dur, o, sh):
    """S3：车会通过几件事告诉你状态——三条线索先以光点出现、汇向一点。"""
    pts = [(470, 470), (960, 400), (1430, 500)]
    for i, (x, y) in enumerate(pts):
        t0 = 0.5 + i * 0.55
        a = clamp((t - t0) / 0.4)
        if a <= 0:
            continue
        o.dot((x, y), 7, TEAL, 0.95 * a, 20, 0.85)
        # 线索汇向画面右下方的「判断」点
        p = ease_out_cubic(clamp((t - t0 - 0.2) / 1.4))
        if p > 0.02:
            ex = lerp(x, 960, p)
            ey = lerp(y, 760, p)
            for seg in V.dashed(np.array([[x, y], [ex, ey]]), 16, 10):
                o.stroke(seg, TEAL, 1.1, 0.35 * a, 6, 0.3)


def ov_channels_line(t, dur, o, sh):
    """S3：三个渠道 → 一条信息线。"""
    labels = [("方向盘变重多少", (330, 330)), ("车身倾多少", (330, 470)),
              ("后轮什么时候开始滑", (330, 610))]
    for i, (txt, xy) in enumerate(labels):
        t0 = 0.25 + i * 0.75
        a = clamp((t - t0) / 0.45)
        if a <= 0:
            continue
        hud_label(o, txt, xy, 30, MUTED, 0.85 * a, track=2)
        o.stroke([(xy[0] + 300, xy[1]), (xy[0] + 430, xy[1])], TEAL, 1.2, 0.5 * a, 6, 0.35)
    # 三条线并成一条，开始生长
    t0 = 2.0
    p = clamp((t - t0) / (dur - t0 - 0.2))
    if p > 0:
        pe = ease_out_cubic(p)
        n = max(2, int(240 * pe))
        xs = np.linspace(0, 1, n)
        px = 760 + 800 * xs
        py = 700 - 26 * np.sin(xs * 2.2) - 40 * xs
        o.stroke(np.stack([px, py], 1), TEAL, 2.0, 0.9, 12, 0.7)
        if t > dur - 1.1:
            aa = window(t, dur - 1.1, dur, 0.3, 0.3)
            hud_label(o, "一条信息线", (1580, 600), 28, TEAL, 0.8 * aa, anchor="rm", track=2)


def _smooth_info(x):
    """信息线：平滑、可预期（x∈0..1）。"""
    return -46 * smoothstep(0.0, 0.6, x) - 10 * x


def ov_smooth_info(t, dur, o, sh):
    grow_curve(o, _smooth_info, 360, 1660, t, 0.2, dur - 0.85, TEAL, 2.2, 12, base=730, amp=1.0)
    # 极限线
    if t > 0.9:
        a = clamp((t - 0.9) / 0.5) * 0.6
        for seg in V.dashed(np.array([[360, 610], [1660, 610]]), 18, 12):
            o.stroke(seg, EMBER, 1.1, a, 5, 0.3)
        hud_label(o, "极限", (1680, 610), 26, EMBER, 0.65 * a, track=2)
    if t > 1.7:
        aa = window(t, 1.7, dur, 0.4, 0.4)
        hud_label(o, "平滑的线", (1000, 500), 30, TEAL, 0.8 * aa, track=3)


def ov_enough_marker(t, dur, o, sh):
    """S3：手上感觉「还够」——标记当前位置与极限的余量。"""
    grow_curve(o, _smooth_info, 360, 1660, t, 0.0, 1.6, TEAL, 2.2, 12, base=730, amp=1.0)
    # 极限线
    for seg in V.dashed(np.array([[360, 610], [1660, 610]]), 18, 12):
        o.stroke(seg, EMBER, 1.1, 0.55, 5, 0.3)
    # 当前点随「还够」推进
    p = clamp((t - 0.4) / (dur - 1.2))
    x = lerp(520, 1500, ease_in_out(p))
    xx = (x - 360) / 1300.0
    y = 730 + _smooth_info(xx)
    o.dot((x, y), 6, BONE, 0.95, 14, 0.7)
    if t > 0.9:
        a = window(t, 0.9, dur, 0.4, 0.35)
        bracket_h(o, x + 40, 1660, y - 4 if y - 4 < 610 else 610, ICE, 0.6 * a, 1.2, 6)
        hud_label(o, "还够", (x + 66, y - 52), 34, ICE, 0.85 * a, track=3)
        hud_label(o, "还差多少", (1540, 660), 26, MUTED, 0.7 * a, anchor="rm", track=2)


def ov_broken_info(t, dur, o, sh):
    """S3：这条线是断的。"""
    # 前半段平滑，后半段断裂消失
    p = clamp((t - 0.1) / 1.1)
    if p > 0:
        pe = ease_out_cubic(p)
        n = max(2, int(150 * pe))
        xs = np.linspace(0.0, 0.55, n)
        px = 360 + (1660 - 360) * xs
        py = 730 + np.array([_smooth_info(x) for x in xs])
        o.stroke(np.stack([px, py], 1), TEAL, 2.2, 0.9, 12, 0.7)
    if t > 1.05:
        p = clamp((t - 1.05) / 0.5)
        # 断口
        x = 360 + (1660 - 360) * 0.55
        y = 730 + _smooth_info(0.55)
        a = 0.9 * (1 - p * 0.3)
        cross(o, (x + 20, y), 22, EMBER, a, 2.4, 10)
        if p >= 1:
            aa = window(t, 1.55, dur, 0.3, 0.3)
            hud_label(o, "断", (x + 70, y - 60), 40, EMBER, 0.9 * aa, track=2)


def ov_line_drop(t, dur, o, sh):
    """S3：前面很轻松，突然就到了极限。"""
    # 平滑段
    if t > 0.05:
        p = clamp((t - 0.05) / 1.2)
        n = max(2, int(170 * ease_out_cubic(p)))
        xs = np.linspace(0, 0.62, n)
        px = 360 + (1660 - 360) * xs
        py = 680 + np.array([_smooth_info(x) for x in xs]) * 0.9
        o.stroke(np.stack([px, py], 1), TEAL, 2.2, 0.9, 12, 0.7)
    # 断崖
    if t > 1.25:
        p = ease_out_cubic(clamp((t - 1.25) / 0.45))
        x0 = 360 + (1660 - 360) * 0.62
        y0 = 680 + _smooth_info(0.62) * 0.9
        x1 = x0 + 160
        y1 = y0 + 230 * p
        o.stroke([(x0, y0), (x1, y1)], EMBER, 2.6, 0.95, 14, 0.7)
        o.dot((x1, y1), 6, EMBER, 0.9, 16, 0.8)
        if p > 0.7:
            aa = window(t, 1.6, dur, 0.3, 0.3)
            hud_label(o, "突然就到极限", (x1 + 30, y1 - 40), 28, EMBER, 0.8 * aa, track=2)


def ov_lead_time(t, dur, o, sh):
    """S3：信息传递的提前量 = 还差多少。"""
    # 平滑线 + 极限线，展示「提前量」区间
    grow_curve(o, _smooth_info, 360, 1620, t, 0.05, 1.5, TEAL, 2.2, 12, base=740, amp=1.0)
    for seg in V.dashed(np.array([[360, 600], [1620, 600]]), 18, 12):
        o.stroke(seg, EMBER, 1.1, 0.55, 5, 0.3)
    hud_label(o, "极限", (1640, 600), 26, EMBER, 0.6, track=2)
    if t > 1.0:
        a = clamp((t - 1.0) / 0.6)
        yy = 740 + _smooth_info(0.72)
        x = 360 + (1620 - 360) * 0.72
        bracket_h(o, x, x, yy, ICE, 0)  # no-op keep
        # 竖直余量标注
        o.stroke([(x + 60, yy), (x + 60, 600)], ICE, 1.4, 0.75 * a, 8, 0.5)
        o.stroke([(x + 52, yy), (x + 68, yy)], ICE, 1.4, 0.75 * a)
        o.stroke([(x + 52, 600), (x + 68, 600)], ICE, 1.4, 0.75 * a)
        o.dot((x + 60, yy), 4, ICE, 0.9 * a, 12, 0.7)
        hud_label(o, "还差多少", (x + 86, (yy + 600) / 2), 30, ICE, 0.85 * a, track=3)
    if t > 2.4:
        aa = window(t, 2.4, dur, 0.4, 0.35)
        hud_label(o, "提前量", (1620, 470), 34, TEAL, 0.85 * aa, anchor="rm", track=4)


def ov_ahead_line(t, dur, o, sh):
    """S3：提前量——在真实前路上画出一条「预判线」（透视贝塞尔）。"""
    if t < 0.15:
        return
    p = clamp((t - 0.15) / (dur * 0.55))
    pe = ease_in_out(p)
    n = max(3, int(120 * pe))
    s = np.linspace(0, 1, n)
    # 透视：远处收窄
    x = 960 + 250 * np.sin(s * 2.4) * (1 - 0.55 * s) + 90 * s ** 2
    y = 900 - 380 * s ** 0.8
    pts = np.stack([x - 0, y], 1)
    # 道路中线偏右
    o.stroke(pts, TEAL, 3.0, 1.0, 18, 0.85)
    if t > 1.6:
        a = window(t, 1.6, dur, 0.35, 0.35)
        mid = n // 2
        hud_label(o, "预判", (pts[mid][0] + 40, pts[mid][1] - 30), 30, TEAL, 0.85 * a, track=3)


# ------------------------------------------------------------------ S4
def ov_torque_ramp(t, dur, o, sh):
    """S4：燃油车——扭矩慢慢爬升。"""
    grow_curve(o, lambda x: 70 * (1 - np.exp(-4 * x)) * 0.9, 300, 1300, t, 0.25, dur - 0.7,
               AMBER, 2.2, 12, base=800, amp=1.0)
    if t > 1.2:
        a = window(t, 1.2, dur, 0.4, 0.4)
        hud_label(o, "扭矩 · 慢慢爬升", (1330, 740), 28, AMBER, 0.85 * a, track=2)


def ov_torque_step(t, dur, o, sh):
    """S4：电车——零转速满扭矩，阶跃。"""
    t_step = 1.0
    a = clamp((t - 0.15) / 0.8)
    if a <= 0:
        return
    # 阶跃曲线
    xs = np.linspace(0, 1, 160)
    ys = np.where(xs < 0.45, 8, 78)
    n = int(len(xs) * clamp((t - 0.15) / 1.4))
    if n >= 2:
        px = 300 + 1000 * xs[:n]
        py = 800 - ys[:n]
        o.stroke(np.stack([px, py], 1), TEAL, 2.4, 0.95 * a, 14, 0.75)
    # 阶跃竖线
    if t > t_step:
        x = 300 + 1000 * 0.45
        o.stroke([(x, 800), (x, 800 - 78)], TEAL, 1.2, 0.5 * a, 6, 0.3)
        o.dot((x, 800 - 78), 5, TEAL, 0.9 * a, 14, 0.7)
    if t > 1.8:
        aa = window(t, 1.8, dur, 0.4, 0.4)
        hud_label(o, "零转速 · 满扭矩", (1350, 690), 28, TEAL, 0.85 * aa, track=2)


def ov_jerk_spike(t, dur, o, sh):
    """S4：加速度突然出现——jerk 尖峰（雨滴被甩出是真实载体）。"""
    # 加速度阶跃 + jerk 尖峰（对齐旁白/音效：镜头内约 2.8s）
    t0 = 2.55
    if t < 1.8:
        return
    # 轴：左下角小图
    x0, x1 = 300, 1180
    o.stroke([(x0, 800), (x1, 800)], MUTED, 1.0, 0.35)
    o.stroke([(x0, 800), (x0, 520)], MUTED, 1.0, 0.35)
    # 加速度阶跃
    if t > t0:
        p = clamp((t - t0) / 0.12)
        xm = x0 + (x1 - x0) * 0.45
        o.stroke([(x0, 720), (xm, 720)], TEAL, 2.2, 0.8, 10, 0.6)
        o.stroke([(xm, 720), (xm, 600)], TEAL, 2.2, 0.8, 10, 0.6)
        o.stroke([(xm, 600), (x1, 600)], TEAL, 2.2, 0.8 * p, 10, 0.6)
    # jerk 尖峰
    if t > t0 + 0.1:
        p = clamp((t - t0 - 0.1) / 0.35)
        xm = x0 + (x1 - x0) * 0.45
        h = 150 * p
        o.stroke([(xm - 120, 800), (xm - 6, 800 - h), (xm + 6, 800), (xm + 120, 800)],
                 EMBER, 2.4, 0.95, 16, 0.8)
        if p >= 1:
            aa = window(t, 3.1, dur, 0.3, 0.3)
            o.text("jerk", (xm + 150, 800 - h - 10), 46, color=EMBER, font=F_SERIF,
                   anchor="lm", alpha=0.9 * aa, track=2, glow=12, glow_strength=0.5)
            hud_label(o, "加速度的变化率", (xm + 150, 800 - h + 46), 24, MUTED, 0.7 * aa, track=2)


def ov_push_nausea(t, dur, o, sh):
    """S4：推背感 / 晕车感——同一个 jerk 的两面。"""
    cx, cy = 960, 620
    a = clamp((t - 0.2) / 0.7)
    if a <= 0:
        return
    # 同一个波形：正向尖峰（推背）与负向尖峰（晕车）
    xs = np.linspace(0, 1, 140)
    n = int(len(xs) * clamp((t - 0.2) / (dur - 1.2)))
    if n >= 3:
        base = 620
        ys = (np.exp(-((xs - 0.28) ** 2) / 0.006) * 110
              - np.exp(-((xs - 0.72) ** 2) / 0.006) * 110)
        px = 420 + 1080 * xs[:n]
        py = base - ys[:n]
        o.stroke(np.stack([px, py], 1), GOLD, 2.3, 0.9 * a, 14, 0.7)
        # 中线
        for seg in V.dashed(np.array([[420, base], [1500, base]]), 16, 12):
            o.stroke(seg, MUTED, 1.0, 0.3 * a)
        if n > 40:
            hud_label(o, "推背感", (620, 480), 30, AMBER, 0.85 * a, track=3)
            hud_label(o, "晕车感", (1300, 760), 30, EMBER, 0.85 * a, track=3)
    if t > 1.9:
        aa = window(t, 1.9, dur, 0.4, 0.35)
        o.text("同一个 jerk", (960, 860), 34, color=BONE, font=F_SERIF, anchor="mm",
               alpha=0.8 * aa, track=3)


# ------------------------------------------------------------------ S5
def ov_residual_curves(t, dur, o, sh):
    """S5：回望三条曲线——它们淡出（记住的不是赫兹和阻尼比）。"""
    a = window(t, 0.3, dur - 0.2, 0.7, 0.9)
    if a <= 0:
        return
    for k, (col, fn) in enumerate([
            (TEAL, lambda x: 26 * math.exp(-1.6 * x) * math.sin(3.4 * x * math.pi)),
            (AMBER, lambda x: 18 * math.exp(-1.2 * x) * math.sin(2.4 * x * math.pi + 0.7)),
            (EMBER, lambda x: 12 * math.exp(-1.8 * x) * math.sin(4.2 * x * math.pi + 1.3))]):
        xs = np.linspace(0, 1, 120)
        px = 300 + 1320 * xs
        py = 760 + np.array([fn(x) for x in xs])
        o.stroke(np.stack([px, py], 1), col, 1.6, 0.5 * a, 10, 0.5)


def ov_spec_can(t, dur, o, sh):
    """S5：参数表能告诉你「能做什么」。"""
    x0, y0 = 250, 340
    rows = ["功率", "扭矩", "零百加速", "续航", "悬架"]
    a0 = window(t, 0.2, dur, 0.5, 0.5)
    if a0 <= 0:
        return
    o.text("能做什么", (x0, y0 - 70), 40, color=TEAL, font=F_SERIF, anchor="lm",
           alpha=0.9 * a0, track=2, glow=10, glow_strength=0.4)
    for i, row in enumerate(rows):
        t0 = 0.4 + i * 0.22
        a = clamp((t - t0) / 0.4)
        if a <= 0:
            continue
        y = y0 + i * 58
        hud_label(o, row, (x0, y), 28, MUTED, 0.8 * a, track=2)
        o.stroke([(x0 + 120, y), (x0 + 320, y)], DIM, 1.0, 0.5 * a)
        o.dot((x0 + 340, y), 3, TEAL, 0.9 * a, 8, 0.5)


def ov_spec_cannot(t, dur, o, sh):
    """S5：但它告诉不了你「坐在里面是什么感觉」。"""
    x0, y0 = 1150, 330
    rows = ["功率", "扭矩", "零百加速", "续航", "悬架"]
    a0 = clamp((t - 0.1) / 0.4)
    for i, row in enumerate(rows):
        y = y0 + i * 58
        a = clamp((t - 0.1 - i * 0.10) / 0.35) * 0.5
        if a <= 0:
            continue
        hud_label(o, row, (x0, y), 28, DIM, a * 0.8, track=2)
        o.stroke([(x0 + 120, y), (x0 + 320, y)], DIM, 1.0, 0.3 * a)
    # 划掉整表
    if t > 1.2:
        p = ease_out_cubic(clamp((t - 1.2) / 0.5))
        o.stroke([(x0 - 30, y0 + 280), (x0 - 30 + 420 * p, y0 + 40)], EMBER, 2.2, 0.75, 10, 0.5)
    if t > 1.7:
        aa = window(t, 1.7, dur, 0.4, 0.3)
        o.text("坐进去 是什么感觉", (960, 640), 56, color=BONE, font=F_SERIF, anchor="mm",
               alpha=0.92 * aa, track=3, glow=14, glow_strength=0.45)


def ov_ai_specs(t, dur, o, sh):
    """S5：AI 能写出所有参数，却写不出体感。"""
    x0, y0 = 1130, 300
    rows = ["功率", "扭矩", "续航", "零百", "风阻", "轴距"]
    a0 = clamp((t - 0.1) / 0.3)
    if a0 <= 0:
        return
    for i, row in enumerate(rows):
        t0 = 0.15 + i * 0.20
        a = clamp((t - t0) / 0.25)
        if a <= 0:
            continue
        y = y0 + i * 52
        hud_label(o, row, (x0, y), 26, MUTED, 0.8 * a, track=2)
        o.stroke([(x0 + 110, y), (x0 + 300, y)], TEAL, 1.2, 0.55 * a)
    # 最后一格：体感 → 写不出来
    if t > 1.75:
        y = y0 + len(rows) * 52 + 12
        a = clamp((t - 1.75) / 0.3)
        hud_label(o, "体感", (x0, y), 30, AMBER, 0.95 * a, track=3)
        # 光标闪烁后变成省略号
        blink = (math.sin(t * 9) > 0) if t < dur - 0.5 else False
        if t < 1.75 + 0.9:
            if blink:
                o.stroke([(x0 + 100, y - 16), (x0 + 100, y + 16)], AMBER, 2.0, 0.8 * a, 8, 0.5)
        else:
            aa = clamp((t - 2.7) / 0.3)
            o.text("……", (x0 + 96, y), 30, color=DIM, font=F_SERIF, anchor="lm", alpha=0.8 * aa)


def ov_ecg_body(t, dur, o, sh):
    """S5：身体是松的，还是紧的——心跳线从手部生长出来。"""
    t0 = 0.4
    p = clamp((t - t0) / (dur - 1.0))
    if p <= 0:
        return
    pe = ease_in_out(p)
    n = max(3, int(240 * pe))
    xs = np.linspace(0, 1, n)
    prev = None
    ys = []
    for x in xs:
        # 合成心跳：P-QRS-T
        beat = 0.0
        for c, w, amp in ((0.16, 0.02, 0.15), (0.22, 0.008, -0.18), (0.235, 0.006, 1.0),
                          (0.25, 0.009, -0.28), (0.36, 0.03, 0.22)):
            u = x - c
            beat += amp * math.exp(-(u * u) / (2 * w * w))
        ys.append(beat)
    ys = np.array(ys)
    y = np.array(ys) * 90
    px = 360 + 1240 * xs
    py = 640 - y
    o.stroke(np.stack([px, py], 1), GOLD, 2.4, 0.95, 16, 0.8)
    # 当前点光晕
    cx, cy = px[-1], py[-1]
    o.glow((cx, cy), 70, GOLD, 0.30)
    if t > 1.4:
        a = window(t, 1.4, dur, 0.4, 0.35)
        hud_label(o, "身体是松的，还是紧的", (960, 780), 34, BONE, 0.85 * a, anchor="mm", track=3)


def ov_question(t, dur, o, sh):
    """S5：把问题交给观众。"""
    a = window(t, 0.35, dur - 0.1, 0.6, 0.5)
    if a <= 0:
        return
    o.text("你坐过最让你放心的车", (960, 520), 62, color=BONE, font=F_SERIF, anchor="mm",
           alpha=0.92 * a, track=3, glow=12, glow_strength=0.4)
    o.text("是哪一辆？", (960, 620), 62, color=BONE, font=F_SERIF, anchor="mm",
           alpha=0.92 * a, track=3, glow=12, glow_strength=0.4)


def ov_comment(t, dur, o, sh):
    a = window(t, 0.1, dur, 0.3, 0.2)
    if a <= 0:
        return
    o.text("评论区聊聊", (960, 560), 52, color=BONE, font=F_SERIF, anchor="mm",
           alpha=0.9 * a, track=4)


OVERLAYS = {
    "spec_sheet": ov_spec_sheet,
    "grip_hint": ov_grip_hint,
    "mystic": ov_mystic,
    "impact_dong": ov_impact_dong,
    "impact_wobble": ov_impact_wobble,
    "soft_hard": ov_soft_hard,
    "damping_curves": ov_damping_curves,
    "damped_trace": ov_damped_trace,
    "undamped_trace": ov_undamped_trace,
    "body_sway": ov_body_sway,
    "channels3": ov_channels3,
    "channels_line": ov_channels_line,
    "smooth_info": ov_smooth_info,
    "enough_marker": ov_enough_marker,
    "broken_info": ov_broken_info,
    "line_drop": ov_line_drop,
    "lead_time": ov_lead_time,
    "ahead_line": ov_ahead_line,
    "torque_ramp": ov_torque_ramp,
    "torque_step": ov_torque_step,
    "jerk_spike": ov_jerk_spike,
    "push_nausea": ov_push_nausea,
    "residual_curves": ov_residual_curves,
    "spec_can": ov_spec_can,
    "spec_cannot": ov_spec_cannot,
    "ai_specs": ov_ai_specs,
    "ecg_body": ov_ecg_body,
    "question": ov_question,
    "comment": ov_comment,
}
