#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 05 期数据层叠加器：压在实拍 / ComfyUI 镜头上的细线数据层。

约定：每个函数签名 `def ov_xxx(t, dur, o, sh)`，t 为镜头内局部时间（秒），
o 为 ep05viz.OverlayPainter，sh 为 shots.json 的镜头 dict。函数只画 RGBA 叠加层，
最终由 finalize 统一调色/颗粒/遮幅/字幕。

设计：数据层是「压在画面里的光」——细线 + 柔辉光 + 等宽数字刻度，不做灰底图表卡。
文字可读性：CJK 一律走 F_SANS_R / F_SANS / F_SERIF；等宽字体只用于数字与公式；
文字下可加柔和的深色 scrim（柔光暗斑，不是卡片）提升压片可读性。
花字全片克制：big_disease / formula_edges / quote_negscale / defensive_structure /
data_74_43 共 5 处。
"""
import math

import numpy as np

import ep05viz as V
from ep05viz import (TEAL, AMBER, EMBER, BONE, MUTED, DIM, GOLD, ICE, WHITE,
                     F_SANS, F_SANS_R, F_SERIF, F_MONO, W, H, SAFE_T, SAFE_B,
                     clamp, ease_in_out, ease_out_cubic, smoothstep, window, lerp,
                     text_tex, text_size, INK, TEAL_D)

# 安全区（2.35:1 遮幅内，y∈[132,948]；字幕在下黑边内）
L, R = 220, 1700
TOP, BOT = 190, 900
TEXT2 = (198, 210, 218)   # 压在亮底片上的次级文字（比 MUTED 更亮）


# ------------------------------------------------------------------ helpers
def hud_label(o, text, xy, size=30, color=TEXT2, alpha=1.0, anchor="lm", track=1.5,
              stroke=2):
    o.text(text, xy, size, color=color, font=F_SANS_R, anchor=anchor, alpha=alpha,
           track=track, stroke=stroke, stroke_color=(0, 0, 0))


def mono(o, text, xy, size=26, color=MUTED, alpha=1.0, anchor="lm", track=0.5,
         glow=0.0, glow_strength=0.45):
    o.text(text, xy, size, color=color, font=F_MONO, anchor=anchor, alpha=alpha,
           track=track, stroke=1, stroke_color=(0, 0, 0), glow=glow,
           glow_strength=glow_strength)


def mixed(o, parts, xy, size, anchor="lm", alpha=1.0, track=0.0, glow=0.0,
          glow_strength=0.45):
    """混排一行：中文走 CJK 字体、数字走等宽字体，按顺序拼在一行。"""
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


def scrim(o, xy, r=260, alpha=0.30, color=(3, 6, 9)):
    """柔和暗斑：只压暗局部，让文字从底片里浮出来（不是灰底卡片）。"""
    if alpha > 0.004:
        o.glow(xy, r=r, color=color, alpha=clamp(alpha))


def rule(o, x0, x1, y, t, t0, t1, color=MUTED, alpha=0.55, width=1.2):
    a = window(t, t0, t1, 0.25, 0.3)
    if a <= 0:
        return
    x = lerp(x0, x1, ease_out_cubic(clamp((t - t0) / max(1e-3, t1 - t0))))
    o.stroke([(x0, y), (x, y)], color, width, alpha * a)


def 花字(o, text, xy, t, t0, t1, color=WHITE, size=100, font=F_SERIF,
         glow_color=None, appear=0.24, track=2.0):
    """大字花字：小幅上浮 + 淡入淡出（全片仅 5 处）。"""
    if t < t0 or t > t1:
        return
    a = window(t, t0, t1, appear, appear * 1.5)
    if a <= 0.003:
        return
    p = clamp((t - t0) / appear)
    y = xy[1] - 10 * ease_out_cubic(clamp((t - t0) / 0.8))
    o.text(text, (xy[0], y), size, color=color, font=font, anchor="mm", alpha=a,
           track=track, glow=18, glow_strength=0.55)


# ------------------------------------------------------------------ S1
def ov_stamp_count(t, dur, o, sh):
    """S1 s2：一个决定，走五个部门，签七个字 —— 刻度逐个亮起。"""
    x = 246.0
    a = clamp((t - 0.10) / 0.5)
    if a <= 0:
        return
    scrim(o, (x + 210, 766), 360, 0.52 * a)
    hud_label(o, "一个决定", (x, 640), 28, TEXT2, 1.0 * a, track=4)
    # 五个部门：刻度 0.35s 起逐个亮
    for i in range(5):
        ta = clamp((t - (0.35 + i * 0.30)) / 0.35)
        if ta <= 0:
            continue
        xx = x + 8 + i * 44
        o.stroke([(xx, 726), (xx, 726 - 18 * ease_out_cubic(ta))],
                 TEAL if ta > 0.55 else TEAL_D, 2.6, 0.95 * ta, 8, 0.45)
        o.dot((xx, 706), 3.0, TEAL, 0.92 * ta, 10, 0.65)
    na = clamp((t - 0.25) / 0.4)
    mixed(o, [("5", BONE, F_MONO), (" 个部门", TEXT2, F_SANS_R)], (x, 766), 44,
          alpha=0.98 * na, glow=8)
    # 七个字
    for i in range(7):
        ta = clamp((t - (1.35 + i * 0.22)) / 0.30)
        if ta <= 0:
            continue
        xx = x + 8 + i * 34
        o.stroke([(xx, 844), (xx, 844 - 14 * ease_out_cubic(ta))],
                 AMBER if ta > 0.55 else (140, 112, 76), 2.4, 0.95 * ta, 8, 0.45)
    na2 = clamp((t - 1.25) / 0.4)
    mixed(o, [("7", AMBER, F_MONO), (" 个字", TEXT2, F_SANS_R)], (x, 876), 44,
          alpha=0.98 * na2, glow=10)
    rule(o, x, x + 250, 690, t, 0.4, 1.0, MUTED, 0.4, 1.0)


def ov_big_disease(t, dur, o, sh):
    """S1 s6：这是「大」本身带的病 —— 花字 #1（压在走廊尽头）。"""
    a = clamp((t - 0.55) / 0.6)
    if a <= 0:
        return
    scrim(o, (960, 690), 500, 0.46 * a)
    花字(o, "「大」本身带的病", (960, 690), t, max(0.55, dur * 0.28), dur + 0.8,
         color=WHITE, size=88, track=3.0)


