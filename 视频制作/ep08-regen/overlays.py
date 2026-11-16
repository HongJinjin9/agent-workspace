#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 08 期叠加层：压在 H3 实拍底上的代码标注（混合镜头专用，19 个 H3 镜 + 备用）。

签名：`def ov_xxx(t, dur, o, sh)`；o 为 ep08viz.OverlayPainter（1920×1080 RGBA）。
规则（PDF §三 形态 C）：文字/数字全部来自 facts 与锁定稿；标注轨迹由代码定义；
不进入底部字幕安全区（y>900 不放内容）；H3 只负责质感，信息由本层承担。
"""
import math

import numpy as np

import ep08viz as v

W, H = v.W, v.H
SAFE_BOTTOM = 900.0


def T(o, s, xy, size=30, color=v.BONE, font=v.F_SANS, alpha=1.0, anchor="mm",
      track=1.0, glow=0.0):
    if isinstance(font, (int, float)):      # 防御：误把 alpha 传到 font 位置
        alpha, font = float(font), v.F_SANS
    o.text(s, xy, size, color, font, anchor, alpha, track=track, glow=glow)


def M(o, s, xy, size=24, color=v.MUTED, alpha=1.0, anchor="mm", track=0.6, glow=0.0):
    o.text(s, xy, size, color, v.F_MONO, anchor, alpha, track=track, glow=glow)


def chip(o, xy, s, color=v.TEAL, alpha=1.0, size=22, fill=0.10):
    im = v.text_tex(s, size, color, v.F_SANS_R, 0, (0, 0, 0), 0.6)
    w, h = im.width + 34, im.height + 20
    x, y = xy
    o.bar((x - w / 2, y - h / 2), (x + w / 2, y + h / 2), color, alpha * fill)
    o.stroke([(x - w / 2, y - h / 2), (x + w / 2, y - h / 2), (x + w / 2, y + h / 2),
              (x - w / 2, y + h / 2)], color, 1.4, alpha * 0.8, closed=True)
    T(o, s, (x, y), size, color, v.F_SANS_R, alpha, track=0.6)


def rule(o, x0, x1, y, color=v.MUTED, alpha=0.6, w=1.6):
    o.stroke([(x0, y), (x1, y)], color, w, alpha)


def arrow(o, p0, p1, color=v.TEAL, alpha=1.0, w=2.6, head=16, glow=8):
    o.stroke([p0, p1], color, w, alpha, glow, 0.5)
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = max(1e-3, math.hypot(dx, dy))
    ux, uy = dx / L, dy / L
    o.stroke([(p1[0] - head * ux - head * 0.5 * uy, p1[1] - head * uy + head * 0.5 * ux),
              p1,
              (p1[0] - head * ux + head * 0.5 * uy, p1[1] - head * uy - head * 0.5 * ux)],
             color, w, alpha, glow, 0.4)


def ring(o, cx, cy, R, frac, color=v.TEAL, width=10, alpha=1.0):
    o.stroke([v.polar(cx, cy, R, d) for d in range(0, 361, 3)], v.LINE, width, alpha * 0.6,
             closed=True)
    if frac > 0.002:
        pts = [v.polar(cx, cy, R, d) for d in np.arange(-90, -90 + 360 * frac, 1.5)]
        o.stroke(np.array(pts, np.float32), color, width, alpha, glow=14, glow_a=0.5)


def bezier_pts(p0, p1, p2, p3, n=80):
    ts = np.linspace(0, 1, n)[:, None]
    pts = ((1 - ts) ** 3) * np.array(p0) + 3 * ((1 - ts) ** 2) * ts * np.array(p1) \
        + 3 * (1 - ts) * ts ** 2 * np.array(p2) + ts ** 3 * np.array(p3)
    return pts.astype(np.float32)


# ---------------------------------------------------------------- S02
def ov_soc_climb(t, dur, o, sh):
    """S02：电量在往上走（示意，不出现具体百分比/无来源数字）。"""
    a = v.window(t, 0.15, dur - 0.1, 0.25, 0.25)
    x, y = 1430.0, 420.0
    T(o, "电量", (x, y - 110), 26, v.MUTED, v.F_SANS_R, a * 0.9, track=3)
    T(o, "↑", (x, y), 120, v.TEAL, a, track=0, glow=18 * a)
    T(o, "回收中 · 示意", (x, y + 96), 24, v.TEAL, v.F_SANS_R, a * 0.95, track=2)
    T(o, "电量在往上走", (x, y + 150), 26, v.BONE, v.F_SANS_R, a * 0.95, track=2)


# ---------------------------------------------------------------- S05
def ov_conservation_text(t, dur, o, sh):
    a = v.window(t, 0.2, dur - 0.05, 0.35, 0.3)
    T(o, "能量守恒", (960, 420), 96, v.BONE, v.F_SANS, a, track=8, glow=14 * a)
    rule(o, 700, 1220, 512, v.TEAL, a * 0.8, 2.0)
    T(o, "能量不会凭空出现，也不会凭空消失", (960, 570), 28, v.MUTED, v.F_SANS_R, a * 0.9,
      track=2)


# ---------------------------------------------------------------- S07
def ov_wheel_push_arrow(t, dur, o, sh):
    a = v.window(t, 0.2, dur - 0.05, 0.3, 0.3)
    # 从轮端向电机方向的回推箭头
    for k in range(3):
        y = 590 + k * 60
        arrow(o, (1320, y), (820, y - 20), v.TEAL, a * (0.9 - k * 0.2), 3.0, 18, 10)
    T(o, "轮子推着电机转", (960, 760), 34, v.TEAL, v.F_SANS, a, track=4, glow=10 * a)
    chip(o, (1560, 360), "轮端 → 电机", v.TEAL, a, 22)


# ---------------------------------------------------------------- S10
def ov_heat_vs_charge(t, dur, o, sh):
    a = v.window(t, 0.2, dur - 0.05, 0.3, 0.3)
    # 左右分界
    o.stroke([(960, 240), (960, 860)], v.MUTED, 1.2, a * 0.35)
    # 左：热
    T(o, "变成热", (620, 340), 34, v.AMBER, v.F_SANS, a, track=3)
    for k in range(7):
        x = 420 + k * 56
        o.stroke([(x, 640), (x + 10, 560 - k * 8)], v.AMBER, 2.0, a * 0.5, 10, 0.4)
    # 右：电
    T(o, "变成电", (1300, 340), 34, v.TEAL, v.F_SANS, a, track=3)
    arrow(o, (1180, 640), (1180, 520), v.TEAL, a * 0.9, 3.0, 18, 10)
    M(o, "→ 电池", (1290, 560), 26, v.TEAL, a * 0.9)
    T(o, "本来要变成刹车热的那部分", (960, 850), 28, v.MUTED, v.F_SANS_R, a * 0.9, track=2)


# ---------------------------------------------------------------- S20
def ov_bms_gate(t, dur, o, sh):
    a = v.window(t, 0.2, dur - 0.05, 0.3, 0.3)
    x0, y0 = 1230.0, 560.0
    o.bar((x0, y0), (x0 + 430, y0 + 230), (10, 14, 18), a * 0.55)
    o.stroke([(x0, y0), (x0 + 430, y0), (x0 + 430, y0 + 230), (x0, y0 + 230)], v.TEAL,
             1.6, a * 0.8, closed=True)
    T(o, "BMS 门禁", (x0 + 20, y0 + 26), 24, v.TEAL, v.F_SANS_R, a, anchor="lm", track=2)
    for k, (lab, frac) in enumerate((("电量", 0.92), ("温度", 0.55), ("倍率", 0.4))):
        y = y0 + 70 + k * 46
        T(o, lab, (x0 + 20, y), 20, v.MUTED, v.F_SANS_R, a * 0.85, anchor="lm")
        o.bar((x0 + 90, y - 7), (x0 + 90 + 260 * frac, y + 7), v.TEAL, a * 0.5)
    T(o, "电池说了算", (x0 + 215, y0 + 210), 24, v.BONE, v.F_SANS, a, track=2)


# ---------------------------------------------------------------- S25
def ov_pedal_power(t, dur, o, sh):
    a = v.window(t, 0.15, dur - 0.05, 0.2, 0.2)
    cx, cy, R = 1470.0, 420.0, 150.0
    o.stroke([v.polar(cx, cy, R, d) for d in np.arange(150, 391, 2)], v.LINE, 8.0, a * 0.6)
    jump = v.smoothstep(0.25, dur * 0.7, t)
    ang = 150 + 240 * (0.30 + 0.62 * jump)
    o.stroke([v.polar(cx, cy, R - 24, ang), v.polar(cx, cy, 10, ang)], v.TEAL, 3.4, a, 14, 0.5)
    o.dot((cx, cy), 6, v.TEAL, a, glow=14)
    M(o, "回收功率", (cx, cy + 90), 22, v.MUTED, a * 0.85)
    T(o, "回收功率", (960, 330), 40, v.BONE, v.F_SANS, a, track=4, glow=8 * a)


# ---------------------------------------------------------------- S30
def ov_heat_text(t, dur, o, sh):
    a = v.window(t, 0.2, dur - 0.05, 0.3, 0.3)
    T(o, "否则全变成热", (960, 380), 54, v.AMBER, v.F_SANS, a, track=5, glow=16 * a)
    for k in range(9):
        x = 620 + k * 84
        o.stroke([(x, 700 - (k % 3) * 20), (x + 14, 620 - (k % 3) * 20)], v.AMBER, 2.0,
                 a * 0.4, 10, 0.4)
    M(o, "刹车盘上的热，收不回来", (960, 760), 26, v.MUTED, a * 0.85)


# ---------------------------------------------------------------- S35
def ov_real78(t, dur, o, sh):
    a = v.window(t, 0.2, dur - 0.05, 0.3, 0.25)
    M(o, "实车试验", (960, 380), 30, v.MUTED, a * 0.9, track=4)
    T(o, "78%", (960, 500), 150, v.TEAL, v.F_SANS, a, track=4, glow=20 * a)
    o.bar((660, 600), (1260, 616), v.LINE, a * 0.6)
    o.bar((660, 600), (660 + 600 * 0.78, 616), v.TEAL, a * 0.9)
    T(o, "单次制动回收率（Valladolid 等，2023，F05）", (960, 680), 24, v.MUTED,
      v.F_SANS_R, a * 0.85, track=1.5)


# ---------------------------------------------------------------- S39
def ov_city_curve(t, dur, o, sh):
    a = v.window(t, 0.2, dur - 0.05, 0.3, 0.3)
    x0, x1, y0, y1 = 380.0, 1540.0, 800.0, 600.0
    o.stroke([(x0, y0), (x1, y0)], v.LINE, 1.4, a * 0.8)
    o.stroke([(x0, y0), (x0, y1)], v.LINE, 1.4, a * 0.8)
    xs = np.linspace(0, 1, 120)
    # 密集的回收脉冲（走走停停）
    yy = 0.25 + 0.55 * (np.sin(xs * 26) * 0.5 + 0.5) * (0.6 + 0.4 * np.sin(xs * 3))
    pts = np.stack([x0 + xs * (x1 - x0), y0 - yy * (y0 - y1)], 1)
    n = max(2, int(len(pts) * v.smoothstep(0.2, dur * 0.8, t)))
    o.stroke(pts[:n], v.TEAL, 2.4, a * 0.9, 12, 0.5)
    T(o, "城市走走停停", (960, 380), 40, v.BONE, v.F_SANS, a, track=4)


# ---------------------------------------------------------------- S40
def ov_mgh_annotation(t, dur, o, sh):
    a = v.window(t, 0.2, dur - 0.05, 0.3, 0.3)
    T(o, "E = mgh", (1420, 380), 52, v.TEAL, v.F_MONO, a, track=2, glow=10 * a)
    M(o, "1 km · 落差 50 m", (1420, 460), 28, v.MUTED, a * 0.9)
    arrow(o, (1420, 700), (1420, 560), v.TEAL, a * 0.85)
    T(o, "长下坡：势能", (1420, 760), 30, v.BONE, v.F_SANS, a * 0.95, track=3)


# ---------------------------------------------------------------- S44
def ov_cold_limit(t, dur, o, sh):
    a = v.window(t, 0.2, dur - 0.05, 0.3, 0.3)
    # 左侧温度计
    x, y0, y1 = 380.0, 360.0, 740.0
    o.stroke([(x - 14, y0), (x - 14, y1), (x + 14, y1), (x + 14, y0)], v.MUTED, 2.0, a * 0.8)
    o.dot((x, y1 + 26), 26, v.ICE, a * 0.7)
    frac = 0.20 + 0.25 * v.smoothstep(0.2, dur * 0.8, t)
    o.bar((x - 6, v.lerp(y1, y0, frac)), (x + 6, y1), v.ICE, a * 0.8)
    M(o, "低温", (x, y0 - 30), 26, v.ICE, a * 0.9)
    # 回收能力条被压窄
    bx0, bx1, by = 620.0, 1660.0, 620.0
    o.bar((bx0, by - 18), (bx1, by + 18), v.LINE, a * 0.5)
    wide = v.lerp(1.0, 0.45, v.smoothstep(0.2, dur * 0.8, t))
    o.bar((bx0, by - 18), (bx0 + (bx1 - bx0) * wide, by + 18), v.ICE, a * 0.5)
    T(o, "低温：限制更紧", (960, 330), 40, v.BONE, v.F_SANS, a, track=4)
    M(o, "充电能力下降 → 回收能力条被压窄（F10/F11）", (960, 760), 26, v.MUTED, a * 0.85)


# ---------------------------------------------------------------- S48
def ov_aero_arrows(t, dur, o, sh):
    a = v.window(t, 0.2, dur - 0.05, 0.3, 0.3)
    for k in range(7):
        y = 420 + k * 56
        ln = 260 + 180 * v.smoothstep(0.2, dur * 0.8, t)
        arrow(o, (1500, y), (1500 - ln, y - 8), v.ICE, a * 0.45, 2.2 + k * 0.4, 14, 6)
    T(o, "风阻吃大头", (960, 360), 48, v.ICE, v.F_SANS, a, track=5, glow=10 * a)
    M(o, "车速越高，风阻越大：这部分收不回来", (960, 800), 27, v.MUTED, a * 0.9)


# ---------------------------------------------------------------- S49
def ov_grip_ring(t, dur, o, sh):
    a = v.window(t, 0.15, dur - 0.05, 0.25, 0.25)
    cx, cy, R = 1180.0, 620.0, 190.0
    frac = 0.85 - 0.55 * v.smoothstep(0.3, dur * 0.85, t)
    ring(o, cx, cy, R, frac, v.TEAL if frac > 0.6 else v.EMBER, 10, a)
    T(o, "第四条：抓地力不足", (960, 380), 42, v.BONE, v.F_SANS, a, track=4)
    M(o, "轮胎抓不住地面 → 回收不能硬来", (960, 800), 26, v.MUTED, a * 0.9)


# ---------------------------------------------------------------- S50
def ov_abs_indicator(t, dur, o, sh):
    a = v.window(t, 0.1, dur - 0.05, 0.2, 0.2)
    # ABS 灯（闪烁）
    blink = 0.55 + 0.45 * math.sin(t * 9)
    chip(o, (430, 400), "ABS", v.EMBER, a * blink, 34, fill=0.16)
    T(o, "ABS：先保方向", (960, 330), 42, v.BONE, v.F_SANS, a, track=4)
    # 轮速抖动曲线
    x0, x1, y = 620.0, 1500.0, 720.0
    o.stroke([(x0, y), (x1, y)], v.LINE, 1.4, a * 0.7)
    jitter = 0.16 + 0.3 * abs(math.sin(t * 7))
    xs = np.linspace(0, 1, 150)
    ys = 0.22 + jitter * (np.sin(xs * 90) * 0.5 + 0.5) * np.exp(-xs * 0.4)
    pts = np.stack([x0 + xs * (x1 - x0), y - ys * 140], 1)
    o.stroke(pts, v.TEAL, 2.2, a * 0.85, 8, 0.4)
    M(o, "轮速抖动 · 回收退出 · 摩擦制动接管", (960, 800), 26, v.MUTED, a * 0.9)


# ---------------------------------------------------------------- S53
def ov_pedal_logic(t, dur, o, sh):
    a = v.window(t, 0.2, dur - 0.05, 0.3, 0.3)
    T(o, "单踏板", (960, 330), 44, v.BONE, v.F_SANS, a, track=4)
    nodes = ((480.0, 620.0, "抬油门"), (960.0, 620.0, "电机回收"),
             (1440.0, 620.0, "机械刹车补足"))
    for i, (x, y, lab) in enumerate(nodes):
        on = i <= int(v.smoothstep(0.2, dur * 0.8, t) * 3)
        o.stroke(v._rounded_rect_pts(x - 130, y - 40, x + 130, y + 40, 12),
                 v.TEAL if on else v.MUTED, 1.8, a * (0.9 if on else 0.35), 10 if on else 0)
        T(o, lab, (x, y), 28, v.BONE if on else v.MUTED, v.F_SANS_R,
          a * (0.95 if on else 0.4), track=1)
    arrow(o, (620, 620), (830, 620), v.TEAL, a * 0.75)
    arrow(o, (1100, 620), (1310, 620), v.AMBER, a * 0.6)
    M(o, "先回收，不够再上刹车；松油门那一下就开始", (960, 760), 26, v.MUTED, a * 0.9)


# ---------------------------------------------------------------- S55
def ov_decel_cup(t, dur, o, sh):
    a = v.window(t, 0.2, dur - 0.05, 0.3, 0.3)
    x0, x1, y0, y1 = 420.0, 1480.0, 800.0, 560.0
    o.stroke([(x0, y0), (x1, y0)], v.LINE, 1.4, a * 0.7)
    xs = np.linspace(0, 1, 100)

    def smooth_dec(x):
        return np.exp(-((x - 0.3) ** 2) / (2 * 0.22 ** 2))

    def jerk_dec(x):
        return np.exp(-((x - 0.32) ** 2) / (2 * 0.08 ** 2)) * 0.95
    for fn, col, lab in ((smooth_dec, v.TEAL, "平顺"), (jerk_dec, v.AMBER, "点头")):
        ys = fn(xs)
        pts = np.stack([x0 + xs * (x1 - x0), y0 - ys * (y0 - y1)], 1)
        n = max(2, int(100 * v.smoothstep(0.2, dur * 0.8, t)))
        o.stroke(pts[:n], col, 2.6, a * 0.9, 12, 0.5)
    T(o, "平顺 vs 点头", (960, 350), 42, v.BONE, v.F_SANS, a, track=4)
    M(o, "分得好平顺，分不好脚下会点头（Blending）", (960, 800), 26, v.MUTED, a * 0.9)


# ---------------------------------------------------------------- S56 / S57
def _range_ring(t, dur, o, frac, color, title, center, sub):
    a = v.window(t, 0.15, dur - 0.05, 0.25, 0.25)
    cx, cy, R = 1420.0, 500.0, 150.0
    ring(o, cx, cy, R, frac, color, 16, a)
    T(o, center, (cx, cy), 64, color, v.F_SANS, a, track=2, glow=14 * a)
    M(o, "回收占比 · 视觉示意（非读数）", (cx, cy + 220), 20, v.MUTED, a * 0.8, track=0.5)
    T(o, title, (960, 360), 44, v.BONE, v.F_SANS, a, track=4)
    M(o, sub, (960, 800), 26, v.MUTED, a * 0.9)


def ov_ring_city(t, dur, o, sh):
    _range_ring(t, dur, o, 0.22 * v.smoothstep(0.2, dur * 0.8, t), v.TEAL,
                "城市省", "实打实省", "走走停停，回收实打实贡献续航")


def ov_ring_highway(t, dur, o, sh):
    """S57：高速续航：回收占比几乎为零（空景 + <5%，不出现百分比读数）。"""
    a = v.window(t, 0.15, dur - 0.05, 0.25, 0.25)
    T(o, "高速难", (960, 380), 44, v.BONE, v.F_SANS, a, track=4)
    T(o, "< 5%", (960, 500), 132, v.AMBER, v.F_SANS, a, track=4, glow=20 * a)
    M(o, "高速巡航，回收能量占驱动能量常不到 5%（F06）", (960, 620), 26, v.MUTED, a * 0.9,
      track=1)
    # 高速空景：稀疏横向光带 + 路面透视（不抢文字）
    for k in range(3):
        y = 760 + k * 30
        xs = v.lerp(300, 1600, (t * 0.22 + k * 0.3) % 1.0)
        o.stroke([(xs - 260, y), (xs, y - 6)], v.ICE, 2.2, a * 0.22, 8, 0.4)
        o.stroke([(xs - 130, y + 14), (xs, y + 6)], v.MUTED, 1.6, a * 0.16)


# ---------------------------------------------------------------- S58
def ov_pad_bars(t, dur, o, sh):
    a = v.window(t, 0.2, dur - 0.05, 0.3, 0.3)
    T(o, "刹车片更耐磨", (960, 350), 44, v.BONE, v.F_SANS, a, track=4)
    base = 720.0
    for i, (lab, h, col, x) in enumerate((("有回收的日常", 0.85, v.TEAL, 700.0),
                                          ("全靠摩擦制动", 0.45, v.AMBER, 1180.0))):
        aa = v.smoothstep(0.25 + i * 0.25, dur * 0.75, t)
        o.bar((x - 70, base - 260 * h * aa), (x + 70, base), col, a * 0.35)
        o.stroke([(x - 70, base - 260 * h * aa), (x + 70, base - 260 * h * aa),
                  (x + 70, base), (x - 70, base)], col, 2.0, a * 0.85, closed=True)
        T(o, lab, (x, base + 50), 24, v.MUTED, v.F_SANS_R, a * 0.85, track=1)
    M(o, "定性对比，不写死倍数（F16）", (960, 800), 24, v.MUTED, a * 0.8)


# ---------------------------------------------------------------- S59
def ov_rust_text(t, dur, o, sh):
    a = v.window(t, 0.2, dur - 0.05, 0.3, 0.3)
    T(o, "但也不能不用", (960, 360), 48, v.BONE, v.F_SANS, a, track=5, glow=8 * a)
    chip(o, (960, 470), "长期不用会锈 → 偶尔轻踩机械制动", v.AMBER, a * 0.9, 26)
    M(o, "回收改变的是分配，不是取消机械刹车", (960, 790), 26, v.MUTED, a * 0.85)


# ---------------------------------------------------------------- S60
def ov_style_traces(t, dur, o, sh):
    a = v.window(t, 0.2, dur - 0.05, 0.3, 0.3)
    # 两条轨迹（同一条路，两种开法）
    o.stroke(bezier_pts((380, 700), (760, 660), (1080, 700), (1520, 560)), v.TEAL,
             3.0, a * 0.8, 10, 0.4)
    o.stroke(bezier_pts((380, 700), (820, 740), (1120, 600), (1520, 660)), v.AMBER,
             3.0, a * 0.7, 10, 0.4)
    T(o, "提前松", (1120, 660), 24, v.TEAL, v.F_SANS_R, a * 0.9, track=2)
    T(o, "到跟前重刹", (1180, 580), 24, v.AMBER, v.F_SANS_R, a * 0.9, track=2)
    T(o, "改变的是习惯", (960, 350), 42, v.BONE, v.F_SANS, a, track=4)


# ---------------------------------------------------------------- S66
def ov_end_line(t, dur, o, sh):
    a = v.window(t, 0.2, dur - 0.05, 0.35, 0.35)
    T(o, "边界", (960, 430), 96, v.BONE, v.F_SANS, a, track=12, glow=14 * a)
    rule(o, 760, 1160, 520, v.TEAL, a * 0.75, 1.8)
    M(o, "收 / 不收", (960, 600), 30, v.TEAL, a * 0.9, track=6)


OVERLAYS = {
    "soc_climb": ov_soc_climb,
    "conservation_text": ov_conservation_text,
    "wheel_push_arrow": ov_wheel_push_arrow,
    "heat_vs_charge": ov_heat_vs_charge,
    "bms_gate": ov_bms_gate,
    "pedal_power": ov_pedal_power,
    "heat_text": ov_heat_text,
    "real78": ov_real78,
    "city_curve": ov_city_curve,
    "mgh_annotation": ov_mgh_annotation,
    "cold_limit": ov_cold_limit,
    "aero_arrows": ov_aero_arrows,
    "grip_ring": ov_grip_ring,
    "abs_indicator": ov_abs_indicator,
    "pedal_logic": ov_pedal_logic,
    "decel_cup": ov_decel_cup,
    "ring_city": ov_ring_city,
    "ring_highway": ov_ring_highway,
    "pad_bars": ov_pad_bars,
    "rust_text": ov_rust_text,
    "style_traces": ov_style_traces,
    "end_line": ov_end_line,
}
