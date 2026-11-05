"""Tiny 3D engine for cinematic 奇门 board shots.

Renders textured quads (tiles / holographic cards), glowing 3D rings, particles
and 3D text planes with a perspective camera, then applies bloom, grade, grain.
Pure PIL/numpy so it runs on CPU fast enough for thousands of frames.
"""
import math
import os

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.abspath(__file__))
W, H = 900, 1600

F_SERIF = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc"
F_SERIF_B = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc"
F_SANS = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
F_SANS_B = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"

GOLD = (240, 202, 110)
GOLD_B = (255, 214, 79)
TEAL = (79, 195, 247)
RED = (226, 96, 92)
PURPLE = (166, 136, 205)
WHITE = (238, 245, 252)
MUTED = (156, 180, 202)
DIM = (96, 122, 146)


def clamp(v, a=0.0, b=1.0):
    return a if v < a else (b if v > b else v)


def ease_out(t):
    t = clamp(t)
    return 1 - (1 - t) ** 3


def ease_in_out(t):
    t = clamp(t)
    return 0.5 - 0.5 * math.cos(math.pi * t)


def lerp(a, b, t):
    return a + (b - a) * t


# ------------------------------------------------------------------ camera
class Camera:
    def __init__(self, pos, target, fov_deg=40.0, up=(0, 1, 0)):
        self.pos = np.array(pos, dtype=np.float64)
        self.target = np.array(target, dtype=np.float64)
        f = self.target - self.pos
        self.fwd = f / np.linalg.norm(f)
        r = np.cross(self.fwd, np.array(up, dtype=np.float64))
        self.right = r / np.linalg.norm(r)
        self.up = np.cross(self.right, self.fwd)
        self.f = (H / 2.0) / math.tan(math.radians(fov_deg) / 2.0)

    def project(self, pts):
        """pts: (N,3) world -> (N,2) screen + (N,) depth z>0 in front."""
        p = np.asarray(pts, dtype=np.float64) - self.pos
        xc = p @ self.right
        yc = p @ self.up
        zc = p @ self.fwd
        z = np.maximum(zc, 1e-6)
        sx = W / 2.0 + self.f * xc / z
        sy = H / 2.0 - self.f * yc / z
        return np.stack([sx, sy], axis=-1), zc


# ------------------------------------------------------------------ textures
_TEX_CACHE = {}


def tile_tex(idx):
    key = ("tile", idx)
    im = _TEX_CACHE.get(key)
    if im is None:
        im = Image.open(os.path.join(ROOT, "assets", "tiles", f"tile_{idx}.png")).convert("RGBA")
        im = im.resize((320, 320), Image.LANCZOS)
        _TEX_CACHE[key] = im
    return im


def text_tex(s, size, color=WHITE, font_path=F_SERIF_B, stroke=0, stroke_fill=(0, 0, 0),
             glow=0, glow_color=None, glow_strength=0.9, pad=0):
    """Render text to an RGBA texture (tight bbox + padding)."""
    key = ("text", s, size, color, font_path, stroke, glow, glow_color, round(glow_strength, 2))
    im = _TEX_CACHE.get(key)
    if im is not None:
        return im
    fnt = ImageFont.truetype(font_path, size)
    d = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
    box = d.textbbox((0, 0), s, font=fnt, stroke_width=stroke)
    tw = box[2] - box[0]
    th = box[3] - box[1]
    p = pad + int(size * 0.25) + (glow * 2 if glow else 0)
    im = Image.new("RGBA", (tw + 2 * p, th + 2 * p), (0, 0, 0, 0))
    dd = ImageDraw.Draw(im)
    tx, ty = p - box[0], p - box[1]
    if glow:
        gl = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ImageDraw.Draw(gl).text((tx, ty), s, font=fnt, fill=(glow_color or color) + (255,),
                                stroke_width=stroke, stroke_fill=(glow_color or color) + (255,))
        gl = gl.filter(ImageFilter.GaussianBlur(glow))
        a = gl.getchannel("A").point(lambda v: int(v * glow_strength))
        gl.putalpha(a)
        im.alpha_composite(gl)
    dd.text((tx, ty), s, font=fnt, fill=color + (255,), stroke_width=stroke,
            stroke_fill=stroke_fill + (255,))
    im._glyph = (tw, th, p, p)
    _TEX_CACHE[key] = im
    return im