# ------------------------------------------------------------------ S2
def ov_formula_edges(t, dur, o, sh):
    """S2 s3：关系数 n(n−1)/2 —— 花字 #2（公式是等宽数字，计数与场景同步增长）。"""
    x = 240.0
    a = clamp((t - 0.15) / 0.5)
    if a <= 0:
        return
    scrim(o, (x + 300, 330), 340, 0.46 * a)
    hud_label(o, "关系数", (x, 240), 26, MUTED, 0.78 * a, track=4)
    o.text("n(n−1)/2", (x, 300), 66, TEAL, font=F_MONO, anchor="lm",
           alpha=0.96 * a, track=1, glow=14, glow_strength=0.5)
    rule(o, x, x + 360, 340, t, 0.35, 0.9, GOLD, 0.55, 1.2)
    o.text("= 20 × 19 / 2 = 190", (x, 388), 36, BONE, font=F_MONO, anchor="lm",
           alpha=0.9 * a, stroke=1, stroke_color=(0, 0, 0))
    hud_label(o, "每条连线 = 一次协调", (x, 446), 24, MUTED, 0.62 * a, track=2)
    # 与场景生长同步的真实连线计数（只做细刻度，避免与场景内的计数重复）
    n_edges = V.net_edge_count(t, dur, 10, 20)
    a2 = clamp((t - 0.4) / 0.6)
    for k in range(20):
        xx = x + 4 + k * 15
        lit = k < int(n_edges / 190.0 * 20.0)
        o.stroke([(xx, 506), (xx, 506 - (12 if lit else 6))], TEAL if lit else TEAL_D,
                 1.2, (0.8 if lit else 0.35) * a2)


