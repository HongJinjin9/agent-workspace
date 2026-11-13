#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 06 期全画幅程序化场景（冷开场 / 柱状对比 / 引述卡 / 数据曲线 / 收束 / 片尾）。

每个场景签名 `def scene_xxx(t, dur, sh) -> PIL.Image`，t 为镜头内局部时间。
所有图形由 ep06viz.py 的真实数值模型生成：
- 柱状条：柱高严格 ∝ 13,438 / 12,445（上险量），数字与柱同步滚动；
- 份额曲线：10.3% → 7.0%（两点真实数据，线性）；
- 引述卡：打字机逐字（字数由时间窗口驱动），引号包裹 + 发言人/时间/出处；
- 收束：程序化纸张与侧光（空白手册），尘埃由相位漂移。

风格约束：冷灰基底 + 暖金点缀；一屏一个第一视觉重点；无进度条/章节卡/闪白；
文字在 2.35:1 遮幅安全区内（y∈[150,900]），字幕在下黑边内。
"""
import math

import numpy as np
from PIL import Image

import ep06viz as V
from ep06viz import (W, H, BAR, SAFE_T, SAFE_B, INK, INK2, BONE, MUTED, DIM, TEAL,
                     TEAL_D, AMBER, GOLD, EMBER, ICE, WHITE, F_SERIF, F_SERIF_R,
                     F_SANS, F_SANS_R, F_MONO, clamp, lerp, ease_in_out,
                     ease_out_cubic, ease_in_cubic, smoothstep, window,
                     STEEL, STEEL_D, SLATE, PAPER, PAPER_D, GOLD_D, RED_SEAL, RED_D,
                     V_IDEAL_ONE_2021_11, V_VW_FIVE_2021_11, V_DIFF_2021_11,
                     V_EXT_2025_FULL, V_EXT_2026_JAN_MAY, YO_Y_2026_JAN_MAY,
                     YO_Y_2026_MAY, SHARE_2025_05, SHARE_2026_05, TALLY,
                     bar_height, grow_progress, grow_bar, count_up,
                     tw_count, tw_text, cursor_alpha, seal_drop, ink_bleed,
                     share_value, pct_str, page_corners, paper_lines,
                     dust_motes)

ROOT = "/app/vedio/ep06-dialogue"

_GRID = None


def grid():
    global _GRID
    if _GRID is None:
        yy, xx = np.ogrid[:H, :W]
        _GRID = (xx.astype(np.float32) / W, yy.astype(np.float32) / H)
    return _GRID


# ---------------------------------------------------------------- backgrounds
def grey_bg(t, dur, base=(0.030, 0.035, 0.040), light=(0.42, 0.50, 0.56),
            strength=0.11, cx=0.46, cy=0.40, warm=0.0, drift=0.012):
    """冷灰基底：斜上方柔光 + 缓慢漂移；warm 控制暖金偏移（0..1）。"""
    nx, ny = grid()
    gx = cx + drift * math.sin(t * 0.31 + 0.4)
    gy = cy + drift * 0.5 * math.cos(t * 0.23)
    g = np.exp(-(((nx - gx) ** 2) / (0.52 ** 2) + ((ny - gy) ** 2) / (0.42 ** 2)))
    cold = np.array(light, np.float32)
    hot = np.array([0.56, 0.42, 0.24], np.float32)
    tint = cold * (1 - warm) + hot * warm
    rgb = np.array(base, np.float32)[None, None, :] + g[..., None] * tint * strength
    yy = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    rgb *= (1.0 - 0.30 * smoothstep(0.55, 1.0, yy))
    return np.clip(rgb, 0, 1)


def table_bg(t, dur, warm=0.0, horizon=0.62):
    """暗桌面：地平线以上是虚化墙面，以下是桌面反光；可用 warm 偏暖。"""
    nx, ny = grid()
    rgb = grey_bg(t, dur, base=(0.026, 0.030, 0.034),
                  light=(0.40, 0.48, 0.54), strength=0.10,
                  cx=0.55, cy=0.34, warm=warm)
    yy = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    table = smoothstep(horizon - 0.02, horizon + 0.02, yy)
    wood = np.array([0.055, 0.044, 0.034], np.float32) + warm * np.array(
        [0.030, 0.018, 0.006], np.float32)
    rgb = rgb * (1 - table) + wood[None, None, :] * table
    streak = np.exp(-((yy - (horizon + 0.16)) ** 2) / (2 * 0.05 ** 2))
    rgb += streak * np.array([0.10, 0.085, 0.060], np.float32) * (0.35 + 0.25 * warm)
    return np.clip(rgb, 0, 1)


def warm_bg(t, dur):
    """片尾：暖中性暗底 + 柔焦光斑。"""
    nx, ny = grid()
    rgb = np.zeros((H, W, 3), np.float32) + np.array([0.030, 0.027, 0.023], np.float32)
    g1 = np.exp(-(((nx - 0.72) ** 2) / 0.10 + ((ny - 0.30) ** 2) / 0.14))
    g2 = np.exp(-(((nx - 0.30) ** 2) / 0.16 + ((ny - 0.70) ** 2) / 0.12))
    heat = 0.026 * math.sin(t * 0.40)
    rgb += g1[..., None] * np.array([0.16, 0.12, 0.07], np.float32) * (0.9 + heat)
    rgb += g2[..., None] * np.array([0.05, 0.05, 0.06], np.float32) * 0.7
    yy = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    rgb *= (1.0 - 0.30 * smoothstep(0.55, 1.0, yy))
    return np.clip(rgb, 0, 1)


# ---------------------------------------------------------------- primitives
def rule(p, x0, x1, y, alpha=0.6, color=GOLD, width=1.2, glow=8):
    p.stroke([(x0, y), (x1, y)], color, width, alpha, glow, 0.35)


def draw_mixed(p, parts, xy, size, anchor="lm", alpha=1.0, track=0.0, glow=0.0,
               glow_strength=0.35):
    """混排：中文走 CJK 字体、数字走等宽字体（防 tofu）。"""
    total = 0.0
    widths = []
    for text, color, font in parts:
        w = V.text_size(text, size, font, stroke=1, track=track)[0]
        widths.append(w)
        total += w
    x = xy[0]
    if anchor == "rm":
        x -= total
    elif anchor == "mm":
        x -= total * 0.5
    for (text, color, font), w in zip(parts, widths):
        V.draw_text(p.rgb, text, (x, xy[1]), size, color, font, anchor="lm",
                    alpha=alpha, stroke=1, stroke_color=(0, 0, 0), track=track,
                    glow=glow, glow_strength=glow_strength)
        x += w
    return total


# ---------------------------------------------------------------- 冷开场
def scene_cold_title(t, dur, sh=None):
    """冷开场：冷灰桌面，标题 + 副标题 + 系列名；一道金色“判决线”。"""
    bg = table_bg(t, dur, warm=0.10, horizon=0.64)
    p = V.Painter(bg)
    # 桌面两侧：手册与账本的低对比剪影（道具母题第一次出现）
    p.fill_poly([(300, 704), (470, 690), (492, 760), (318, 776)], (34, 32, 30), 0.55)
    p.stroke([(300, 704), (470, 690), (492, 760), (318, 776), (300, 704)],
             (86, 78, 66), 1.0, 0.22)
    p.stroke([(318, 706), (486, 692)], (150, 142, 126), 1.0, 0.25)
    p.fill_poly([(1450, 700), (1596, 712), (1588, 772), (1442, 760)], (26, 30, 34), 0.6)
    p.stroke([(1450, 700), (1596, 712), (1588, 772), (1442, 760), (1450, 700)],
             (84, 94, 102), 1.0, 0.26)
    lp = ease_in_out(clamp((t - 0.02) / max(0.22, dur * 0.10)))
    if lp > 0:
        half = 430 * lp
        p.stroke([(960 - half, 506), (960 + half, 506)], GOLD, 1.6, 0.80, 12, 0.45)
        p.dot((960 - half, 506), 2.6, GOLD, 0.75, 8, 0.5)
        p.dot((960 + half, 506), 2.6, GOLD, 0.75, 8, 0.5)
    p.flush()
    a0 = window(t, 0.04, dur - 0.02, 0.30, 0.30)
    V.draw_text(p.rgb, "VIBE 知识共赏 · 第 06 期", (960, 388), 24, MUTED, F_SANS_R,
                anchor="mm", alpha=0.72 * a0, track=5)
    a1 = window(t, 0.16, dur - 0.02, 0.42, 0.30)
    if a1 > 0:
        rise = 14 * (1 - ease_out_cubic(clamp((t - 0.16) / max(0.3, dur * 0.10))))
        V.draw_text(p.rgb, "他们说，这是最糟糕的方案", (960, 438 - rise), 68, BONE,
                    F_SERIF, anchor="mm", alpha=0.97 * a1, track=3,
                    glow=16, glow_strength=0.42)
    a2 = window(t, 0.55, dur - 0.02, 0.40, 0.30)
    if a2 > 0:
        V.draw_text(p.rgb, "一场持续六年的技术判决，和它自己的判决", (960, 556), 30,
                    MUTED, F_SANS_R, anchor="mm", alpha=0.86 * a2, track=3)
    a3 = clamp((t - 0.95) / 0.55)
    if a3 > 0:
        draw_mixed(p, [("2020", DIM, F_MONO), (" — ", DIM, F_MONO),
                       ("2026", DIM, F_MONO)], (960, 624), 22, anchor="mm",
                   alpha=0.6 * a3, track=2)
    p.bloom(threshold=0.64, strength=0.5)
    return p.to_image()


# ---------------------------------------------------------------- 第二幕 柱状对比
def scene_bar_compare(t, dur, sh=None):
    """13,438 对 12,445：两根柱从零生长，后者停住，差值 993 单独落下。"""
    bg = grey_bg(t, dur, base=(0.028, 0.033, 0.038), strength=0.10, cx=0.5, cy=0.42,
                 warm=0.25)
    p = V.Painter(bg)
    base_y = 796.0
    h_max = 404.0
    vmax = float(V_IDEAL_ONE_2021_11)
    x1, x2 = 610.0, 1210.0
    bar_w = 168.0
    g1a, g1b = dur * 0.03, dur * 0.40
    g2a, g2b = dur * 0.65, dur * 0.90
    h1 = bar_height(V_IDEAL_ONE_2021_11, vmax, h_max) * grow_progress(t, g1a, g1b)
    h2 = bar_height(V_VW_FIVE_2021_11, vmax, h_max) * grow_progress(t, g2a, g2b)
    p.stroke([(330, base_y), (1700, base_y)], (96, 106, 114), 1.3, 0.65)
    for val in (5000, 10000):
        yy = base_y - bar_height(val, vmax, h_max)
        for seg in V.dashed(np.array([[360.0, yy], [1660.0, yy]]), 16, 12):
            p.stroke(seg, (70, 80, 88), 1.0, 0.40)
    # 柱 1：理想 ONE（暖金）
    p.fill_rect((x1 - bar_w / 2, base_y - h1), (x1 + bar_w / 2, base_y),
                (26, 23, 19), 0.92)
    p.fill_rect((x1 - bar_w / 2, base_y - h1), (x1 + bar_w / 2, base_y),
                (150, 118, 66), 0.20 + 0.10 * clamp((t - g1b) / 1.2))
    p.stroke([(x1 - bar_w / 2, base_y - h1), (x1 + bar_w / 2, base_y - h1)],
             GOLD, 2.6, 0.95, 12, 0.5)
    p.stroke([(x1 - bar_w / 2, base_y - h1), (x1 - bar_w / 2, base_y)],
             GOLD_D, 1.4, 0.7)
    # 柱 2：大众五款（冷钢灰）
    p.fill_rect((x2 - bar_w / 2, base_y - h2), (x2 + bar_w / 2, base_y),
                (20, 24, 28), 0.92)
    p.fill_rect((x2 - bar_w / 2, base_y - h2), (x2 + bar_w / 2, base_y),
                (84, 108, 120), 0.16 + 0.10 * clamp((t - g2b) / 1.2))
    p.stroke([(x2 - bar_w / 2, base_y - h2), (x2 + bar_w / 2, base_y - h2)],
             STEEL, 2.6, 0.95, 12, 0.5)
    p.stroke([(x2 - bar_w / 2, base_y - h2), (x2 - bar_w / 2, base_y)],
             STEEL_D, 1.4, 0.75)
    # 差值 993（括号 + 虚线延长）
    gap_a = clamp((t - dur * 0.56) / max(0.5, dur * 0.10))
    if gap_a > 0:
        y1 = base_y - bar_height(V_IDEAL_ONE_2021_11, vmax, h_max)
        y2 = base_y - bar_height(V_VW_FIVE_2021_11, vmax, h_max)
        lx = 1500.0
        for seg in V.dashed(np.array([[x1 + bar_w / 2 + 10, y1], [lx, y1]]), 18, 12):
            p.stroke(seg, GOLD, 1.2, 0.55 * gap_a)
        for seg in V.dashed(np.array([[x2 + bar_w / 2 + 10, y2], [lx, y2]]), 18, 12):
            p.stroke(seg, STEEL, 1.2, 0.55 * gap_a)
        p.stroke([(lx, y1), (lx, y2)], GOLD, 1.4, 0.75 * gap_a)
        p.stroke([(lx - 9, y1), (lx + 9, y1)], GOLD, 1.4, 0.75 * gap_a)
        p.stroke([(lx - 9, y2), (lx + 9, y2)], GOLD, 1.4, 0.75 * gap_a)
    p.flush()
    # 数字与标签（花字 13,438 / 12,445，随柱高同步滚动）
    a_num = clamp((t - g1a) / 0.3)
    if a_num > 0:
        n1 = count_up(t, g1a, g1b, V_IDEAL_ONE_2021_11)
        n2 = count_up(t, g2a, g2b, V_VW_FIVE_2021_11)
        y1 = base_y - bar_height(V_IDEAL_ONE_2021_11, vmax, h_max)
        y2 = base_y - bar_height(V_VW_FIVE_2021_11, vmax, h_max)
        V.draw_text(p.rgb, "{:,}".format(n1), (x1, y1 - 74), 92, GOLD, F_MONO,
                    anchor="mm", alpha=0.97 * a_num, track=1, glow=16,
                    glow_strength=0.5)

        V.draw_text(p.rgb, "{:,}".format(n2), (x2, y2 - 70), 84, STEEL, F_MONO,
                    anchor="mm", alpha=0.95 * a_num, track=1, glow=14,
                    glow_strength=0.45)

    a_lab = clamp((t - dur * 0.10) / 0.7)
    if a_lab > 0:
        V.draw_text(p.rgb, "理想 ONE", (x1, base_y + 44), 30, BONE, F_SANS, anchor="mm",
                    alpha=0.95 * a_lab, track=2)
        V.draw_text(p.rgb, "2021-11 · 单月上险（台）", (x1, base_y + 84), 24, MUTED,
                    F_SANS_R, anchor="mm", alpha=0.78 * a_lab, track=2)
    a_lab2 = clamp((t - dur * 0.60) / 0.7)
    if a_lab2 > 0:
        V.draw_text(p.rgb, "大众五款中大型 SUV", (x2, base_y + 44), 30, BONE, F_SANS,
                    anchor="mm", alpha=0.95 * a_lab2, track=2)
        V.draw_text(p.rgb, "途昂 / 途锐 / 揽境 / ID.6 X / ID.6 Crozz", (x2, base_y + 84),
                    22, MUTED, F_SANS_R, anchor="mm", alpha=0.72 * a_lab2, track=1)
    reread = window(t, dur * 0.42, dur * 0.52, 0.20, 0.3)
    if reread > 0:
        y1n = base_y - bar_height(V_IDEAL_ONE_2021_11, vmax, h_max)
        p.stroke([(x1 - 190, y1n - 10), (x1 + 190, y1n - 10)], GOLD, 2.0,
                 0.55 * reread, 10, 0.45)
    a_gap = clamp((t - dur * 0.90) / max(0.3, dur * 0.04))
    if a_gap > 0:
        y1 = base_y - bar_height(V_IDEAL_ONE_2021_11, vmax, h_max)
        y2 = base_y - bar_height(V_VW_FIVE_2021_11, vmax, h_max)
        ym = (y1 + y2) / 2
        V.draw_text(p.rgb, "+993 台", (1592, ym - 34), 46, GOLD, F_MONO, anchor="lm",
                    alpha=0.95 * a_gap, glow=12, glow_strength=0.4)
        V.draw_text(p.rgb, "仅多 8.0%", (1592, ym + 16), 26, MUTED, F_SANS_R,
                    anchor="lm", alpha=0.8 * a_gap, track=2)
    a_cap = clamp((t - dur * 0.08) / 0.7)
    if a_cap > 0:
        V.draw_text(p.rgb, "单月上险量 · 数据来源：中国产经网（引用上险数据）",
                    (300, 240), 22, DIM, F_SANS_R, anchor="lm", alpha=0.62 * a_cap,
                    track=1)
    p.bloom(threshold=0.62, strength=0.5)
    return p.to_image()


# ---------------------------------------------------------------- 引述卡（打字机）
def _card_bg(t, dur, warm=0.0, light_x=0.24):
    """引述卡底：暗桌面 + 一侧暖光。"""
    bg = table_bg(t, dur, warm=warm, horizon=0.80)
    nx, ny = grid()
    g = np.exp(-(((nx - light_x) ** 2) / 0.05 + ((ny - 0.36) ** 2) / 0.14))
    bg = bg + g[..., None] * np.array([0.10, 0.085, 0.060], np.float32) * (0.6 + warm)
    return np.clip(bg, 0, 1)


def scene_quote_feng(t, dur, sh=None):
    """冯思翰引述卡：全句打字机 + 引号 + 发言人/时间/出处小字（第一幕，偏冷）。"""
    bg = _card_bg(t, dur, warm=0.0, light_x=0.20)
    p = V.Painter(bg)
    p.flush()
    aq = clamp((t - 0.15) / 0.5)
    if aq > 0:
        V.draw_text(p.rgb, "“", (252, 300), 150, GOLD_D, F_SERIF, anchor="lt",
                    alpha=0.75 * aq)
    lines = ["增程式电动车从单车角度看具备一定价值，",
             "但从整个国家和地球的角度来说，",
             "简直是胡说八道，是最糟糕的方案。"]
    colors = [BONE, BONE, AMBER]
    x_l = 360.0
    y_l = 372.0
    lh = 94.0
    total_chars = sum(len(x) for x in lines)
    t0 = 0.30
    t1 = max(t0 + 2.6, dur - 1.15)
    shown = tw_count(t, t0, t1, total_chars)
    acc = 0
    typing = shown < total_chars
    for k, (line, col) in enumerate(zip(lines, colors)):
        n = max(0, min(len(line), shown - acc))
        if n > 0:
            seg = line[:n]
            V.draw_text(p.rgb, seg, (x_l, y_l + k * lh), 48, col, F_SANS,
                        anchor="lm", alpha=0.96, track=1, glow=8, glow_strength=0.25)
            if n < len(line) and typing:
                w = V.text_size(seg, 48, F_SANS, stroke=0, track=1)[0]
                a = cursor_alpha(t, t0, t1)
                p.stroke([(x_l + w + 4, y_l + k * lh - 28),
                          (x_l + w + 4, y_l + k * lh + 28)], GOLD, 2.0, 0.7 * a)
        acc += len(line)
    if not typing:
        aqc = clamp((t - t1) / 0.4)
        V.draw_text(p.rgb, "”", (1620, y_l + 2 * lh), 120, GOLD_D, F_SERIF,
                    anchor="rm", alpha=0.75 * aqc)
    a_cap = clamp((t - max(0.95, dur * 0.17)) / 0.7)
    if a_cap > 0:
        p.stroke([(360, 726), (360 + 190 * ease_out_cubic(a_cap), 726)], GOLD, 1.1,
                 0.55 * a_cap)
        V.draw_text(p.rgb, "—— 大众集团中国区 CEO 冯思翰，2020 年 9 月 8 日",
                    (360, 772), 28, MUTED, F_SANS_R, anchor="lm",
                    alpha=0.92 * a_cap, track=1)
        V.draw_text(p.rgb, "成都媒体沟通会 · 来源：麻省理工科技评论中文站 / 凤凰网汽车 / 汽车之家",
                    (360, 816), 22, DIM, F_SANS_R, anchor="lm", alpha=0.75 * a_cap,
                    track=1)
    p.bloom(threshold=0.62, strength=0.45)
    return p.to_image()


def scene_quote_li(t, dur, sh=None):
    """李想八字引述卡：打字机逐字 + 引号 + 「李想，2021 年 12 月 22 日（微博）」。"""
    bg = _card_bg(t, dur, warm=0.18, light_x=0.52)
    p = V.Painter(bg)
    p.flush()
    quote = "感谢鞭策，继续努力。"
    x_l, y_l = 486.0, 470.0
    size = 86
    adv = size * 1.02
    t0 = 0.25
    t1 = 3.30
    n = tw_count(t, t0, t1, len(quote))
    aq = clamp((t - 0.15) / 0.4)
    if aq > 0:
        V.draw_text(p.rgb, "“", (x_l - 88, y_l - 92), 120, GOLD_D, F_SERIF,
                    anchor="mm", alpha=0.78 * aq)
    for i in range(n):
        V.draw_text(p.rgb, quote[i], (x_l + i * adv, y_l), size, BONE, F_SANS,
                    anchor="lm", alpha=0.98, glow=10, glow_strength=0.28)
    if t < t1:
        cx = x_l + n * adv + 6
        p.stroke([(cx, y_l - 44), (cx, y_l + 44)], GOLD, 2.2,
                 0.7 * cursor_alpha(t, t0, t1))
    else:
        aqc = clamp((t - t1) / 0.4)
        V.draw_text(p.rgb, "”", (x_l + len(quote) * adv + 30, y_l), 120, GOLD_D,
                    F_SERIF, anchor="lm", alpha=0.8 * aqc)
    a_cap = clamp((t - 3.45) / 0.7)
    if a_cap > 0:
        p.stroke([(x_l, 606), (x_l + 220 * ease_out_cubic(a_cap), 606)], GOLD, 1.1,
                 0.6 * a_cap)
        V.draw_text(p.rgb, "—— 李想，2021 年 12 月 22 日（微博）", (x_l, 652), 30,
                    MUTED, F_SANS_R, anchor="lm", alpha=0.94 * a_cap, track=1)
        V.draw_text(p.rgb, "来源：中国产经网 / 汽车之家车家号", (x_l, 696), 22, DIM,
                    F_SANS_R, anchor="lm", alpha=0.72 * a_cap, track=1)
    p.bloom(threshold=0.62, strength=0.45)
    return p.to_image()


# ---------------------------------------------------------------- 第四幕 数据曲线
def scene_data_curve(t, dur, sh=None):
    """增程退潮：左=2025 全年 123 万 / 2026 1–5 月 41 万（柱高∝数值）；
    右=份额 10.3% → 7.0% 下行线 + 2026-05 单月 -24.9%。"""
    bg = grey_bg(t, dur, base=(0.028, 0.033, 0.038), strength=0.10, cx=0.44, cy=0.44,
                 warm=0.0)
    p = V.Painter(bg)
    # ---------------- 左：销量柱（同一刻度，柱高严格 ∝ 数值）
    base_y = 802.0
    h_max = 336.0
    vmax = float(V_EXT_2025_FULL)
    bx1, bx2 = 486.0, 772.0
    bw = 136.0
    g1a, g1b = dur * 0.02, dur * 0.26
    g2a, g2b = dur * 0.14, dur * 0.44
    h1 = bar_height(V_EXT_2025_FULL, vmax, h_max) * grow_progress(t, g1a, g1b)
    h2 = bar_height(V_EXT_2026_JAN_MAY, vmax, h_max) * grow_progress(t, g2a, g2b)
    p.stroke([(300, base_y), (1040, base_y)], (96, 106, 114), 1.2, 0.6)
    p.fill_rect((bx1 - bw / 2, base_y - h1), (bx1 + bw / 2, base_y), (24, 22, 19), 0.92)
    p.fill_rect((bx1 - bw / 2, base_y - h1), (bx1 + bw / 2, base_y),
                (150, 120, 70), 0.20 + 0.08 * clamp((t - g1b) / 1.2))
    p.stroke([(bx1 - bw / 2, base_y - h1), (bx1 + bw / 2, base_y - h1)], GOLD, 2.6,
             0.95, 12, 0.5)
    p.fill_rect((bx2 - bw / 2, base_y - h2), (bx2 + bw / 2, base_y), (20, 24, 28), 0.92)
    p.fill_rect((bx2 - bw / 2, base_y - h2), (bx2 + bw / 2, base_y),
                (88, 112, 124), 0.16 + 0.08 * clamp((t - g2b) / 1.2))
    p.stroke([(bx2 - bw / 2, base_y - h2), (bx2 + bw / 2, base_y - h2)], STEEL, 2.6,
             0.95, 12, 0.5)
    # ---------------- 右：份额下行线（两点真实数据）
    sx0, sx1 = 1152.0, 1640.0
    sy_b, sy_t = 802.0, 322.0
    vmin, vmax_s = 0.060, 0.110

    def share_y(v):
        return sy_b - (v - vmin) / (vmax_s - vmin) * (sy_b - sy_t)

    y_a = share_y(SHARE_2025_05)
    y_b = share_y(SHARE_2026_05)
    u_axes = ease_out_cubic(clamp((t - dur * 0.44) / max(0.3, dur * 0.05)))
    if u_axes > 0:
        p.stroke([(sx0, sy_b), (sx0 + (sx1 - sx0) * u_axes, sy_b)], (92, 104, 112),
                 1.2, 0.55)
        p.stroke([(sx0, sy_b), (sx0, sy_b - (sy_b - sy_t) * u_axes)], (92, 104, 112),
                 1.2, 0.5)
        for pc in (6, 7, 8, 9, 10, 11):
            yy = share_y(pc / 100.0)
            p.stroke([(sx0 - 5, yy), (sx0 + 5, yy)], (74, 86, 96), 1.0, 0.35)
    u_line = ease_in_out(clamp((t - dur * 0.46) / max(0.4, dur * 0.26)))
    if u_line > 0:
        x_end = sx0 + (sx1 - sx0) * u_line
        y_end = y_a + (y_b - y_a) * u_line
        p.stroke([(sx0, y_a), (x_end, y_end)], AMBER, 2.8, 0.95, 16, 0.7)
        p.dot((x_end, y_end), 5.2, AMBER, 0.95, 14, 0.8)
    p.dot((sx0, y_a), 5.2, STEEL, 0.9, 12, 0.7)
    p.dot((sx1, y_b), 5.2, AMBER, 0.85 * clamp((u_line - 0.95) / 0.05), 14, 0.8) \
        if u_line > 0.95 else None
    p.flush()
    # ---------------- 左：数字与标签（花字 123 万 / 9.7%）
    a_num = clamp((t - g1a) / 0.3)
    if a_num > 0:
        y1 = base_y - bar_height(V_EXT_2025_FULL, vmax, h_max)
        y2 = base_y - bar_height(V_EXT_2026_JAN_MAY, vmax, h_max)
        draw_mixed(p, [("123", GOLD, F_MONO), (" 万", GOLD, F_SANS)],
                   (bx1, y1 - 62), 84, anchor="mm", alpha=0.97 * a_num,
                   glow=16, glow_strength=0.48)
        draw_mixed(p, [("41", STEEL, F_MONO), (" 万", STEEL, F_SANS)],
                   (bx2, y2 - 52), 56, anchor="mm", alpha=0.95 * a_num,
                   glow=10, glow_strength=0.35)
        V.draw_text(p.rgb, "2025 全年", (bx1, base_y + 36), 26, MUTED, F_SANS_R,
                    anchor="mm", alpha=0.7 * a_num, track=2)
        V.draw_text(p.rgb, "2026 1–5 月", (bx2, base_y + 36), 26, MUTED, F_SANS_R,
                    anchor="mm", alpha=0.7 * a_num, track=2)
    a_97 = clamp((t - dur * 0.30) / 0.7)
    if a_97 > 0:
        V.draw_text(p.rgb, "-9.7%", (900, 448), 62, AMBER, F_MONO, anchor="lm",
                    alpha=0.96 * a_97, glow=14, glow_strength=0.45)
        V.draw_text(p.rgb, "1–5 月累计同比", (902, 500), 24, MUTED, F_SANS_R,
                    anchor="lm", alpha=0.8 * a_97, track=2)
    V.draw_text(p.rgb, "增程销量", (300, 268), 26, MUTED, F_SANS_R, anchor="lm",
                alpha=0.62, track=4)
    V.draw_text(p.rgb, "增程份额", (sx0, 268), 26, MUTED, F_SANS_R, anchor="lm",
                alpha=0.62, track=4)
    # ---------------- 右：份额刻度与两端标签
    a_share = clamp((t - dur * 0.42) / 0.7)
    if a_share > 0:
        for pc in (6, 7, 8, 9, 10, 11):
            yy = share_y(pc / 100.0)
            V.draw_text(p.rgb, "%d%%" % pc, (sx0 - 12, yy), 20, DIM, F_MONO,
                        anchor="rm", alpha=0.6 * a_share)
        V.draw_text(p.rgb, "2025-05", (sx0, sy_b + 34), 22, DIM, F_MONO, anchor="mm",
                    alpha=0.6 * a_share)
        V.draw_text(p.rgb, "2026-05", (sx1, sy_b + 34), 22, DIM, F_MONO, anchor="mm",
                    alpha=0.6 * a_share)
    a_pa = clamp((t - dur * 0.46) / 0.6)
    if a_pa > 0:
        V.draw_text(p.rgb, "10.3%", (sx0 + 26, y_a - 30), 44, STEEL, F_MONO,
                    anchor="lm", alpha=0.95 * a_pa, glow=10, glow_strength=0.35)
    a_pb = clamp((t - dur * 0.70) / 0.5)
    if a_pb > 0:
        V.draw_text(p.rgb, "7.0%", (sx1 + 8, y_b - 34), 46, AMBER, F_MONO,
                    anchor="rm", alpha=0.96 * a_pb, glow=12, glow_strength=0.4)
    a_249 = clamp((t - dur * 0.78) / 0.6)
    if a_249 > 0:
        V.draw_text(p.rgb, "5 月单月批发", (sx1, sy_b + 78), 24, MUTED, F_SANS_R,
                    anchor="rm", alpha=0.8 * a_249, track=2)
        V.draw_text(p.rgb, "-24.9%", (sx1, sy_b + 126), 40, AMBER, F_MONO,
                    anchor="rm", alpha=0.95 * a_249, glow=10, glow_strength=0.4)
    a_fn = clamp((t - dur * 0.16) / 0.8)
    if a_fn > 0:
        V.draw_text(p.rgb, "口径：不同周期仅示量级；-9.7% 为 2026 年 1–5 月累计同比 · 来源：乘联会",
                    (300, 900), 22, DIM, F_SANS_R, anchor="lm", alpha=0.6 * a_fn,
                    track=1)
    p.bloom(threshold=0.62, strength=0.5)
    return p.to_image()


# ---------------------------------------------------------------- 收束：空白手册
def scene_blank_manual(t, dur, sh=None):
    """收束：暗桌上一本新的空白手册，右侧暖光，尘埃缓慢漂移（“这本，还没写”）。"""
    bg = table_bg(t, dur, warm=0.62, horizon=0.54)
    nx, ny = grid()
    # 右侧侧光（大片暖光）
    g = np.exp(-(((nx - 0.84) ** 2) / 0.055 + ((ny - 0.40) ** 2) / 0.20))
    bg = bg + g[..., None] * np.array([0.30, 0.24, 0.15], np.float32) * 0.42
    yy = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    bg *= (1.0 - 0.28 * smoothstep(0.80, 1.0, yy))
    p = V.Painter(np.clip(bg, 0, 1))
    # 呼吸式轻推（相机几乎不动，但有生命）
    zoom = 1.0 + 0.010 * math.sin(t * 0.55)
    ccx, ccy = 960.0, 590.0

    def z(x, y):
        return (ccx + (x - ccx) * zoom, ccy + (y - ccy) * zoom)

    cover = np.array([z(636, 418), z(1252, 392), z(1332, 806), z(566, 838)],
                     np.float32)
    # 书在桌面上的柔和阴影
    p.halo(z(950, 840), 560, (8, 7, 6), 0.30)
    p.halo(z(980, 700), 520, (150, 118, 74), 0.045)
    # 书页厚度（左侧与下侧）
    pages = np.array([cover[0], cover[3], (cover[3][0] - 26, cover[3][1] + 16),
                      (cover[0][0] - 26, cover[0][1] + 16)], np.float32)
    p.fill_poly(pages, (178, 170, 154), 0.5)
    for k in range(7):
        f = (k + 1) / 8.0
        p.stroke([(cover[0][0] - 4 - k * 3.0, cover[0][1] + 2 + k * 2.0),
                  (cover[3][0] - 4 - k * 3.0, cover[3][1] + 2 + k * 2.0)],
                 (168, 160, 144), 1.0, 0.35 - k * 0.03)
    # 封面：哑光深炭灰（暖）
    p.fill_poly(cover, (42, 38, 33), 0.97)
    p.fill_poly([z(700, 440), z(1240, 418), z(1300, 780), z(620, 806)],
                (50, 45, 39), 0.55)
    p.stroke(list(cover) + [cover[0]], (150, 126, 88), 1.6, 0.55, 10, 0.35)
    # 封面上的一枚压印方框（无字）
    p.stroke([z(846, 566), z(1180, 550), z(1196, 742), z(858, 760), z(846, 566)],
             (120, 102, 74), 1.0, 0.40)
    p.stroke([z(870, 588), z(1160, 574), z(1174, 720), z(882, 736), z(870, 588)],
             (96, 84, 62), 1.0, 0.28)
    # 侧光：沿封面扫过一条柔光带（用柔光点直接叠在 rgb 上，
    # 避免 Painter 多色 mask 叠加时“后画颜色/前画透明度”的混色问题）
    lp = 0.5 - 0.5 * math.cos(t * 0.22)
    for (uc, rr, aa) in ((0.58 + 0.045 * lp, 155.0, 0.105),
                         (0.66 + 0.045 * lp, 136.0, 0.085),
                         (0.74 + 0.045 * lp, 116.0, 0.065)):
        top = cover[0] + (cover[1] - cover[0]) * uc
        bot = cover[3] + (cover[2] - cover[3]) * uc
        for f in (0.20, 0.46, 0.72, 0.94):
            px = top[0] + (bot[0] - top[0]) * f
            py = top[1] + (bot[1] - top[1]) * f
            p.halo((px, py), rr, (240, 212, 162), aa * 0.62)
    # 下侧页口（纸张厚度）
    for k in range(5):
        off = 6 + k * 4
        p.stroke([(cover[3][0] + 4 + off * 0.6, cover[3][1] + off),
                  (cover[2][0] + 2 + off * 0.6, cover[2][1] + off)],
                 (176, 168, 152), 1.0, 0.20 - k * 0.02)
    for f in (0.30, 0.55, 0.78, 0.94):
        px = cover[1][0] + (cover[2][0] - cover[1][0]) * f
        py = cover[1][1] + (cover[2][1] - cover[1][1]) * f
        p.halo((px - 60, py), 150, (236, 206, 156), 0.065)
    p.stroke([cover[1], cover[2]], (232, 208, 162), 1.8, 0.55, 12, 0.4)
    # 尘埃（在侧光里缓慢漂移）
    xs, ys, rs, phs, sps = dust_motes(22, seed=616, lo=(0.36, 0.18), hi=(0.95, 0.82))
    for i in range(len(xs)):
        dx = xs[i] + 0.010 * math.sin(t * sps[i] * 0.5 + phs[i])
        dy = ys[i] + 0.008 * math.cos(t * sps[i] * 0.42 + phs[i] * 1.3)
        lit = 0.35 + 0.65 * clamp((dx - 0.30) / 0.6)
        a = (0.10 + 0.16 * (0.5 + 0.5 * math.sin(t * sps[i] * 0.8 + phs[i]))) * lit
        p.dot(z(dx * W, dy * H), rs[i] * 0.85, (238, 226, 198), a)
    # ~4.5s「这本还没写」：一丝侧光扫过 + 几粒尘埃被照亮
    beat = clamp((t - dur * 0.42) / max(0.3, dur * 0.10))
    if beat > 0:
        pulse = math.sin(min(1.0, beat) * math.pi) * 0.5 + 0.5
        p.halo(z(1120, 560), 300, (240, 210, 158), 0.10 * pulse)
        for i in range(6):
            bx = 0.58 + 0.06 * i
            by = 0.34 + 0.05 * math.sin(i * 2.1 + t * 0.8)
            p.dot(z(bx * W + 20 * pulse, by * H - 40 * beat), 1.6,
                  (252, 238, 208), 0.22 * pulse)
    # 最后：右上角一页轻轻翘起（“还没写”的呼吸）
    lift = smoothstep(0.55, 0.9, clamp(t / max(dur, 1e-3)))
    if lift > 0:
        br = cover[1]
        tip = (br[0] - 24 * lift, br[1] - 70 * lift)
        p.fill_poly([br, (br[0] - 96, br[1] + 6), tip], (176, 168, 152),
                    0.12 * lift)
        p.stroke([br, tip, (br[0] - 96, br[1] + 6)], (214, 204, 186), 1.0,
                 0.30 * lift)
    p.flush()
    p.bloom(threshold=0.66, strength=0.35)
    return p.to_image()


# ---------------------------------------------------------------- 片尾卡
def scene_end_card(t, dur, sh=None):
    """片尾：虚构人物声明 + AI 辅助制作声明 + 选题核实由人完成 + 参考资料。"""
    bg = warm_bg(t, dur)
    p = V.Painter(bg)
    # 背景：一本手册的极淡轮廓（母题收束）
    a_bg = 0.10 * clamp((t - 0.1) / 1.2)
    p.stroke([(620, 470), (1280, 448), (1352, 828), (568, 856), (620, 470)],
             (140, 120, 88), 1.4, a_bg, 10, 0.3)
    p.flush()
    V.draw_text(p.rgb, "VIBE 知识共赏 · 第 06 期", (960, 220), 24, MUTED, F_SANS_R,
                anchor="mm", alpha=0.72 * clamp((t - 0.08) / 0.6), track=5)
    a = clamp((t - 0.16) / 0.75)
    if a > 0:
        rise = 14 * (1 - ease_out_cubic(clamp((t - 0.16) / 0.7)))
        V.draw_text(p.rgb, "他们说，这是最糟糕的方案", (960, 296 - rise), 58, BONE,
                    F_SERIF, anchor="mm", alpha=0.97 * a, track=3,
                    glow=14, glow_strength=0.38)
    a = clamp((t - 0.58) / 0.65)
    if a > 0:
        V.draw_text(p.rgb, "一场持续六年的技术判决，和它自己的判决", (960, 356), 26,
                    MUTED, F_SANS_R, anchor="mm", alpha=0.82 * a, track=3)
    a = clamp((t - 0.92) / 0.5)
    if a > 0:
        p.stroke([(700, 396), (700 + 520 * a, 396)], GOLD, 1.2, 0.55, 8, 0.35)
        p.flush()
    # 双声明 + 由人完成
    a1 = clamp((t - 1.20) / 0.6)
    if a1 > 0:
        V.draw_text(p.rgb, "本片人物为 AI 生成的虚构形象，不代表任何真实人物",
                    (960, 462), 40, BONE, F_SANS, anchor="mm", alpha=0.97 * a1,
                    track=1, glow=10, glow_strength=0.3)
    a2 = clamp((t - 1.44) / 0.6)
    if a2 > 0:
        V.draw_text(p.rgb, "本片画面与配音含 AI 辅助制作", (960, 520), 44, BONE,
                    F_SANS, anchor="mm", alpha=0.97 * a2, track=1, glow=10,
                    glow_strength=0.3)
    a3 = clamp((t - 1.66) / 0.6)
    if a3 > 0:
        V.draw_text(p.rgb, "选题、核实与判断，由人完成", (960, 576), 38, AMBER,
                    F_SANS_R, anchor="mm", alpha=0.94 * a3, track=2, glow=10,
                    glow_strength=0.35)
    # 参考资料
    a4 = clamp((t - 2.30) / 0.7)
    if a4 > 0:
        V.draw_text(p.rgb, "引述：冯思翰 2020-09-08 成都媒体沟通会（MIT 科技评论中文站 / 凤凰网汽车 / 汽车之家）",
                    (960, 656), 22, DIM, F_SANS_R, anchor="mm", alpha=0.78 * a4,
                    track=1)
        V.draw_text(p.rgb, "上险数据：中国产经网 · 销量/份额：乘联会 2025–2026 · ID.ERA 9X 定位：上汽大众官方（多家媒体报道）",
                    (960, 690), 22, DIM, F_SANS_R, anchor="mm", alpha=0.72 * a4,
                    track=1)
        V.draw_text(p.rgb, "片中对话为创作内容；引述的公开言论均标注时间与出处。",
                    (960, 724), 22, DIM, F_SANS_R, anchor="mm", alpha=0.66 * a4,
                    track=1)
    a5 = clamp((t - 3.05) / 0.7)
    if a5 > 0:
        V.draw_text(p.rgb, "点赞 · 关注，下期见", (960, 800), 28, MUTED, F_SANS_R,
                    anchor="mm", alpha=0.62 * a5, track=4)
    if dur > 8.0:
        fade = 1.0 - smoothstep(dur - 1.2, dur - 0.05, t)
        p.rgb *= fade
    p.bloom(threshold=0.66, strength=0.4)
    return p.to_image()


def scene_outro_black(t, dur, sh=None):
    """尾部黑场：把最后一点暖光收掉。"""
    nx, ny = grid()
    glow = np.exp(-(((nx - 0.72) ** 2) / 0.10 + ((ny - 0.34) ** 2) / 0.18))
    fade = 1.0 - smoothstep(0.0, min(3.0, max(0.3, dur * 0.5)), t)
    rgb = np.full((H, W, 3), 0.004, np.float32)
    rgb += glow[..., None] * np.array([0.055, 0.045, 0.032], np.float32) * fade
    p = V.Painter(rgb)
    p.grain(seed=6, amt=0.004)
    return p.to_image()


SCENES = {
    "cold_title": scene_cold_title,
    "bar_compare": scene_bar_compare,
    "quote_feng": scene_quote_feng,
    "quote_li": scene_quote_li,
    "data_curve": scene_data_curve,
    "blank_manual": scene_blank_manual,
    "end_card": scene_end_card,
    "outro_black": scene_outro_black,
}
