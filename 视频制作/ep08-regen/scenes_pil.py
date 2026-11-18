#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 08 期全画幅程序化场景（代码层英雄镜头，44 个代码镜 + 混合镜降级）。

签名：`def scene_xxx(t, dur, sh=None) -> PIL.Image`；t=镜头内局部时间，dur=镜头时长。
原则：一屏一个第一视觉重点；运动必须表达变化（方向反转/逐站高亮/数字落定/曲线对比）；
所有硬数字来自 facts.json（锁定稿 §7.2 F01–F18），场景内不手写数字。
内容区限制在 2.35:1 安全区 y∈[132,948]。
"""
import json
import math
import os

import numpy as np
from PIL import Image

import ep08viz as v

ROOT = os.path.dirname(os.path.abspath(__file__))
W, H, FPS = v.W, v.H, v.FPS
SAFE_T, SAFE_B = v.SAFE_T, v.SAFE_B

_FACTS = None


def facts():
    global _FACTS
    if _FACTS is None:
        try:
            _FACTS = json.load(open(os.path.join(ROOT, "facts.json"), encoding="utf-8"))
        except Exception:
            _FACTS = {}
    return _FACTS


def F(path, default=None):
    cur = facts()
    for k in path.split("."):
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            return default
    return cur


def ramp(t, t0, t1):
    return 1.0 if t1 <= t0 and t >= t1 else (0.0 if t1 <= t0 else v.smoothstep(t0, t1, t))


def win(t, t0, t1, fin=0.28, fout=0.28):
    return v.window(t, t0, t1, fin, fout)


def txt(p, s, xy, size, color=v.BONE, font=v.F_SANS, anchor="mm", alpha=1.0,
        track=1.0, glow=0.0):
    v.draw_text(p.rgb, s, xy, size, color, font, anchor, alpha, track=track, glow=glow)


def mono(p, s, xy, size=24, color=v.MUTED, alpha=1.0, anchor="mm", track=0.6):
    v.draw_text(p.rgb, s, xy, size, color, v.F_MONO, anchor, alpha, track=track)


def finish(p, vig=0.30, grain=0.016):
    p.vignette(vig)
    p.grain(seed=20261116, amt=grain)
    return p.to_image()


def bg(tint=v.TEAL, strength=0.11, cx=0.5, cy=0.48, grid=True):
    return v.bg_frame(tint=tint, strength=strength, cx=cx, cy=cy, grid=grid)


def big_number(p, value, xy, size=150, color=v.TEAL, alpha=1.0, unit="", unit_size=34):
    txt(p, value, xy, size, color, v.F_MONO, "mm", alpha, track=2, glow=12 * alpha)
    if unit:
        txt(p, unit, (xy[0], xy[1] + size * 0.62), unit_size, v.MUTED, v.F_SANS_R, "mm",
            alpha * 0.85, track=2)


def axes(p, x0, y0, x1, y1, alpha=1.0, glow=0.0):
    p.stroke([(x0, y0), (x1, y0)], v.LINE, 1.6, alpha * 0.9)
    p.stroke([(x0, y0), (x0, y1)], v.LINE, 1.6, alpha * 0.9)
    for k in range(5):
        x = v.lerp(x0, x1, k / 4.0)
        p.stroke([(x, y0), (x, y0 + 7)], v.DIM, 1.1, alpha * 0.6)


def curve_poly(fn, x0, x1, n=140):
    xs = np.linspace(x0, x1, n)
    return np.stack([xs, fn(xs)], 1).astype(np.float32)


# ================================================================ C2 可逆能量通道（母题）
# 视觉顺序（从左到右）：轮端 → 电机 → 逆变器 → 电池；回收=右→左（青），驱动=左→右（琥珀）。
CH_X = [300.0, 790.0, 1260.0, 1700.0]
CH_Y = 520.0
_CH_HALF = {"wheel": 136.0, "motor": 128.0, "inverter": 100.0, "battery": 126.0}
_CH_CN = {"wheel": "轮端", "motor": "电机", "inverter": "逆变器", "battery": "电池"}
_CH_EN = {"wheel": "WHEEL", "motor": "MOTOR", "inverter": "INVERTER", "battery": "BATTERY"}


def chain_pos():
    return dict(zip(("wheel", "motor", "inverter", "battery"), CH_X))


def chain_segs(y=CH_Y):
    segs = []
    keys = ("wheel", "motor", "inverter", "battery")
    for i in range(3):
        a, b = keys[i], keys[i + 1]
        x0 = CH_X[i] + _CH_HALF[a]
        x1 = CH_X[i + 1] - _CH_HALF[b]
        segs.append(np.array([[x0, y], [x1, y]], np.float32))
    return segs


def draw_chain(p, t=0.0, direction=1, flow=1.0, active=None, y=CH_Y, alpha=1.0,
               soc=0.62, spin=None, turn=0.0, labels=True, eff=None, stage=2.0,
               heat=0.0, dim=0.0):
    """方向契约（全片统一，验收项）：
    布局：轮端(左) → 电机 → 逆变器 → 电池(右)。
    direction=+1 回收/充电：轮端→电机→逆变器→电池，能量点/箭头 **左→右**（青色）；
    direction=-1 驱动/放电：电池→逆变器→电机→轮端，能量点/箭头 **右→左**（琥珀）。
    """
    a = alpha
    col = v.TEAL if direction > 0 else v.AMBER
    spin = (t * 3.4 if spin is None else spin)
    # 通道底板
    for seg in chain_segs(y):
        p.stroke(seg, v.LINE, 7.0, a * 0.42)
        p.stroke(seg, v.LINE, 11.0, a * 0.14)
    # 四站
    v.draw_wheel(p, CH_X[0], y, 136.0, spin=spin * 57.3, alpha=a,
                 torque=(-0.7 if direction > 0 else 0.7))
    v.draw_motor(p, CH_X[1], y, 128.0, spin=spin * 57.3, alpha=a,
                 active=("rotor" if direction > 0 else "stator"),
                 flux=0.9 if direction > 0 else 0.15)
    v.draw_inverter(p, CH_X[2], y, 200.0, 190.0,
                    active=("phase" if direction > 0 else "dc"), alpha=a,
                    live=0.6 + 0.3 * math.sin(t * 5) ** 2)
    v.draw_battery_pack(p, CH_X[3], y, 252.0, 212.0, soc=soc, temp=0.5, alpha=a,
                        fill=direction, glow=0.0)
    # 主方向箭头（通道中央，物理方向一眼可读）
    for seg in chain_segs(y):
        mid = seg.mean(axis=0)
        sgn = 1 if direction > 0 else -1
        pts = [(mid[0] - 15 * sgn, y - 15), (mid[0] + 15 * sgn, y),
               (mid[0] - 15 * sgn, y + 15)]
        p.stroke(np.array(pts, np.float32), col, 3.4, a * 0.95, 14, 0.6)
    # 流动粒子
    if flow > 0.001:
        for seg in chain_segs(y):
            v.flow_dots(p, seg, t, speed=330, direction=direction, color=col,
                        n=5, alpha=a * flow, r=3.0, glow=12)
    # 损耗支路
    if heat > 0.02:
        for key, x in (("motor", CH_X[1]), ("inverter", CH_X[2]), ("battery", CH_X[3])):
            v.loss_tap(p, (x, y + 116), alpha=a * heat, length=46)
    # 高亮环
    for key, i in (("wheel", 0), ("motor", 1), ("inverter", 2), ("battery", 3)):
        if active == key:
            if key in ("wheel", "motor"):
                r = _CH_HALF[key] + 12
                p.stroke([v.polar(CH_X[i], y, r, d) for d in range(0, 361, 4)], v.TEAL,
                         2.2, a * 0.85, 12, 0.6, closed=True)
            else:
                p.stroke(v._rounded_rect_pts(CH_X[i] - _CH_HALF[key] - 8, y - 106,
                                             CH_X[i] + _CH_HALF[key] + 8, y + 106, 14),
                         v.TEAL, 2.2, a * 0.85, 12, 0.6)
    if labels:
        for i, key in enumerate(("wheel", "motor", "inverter", "battery")):
            dim_a = 0.35 if dim and active not in (None, key) else 1.0
            txt(p, _CH_CN[key], (CH_X[i], y + 182), 32, v.BONE, v.F_SANS, "mm",
                a * 0.95 * dim_a, track=2)
            txt(p, _CH_EN[key], (CH_X[i], y + 212), 16, v.MUTED, v.F_MONO, "mm",
                a * 0.7 * dim_a, track=2)
    if eff:
        for key, val in eff.items():
            i = ("wheel", "motor", "inverter", "battery").index(key)
            txt(p, val, (CH_X[i], y - 150), 26, v.TEAL if direction < 0 else v.AMBER,
                v.F_MONO, "mm", a * 0.9)


# ================================================================ S1 冷开场
def scene_word_strike_motor(t, dur, sh=None):
    """S03：「永动机」草图被红笔划掉，落「能量守恒」。"""
    b = bg(v.TEAL, 0.09)
    p = v.Painter(b)
    # 草图：一个轮子 + 打叉的箭头回路
    cx, cy, R = 830.0, 520.0, 190.0
    p.stroke([v.polar(cx, cy, R, d) for d in range(0, 361, 4)], v.STEEL, 2.0, 0.55, closed=True)
    p.stroke([v.polar(cx, cy, 26, d) for d in range(0, 361, 8)], v.STEEL, 1.6, 0.5, closed=True)
    for k in range(6):
        a0 = k * 60
        p.stroke([v.polar(cx, cy, 30, a0), v.polar(cx, cy, R - 16, a0)], v.STEEL, 1.2, 0.35)
    # 环形箭头（草稿）
    pts = [v.polar(cx, cy, R + 62, d) for d in range(-60, 250, 5)]
    p.stroke(np.array(pts, np.float32), v.AMBER, 2.0, 0.4, 8, 0.4)
    p.flush()
    txt(p, "永动机", (cx, cy - 300), 64, v.BONE, v.F_SERIF, "mm", 0.85, track=6)
    txt(p, "≈ 无中生有", (cx, cy + 300), 26, v.MUTED, v.F_SANS_R, "mm", 0.6, track=3)
    # 红笔划掉
    s = ramp(t, dur * 0.18, dur * 0.62)
    x0, x1 = 520.0, 1370.0
    p.stroke([(x0, cy - 150), (x0 + (x1 - x0) * s, cy + 150 - 300 * 0)], v.EMBER, 5.0,
             0.9 * min(1, s * 3), 16, 0.5)
    p.flush()
    # 落字
    a = ramp(t, dur * 0.55, dur * 0.9)
    txt(p, "能量守恒", (1420, 760), 56, v.TEAL, v.F_SANS, "mm", a, track=5, glow=14 * a)
    txt(p, "这条规矩，回收也绕不过", (1420, 812), 24, v.MUTED, v.F_SANS_R, "mm", a * 0.9, track=2)
    return finish(p)


def scene_chain_lightup(t, dur, sh=None):
    """S04：母题第一次亮起：轮端→电机→逆变器→电池，逐站点亮。"""
    b = bg(v.TEAL, 0.12)
    p = v.Painter(b)
    order = ["wheel", "motor", "inverter", "battery"]
    k = min(3, int(ramp(t, 0.4, dur - 0.4) * 4.0))
    active = order[k]
    lit = order[:k + 1]
    draw_chain(p, t=t, direction=1, flow=0.9, active=active, y=CH_Y, soc=0.6,
               heat=0.0, labels=False)
    # 未点亮站点压暗：用暗圆覆盖（先画后亮）
    p.flush()
    for i, key in enumerate(order):
        on = key in lit
        if not on:
            if key in ("wheel", "motor"):
                p.dark_circle((CH_X[i], CH_Y), _CH_HALF[key] + 16, factor=0.35)
            else:
                p.fill_rect((CH_X[i] - 110, CH_Y - 110), (CH_X[i] + 110, CH_Y + 110),
                            (10, 14, 18), 0.55)
    p.flush()
    # 站点标签 + 序号亮起
    for i, key in enumerate(order):
        on = key in lit
        txt(p, _CH_CN[key], (CH_X[i], CH_Y + 168), 34, v.BONE if on else v.DIM,
            v.F_SANS, "mm", 0.95 if on else 0.45, track=2)
        if on:
            txt(p, "第 %d 站" % (i + 1), (CH_X[i], CH_Y + 204), 18,
                v.TEAL if i < 3 else v.AMBER, v.F_MONO, "mm", 0.85, track=1.5)
    a = ramp(t, dur * 0.55, dur * 0.85)
    txt(p, "轮端 · 电机 · 逆变器 · 电池", (960, 236), 34, v.MUTED, v.F_SANS_R, "mm",
        a * 0.9, track=5)
    txt(p, "一条可以倒着走的能量通道", (960, 884), 34, v.BONE, v.F_SANS, "mm",
        ramp(t, dur * 0.30, dur * 0.55), track=3)
    return finish(p)


# ================================================================ S2 立判
def scene_chain_drive(t, dur, sh=None):
    """S06：驱动链：电池→逆变器→电机→轮端，能量点向前流。"""
    b = bg(v.AMBER, 0.10)
    p = v.Painter(b)
    draw_chain(p, t=t, direction=-1, flow=1.0, active=None, y=CH_Y, soc=0.64,
               labels=True, heat=0.0)
    p.flush()
    a = ramp(t, 0.3, dur * 0.5)
    txt(p, "放电 → 驱动", (960, 216), 40, v.AMBER, v.F_SANS, "mm", a, track=4, glow=10)
    txt(p, "电池放电，逆变器把直流变成三相交流，电机把电变成转动", (960, 268), 24,
        v.MUTED, v.F_SANS_R, "mm", a * 0.9, track=1.5)
    txt(p, "能量点从左向右走完四站", (960, 884), 30, v.BONE, v.F_SANS_R, "mm",
        ramp(t, dur * 0.55, dur * 0.9), track=2)
    return finish(p)


def scene_motor_swap(t, dur, sh=None):
    """S08：电机剖面：两种工作状态并排（电动 / 发电）。"""
    b = bg(v.TEAL, 0.09, cx=0.5)
    p = v.Painter(b)
    R = 190.0
    # 左：电动
    v.draw_motor(p, 470.0, 540.0, R, spin=t * 3.2 * 57.3, alpha=1.0, active="stator",
                 flux=0.1)
    # 右：发电（反向旋转 + 磁力线）
    v.draw_motor(p, 1410.0, 540.0, R, spin=-t * 3.2 * 57.3, alpha=1.0, active="rotor",
                 flux=0.95)
    p.flush()
    txt(p, "电动", (470, 800), 44, v.AMBER, v.F_SANS, "mm", 0.9, track=4)
    txt(p, "电能 → 转动", (470, 844), 24, v.MUTED, v.F_SANS_R, "mm", 0.8, track=2)
    txt(p, "发电", (1410, 800), 44, v.TEAL, v.F_SANS, "mm", 0.9, track=4)
    txt(p, "转动 → 电能", (1410, 844), 24, v.MUTED, v.F_SANS_R, "mm", 0.8, track=2)
    # 中间等号
    txt(p, "同一台", (960, 500), 30, v.BONE, v.F_SANS_R, "mm", 0.85, track=2)
    txt(p, "电机", (960, 580), 64, v.BONE, v.F_SANS, "mm", 0.9, track=4)
    txt(p, "定子线圈 / 转子 / 气隙：通电是电动机，被反拖是发电机", (960, 236), 26,
        v.MUTED, v.F_SANS_R, "mm", 0.8, track=2)
    txt(p, "电动 / 发电 同一台", (960, 884), 34, v.BONE, v.F_SANS, "mm", 0.9, track=3)
    return finish(p)


def scene_word_swap(t, dur, sh=None):
    """S09：「魔法」被擦掉，换成「可逆」。"""
    b = bg(v.TEAL, 0.08)
    p = v.Painter(b)
    p.flush()
    a = ramp(t, 0.2, 1.0)
    txt(p, "魔法", (620, 540), 130, v.BONE, v.F_SERIF, "mm", a, track=8)
    # 擦除条
    s = ramp(t, dur * 0.25, dur * 0.65)
    if s > 0:
        p.fill_rect((280, 440), (280 + 680 * s, 640), (14, 18, 22), 0.92)
        p.flush()
        # 橡皮痕
        p.stroke([(300, 560), (300 + 640 * s, 500)], v.MUTED, 3.0, 0.25 * s)
        p.flush()
    # 新词
    a2 = ramp(t, dur * 0.55, dur * 0.95)
    txt(p, "可逆", (1240, 540), 140, v.TEAL, v.F_SANS, "mm", a2, track=8, glow=20 * a2)
    txt(p, "不是魔法 · 是可逆", (960, 800), 36, v.BONE, v.F_SANS_R, "mm", a2, track=4)
    # 双向箭头
    yy = 690
    p.stroke([(720, yy), (1200, yy)], v.TEAL, 3.0, 0.6 * a2, 12, 0.5)
    p.stroke([(750, yy - 12), (720, yy), (750, yy + 12)], v.TEAL, 3.0, 0.6 * a2)
    p.stroke([(1170, yy - 12), (1200, yy), (1170, yy + 12)], v.TEAL, 3.0, 0.6 * a2)
    p.flush()
    return finish(p)


def scene_bucket_limit(t, dur, sh=None):
    """S12：一只桶：倒回去的能量只剩大半，缺口标注摩擦/热。"""
    b = bg(v.AMBER, 0.08)
    p = v.Painter(b)
    cx, cy = 900.0, 560.0
    # 桶
    bucket = np.array([[cx - 230, cy - 170], [cx + 230, cy - 170], [cx + 180, cy + 210],
                       [cx - 180, cy + 210]], np.float32)
    p.stroke(bucket, v.STEEL, 3.0, 0.85, closed=True)
    p.fill_poly(bucket, (10, 14, 18), 0.5)
    p.flush()
    # 桶内液面：从空到 70%
    fill = ramp(t, dur * 0.25, dur * 0.8) * 0.70
    y_top = v.lerp(cy + 210, cy - 150, fill)
    pts = np.array([[cx - 210, y_top], [cx + 210, y_top], [cx + 175, cy + 205],
                    [cx - 175, cy + 205]], np.float32)
    p.fill_poly(pts, v.TEAL, 0.30)
    p.stroke([pts[0], pts[1]], v.TEAL_P, 2.4, 0.9, 12, 0.5)
    p.flush()
    # 缺口标注
    a = ramp(t, dur * 0.55, dur * 0.9)
    p.stroke([(cx + 240, cy - 170), (cx + 380, cy - 270)], v.EMBER, 2.0, 0.8 * a)
    txt(p, "倒回去的只剩大半", (cx, cy - 300), 34, v.BONE, v.F_SANS_R, "mm", a, track=2)
    txt(p, "缺口：摩擦 / 热 / 风阻", (cx, cy + 300), 28, v.EMBER_P, v.F_SANS_R, "mm", a * 0.95,
        track=2)
    txt(p, "回收有上限，因为没有白来的能量", (960, 884), 34, v.BONE, v.F_SANS, "mm",
        ramp(t, dur * 0.65, dur * 0.95), track=3)
    return finish(p)


def scene_word_strike_more(t, dur, sh=None):
    """S13：「越开越多」被划掉 → 没有白来的能量。"""
    b = bg(v.EMBER, 0.07)
    p = v.Painter(b)
    p.flush()
    a = ramp(t, 0.2, 1.0)
    txt(p, "越开越多", (760, 480), 96, v.BONE, v.F_SANS, "mm", a, track=6)
    s = ramp(t, dur * 0.25, dur * 0.6)
    p.stroke([(380, 540), (380 + 780 * s, 440)], v.EMBER, 6.0, 0.95 * min(1, s * 3), 16, 0.5)
    p.flush()
    a2 = ramp(t, dur * 0.55, dur * 0.9)
    txt(p, "没有白来的能量", (960, 690), 64, v.TEAL, v.F_SANS, "mm", a2, track=4, glow=14 * a2)
    txt(p, "回收最多把这一脚本来要扔的，捡回大半", (960, 788), 28, v.MUTED, v.F_SANS_R,
        "mm", a2 * 0.95, track=2)
    return finish(p)


def scene_three_place(t, dur, sh=None):
    """S14：三件套总览：电机、逆变器、电池沿一条线排开（依次落位）。"""
    b = bg(v.TEAL, 0.10)
    p = v.Painter(b)
    xs = (430.0, 960.0, 1500.0)
    y = 520.0
    items = (("motor", "电机", "电 ⇄ 转动"), ("inverter", "逆变器", "直流 ⇄ 交流"),
             ("battery", "电池", "可充可放"))
    for i, (key, cn, sub) in enumerate(items):
        a = ramp(t, 0.3 + i * 0.5, 0.9 + i * 0.5)
        if a < 0.02:
            continue
        dy = (1 - a) * -40
        if key == "motor":
            v.draw_motor(p, xs[i], y + dy, 128, spin=t * 2.6 * 57.3, alpha=a * 0.95,
                         active="stator", flux=0.3)
        elif key == "inverter":
            v.draw_inverter(p, xs[i], y + dy, 190, 190, active="dc", alpha=a * 0.95)
        else:
            v.draw_battery_pack(p, xs[i], y + dy, 240, 200, soc=0.65, alpha=a * 0.95,
                                fill=-1)
        txt(p, cn, (xs[i], 760), 40, v.BONE, v.F_SANS, "mm", a * 0.95, track=3)
        txt(p, sub, (xs[i], 804), 22, v.MUTED, v.F_SANS_R, "mm", a * 0.85, track=1.5)
    # 连接线
    a = ramp(t, dur * 0.5, dur * 0.85)
    p.stroke([(560, y), (850, y)], v.MUTED, 1.6, 0.5 * a)
    p.stroke([(1070, y), (1380, y)], v.MUTED, 1.6, 0.5 * a)
    p.flush()
    txt(p, "干活的是三件套", (960, 236), 38, v.BONE, v.F_SANS, "mm", 0.9, track=4)
    txt(p, "电机 · 逆变器 · 电池", (960, 884), 34, v.MUTED, v.F_SANS_R, "mm", a, track=4)
    return finish(p)


def scene_motor_current(t, dur, sh=None):
    """S15：电机剖面：电流与转动的互换（线圈 + 磁场线）。"""
    b = bg(v.TEAL, 0.09, cx=0.45)
    p = v.Painter(b)
    cx, cy, R = 760.0, 540.0, 250.0
    v.draw_motor(p, cx, cy, R, spin=t * 3.0 * 57.3, alpha=1.0, active="stator", flux=0.5)
    # 三相电流波形（从定子引出）
    a = ramp(t, 0.3, dur * 0.7)
    for k in range(3):
        pts = []
        for q in range(60):
            x = 1120 + q * 10
            y = 520 + k * 70 + 26 * math.sin(q * 0.35 - t * 5 + k * 2.1)
            pts.append((x, y))
        p.stroke(np.array(pts, np.float32), (v.TEAL, v.AMBER, v.ICE)[k], 2.2, 0.75 * a, 8, 0.4)
    p.flush()
    txt(p, "定子线圈", (cx - 0, cy - 320), 28, v.BONE, v.F_SANS_R, "mm", 0.85, track=2)
    txt(p, "转子", (cx + 40, cy + 30), 24, v.BONE, v.F_SANS_R, "mm", 0.8, track=2)
    txt(p, "三相电流", (1460, 400), 26, v.TEAL, v.F_SANS_R, "mm", 0.85 * a, track=2)
    txt(p, "电 ⇄ 转动", (960, 884), 36, v.BONE, v.F_SANS, "mm", 0.9, track=4)
    return finish(p)


def scene_inverter_door(t, dur, sh=None):
    """S16：逆变器：一扇双向门，门上桥式功率器件。"""
    b = bg(v.AMBER, 0.08)
    p = v.Painter(b)
    cx, cy = 930.0, 540.0
    # 门框
    p.stroke(v._rounded_rect_pts(cx - 240, cy - 240, cx + 240, cy + 240, 16), v.STEEL, 2.6, 0.8)
    # 六开关（三桥臂）
    for k in range(3):
        bx = cx - 120 + k * 120
        p.stroke([(bx, cy - 200), (bx, cy + 200)], v.DIM, 1.2, 0.5)
        for s in (0, 1):
            sy = cy + (-80 if s == 0 else 80)
            p.fill_rect((bx - 16, sy - 14), (bx + 16, sy + 14), v.TEAL, 0.16)
            p.stroke([(bx - 16, sy - 14), (bx + 16, sy - 14), (bx + 16, sy + 14),
                      (bx - 16, sy + 14)], v.STEEL, 1.4, 0.7, closed=True)
    # 门开合：两扇门板左右移开，露出桥臂
    open_ = 0.5 + 0.5 * math.sin(t * 2.4)
    op = 150 + 300 * open_
    p.fill_rect((cx - 400 - op, cy - 280), (cx - 40 - op, cy + 280), (14, 18, 22), 0.9)
    p.fill_rect((cx + 40 + op, cy - 280), (cx + 400 + op, cy + 280), (14, 18, 22), 0.9)
    p.flush()
    txt(p, "双向门", (cx, cy - 320), 44, v.BONE, v.F_SANS, "mm", 0.9, track=4)
    txt(p, "同一套功率器件，方向反过来", (cx, cy + 330), 28, v.MUTED, v.F_SANS_R, "mm", 0.85, track=2)
    txt(p, "DC 母线", (cx, cy - 300), 24, v.AMBER, v.F_SANS_R, "mm", 0.8, track=2)
    txt(p, "三相交流", (cx, cy + 300), 24, v.TEAL, v.F_SANS_R, "mm", 0.8, track=2)
    txt(p, "开关声", (960, 884), 26, v.DIM, v.F_MONO, "mm", 0.6, track=2)
    return finish(p)


def _wave_scene(t, dur, reverse=False):
    b = bg(v.TEAL if reverse else v.AMBER, 0.08)
    p = v.Painter(b)
    x0, x1 = 300.0, 1620.0
    yc = 520.0
    # 轴向器
    p.stroke([(x0, yc), (x1, yc)], v.LINE, 1.6, 0.7)
    grow = ramp(t, 0.3, dur * 0.8)
    if not reverse:
        # DC 平直段 → 三相正弦（从左到右生长）
        p.stroke([(x0, yc - 40), (x0 + 60, yc - 40)], v.AMBER, 3.0, 0.9)
        p.stroke([(x0, yc + 40), (x0 + 60, yc + 40)], v.AMBER, 3.0, 0.9)
        end = int(x0 + 120 + (x1 - x0 - 160) * grow)
        for k in range(3):
            pts = [(x, yc + 28 * k - 28 + 90 * math.sin((x - x0) * 0.012 - t * 4 + k * 2.1))
                   for x in np.arange(x0 + 120, end, 6)]
            if len(pts) > 1:
                p.stroke(np.array(pts, np.float32), (v.TEAL, v.ICE, v.TEAL_P)[k], 2.4, 0.85, 10, 0.5)
        p.flush()
        txt(p, "直流", (x0 + 60, yc - 110), 30, v.AMBER, v.F_SANS_R, "mm", 0.9, track=3)
        txt(p, "三相交流", (x1 - 180, yc - 200), 30, v.TEAL, v.F_SANS_R, "mm", 0.9 * grow, track=3)
        txt(p, "直流 → 交流", (960, 884), 34, v.BONE, v.F_SANS, "mm", 0.9, track=4)
    else:
        # 三相交流 → 整流 → DC（从右往左收缩）
        end = int(x1 - 120 - (x1 - x0 - 160) * grow)
        for k in range(3):
            pts = [(x, yc + 28 * k - 28 + 90 * math.sin((x - x0) * 0.012 + t * 4 + k * 2.1))
                   for x in np.arange(max(x0 + 120, end), x1 - 60, 6)]
            if len(pts) > 1:
                p.stroke(np.array(pts, np.float32), (v.TEAL, v.ICE, v.TEAL_P)[k], 2.4, 0.85, 10, 0.5)
        p.stroke([(x1 - 60, yc - 40), (x1, yc - 40)], v.AMBER, 3.0, 0.9 * grow)
        p.stroke([(x1 - 60, yc + 40), (x1, yc + 40)], v.AMBER, 3.0, 0.9 * grow)
        p.flush()
        txt(p, "三相交流", (x0 + 100, yc - 200), 30, v.TEAL, v.F_SANS_R, "mm", 0.9, track=3)
        txt(p, "直流", (x1 - 60, yc - 110), 30, v.AMBER, v.F_SANS_R, "mm", 0.9 * grow, track=3)
        txt(p, "交流 → 直流", (960, 884), 34, v.BONE, v.F_SANS, "mm", 0.9, track=4)
    return finish(p)


def scene_wave_forward(t, dur, sh=None):
    return _wave_scene(t, dur, reverse=False)


def scene_wave_reverse(t, dur, sh=None):
    return _wave_scene(t, dur, reverse=True)


def scene_switches(t, dur, sh=None):
    """S19：功率器件特写：同一组开关，方向反了（同一套器件，翻向可读）。"""
    b = bg(v.TEAL, 0.07)
    p = v.Painter(b)
    cx, cy = 960.0, 560.0
    flip = ramp(t, dur * 0.4, dur * 0.7)
    for k in range(3):
        bx = cx - 360 + k * 360
        p.stroke([(bx, cy - 300), (bx, cy - 110)], v.AMBER, 3.0, 0.5)
        p.stroke([(bx, cy + 110), (bx, cy + 300)], v.MUTED, 3.0, 0.5)
        p.stroke([(bx, cy - 300), (bx, cy + 300)], v.DIM, 1.2, 0.25)
        for sidx, sy in ((0, cy - 170), (1, cy + 170)):
            ang = math.radians(30) * (1 if sidx == 0 else -1) * (1 if flip < 0.5 else -1)
            col = v.TEAL if (sidx == 0) == (flip >= 0.5) else v.AMBER
            x0, y0 = bx - 62, sy + 44
            x1, y1 = bx - 62 + 124 * math.cos(ang), sy + 44 - 124 * math.sin(ang)
            p.stroke([(bx - 70, sy - 54), (bx + 70, sy - 54), (bx + 70, sy + 54),
                      (bx - 70, sy + 54)], col, 2.2, 0.9, 12, 0.5, closed=True)
            p.stroke([(x0, y0), (x1, y1)], v.BONE, 4.0, 0.95, 12, 0.5)
            p.dot((x1, y1), 4.5, v.BONE, 0.95, glow=10)
        p.dot((bx, cy), 4.0, v.TEAL if flip >= 0.5 else v.MUTED, 0.9)
        p.stroke([(bx + 78, cy), (bx + 160, cy)], v.TEAL if flip >= 0.5 else v.MUTED, 2.4, 0.8)
    p.flush()
    txt(p, "同一套器件", (960, 226), 40, v.BONE, v.F_SANS, "mm", 0.9, track=4)
    txt(p, "方向反了", (960, cy + 380), 44, v.TEAL, v.F_SANS, "mm", flip, track=4, glow=14)
    txt(p, "6 个开关按顺序开合，改变电流方向", (960, 300), 24, v.MUTED, v.F_SANS_R, "mm",
        0.8, track=1.5)
    return finish(p)


def scene_chain_final(t, dur, sh=None):
    """S21：四站通道图定稿：轮端→电机→逆变器→电池。"""
    b = bg(v.TEAL, 0.12)
    p = v.Painter(b)
    draw_chain(p, t=t, direction=1, flow=0.75, active=None, y=CH_Y, soc=0.62,
               labels=True, heat=0.0)
    p.flush()
    txt(p, "一条路，两个方向", (960, 214), 40, v.BONE, v.F_SANS, "mm", 0.9, track=4)
    txt(p, "四站定型：轮端 · 电机 · 逆变器 · 电池", (960, 884), 32, v.MUTED,
        v.F_SANS_R, "mm", ramp(t, 0.4, dur * 0.8), track=3)
    return finish(p)


def scene_chain_bidir(t, dur, sh=None):
    """S22：同一条路双向箭头：驱动向前、回收向后。"""
    b = bg(v.TEAL, 0.10)
    p = v.Painter(b)
    y = CH_Y
    draw_chain(p, t=t, direction=1, flow=0.8, active=None, y=y, soc=0.62, labels=True,
               heat=0.0)
    # 上方：驱动箭头（电池→轮端 = 右→左，琥珀）；下方：回收箭头（轮端→电池 = 左→右，青）
    a = ramp(t, 0.25, dur * 0.7)
    for seg in chain_segs(y):
        mid = seg.mean(axis=0)
        up = [(mid[0] + 165, y - 62), (mid[0] - 165, y - 62)]
        p.stroke(np.array(up, np.float32), v.AMBER, 3.0, 0.8 * a, 12, 0.5)
        p.stroke(np.array([(mid[0] - 150, y - 74), (mid[0] - 170, y - 62),
                           (mid[0] - 150, y - 50)], np.float32), v.AMBER, 3.0, 0.85 * a)
        dn = [(mid[0] - 165, y + 62), (mid[0] + 165, y + 62)]
        p.stroke(np.array(dn, np.float32), v.TEAL, 3.0, 0.8 * a, 12, 0.5)
        p.stroke(np.array([(mid[0] + 150, y + 50), (mid[0] + 170, y + 62),
                           (mid[0] + 150, y + 74)], np.float32), v.TEAL, 3.0, 0.85 * a)
    p.flush()
    txt(p, "驱动", (960, 340), 26, v.AMBER, v.F_SANS_R, "mm", 0.9, track=3)
    txt(p, "回收", (960, 706), 26, v.TEAL, v.F_SANS_R, "mm", 0.9, track=3)
    txt(p, "同一条路", (960, 236), 40, v.BONE, v.F_SANS, "mm", 0.9, track=4)
    txt(p, "差别只有一个：功率往哪边流", (960, 884), 32, v.MUTED, v.F_SANS_R, "mm", a, track=2)
    return finish(p)


def scene_arrow_flip(t, dur, sh=None):
    """S23：功率方向：一个箭头从电池一侧翻到轮端一侧。"""
    b = bg(v.TEAL, 0.08)
    p = v.Painter(b)
    flip = ramp(t, dur * 0.35, dur * 0.75)
    cx, cy = 960.0, 520.0
    # 布局契约：轮端(左) → 电机 → 逆变器 → 电池(右)
    p.stroke([(360, cy), (1560, cy)], v.LINE, 8.0, 0.35)
    # flip=0 驱动：箭头指向左（电池→轮端，琥珀）；flip=1 回收：箭头指向右（轮端→电池，青）
    dx = math.cos(math.pi * (1 - flip))       # flip0: -1（左），flip1: +1（右）
    x0, x1 = cx - 380 * dx, cx + 380 * dx if False else cx + 380 * dx
    # 让箭头主体从短到长再翻转
    reach = 0.4 + 0.6 * math.sin(math.pi * min(1.0, flip * 1.4)) if flip < 0.5 else 1.0
    x0, x1 = cx - 380 * dx * reach, cx + 380 * dx * reach
    col = v.AMBER if flip < 0.5 else v.TEAL
    p.stroke([(x0, cy), (x1, cy)], col, 7.0, 0.95, 26, 0.7)
    head = [(x1 - 46 * math.copysign(1, dx), cy - 32), (x1, cy),
            (x1 - 46 * math.copysign(1, dx), cy + 32)]
    p.stroke(np.array(head, np.float32), col, 5.0, 0.95, 18, 0.6)
    p.flush()
    txt(p, "轮端", (330, cy + 90), 30, v.TEAL if flip >= 0.5 else v.MUTED, v.F_SANS,
        "mm", 0.9, track=2)
    txt(p, "电池", (1590, cy + 90), 30, v.AMBER if flip < 0.5 else v.MUTED, v.F_SANS,
        "mm", 0.9, track=2)
    txt(p, "功率往哪边流", (960, cy - 160), 42, v.BONE, v.F_SANS, "mm", 0.9, track=4)
    txt(p, "放电：往左 ｜ 回收：往右", (960, cy + 200), 30, v.MUTED, v.F_SANS_R, "mm",
        0.85, track=2)
    return finish(p)


def scene_chain_reverse(t, dur, sh=None):
    """S24：刹车时顺序反过来：轮端推电机→发电机→整流→电池收电；定格成母题。"""
    b = bg(v.TEAL, 0.12)
    p = v.Painter(b)
    order = ["wheel", "motor", "inverter", "battery"]
    k = min(3, int(ramp(t, 0.5, dur * 0.75) * 4.0))
    active = order[k]
    draw_chain(p, t=t, direction=1, flow=1.0, active=active, y=CH_Y, soc=0.62,
               labels=False, heat=0.35 * ramp(t, dur * 0.5, dur * 0.9))
    p.flush()
    # 逐站文字（反向顺序 ①②③④）
    stage_txt = {0: ("轮端", "轮子反过来推电机"), 1: ("电机", "变成发电机"),
                 2: ("逆变器", "把交流整流回直流"), 3: ("电池", "收电")}
    for i, key in enumerate(order):
        on = i <= k
        txt(p, stage_txt[i][0], (CH_X[i], CH_Y + 168), 32, v.BONE if on else v.DIM,
            v.F_SANS, "mm", 0.95 if on else 0.4, track=2)
        if on:
            txt(p, stage_txt[i][1], (CH_X[i], CH_Y + 204), 17, v.TEAL, v.F_MONO, "mm",
                0.8, track=0.5)
    # 反向序号
    for i in range(4):
        if i <= k:
            txt(p, str(i + 1), (CH_X[i] - 46, CH_Y - 116), 26, v.TEAL, v.F_MONO, "mm",
                0.85, glow=8)
    txt(p, "刹车：反向四站", (960, 214), 40, v.BONE, v.F_SANS, "mm", ramp(t, 0.4, 1.2),
        track=4)
    a = ramp(t, dur * 0.72, dur * 0.95)
    txt(p, "记住这张图，后面都用它", (960, 884), 34, v.TEAL, v.F_SANS, "mm", a, track=3,
        glow=10 * a)
    return finish(p)


# ================================================================ S4 能量账
def scene_formula_appear(t, dur, sh=None):
    """S26：公式 ½mv² 被写到画面中央（逐项浮现）。"""
    b = bg(v.TEAL, 0.07)
    p = v.Painter(b)
    cx, cy = 960.0, 500.0
    a1 = ramp(t, 0.2, 0.9)
    txt(p, "动能", (cx - 250, cy), 60, v.BONE, v.F_SANS_R, "rm" if False else "mm", a1, track=2)
    txt(p, "=", (cx - 120, cy), 60, v.BONE, v.F_MONO, "mm", a1)
    a2 = ramp(t, 0.6, 1.3)
    txt(p, "½", (cx - 20, cy), 90, v.TEAL, v.F_SERIF, "mm", a2, track=0)
    a3 = ramp(t, 1.0, 1.7)
    txt(p, "m", (cx + 80, cy), 76, v.TEAL, v.F_SERIF, "mm", a3, track=0)
    txt(p, "v²", (cx + 200, cy), 76, v.TEAL, v.F_SERIF, "mm", ramp(t, 1.4, 2.1), track=0)
    # 底部释义
    a = ramp(t, dur * 0.55, dur * 0.9)
    txt(p, "质量 × 速度的平方", (cx, cy + 130), 30, v.MUTED, v.F_SANS_R, "mm", a, track=2)
    txt(p, "先看扔了多少：动能 = ½ m v²", (960, 884), 34, v.BONE, v.F_SANS, "mm", a, track=2)
    return finish(p)


def scene_formula_substitute(t, dur, sh=None):
    """S27：代入：质量 1.5 t、速度 100 km/h 滑进槽位。"""
    b = bg(v.AMBER, 0.07)
    p = v.Painter(b)
    cx, cy = 960.0, 480.0
    s = ramp(t, 0.2, dur * 0.7)
    # 公式骨架
    txt(p, "½", (cx - 260, cy), 76, v.TEAL, v.F_SERIF, "mm", 0.9, track=0)
    txt(p, "×", (cx - 180, cy), 48, v.BONE, v.F_MONO, "mm", 0.8)
    # 槽位 m
    p.stroke(v._rounded_rect_pts(cx - 130, cy - 60, cx - 10, cy + 60, 10), v.MUTED, 2.0, 0.6)
    p.flush()
    txt(p, "m", (cx - 70, cy), 56, v.TEAL, v.F_SERIF, "mm", 0.9)
    txt(p, "×", (cx + 20, cy), 48, v.BONE, v.F_MONO, "mm", 0.8)
    # 槽位 v²
    p.stroke(v._rounded_rect_pts(cx + 60, cy - 60, cx + 300, cy + 60, 10), v.MUTED, 2.0, 0.6)
    p.flush()
    txt(p, "v²", (cx + 180, cy), 56, v.TEAL, v.F_SERIF, "mm", 0.9)
    # 数值滑入
    am = ramp(t, 0.5, dur * 0.65)
    txt(p, "1.5 t", (cx - 70, cy - 100 + 40 * (1 - am)), 40, v.BONE, v.F_MONO, "mm", am, track=1)
    av = ramp(t, dur * 0.45, dur * 0.85)
    txt(p, "100 km/h", (cx + 180, cy - 100 + 40 * (1 - av)), 40, v.BONE, v.F_MONO, "mm",
        av, track=1)
    a = ramp(t, dur * 0.6, dur * 0.95)
    txt(p, "1.5 t · 100 km/h", (960, 780), 44, v.TEAL, v.F_MONO, "mm", a, track=2)
    txt(p, "示例车：质量 1.5 t，从 100 刹到 0", (960, 884), 30, v.MUTED, v.F_SANS_R,
        "mm", a, track=2)
    return finish(p)


def scene_result_016(t, dur, sh=None):
    """S28：结果：约 0.16 度电，数字落定。"""
    b = bg(v.TEAL, 0.10)
    p = v.Painter(b)
    a = ramp(t, 0.3, dur * 0.6)
    val = 0.160 * ramp(t, 0.3, min(dur * 0.45, 2.2))
    big_number(p, "%.3f" % val, (960, 470), 190, v.TEAL, a, "kWh")  # 落定 0.160（F01 计算值）
    txt(p, "约 0.16 度电", (960, 690), 44, v.BONE, v.F_SANS, "mm", ramp(t, dur * 0.6, dur * 0.9),
        track=3)
    txt(p, "1.5 t 示例车 · 100 → 0 km/h · 物理估算，非实测（F01）", (960, 884), 26,
        v.MUTED, v.F_SANS_R, "mm", ramp(t, dur * 0.55, dur * 0.85), track=2)
    # 对比条：0.16 kWh vs 60 kWh
    p.fill_rect((360, 760), (1560, 776), v.LINE, 0.6)
    p.fill_rect((360, 760), (360 + 1200 * 0.161 / 60.0, 776), v.TEAL, 0.9)
    p.fill_rect((360, 745), (370, 791), v.TEAL, 0.8)
    p.flush()
    return finish(p)


def scene_quadratic_curve(t, dur, sh=None):
    """S29：速度平方关系曲线：100→120 km/h，动能抬升 44%。"""
    b = bg(v.TEAL, 0.07)
    p = v.Painter(b)
    x0, x1, y0, y1 = 380.0, 1560.0, 760.0, 340.0
    axes(p, x0, y0, x1, y1)
    p.flush()
    # KE ∝ v²
    def fx(vv):
        return x0 + (vv - 40) / 100.0 * (x1 - x0)
    def fy(vv):
        return y0 - ((vv / 130.0) ** 2) * (y0 - y1)
    grow = ramp(t, 0.3, dur * 0.7)
    pts = [(fx(vv), fy(vv)) for vv in np.linspace(40, 40 + 80 * grow, 90)]
    p.stroke(np.array(pts, np.float32), v.TEAL, 3.2, 0.95, 14, 0.6)
    # 100 / 120 标记
    for vv, col, lab in ((100, v.TEAL, "100"), (120, v.EMBER_P, "120")):
        if grow > (vv - 40) / 80.0 - 0.05:
            xx, yy = fx(vv), fy(vv)
            p.dot((xx, yy), 6, col, 0.95, glow=14)
            txt(p, "%s km/h" % lab, (xx, yy - 34), 22, col, v.F_MONO, "mm", 0.9)
    # 括号：+44%
    a = ramp(t, dur * 0.62, dur * 0.9)
    x100, x120 = fx(100), fx(120)
    y100, y120 = fy(100), fy(120)
    p.stroke([(x120 + 20, y100), (x120 + 20, y120)], v.EMBER_P, 2.0, 0.85 * a)
    p.stroke([(x120 + 10, y100), (x120 + 30, y100)], v.EMBER_P, 2.0, 0.85 * a)
    p.stroke([(x120 + 10, y120), (x120 + 30, y120)], v.EMBER_P, 2.0, 0.85 * a)
    p.flush()
    txt(p, "+44%", (x120 + 84, (y100 + y120) / 2), 40, v.EMBER_P, v.F_MONO, "mm", a, glow=12)
    txt(p, "动能随速度的平方涨", (960, 236), 38, v.BONE, v.F_SANS, "mm", 0.9, track=3)
    txt(p, "100 → 120 km/h，动能多出四成多（F01）", (960, 884), 26, v.MUTED, v.F_SANS_R,
        "mm", a, track=2)
    return finish(p)


def scene_chain_loss_bar(t, dur, sh=None):
    """S31：回收要过三站，每站掉一段能量条。"""
    b = bg(v.TEAL, 0.08)
    p = v.Painter(b)
    x0, x1, y = 300.0, 1620.0, 520.0
    x_end = x0 + (x1 - x0) * ramp(t, 0.3, dur * 0.85)
    p.fill_rect((x0, y - 34), (x1, y + 34), v.LINE, 0.35)
    p.fill_rect((x0, y - 34), (x_end, y + 34), v.TEAL, 0.75)
    # 四站刻度（轮端在起点）
    for i, (xx, lab) in enumerate(((x0, "轮端"), (x0 + (x1 - x0) * 0.34, "电机"),
                                   (x0 + (x1 - x0) * 0.66, "逆变器"),
                                   (x1, "电池"))):
        p.stroke([(xx, y - 52), (xx, y + 52)], v.BONE, 1.6, 0.6)
        txt(p, lab, (xx, y + 84), 26, v.MUTED, v.F_SANS_R, "mm", 0.85, track=2)
    # 掉电标记
    a = ramp(t, dur * 0.5, dur * 0.9)
    for i, xx in enumerate((x0 + (x1 - x0) * 0.34, x0 + (x1 - x0) * 0.66)):
        txt(p, "−10%", (xx, y - 84), 24, v.AMBER, v.F_MONO, "mm", a * (1 if i == 0 else 0.85))
    p.flush()
    txt(p, "每站都掉一点", (960, 236), 40, v.BONE, v.F_SANS, "mm", 0.9, track=3)
    txt(p, "轮端 → 电机 → 逆变器 → 电池（F03：台架 70%–87%）", (960, 884), 28,
        v.MUTED, v.F_SANS_R, "mm", ramp(t, dur * 0.6, dur * 0.95), track=2)
    return finish(p)


def _eff_band(p, x0, x1, y, low, high, color, alpha=1.0, marker=None):
    p.fill_rect((x0, y - 22), (x1, y + 22), v.LINE, 0.45 * alpha)
    p.fill_rect((x0, y - 22), (x1, y + 22), color, 0.10 * alpha)
    bx0 = x0 + (x1 - x0) * low
    bx1 = x0 + (x1 - x0) * high
    p.fill_rect((bx0, y - 22), (bx1, y + 22), color, 0.55 * alpha)
    p.stroke([(bx0, y - 34), (bx0, y + 34)], color, 2.2, 0.9 * alpha, 10, 0.4)
    p.stroke([(bx1, y - 34), (bx1, y + 34)], color, 2.2, 0.9 * alpha, 10, 0.4)
    if marker is not None:
        mx = x0 + (x1 - x0) * marker
        p.dot((mx, y), 7, v.WHITE, 0.95 * alpha, glow=14)


def scene_eff_gauge_regen(t, dur, sh=None):
    """S32：台架实测效率：轮端→电池 70%–87% 的仪表条。"""
    b = bg(v.TEAL, 0.09)
    p = v.Painter(b)
    x0, x1, y = 380.0, 1540.0, 520.0
    low = F("F03.low", 0.70)
    high = F("F03.high", 0.87)
    grow = ramp(t, 0.4, dur * 0.8)
    _eff_band(p, x0, x1, y, low, high, v.TEAL, grow, marker=0.5 + 0.5 * math.sin(t * 3))
    # 刻度 0/50/100
    for vv in (0, 0.25, 0.5, 0.75, 1.0):
        xx = x0 + (x1 - x0) * vv
        p.stroke([(xx, y + 40), (xx, y + 52)], v.DIM, 1.2, 0.6)
        txt(p, "%d%%" % int(vv * 100), (xx, y + 76), 20, v.DIM, v.F_MONO, "mm", 0.6)
    p.flush()
    txt(p, "回收效率：轮端制动功率 → 电池充电功率", (960, 236), 36, v.BONE, v.F_SANS,
        "mm", 0.9, track=2)
    a = ramp(t, dur * 0.55, dur * 0.85)
    txt(p, "70% – 87%", (960, 300), 52, v.TEAL, v.F_MONO, "mm", a, track=3, glow=12 * a)
    txt(p, "台架实测（UDDS，F03）", (960, 884), 28, v.MUTED, v.F_SANS_R, "mm", a, track=2)
    return finish(p)


def scene_eff_bars_compare(t, dur, sh=None):
    """S33：对照：驱动方向 87%–89%，两条效率条并排。"""
    b = bg(v.AMBER, 0.07)
    p = v.Painter(b)
    x0, x1 = 420.0, 1540.0
    a = ramp(t, 0.3, dur * 0.6)
    _eff_band(p, x0, x1, 460.0, F("F03.low", 0.70), F("F03.high", 0.87), v.TEAL, a)
    a2 = ramp(t, dur * 0.45, dur * 0.8)
    _eff_band(p, x0, x1, 640.0, F("F04.low", 0.87), F("F04.high", 0.89), v.AMBER, a2)
    p.flush()
    txt(p, "回收（轮端→电池）", (x0 - 30, 460), 26, v.TEAL, v.F_SANS_R, "rm", a, track=1)
    txt(p, "驱动（电池→轮端）", (x0 - 30, 640), 26, v.AMBER, v.F_SANS_R, "rm", a2, track=1)
    txt(p, "70%–87%", (x1 + 30, 460), 26, v.TEAL, v.F_MONO, "lm", a)
    txt(p, "87%–89%", (x1 + 30, 640), 26, v.AMBER, v.F_MONO, "lm", a2)
    txt(p, "两个方向，两条效率", (960, 236), 38, v.BONE, v.F_SANS, "mm", 0.9, track=3)
    txt(p, "口径分开写：回收效率 ≠ 驱动效率（F03/F04）", (960, 884), 26, v.MUTED,
        v.F_SANS_R, "mm", ramp(t, dur * 0.6, dur * 0.95), track=2)
    return finish(p)


def scene_eff_diff(t, dur, sh=None):
    """S34：回收条与驱动条叠合对照，差值区域高亮（方向每换一次都要交过路费）。"""
    b = bg(v.TEAL, 0.07)
    p = v.Painter(b)
    x0, x1 = 400.0, 1500.0
    a = ramp(t, 0.3, dur * 0.9)
    low3, high3 = F("F03.low", 0.70), F("F03.high", 0.87)
    low4, high4 = F("F04.low", 0.87), F("F04.high", 0.89)
    # 两条区间线叠合（同一轴，略微错开 6px 便于同时可读）
    _eff_band(p, x0, x1, 462.0, low4, high4, v.AMBER, a)
    _eff_band(p, x0, x1, 486.0, low3, high3, v.TEAL, a)
    # 差值区域（87% → 89%）：斜线高亮
    dx0 = x0 + (x1 - x0) * high3
    dx1 = x0 + (x1 - x0) * high4
    for k in range(7):
        xx = v.lerp(dx0, dx1, k / 6.0)
        p.stroke([(xx - 8, 540), (xx + 16, 430)], v.EMBER_P, 1.6, 0.55 * a)
    p.stroke([(dx0, 430), (dx0, 540)], v.EMBER_P, 2.0, 0.9 * a)
    p.stroke([(dx1, 430), (dx1, 540)], v.EMBER_P, 2.0, 0.9 * a)
    p.fill_rect((dx0, 430), (dx1, 540), v.EMBER_P, 0.10 * a)
    p.flush()
    txt(p, "驱动（电池→轮端）87–89%", (x1 + 24, 462), 24, v.AMBER, v.F_SANS_R, "lm",
        0.95, track=1)
    txt(p, "回收（轮端→电池）70–87%", (x1 + 24, 486), 24, v.TEAL, v.F_SANS_R, "lm",
        0.95, track=1)
    txt(p, "差值", (dx1 + 26, 485), 24, v.EMBER_P, v.F_SANS_R, "lm", 0.9, track=2)
    txt(p, "方向每换一次，都要交过路费", (960, 236), 40, v.BONE, v.F_SANS, "mm",
        0.95, track=3)
    txt(p, "回收总是比驱动更亏一点", (960, 884), 32, v.BONE, v.F_SANS_R, "mm", a,
        track=2)
    return finish(p)


def scene_sankey_loss(t, dur, sh=None):
    """S36：能量损失去向：回收 / 热 / 风阻 / 滚阻 三路分流（Sankey）。"""
    b = bg(v.AMBER, 0.06)
    p = v.Painter(b)
    # 主路：100%
    x0, x1 = 330.0, 1560.0
    ytop, ybot = 420.0, 700.0
    rec = F("F05.value", 0.78)
    grow = ramp(t, 0.35, dur * 0.85)
    # 回收带（上半，青）
    v.sankey_ribbon(p, x0, ytop, ytop + (ybot - ytop) * rec * grow,
                    x1, 380.0, 380.0 + 64.0, v.TEAL, 0.5 * grow, glow=0)
    # 损耗三股（下半，琥珀渐弱）
    base = ybot
    for i, (frac, col, lab) in enumerate(((0.45, v.AMBER, "热"),
                                          (0.35, v.AMBER_D, "风阻"),
                                          (0.20, v.MUTED, "滚阻"))):
        y0 = ytop + (ybot - ytop) * rec + (ybot - ytop) * (1 - rec) * (0.0 + 0.34 * i) * grow
        y1 = y0 + (ybot - ytop) * (1 - rec) * 0.30 * grow
        v.sankey_ribbon(p, x0, y0, y1, x1, 740.0 + i * 48, 740.0 + i * 48 + 30, col,
                        0.35 * grow, glow=0)
    p.flush()
    txt(p, "回收 ≈ 78%（实车试验，F05）", (x1 - 30, 400), 24, v.TEAL, v.F_SANS_R, "rm",
        grow, track=1)
    for i, lab in enumerate(("热", "风阻", "滚阻")):
        txt(p, lab, (x1 - 30, 740 + i * 48 + 12), 24, v.AMBER if i < 2 else v.MUTED,
            v.F_SANS_R, "rm", grow * (1 - i * 0.12), track=2)
    txt(p, "剩下的去了哪", (960, 226), 40, v.BONE, v.F_SANS, "mm", 0.9, track=3)
    txt(p, "热 · 风阻 · 滚阻", (960, 884), 34, v.MUTED, v.F_SANS_R, "mm", grow, track=4)
    return finish(p)


def scene_aero_drag(t, dur, sh=None):
    """S37：车速升高，风阻箭头成倍变粗，能量被风带走。"""
    b = bg(v.ICE, 0.06)
    p = v.Painter(b)
    # 车侧轮廓
    v.car_side(p, 760, 560, scale=1.7, alpha=0.9)
    speed = ramp(t, 0.3, dur * 0.85)
    a = ramp(t, 0.25, dur * 0.7)
    # 风阻箭头：随速度变粗变长
    for k in range(9):
        yy = 380 + k * 42
        ln = 300 + 420 * speed
        w = 1.5 + 7 * speed
        p.stroke([(1330, yy), (1330 + ln, yy - 10)], v.ICE, w, 0.35 * a, 8, 0.4)
        p.stroke([(1330 + ln - 32, yy - 14), (1330 + ln, yy - 10),
                  (1330 + ln - 34, yy + 6)], v.ICE, w * 0.8, 0.4 * a)
    p.flush()
    txt(p, "车速越高，风阻越狠", (960, 226), 40, v.BONE, v.F_SANS, "mm", 0.9, track=3)
    txt(p, "风阻 ∝ 速度²，这部分收不回来", (960, 884), 30, v.MUTED, v.F_SANS_R, "mm", a,
        track=2)
    return finish(p)


def scene_highway_share(t, dur, sh=None):
    """S38：高速巡航：回收能量占驱动能量不到 5%（占比环几乎为空）。"""
    b = bg(v.TEAL, 0.07)
    p = v.Painter(b)
    cx, cy, R = 960.0, 540.0, 240.0
    p.stroke([v.polar(cx, cy, R, d) for d in range(0, 361, 3)], v.LINE, 14.0, 0.6, closed=True)
    p.flush()
    frac = 0.045 * ramp(t, 0.4, dur * 0.85)
    if frac > 0.001:
        pts = [v.polar(cx, cy, R, d) for d in np.arange(-90, -90 + 360 * frac, 1.5)]
        p.stroke(np.array(pts, np.float32), v.TEAL, 14.0, 0.95, 18, 0.6)
        p.flush()
    txt(p, "< 5%", (cx, cy - 10), 96, v.TEAL, v.F_MONO, "mm", 0.95, track=2, glow=16)
    txt(p, "回收能量 ÷ 驱动能量（高速巡航，F06）", (cx, cy + 96), 26, v.MUTED,
        v.F_SANS_R, "mm", 0.85, track=2)
    txt(p, "高速上占比几乎为零", (960, 236), 40, v.BONE, v.F_SANS, "mm", 0.9, track=3)
    txt(p, "不是效率低，是总量本来就没多少可收", (960, 884), 30, v.MUTED, v.F_SANS_R,
        "mm", 0.85, track=2)
    return finish(p)


def scene_downhill_numbers(t, dur, sh=None):
    """S41：1 km、落差 50 m → 约 0.2 度；按七成回收 ≈ 0.14 度，够跑不到 1 km。"""
    b = bg(v.TEAL, 0.09)
    p = v.Painter(b)
    # 左侧小坡示意
    p.stroke([(260, 700), (860, 420)], v.STEEL, 2.4, 0.75)
    p.stroke([(260, 700), (860, 700)], v.DIM, 1.2, 0.4)
    p.stroke([(860, 420), (860, 700)], v.MUTED, 1.6, 0.6)
    v.car_side(p, 520, 640, scale=0.55, alpha=0.8)
    txt(p, "落差 50 m", (880, 560), 24, v.MUTED, v.F_SANS_R, "lm", 0.85, track=1)
    txt(p, "1 km", (560, 740), 22, v.MUTED, v.F_MONO, "mm", 0.8)
    p.flush()
    rows = (("势能 E = mgh", "0.20 kWh", v.BONE),
            ("按七成回收", "0.14 kWh", v.TEAL),
            ("按 15 kWh/100km", "< 1 km", v.TEAL))
    for i, (k1, k2, col) in enumerate(rows):
        a = ramp(t, 0.6 + i * 0.6, 1.2 + i * 0.6)
        txt(p, k1, (1080, 400 + i * 110), 28, v.MUTED, v.F_SANS_R, "lm", 0.85 * a, track=1)
        txt(p, k2, (1080, 452 + i * 110), 46, col, v.F_MONO, "lm", 0.95 * a, track=2)
    txt(p, "长下坡：势能", (960, 226), 38, v.BONE, v.F_SANS, "mm", 0.9, track=4)
    txt(p, "1.5 t 示例车 · 物理估算，非实测（F02）", (960, 884), 28, v.MUTED,
        v.F_SANS_R, "mm", ramp(t, dur * 0.6, dur * 0.95), track=2)
    return finish(p)


# ================================================================ S5 四条限制
def scene_limits_quad(t, dur, sh=None):
    """S42：四条限制总览：满电 / 低温 / 高速 / 抓地力，四格依次点亮再变暗。

    可读性：卡片亮起时带微光底 + 亮边框，标题/说明提亮（1080p 下可读）。
    """
    b = bg(v.EMBER, 0.06)
    p = v.Painter(b)
    items = (("满电", "电池满了，不收"), ("低温", "充电能力下降"),
             ("高速", "反电动势 + 风阻"), ("抓地力", "ABS 介入，回收让路"))
    xs = (500.0, 900.0, 1300.0, 1700.0)
    y0, y1 = 380.0, 700.0
    lit = min(4, int(ramp(t, 0.3, dur * 0.55) * 4.0))
    for i, (t1, t2) in enumerate(items):
        on = i < lit
        aa = 1.0 if on else 0.5
        x0, x1 = xs[i] - 136, xs[i] + 136
        if on:
            p.fill_rect((x0, y0), (x1, y1), (179, 57, 46), 0.07)
        p.stroke([(x0, y0), (x1, y0), (x1, y1), (x0, y1)],
                 (232, 132, 112) if on else v.MUTED, 2.6 if on else 1.6, aa,
                 16 if on else 4, 0.55, closed=True)
        p.dot((xs[i], y0 + 30), 4.2, v.EMBER_P if on else v.MUTED, aa, glow=10 if on else 0)
    p.flush()
    for i, (t1, t2) in enumerate(items):
        on = i < lit
        aa = 1.0 if on else 0.5
        txt(p, t1, (xs[i], y0 + 122), 46, (255, 168, 148) if on else v.MUTED, v.F_SANS,
            "mm", aa, track=3)
        txt(p, "第 %d 条" % (i + 1), (xs[i], y0 + 74), 19, v.BONE if on else v.DIM,
            v.F_MONO, "mm", aa * 0.85, track=1)
        txt(p, t2, (xs[i], y0 + 198), 23, (235, 226, 214) if on else v.MUTED,
            v.F_SANS_R, "mm", aa, track=1)
    # 后面依次暗下（保留最后一张亮）
    dim = ramp(t, dur * 0.62, dur * 0.95)
    if dim > 0.01:
        d = int(dim * 3)
        for i in range(0, 3 - min(3, d)):
            p.fill_rect((xs[i] - 138, y0 - 2), (xs[i] + 138, y1 + 2), (12, 15, 18), 0.66)
        p.flush()
    txt(p, "四条限制", (960, 236), 42, v.BONE, v.F_SANS, "mm", 0.95, track=4)
    txt(p, "不是随时都能回收", (960, 884), 34, v.BONE, v.F_SANS_R, "mm", 0.9, track=3)
    return finish(p)


def scene_limit_full(t, dur, sh=None):
    """S43：满电：电池 100%，回收请求被拒，机械刹车接管。"""
    b = bg(v.EMBER, 0.06)
    p = v.Painter(b)
    cx, cy = 760.0, 540.0
    v.draw_battery_pack(p, cx, cy, 300.0, 250.0, soc=1.0, temp=0.5, alpha=1.0, fill=-1)
    # 回收电流箭头（从右往左）被红叉挡住
    a = ramp(t, 0.3, dur * 0.7)
    for k in range(3):
        yy = cy - 70 + k * 70
        p.stroke([(cx + 220, yy), (cx + 400, yy)], v.TEAL, 3.0, 0.8 * a, 10, 0.5)
        p.stroke([(cx + 370, yy - 12), (cx + 400, yy), (cx + 370, yy + 12)], v.TEAL, 3.0, 0.8 * a)
    # 红叉/挡板
    bx = cx + 250
    p.stroke([(bx, cy - 110), (bx, cy + 110)], v.EMBER, 5.0, 0.95, 14, 0.5)
    p.stroke([(bx - 26, cy - 90), (bx + 26, cy + 90)], v.EMBER, 4.0, 0.85)
    p.stroke([(bx - 26, cy + 90), (bx + 26, cy - 90)], v.EMBER, 4.0, 0.85)
    # 机械刹车接管：右下刹车盘示意
    v.draw_wheel(p, 1450.0, 620.0, 110.0, spin=t * 2.0 * 57.3, alpha=0.9, torque=0.8)
    p.stroke([(1220, 760), (1330, 760)], v.EMBER, 2.0, 0.7 * a)
    p.flush()
    txt(p, "电池 100%", (cx, cy - 200), 34, v.BONE, v.F_SANS, "mm", 0.9, track=3)
    txt(p, "回收请求被拒绝", (cx, 300), 30, v.EMBER_P, v.F_SANS_R, "mm", a, track=2)
    txt(p, "机械刹车接管", (1450, 780), 30, v.BONE, v.F_SANS_R, "mm", a, track=2)
    txt(p, "满电：不收", (960, 884), 36, v.EMBER_P, v.F_SANS, "mm", 0.9, track=4)
    return finish(p)


def scene_lithium_plating(t, dur, sh=None):
    """S45：低温充电微观示意：锂离子在负极表面析出。"""
    b = bg(v.ICE, 0.06)
    p = v.Painter(b)
    # 负极表面（横向平面）
    y = 620.0
    p.fill_rect((240, y), (1680, y + 170), (24, 32, 40), 0.9)
    p.stroke([(240, y), (1680, y)], v.STEEL, 2.4, 0.8)
    p.flush()
    # 离子从电解液落下
    rng = np.random.default_rng(11)
    a = ramp(t, 0.3, dur * 0.8)
    for k in range(34):
        sx = 280 + rng.uniform(0, 1360)
        ph = rng.uniform(0, 1)
        prog = (ph + t * 0.55) % 1.0
        yy = v.lerp(y - 260, y - 6, prog * prog)
        if a < 0.05:
            continue
        p.dot((sx, yy), 3.0, v.ICE, 0.55 * a, glow=8)
    # 析出颗粒堆积
    for k in range(18):
        sx = 300 + rng.uniform(0, 1320)
        p.dot((sx, y - rng.uniform(2, 22)), rng.uniform(3, 7), v.EMBER_P,
              0.4 * a, glow=8)
    p.flush()
    txt(p, "负极表面", (330, y + 90), 26, v.BONE, v.F_SANS_R, "lm", 0.85, track=2)
    txt(p, "锂离子", (1340, 330), 24, v.ICE, v.F_SANS_R, "mm", 0.8 * a, track=2)
    txt(p, "析锂 · 伤寿命", (960, 280), 42, v.EMBER_P, v.F_SANS, "mm", a, track=4, glow=12 * a)
    txt(p, "太冷还硬充：离子堆在表面，变成金属锂（F11）", (960, 884), 28, v.MUTED,
        v.F_SANS_R, "mm", a, track=2)
    return finish(p)


def scene_tach_high(t, dur, sh=None):
    """S46：车速太高：转速表冲上高位。"""
    b = bg(v.EMBER, 0.05)
    p = v.Painter(b)
    cx, cy, R = 960.0, 560.0, 270.0
    # 表盘
    p.stroke([v.polar(cx, cy, R, d) for d in range(0, 361, 3)], v.LINE, 8.0, 0.7, closed=True)
    # 红区 80%-100%
    red = [v.polar(cx, cy, R, d) for d in np.arange(30, 120, 2)]
    p.stroke(np.array(red, np.float32), v.EMBER, 8.0, 0.8, 14, 0.5)
    sweep = ramp(t, 0.3, dur * 0.85)
    ang = v.lerp(-110, 96, sweep)
    p.stroke([v.polar(cx, cy, R - 40, ang), v.polar(cx, cy, 16, ang)], v.EMBER_P, 5.0,
             1.0, 18, 0.6)
    p.dot((cx, cy), 10, v.EMBER_P, 1.0, glow=22)
    for k in range(7):
        a0 = -110 + k * 33
        p.stroke([v.polar(cx, cy, R - 14, a0), v.polar(cx, cy, R + 10, a0)], v.MUTED,
                 1.6, 0.6)
    p.flush()
    txt(p, "车速冲上高位", (960, 300), 40, v.BONE, v.F_SANS, "mm", 0.9, track=3)
    txt(p, "第三条：太快", (960, 884), 36, v.EMBER_P, v.F_SANS, "mm", 0.9, track=4)
    return finish(p)


def scene_back_emf_wall(t, dur, sh=None):
    """S47：反电动势电压墙：电机电压顶住电池电压，回收电流被压住。"""
    b = bg(v.AMBER, 0.06)
    p = v.Painter(b)
    # 两条电压柱
    x_batt, x_emf = 760.0, 1180.0
    base = 760.0
    h_batt = 300.0
    emf = ramp(t, 0.25, dur * 0.8)
    h_emf = 300.0 + 260.0 * emf
    p.fill_rect((x_batt - 60, base - h_batt), (x_batt + 60, base), v.TEAL, 0.35)
    p.stroke([(x_batt - 60, base - h_batt), (x_batt + 60, base - h_batt)], v.TEAL, 2.4, 0.9, 12, 0.5)
    p.fill_rect((x_emf - 60, base - h_emf), (x_emf + 60, base), v.AMBER, 0.35)
    p.stroke([(x_emf - 60, base - h_emf), (x_emf + 60, base - h_emf)], v.AMBER, 2.4, 0.9, 12, 0.5)
    # 电压墙（母线）
    wall = base - h_batt - 30
    p.stroke([(620, wall), (1500, wall)], v.EMBER, 3.0, 0.9, 14, 0.5)
    # 回收电流箭头被墙顶住
    cxa = 1450.0
    p.stroke([(cxa, base - 100), (cxa, wall + 60)], v.TEAL, 3.0, 0.6, 10, 0.5)
    p.stroke([(cxa - 14, wall + 80), (cxa, wall + 52), (cxa + 14, wall + 80)], v.TEAL, 3.0, 0.6)
    p.stroke([(cxa - 20, wall + 52), (cxa + 20, wall + 52)], v.EMBER, 4.0, 0.95)
    p.flush()
    txt(p, "电池电压", (x_batt, base + 40), 24, v.TEAL, v.F_SANS_R, "mm", 0.85, track=2)
    txt(p, "电机反电动势", (x_emf, base + 40), 24, v.AMBER, v.F_SANS_R, "mm", 0.85, track=2)
    txt(p, "母线电压墙", (630, wall - 22), 24, v.EMBER_P, v.F_SANS_R, "lm", 0.85, track=2)
    a = ramp(t, dur * 0.55, dur * 0.9)
    txt(p, "反电动势顶住", (960, 236), 42, v.BONE, v.F_SANS, "mm", 0.9, track=4)
    txt(p, "车速越高，反电动势越高，回收力矩越受限（F15）", (960, 884), 28, v.MUTED,
        v.F_SANS_R, "mm", a, track=2)
    return finish(p)


def scene_power_limit_sliders(t, dur, sh=None):
    """S51：SOC / 温度 / 倍率 三滑块把回收功率压住。"""
    b = bg(v.AMBER, 0.06)
    p = v.Painter(b)
    # 顶部：回收功率条（被逐次下压）
    x0, x1, y = 360.0, 1560.0, 380.0
    p.fill_rect((x0, y - 26), (x1, y + 26), v.LINE, 0.45)
    p.flush()
    # 三个滑块：依次从 1.0 压到 0.45/0.55/0.60
    sliders = (("电量 SOC", 0.45, 400.0), ("电池温度", 0.55, 560.0), ("充电倍率", 0.60, 720.0))
    vals = []
    for i, (lab, v_target, sy) in enumerate(sliders):
        a = ramp(t, 0.4 + i * 0.7, 1.0 + i * 0.7)
        vv = v.lerp(1.0, v_target, a)
        vals.append(vv)
        p.stroke([(x0, sy), (x1, sy)], v.LINE, 3.0, 0.5)
        xx = x0 + (x1 - x0) * vv
        p.dot((xx, sy), 13, v.AMBER, 0.95, glow=16)
        txt(p, lab, (x0 - 24, sy), 26, v.MUTED, v.F_SANS_R, "rm", a * 0.9, track=1)
        chip_txt = "收紧" if vv < 0.9 else "放宽"
        txt(p, chip_txt, (x1 + 24, sy), 24, v.AMBER if vv < 0.9 else v.MUTED,
            v.F_SANS_R, "lm", a * 0.75, track=1)
    cap = min(vals) if vals else 1.0
    a = ramp(t, dur * 0.6, dur * 0.9)
    p.fill_rect((x0, y - 26), (x0 + (x1 - x0) * cap, y + 26), v.EMBER, 0.55 * a)
    p.flush()
    txt(p, "回收功率上限", (960, 280), 28, v.BONE, v.F_SANS_R, "mm", 0.85, track=2)
    txt(p, "三重上限，谁最低听谁的", (960, 884), 30, v.MUTED, v.F_SANS_R, "mm", a, track=2)
    return finish(p)


def scene_condition_fold(t, dur, sh=None):
    """S52：「看条件的账」：条件卡合上，只留回收通道图（卡片提亮可读）。"""
    b = bg(v.TEAL, 0.08)
    p = v.Painter(b)
    fold = ramp(t, 0.4, dur * 0.85)
    cards = (("① 满电", 380.0), ("② 低温", 540.0), ("③ 高速", 700.0), ("④ 抓地力", 860.0))
    for i, (lab, cy) in enumerate(cards):
        w = v.lerp(200.0, 0.0, fold)
        h = v.lerp(86.0, 0.0, fold)
        if w > 2:
            x0, y0, x1, y1 = 960 - w / 2, cy - h / 2, 960 + w / 2, cy + h / 2
            p.fill_rect((x0, y0), (x1, y1), (179, 57, 46), 0.06)
            p.stroke([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], (232, 132, 112), 2.4,
                     0.95 * (1 - fold * 0.5), 12, 0.5, closed=True)
    p.flush()
    if fold < 0.7:
        for i, (lab, cy) in enumerate(cards):
            yy = v.lerp(cy, 620.0, fold)
            txt(p, lab, (960, yy), 34, (255, 178, 158), v.F_SANS, "mm", (1 - fold),
                track=3)
    # 留下通道图
    a = ramp(t, dur * 0.6, dur * 0.95)
    if a > 0.02:
        for x in (420.0, 760.0, 1100.0, 1440.0):
            p.dot((x, 700), 10, v.TEAL, a * 0.95, glow=16)
        p.stroke([(420, 700), (1440, 700)], v.TEAL, 2.4, a * 0.7, 12, 0.5)
        p.flush()
        for lab, x in (("轮端", 420.0), ("电机", 760.0), ("逆变器", 1100.0), ("电池", 1440.0)):
            txt(p, lab, (x, 762), 26, v.BONE if x > 700 else v.MUTED, v.F_SANS_R, "mm",
                a * 0.95, track=2)
    txt(p, "条件不对，就不收", (960, 884), 34, v.BONE, v.F_SANS, "mm", a, track=3)
    txt(p, "回收是看条件的账", (960, 236), 38, v.BONE, v.F_SANS, "mm", 0.95, track=3)
    return finish(p)


# ================================================================ S6 再判
def scene_blend_curves(t, dur, sh=None):
    """S54：混合制动：回收与机械刹车怎么分（串行/并行）。"""
    b = bg(v.TEAL, 0.07)
    p = v.Painter(b)
    x0, x1, y0, y1 = 400.0, 1560.0, 740.0, 340.0
    axes(p, x0, y0, x1, y1)
    p.flush()
    # x 轴：制动需求；y 轴：制动力
    xs = np.linspace(0, 1, 120)
    regen = np.minimum(1.0, xs / 0.55) * 0.62
    friction = np.clip((xs - 0.42) / 0.58, 0, 1) * 0.55
    total = regen + friction
    def to_scr(xx, yy):
        return (x0 + xx * (x1 - x0), y0 - yy * (y0 - y1))
    grow = ramp(t, 0.3, dur * 0.9)
    n = max(2, int(len(xs) * grow))
    pr = [to_scr(xs[i], regen[i]) for i in range(n)]
    pf = [to_scr(xs[i], friction[i]) for i in range(n)]
    pt = [to_scr(xs[i], min(1.0, total[i])) for i in range(n)]
    if len(pr) > 1:
        p.stroke(np.array(pr, np.float32), v.TEAL, 3.0, 0.9, 12, 0.5)
        p.stroke(np.array(pf, np.float32), v.AMBER, 3.0, 0.9, 12, 0.5)
        p.stroke(np.array(pt, np.float32), v.BONE, 2.0, 0.7)
    p.flush()
    txt(p, "回收制动力", (x0 + 130, y0 - 240), 22, v.TEAL, v.F_SANS_R, "lm", 0.85, track=1)
    txt(p, "机械制动力", (x0 + 620, y0 - 240), 22, v.AMBER, v.F_SANS_R, "lm", 0.85, track=1)
    txt(p, "制动需求 →", (x1 - 140, y0 - 60), 22, v.MUTED, v.F_SANS_R, "lm", 0.8, track=1)
    txt(p, "混合制动 Blending", (960, 236), 38, v.BONE, v.F_SANS, "mm", 0.9, track=3)
    txt(p, "先回收，不够再上机械刹车：叠加，不是替代", (960, 884), 30, v.MUTED,
        v.F_SANS_R, "mm", ramp(t, dur * 0.6, dur * 0.95), track=2)
    return finish(p)


def scene_style_curves(t, dur, sh=None):
    """S61：提前松油门 vs 到跟前重刹：回收功率曲线对比。"""
    b = bg(v.TEAL, 0.07)
    p = v.Painter(b)
    x0, x1, y0, y1 = 400.0, 1560.0, 740.0, 360.0
    axes(p, x0, y0, x1, y1)
    p.flush()
    # 两条回收功率曲线：早松（宽缓）/ 重刹（窄尖）
    def early(x):
        return np.exp(-((x - 0.42) ** 2) / (2 * 0.20 ** 2)) * 0.55
    def lateb(x):
        return np.exp(-((x - 0.74) ** 2) / (2 * 0.055 ** 2)) * 0.9
    xs = np.linspace(0, 1, 160)
    def scr(xx, yy):
        return (x0 + xx * (x1 - x0), y0 - yy * (y0 - y1))
    grow = ramp(t, 0.3, dur * 0.9)
    n = max(2, int(len(xs) * grow))
    pe = np.array([scr(xs[i], early(xs[i])) for i in range(n)], np.float32)
    pl = np.array([scr(xs[i], lateb(xs[i])) for i in range(n)], np.float32)
    # 面积差高亮（早松的累积回收更多）
    p.stroke(pe, v.TEAL, 3.4, 0.95, 14, 0.6)
    p.stroke(pl, v.AMBER, 3.0, 0.9, 14, 0.6)
    p.flush()
    txt(p, "提前松", (x0 + 250, y1 + 60), 26, v.TEAL, v.F_SANS_R, "lm", 0.9, track=2)
    txt(p, "到跟前重刹", (x0 + 900, y1 + 40), 26, v.AMBER, v.F_SANS_R, "lm", 0.9, track=2)
    a = ramp(t, dur * 0.6, dur * 0.95)
    txt(p, "提前松，收得多", (960, 236), 40, v.BONE, v.F_SANS, "mm", 0.9, track=3)
    txt(p, "越急，回收越少；窗口越宽，收得越多", (960, 884), 30, v.MUTED, v.F_SANS_R,
        "mm", a, track=2)
    return finish(p)


def scene_bars_compare(t, dur, sh=None):
    """S62：急与缓：回收量柱状对比，差距缩小。"""
    b = bg(v.TEAL, 0.07)
    p = v.Painter(b)
    base = 740.0
    bars = (("提前松", 0.72, v.TEAL, 700.0), ("到跟前重刹", 0.34, v.AMBER, 1150.0))
    for i, (lab, h, col, bx) in enumerate(bars):
        a = ramp(t, 0.3 + i * 0.4, dur * 0.75 + i * 0.2)
        hh = (base - 320) * h * a
        p.fill_rect((bx - 110, base - hh), (bx + 110, base), col, 0.32)
        p.stroke([(bx - 110, base - hh), (bx + 110, base - hh), (bx + 110, base),
                  (bx - 110, base)], col, 2.2, 0.9, 12, 0.5, closed=True)
        txt(p, lab, (bx, base + 56), 30, v.BONE, v.F_SANS_R, "mm", 0.9, track=2)
        txt(p, "相对更多" if i == 0 else "相对更少", (bx, base - hh - 30), 26, col,
            v.F_SANS_R, "mm", a, glow=10)
    p.flush()
    # 差距标注
    a = ramp(t, dur * 0.6, dur * 0.95)
    txt(p, "差距", (925, 380), 26, v.MUTED, v.F_SANS_R, "mm", a, track=2)
    txt(p, "越急，收得越少", (960, 884), 34, v.BONE, v.F_SANS, "mm", a, track=3)
    txt(p, "同样一次减速，回收量相对对比 · 示意（非实测）", (960, 236), 28, v.MUTED,
        v.F_SANS_R, "mm", 0.8, track=2)
    return finish(p)


# ================================================================ S7 收束
def scene_chain_reprise(t, dur, sh=None):
    """S63：回到母题：可逆能量通道图，能量点在两端往返（速度放缓）。"""
    b = bg(v.TEAL, 0.12)
    p = v.Painter(b)
    draw_chain(p, t=t * 0.7, direction=1, flow=0.65, active=None, y=CH_Y, soc=0.62,
               labels=True, heat=0.0)
    p.flush()
    # 两端往返的能量点
    a = ramp(t, 0.3, dur * 0.6)
    x_from, x_to = CH_X[0] + 130, CH_X[3] - 130
    u = 0.5 + 0.5 * math.sin(t * 1.6 - math.pi / 2)
    x = v.lerp(x_from, x_to, u)
    p.halo((x, CH_Y), 34, v.TEAL, 0.35 * a)
    p.dot((x, CH_Y), 9, v.TEAL_P, 0.95 * a, glow=22)
    p.flush()
    txt(p, "不是魔法", (960, 236), 40, v.BONE, v.F_SANS, "mm", a, track=4)
    txt(p, "能量点只是换了个方向走", (960, 884), 30, v.MUTED, v.F_SANS_R, "mm", a, track=2)
    return finish(p)


def scene_chain_store(t, dur, sh=None):
    """S64：同样的动能，被「换了个方向」存回电池（能量点拐弯进入电池）。"""
    b = bg(v.TEAL, 0.12)
    p = v.Painter(b)
    draw_chain(p, t=t * 0.6, direction=1, flow=0.8, active="battery", y=CH_Y, soc=0.66,
               labels=True, heat=0.0)
    p.flush()
    # 能量点从轮端出发，沿通道进入电池，最后在电池处蓄光
    u = ramp(t, 0.3, dur * 0.85)
    x = v.lerp(CH_X[0] + 130, CH_X[3], min(1.0, u * 1.15))
    y = CH_Y + 10 * math.sin(u * math.pi * 3) * (1 - u)
    p.dot((x, y), 8, v.TEAL_P, 0.95, glow=22)
    if u > 0.85:
        p.halo((CH_X[3], CH_Y), 90 * (u - 0.85) / 0.15, v.TEAL, 0.45)
    p.flush()
    a = ramp(t, dur * 0.5, dur * 0.9)
    txt(p, "换方向，存回去", (960, 236), 40, v.BONE, v.F_SANS, "mm", a, track=4)
    txt(p, "同样的动能，换个方向就是充电", (960, 884), 30, v.MUTED, v.F_SANS_R, "mm", a,
        track=2)
    return finish(p)


def scene_quote_card(t, dur, sh=None):
    """S65：金句卡：回收的是能量，也是判断。"""
    b = np.zeros((H, W, 3), np.float32) + 0.012
    p = v.Painter(b)
    # 极细的一根能量线作底
    p.stroke([(560, 700), (1360, 700)], v.TEAL, 1.2, 0.18, 6, 0.4)
    p.flush()
    a = ramp(t, 0.4, dur * 0.8)
    txt(p, "回收的是能量", (960, 430), 84, v.BONE, v.F_SERIF, "mm", a, track=6)
    a2 = ramp(t, dur * 0.35, dur * 0.8)
    txt(p, "也是判断", (960, 560), 84, v.TEAL, v.F_SERIF, "mm", a2, track=8, glow=16 * a2)
    return finish(p, vig=0.22, grain=0.012)


def scene_end_card(t, dur, sh=None):
    """S67：片尾声明卡（双声明）。"""
    b = np.zeros((H, W, 3), np.float32) + 0.010
    p = v.Painter(b)
    # 顶部细题
    a = ramp(t, 0.2, 1.2)
    txt(p, "第 08 期 ｜ 电动车松开油门为什么能充电", (960, 300), 28, v.MUTED, v.F_SANS_R,
        "mm", a * 0.85, track=3)
    # 两条声明（画面卡）
    a1 = ramp(t, 0.6, 1.6)
    txt(p, "本片画面与配音含 AI 辅助制作", (960, 470), 52, v.BONE, v.F_SANS, "mm", a1,
        track=3)
    a2 = ramp(t, 1.4, 2.4)
    txt(p, "选题、核实与判断，由人完成", (960, 600), 52, v.BONE, v.F_SANS, "mm", a2,
        track=3)
    # 底部系列标识
    a3 = ramp(t, 2.4, 3.4)
    txt(p, "vibe 知识共赏", (960, 800), 24, v.DIM, v.F_MONO, "mm", a3, track=6)
    p.flush()
    return finish(p, vig=0.18, grain=0.010)


# ================================================================ 混合镜降级（H3 缺失时）
def _fallback_scene(name):
    """H3 素材缺失时的降级场景：冷灰工程底 + 抽象能量流动纹理 + 该镜叠加层信息。

    不黑屏、信息不丢；用缓慢的能量点/光带/斜线纹理避免「空画面」，
    与全片母题（可逆能量通道）一致。
    """
    def fn(t, dur, sh=None):
        try:
            import overlays
            fnover = overlays.OVERLAYS.get(name)
        except Exception:
            fnover = None
        b = bg(v.TEAL, 0.11)
        p = v.Painter(b)
        # 抽象能量带：一条贯穿画面的柔光通道
        yc = 620.0
        p.stroke([(120, yc), (1800, yc)], v.TEAL, 26.0, 0.045)
        p.stroke([(120, yc), (1800, yc)], v.TEAL, 2.0, 0.18, 18, 0.45)
        # 缓慢漂移的斜向纹理
        for k in range(7):
            x = 120 + ((k * 270 + t * 38) % 1680)
            p.stroke([(x, 300), (x + 150, 860)], v.MUTED, 1.2, 0.08)
        # 能量点（沿通道往返，方向随位置：左→右）
        for k in range(9):
            u = (t * 0.16 + k / 9.0) % 1.0
            x = v.lerp(160, 1760, u)
            y = yc + 34 * math.sin(u * math.pi * 2 + t * 0.7 + k)
            p.dot((x, y), 2.6 + 1.2 * math.sin(t * 1.3 + k), v.TEAL, 0.32, glow=10)
        # 上下少量冷光点
        for k in range(5):
            x = 260 + ((k * 380 + t * 22) % 1500)
            y = 340 + 90 * math.sin(k + t * 0.5)
            p.dot((x, y), 1.8, v.ICE, 0.18)
        p.flush()
        if fnover:
            try:
                o = v.OverlayPainter()
                fnover(t, dur, o, sh)
                img = o.image()
                arr = np.asarray(p.to_image(), np.float32) / 255.0
                ov = np.asarray(img, np.float32) / 255.0
                a = ov[..., 3:4]
                arr = arr * (1 - a) + ov[..., :3] * a
                p.rgb = arr.astype(np.float32)
            except Exception as e:  # pragma: no cover
                print("[scene] fallback overlay fail", name, e, flush=True)
        return finish(p)
    return fn


# ================================================================ S01 钩子（纯代码，C1）
def scene_hook_power_flip(t, dur, sh=None):
    """S01：功率表从「放电」翻到「回收」——片头 5 秒钩子（纯代码，无 H3）。

    口径（facts §7.1）：不出现具体功率 kW、不出现未列来源的电量数字；
    钩子靠「松油门 / 车在充电 / 能量倒着走」成立。
    """
    b = bg(v.TEAL, 0.12, cx=0.42, cy=0.5)
    p = v.Painter(b)
    cx, cy, R = 760.0, 545.0, 268.0
    p.stroke([v.polar(cx, cy, R, d) for d in np.arange(150, 391, 1.5)], v.LINE, 12.0, 0.6)
    p.stroke([v.polar(cx, cy, R, d) for d in np.arange(150, 271, 1.5)], v.AMBER, 10.0, 0.20)
    p.stroke([v.polar(cx, cy, R, d) for d in np.arange(270, 391, 1.5)], v.TEAL, 10.0, 0.26)
    for k in range(21):
        deg = 150 + 12 * k
        big = 1.0 if k % 5 == 0 else 0.55
        p.stroke([v.polar(cx, cy, R - 12, deg),
                  v.polar(cx, cy, R + (14 if big > 0.7 else 8), deg)],
                 v.MUTED, 1.8 if big > 0.7 else 1.2, 0.6 * big)
    swing = ramp(t, 1.1, min(dur - 0.3, 2.9))
    deg = v.lerp(150 + 240 * 0.78, 150 + 240 * 0.18, swing)
    col = v.TEAL if swing > 0.55 else v.AMBER
    p.stroke([v.polar(cx, cy, R - 42, deg), v.polar(cx, cy, 14, deg)], col, 5.0, 1.0, 18, 0.6)
    p.dot((cx, cy), 11, col, 1.0, glow=22)
    back = ramp(t, 1.5, min(dur - 0.2, 3.4))
    for k in range(3):
        yy = cy - 60 + k * 60
        x0, x1 = 1290.0, 1590.0
        p.stroke([(x0, yy), (v.lerp(x0, x1, back), yy)], v.TEAL, 2.6, 0.85 * back, 12, 0.5)
        if back > 0.15:
            xe = v.lerp(x0, x1, back)
            p.stroke([(xe - 16, yy - 12), (xe, yy), (xe - 16, yy + 12)], v.TEAL, 2.6,
                     0.85 * back)
    p.flush()
    v.draw_text(p.rgb, "放电", (cx - 150, cy - 150), 24, v.AMBER if swing < 0.5 else v.DIM,
                v.F_SANS_R, "mm", 0.75, track=3)
    v.draw_text(p.rgb, "回收", (cx + 150, cy - 150), 24, v.TEAL if swing > 0.5 else v.DIM,
                v.F_SANS_R, "mm", 0.8, track=3)
    v.draw_text(p.rgb, "方向反了", (cx, cy + 96), 30, col, v.F_SANS_R, "mm", 0.9 * back,
                track=3)
    a = back
    v.draw_text(p.rgb, "动能回收", (1470, 360), 30, v.MUTED, v.F_SANS_R, "mm", 0.85, track=3)
    v.draw_text(p.rgb, "能量倒着走", (1470, 452), 52, v.TEAL, v.F_SANS, "mm", a, track=3,
                glow=14 * a)
    for k in range(5):
        xx = v.lerp(1560, 1210, ((t * 0.6 + k * 0.2) % 1.0))
        p.dot((xx, 540 + (k % 2) * 26), 3.4, v.TEAL, a * 0.8, glow=12)
    p.flush()
    v.draw_text(p.rgb, "仪表上，能量在往回走", (1470, 640), 28, v.BONE, v.F_SANS_R,
                "mm", 0.9 * a, track=2)
    v.draw_text(p.rgb, "松油门", (330, 756), 88, v.BONE, v.F_SANS, "mm", 0.95, track=5)
    v.draw_text(p.rgb, "车在充电", (330, 852), 88, v.TEAL, v.F_SANS, "mm", 0.95, track=5,
                glow=18)
    return finish(p)


# ================================================================ S11 充电 vs 回收
def scene_word_correct(t, dur, sh=None):
    """S11：「充电」与「回收」两个词并列，后者被红框圈住。"""
    b = bg(v.TEAL, 0.07)
    p = v.Painter(b)
    a = ramp(t, 0.2, 0.9)
    txt(p, "充电", (700, 500), 96, v.MUTED, v.F_SANS, "mm", a, track=6)
    a2 = ramp(t, 0.55, 1.3)
    txt(p, "回收", (1240, 500), 96, v.TEAL, v.F_SANS, "mm", a2, track=6, glow=14 * a2)
    s = ramp(t, dur * 0.45, dur * 0.85)
    if s > 0:
        w = 220 * s
        p.stroke(v._rounded_rect_pts(1240 - w, 400, 1240 + w, 600, 20), v.EMBER, 4.0,
                 0.95, 16, 0.5)
        p.flush()
    txt(p, "准确说法不是充电，是回收", (960, 780), 36, v.BONE, v.F_SANS_R, "mm",
        ramp(t, dur * 0.55, dur * 0.95), track=2)
    txt(p, "电不是“发”出来的，是把动能收回来", (960, 884), 28, v.MUTED, v.F_SANS_R,
        "mm", a2 * 0.9, track=2)
    return finish(p)


SCENES = {
    # S1
    "hook_power_flip": scene_hook_power_flip,
    "word_strike_motor": scene_word_strike_motor,
    "chain_lightup": scene_chain_lightup,
    # S2
    "chain_drive": scene_chain_drive,
    "motor_swap": scene_motor_swap,
    "word_swap": scene_word_swap,
    "word_correct": scene_word_correct,
    "bucket_limit": scene_bucket_limit,
    "word_strike_more": scene_word_strike_more,
    # S3
    "three_place": scene_three_place,
    "motor_current": scene_motor_current,
    "inverter_door": scene_inverter_door,
    "wave_forward": scene_wave_forward,
    "wave_reverse": scene_wave_reverse,
    "switches": scene_switches,
    "chain_final": scene_chain_final,
    "chain_bidir": scene_chain_bidir,
    "arrow_flip": scene_arrow_flip,
    "chain_reverse": scene_chain_reverse,
    # S4
    "formula_appear": scene_formula_appear,
    "formula_substitute": scene_formula_substitute,
    "result_016": scene_result_016,
    "quadratic_curve": scene_quadratic_curve,
    "chain_loss_bar": scene_chain_loss_bar,
    "eff_gauge_regen": scene_eff_gauge_regen,
    "eff_bars_compare": scene_eff_bars_compare,
    "eff_diff": scene_eff_diff,
    "sankey_loss": scene_sankey_loss,
    "aero_drag": scene_aero_drag,
    "highway_share": scene_highway_share,
    "downhill_numbers": scene_downhill_numbers,
    # S5
    "limits_quad": scene_limits_quad,
    "limit_full": scene_limit_full,
    "lithium_plating": scene_lithium_plating,
    "tach_high": scene_tach_high,
    "back_emf_wall": scene_back_emf_wall,
    "power_limit_sliders": scene_power_limit_sliders,
    "condition_fold": scene_condition_fold,
    # S6
    "blend_curves": scene_blend_curves,
    "style_curves": scene_style_curves,
    "bars_compare": scene_bars_compare,
    # S7
    "chain_reprise": scene_chain_reprise,
    "chain_store": scene_chain_store,
    "quote_card": scene_quote_card,
    "end_card": scene_end_card,
}


# 混合镜降级场景注册：SCENES["fb_<overlay>"] = 冷灰底 + 该镜叠加层
try:
    import overlays as _ovl
    for _name in _ovl.OVERLAYS:
        SCENES["fb_" + _name] = _fallback_scene(_name)
except Exception as _e:  # pragma: no cover
    print("[scene] fallback scenes 注册失败:", _e, flush=True)
