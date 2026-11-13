#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 06 期数据层叠加器：压在 ComfyUI 角色/道具镜头与 B-roll 上的细线数据层。

约定：每个函数签名 `def ov_xxx(t, dur, o, sh)`，t 为镜头内局部时间（秒），
o 为 ep06viz.OverlayPainter，sh 为 shots.json 的镜头 dict。函数只画 RGBA 叠加层，
最终由 finalize 统一调色/颗粒/遮幅/字幕。

设计：薄线 + 柔光 + 等宽数字，不做灰底图表卡；文字下用柔和的深色 scrim 提升压片可读性。
CJK 一律走 F_SANS_R / F_SANS / F_SERIF；F_MONO 只用于数字/公式。
花字配额在 scenes_pil.py（13438 / 12445 / 123万 / 9.7% 共 4 处），本文件里的数字是次级数据层。
"""
import math

import numpy as np

import ep06viz as V
from ep06viz import (W, H, BONE, MUTED, DIM, GOLD, AMBER, ICE, WHITE, STEEL, STEEL_D,
                     PAPER, GOLD_D, RED_SEAL, RED_D, F_SANS, F_SANS_R, F_SERIF,
                     F_MONO, INK, clamp, ease_in_out, ease_out_cubic, smoothstep,
                     window, lerp, text_size,
                     V_IDEAL_ONE_2021_11, V_VW_FIVE_2021_11, V_DIFF_2021_11,
                     YO_Y_2026_JAN_MAY, YO_Y_2026_MAY, SHARE_2025_05, SHARE_2026_05,
                     TALLY, count_up, grow_progress, seal_drop, ink_bleed, pct_str)

TEXT2 = (198, 208, 214)


# ------------------------------------------------------------------ helpers
def hud_label(o, text, xy, size=28, color=TEXT2, alpha=1.0, anchor="lm", track=1.5,
              stroke=2):
    o.text(text, xy, size, color=color, font=F_SANS_R, anchor=anchor, alpha=alpha,
           track=track, stroke=stroke, stroke_color=(0, 0, 0))


def mono(o, text, xy, size=30, color=TEXT2, alpha=1.0, anchor="lm", track=0.5,
         glow=0.0, glow_strength=0.45):
    o.text(text, xy, size, color=color, font=F_MONO, anchor=anchor, alpha=alpha,
           track=track, stroke=1, stroke_color=(0, 0, 0), glow=glow,
           glow_strength=glow_strength)


def mixed(o, parts, xy, size, anchor="lm", alpha=1.0, track=0.0, glow=0.0,
          glow_strength=0.45):
    total = 0.0
    widths = []
    for text, color, font in parts:
        w = text_size(text, size, font, stroke=1, track=track)[0]
        widths.append(w)
        total += w
    x = xy[0]
    if anchor == "rm":
        x -= total
    elif anchor == "mm":
        x -= total * 0.5
    for (text, color, font), w in zip(parts, widths):
        o.text(text, (x, xy[1]), size, color=color, font=font, anchor="lm",
               alpha=alpha, track=track, stroke=1, stroke_color=(0, 0, 0),
               glow=glow, glow_strength=glow_strength)
        x += w
    return total


def scrim(o, xy, r=280, alpha=0.32, color=(3, 5, 8)):
    if alpha > 0.004:
        o.glow(xy, r=r, color=color, alpha=clamp(alpha))


def rule(o, x0, x1, y, t, t0, t1, color=GOLD, alpha=0.55, width=1.2):
    a = window(t, t0, t1, 0.25, 0.3)
    if a <= 0:
        return
    x = lerp(x0, x1, ease_out_cubic(clamp((t - t0) / max(1e-3, t1 - t0))))
    o.stroke([(x0, y), (x, y)], color, width, alpha * a)


# ------------------------------------------------------------------ 第一幕 判决
def ov_verdict_stamp(t, dur, o, sh):
    """红色盖章式「判决」：印章环砸下 + 红字 + 日期（压 C3/C10 盖章/红印镜头）。"""
    t0 = dur * 0.30
    scale, alpha = seal_drop(t, t0)
    if alpha <= 0.01:
        return
    cx, cy = 1206.0, 512.0
    r = 118.0 * scale
    bleed = ink_bleed(t, t0, 1.6)
    # 柔和暗底（让红印从画面里浮出）
    scrim(o, (cx, cy), 260, 0.26 * alpha)
    # 印泥洇开的柔光
    o.glow((cx, cy), r=int(r * 1.55), color=RED_SEAL, alpha=0.22 * bleed * alpha)
    # 印章双环（手绘质感的圆：两圈 + 若干缺口）
    for rr, w, a in ((r, 5.0, 0.92), (r * 0.90, 1.8, 0.60)):
        th = np.linspace(0, 2 * math.pi, 96)
        pts = np.stack([cx + rr * np.cos(th), cy + rr * np.sin(th)], 1)
        o.stroke(pts, RED_SEAL, w, a * alpha)
    # 印面缺口（不规则，像真印章）
    for k in range(7):
        ang = 2 * math.pi * k / 7 + 0.4
        o.stroke([(cx + r * 0.93 * math.cos(ang), cy + r * 0.93 * math.sin(ang)),
                  (cx + r * 1.02 * math.cos(ang), cy + r * 1.02 * math.sin(ang))],
                 RED_D, 2.0, 0.5 * alpha)
    # 中心「判决」
    o.text("判决", (cx, cy - 6), int(58 * scale), color=RED_SEAL, font=F_SANS,
           anchor="mm", alpha=0.95 * alpha, track=int(8 * scale),
           stroke=0)
    o.text("2020.09.08", (cx, cy + 58 * scale), int(20 * scale), color=RED_SEAL,
           font=F_MONO, anchor="mm", alpha=0.62 * alpha, track=2)
    # 溅出的细小印泥点
    rng = np.random.default_rng(906)
    for k in range(9):
        ang = rng.uniform(0, 2 * math.pi)
        dd = r * rng.uniform(1.10, 1.34)
        rr2 = rng.uniform(1.2, 2.8)
        o.dot((cx + dd * math.cos(ang), cy + dd * math.sin(ang)), rr2, RED_SEAL,
              rng.uniform(0.25, 0.55) * bleed * alpha)
    # 小字：最糟糕的方案（红）
    a2 = clamp((t - t0 - 0.30) / 0.5)
    if a2 > 0:
        hud_label(o, "「最糟糕的方案」", (cx, cy + r + 74), 26, RED_SEAL,
                  0.85 * a2, anchor="mm", track=2)


# ------------------------------------------------------------------ 数据层：销量
def ov_num_13438(t, dur, o, sh):
    """13,438 台 callout（数字滚动；压女性点平板/账本特写）。"""
    x, y = 252.0, 676.0
    a = clamp((t - 0.18) / 0.5)
    if a <= 0:
        return
    scrim(o, (x + 240, y - 10), 330, 0.40 * a)
    hud_label(o, "理想 ONE · 2021-11 单月上险", (x, y - 84), 24, TEXT2, 0.82 * a,
              track=2)
    n = count_up(t, 0.18, 1.05, V_IDEAL_ONE_2021_11)
    mono(o, "{:,}".format(n), (x, y), 76, GOLD, 0.97 * a, glow=16, glow_strength=0.5)
    mixed(o, [("台", TEXT2, F_SANS_R)], (x + 300, y - 20), 26, alpha=0.8 * a)
    rule(o, x, x + 380, y + 44, t, 0.25, 0.9, GOLD, 0.5, 1.1)


def ov_num_12445(t, dur, o, sh):
    """12,445 台 callout（大众五款合计；压账本/桌面镜头）。"""
    x, y = 1668.0, 676.0
    a = clamp((t - 0.18) / 0.5)
    if a <= 0:
        return
    scrim(o, (x - 240, y - 10), 330, 0.40 * a)
    hud_label(o, "大众五款中大型 SUV · 同期上险合计", (x, y - 84), 24, TEXT2,
              0.82 * a, anchor="rm", track=2)
    n = count_up(t, 0.18, 1.05, V_VW_FIVE_2021_11)
    mono(o, "{:,}".format(n), (x, y), 70, STEEL, 0.95 * a, anchor="rm", glow=14,
         glow_strength=0.45)
    mixed(o, [("台", TEXT2, F_SANS_R)], (x, y - 20), 26, anchor="rm", alpha=0.8 * a)
    rule(o, x - 380, x, y + 44, t, 0.25, 0.9, STEEL, 0.5, 1.1)


def ov_num_993(t, dur, o, sh):
    """「还差 993 台」：差值单独落下（细线 + 等宽数字）。"""
    a = clamp((t - 0.10) / 0.45)
    if a <= 0:
        return
    cx, cy = 960.0, 752.0
    scrim(o, (cx, cy), 300, 0.34 * a)
    drop = (1.0 - ease_out_cubic(clamp((t - 0.10) / 0.5))) * 18
    mixed(o, [("还差 ", TEXT2, F_SANS_R), ("993", GOLD, F_MONO), (" 台", TEXT2, F_SANS_R)],
          (cx, cy - drop), 44, anchor="mm", alpha=0.95 * a, glow=10)
    # 两根细线：一根停住、一根继续（用长度差表达 993）
    x0, x1 = cx - 250, cx + 250
    p1 = ease_out_cubic(clamp((t - 0.10) / 0.6))
    o.stroke([(x0, cy + 66), (x0 + 500 * p1, cy + 66)], GOLD, 1.6, 0.55 * a, 6, 0.3)
    o.stroke([(x0, cy + 86), (x0 + 462 * p1, cy + 86)], STEEL, 1.6, 0.45 * a, 6, 0.3)


# ------------------------------------------------------------------ 数据层：退潮
def ov_drop_97(t, dur, o, sh):
    """-9.7% callout（2026 年 1–5 月累计同比）。"""
    x, y = 252.0, 620.0
    a = clamp((t - 0.22) / 0.6)
    if a <= 0:
        return
    scrim(o, (x + 210, y - 10), 300, 0.40 * a)
    hud_label(o, "2026 年 1–5 月 · 累计", (x, y - 78), 24, TEXT2, 0.82 * a, track=2)
    mono(o, pct_str(YO_Y_2026_JAN_MAY), (x, y), 72, AMBER, 0.97 * a,
         glow=16, glow_strength=0.5)
    hud_label(o, "同比", (x + 250, y - 22), 26, TEXT2, 0.8 * a, track=2)
    # 下行细线
    p = ease_in_out(clamp((t - 0.35) / 1.0))
    if p > 0:
        o.stroke([(x + 20, y + 56), (x + 20 + 300 * p, y + 56 + 52 * p)], AMBER,
                 1.6, 0.55 * a, 8, 0.35)


def ov_drop_249(t, dur, o, sh):
    """-24.9% callout（2026 年 5 月单月批发同比）。"""
    x, y = 1668.0, 600.0
    a = clamp((t - 0.22) / 0.6)
    if a <= 0:
        return
    scrim(o, (x - 230, y - 10), 310, 0.40 * a)
    hud_label(o, "2026 年 5 月 · 单月批发", (x, y - 86), 24, TEXT2, 0.82 * a,
              anchor="rm", track=2)
    mono(o, pct_str(YO_Y_2026_MAY), (x, y), 78, AMBER, 0.97 * a, anchor="rm",
         glow=18, glow_strength=0.5)
    hud_label(o, "同比", (x, y - 26), 26, TEXT2, 0.8 * a, anchor="rm", track=2)
    p = ease_in_out(clamp((t - 0.35) / 1.0))
    if p > 0:
        o.stroke([(x - 20, y + 58), (x - 20 - 300 * p, y + 58 + 56 * p)], AMBER,
                 1.6, 0.55 * a, 8, 0.35)


def ov_share_shift(t, dur, o, sh):
    """份额 10.3% → 7.0%：两枚数字 + 一段下行细线。"""
    a = clamp((t - 0.25) / 0.6)
    if a <= 0:
        return
    x0, x1, y0, y1 = 1120.0, 1560.0, 470.0, 620.0
    scrim(o, ((x0 + x1) / 2, (y0 + y1) / 2 + 30), 340, 0.36 * a)
    hud_label(o, "增程份额 · 2025-05 → 2026-05", (x0, y0 - 58), 24, TEXT2, 0.82 * a,
              track=2)
    p = ease_in_out(clamp((t - 0.30) / 1.1))
    if p > 0:
        o.stroke([(x0, y0), (x0 + (x1 - x0) * p, y0 + (y1 - y0) * p)], AMBER,
                 2.4, 0.9 * a, 12, 0.5)
        o.dot((x0 + (x1 - x0) * p, y0 + (y1 - y0) * p), 4.5, AMBER, 0.9 * a, 10, 0.6)
    mono(o, pct_str(SHARE_2025_05), (x0 + 6, y0 - 26), 46, STEEL, 0.95 * a,
         glow=10, glow_strength=0.35)
    a2 = clamp((t - 0.85) / 0.6)
    if a2 > 0:
        mono(o, pct_str(SHARE_2026_05), (x1 + 6, y1 - 30), 50, AMBER, 0.96 * a2,
             anchor="rm", glow=12, glow_strength=0.4)


# ------------------------------------------------------------------ 2:1:1 胜负标记
def ov_verdict_tally(t, dur, o, sh):
    """右下角小计分板：2:1:1 的四个判决节点，按 sh['stage'] 点亮已发生项。

    stage: 1=第一幕 M 胜；2=+第二幕 L 胜；3=+第三幕 平；4=+第四幕 谁也没赢。
    """
    stage = int((sh or {}).get("stage", 4))
    stage = max(1, min(4, stage))
    a = clamp((t - 0.15) / 0.55)
    if a <= 0:
        return
    xr = 1688.0
    y0 = 606.0
    row_h = 42.0
    scrim(o, (xr - 170, y0 + row_h * 1.6), 330, 0.34 * a)
    hud_label(o, "判决", (xr, y0 - 46), 22, TEXT2, 0.66 * a, anchor="rm", track=4)
    for i, (act, res) in enumerate(TALLY):
        if i >= stage:
            break
        ai = clamp((t - (0.20 + i * 0.15)) / 0.32)
        if ai <= 0:
            continue
        yy = y0 + i * row_h
        win = (res in ("M 胜", "L 胜"))
        col = GOLD if (win and i == stage - 1) else (TEXT2 if not win else MUTED)
        # 左侧小刻度
        o.stroke([(xr - 330, yy), (xr - 302, yy)], col, 1.6, 0.7 * ai * a)
        hud_label(o, act, (xr - 288, yy), 24, TEXT2, 0.78 * ai * a, track=2)
        hud_label(o, res, (xr, yy), 24, col, 0.9 * ai * a, anchor="rm", track=2)
    # 合计：2:1:1 的当下比分（只在 stage>=2 时显示）
    if stage >= 2:
        a3 = clamp((t - 1.0) / 0.6)
        if a3 > 0:
            mixed(o, [("比分 ", TEXT2, F_SANS_R), ("1:1", GOLD, F_MONO)],
                  (xr, y0 + 4 * row_h + 18), 26, anchor="rm", alpha=0.72 * a3)


def ov_flat_verdict(t, dur, o, sh):
    """「这局，平。」压字（第三幕末，压合上手册/靠回椅背的背影）。"""
    a = clamp((t - 0.12) / 0.5)
    if a <= 0:
        return
    x, y = 252.0, 640.0
    scrim(o, (x + 200, y), 320, 0.38 * a)
    o.text("这局，", (x, y), 46, BONE, font=F_SANS, anchor="lm", alpha=0.95 * a,
           track=2, stroke=2, stroke_color=(0, 0, 0))
    o.text("平。", (x + 150, y), 52, AMBER, font=F_SANS, anchor="lm", alpha=0.97 * a,
           track=2, stroke=2, stroke_color=(0, 0, 0), glow=12, glow_strength=0.4)
    rule(o, x, x + 260, y + 46, t, 0.25, 0.9, GOLD, 0.55, 1.1)


OVERLAYS = {
    "verdict_stamp": ov_verdict_stamp,
    "num_13438": ov_num_13438,
    "num_12445": ov_num_12445,
    "num_993": ov_num_993,
    "drop_97": ov_drop_97,
    "drop_249": ov_drop_249,
    "share_shift": ov_share_shift,
    "verdict_tally": ov_verdict_tally,
    "flat_verdict": ov_flat_verdict,
}
