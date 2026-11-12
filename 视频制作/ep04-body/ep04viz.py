#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第 04 期《你的身体，比参数表更懂车》视觉库
==========================================
横屏 1920×1080 / 24fps / 2.35:1 遮幅（上下各 132px 黑边由 finalize 统一加）。

设计语言（承接「vibe 知识共赏」系列）：
- 真实 B-roll / 静帧底片压暗、冷蓝青影调 + 暖琥珀高光；
- 数据层是「压在实拍上的光」：细线 + 柔辉光 + 等宽数字刻度，不做灰底图表卡；
- 曲线用真实数学函数生成（阻尼振荡 / 二阶系统冲击响应 / jerk 导数 / 心跳合成）；
- 全片统一颗粒、暗角、调色；字幕在 2.35 遮幅下黑边内，不与画面争第一视觉重点。

本模块只放可复用图元（cv2 矢量 + PIL 文字 + numpy 后期），场景在 scene_body.py。
"""
import math
import os

import cv2
import numpy as np
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

# ---------------------------------------------------------------- palette
INK = (6, 10, 14)
INK2 = (12, 18, 24)
BONE = (242, 238, 229)
MUTED = (150, 166, 176)
DIM = (92, 110, 122)
TEAL = (74, 226, 212)
TEAL_D = (24, 96, 100)
AMBER = (244, 172, 98)
GOLD = (235, 197, 122)
EMBER = (232, 92, 80)
ICE = (168, 222, 238)
WHITE = (248, 246, 240)


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


# ---------------------------------------------------------------- math signals
def damped_osc(t, freq_hz=1.6, zeta=0.3, amp=1.0, phase=0.0):
    """二阶欠阻尼冲击响应：x(t)=A e^{-ζωt} sin(ω_d t)（真实数学函数）。"""
    omega = 2 * math.pi * freq_hz
    wd = omega * math.sqrt(max(1e-6, 1 - zeta ** 2))
    return amp * np.exp(-zeta * omega * t) * np.sin(wd * t + phase)


def two_dof_quarter_car(dt=1.0 / 480.0, dur=20.0, ms=320.0, mu=42.0, ks=26000.0,
                        kt=240000.0, cs=1400.0, bump_h=0.11, bump_t=0.16,
                        speed_mps=0.0):
    """1/4 车二自由度模型：簧上/簧下质量、悬架弹簧+阻尼、轮胎刚度。

    以「路面凸起」为输入（半正弦），RK4 积分，返回时间轴与车身/车轮位移。
    ms/mu: kg；ks/kt: N/m；cs: N·s/m；bump_h: m。
    默认参数对应：车身固有频率 ≈ 1.4 Hz、车轮 ≈ 12 Hz、阻尼比 ≈ 0.2。
    """
    n = int(dur / dt)
    t = np.arange(n) * dt
    zs = np.zeros(n)
    zu = np.zeros(n)
    zs[0] = 0.0
    zu[0] = 0.0
    vs = 0.0
    vu = 0.0

    def road(tt):
        if tt < 0 or tt > bump_t:
            return 0.0
        return bump_h * 0.5 * (1 - math.cos(2 * math.pi * tt / bump_t))

    def acc(zs, zu, vs, vu, tt):
        # 悬架力（车身对车轮的相对位移/速度）
        fs = ks * (zs - zu) + cs * (vs - vu)
        fu = kt * (zu - road(tt))
        a_s = -fs / ms
        a_u = (fs - fu) / mu
        return a_s, a_u

    for i in range(1, n):
        tt = t[i]
        a_s, a_u = acc(zs[i - 1], zu[i - 1], vs, vu, tt)
        # RK4（简化：状态 [zs, vs, zu, vu]）
        def deriv(zs_, vs_, zu_, vu_, t_):
            fs = ks * (zs_ - zu_) + cs * (vs_ - vu_)
            fu = kt * (zu_ - road(t_))
            return vs_, -fs / ms, vu_, (fs - fu) / mu

        y = (zs[i - 1], vs, zu[i - 1], vu)
        k1 = deriv(*y, tt)
        y2 = tuple(y[j] + 0.5 * dt * k1[j] for j in range(4))
        k2 = deriv(*y2, tt + dt / 2)
        y3 = tuple(y[j] + 0.5 * dt * k2[j] for j in range(4))
        k3 = deriv(*y3, tt + dt / 2)
        y4 = tuple(y[j] + dt * k3[j] for j in range(4))
        k4 = deriv(*y4, tt + dt)
        ynew = tuple(y[j] + dt / 6 * (k1[j] + 2 * k2[j] + 2 * k3[j] + k4[j]) for j in range(4))
        zs[i], vs, zu[i], vu = ynew
    return t, zs, zu


# ---------------------------------------------------------------- text
_TEX = {}


def _font(path, size):
    key = ("font", path, size)
    f = _TEX.get(key)
    if f is None:
        f = ImageFont.truetype(path, size)
        _TEX[key] = f
    return f


def text_tex(s, size, color=BONE, font=F_SERIF, stroke=0, stroke_color=(0, 0, 0),
             track=0.0, alpha=255):
    """渲染一段文字为 RGBA（带字距 track px）。缓存。"""
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
        """把累积的按颜色 mask 一次性合成到画布（uint8 组装 + 单次 float 合成）。"""
        if not self._masks and not self._glows:
            return self
        paint = np.zeros((H, W, 3), np.uint8)
        pa = np.zeros((H, W), np.uint8)
        for color, m in self._masks.items():
            if not m.any():
                continue
            paint[m.astype(bool)] = np.array(color, np.uint8)
            np.maximum(pa, m, out=pa)
        if self._glows:
            gh, gw = H // 4, W // 4
            gpaint = np.zeros((gh, gw, 3), np.float32)
            ga = np.zeros((gh, gw), np.float32)
            for (color, _r), g in self._glows.items():
                if not g.any():
                    continue
                gb = cv2.GaussianBlur(g, (0, 0), max(0.9, _r / 6.0)).astype(np.float32) / 255.0
                gb *= glow_strength
                col = np.array(color, np.float32) / 255.0
                gpaint = col * gb[..., None] + gpaint * (1 - gb[..., None])
                ga = gb + ga * (1 - gb)
            gpaint = cv2.resize(gpaint, (W, H), interpolation=cv2.INTER_LINEAR)
            ga = cv2.resize(ga, (W, H), interpolation=cv2.INTER_LINEAR)
            a_f = ga[..., None]
            paint = ((gpaint * a_f + paint.astype(np.float32) / 255.0 * (1 - a_f)) * 255).astype(np.uint8)
            pa = ((ga + pa.astype(np.float32) / 255.0 * (1 - ga)) * 255).astype(np.uint8)
        a = pa.astype(np.float32) / 255.0
        a = np.clip(a, 0, 1)
        self.rgb *= (1 - a[..., None])
        self.rgb += (paint.astype(np.float32) / 255.0) * a[..., None]
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