def ov_quote_negscale(t, dur, o, sh):
    """S2 s7：组织规模负效率 —— 花字 #3（百叶窗光上压字）。"""
    a = clamp((t - 0.4) / 0.6)
    if a <= 0:
        return
    scrim(o, (960, 610), 600, 0.44 * a)
    hud_label(o, "周雪光《中国国家治理的制度逻辑》", (960, 470), 24, MUTED,
              0.68 * a, anchor="mm", track=3)
    花字(o, "组织规模负效率", (960, 612), t, 1.0, dur + 0.6,
         color=WHITE, size=92, track=4.0)
    a2 = clamp((t - 2.1) / 0.8)
    if a2 > 0:
        hud_label(o, "信息越散 · 不对称越重 · 效率越低", (960, 700), 28, MUTED,
                  0.78 * a2, anchor="mm", track=3)


def ov_quote_setting(t, dur, o, sh):
    """S2 s9：不是哪家公司的毛病 / 是所有大组织的出厂设置。"""
    a1 = clamp((t - 0.35) / 0.6)
    if a1 > 0:
        scrim(o, (960, 590), 520, 0.42 * a1)
        o.text("这不是哪家公司的毛病", (960, 556), 46, BONE, font=F_SANS,
               anchor="mm", alpha=0.97 * a1, track=2, glow=12, glow_strength=0.38,
               stroke=2, stroke_color=(0, 0, 0))
    a2 = clamp((t - 2.25) / 0.7)
    if a2 > 0:
        scrim(o, (960, 634), 460, 0.36 * a2)
        o.text("这是所有大组织的出厂设置", (960, 634), 54, AMBER, font=F_SANS,
               anchor="mm", alpha=0.98 * a2, track=2, glow=14, glow_strength=0.45,
               stroke=2, stroke_color=(0, 0, 0))


# ------------------------------------------------------------------ S3
def ov_defensive_structure(t, dur, o, sh):
    """S3 s5：防御性结构 —— 花字 #4；随后是「防止错误 vs 创造价值」与停靠/路径对比。"""
    a = clamp((t - 0.35) / 0.6)
    if a <= 0:
        return
    hud_label(o, "詹姆斯·威尔逊 · 官僚组织理论", (560, 468), 24, MUTED, 0.66 * a,
              anchor="mm", track=2)
    # 花字 #4（在旁白念到“防御性结构”时出现）
    scrim(o, (560, 566), 520, 0.30)
    花字(o, "防御性结构", (560, 566), t, 3.55, dur + 0.8, color=WHITE, size=96,
         track=5.0)
    a2 = clamp((t - 5.1) / 0.8)
    if a2 > 0:
        o.text("更擅长防止错误，而不是创造价值", (560, 652), 30, MUTED,
               font=F_SANS_R, anchor="mm", alpha=0.82 * a2, track=2,
               stroke=1, stroke_color=(0, 0, 0))
    # 停靠 / 路径对比（右侧，横向两行 —— 停靠越多、路径越长）
    a3 = clamp((t - 10.4) / 0.7)
    if a3 <= 0:
        return
    xl = 1084.0
    scrim(o, (1400, 650), 380, 0.42 * a3)
    hud_label(o, "加一层 · 多停一次", (xl, 500), 28, AMBER, 0.82 * a3, track=3)
    rows = ((3, 592.0, TEAL_D, "43.2", 0.85),
            (8, 688.0, TEAL, "121.2", 1.0))
    for nfloor, yy, col, pathm, aa in rows:
        # 停靠刻度：每一层一枚（停靠次数随层数同步增加）
        tk = clamp((t - (10.9 + (0 if nfloor == 3 else 0.9))) / 0.8)
        if tk <= 0:
            continue
        for i in range(nfloor):
            tick = clamp((t - (10.9 + (0 if nfloor == 3 else 0.9) + i * 0.05)) / 0.3)
            if tick <= 0:
                continue
            xx = xl + 6 + i * 26
            o.stroke([(xx, yy), (xx, yy - 20 * tick)], AMBER if tick < 1 else col,
                     2.0, 0.9 * tick * aa)
            o.dot((xx, yy - 20), 2.4, AMBER, 0.9 * tick * aa, 8, 0.5)
        o.stroke([(xl, yy + 4), (xl + nfloor * 26 + 4, yy + 4)], col, 1.0, 0.45 * tk)
        mixed(o, [("%d 层" % nfloor, BONE, F_SANS_R),
                  (" · 停靠 ", MUTED, F_SANS_R), ("%d" % nfloor, AMBER, F_MONO),
                  (" 次 · 路径 ", MUTED, F_SANS_R), (pathm, col, F_MONO),
                  (" m", MUTED, F_SANS_R)], (xl, yy + 42), 26,
              alpha=0.86 * tk * aa, glow=6 if nfloor == 8 else 0)
    a4 = clamp((t - 12.4) / 0.8)
    if a4 > 0:
        mixed(o, [("路径 ", MUTED, F_SANS_R), ("×2.8", GOLD, F_MONO)],
              (xl, 776), 30, alpha=0.85 * a4, glow=8)