def sprite_glow(r=64, color=(255, 210, 110)):
    key = ("sprite", r, color)
    im = _TEX_CACHE.get(key)
    if im is None:
        y, x = np.ogrid[:2 * r, :2 * r]
        d2 = (x - r) ** 2 + (y - r) ** 2
        g = np.exp(-d2 / (2 * (r * 0.32) ** 2))
        a = (np.clip(g, 0, 1) * 255).astype(np.uint8)
        im = Image.new("RGBA", (2 * r, 2 * r), color + (255,))
        im.putalpha(Image.fromarray(a))
        _TEX_CACHE[key] = im
    return im


# ------------------------------------------------------------------ helpers
def _homography(src, dst):
    """H mapping src (u,v) -> dst (x,y), 4 corners, using DLT."""
    A = []
    for (u, v), (x, y) in zip(src, dst):
        A.append([u, v, 1, 0, 0, 0, -x * u, -x * v, -x])
        A.append([0, 0, 0, u, v, 1, -y * u, -y * v, -y])
    A = np.asarray(A, dtype=np.float64)
    _, _, Vt = np.linalg.svd(A)
    return Vt[-1].reshape(3, 3)


def quad_texture(dst_quad, tex, alpha=1.0, blur=0.0, shade=1.0):
    """Render textured quad. dst_quad: 4 screen points in order TL,TR,BR,BL."""
    dst = np.asarray(dst_quad, dtype=np.float64)
    x0, y0 = dst.min(axis=0)
    x1, y1 = dst.max(axis=0)
    bx, by = int(math.floor(x0)), int(math.floor(y0))
    bw, bh = int(math.ceil(x1)) - bx + 2, int(math.ceil(y1)) - by + 2
    if bw < 2 or bh < 2 or bw > W * 2 or bh > H * 2:
        return None
    tw, th = tex.size
    src = [(0, 0), (tw, 0), (tw, th), (0, th)]
    Hm = _homography(src, dst)
    try:
        Hi = np.linalg.inv(Hm)
    except np.linalg.LinAlgError:
        return None
    # map bbox-local coords (x+bx, y+by) -> source
    a, b, c = Hi[0]
    d, e, f = Hi[1]
    g, h, i = Hi[2]
    # u = (a*(x+bx)+b*(y+by)+c) / (g*(x+bx)+h*(y+by)+i)
    c2 = a * bx + b * by + c
    f2 = d * bx + e * by + f
    i2 = g * bx + h * by + i
    coeffs = (a / i2, b / i2, c2 / i2, d / i2, e / i2, f2 / i2, g / i2, h / i2)
    try:
        layer = tex.transform((bw, bh), Image.PERSPECTIVE, coeffs, Image.BILINEAR)
    except Exception:
        return None
    if shade != 1.0:
        arr = np.asarray(layer.convert("RGB"), dtype=np.float32) * shade
        rgb = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGBA")
        rgb.putalpha(layer.getchannel("A"))
        layer = rgb
    if blur > 0.2:
        layer = layer.filter(ImageFilter.GaussianBlur(blur))
    if alpha < 0.999:
        a2 = layer.getchannel("A").point(lambda v: int(v * alpha))
        layer.putalpha(a2)
    return layer, bx, by


def draw_items(img, items):
    """items: list of dicts with 'depth' (draw far->near) and draw fn."""
    for it in sorted(items, key=lambda x: -x["depth"]):
        it["draw"](img)


_VIG = {}


