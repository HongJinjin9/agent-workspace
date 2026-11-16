#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""代码渲染的 H3 首帧构图（无实拍素材/实拍构图不符的镜）。

设计稿 §6.1 允许首帧「含代码画的图形与文字」，但本模块**不放任何文字/数字/UI 可读内容**：
只给冷灰影调 + 构图形状（内饰/屏幕发光条/侧窗/车头/车尾/杯架/长焦高速），
让 H3 从这一帧“长出”运动；信息与数字全部由代码叠加层在成片中另画。
画布 1920×1080 渲染后按目标画幅裁切缩放（864×480 / 1280×736）。
"""
import math

import numpy as np
from PIL import Image

import ep08viz as v


def _canvas(tint=v.TEAL, strength=0.10, cx=0.5, cy=0.5):
    return v.bg_frame(tint=tint, strength=strength, cx=cx, cy=cy, grid=False)


def _finish(p, crop=(0.5, 0.5), out_size=(864, 480), vig=0.34, grain=0.020):
    p.vignette(vig)
    p.grain(seed=20261116, amt=grain)
    im = p.to_image()
    # 代码构图的 H3 首帧需要足够结构信息：提亮 + 提对比（H3 会继承首帧曝光/对比）
    a = np.asarray(im, np.float32) / 255.0
    a = np.clip(a * 1.55, 0, 1)
    a = np.clip((a - 0.5) * 1.14 + 0.5, 0, 1)
    a = np.clip(a * 1.05 + 0.012, 0, 1)
    im = Image.fromarray((a * 255).astype(np.uint8))
    W, H = im.size
    tw, th = out_size
    ar = tw / float(th)
    # cover 裁切
    if W / float(H) > ar:
        nw = int(round(H * ar)); x0 = int((W - nw) * crop[0]); box = (x0, 0, x0 + nw, H)
    else:
        nh = int(round(W / ar)); y0 = int((H - nh) * crop[1]); box = (0, y0, W, y0 + nh)
    return im.crop(box).resize((tw, th), Image.LANCZOS)


# ---------------------------------------------------------------- S01 hero：车内中控/仪表
def art_s01(out_size=(1280, 736)):
    bg = _canvas(v.TEAL, 0.08, cx=0.45, cy=0.5)
    p = v.Painter(bg)
    W, H = v.W, v.H
    # 前挡风：上方暗带 + 车外红色尾灯 bokeh
    p.fill_poly(np.array([[0, 0], [W, 0], [W, 380], [0, 320]], np.float32), (8, 11, 14), 0.85)
    for k, (x, y, r) in enumerate(((300, 240, 60), (380, 200, 30), (1350, 220, 46), (1470, 250, 24))):
        p.halo((x, y), r, v.EMBER, 0.20)
    # 仪表台轮廓（一条缓弧）
    p.stroke([(0, 380), (420, 352), (980, 356), (W, 392)], v.LINE, 2.0, 0.8)
    # 中控屏：屏幕占画面约 1/3，只画发光条（无任何文字/数字）
    sx0, sy0, sx1, sy1 = 700, 300, 1250, 640
    p.stroke(v._rounded_rect_pts(sx0 - 8, sy0 - 8, sx1 + 8, sy1 + 8, 18), v.STEEL, 2.2, 0.55, 10, 0.4)
    p.fill_rect((sx0, sy0), (sx1, sy1), (6, 10, 12), 0.95)
    # 屏幕内的能量条（琥珀=放电→画面右端收窄，暗示即将翻转）
    bars = ((760, 340, 780, 600, v.AMBER, 0.55), (820, 372, 840, 600, v.AMBER, 0.42),
            (880, 404, 900, 600, v.TEAL, 0.30), (940, 436, 960, 600, v.TEAL, 0.24))
    for (x0, y0, x1, y1, col, a) in bars:
        p.fill_rect((x0, y0), (x1, y1), col, a)
        p.stroke([(x0, y0), (x0, y1)], col, 1.4, a + 0.2, 12, 0.5)
    # 一条能量通道横线（屏幕中央）
    p.stroke([(sx0 + 40, 470), (sx1 - 40, 470)], v.TEAL, 2.2, 0.55, 14, 0.5)
    for xx in range(sx0 + 90, sx1 - 60, 110):
        p.dot((xx, 470), 3.0, v.TEAL, 0.75, glow=12)
    # 方向盘弧 + 手（剪影，不露脸）
    p.stroke([v.polar(420, 720, 250, d) for d in range(196, 345, 3)], v.STEEL, 18.0, 0.22)
    p.stroke([v.polar(420, 720, 250, d) for d in range(196, 345, 3)], v.STEEL, 2.0, 0.5)
    # 中央出风口
    p.stroke(v._rounded_rect_pts(560, 430, 680, 500, 8), v.DIM, 1.4, 0.6)
    p.flush()
    return _finish(p, crop=(0.5, 0.5), out_size=out_size, vig=0.38)


# ---------------------------------------------------------------- S02 侧窗长下坡
def art_s02(out_size=(864, 480)):
    bg = _canvas(v.ICE, 0.06, cx=0.4, cy=0.5)
    p = v.Painter(bg)
    W, H = v.W, v.H
    # 左侧 72% 为车窗：远处道路与护栏线
    win = np.array([[0, 90], [1360, 40], [1400, 980], [0, 1010]], np.float32)
    p.fill_poly(win, (10, 14, 18), 0.92)
    # 下坡路面（斜向）
    p.fill_poly(np.array([[0, 700], [1400, 520], [1400, 1010], [0, 1010]], np.float32),
                (18, 24, 28), 0.9)
    # 护栏立柱：随下坡斜线排列
    for k in range(14):
        x = 60 + k * 100
        y = 700 - k * 13
        p.stroke([(x, y), (x + 4, y - 110)], v.STEEL, 4.0, 0.55)
        p.stroke([(x + 4, y - 78), (x + 104, y - 91)], v.STEEL, 2.0, 0.35)
    # 路灯/车灯光斑：横向拉长
    for k, (x, y, w) in enumerate(((240, 560, 180), (560, 520, 150), (900, 500, 200),
                                   (1150, 470, 130), (180, 760, 90))):
        p.halo((x, y), 46, v.AMBER, 0.16)
        p.stroke([(x - w / 2, y), (x + w / 2, y)], v.AMBER, 6.0, 0.22, 18, 0.5)
    # 右侧窗框/内饰暗边
    p.fill_poly(np.array([[1360, 0], [W, 0], [W, H], [1400, H]], np.float32), (14, 18, 22), 0.98)
    p.stroke([(1368, 30), (1400, 980)], v.STEEL, 3.0, 0.4)
    p.flush()
    return _finish(p, crop=(0.5, 0.5), out_size=out_size, vig=0.33)


# ---------------------------------------------------------------- S48 高速低机位
def art_s48(out_size=(864, 480)):
    bg = _canvas(v.TEAL, 0.06, cx=0.5, cy=0.6)
    p = v.Painter(bg)
    W, H = v.W, v.H
    # 路面占下 2/3：透视车道线
    p.fill_poly(np.array([[0, 420], [W, 400], [W, H], [0, H]], np.float32), (16, 21, 25), 0.95)
    for k in range(6):
        x0 = 300 + k * 260
        p.stroke([(x0, H), (x0 + (x0 - 960) * -0.25, 460)], v.MUTED, 3.0, 0.22)
    p.stroke([(0, 690), (W, 660)], v.MUTED, 2.0, 0.18)
    # 车头剪影：左侧入画，车灯两束
    body = np.array([[120, 700], [560, 640], [640, 520], [520, 420], [300, 400],
                     [140, 470], [80, 600]], np.float32)
    p.fill_poly(body, (10, 13, 16), 0.97)
    p.stroke(body, v.STEEL, 2.4, 0.55, closed=True)
    p.dot((240, 590), 16, v.WHITE, 0.85, glow=40)
    p.dot((470, 560), 14, v.WHITE, 0.8, glow=36)
    # 车灯光锥
    for (x, y) in ((240, 590), (470, 560)):
        p.fill_poly(np.array([[x, y], [x + 520, y + 60], [x + 520, y + 260], [x, y + 90]], np.float32),
                    v.ICE, 0.06)
    # 速度线（横向拉丝）
    for k in range(7):
        y = 430 + k * 26
        p.stroke([(900 + k * 30, y), (1700, y - 6)], v.MUTED, 2.0, 0.10)
    p.flush()
    return _finish(p, crop=(0.5, 0.55), out_size=out_size, vig=0.34)


# ---------------------------------------------------------------- S50 湿滑急刹（侧后 45°）
def art_s50(out_size=(864, 480)):
    bg = _canvas(v.EMBER, 0.06, cx=0.5, cy=0.55)
    p = v.Painter(bg)
    W, H = v.W, v.H
    # 湿路面
    p.fill_poly(np.array([[0, 520], [W, 470], [W, H], [0, H]], np.float32), (12, 17, 20), 0.95)
    for k in range(6):
        p.stroke([(0, 560 + k * 70), (W, 520 + k * 70)], v.STEEL, 1.6, 0.10)
    # 车身剪影（侧后 45°，占中左）
    body = np.array([[160, 640], [240, 470], [560, 400], [900, 450], [980, 560],
                     [980, 660], [760, 700], [300, 710]], np.float32)
    p.fill_poly(body, (9, 12, 15), 0.98)
    p.stroke(body, v.STEEL, 2.2, 0.5, closed=True)
    # 尾灯两组（红）
    for (x, y) in ((880, 580), (880, 640)):
        p.fill_rect((x - 26, y - 12), (x + 26, y + 12), v.EMBER, 0.8)
        p.halo((x, y), 70, v.EMBER, 0.25)
    # 水花颗粒
    rng = np.random.default_rng(8)
    for _ in range(120):
        x = rng.uniform(120, 980); y = rng.uniform(600, 900)
        p.dot((x, y), rng.uniform(1.0, 3.0), v.ICE, rng.uniform(0.15, 0.5))
    # 雨丝
    for _ in range(40):
        x = rng.uniform(0, W); y = rng.uniform(0, 500)
        p.stroke([(x, y), (x - 14, y + 90)], v.ICE, 1.2, 0.12)
    p.flush()
    return _finish(p, crop=(0.5, 0.5), out_size=out_size, vig=0.36)


# ---------------------------------------------------------------- S55 杯架水面
def art_s55(out_size=(864, 480)):
    bg = _canvas(v.TEAL, 0.07, cx=0.5, cy=0.5)
    p = v.Painter(bg)
    W, H = v.W, v.H
    # 中央扶手台面
    p.fill_rect((0, 300), (W, H), (12, 16, 20), 0.95)
    p.stroke([(0, 304), (W, 304)], v.STEEL, 2.0, 0.35)
    # 两个杯架圆孔 + 水面
    for (cx, cy, r) in ((700, 640, 170), (1130, 620, 160)):
        p.dark_circle((cx, cy), r + 26, factor=0.35)
        p.stroke([v.polar(cx, cy, r, d) for d in range(0, 361, 4)], v.STEEL, 4.0, 0.6, closed=True)
        p.stroke([v.polar(cx, cy, r - 24, d) for d in range(0, 361, 4)], v.STEEL, 1.6, 0.4, closed=True)
        # 液面：椭圆高光
        p.fill_circle((cx, cy + 10), r - 30, (30, 52, 56), 0.85)
        pts = [v.polar(cx, cy + 10, r - 34, d) for d in range(0, 361, 6)]
        p.stroke(np.array(pts), v.TEAL_P, 1.8, 0.5, 12, 0.5, closed=True)
        p.halo((cx - r * 0.2, cy - r * 0.1), r * 0.5, v.TEAL, 0.12)
    # 前景（方向盘边缘虚化）
    p.stroke([v.polar(80, 1200, 620, d) for d in range(200, 330, 3)], v.LINE, 40.0, 0.5)
    p.flush()
    return _finish(p, crop=(0.5, 0.5), out_size=out_size, vig=0.35)


# ---------------------------------------------------------------- S57 高速长焦（车身占左 1/3）
def art_s57(out_size=(864, 480)):
    bg = _canvas(v.TEAL, 0.05, cx=0.5, cy=0.5)
    p = v.Painter(bg)
    W, H = v.W, v.H
    # 远景路面：低对比横带
    p.fill_poly(np.array([[0, 500], [W, 480], [W, 760], [0, 800]], np.float32), (14, 19, 23), 0.9)
    for k in range(4):
        p.stroke([(0, 560 + k * 52), (W, 540 + k * 52)], v.STEEL, 1.4, 0.14)
    # 车身剪影占左 1/3（长焦压缩）
    car = np.array([[60, 700], [90, 560], [300, 500], [560, 520], [640, 610], [630, 720],
                    [380, 750], [120, 745]], np.float32)
    p.fill_poly(car, (9, 12, 15), 0.98)
    p.stroke(car, v.STEEL, 2.2, 0.55, closed=True)
    # 车灯与反光
    p.dot((620, 620), 10, v.WHITE, 0.7, glow=26)
    p.dot((96, 660), 8, v.EMBER, 0.7, glow=22)
    # 前景模糊（长焦虚化条带）
    for k in range(5):
        p.stroke([(0, 150 + k * 42), (W, 130 + k * 42)], v.MUTED, 10.0, 0.08)
    p.flush()
    return _finish(p, crop=(0.45, 0.5), out_size=out_size, vig=0.34)


RENDER = {
    "art_s01": art_s01,
    "art_s02": art_s02,
    "art_s48": art_s48,
    "art_s50": art_s50,
    "art_s55": art_s55,
    "art_s57": art_s57,
}


def render(name, out_size):
    fn = RENDER[name]
    im = fn(out_size)
    return im