# ------------------------------------------------------------------ S3 rules
def ov_quote_rules(t, dur, o, sh):
    """S3 s9：规则越压越紧，一线的灵活度往下掉（唐斯）。"""
    a1 = clamp((t - 0.4) / 0.6)
    if a1 > 0:
        scrim(o, (470, 560), 470, 0.46 * a1)
        hud_label(o, "唐斯 · 科层体制扩张", (296, 474), 22, MUTED, 0.62 * a1, track=2)
        o.text("规则越压越紧", (296, 528), 48, BONE, font=F_SANS, anchor="lm",
               alpha=0.98 * a1, track=3, glow=12, glow_strength=0.35,
               stroke=2, stroke_color=(0, 0, 0))
    a2 = clamp((t - 1.9) / 0.7)
    if a2 > 0:
        o.text("一线的灵活度，就往下掉", (296, 594), 34, TEXT2, font=F_SANS_R,
               anchor="lm", alpha=0.94 * a2, track=2,
               stroke=2, stroke_color=(0, 0, 0))
    # 下降的细线（灵活度）
    p = clamp((t - 2.5) / 2.0)
    if p > 0:
        xs = np.linspace(0, 1, 80)
        x = 1080 + 520 * xs
        y = 470 + 250 * (xs ** 1.35) * ease_out_cubic(p)
        n = max(3, int(len(xs) * ease_out_cubic(p)))
        o.stroke(np.stack([x[:n], y[:n]], 1), EMBER, 1.8, 0.7, 10, 0.5)
        o.dot((x[n - 1], y[n - 1]), 4.0, EMBER, 0.85, 10, 0.6)
    a3 = clamp((t - 4.4) / 0.7)
    if a3 > 0:
        hud_label(o, "灵活度", (1608, 742), 28, EMBER, 0.95 * a3, track=2)


# ------------------------------------------------------------------ S4
def ov_blame_blank(t, dur, o, sh):
    """S4 s7：谁都不越界，谁都不担责，事情卡在缝里 —— 词落进中央那块空白。"""
    a = clamp((t - 0.35) / 0.6)
    if a <= 0:
        return
    # 中央空白是语义本体：文字就放在空白里、围着那张“事情”的纸
    a1 = clamp((t - 0.45) / 0.6)
    if a1 > 0:
        o.text("谁都不越界", (960, 392), 32, MUTED, font=F_SANS, anchor="mm",
               alpha=0.80 * a1, track=3, stroke=1, stroke_color=(0, 0, 0))
    a2 = clamp((t - 1.15) / 0.6)
    if a2 > 0:
        o.text("谁都不担责", (960, 440), 32, MUTED, font=F_SANS, anchor="mm",
               alpha=0.80 * a2, track=3, stroke=1, stroke_color=(0, 0, 0))
    a3 = clamp((t - 1.95) / 0.7)
    if a3 > 0:
        scrim(o, (960, 656), 230, 0.26 * a3)
        o.text("事情卡在缝里", (960, 656), 50, AMBER, font=F_SANS, anchor="mm",
               alpha=0.95 * a3, track=2, glow=14, glow_strength=0.4,
               stroke=1, stroke_color=(0, 0, 0))
    # 细线把“缝里”指回那张纸
    p = clamp((t - 2.5) / 1.0)
    if p > 0:
        x_end = lerp(960, 960, ease_out_cubic(p))
        o.stroke([(960, 620), (960, 584)], GOLD, 1.1, 0.35 * p)


