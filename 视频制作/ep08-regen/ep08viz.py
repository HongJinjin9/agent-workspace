#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第 08 期《电动车松开油门为什么能充电》视觉库
==================================================
横屏 1920×1080 / 24fps / 2.35:1 遮幅（上下各 132px 黑边由 finalize 统一加）。

设计语言（延续「vibe 知识共赏」系列）：
- 影调：冷灰底 #0e1216 / 纸白 #e9e4d8 / 能量青 #2fd3c5（回收、电）/
  动力琥珀 #d9a441（输出、损耗）/ 批注红 #b3392e（危险、限制）；
- 数据层是「压在实拍上的光」：细线 + 柔辉光 + 等宽数字刻度，不做灰底图表卡；
- 原理必须由真实拓扑与数学生成：可逆能量通道、电机定子/转子三相绕组、
  逆变器三桥臂、电池模组串并、Sankey 宽度 = 能量值；
- 一屏一个第一视觉重点；全片统一颗粒、暗角、调色；字幕在 2.35 遮幅下黑边内。

本模块 = 可复用图元（cv2 矢量 + PIL 文字 + numpy 后期）+ 本期模型层
（能量通道 / 电机 / 逆变器 / 电池 / 能量账 / 功率表 / 单踏板），
scenes_pil.py 与 overlays.py 共用同一套坐标系，保证同一物体跨镜连续。
"""
import math
import os

import cv2
import numpy as np

try:  # 128 核机器上把 OpenCV 内部线程压到 1，避免每个渲染进程开满线程互相拖死
    cv2.setNumThreads(1)
except Exception:
    pass
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1920, 1080, 24
BAR = 132                       # 2.35:1：1080 - 2*132 = 816; 1920/816 ≈ 2.353
SAFE_T, SAFE_B = BAR, H - BAR   # 内容安全区（数据层不进黑边）

ROOT = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- fonts
F_SERIF = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc"
F_SERIF_R = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc"
F_SANS = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
F_SANS_R = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
F_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"

# ---------------------------------------------------------------- palette（PLAN §1）
INK = (14, 18, 22)              # #0e1216
INK2 = (23, 30, 36)
BONE = (233, 228, 216)          # #e9e4d8 纸白
WHITE = (248, 246, 240)
MUTED = (140, 156, 166)
DIM = (80, 96, 106)
LINE = (46, 60, 70)
TEAL = (47, 211, 197)           # #2fd3c5 回收 / 电
TEAL_D = (16, 86, 84)
TEAL_P = (158, 238, 229)
AMBER = (217, 164, 65)          # #d9a441 输出 / 损耗
AMBER_D = (104, 74, 24)
GOLD = (238, 198, 112)
EMBER = (179, 57, 46)           # #b3392e 危险 / 限制
EMBER_P = (224, 116, 96)
ICE = (168, 208, 224)
STEEL = (154, 172, 182)         # 结构金属
GRID = (44, 58, 68)


def c8(c):
    return tuple(int(max(0, min(255, v))) for v in c)


def ease_out_cubic(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def ease_in_cubic(t):
    t = max(0.0, min(1.0, t))
    return t ** 3


def ease_in_out(t):
    t = max(0.0, min(1.0, t))
    return 0.5 - 0.5 * math.cos(math.pi * t)


def smoothstep(a, b, x):
    if isinstance(x, np.ndarray):
        t = np.clip((x - a) / (b - a), 0.0, 1.0) if b != a else (x < a).astype(np.float32)
        return t * t * (3 - 2 * t)
    if b == a:
        return 0.0 if x < a else 1.0
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def clamp(x, a=0.0, b=1.0):
    return a if x < a else (b if x > b else x)


def lerp(a, b, t):
    return a + (b - a) * t


def window(t, t0, t1, fin=0.35, fout=0.35):
    """0→1→0 envelope in [t0,t1] with soft edges."""
    if t < t0 or t > t1:
        return 0.0
    return min(1.0, smoothstep(0, fin, t - t0), smoothstep(0, fout, t1 - t))


def damped_osc(t, freq_hz=1.6, zeta=0.3, amp=1.0, phase=0.0):
    """二阶欠阻尼冲击响应：x(t)=A e^{-ζωt} sin(ω_d t)（真实数学函数）。"""
    omega = 2 * math.pi * freq_hz
    wd = omega * math.sqrt(max(1e-6, 1 - zeta ** 2))
    return amp * np.exp(-zeta * omega * t) * np.sin(wd * t + phase)


# ================================================================ ep08 model layer
# 可逆能量通道 / 电机剖面 / 逆变器 / 电池 / 能量账 / 功率表 —— 全片共用同一坐标系。
# 所有能量数字从 facts.json 注入（本模块只负责画，不写死数字）。

# ---------------------------------------------------------------- 可逆能量通道
# 电池 — 逆变器 — 电机 — 车轮；放电（左→右）为动力琥珀，回收（右→左）为能量青。
CHAIN = [
    {"key": "battery",  "label": "电池",   "sub": "BATTERY PACK",  "x": 322.0, "y": 560.0},
    {"key": "inverter", "label": "逆变器", "sub": "INVERTER",      "x": 806.0, "y": 560.0},
    {"key": "motor",    "label": "电机",   "sub": "MOTOR / GEN",   "x": 1245.0, "y": 560.0},
    {"key": "wheel",    "label": "车轮",   "sub": "WHEEL",         "x": 1688.0, "y": 560.0},
]
CHAIN_Y = 560.0


def chain_segments(y=CHAIN_Y):
    """通道各段折线：电池↔逆变器↔电机↔车轮（端点按部件外形裁剪）。"""
    xs = [n["x"] for n in CHAIN]
    # 部件半宽：电池 118 / 逆变器 84 / 电机 112 / 车轮 120
    half = [118.0, 84.0, 112.0, 120.0]
    segs = []
    for i in range(3):
        x0 = xs[i] + half[i]
        x1 = xs[i + 1] - half[i + 1]
        segs.append(np.array([[x0, y], [x1, y]], np.float32))
    return segs


def chain_nodes():
    return [dict(n) for n in CHAIN]


def polar(cx, cy, r, deg):
    a = math.radians(deg)
    return (cx + r * math.cos(a), cy + r * math.sin(a))


def _rounded_rect_pts(x0, y0, x1, y1, r, n=6):
    """圆角矩形轮廓点列（用于 Painter.stroke）。"""
    r = min(r, (x1 - x0) / 2, (y1 - y0) / 2)
    pts = []
    for cx, cy, a0 in ((x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0),
                       (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)):
        for k in range(n + 1):
            a = math.radians(a0 + 90.0 * k / n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return np.array(pts, np.float32)


def draw_battery_pack(p, cx, cy, w=236.0, h=196.0, soc=0.62, temp=0.5,
                      highlight=None, alpha=1.0, glow=0.0, fill=0.0):
    """电池剖面：模组阵列（3×2）+ 电芯 + BMS + SOC 条 + 高低温热状态。"""
    x0, x1 = cx - w / 2, cx + w / 2
    y0, y1 = cy - h / 2, cy + h / 2
    hh = highlight or {}
    a = alpha
    # 外壳
    p.stroke(_rounded_rect_pts(x0, y0, x1, y1, 14), STEEL, 2.0, a * 0.85, glow, 0.5)
    # 模组 3 列 × 2 行
    mx0, mx1 = x0 + 16, x1 - 16
    my0, my1 = y0 + 30, y1 - 52
    cols, rows = 3, 2
    gap = 10.0
    mw = (mx1 - mx0 - gap * (cols - 1)) / cols
    mh = (my1 - my0 - gap * (rows - 1)) / rows
    heat = clamp((temp - 0.55) / 0.45) * 0.55 + clamp((0.35 - temp) / 0.35) * 0.55
    for r in range(rows):
        for c in range(cols):
            gx0 = mx0 + c * (mw + gap)
            gy0 = my0 + r * (mh + gap)
            on = hh.get("module") is None or hh.get("module") == (r * cols + c)
            ha = a if on else a * 0.38
            p.stroke(_rounded_rect_pts(gx0, gy0, gx0 + mw, gy0 + mh, 5), ICE, 1.4, ha * 0.75)
            # 电芯：每模组 4 列
            ncell = 4
            cw = (mw - 8) / ncell
            for k in range(ncell):
                cx0 = gx0 + 4 + k * cw
                lvl = clamp((soc - (r * cols + c) * 0.06) * 1.12 - k * 0.2)
                col = TEAL if lvl > 0.55 else (TEAL_D if lvl > 0.2 else DIM)
                if heat > 0.02:
                    col = (int(col[0] + (EMBER[0] - col[0]) * heat * 0.7),
                           int(col[1] + (EMBER[1] - col[1]) * heat * 0.7),
                           int(col[2] + (EMBER[2] - col[2]) * heat * 0.7))
                p.fill_rect((cx0, gy0 + 6), (cx0 + cw * 0.62, gy0 + mh - 6), col,
                            ha * (0.20 + 0.55 * lvl))
    # BMS 条
    by = y1 - 34
    p.stroke([(x0 + 16, by), (x1 - 16, by)], MUTED, 1.2, a * 0.55)
    for k in range(4):
        xx = x0 + 24 + k * 52
        p.dot((xx, by), 2.2, TEAL_P, a * 0.7)
    # SOC 条
    sx0, sx1 = x0 + 16, x1 - 16
    sy0, sy1 = y0 + 12, y0 + 20
    p.fill_rect((sx0, sy0), (sx1, sy1), LINE, a * 0.6)
    p.fill_rect((sx0, sy0), (sx0 + (sx1 - sx0) * clamp(soc), sy1), TEAL, a * 0.9)
    # 充放电端子（右端接通道）
    p.stroke([(x1, cy - 16), (x1 + 8, cy - 16)], AMBER, 2.0, a * 0.8)
    p.stroke([(x1, cy + 16), (x1 + 8, cy + 16)], MUTED, 2.0, a * 0.8)
    p.dot((x1 + 8, cy), 2.6, TEAL_P if fill >= 0 else AMBER, a, glow=6)
    if hh.get("outline"):
        p.stroke(_rounded_rect_pts(x0 - 5, y0 - 5, x1 + 5, y1 + 5, 16), TEAL, 2.2, a * 0.9, 10, 0.6)


def draw_inverter(p, cx, cy, w=168.0, h=172.0, active="dc", alpha=1.0, glow=0.0,
                  highlight=None, live=0.0):
    """逆变器：DC 母线（±）→ 三桥臂（6 开关）→ 三相输出。active: dc/phase/heat。"""
    x0, x1 = cx - w / 2, cx + w / 2
    y0, y1 = cy - h / 2, cy + h / 2
    a = alpha
    hh = highlight or {}
    # 外壳 + 散热齿
    p.stroke(_rounded_rect_pts(x0, y0, x1, y1, 8), STEEL, 2.0, a * 0.85)
    for k in range(5):
        y = y0 + 12 + k * (h - 24) / 4
        p.stroke([(x0 - 10, y), (x0 - 2, y)], MUTED, 1.4, a * 0.4)
        p.stroke([(x1 + 2, y), (x1 + 10, y)], MUTED, 1.4, a * 0.4)
    # DC 母线（左）
    bus_x = x0 + 22
    p.stroke([(bus_x, y0 + 14), (bus_x, y1 - 14)], AMBER, 2.4, a * (0.95 if active == "dc" else 0.5),
             glow if active == "dc" else 0, 0.5)
    p.dot((bus_x, y0 + 12), 3.0, AMBER, a)
    p.dot((bus_x, y1 - 12), 3.0, MUTED, a)
    p.stroke([(bus_x - 7, y0 + 12), (bus_x + 7, y0 + 12)], AMBER, 1.4, a)
    p.stroke([(bus_x - 7, y1 - 12), (bus_x + 7, y1 - 12)], MUTED, 1.4, a)
    # 三桥臂：DC 母线 → 上下开关 → 中点 → 三相输出
    br_x0, br_x1 = bus_x + 26, x1 - 26
    for k in range(3):
        bx = lerp(br_x0, br_x1, k / 2.0)
        col = TEAL if active == "phase" else STEEL
        p.stroke([(bx, y0 + 24), (bx, y1 - 24)], DIM, 1.2, a * 0.7)
        for sw in (0, 1):
            sy = lerp(y0 + 40, y1 - 40, sw)
            p.stroke([(bus_x, sy), (bx, sy)], DIM, 1.2, a * 0.55)
            p.fill_rect((bx - 8, sy - 8), (bx + 8, sy + 8), col, a * (0.16 + 0.42 * live))
            p.stroke([(bx - 8, sy - 8), (bx + 8, sy - 8), (bx + 8, sy + 8),
                      (bx - 8, sy + 8)], col, 1.3, a * 0.9, closed=True)
            p.stroke([(bx + 11, sy + 6), (bx + 11, sy - 6)], MUTED, 1.1, a * 0.5)
        # 中点 → 输出（水平引出，相位错开）
        p.dot((bx, cy), 2.4, TEAL if active == "phase" else MUTED, a)
        oy = cy + (k - 1) * 20
        p.stroke([(bx, cy), (bx, oy), (x1 - 4, oy)], TEAL, 1.7,
                 a * (0.9 if active == "phase" else 0.35),
                 glow if active == "phase" else 0, 0.5)
        p.dot((x1 - 4, oy), 3.0, TEAL if active == "phase" else MUTED, a * 0.9,
              glow=8 if active == "phase" else 0)
    if hh.get("outline"):
        p.stroke(_rounded_rect_pts(x0 - 4, y0 - 4, x1 + 4, y1 + 4, 10), TEAL, 2.2, a * 0.9, 10, 0.6)


def draw_motor(p, cx, cy, r=112.0, spin=0.0, alpha=1.0, active="rotor", glow=0.0,
               highlight=None, flux=0.0):
    """电机剖面：定子槽（三相绕组）+ 气隙 + 转子磁极 + 轴。active: stator/rotor/phase。"""
    a = alpha
    hh = highlight or {}
    # 外壳（立即压暗，防止后续 mask 合成把环线盖掉）
    p.dark_circle((cx, cy), r + 10, factor=0.30 if active == "rotor" else 0.40)
    p.stroke([polar(cx, cy, r + 8, k * 3.0) for k in range(120)], STEEL, 1.6, a * 0.5, closed=True)
    # 定子铁芯环
    for rr in (r, r - 26):
        p.stroke([polar(cx, cy, rr, k * 2.5) for k in range(145)], STEEL, 1.4, a * 0.55, closed=True)
    # 定子槽：12 槽，三相循环着色
    phases = (TEAL, AMBER, ICE)
    for k in range(12):
        deg = k * 30.0 + spin * 0.0
        cxx, cyy = polar(cx, cy, r - 13, deg)
        col = phases[k % 3]
        act = active == "stator" or active == "phase"
        p.fill_rect((cxx - 6, cyy - 11), (cxx + 6, cyy + 11), col,
                    a * (0.52 if act else 0.24))
        if active == "phase":
            p.dot((cxx, cyy), 2.2, WHITE, a * 0.8)
    # 气隙
    p.stroke([polar(cx, cy, r - 36, k * 3.0) for k in range(120)], DIM, 1.0, a * 0.55, closed=True)
    # 转子（8 极：N/S 交替，环形扇区）
    rot = r - 44
    inner = 16.0
    ang = spin
    n_pole = 8
    step = 360.0 / n_pole
    on = active == "rotor"
    for k in range(n_pole):
        a0 = ang + k * step + 1.5
        a1 = a0 + step - 3.0
        outer = [polar(cx, cy, rot, a0 + (a1 - a0) * q / 7.0) for q in range(8)]
        innr = [polar(cx, cy, inner, a1 - (a1 - a0) * q / 7.0) for q in range(8)]
        col = (172, 96, 82) if k % 2 == 0 else (74, 158, 156)
        p.fill_poly(np.array(outer + innr, np.float32), col, a * (0.30 if on else 0.16))
        p.stroke([outer[0], innr[-1]], DIM, 1.0, a * 0.45)
    p.stroke([polar(cx, cy, rot, k * 3.0) for k in range(120)], STEEL, 1.4, a * 0.75, closed=True)
    # 轴
    p.fill_circle((cx, cy), 13, STEEL, a * 0.8)
    p.dot((cx, cy), 5, INK, a)
    # 磁力线（回收时反向旋转）
    if flux > 0.02:
        for k in range(3):
            rr = rot * (0.45 + 0.18 * k)
            p.stroke([polar(cx, cy, rr, ang * 0.6 + q * 10.0) for q in range(36)],
                     TEAL, 1.1, a * 0.28 * flux, closed=True)
    if hh.get("outline"):
        p.stroke([polar(cx, cy, r + 12, k * 3.0) for k in range(120)], TEAL, 2.2, a * 0.9, 10, 0.6, closed=True)


def draw_wheel(p, cx, cy, r=118.0, spin=0.0, alpha=1.0, torque=0.0):
    """车轮 + 轮毂：旋转由 spin 直接驱动（真实滚动相位）。"""
    a = alpha
    p.dark_circle((cx, cy), r + 8, factor=0.26)
    p.stroke([polar(cx, cy, r, k * 3.0) for k in range(120)], STEEL, 3.4, a * 1.0, closed=True)
    p.stroke([polar(cx, cy, r - 13, k * 3.0) for k in range(120)], BONE, 1.3, a * 0.55, closed=True)
    # 轮辐
    for k in range(5):
        deg = spin + k * 72.0
        p.stroke([polar(cx, cy, 24, deg), polar(cx, cy, r - 22, deg)], STEEL, 1.6, a * 0.7)
    p.fill_circle((cx, cy), 22, LINE, a * 0.9)
    p.dot((cx, cy), 7, MUTED, a)
    # 接地点
    p.stroke([(cx - 46, cy + r + 6), (cx + 46, cy + r + 6)], MUTED, 1.6, a * 0.5)
    if abs(torque) > 0.01:
        col = TEAL if torque < 0 else AMBER
        p.dot((cx, cy), 8 + 22 * clamp(abs(torque)), col, a * 0.22)


def draw_energy_chain(p, t=0.0, direction=1, flow=0.0, active=None, alpha=1.0,
                      labels=True, y=CHAIN_Y, dim_unused=False, loss=False,
                      soc=0.62, spin=0.0, live=0.6):
    """可逆能量通道主图：direction=+1 放电（电池→车轮，琥珀）；−1 回收（青）。"""
    a = alpha
    col = TEAL if direction < 0 else AMBER
    # 通道底板
    for seg in chain_segments(y):
        p.stroke(seg, LINE, 6.0, a * 0.42)
        p.stroke(seg, LINE, 10.0, a * 0.16)
    # 节点
    draw_battery_pack(p, CHAIN[0]["x"], y, soc=soc, alpha=a,
                      highlight={"outline": active == "battery"},
                      glow=8 if active == "battery" else 0, fill=direction)
    draw_inverter(p, CHAIN[1]["x"], y, alpha=a,
                  active="dc" if direction > 0 else "phase",
                  highlight={"outline": active == "inverter"},
                  live=live)
    draw_motor(p, CHAIN[2]["x"], y, spin=spin, alpha=a,
               active="rotor" if direction < 0 else "stator",
               highlight={"outline": active == "motor"},
               flux=1.0 if direction < 0 else 0.0)
    draw_wheel(p, CHAIN[3]["x"], y, spin=spin, alpha=a, torque=-direction * 0.6)
    # 流动粒子（方向即能量流向）
    if flow > 0.001:
        for seg in chain_segments(y):
            flow_dots(p, seg, t, speed=300.0, direction=-direction, color=col,
                      n=6, alpha=a * flow, r=2.6, glow=9)
    # 损耗支路（向下，琥珀色热流）：labels 由场景层用 facts 标注
    if loss:
        for x in (CHAIN[1]["x"], CHAIN[2]["x"]):
            loss_tap(p, (x, y + 96), alpha=a * 0.85)
    if labels:
        for n in CHAIN:
            draw_text(p.rgb, n["label"], (n["x"], y + (168 if n["key"] != "wheel" else 178)),
                      34, BONE, F_SANS, "mm", a * 0.95, track=2.0)
            draw_text(p.rgb, n["sub"], (n["x"], y + (202 if n["key"] != "wheel" else 212)),
                      17, MUTED, F_MONO, "mm", a * 0.7, track=1.6)


def loss_tap(p, xy, alpha=1.0, length=52, color=AMBER):
    """单级损耗支路：从通道向下引出的热流（方向始终向下=离开能量通道）。"""
    x, y = xy
    p.stroke([(x, y), (x, y + length)], color, 2.0, alpha * 0.8, 8, 0.4)
    p.stroke([(x - 6, y + length - 8), (x, y + length), (x + 6, y + length - 8)],
             color, 2.0, alpha * 0.9)
    p.dot((x, y + length + 12), 2.4, color, alpha * 0.55)


def flow_dots(p, pts, t, speed=300.0, direction=1, color=TEAL, n=6, alpha=1.0,
              r=2.6, glow=9, trail=True):
    """沿折线的流动粒子（能量方向的可视化，不是装饰）。"""
    pts = np.asarray(pts, np.float32)
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    L = float(seg.sum())
    if L <= 1e-3:
        return
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    phase = (t * speed) % (L / n)
    for k in range(n):
        s = (phase + k * (L / n)) % L
        if direction < 0:
            s = L - s
        i = int(np.searchsorted(cum, s, side="right") - 1)
        i = min(max(0, i), len(pts) - 2)
        f = (s - cum[i]) / max(1e-6, seg[i])
        xy = pts[i] + f * (pts[i + 1] - pts[i])
        p.dot(xy, r, color, alpha, glow=glow, glow_a=0.75)


# ---------------------------------------------------------------- 能量账（Sankey）
def sankey_ribbon(p, x0, y0a, y0b, x1, y1a, y1b, color, alpha=0.55, glow=0.0, n=28):
    """Sankey 带宽条带：两端上下沿各自平滑过渡，宽度 = 能量值。"""
    ts = np.linspace(0, 1, n)
    xs = x0 + (x1 - x0) * ts
    # cubic ease 的上下沿
    e = ts * ts * (3 - 2 * ts)
    ya = y0a + (y1a - y0a) * e
    yb = y0b + (y1b - y0b) * e
    top = np.stack([xs, ya], 1)
    bot = np.stack([xs, yb], 1)[::-1]
    poly = np.concatenate([top, bot], 0)
    p.fill_poly(poly, color, alpha)
    if glow > 0:
        p.stroke(top, color, 1.2, alpha * 0.5, glow, 0.4)
        p.stroke(bot, color, 1.2, alpha * 0.5, glow, 0.4)


# ---------------------------------------------------------------- 功率表 / 仪表
def power_meter(p, cx, cy, R, value, vmin=-30.0, vmax=120.0, alpha=1.0, label="",
                unit="kW"):
    """车机功率表：左负（回收，青）右正（输出，琥珀）；value 单位 kW。"""
    a0, a1 = 155.0, 385.0          # 左侧起点 155° → 顺时针到 385°（跨过 270°底部）
    # 背景弧 + 区域弧
    def arc_pts(va, vb, r=R):
        ta = a0 + (a1 - a0) * clamp((va - vmin) / (vmax - vmin))
        tb = a0 + (a1 - a0) * clamp((vb - vmin) / (vmax - vmin))
        return np.array([polar(cx, cy, r, lerp(ta, tb, q / 40.0)) for q in range(41)], np.float32)
    p.stroke(arc_pts(vmin, vmax, R), LINE, 9, a * 0.55)
    p.stroke(arc_pts(vmin, 0.0, R), TEAL, 8, a * 0.30)
    p.stroke(arc_pts(0.0, vmax, R), AMBER, 8, a * 0.24)
    # 刻度
    for v in range(int(vmin // 30) * 30, int(vmax) + 1, 30):
        if v < vmin or v > vmax:
            continue
        ang = a0 + (a1 - a0) * clamp((v - vmin) / (vmax - vmin))
        p.stroke([polar(cx, cy, R - 13, ang), polar(cx, cy, R - 22, ang)],
                 MUTED, 1.4, a * 0.7)
    # 指针
    vv = clamp(value, vmin, vmax)
    ang = a0 + (a1 - a0) * clamp((vv - vmin) / (vmax - vmin))
    col = TEAL if vv < 0 else AMBER
    p.stroke([polar(cx, cy, R - 26, ang), polar(cx, cy, 6, ang)], col, 3.2, a, 12, 0.7)
    p.dot((cx, cy), 7, col, a, glow=14)
    # 数字
    return col


# ---------------------------------------------------------------- 轴 / 曲线 / 条
def draw_axes(p, x0, y0, x1, y1, alpha=1.0, xticks=5, yticks=4, glow=0.0):
    p.stroke([(x0, y0), (x1, y0)], LINE, 1.6, alpha * 0.9)
    p.stroke([(x0, y0), (x0, y1)], LINE, 1.6, alpha * 0.9)
    for k in range(xticks + 1):
        x = lerp(x0, x1, k / xticks)
        p.stroke([(x, y0), (x, y0 + 7)], DIM, 1.2, alpha * 0.7)
    for k in range(yticks + 1):
        y = lerp(y0, y1, k / yticks)
        p.stroke([(x0 - 7, y), (x0, y)], DIM, 1.2, alpha * 0.7)


def curve_pts(fn, x0, x1, n=160):
    xs = np.linspace(x0, x1, n)
    return np.stack([xs, fn(xs)], 1).astype(np.float32)


def car_side(p, cx, cy, scale=1.0, alpha=1.0, regen=0.0, glow=0.0):
    """极简车侧轮廓线（能量箭头沿车身回流），用于钩子/下坡示意。"""
    s = scale
    pts = np.array([(-150, 26), (-138, -6), (-92, -16), (-70, -46), (-18, -56),
                    (34, -56), (66, -44), (96, -40), (138, -26), (152, -4),
                    (150, 22), (118, 30), (60, 32), (-40, 32), (-108, 28)], np.float32)
    pts[:, 0] = cx + pts[:, 0] * s
    pts[:, 1] = cy + pts[:, 1] * s
    p.stroke(pts, BONE, 2.6, alpha * 0.85, glow, 0.5, closed=True)
    for wx in (-84, 86):
        p.stroke([polar(cx + wx * s, cy + 34 * s, 26 * s, d) for d in range(0, 361, 5)],
                 BONE, 2.0, alpha * 0.8, closed=True)
        p.stroke([polar(cx + wx * s, cy + 34 * s, 7 * s, d) for d in range(0, 361, 10)],
                 MUTED, 1.2, alpha * 0.6, closed=True)
# ---------------------------------------------------------------- 底 / 版式
_BG_CACHE = {}


def bg_frame(tint=TEAL, strength=0.11, cx=0.5, cy=0.45, grid=True, grid_step=72,
             horizon=None, dark=1.0):
    """冷灰技术底：垂直渐变 + 单色柔光 + 细网格；全片统一，靠内容而非背景动。

    同一组参数的底图缓存复用（底图全片静态，不承担叙事运动）。
    """
    key = (tuple(tint), round(strength, 4), round(cx, 3), round(cy, 3), bool(grid),
           grid_step, horizon, round(dark, 4))
    cached = _BG_CACHE.get(key)
    if cached is not None:
        return cached.copy()
    yy = np.linspace(0.0, 1.0, H, dtype=np.float32)[:, None, None]
    base = np.array(INK, np.float32) / 255.0
    shade = 0.72 + 0.52 * (1.0 - yy) ** 1.5
    rgb = np.ones((H, W, 3), np.float32) * base[None, None, :] * shade * dark
    gy, gx = np.ogrid[:H, :W]
    nx = (gx - cx * W) / (W * 0.52)
    ny = (gy - cy * H) / (H * 0.46)
    g = np.exp(-(nx * nx * 1.5 + ny * ny * 2.1)) * strength
    rgb = rgb + (np.array(tint, np.float32) / 255.0)[None, None, :] * g[..., None]
    if grid:
        gv = 0.022 * dark
        xs = np.arange(0, W, grid_step)
        ys = np.arange(0, H, grid_step)
        rgb[:, xs, :] += gv
        rgb[ys, :, :] += gv
    if horizon is not None:
        y = int(horizon)
        rgb[max(0, y - 1):y + 2] = rgb[max(0, y - 1):y + 2] * 0.82 + 0.04
    rgb = np.clip(rgb, 0, 1)
    _BG_CACHE[key] = rgb
    return rgb.copy()


def ribbon_glow(rgb, y0, y1, color=(47, 211, 197), strength=0.10):
    """水平能量带柔光（作为版式背景，不承载数字）。"""
    yy = np.arange(H, dtype=np.float32)[:, None, None]
    band = np.exp(-((yy - (y0 + y1) / 2.0) ** 2) / (2 * 120.0 ** 2)) * strength
    return np.clip(rgb + (np.array(color, np.float32) / 255.0)[None, None, :] * band, 0, 1)


def leader_label(p, xy, tx, ty, text, sub=None, color=BONE, size=30, alpha=1.0,
                 sub_color=MUTED, sub_size=17, font=F_SANS, align="left"):
    """引线标签：细折线 + 端点小点 + 主/副文本（用于剖面标注）。"""
    x, y = xy
    pts = [(x, y), (tx, y), (tx, ty)]
    p.stroke(pts, MUTED, 1.2, alpha * 0.65)
    p.dot((x, y), 2.4, color, alpha * 0.9)
    anchor = "lm" if align == "left" else "rm"
    dx = 6 if align == "left" else -6
    draw_text(p.rgb, text, (tx + dx, ty), size, color, font, anchor, alpha)
    if sub:
        draw_text(p.rgb, sub, (tx + dx, ty + size * 0.78), sub_size, sub_color,
                  F_MONO, anchor, alpha * 0.8, track=1.0)


def chip(rgb, xy, text, color=TEAL, size=22, alpha=1.0, pad=(14, 8), font=F_SANS_R):
    """小标签（取值 / 单位 / 限制条件）。"""
    im = text_tex(text, size, color, font, 0, (0, 0, 0), 1.0)
    x, y = xy
    w, h = im.width + pad[0] * 2, im.height + pad[1]
    return x - w / 2, y - h / 2, w, h


def draw_chip(p, xy, text, color=TEAL, size=22, alpha=1.0, pad=(16, 9), fill=0.10,
              font=F_SANS_R, anchor="mm"):
    im = text_tex(text, size, color, font, 0, (0, 0, 0), 0.6)
    w, h = im.width + pad[0] * 2, im.height + pad[1]
    x, y = xy
    ax = {"mm": 0.5, "lm": 0.0, "rm": 1.0}.get(anchor, 0.5)
    x0, y0 = x - w * ax, y - h / 2
    p.fill_rect((x0, y0), (x0 + w, y0 + h), color, alpha * fill)
    p.stroke([(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)], color,
             1.2, alpha * 0.75, closed=True)
    draw_text(p.rgb, text, (x, y), size, color, font, "mm", alpha, track=0.6)


# ---------------------------------------------------------------- text
_TEX = {}


def _font(path, size):
    key = ("font", path, size)
    f = _TEX.get(key)
    if f is None:
        f = ImageFont.truetype(path, size)
        _TEX[key] = f
    return f


_GLYPH_MISS = {}


def _has_cjk(s):
    return any("\u4e00" <= ch <= "\u9fff" for ch in s)


def _glyph_missing(font_path, ch):
    """用私有区字符位图作 tofu 参照，判断字体是否缺该字形。"""
    key = (font_path, ch)
    v = _GLYPH_MISS.get(key)
    if v is None:
        fnt = _font(font_path, 40)
        ref = Image.new("L", (96, 96), 0)
        ImageDraw.Draw(ref).text((8, 8), "\ue000", font=fnt, fill=255)
        im = Image.new("L", (96, 96), 0)
        ImageDraw.Draw(im).text((8, 8), ch, font=fnt, fill=255)
        v = np.array_equal(np.asarray(im), np.asarray(ref))
        _GLYPH_MISS[key] = v
    return v


def safe_font(s, font):
    """数据标签常混排中文与等宽数字：若所选字体缺字形，自动回退到含 CJK 的字体。

    这样 overlays/scenes 里即使误把中文传给 F_MONO，也不会渲染成豆腐块。
    """
    if font == F_MONO and _has_cjk(s):
        return F_SANS_R
    if _has_cjk(s):
        for ch in s:
            if "\u4e00" <= ch <= "\u9fff" and _glyph_missing(font, ch):
                return F_SANS_R
    return font


def audit_glyphs(text, fonts=None):
    """字形自检：返回 (font, char) 缺失清单；正常应为空。

    预览脚本会扫描 scenes_pil.py / overlays.py 里出现的全部中文，
    确认负责排版的四种 CJK 字体都覆盖，避免再出现豆腐块。
    """
    fonts = fonts or (F_SANS, F_SANS_R, F_SERIF, F_SERIF_R)
    miss = set()
    for font in fonts:
        for ch in sorted(set(text)):
            if "\u4e00" <= ch <= "\u9fff" and _glyph_missing(font, ch):
                miss.add((os.path.basename(font), ch))
    return sorted(miss)


def font_covers(s, font):
    """供预览自检：字体是否覆盖字符串内所有中文。"""
    return all(not ("\u4e00" <= ch <= "\u9fff") or not _glyph_missing(font, ch)
               for ch in s)


def text_tex(s, size, color=BONE, font=F_SERIF, stroke=0, stroke_color=(0, 0, 0),
             track=0.0, alpha=255):
    """渲染一段文字为 RGBA（带字距 track px）。缓存。"""
    font = safe_font(s, font)
    key = ("t", s, size, tuple(color), font, stroke, tuple(stroke_color), round(track, 2), alpha)
    im = _TEX.get(key)
    if im is not None:
        return im
    fnt = _font(font, size)
    d = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
    if track == 0:
        box = d.textbbox((0, 0), s, font=fnt, stroke_width=stroke)
        tw, th = box[2] - box[0], box[3] - box[1]
        pad = stroke + int(size * 0.18)
        im = Image.new("RGBA", (tw + 2 * pad, th + 2 * pad), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((pad - box[0], pad - box[1]), s, font=fnt,
                                fill=tuple(color) + (alpha,), stroke_width=stroke,
                                stroke_fill=tuple(stroke_color) + (alpha,))
    else:
        widths = []
        for ch in s:
            bb = d.textbbox((0, 0), ch, font=fnt)
            widths.append(max(1, bb[2] - bb[0]))
        tw = int(sum(widths) + track * max(0, len(s) - 1))
        asc, desc = fnt.getmetrics()
        th = asc + desc
        pad = stroke + int(size * 0.18)
        im = Image.new("RGBA", (tw + 2 * pad, th + 2 * pad), (0, 0, 0, 0))
        dd = ImageDraw.Draw(im)
        x = pad
        for ch, w in zip(s, widths):
            dd.text((x, pad), ch, font=fnt, fill=tuple(color) + (alpha,),
                    stroke_width=stroke, stroke_fill=tuple(stroke_color) + (alpha,))
            x += w + track
    _TEX[key] = im
    return im


def text_size(s, size, font=F_SERIF, stroke=0, track=0.0):
    im = text_tex(s, size, BONE, font, stroke, track=track)
    return im.size


_ANCHOR = {"mm": (0.5, 0.5), "lm": (0.0, 0.5), "rm": (1.0, 0.5),
           "mt": (0.5, 0.0), "mb": (0.5, 1.0), "lt": (0.0, 0.0),
           "rt": (1.0, 0.0), "lb": (0.0, 1.0), "rb": (1.0, 1.0)}


def draw_text(rgb, s, xy, size, color=BONE, font=F_SERIF, anchor="mm", alpha=1.0,
              stroke=0, stroke_color=(0, 0, 0), track=0.0, glow=0.0,
              glow_color=None, glow_strength=0.55, rotate=0.0, scale=1.0):
    """在 float32 RGB (0..1) 画布上叠文字（RGBA 贴图，带可选柔光）。"""
    if alpha <= 0.002:
        return rgb
    tex = text_tex(s, size, color, font, stroke, stroke_color, track)
    if scale != 1.0:
        nw, nh = max(1, int(tex.width * scale)), max(1, int(tex.height * scale))
        tex = tex.resize((nw, nh), Image.BILINEAR)
    if rotate:
        tex = tex.rotate(rotate, resample=Image.BICUBIC, expand=True)
    ax, ay = _ANCHOR.get(anchor, (0.5, 0.5))
    px = int(round(xy[0] - ax * tex.width))
    py = int(round(xy[1] - ay * tex.height))
    if glow > 0.3:
        gm = tex.getchannel("A").resize((max(1, tex.width // 2), max(1, tex.height // 2)),
                                        Image.BILINEAR)
        gm = gm.filter(ImageFilter.GaussianBlur(max(0.8, glow / 3.0)))
        gm = gm.resize(tex.size, Image.BILINEAR)
        ga = np.asarray(gm, dtype=np.float32) * (glow_strength / 255.0)
        arr = np.asarray(tex, dtype=np.float32) / 255.0
        gcol = np.array(glow_color or color, dtype=np.float32) / 255.0
        x0, y0 = max(0, px), max(0, py)
        x1, y1 = min(W, px + tex.width), min(H, py + tex.height)
        if x1 > x0 and y1 > y0:
            sub = rgb[y0:y1, x0:x1]
            gsub = ga[y0 - py:y1 - py, x0 - px:x1 - px]
            gsub = (gsub * alpha)[..., None]
            sub[:] = sub * (1 - gsub) + gcol * gsub
    arr = np.asarray(tex, dtype=np.float32) / 255.0
    a = (arr[..., 3] * alpha)[..., None]
    rgb_ch = arr[..., :3]
    x0, y0 = max(0, px), max(0, py)
    x1, y1 = min(W, px + tex.width), min(H, py + tex.height)
    if x1 <= x0 or y1 <= y0:
        return rgb
    sub = rgb[y0:y1, x0:x1]
    asub = a[y0 - py:y1 - py, x0 - px:x1 - px]
    csub = rgb_ch[y0 - py:y1 - py, x0 - px:x1 - px]
    sub[:] = sub * (1 - asub) + csub * asub
    return rgb


# ---------------------------------------------------------------- painter
class Painter:
    """RGB 画布 + 按颜色累积的矢量笔画（cv2 AA），flush 时统一上色+柔光。

    stroke 参数：
      pts     (N,2) 屏幕坐标
      color   颜色（key）
      width   线宽（px）
      alpha   不透明度 0..1
      glow    柔光辉光半径（px，0 关闭）
      glow_a  辉光强度
    先调若干 stroke/dot/poly，再 flush()。多次 flush 会清空累积。
    """

    def __init__(self, base=None):
        if base is None:
            self.rgb = np.zeros((H, W, 3), np.float32)
        else:
            self.rgb = np.ascontiguousarray(base, dtype=np.float32)
        self._masks = {}
        self._glows = {}

    # ---- accumulate
    def _m(self, color):
        m = self._masks.get(color)
        if m is None:
            m = np.zeros((H, W), np.uint8)
            self._masks[color] = m
        return m

    def stroke(self, pts, color, width=2, alpha=1.0, glow=0, glow_a=0.6, closed=False):
        if alpha <= 0.004:
            return self
        arr = np.asarray(pts, dtype=np.float32).reshape(-1, 2)
        if len(arr) < 2:
            return self
        if len(arr) > 900:
            arr = arr[:: max(1, len(arr) // 900)]
        pa = np.round(arr).astype(np.int32)
        a = int(255 * clamp(alpha))
        cv2.polylines(self._m(color), [pa], closed, a, max(1, int(round(width))), cv2.LINE_AA)
        if glow > 0.5:
            rel = (color, round(float(glow), 1))
            g = self._glows.get(rel)
            if g is None:
                g = np.zeros((H // 4, W // 4), np.uint8)
                self._glows[rel] = g
            ga = np.round(arr / 4.0).astype(np.int32)
            cv2.polylines(g, [ga], closed, int(255 * clamp(alpha * glow_a)),
                          max(1, int(round(width / 4.0))), cv2.LINE_AA)
        return self

    def dot(self, xy, r=4, color=BONE, alpha=1.0, glow=0, glow_a=0.7):
        if alpha <= 0.004:
            return self
        a = int(255 * clamp(alpha))
        cv2.circle(self._m(color), (int(round(xy[0])), int(round(xy[1]))),
                   max(1, int(round(r))), a, -1, cv2.LINE_AA)
        if glow > 0.5:
            rel = (color, round(float(glow), 1))
            g = self._glows.get(rel)
            if g is None:
                g = np.zeros((H // 4, W // 4), np.uint8)
                self._glows[rel] = g
            cv2.circle(g, (int(round(xy[0] / 4)), int(round(xy[1] / 4))),
                       max(1, int(round(r / 4))), int(255 * clamp(alpha * glow_a)), -1, cv2.LINE_AA)
        return self

    def rect(self, xy0, xy1, color, alpha=1.0, width=2, glow=0, glow_a=0.5):
        pts = [(xy0[0], xy0[1]), (xy1[0], xy0[1]), (xy1[0], xy1[1]), (xy0[0], xy1[1])]
        return self.stroke(pts, color, width, alpha, glow, glow_a, closed=True)

    def fill_poly(self, pts, color, alpha=1.0):
        if alpha <= 0.004:
            return self
        arr = np.asarray(pts, dtype=np.float32).reshape(-1, 2)
        cv2.fillPoly(self._m(color), [np.round(arr).astype(np.int32)],
                     int(255 * clamp(alpha)), cv2.LINE_AA)
        return self

    def fill_circle(self, xy, r, color, alpha=1.0):
        if alpha <= 0.004:
            return self
        cv2.circle(self._m(color), (int(round(xy[0])), int(round(xy[1]))),
                   max(1, int(round(r))), int(255 * clamp(alpha)), -1, cv2.LINE_AA)
        return self

    def fill_rect(self, xy0, xy1, color, alpha=1.0):
        if alpha <= 0.004:
            return self
        x0 = int(round(min(xy0[0], xy1[0]))); y0 = int(round(min(xy0[1], xy1[1])))
        x1 = int(round(max(xy0[0], xy1[0]))); y1 = int(round(max(xy0[1], xy1[1])))
        cv2.rectangle(self._m(color), (x0, y0), (x1, y1), int(255 * clamp(alpha)), -1,
                      cv2.LINE_AA)
        return self

    def dark_circle(self, xy, r, factor=0.42, feather=0.22):
        """压暗圆形底（立即写入 rgb，避免 mask 合成顺序把部件环线盖掉）。"""
        x, y = int(round(xy[0])), int(round(xy[1]))
        r = max(2, int(round(r)))
        x0, x1 = max(0, x - r), min(W, x + r)
        y0, y1 = max(0, y - r), min(H, y + r)
        if x1 <= x0 or y1 <= y0:
            return self
        yy, xx = np.ogrid[y0 - y:y1 - y, x0 - x:x1 - x]
        d = np.sqrt((xx ** 2 + yy ** 2).astype(np.float32)) / float(r)
        m = np.clip((1.0 + feather - d) / feather, 0.0, 1.0)[..., None]
        sub = self.rgb[y0:y1, x0:x1]
        sub *= (1.0 - m * (1.0 - factor))
        return self

    def halo(self, xy, r, color, alpha=0.5):
        """圆形柔光（可直接叠加到画布）。"""
        a = clamp(alpha)
        x, y = int(round(xy[0])), int(round(xy[1]))
        r = max(2, int(round(r)))
        x0, x1 = max(0, x - r), min(W, x + r)
        y0, y1 = max(0, y - r), min(H, y + r)
        if x1 <= x0 or y1 <= y0:
            return self
        ph, pw = y1 - y0, x1 - x0
        sh_, sw_ = max(2, ph // 4), max(2, pw // 4)
        yy, xx = np.ogrid[0:sh_, 0:sw_]
        yy = (yy + 0.5) * (ph / sh_) - (y - y0)
        xx = (xx + 0.5) * (pw / sw_) - (x - x0)
        d2 = (xx ** 2 + yy ** 2) / float(r * r)
        g = np.exp(-d2 * 2.4) * a
        g = cv2.resize(g.astype(np.float32), (pw, ph), interpolation=cv2.INTER_LINEAR)
        col = np.array(color, np.float32) / 255.0
        sub = self.rgb[y0:y1, x0:x1]
        sub[:] = sub * (1 - g[..., None]) + col * g[..., None]
        return self

    def flush(self, glow_strength=1.0):
        """把累积的按颜色 mask 合成到画布。

        性能：每个颜色只在其包围盒内做混合（图形普遍只占画面小部分），
        辉光统一在 1/4 分辨率累积后一次性上采样，避免全画幅逐色运算。
        """
        if not self._masks and not self._glows:
            return self
        # ---- 辉光：1/4 分辨率累积 → 一次上采样
        if self._glows:
            gh, gw = H // 4, W // 4
            grgb = np.zeros((gh, gw, 3), np.float32)
            ga = np.zeros((gh, gw), np.float32)
            for (color, _r), g in self._glows.items():
                if not g.any():
                    continue
                gb = cv2.GaussianBlur(g, (0, 0), max(0.9, _r / 6.0)).astype(np.float32) / 255.0
                gb *= glow_strength
                col = np.array(color, np.float32) / 255.0
                grgb = col * gb[..., None] + grgb * (1 - gb[..., None])
                ga = gb + ga * (1 - gb)
            up_rgb = cv2.resize(grgb, (W, H), interpolation=cv2.INTER_LINEAR)
            up_a = cv2.resize(ga, (W, H), interpolation=cv2.INTER_LINEAR)
            a = up_a[..., None]
            self.rgb *= (1 - a)
            self.rgb += up_rgb * a
        # ---- 实色：逐色包围盒内 alpha 混合（后插入的颜色覆盖先插入的）
        for color, m in self._masks.items():
            x, y, w, h = cv2.boundingRect(m)
            if w <= 0 or h <= 0:
                continue
            msub = m[y:y + h, x:x + w].astype(np.float32) * (1.0 / 255.0)
            if msub.max() <= 0.004:
                continue
            sub = self.rgb[y:y + h, x:x + w]
            col = np.array(color, np.float32) * (1.0 / 255.0)
            a3 = msub[..., None]
            sub *= (1 - a3)
            sub += col * a3
        self._masks.clear()
        self._glows.clear()
        return self

    # ---- post
    def add(self, arr, gain=1.0, alpha=None):
        if alpha is None:
            self.rgb += np.asarray(arr, np.float32) * gain
        else:
            a = np.asarray(alpha, np.float32)[..., None]
            self.rgb = self.rgb * (1 - a) + np.asarray(arr, np.float32) * a
        return self

    def clip(self):
        np.clip(self.rgb, 0.0, 1.0, out=self.rgb)
        return self

    def bloom(self, threshold=0.62, strength=0.55, radius=1.0):
        small = cv2.resize(self.rgb, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
        lum = small.max(axis=2)
        bright = np.clip((lum - threshold) / (1 - threshold), 0, 1) ** 1.4
        b = small * bright[..., None]
        b = cv2.GaussianBlur(b, (0, 0), 5.0 * radius)
        b = cv2.resize(b, (W, H), interpolation=cv2.INTER_LINEAR)
        self.rgb += b * strength
        return self

    def vignette(self, strength=0.42):
        vig = _vignette()
        self.rgb *= (1 - strength * vig)[..., None]
        return self

    def grain(self, seed=0, amt=0.022):
        rng = np.random.default_rng(seed)
        n = rng.standard_normal((H, W, 1)).astype(np.float32) * amt
        self.rgb += n
        return self

    def to_image(self):
        self.clip()
        return Image.fromarray((self.rgb * 255).astype(np.uint8))


_VIG = None


def _vignette():
    global _VIG
    if _VIG is None:
        yy, xx = np.ogrid[:H, :W]
        nx = (xx - W / 2) / (W / 2)
        ny = (yy - H / 2) / (H / 2)
        d = np.sqrt(nx ** 2 + ny ** 2) / 1.414
        _VIG = np.clip(d ** 2.4, 0, 1).astype(np.float32)
    return _VIG


# ---------------------------------------------------------------- backgrounds
_IMGCACHE = {}


def load_plate(path, max_w=3840):
    """加载并缓存底片（一次缩放到 3840 宽，供慢推/漂移用）。"""
    key = (path, max_w)
    im = _IMGCACHE.get(key)
    if im is None:
        im = Image.open(path).convert("RGB")
        if im.width > max_w:
            im = im.resize((max_w, int(round(im.height * max_w / im.width))), Image.LANCZOS)
        arr = np.asarray(im, dtype=np.float32) / 255.0
        _IMGCACHE[key] = arr
        im = arr
    return im


def plate_frame(path, zoom=1.0, cx=0.5, cy=0.5, dark=0.42, tint=(0.72, 0.86, 1.0),
                blur=0.0, sat=0.9):
    """从底片裁出 1920×1080 帧：zoom≥1，cx/cy 为 0..1 取景中心。返回 float32 RGB。"""
    src = load_plate(path)
    sh, sw = src.shape[:2]
    zoom = max(1.0, zoom)
    cw, ch = int(sw / zoom), int(sh / zoom)
    x0 = int(np.clip(cx * sw - cw / 2, 0, sw - cw))
    y0 = int(np.clip(cy * sh - ch / 2, 0, sh - ch))
    crop = src[y0:y0 + ch, x0:x0 + cw]
    interp = cv2.INTER_AREA if crop.shape[0] > H else cv2.INTER_LINEAR
    out = cv2.resize(crop, (W, H), interpolation=interp)
    if blur > 0.3:
        out = cv2.GaussianBlur(out, (0, 0), blur)
    out = out * np.array(tint, np.float32)[None, None, :]
    out = out * (1 - dark) + np.array(INK, np.float32) / 255.0 * dark
    gray = cv2.cvtColor(out, cv2.COLOR_RGB2GRAY)[..., None]
    out = out * sat + gray * (1 - sat)
    return out


def video_plate_frame(path, zoom=1.0, cx=0.5, cy=0.5, dark=0.42, tint=(0.72, 0.86, 1.0),
                      blur=0.0, sat=0.9, t=0.0):
    """视频底片取帧（场景内用 ffmpeg 预处理，这里仅供预览/兜底）。"""
    return plate_frame(path, zoom, cx, cy, dark, tint, blur, sat)


def invert_plate(base):
    """数据层底替：把底片变成深色工程纹理（用于纯数据镜头）。"""
    g = base.mean(axis=2, keepdims=True)
    out = np.array(INK, np.float32) / 255.0 * 0.92 + (g ** 1.3) * 0.10
    out = np.repeat(out, 3, axis=2)
    return out


# ---------------------------------------------------------------- misc primitives
def dashed(pts, dash=10, gap=8):
    """把折线切成虚线点列。"""
    pts = np.asarray(pts, np.float64)
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    total = seg.sum()
    if total <= 0:
        return pts
    out = []
    d = 0.0
    i = 0
    acc = 0.0
    step = dash + gap
    dcur = 0.0
    while dcur < total:
        target = dcur + dash
        # 采样沿折线
        ts = np.concatenate([[0], np.cumsum(seg)])
        k = np.searchsorted(ts, dcur)
        k = min(max(1, k), len(pts) - 1)
        frac0 = (dcur - ts[k - 1]) / max(1e-9, seg[k - 1])
        p0 = pts[k - 1] + frac0 * (pts[k] - pts[k - 1])
        k2 = min(max(1, np.searchsorted(ts, target)), len(pts) - 1)
        frac1 = (target - ts[k2 - 1]) / max(1e-9, seg[k2 - 1])
        p1 = pts[k2 - 1] + frac1 * (pts[k2] - pts[k2 - 1])
        out.append([p0, p1])
        dcur += step
    return out


def glow_curve(pts, color, width=2.4, alpha=1.0, glow=14, glow_a=0.65, dash=0, gap=0):
    """返回一段可直接交给 Painter.stroke 的点列；dash>0 时返回多段。"""
    pts = np.asarray(pts, np.float32)
    if dash and len(pts) > 2:
        return None  # 由调用方使用 segments()
    return pts


def curve_points(fn, x0, x1, n=160):
    xs = np.linspace(x0, x1, n)
    ys = fn(xs)
    return np.stack([xs, ys], axis=1)


class OverlayPainter:
    """RGBA 透明层画布（叠加在实拍 B-roll 上的数据层 / 花字）。

    性能：等所有 stroke/dot/bar/text 累积到按颜色的 uint8 mask，image() 时一次性
    合成（每帧只做少量全画幅 float 运算），比逐图元合成快 5—10 倍。
    """

    def __init__(self):
        self._core = {}      # color -> uint8 (H,W)
        self._glow = {}      # (color, radius) -> uint8 (H//4,W//4)
        self._halos = []     # (color, y0,y1,x0,x1, g float32)
        self._texts = []     # (rgba uint8 array, px, py, alpha)

    def _m(self, color):
        m = self._core.get(color)
        if m is None:
            m = np.zeros((H, W), np.uint8)
            self._core[color] = m
        return m

    def _g(self, color, radius):
        key = (color, max(1.0, round(float(radius), 1)))
        g = self._glow.get(key)
        if g is None:
            g = np.zeros((H // 4, W // 4), np.uint8)
            self._glow[key] = g
        return g

    def stroke(self, pts, color, width=2, alpha=1.0, glow=0, glow_a=0.65, closed=False):
        if alpha <= 0.004:
            return self
        arr = np.asarray(pts, np.float32).reshape(-1, 2)
        if len(arr) < 2:
            return self
        if len(arr) > 900:
            arr = arr[:: max(1, len(arr) // 900)]
        pa = np.round(arr).astype(np.int32)
        a = int(255 * clamp(alpha))
        cv2.polylines(self._m(color), [pa], closed, a, max(1, int(round(width))), cv2.LINE_AA)
        if glow > 0.5:
            ga = np.round(arr / 4.0).astype(np.int32)
            cv2.polylines(self._g(color, glow), [ga], closed,
                          int(255 * clamp(alpha * glow_a)),
                          max(1, int(round(width / 4.0))), cv2.LINE_AA)
        return self

    def dot(self, xy, r=4, color=BONE, alpha=1.0, glow=0, glow_a=0.8):
        if alpha <= 0.004:
            return self
        a = int(255 * clamp(alpha))
        cv2.circle(self._m(color), (int(round(xy[0])), int(round(xy[1]))),
                   max(1, int(round(r))), a, -1, cv2.LINE_AA)
        if glow > 0.5:
            cv2.circle(self._g(color, glow), (int(round(xy[0] / 4)), int(round(xy[1] / 4))),
                       max(1, int(round(r / 4))), int(255 * clamp(alpha * glow_a)), -1, cv2.LINE_AA)
        return self

    def rect(self, xy0, xy1, color, alpha=1.0, width=2, glow=0, glow_a=0.5):
        pts = [(xy0[0], xy0[1]), (xy1[0], xy0[1]), (xy1[0], xy1[1]), (xy0[0], xy1[1])]
        return self.stroke(pts, color, width, alpha, glow, glow_a, closed=True)

    def bar(self, xy0, xy1, color, alpha=1.0):
        if alpha <= 0.004:
            return self
        x0 = max(0, int(xy0[0])); y0 = max(0, int(xy0[1]))
        x1 = min(W, int(xy1[0])); y1 = min(H, int(xy1[1]))
        if x1 <= x0 or y1 <= y0:
            return self
        cv2.rectangle(self._m(color), (x0, y0), (x1, y1), int(255 * clamp(alpha)), -1)
        return self

    def glow(self, xy, r=120, color=TEAL, alpha=0.4):
        x, y = int(xy[0]), int(xy[1])
        x0, x1 = max(0, x - r), min(W, x + r)
        y0, y1 = max(0, y - r), min(H, y + r)
        if x1 <= x0 or y1 <= y0:
            return self
        yy, xx = np.ogrid[y0 - y:y1 - y, x0 - x:x1 - x]
        g = np.exp(-((xx ** 2 + yy ** 2) / (r * r)) * 2.2) * clamp(alpha)
        self._halos.append((tuple(color), y0, y1, x0, x1, g.astype(np.float32)))
        return self

    def text(self, s, xy, size, color=BONE, font=F_SERIF, anchor="mm", alpha=1.0,
             stroke=0, stroke_color=(0, 0, 0), track=0.0, glow=0.0, glow_strength=0.55):
        if alpha <= 0.002:
            return self
        tex = text_tex(s, size, color, font, stroke, stroke_color, track)
        ax, ay = _ANCHOR.get(anchor, (0.5, 0.5))
        px = int(round(xy[0] - ax * tex.width))
        py = int(round(xy[1] - ay * tex.height))
        arr = np.asarray(tex, np.uint8).copy()
        if glow > 0.3:
            gm = tex.getchannel("A").resize((max(1, tex.width // 2), max(1, tex.height // 2)),
                                            Image.BILINEAR)
            gm = gm.filter(ImageFilter.GaussianBlur(max(0.8, glow / 3.0)))
            gm = gm.resize(tex.size, Image.BILINEAR)
            ga = (np.asarray(gm, np.float32) / 255.0 * glow_strength * alpha)
            # 直接在 rgb 里先叠 glow：记录为额外的 text 层
            gcol = np.array(color, np.float32)
            glow_rgba = np.zeros((tex.height, tex.width, 4), np.uint8)
            glow_rgba[..., :3] = gcol.astype(np.uint8)
            glow_rgba[..., 3] = np.clip(ga * 255, 0, 255).astype(np.uint8)
            self._texts.append((glow_rgba, px, py, 1.0))
        self._texts.append((arr, px, py, clamp(alpha)))
        return self

    def image(self):
        rgb = np.zeros((H, W, 3), np.float32)
        a = np.zeros((H, W), np.float32)
        glow_by_color = {}
        for (color, _r), g in self._glow.items():
            if not g.any():
                continue
            gb = cv2.GaussianBlur(g, (0, 0), max(0.9, _r / 6.0))
            gu = cv2.resize(gb, (W, H), interpolation=cv2.INTER_LINEAR)
            m = gu.astype(np.float32) / 255.0
            prev = glow_by_color.get(color)
            glow_by_color[color] = m if prev is None else np.maximum(prev, m)
        for color, m8 in self._core.items():
            m = m8.astype(np.float32) / 255.0
            g = glow_by_color.get(color)
            if g is not None:
                m = np.maximum(m, g * 0.92)
            col = np.array(color, np.float32) / 255.0
            rgb = col * m[..., None] + rgb * (1 - m[..., None])
            a = m + a * (1 - m)
        for color, y0, y1, x0, x1, g in self._halos:
            m = np.zeros((H, W), np.float32)
            m[y0:y1, x0:x1] = g
            col = np.array(color, np.float32) / 255.0
            rgb = col * m[..., None] + rgb * (1 - m[..., None])
            a = m + a * (1 - m)
        for patch, px, py, alpha in self._texts:
            ph, pw = patch.shape[:2]
            x0, y0 = max(0, px), max(0, py)
            x1, y1 = min(W, px + pw), min(H, py + ph)
            if x1 <= x0 or y1 <= y0:
                continue
            sub = patch[y0 - py:y1 - py, x0 - px:x1 - px]
            aa = sub[..., 3].astype(np.float32) / 255.0 * alpha
            cc = sub[..., :3].astype(np.float32) / 255.0
            rgb_sub = rgb[y0:y1, x0:x1]
            a_sub = a[y0:y1, x0:x1]
            rgb_sub[:] = cc * aa[..., None] + rgb_sub * (1 - aa[..., None])
            a_sub[:] = aa + a_sub * (1 - aa)
        rgba = np.concatenate([np.clip(rgb, 0, 1), np.clip(a, 0, 1)[..., None]], axis=2)
        return Image.fromarray((rgba * 255).astype(np.uint8), "RGBA")


# ---------------------------------------------------------------- cheap film looks
def color_grade(rgb, contrast=1.05, sat=1.04, lift=(0.0, 0.006, 0.018)):
    arr = np.clip(rgb, 0, 1)
    arr = (arr - 0.5) * contrast + 0.5
    gray = arr.mean(axis=2, keepdims=True)
    arr = gray + (arr - gray) * sat
    arr += np.array(lift, np.float32)[None, None, :]
    return np.clip(arr, 0, 1)


def soft_light_top(rgb, strength=0.10, color=(1.0, 0.86, 0.66), cy=0.12):
    yy = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    g = np.exp(-((yy - cy) ** 2) / (2 * 0.22 ** 2)) * strength
    return np.clip(rgb + np.array(color, np.float32)[None, None, :] * g, 0, 1)