def _vignette_mask(strength):
    im = _VIG.get(strength)
    if im is None:
        yy, xx = np.ogrid[:H, :W]
        nx = (xx - W / 2) / (W / 2)
        ny = (yy - H / 2) / (H / 2)
        d = np.sqrt(nx ** 2 + ny ** 2) / 1.414
        im = np.clip(1 - strength * (d ** 2.2), 0, 1).astype(np.float32)
        _VIG[strength] = im
    return im


_LEAK = None


def _leak_img():
    global _LEAK
    if _LEAK is None:
        yy, xx = np.ogrid[:H, :W]
        g = np.exp(-((xx - W * 0.86) ** 2) / (2 * (W * 0.30) ** 2)) * np.exp(-((yy - H * 0.20) ** 2) / (2 * (H * 0.34) ** 2))
        arr = np.zeros((H, W, 3), dtype=np.float32)
        arr[..., 0] = g * 72
        arr[..., 1] = g * 40
        arr[..., 2] = g * 14
        _LEAK = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    return _LEAK


class Renderer:
    def __init__(self, bg=None):
        self.bg = bg

    def base(self):
        if self.bg is not None:
            return self.bg.copy()
        return bg_base().copy()

    def finish(self, img, bloom=0.7, grade=1.0, grain_amt=3.4, seed=0, vignette=0.5,
               leak=0.0):
        rgb = img.convert("RGB")
        small = rgb.resize((W // 8, H // 8), Image.BILINEAR)
        arr = np.asarray(small, dtype=np.float32)
        lum = arr.mean(axis=2, keepdims=True)
        thr = 105.0
        bright = np.clip((lum - thr) / (255 - thr), 0, 1) ** 1.5
        bloom_img = Image.fromarray(np.clip(arr * bright, 0, 255).astype(np.uint8)).convert("RGB")
        bloom_img = bloom_img.filter(ImageFilter.GaussianBlur(6)).resize((W, H), Image.BILINEAR)
        if bloom > 0:
            rgb = ImageChops.add(rgb, bloom_img.point(lambda v: int(v * bloom)))
        if leak > 0:
            rgb = ImageChops.add(rgb, _leak_img().point(lambda v: int(v * leak)))
        arr = np.asarray(rgb, dtype=np.float32) / 255.0
        arr = np.clip(arr, 0, 1) ** (1.0 / 1.05)
        arr[..., 2] = np.clip(arr[..., 2] * 1.05 + 0.004, 0, 1)
        arr[..., 0] = np.clip(arr[..., 0] * 1.01, 0, 1)
        arr = np.clip((arr - 0.5) * 1.06 + 0.5, 0, 1)
        if vignette > 0:
            arr *= _vignette_mask(vignette)[:, :, None]
        rgb = Image.fromarray(np.clip(arr * 255, 0, 255).astype(np.uint8))
        if grain_amt > 0:
            rng = np.random.default_rng(seed + 7)
            noise = rng.integers(-6, 7, (H, W), dtype=np.int16)
            a = np.asarray(rgb, dtype=np.int16) + (noise[:, :, None] * (grain_amt / 6.0)).astype(np.int16)
            rgb = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
        return rgb

# ------------------------------------------------------------------ background
_BG = None


def bg_base():
    global _BG
    if _BG is not None:
        return _BG
    y, x = np.ogrid[:H, :W]
    nx = (x - W * 0.5) / (W * 0.5)
    ny = (y - H * 0.42) / (H * 0.55)
    d = np.sqrt(nx ** 2 + ny ** 2)
    base = np.zeros((H, W, 3), dtype=np.float32)
    glow = np.exp(-(d ** 2) * 2.0)
    base[..., 0] = 6 + 18 * glow
    base[..., 1] = 9 + 34 * glow
    base[..., 2] = 18 + 58 * glow
    # subtle stars / dust
    rng = np.random.default_rng(9)
    for _ in range(260):
        sx, sy = int(rng.uniform(0, W)), int(rng.uniform(0, H))
        b = rng.uniform(4, 26)
        r = rng.integers(0, 2)
        base[max(0, sy - r):sy + r + 1, max(0, sx - r):sx + r + 1] += b * 0.35
    _BG = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8)).convert("RGBA")
    return _BG