# ------------------------------------------------------------------ S5
def ov_data_74_43(t, dur, o, sh):
    """S5 s6：74% → 43% —— 花字 #5（两个真实数字压在曲线两端）。"""
    s16, _ = V.fatigue_mark(2016)
    s22, _ = V.fatigue_mark(2022)
    x16, y16 = V.fatigue_xy(s16)
    x22, y22 = V.fatigue_xy(s22)
    m1 = clamp((t - 1.35) / 0.5)
    if m1 > 0:
        # 74% 放在右上空白区，用细引线指回 2016 的第一个峰（不压标题/曲线）
        bx, by = 1010.0, 218.0
        scrim(o, (bx + 70, by + 6), 220, 0.34 * m1)
        o.text("74%", (bx, by), 86, AMBER, font=F_MONO, anchor="lm",
               alpha=0.97 * m1, track=1, glow=16, glow_strength=0.5,
               stroke=1, stroke_color=(0, 0, 0))
        o.stroke([(bx - 14, by + 12), (x16 + 120, 268), (x16 + 16, y16 - 18)],
                 AMBER, 1.1, 0.55 * m1)
        o.dot((x16 + 14, y16 - 16), 2.8, AMBER, 0.8 * m1, 8, 0.5)
    m2 = clamp((t - 3.10) / 0.55)
    if m2 > 0:
        tx2, ty2 = x22 + 8, y22 - 172
        scrim(o, (tx2 - 96, ty2 + 6), 220, 0.34 * m2)
        o.text("43%", (tx2, ty2), 86, TEAL, font=F_MONO, anchor="rm",
               alpha=0.97 * m2, track=1, glow=16, glow_strength=0.5,
               stroke=1, stroke_color=(0, 0, 0))
        o.stroke([(tx2 - 124, ty2 + 30), (x22 - 8, y22 - 22)], TEAL, 1.1, 0.5 * m2)
        o.dot((x22 - 8, y22 - 20), 2.8, TEAL, 0.8 * m2, 8, 0.5)
    a3 = clamp((t - 4.0) / 0.7)
    if a3 > 0:
        xm = (x16 + x22) * 0.5 + 60
        ym = (y16 + y22) * 0.5 - 60
        mixed(o, [("−", GOLD, F_MONO), ("31", GOLD, F_MONO), (" pp", MUTED, F_SANS_R)],
              (xm, ym), 34, anchor="mm", alpha=0.85 * a3, glow=8)


def ov_quote_gallup(t, dur, o, sh):
    """S5 s7-s9：Gallup 73%（第一拍）→ Prosci 的变革疲劳定义（第二拍，交叉淡入）。"""
    a = clamp((t - 0.30) / 0.5)
    beat1 = a * (1.0 - clamp((t - 6.3) / 0.9) * 0.88)
    if beat1 > 0.01:
        scrim(o, (430, 700), 400, 0.44 * beat1)
        n = int(round(73 * ease_out_cubic(clamp((t - 0.30) / 0.9))))
        o.text("%d%%" % n, (252, 650), 96, TEAL, font=F_MONO, anchor="lm",
               alpha=0.96 * beat1, track=1, glow=16, glow_strength=0.5,
               stroke=1, stroke_color=(0, 0, 0))
        hud_label(o, "的员工表示", (528, 626), 30, MUTED, 0.82 * beat1, track=2)
        a1b = clamp((t - 3.4) / 0.7)
        if a1b > 0:
            o.text("公司过去一年经历过破坏性变革", (252, 742), 38, BONE,
                   font=F_SANS, anchor="lm", alpha=0.95 * a1b * beat1, track=2,
                   stroke=2, stroke_color=(0, 0, 0))
            hud_label(o, "Gallup · 经媒体报道与综述转引", (252, 800), 22, MUTED,
                      0.6 * a1b * beat1, track=1)
    # 第二拍：Prosci 定义
    a2 = clamp((t - 6.6) / 0.9)
    if a2 > 0:
        scrim(o, (470, 690), 420, 0.42 * a2)
        hud_label(o, "Prosci", (252, 606), 22, GOLD, 0.7 * a2, track=3)
        o.text("超过承受能力的那一个项目", (252, 668), 36, BONE, font=F_SANS,
               anchor="lm", alpha=0.96 * a2, track=2,
               stroke=2, stroke_color=(0, 0, 0))
        o.text("就叫「变革疲劳」", (252, 726), 42, AMBER, font=F_SANS, anchor="lm",
               alpha=0.98 * a2, track=2, glow=12, glow_strength=0.4,
               stroke=2, stroke_color=(0, 0, 0))


def ov_quote_carnegie(t, dur, o, sh):
    """S5 s10：员工不是不愿变革 —— 是没被装备好、被支持、被看见。"""
    a1 = clamp((t - 0.55) / 0.6)
    if a1 <= 0:
        return
    x = 566.0
    scrim(o, (x + 300, 320), 470, 0.40 * a1)
    hud_label(o, "戴尔·卡内基", (x, 240), 22, MUTED, 0.62 * a1, track=2)
    o.text("员工不是不愿变革", (x, 292), 42, BONE, font=F_SANS, anchor="lm",
           alpha=0.98 * a1, track=2, glow=12, glow_strength=0.35,
           stroke=2, stroke_color=(0, 0, 0))
    a2 = clamp((t - 1.9) / 0.7)
    if a2 > 0:
        o.text("是不觉得自己被装备好", (x, 350), 34, TEXT2, font=F_SANS_R,
               anchor="lm", alpha=0.94 * a2, track=2,
               stroke=2, stroke_color=(0, 0, 0))
    a3 = clamp((t - 2.8) / 0.7)
    if a3 > 0:
        o.text("被支持、被看见", (x, 404), 36, AMBER, font=F_SANS_R, anchor="lm",
               alpha=0.96 * a3, track=3, glow=12, glow_strength=0.4,
               stroke=2, stroke_color=(0, 0, 0))


# ------------------------------------------------------------------ S6
def ov_dir_one(t, dur, o, sh):
    """S6 s4：第一，承认「大」本身有代价 —— 承认它，才会防它。"""
    a0 = clamp((t - 0.35) / 0.5)
    if a0 <= 0:
        return
    scrim(o, (560, 500), 560, 0.55 * a0)
    hud_label(o, "第一", (296, 408), 26, GOLD, 0.8 * a0, track=4)
    o.stroke([(296, 442), (296 + 170 * ease_out_cubic(clamp((t - 0.35) / 0.8)), 442)],
             GOLD, 1.2, 0.5 * a0)
    a1 = clamp((t - 0.8) / 0.7)
    if a1 > 0:
        o.text("承认「大」本身有代价", (296, 500), 48, BONE, font=F_SANS, anchor="lm",
               alpha=0.98 * a1, track=3, glow=12, glow_strength=0.35,
               stroke=2, stroke_color=(0, 0, 0))
    a2 = clamp((t - 2.4) / 0.7)
    if a2 > 0:
        o.text("承认它，才会防它", (296, 572), 40, AMBER, font=F_SANS_R, anchor="lm",
               alpha=0.96 * a2, track=3, glow=12, glow_strength=0.4,
               stroke=2, stroke_color=(0, 0, 0))


OVERLAYS = {
    "stamp_count": ov_stamp_count,
    "big_disease": ov_big_disease,
    "formula_edges": ov_formula_edges,
    "quote_negscale": ov_quote_negscale,
    "quote_setting": ov_quote_setting,
    "defensive_structure": ov_defensive_structure,
    "quote_rules": ov_quote_rules,
    "blame_blank": ov_blame_blank,
    "data_74_43": ov_data_74_43,
    "quote_gallup": ov_quote_gallup,
    "quote_carnegie": ov_quote_carnegie,
    "dir_one": ov_dir_one,
}
