"""Cinematic 3D 奇门 board video (v2 rework).

Real 3D: tiles are textured quads with thickness, lit edges, flying in from space,
rings orbit in 3D, dust particles, holographic panels, camera dolly/orbit, DOF,
bloom, anamorphic streak, grain.
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine3d as E
from engine3d import (W, H, GOLD, GOLD_B, TEAL, RED, PURPLE, WHITE, MUTED, DIM, F_SERIF,
                      F_SERIF_B, F_SANS, F_SANS_B, clamp, ease_out, ease_in_out, lerp)

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "work", "frames2")
os.makedirs(OUT, exist_ok=True)
FPS = 24

# ------------------------------------------------------------------ board data
PALACES = [
    ("巽四宫", "己", "天柱", "伤门", "九地", False),
    ("离九宫", "癸", "天心", "杜门", "九天", False),
    ("坤二宫", "辛", "天蓬·符", "景门", "值符", True),
    ("震三宫", "庚", "天芮", "生门", "玄武", False),
    ("中五宫", "戊", "天禽寄坤", "", "", False),
    ("兑七宫", "丙", "天任", "死门", "螣蛇", True),
    ("艮八宫", "丁", "天英", "休门·使", "白虎", False),
    ("坎一宫", "壬", "天辅", "开门", "六合", False),
    ("乾六宫", "乙", "天冲", "惊门", "太阴", False),
]
ORDER = [4, 3, 2, 1, 0, 8, 7, 6, 5]
STEP = 0.37
TILE = 0.34
TH = 0.045


def palace_center(idx):
    col, row = idx % 3, idx // 3
    return np.array([(col - 1) * STEP, (1 - row) * STEP, 0.0], dtype=np.float64)


def tile_corners(idx, size=TILE, z=0.04, rot=0.0, center=None):
    c = palace_center(idx) + np.array([0, 0, z]) if center is None else np.array(center)
    h = size / 2
    pts = np.array([(-h, h, 0), (h, h, 0), (h, -h, 0), (-h, -h, 0)], dtype=np.float64)
    if abs(rot) > 1e-6:
        ca, sa = math.cos(rot), math.sin(rot)
        R = np.array([[ca, -sa, 0], [sa, ca, 0], [0, 0, 1]])
        pts = pts @ R.T
    return pts + c


# ------------------------------------------------------------------ textures
_DARK_EDGE = None


def edge_image():
    global _DARK_EDGE
    if _DARK_EDGE is None:
        im = Image.new("RGBA", (8, 128), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        for y in range(128):
            t = y / 127.0
            v = int(26 - 14 * t)
            d.line([(0, y), (7, y)], fill=(v, int(v * 1.35), int(v * 1.7), 255))
        _DARK_EDGE = im
    return _DARK_EDGE


_PLATE = None


def plate_image():
    global _PLATE
    if _PLATE is None:
        s = 1024
        im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((10, 10, s - 10, s - 10), radius=40, fill=(7, 12, 20, 255))
        # subtle inner glow border
        for i, a in ((2, 90), (6, 30), (12, 12)):
            d.rounded_rectangle((10 + i, 10 + i, s - 10 - i, s - 10 - i), radius=40 - i,
                                outline=(90, 160, 210, a), width=1)
        # faint grid
        for i in range(1, 9):
            x = 10 + i * (s - 20) / 9
            d.line([(x, 20), (x, s - 20)], fill=(80, 140, 190, 8), width=1)
            y = 10 + i * (s - 20) / 9
            d.line([(20, y), (s - 20, y)], fill=(80, 140, 190, 8), width=1)
        # radial vignette inside plate
        y, x = np.ogrid[:s, :s]
        r = np.sqrt((x - s / 2) ** 2 + (y - s / 2) ** 2) / (s / 2)
        dk = np.clip(r, 0, 1) ** 2
        arr = np.asarray(im.convert("RGB"), dtype=np.float32) * (1 - 0.45 * dk[:, :, None])
        a = im.getchannel("A")
        im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGBA")
        im.putalpha(a)
        _PLATE = im
    return _PLATE


_CARD_CACHE = {}


def card_tex(title, lines, accent=GOLD, kicker="", width=760, scale=1.0, glow=True):
    key = (title, tuple(lines), accent, kicker, width)
    im = _CARD_CACHE.get(key)
    if im is not None:
        return im
    title_f = ImageFont.truetype(F_SERIF_B, int(58 * scale))
    body_f = ImageFont.truetype(F_SANS, int(37 * scale))
    kick_f = ImageFont.truetype(F_SANS_B, int(29 * scale))
    pad = int(44 * scale)
    line_h = int(64 * scale)
    h = pad * 2 + int(84 * scale) + line_h * len(lines) + (int(52 * scale) if kicker else 0)
    h = int(h * 1.02)
    _dm = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
    _maxw = 0
    for _t, _f in [(title, title_f)] + [(l, body_f) for l in lines] + ([(kicker, kick_f)] if kicker else []):
        _maxw = max(_maxw, _dm.textlength(_t, font=_f))
    w = int(max(width, _maxw + 2 * pad + 40))
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    # panel
    d.rounded_rectangle((6, 6, w - 6, h - 6), radius=int(22 * scale), fill=(6, 12, 21, 205))
    d.rounded_rectangle((6, 6, w - 6, h - 6), radius=int(22 * scale),
                        outline=accent + (170,), width=2)
    d.rounded_rectangle((12, 12, w - 12, h - 12), radius=int(18 * scale),
                        outline=accent + (40,), width=1)
    # top accent
    d.rounded_rectangle((pad, 10, pad + 90, 16), radius=3, fill=accent + (230,))
    y = pad
    if kicker:
        d.text((pad, y), kicker, font=kick_f, fill=accent + (255,))
        y += int(52 * scale)
    d.text((pad, y), title, font=title_f, fill=WHITE + (255,))
    y += int(84 * scale)
    for ln in lines:
        d.text((pad, y), ln, font=body_f, fill=(208, 222, 236, 255))
        y += line_h
    if glow:
        gl = im.filter(ImageFilter.GaussianBlur(16))
        a = gl.getchannel("A").point(lambda v: int(v * 0.55))
        gl.putalpha(a)
        out = Image.new("RGBA", (w + 32, h + 32), (0, 0, 0, 0))
        out.alpha_composite(gl, (16, 16))
        out.alpha_composite(im, (16, 16))
        im = out
    _CARD_CACHE[key] = im
    return im


def billboard_quad(center, width_w, aspect, cam):
    """Camera-facing quad at 3D center with given world width and height derived by aspect."""
    c = np.asarray(center, dtype=np.float64)
    hw = width_w / 2
    hh = width_w * aspect / 2
    r = cam.right
    u = cam.up
    return [c - r * hw + u * hh, c + r * hw + u * hh, c + r * hw - u * hh, c - r * hw - u * hh]


def screen_quad(cam, fx, fy, width_frac=None, height_frac=None, tex=None, depth=0.75, tilt=0.0):
    """Build a quad that appears at screen fraction (fx,fy) with given size.

    For text textures, sizes refer to the glyph box (ignoring glow padding).
    """
    if tex is not None and hasattr(tex, "_glyph"):
        gw, gh, gx, gy = tex._glyph
        if height_frac is not None:
            scale = (height_frac * H) / max(gh, 1e-6)
        else:
            scale = (width_frac * W) / max(gw, 1e-6)
        full_w = tex.size[0] * scale
        full_h = tex.size[1] * scale
        # anchor at glyph center, then quad is full texture around it
        gcx = gx + gw / 2
        gcy = gy + gh / 2
        cx_px = fx * W + (tex.size[0] / 2 - gcx) * scale
        cy_px = fy * H + (tex.size[1] / 2 - gcy) * scale
        hw_px = full_w / 2
        hh_px = full_h / 2
    else:
        aspect = tex.size[1] / tex.size[0] if tex is not None else 1.0
        if height_frac is not None:
            hh_px = height_frac * H / 2
            hw_px = hh_px / max(aspect, 1e-6)
        else:
            hw_px = width_frac * W / 2
            hh_px = hw_px * aspect
        cx_px = fx * W
        cy_px = fy * H
    d = depth
    world_w = 2 * hw_px * d / cam.f
    world_h = 2 * hh_px * d / cam.f
    center = cam.pos + cam.fwd * d + cam.right * ((cx_px - W / 2) * d / cam.f) - cam.up * ((cy_px - H / 2) * d / cam.f)
    hw = world_w / 2
    hh = world_h / 2
    tl = center - cam.right * hw + cam.up * hh
    tr = center + cam.right * hw + cam.up * hh
    br = center + cam.right * hw - cam.up * hh
    bl = center - cam.right * hw - cam.up * hh
    if abs(tilt) > 1e-6:
        # push one side deeper (rotate around camera up axis)
        dz = math.tan(tilt)
        tl = tl + cam.fwd * (-hw * dz)
        bl = bl + cam.fwd * (-hw * dz)
        tr = tr + cam.fwd * (hw * dz)
        br = br + cam.fwd * (hw * dz)
    return [tl, tr, br, bl]


def quad_tex_from_image(im):
    """Wrap texture image in the form expected by quad (square-ish textures only)."""
    return im


_BD = {}
ACTIVE_BG = "cosmos"
CURRENT_TL = 0.0


def backdrop(name):
    im = _BD.get(name)
    if im is None:
        p = os.path.join(ROOT, "assets", "backdrops", name + ".jpg")
        src = Image.open(p).convert("RGBA")
        # pad for panning
        pad = Image.new("RGBA", (src.size[0] + 64, src.size[1] + 64), (0, 0, 0, 255))
        pad.paste(src, (32, 32))
        im = pad
        _BD[name] = im
    return im


class SceneRenderer:
    def __init__(self):
        self.cam = E.Camera((0, -2.0, 1.1), (0, 0, 0.03), fov_deg=40)

    def new(self, cam):
        self.cam = cam
        bg = backdrop(ACTIVE_BG)
        w, h = bg.size
        dx = int(32 + 24 * math.sin(CURRENT_TL * 0.07 + 0.5))
        dy = int(32 + 16 * math.cos(CURRENT_TL * 0.05))
        img = bg.crop((dx, dy, dx + W, dy + H)).copy()
        self.img = img
        self.items = []
        return img

    def add_quad(self, corners, tex, alpha=1.0, blur=0.0, shade=1.0, depth_bias=0.0, glow=0.0):
        scr, zc = self.cam.project(np.asarray(corners, dtype=np.float64))
        if (zc <= 0.08).any():
            return
        res = E.quad_texture(scr, tex, alpha=alpha, blur=blur, shade=shade)
        if res is None:
            return
        layer, bx, by = res
        depth = float(zc.mean()) + depth_bias
        self.items.append((depth, "img", (layer, bx, by)))

    def add_poly(self, corners, fill=(10, 16, 26), alpha=1.0, blur=0.0, depth_bias=0.0):
        scr, zc = self.cam.project(np.asarray(corners, dtype=np.float64))
        if (zc <= 0.08).any():
            return
        xs, ys = scr[:, 0], scr[:, 1]
        bx, by = int(np.floor(xs.min())) - 4, int(np.floor(ys.min())) - 4
        bw = int(np.ceil(xs.max())) - bx + 8
        bh = int(np.ceil(ys.max())) - by + 8
        if bw < 2 or bh < 2 or bw > W * 2 or bh > H * 2:
            return
        layer = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        pts = [(p[0] - bx, p[1] - by) for p in scr]
        d.polygon(pts, fill=tuple(fill) + (int(255 * alpha),))
        if blur > 0.3:
            layer = layer.filter(ImageFilter.GaussianBlur(blur))
        depth = float(zc.mean()) + depth_bias
        self.items.append((depth, "img", (layer, bx, by)))

    def add_layers(self, layer, bx, by, depth, depth_bias=0.0):
        self.items.append((depth + depth_bias, "img", (layer, bx, by)))

    def add_line3d(self, pts3, color, width=2, alpha=0.8, blur=6.0, additive=True):
        scr, zc = self.cam.project(np.asarray(pts3, dtype=np.float64))
        if (zc <= 0.08).any():
            return
        pad = int(blur * 2 + width * 2 + 4)
        xs, ys = scr[:, 0], scr[:, 1]
        bx, by = int(np.floor(xs.min())) - pad, int(np.floor(ys.min())) - pad
        bw = int(np.ceil(xs.max())) - bx + pad
        bh = int(np.ceil(ys.max())) - by + pad
        if bw < 2 or bh < 2 or bw > W * 2 or bh > H * 2:
            return
        layer = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.line([(p[0] - bx, p[1] - by) for p in scr], fill=tuple(color) + (int(255 * alpha),),
               width=width, joint="curve")
        if blur > 0.3:
            gl = layer.filter(ImageFilter.GaussianBlur(blur))
            a = gl.getchannel("A").point(lambda v: int(v * 0.8))
            gl.putalpha(a)
            self.items.append((float(zc.mean()) + 0.001, "img", (gl, bx, by)))
        self.items.append((float(zc.mean()), "img", (layer, bx, by)))

    def add_sprite(self, pos3, world_size, color=(255, 210, 110), alpha=1.0, depth_bias=0.0):
        scr, zc = self.cam.project(np.asarray([pos3], dtype=np.float64))
        if (zc[0] <= 0.08).any():
            return
        # screen size from world size
        px = self.cam.f * world_size / max(zc[0], 0.2)
        r = max(3, int(px))
        r = min(r, 400)
        sp = E.sprite_glow(r, tuple(int(c) for c in color))
        if alpha < 0.999:
            sp = sp.copy()
            a = sp.getchannel("A").point(lambda v: int(v * alpha))
            sp.putalpha(a)
        self.items.append((float(zc[0]) + depth_bias, "img", (sp, int(scr[0][0] - r), int(scr[0][1] - r))))

    def add_text_plane(self, text_im, center, world_width, alpha=1.0, billboard=True, rot=0.0, blur=0.0):
        aspect = text_im.size[1] / text_im.size[0]
        if billboard:
            quad = billboard_quad(center, world_width, aspect, self.cam)
        else:
            hw = world_width / 2
            hh = world_width * aspect / 2
            c = np.asarray(center, dtype=np.float64)
            quad = np.array([[-hw, hh, 0], [hw, hh, 0], [hw, -hh, 0], [-hw, -hh, 0]]) + c
        self.add_quad(quad, text_im, alpha=alpha, blur=blur)

    def add_screen_tex(self, tex, fx, fy, width_frac=None, height_frac=None, alpha=1.0,
                       depth=0.75, tilt=0.0, blur=0.0, shade=1.0):
        quad = screen_quad(self.cam, fx, fy, width_frac=width_frac, height_frac=height_frac,
                           tex=tex, depth=depth, tilt=tilt)
        self.add_quad(quad, tex, alpha=alpha, blur=blur, shade=shade)

    def flush(self):
        for depth, kind, payload in sorted(self.items, key=lambda x: -x[0]):
            if kind == "img":
                layer, bx, by = payload
                self.img.alpha_composite(layer, (bx, by))
        return self.img


R = SceneRenderer()


# ------------------------------------------------------------------ helpers
def camera_key(tl, keys, fov_keys=None):
    """keys: [(t, pos, target), ...] linear/eased interpolation."""
    if tl <= keys[0][0]:
        pos, tgt = keys[0][1], keys[0][2]
    elif tl >= keys[-1][0]:
        pos, tgt = keys[-1][1], keys[-1][2]
    else:
        for i in range(len(keys) - 1):
            t0, p0, g0 = keys[i]
            t1, p1, g1 = keys[i + 1]
            if t0 <= tl <= t1:
                k = ease_in_out((tl - t0) / max(1e-6, t1 - t0))
                pos = [lerp(a, b, k) for a, b in zip(p0, p1)]
                tgt = [lerp(a, b, k) for a, b in zip(g0, g1)]
                break
    fov = 40.0
    if fov_keys:
        if tl <= fov_keys[0][0]:
            fov = fov_keys[0][1]
        elif tl >= fov_keys[-1][0]:
            fov = fov_keys[-1][1]
        else:
            for i in range(len(fov_keys) - 1):
                t0, f0 = fov_keys[i]
                t1, f1 = fov_keys[i + 1]
                if t0 <= tl <= t1:
                    fov = lerp(f0, f1, ease_in_out((tl - t0) / max(1e-6, t1 - t0)))
                    break
    return E.Camera(pos, tgt, fov_deg=fov)


def draw_board(cam, img_items_fn, tiles=None, plate=True, ring=True, dim=False, ring_rot=0.0,
               highlight=None, hl_color=GOLD, tile_alpha=1.0, plate_alpha=0.95):
    """Draw plate + rings + tiles (with thickness + shadows)."""
    # plate
    if plate:
        quad = np.array([[-0.62, 0.62, 0.0], [0.62, 0.62, 0.0], [0.62, -0.62, 0.0], [-0.62, -0.62, 0.0]])
        R.add_quad(quad, plate_image(), alpha=plate_alpha * (0.65 if dim else 1.0))
    # rings
    if ring:
        for radius, color, width, alpha, z, ph in (
            (0.70, (90, 170, 225), 2, 0.5, -0.012, 0.0),
            (0.78, (60, 130, 190), 1, 0.35, -0.014, 0.6),
            (0.88, (70, 150, 210), 1, 0.2, -0.016, 1.4),
        ):
            pts = []
            for i in range(160):
                a = 2 * math.pi * i / 160 + ring_rot + ph
                pts.append((radius * math.cos(a), radius * math.sin(a), z))
            R.add_line3d(pts, color, width=width, alpha=alpha * (0.6 if dim else 1.0), blur=3)
    if tiles is None:
        tiles = range(9)
    for idx in tiles:
        draw_tile(idx, highlight=highlight, hl_color=hl_color, alpha=tile_alpha, dim=dim)


def draw_tile(idx, center=None, rot=0.0, lift=0.0, alpha=1.0, highlight=None,
              hl_color=GOLD, dim=False, glow_ring=0.0, scale=1.0):
    top_z = 0.035 + lift
    corners = tile_corners(idx, size=TILE * scale, z=top_z, rot=rot, center=center)
    base_alpha = alpha
    # shadow under tile
    if center is None and lift > 0.005:
        sh = corners.copy()
        sh[:, 2] = 0.002
        R.add_poly(sh, fill=(0, 0, 0), alpha=0.35 * min(1.0, lift * 4), blur=10)
    # side faces
    pts = corners
    for i in range(4):
        p0, p1 = pts[i], pts[(i + 1) % 4]
        quad = [p0, p1, [p1[0], p1[1], p1[2] - TH], [p0[0], p0[1], p0[2] - TH]]
        shade_side = 0.55 if i in (1, 2) else 0.8
        R.add_poly(quad, fill=(int(28 * shade_side), int(44 * shade_side), int(66 * shade_side)),
                   alpha=0.95 * base_alpha, blur=0.0)
    # top face
    dimf = 0.55 if dim else 1.0
    R.add_quad(corners, E.tile_tex(idx), alpha=base_alpha, shade=dimf)
    if highlight == idx or glow_ring > 0:
        c = np.array([palace_center(idx)[0], palace_center(idx)[1], top_z + 0.001])
        r = TILE * 0.62
        pts = []
        for i in range(96):
            a = 2 * math.pi * i / 96
            pts.append(c + np.array([r * math.cos(a), r * math.sin(a), 0]))
        R.add_line3d(pts, hl_color, width=max(2, int(3)), alpha=0.9 * (glow_ring or 1.0), blur=4)


def dust_particles(cam, tl, n=90, intensity=1.0, seed=3, spread=1.6, z_range=(0.0, 1.2), size=0.012,
                   color=(130, 180, 230)):
    rng = np.random.default_rng(seed)
    for i in range(n):
        px, py, pz = rng.uniform(-spread, spread), rng.uniform(-spread, spread), rng.uniform(*z_range)
        drift = 0.015 * math.sin(tl * rng.uniform(0.2, 0.6) + i)
        pos = (px + drift, py + drift * 0.6, pz + 0.01 * math.sin(tl * 0.5 + i * 1.7))
        a = intensity * rng.uniform(0.15, 0.55) * (0.6 + 0.4 * math.sin(tl * rng.uniform(0.5, 1.5) + i))
        R.add_sprite(pos, size * rng.uniform(0.6, 1.4), color=color, alpha=max(0.0, a))


def overlay_text(img, xy, text, size, color=WHITE, anchor="ma", font_path=F_SERIF_B,
                 alpha=1.0, stroke=2, glow=16, glow_color=None):
    E.glow_text(img, xy, text, ImageFont.truetype(font_path, size), color, anchor=anchor,
                radius=glow, strength=0.85, alpha=alpha)


# ------------------------------------------------------------------ timeline
_TL = json.load(open(os.path.join(ROOT, "work", "timeline.json"), encoding="utf-8"))
BEATS = _TL["beats"]
TOTAL = _TL["total"]


def beat_at(tg):
    for i, b in enumerate(BEATS):
        if tg < b["start"] + b["dur"] + 0.45:
            return i, max(0.0, tg - b["start"])
    return len(BEATS) - 1, BEATS[-1]["dur"] + 0.4


# ------------------------------------------------------------------ scenes
def scene_hook(tl, tg, dur):
    p = ease_in_out(clamp(tl / 3.2))
    cam = E.Camera((0.0, lerp(-2.9, -2.15, p), lerp(1.75, 1.22, p)), (0, 0.02, 0.04), fov_deg=42 - 3 * p)
    R.new(cam)
    dust_particles(cam, tl, n=110, intensity=1.0, spread=1.7, z_range=(0.0, 1.4))
    # plate grows in
    pa = ease_out(clamp((tl - 0.2) / 1.0))
    draw_board(cam, None, tiles=[], plate=True, ring=True, plate_alpha=0.95 * pa, ring_rot=tl * 0.15)
    # tiles fly in, staggered
    for order_i, idx in enumerate(ORDER):
        t0 = 0.45 + order_i * 0.22
        p2 = clamp((tl - t0) / 1.05)
        if p2 <= 0:
            continue
        e = ease_out(p2)
        rng = np.random.default_rng(idx + 11)
        start = palace_center(idx) + np.array([rng.uniform(-1.6, 1.6), rng.uniform(-1.4, 1.2),
                                               rng.uniform(0.7, 1.6)])
        if p2 < 1.0:
            c = start + (palace_center(idx) + np.array([0, 0, 0.035]) - start) * e
            draw_tile(idx, center=c, rot=(1 - e) * rng.uniform(-1.4, 1.4), lift=0.0,
                      alpha=clamp(p2 * 2.2), glow_ring=0.8 * (1 - e))
        else:
            draw_tile(idx, glow_ring=max(0.0, 1.0 - (tl - t0 - 1.05) * 1.6))
    # landing ripples
    for order_i, idx in enumerate(ORDER):
        t0 = 0.45 + order_i * 0.22 + 1.05
        dt = tl - t0
        if 0 <= dt < 0.8:
            c = palace_center(idx) + np.array([0, 0, 0.04])
            rr = 0.05 + 0.55 * ease_out(dt / 0.8)
            pts = [c + np.array([rr * math.cos(2 * math.pi * i / 64), rr * math.sin(2 * math.pi * i / 64), 0])
                   for i in range(64)]
            R.add_line3d(pts, (120, 200, 250), width=2, alpha=(1 - dt / 0.8) * 0.9, blur=3)
    # title text planes
    a1 = ease_out((tl - 1.5) / 1.0)
    if a1 > 0:
        t1 = E.text_tex("一张盘", 120, GOLD, glow=22, glow_color=GOLD, glow_strength=1.0)
        R.add_screen_tex(t1, 0.5, 0.235, width_frac=0.50, alpha=a1, depth=0.8)
    a2 = ease_out((tl - 2.1) / 1.1)
    if a2 > 0:
        t2 = E.text_tex("看懂一场峰会", 132, WHITE, glow=26, glow_color=(160, 220, 255), glow_strength=0.8)
        R.add_screen_tex(t2, 0.5, 0.335, width_frac=0.74, alpha=a2, depth=0.8)
    a3 = ease_out((tl - 2.9) / 1.0)
    if a3 > 0:
        t3 = E.text_tex("奇门遁甲起盘 · 全流程实拆", 46, TEAL, font_path=F_SANS, glow=14,
                        glow_color=TEAL, glow_strength=0.6)
        R.add_screen_tex(t3, 0.5, 0.425, width_frac=0.78, alpha=a3, depth=0.8)
        t4 = E.text_tex("2026.11.17-18 · 深圳 APEC", 32, MUTED, font_path=F_SANS, glow=10,
                        glow_color=TEAL, glow_strength=0.4)
        R.add_screen_tex(t4, 0.5, 0.475, width_frac=0.66, alpha=a3, depth=0.8)


def scene_triple_cards(tl, tg, dur):
    """generic: three holographic cards floating in depth."""
    pass


def scene_b02(tl, tg, dur):
    p = ease_in_out(clamp(tl / dur))
    cam = E.Camera((lerp(0.15, -0.25, p), lerp(-2.5, -2.05, p), lerp(1.35, 1.12, p)),
                   (0, 0, 0.05), fov_deg=lerp(42, 39, p))
    R.new(cam)
    dust_particles(cam, tl, n=70, spread=1.5)
    draw_board(cam, None, dim=True, ring_rot=tl * 0.2, plate_alpha=0.6)
    card = card_tex("定局", ["第一步不是排盘，是定局", "看两件事：阴阳遁 · 局数"], GOLD, kicker="01 / 定局")
    a = ease_out((tl - 0.3) / 1.0)
    R.add_screen_tex(card, 0.5, 0.265, width_frac=0.88, alpha=a, depth=2.0, tilt=-0.02)


def scene_b03(tl, tg, dur):
    p = ease_in_out(clamp(tl / dur))
    cam = E.Camera((lerp(0.3, -0.3, p), -2.35, lerp(1.35, 1.15, p)), (0, 0, 0.05), fov_deg=40)
    R.new(cam)
    dust_particles(cam, tl, n=60)
    draw_board(cam, None, dim=True, ring_rot=tl * 0.2)
    c1 = card_tex("阳遁", ["冬至后 · 顺飞"], TEAL, kicker="阳")
    c2 = card_tex("阴遁", ["夏至后 · 逆飞"], RED, kicker="阴")
    a1 = ease_out((tl - 0.2) / 0.7)
    a2 = ease_out((tl - 0.7) / 0.8)
    if a1 > 0:
        R.add_screen_tex(c1, 0.5, 0.30, width_frac=0.76, alpha=a1, tilt=0.03)
    if a2 > 0:
        R.add_screen_tex(c2, 0.5, 0.44, width_frac=0.76, alpha=a2, tilt=-0.03)
    hl = ease_out((tl - 1.3) / 0.8)
    if hl > 0:
        t = E.text_tex("此刻，是阴遁", 96, RED, glow=24, glow_color=RED, glow_strength=1.0)
        R.add_screen_tex(t, 0.5, 0.58, height_frac=0.075, alpha=hl)


def scene_b04(tl, tg, dur):
    p = ease_in_out(clamp(tl / dur))
    cam = E.Camera((lerp(-0.6, 0.6, p), -2.3, lerp(1.25, 1.12, p)), (0, 0, 0.05), fov_deg=41)
    R.new(cam)
    dust_particles(cam, tl, n=70)
    draw_board(cam, None, dim=True, ring_rot=tl * 0.18)
    # 3 season cards in an arc
    rows = [("上元", "阴遁五局", "五", GOLD), ("中元", "阴遁八局", "八", MUTED), ("下元", "阴遁二局", "二", MUTED)]
    for i, (a, b, n, col) in enumerate(rows):
        ap = ease_out((tl - 0.3 - i * 0.3) / 0.8)
        if ap <= 0:
            continue
        card = card_tex(a, [b], col, kicker=f"霜降 · {a}")
        R.add_screen_tex(card, 0.5, 0.22 + i * 0.14, width_frac=0.54, alpha=ap,
                         tilt=(0.03 if i % 2 == 0 else -0.03))
    fin = ease_out((tl - 2.2) / 0.9)
    if fin > 0:
        t = E.text_tex("今天在上元 → 阴遁五局", 64, WHITE, glow=18, glow_color=GOLD, glow_strength=0.8)
        R.add_screen_tex(t, 0.5, 0.62, width_frac=0.76, alpha=fin)


def scene_b05(tl, tg, dur):
    p = ease_in_out(clamp(tl / dur))
    cam = E.Camera((lerp(0.1, -0.1, p), lerp(-2.5, -2.15, p), lerp(1.3, 1.12, p)), (0, 0, 0.05), fov_deg=40)
    R.new(cam)
    dust_particles(cam, tl, n=70)
    draw_board(cam, None, dim=True, ring_rot=tl * 0.18, plate_alpha=0.5)
    rules = [("子午卯酉", "上元"), ("寅申巳亥", "中元"), ("辰戌丑未", "下元")]
    for i, (a, b) in enumerate(rules):
        ap = ease_out((tl - 0.2 - i * 0.35) / 0.8)
        if ap <= 0:
            continue
        card = card_tex(a, [b], TEAL if i == 0 else MUTED, kicker="符头")
        R.add_screen_tex(card, 0.5, 0.17 + i * 0.135, width_frac=0.54, alpha=ap,
                         tilt=(0.03 if i % 2 == 0 else -0.03))
    line = ease_out((tl - 1.3) / 0.8)
    if line > 0:
        t = E.text_tex("11/1 己卯日 · 卯属上元", 56, TEAL, glow=16, glow_color=TEAL, glow_strength=0.8)
        R.add_screen_tex(t, 0.5, 0.585, width_frac=0.80, alpha=line)
    stamp = ease_out((tl - 2.0) / 0.7)
    if stamp > 0:
        s = lerp(1.5, 1.0, ease_out(clamp((tl - 2.0) / 1.0)))
        t = E.text_tex("定案：阴遁五局", 92, GOLD_B, glow=26, glow_color=GOLD, glow_strength=1.2)
        R.add_screen_tex(t, 0.5, 0.705, width_frac=0.84 * s, alpha=stamp)


def scene_b06(tl, tg, dur):
    p = ease_in_out(clamp(tl / dur))
    cam = E.Camera((lerp(0.0, 0.0, p), lerp(-2.5, -2.05, p), lerp(1.55, 1.22, p)), (0, -0.02, 0.05),
                   fov_deg=lerp(42, 38, p))
    R.new(cam)
    dust_particles(cam, tl, n=90)
    draw_board(cam, None, tiles=[], plate=True, ring=True, ring_rot=tl * 0.2)
    for i, idx in enumerate(ORDER):
        t0 = 0.35 + i * (dur * 0.55) / 9.0
        p2 = clamp((tl - t0) / 0.55)
        if p2 <= 0:
            continue
        e = ease_out(p2)
        rng = np.random.default_rng(idx + 31)
        start = palace_center(idx) + np.array([rng.uniform(-1.2, 1.2), rng.uniform(-0.9, 1.0), 0.9])
        if p2 < 1.0:
            c = start + (palace_center(idx) + np.array([0, 0, 0.035]) - start) * e
            draw_tile(idx, center=c, rot=(1 - e) * 0.9, alpha=clamp(p2 * 2.0), glow_ring=0.9 * (1 - e))
        else:
            draw_tile(idx, glow_ring=max(0.0, 1.0 - (tl - t0 - 0.55) * 1.5))
        # ripple
        dt = tl - (t0 + 0.55)
        if 0 <= dt < 0.6:
            c = palace_center(idx) + np.array([0, 0, 0.04])
            rr = 0.04 + 0.5 * ease_out(dt / 0.6)
            pts = [c + np.array([rr * math.cos(2 * math.pi * k / 64), rr * math.sin(2 * math.pi * k / 64), 0])
                   for k in range(64)]
            R.add_line3d(pts, (120, 200, 250), width=2, alpha=(1 - dt / 0.6) * 0.85, blur=3)
    # sequence digits as 3D text
    seq = "5 4 3 2 1 9 8 7 6".split()
    shown = 0
    for i in range(9):
        if tl >= 0.35 + i * (dur * 0.55) / 9.0 + 0.55:
            shown = i + 1
    if shown > 0:
        t = E.text_tex(" ".join(seq[:shown]), 52, GOLD, font_path=F_SANS_B, glow=14,
                       glow_color=GOLD, glow_strength=0.7)
        R.add_screen_tex(t, 0.5, 0.80, width_frac=0.16, alpha=0.95)


def scene_b07(tl, tg, dur):
    p = ease_in_out(clamp(tl / dur))
    ang = 0.10 * math.sin(tl * 0.25)
    cam = E.Camera((0.9 * math.sin(ang), -2.1, lerp(1.25, 1.15, p)), (0, 0, 0.05), fov_deg=40)
    R.new(cam)
    dust_particles(cam, tl, n=80)
    draw_board(cam, None, ring_rot=tl * 0.15)
    mapping = [("戊", "中五", 4), ("己", "巽四", 0), ("庚", "震三", 3), ("辛", "坤二", 2),
               ("壬", "坎一", 7), ("癸", "离九", 1), ("丁", "艮八", 6), ("丙", "兑七", 5), ("乙", "乾六", 8)]
    for i, (gan, pal, idx) in enumerate(mapping):
        ap = clamp((tl - 0.3 - i * 0.35) / 0.5)
        if ap <= 0:
            continue
        c = palace_center(idx) + np.array([0, 0, 0.16])
        t = E.text_tex(f"{gan} · {pal}", 44, GOLD if ap > 0.6 else MUTED, font_path=F_SANS_B, glow=12,
                       glow_color=GOLD, glow_strength=0.5)
        R.add_text_plane(t, c, 0.13, alpha=ap)


def scene_b08(tl, tg, dur):
    p = ease_in_out(clamp(tl / dur))
    cam = E.Camera((lerp(-0.15, 0.15, p), -2.3, lerp(1.2, 1.1, p)), (0, 0, 0.06), fov_deg=40)
    R.new(cam)
    dust_particles(cam, tl, n=80, color=(120, 170, 230))
    # rotating rings only (no board)
    for radius, color, w, a, z, ph in ((0.85, TEAL, 2, 0.55, 0.0, 0.0), (0.85, RED, 2, 0.55, 0.0, math.pi)):
        pts = []
        for i in range(160):
            ang = 2 * math.pi * i / 160 + tl * 0.6 + ph
            pts.append((radius * math.cos(ang), radius * math.sin(ang), z))
        R.add_line3d(pts, color, width=w, alpha=a, blur=6)
    a1 = ease_out((tl - 0.2) / 0.8)
    a2 = ease_out((tl - 0.9) / 0.8)
    if a1 > 0:
        t = E.text_tex("阳遁顺飞", 108, TEAL, glow=22, glow_color=TEAL, glow_strength=1.0)
        R.add_screen_tex(t, 0.5, 0.36, height_frac=0.090, alpha=a1)
    if a2 > 0:
        t = E.text_tex("阴遁逆飞", 108, RED, glow=22, glow_color=RED, glow_strength=1.0)
        R.add_screen_tex(t, 0.5, 0.50, height_frac=0.090, alpha=a2)
    a3 = ease_out((tl - 1.7) / 0.8)
    if a3 > 0:
        t = E.text_tex("逆，是宫序倒着数", 56, WHITE, glow=14, glow_color=(180, 210, 240), glow_strength=0.6)
        R.add_screen_tex(t, 0.5, 0.62, width_frac=0.86, alpha=a3)


def scene_b09(tl, tg, dur):
    p = ease_in_out(clamp(tl / dur))
    cam = E.Camera((lerp(-0.2, 0.2, p), lerp(-2.45, -2.0, p), lerp(1.3, 1.1, p)), (0, 0, 0.05),
                   fov_deg=lerp(41, 38, p))
    R.new(cam)
    dust_particles(cam, tl, n=80)
    draw_board(cam, None, dim=True, ring_rot=tl * 0.2, plate_alpha=0.45)
    rows = [("甲子", "戊"), ("甲戌", "己"), ("甲申", "庚"), ("甲午", "辛"), ("甲辰", "壬"), ("甲寅", "癸")]
    for i, (a, b) in enumerate(rows):
        ap = ease_out((tl - 0.2 - i * 0.22) / 0.5)
        if ap <= 0:
            continue
        hi = i == 4
        card = card_tex(f"{a} · {b}", ["时日柱辛亥属此旬"] if hi else [], GOLD if hi else MUTED,
                        kicker="六甲旬" if hi else "")
        fy = 0.20 + i * 0.105
        R.add_screen_tex(card, 0.5, fy, width_frac=0.62, alpha=ap)


def scene_b10(tl, tg, dur):
    p = ease_in_out(clamp(tl / dur))
    c = palace_center(7)
    cam = E.Camera((c[0], lerp(-2.5, -1.55, p), lerp(1.45, 1.05, p)), (c[0], c[1] + 0.02, 0.08),
                   fov_deg=lerp(41, 38, p))
    R.new(cam)
    dust_particles(cam, tl, n=90)
    draw_board(cam, None, ring_rot=tl * 0.15, dim=True)
    lift = ease_in_out(clamp((tl - 0.6) / 1.2)) * 0.10
    draw_tile(7, lift=lift, glow_ring=1.0)
    c7 = palace_center(7) + np.array([0, 0, 0.05 + lift])
    R.add_sprite(c7 + np.array([0, 0, 0.16]), 0.10, color=TEAL, alpha=0.9)
    a = ease_out((tl - 1.1) / 0.8)
    if a > 0:
        t = E.text_tex("坎一宫 · 天蓬 · 休门", 62, TEAL, glow=18, glow_color=TEAL, glow_strength=0.9)
        R.add_screen_tex(t, 0.5, 0.74, width_frac=0.86, alpha=a)
    a2 = ease_out((tl - 1.8) / 0.8)
    if a2 > 0:
        t = E.text_tex("值符天蓬 · 值使休门", 78, GOLD_B, glow=22, glow_color=GOLD, glow_strength=1.1)
        R.add_screen_tex(t, 0.5, 0.83, width_frac=0.9, alpha=a2)


def _arc(a, b, t, height=0.35):
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    return a + (b - a) * t + np.array([0, 0, height * math.sin(math.pi * t)])


def scene_b11(tl, tg, dur):
    p = ease_in_out(clamp((tl - 0.2) / max(1.0, dur * 0.7)))
    cam = E.Camera((lerp(-0.3, 0.15, p), -2.25, 1.2), (lerp(-0.1, 0.15, p), 0.0, 0.05), fov_deg=39)
    R.new(cam)
    dust_particles(cam, tl, n=80)
    draw_board(cam, None, ring_rot=tl * 0.15)
    a = palace_center(7) + np.array([0, 0, 0.08])
    b = palace_center(2) + np.array([0, 0, 0.08])
    t = ease_in_out(clamp((tl - 0.5) / 1.6))
    pos = _arc(a, b, t, height=0.4)
    # trail
    trail = [pos + np.array([0, 0, -0.002]) - (b - a) * 0.001]
    for k in range(1, 10):
        tk = max(0.0, t - k * 0.02)
        pp = _arc(a, b, tk, height=0.4)
        R.add_sprite(pp, 0.05 * (1 - k / 12.0), color=GOLD, alpha=(1 - k / 10.0) * 0.5)
    R.add_sprite(pos, 0.16, color=GOLD_B, alpha=1.0)
    R.add_sprite(pos, 0.38, color=GOLD, alpha=0.35)
    if tl > 0.4:
        t2 = E.text_tex("时干辛在坤二 · 天蓬移宫", 58, GOLD, glow=16, glow_color=GOLD, glow_strength=0.8)
        R.add_screen_tex(t2, 0.5, 0.80, width_frac=0.86, alpha=ease_out((tl - 0.5) / 0.8))


def scene_b12(tl, tg, dur):
    p = ease_in_out(clamp(tl / dur))
    cam = E.Camera((lerp(-0.55, 0.4, p), -2.2, 1.15), (lerp(-0.3, -0.2, p), -0.1, 0.05), fov_deg=39)
    R.new(cam)
    dust_particles(cam, tl, n=80)
    draw_board(cam, None, ring_rot=tl * 0.15, dim=True)
    a = palace_center(7) + np.array([0, 0, 0.07])
    b = palace_center(6) + np.array([0, 0, 0.07])
    lift = ease_in_out(clamp((tl - 1.4) / 1.0)) * 0.08
    draw_tile(6, lift=lift, glow_ring=clamp((tl - 1.4) * 1.2))
    draw_tile(7, lift=0.04, glow_ring=0.8)
    n = 7
    prog = clamp((tl - 0.4) / 2.4)
    for i in range(n):
        f = (i + 1) / n
        if f > prog + 1e-6:
            break
        pp = _arc(a, b, f, height=0.28)
        R.add_sprite(pp, 0.05, color=TEAL, alpha=0.9)
    R.add_sprite(_arc(a, b, prog, height=0.28), 0.14, color=TEAL, alpha=1.0)
    if tl > 0.3:
        t = E.text_tex("休门：从坎一逆数七宫", 54, MUTED, glow=14, glow_color=TEAL, glow_strength=0.7)
        R.add_screen_tex(t, 0.5, 0.76, width_frac=0.86, alpha=ease_out((tl - 0.3) / 0.8))
    a2 = ease_out((tl - 1.8) / 0.8)
    if a2 > 0:
        t = E.text_tex("落到艮八", 86, GOLD_B, glow=22, glow_color=GOLD, glow_strength=1.1)
        R.add_screen_tex(t, 0.5, 0.855, width_frac=0.86, alpha=a2)


def scene_b13(tl, tg, dur):
    p = ease_in_out(clamp(tl / max(0.6, dur)))
    cam = E.Camera((math.sin(p * 0.9) * 0.5, -2.1, 1.2), (0, 0, 0.05), fov_deg=39)
    R.new(cam)
    dust_particles(cam, tl, n=100)
    draw_board(cam, None, ring_rot=tl * 0.25)
    a = ease_out((tl - 0.2) / 0.7)
    if a > 0:
        t = E.text_tex("盘，布完了", 128, WHITE, glow=26, glow_color=(150, 210, 250), glow_strength=0.9)
        R.add_screen_tex(t, 0.5, 0.33, width_frac=0.86, alpha=a)
        t2 = E.text_tex("九宫 · 九星 · 八门 · 八神", 42, GOLD, font_path=F_SANS, glow=12,
                        glow_color=GOLD, glow_strength=0.6)
        R.add_screen_tex(t2, 0.5, 0.44, width_frac=0.8, alpha=a)


def palace_dive(idx, title_lines, color, sub="", kong=False):
    def scene(tl, tg, dur):
        c = palace_center(idx)
        p = ease_in_out(clamp((tl - 0.3) / 2.4))
        # camera: wide -> close orbit
        cam = E.Camera((c[0] + lerp(0.0, 0.16, p), lerp(-2.6, -1.95, p), lerp(1.5, 1.28, p)),
                       (c[0] * 0.8, c[1] * 0.8, lerp(0.05, 0.08, p)), fov_deg=lerp(40, 38, p))
        R.new(cam)
        dust_particles(cam, tl, n=100, seed=idx + 2, spread=1.2)
        # dim board
        draw_board(cam, None, ring_rot=tl * 0.2, dim=True, plate_alpha=0.5)
        lift = ease_in_out(clamp((tl - 0.6) / 1.6)) * 0.12 + 0.01 * math.sin(tl * 0.8)
        draw_tile(idx, lift=lift, glow_ring=1.0)
        # pulse rings around palace
        for k in range(3):
            ph = (tl * 0.7 + k / 3.0) % 1.0
            rr = TILE * (0.55 + 0.9 * ph)
            c3 = np.array([c[0], c[1], 0.05 + lift])
            pts = [c3 + np.array([rr * math.cos(2 * math.pi * i / 64), rr * math.sin(2 * math.pi * i / 64), 0])
                   for i in range(64)]
            R.add_line3d(pts, color, width=2, alpha=(1 - ph) * 0.6, blur=3)
        # particles around palace
        rng = np.random.default_rng(idx * 7 + 1)
        for i in range(26):
            ang2 = rng.uniform(0, 2 * math.pi)
            rad2 = rng.uniform(0.1, 0.26)
            zz = 0.05 + lift + rng.uniform(0.0, 0.22) + 0.01 * math.sin(tl * 2 + i)
            pos = (c[0] + rad2 * math.cos(ang2 + tl * 0.4), c[1] + rad2 * math.sin(ang2 + tl * 0.4), zz)
            R.add_sprite(pos, rng.uniform(0.006, 0.014), color=color, alpha=rng.uniform(0.3, 0.8))
        if kong:
            scr, zc = cam.project(np.array([[c[0], c[1], 0.10 + lift]]))
            fx = float(scr[0][0]) / W
            fy = float(scr[0][1]) / H
            t = E.text_tex("空", 150, RED, glow=26, glow_color=RED, glow_strength=1.2)
            R.add_screen_tex(t, fx + 0.17, fy - 0.10, height_frac=0.070, alpha=ease_out((tl - 1.0) / 0.8))
        # analysis card
        a = ease_out((tl - 1.2) / 1.0)
        if a > 0:
            card = card_tex(title_lines[0], title_lines[1:], color, kicker=sub)
            R.add_screen_tex(card, 0.5, 0.815, width_frac=0.76, alpha=a, tilt=-0.015)
    return scene


def scene_b19(tl, tg, dur):
    p = ease_in_out(clamp(tl / dur))
    cam = E.Camera((lerp(-0.25, 0.3, p), lerp(-2.45, -2.2, p), lerp(1.4, 1.25, p)), (0, 0, 0.07),
                   fov_deg=40)
    R.new(cam)
    dust_particles(cam, tl, n=70)
    draw_board(cam, None, dim=True, ring_rot=tl * 0.25, plate_alpha=0.38)
    W_, H_ = W, H
    d = ImageDraw.Draw(R.img)
    y = int(H_ * 0.30)
    x0, x1 = int(W_ * 0.12), int(W_ * 0.88)
    nodes = [("11/4", "今日 · 旬空", 0.18, MUTED), ("11/6", "甲申日 · 出空填实", 0.50, GOLD),
             ("11/17-18", "APEC · 深圳", 0.82, TEAL)]
    ap = ease_out((tl - 0.3) / 1.0)
    if ap > 0:
        d.line([(x0, y), (x1, y)], fill=(120, 150, 180, int(80 * ap)), width=2)
        # reveal progress along timeline
        prog = clamp((tl - 0.6) / 2.4)
        xe = int(lerp(x0, x1, prog))
        if xe > x0:
            d.line([(x0, y), (xe, y)], fill=GOLD + (int(200 * ap),), width=5)
    for i, (date, note, f, col) in enumerate(nodes):
        a = ease_out((tl - 0.5 - i * 0.35) / 0.7)
        if a <= 0:
            continue
        px = int(lerp(x0, x1, f))
        pulse = 1.0 + (0.5 * math.sin(tl * 4.0) if i == 1 and tl > 1.6 else 0.0)
        r = int(11 * pulse)
        d.ellipse((px - r, y - r, px + r, y + r), fill=col + (int(255 * a),))
        d.ellipse((px - int(r * 2.2), y - int(r * 2.2), px + int(r * 2.2), y + int(r * 2.2)),
                  outline=col + (int(90 * a),), width=2)
        t = E.text_tex(date, 56, col, glow=12, glow_color=col, glow_strength=0.7)
        R.add_screen_tex(t, px / W_, 0.368, width_frac=0.17, alpha=a, depth=0.5)
        t2 = E.text_tex(note, 26, MUTED, font_path=F_SANS, glow=6, glow_color=col, glow_strength=0.4)
        R.add_screen_tex(t2, px / W_, 0.462, width_frac=0.20, alpha=a, depth=0.5)
    fin = ease_out((tl - 2.2) / 0.9)
    if fin > 0:
        t = E.text_tex("11/6 之前，事多虚声", 52, MUTED, glow=12, glow_color=GOLD, glow_strength=0.6)
        R.add_screen_tex(t, 0.5, 0.74, width_frac=0.80, alpha=fin, depth=0.5)
        t2 = E.text_tex("之后，实底才上桌", 72, GOLD_B, glow=20, glow_color=GOLD, glow_strength=1.0)
        R.add_screen_tex(t2, 0.5, 0.82, width_frac=0.86, alpha=ease_out((tl - 2.6) / 0.9), depth=0.5)


def scene_b20(tl, tg, dur):
    p = ease_in_out(clamp(tl / dur))
    cam = E.Camera((lerp(0.25, -0.25, p), lerp(-2.5, -2.2, p), lerp(1.4, 1.2, p)), (0, 0, 0.06),
                   fov_deg=41)
    R.new(cam)
    dust_particles(cam, tl, n=70)
    draw_board(cam, None, dim=True, ring_rot=tl * 0.2, plate_alpha=0.35)
    items = [("①", "会期前一周", "实质量增，细则与议程集中落地"),
             ("②", "会期内经贸", "签约额亮眼，落地慢于宣传"),
             ("③", "安保与通行", "会场外围管控明显收紧"),
             ("④", "西向参与方", "过程有反复，最终仍成局")]
    for i, (n, a, b) in enumerate(items):
        ap = ease_out((tl - 0.3 - i * 0.6) / 0.8)
        if ap <= 0:
            continue
        card = card_tex(a, [b], GOLD, kicker=f"可检验 · {n}")
        fx = 0.5
        fy = 0.16 + i * 0.135
        R.add_screen_tex(card, fx, fy, width_frac=0.58, alpha=ap,
                         tilt=(0.025 if i % 2 == 0 else -0.025))
    fin = ease_out((tl - 3.0) / 0.9)
    if fin > 0:
        t = E.text_tex("任一条不验，断法就该被推翻", 48, RED, glow=16, glow_color=RED, glow_strength=0.9)
        R.add_screen_tex(t, 0.5, 0.82, width_frac=0.80, alpha=fin)


def scene_b21(tl, tg, dur):
    p = ease_in_out(clamp(tl / dur))
    cam = E.Camera((lerp(-0.2, 0.2, p), lerp(-2.5, -2.2, p), lerp(1.35, 1.2, p)), (0, 0, 0.07),
                   fov_deg=40)
    R.new(cam)
    dust_particles(cam, tl, n=60)
    draw_board(cam, None, dim=True, ring_rot=tl * 0.15, plate_alpha=0.30)
    c1 = card_tex("定局有流派分歧", ["拆补法 → 阴遁五局", "置闰法 → 可能阴八 / 阴二"], GOLD, kicker="学理 01")
    c2 = card_tex("会期来源不一致", ["CEO 峰会 17-18（三源一致）", "领导人会议另有 18-19 之说"], TEAL, kicker="学理 02")
    a1 = ease_out((tl - 0.3) / 0.9)
    a2 = ease_out((tl - 1.0) / 0.9)
    if a1 > 0:
        R.add_screen_tex(c1, 0.5, 0.28, width_frac=0.84, alpha=a1, tilt=0.02)
    if a2 > 0:
        R.add_screen_tex(c2, 0.5, 0.50, width_frac=0.84, alpha=a2, tilt=-0.02)


def scene_b22(tl, tg, dur):
    p = ease_in_out(clamp(tl / dur))
    cam = E.Camera((0, lerp(-2.4, -2.2, p), lerp(1.2, 1.12, p)), (0, 0, 0.05), fov_deg=39)
    R.new(cam)
    dust_particles(cam, tl, n=50, intensity=0.7)
    c = card_tex("边界与免责", ["以上依奇门规则（拆补法定局）推演。", "APEC 为重大公共事件，",
                              "此为术数练习与教学演示，", "不构成任何现实决策依据。"], MUTED, kicker="05 / 边界")
    R.add_screen_tex(c, 0.5, 0.44, width_frac=0.88, alpha=ease_out((tl - 0.2) / 1.0))


def scene_b23(tl, tg, dur):
    p = ease_in_out(clamp(tl / max(0.8, dur)))
    cam = E.Camera((math.sin(p * 1.1) * 0.45, lerp(-2.15, -2.0, p), lerp(1.25, 1.15, p)), (0, 0.02, 0.05),
                   fov_deg=39)
    R.new(cam)
    dust_particles(cam, tl, n=80)
    draw_board(cam, None, ring_rot=tl * 0.3)
    # dark scrim for lower text
    d = ImageDraw.Draw(R.img)
    d.rectangle([0, int(H * 0.60), W, H], fill=(2, 5, 10, 120))
    a = ease_out((tl - 0.2) / 0.8)
    if a > 0:
        t = E.text_tex("想看置闰法双盘互参", 66, WHITE, glow=18, glow_color=(150, 210, 250), glow_strength=0.8)
        R.add_screen_tex(t, 0.5, 0.245, width_frac=0.80, alpha=a, depth=0.5)
        t2 = E.text_tex("还是 60 秒短版？", 66, GOLD_B, glow=18, glow_color=GOLD, glow_strength=0.9)
        R.add_screen_tex(t2, 0.5, 0.345, width_frac=0.80, alpha=ease_out((tl - 0.6) / 0.8), depth=0.5)
        t3 = E.text_tex("评论区说一声", 46, TEAL, font_path=F_SANS, glow=12, glow_color=TEAL, glow_strength=0.6)
        R.add_screen_tex(t3, 0.5, 0.445, width_frac=0.56, alpha=ease_out((tl - 1.1) / 0.8), depth=0.5)
        t4 = E.text_tex("发言稿 · 稽疑　视频 · VCP 视听", 32, MUTED, font_path=F_SANS, glow=8,
                        glow_color=TEAL, glow_strength=0.4)
        R.add_screen_tex(t4, 0.5, 0.555, width_frac=0.66, alpha=ease_out((tl - 1.8) / 0.9), depth=0.5)
        t5 = E.text_tex("术数练习 · 教学演示 · 不构成决策依据", 24, DIM, font_path=F_SANS, glow=6,
                        glow_color=TEAL, glow_strength=0.3)
        R.add_screen_tex(t5, 0.5, 0.615, width_frac=0.72, alpha=ease_out((tl - 2.2) / 0.9), depth=0.5)


SCENES = {
    "b01": scene_hook, "b02": scene_b02, "b03": scene_b03, "b04": scene_b04, "b05": scene_b05,
    "b06": scene_b06, "b07": scene_b07, "b08": scene_b08, "b09": scene_b09, "b10": scene_b10,
    "b11": scene_b11, "b12": scene_b12, "b13": scene_b13,
    "b14": palace_dive(2, ["核心：规格极高，落点尚虚", "时干辛落坤二：天蓬（值符）+ 景门 + 值符神",
                           "值符在：规格够、有主导力、有场子", "景门主文书：正合峰会之象",
                           "但坤二逢空 —— 声势大，实未落定"], RED, sub="坤二宫 · 空", kong=True),
    "b15": palace_dive(7, ["主办方：扎实", "日干壬落坎一：天辅 + 开门 + 六合", "开门主公事，六合主协作",
                           "坎水生天辅木，星得生而旺", "全盘最好的一宫"], TEAL, sub="坎一宫 · 日干"),
    "b16": palace_dive(3, ["经贸：有暗流", "庚 + 天芮 + 玄武，覆压生门", "生门主财利；庚为阻、芮为病",
                           "签约数字与实际落地有落差", "多宣示，少即刻兑现"], GOLD, sub="震三宫"),
    "b17": palace_dive(6, ["安保与会场：严", "丁奇 + 休门（值使）+ 天英 + 白虎", "白虎主威、主兵卫；艮为守",
                           "外围管控收紧，会场内静", "值使落此：执行层偏保守"], TEAL, sub="艮八宫 · 值使"),
    "b18": palace_dive(5, ["变数：西向", "丙 + 天任 + 死门 + 螣蛇，且逢空", "兑为西、为口、为言",
                           "死门主封闭；螣蛇主反复", "谈定即定，结论不易推翻"], PURPLE, sub="兑七宫 · 空",
                        kong=True),
    "b19": scene_b19, "b20": scene_b20, "b21": scene_b21, "b22": scene_b22, "b23": scene_b23,
}


BGS = {"b01": "city", "b02": "cosmos", "b03": "cosmos", "b04": "light", "b05": "light",
       "b06": "cosmos", "b07": "cosmos", "b08": "cosmos", "b09": "light", "b10": "cosmos",
       "b11": "cosmos", "b12": "cosmos", "b13": "city", "b14": "cosmos", "b15": "cosmos",
       "b16": "cosmos", "b17": "cosmos", "b18": "cosmos", "b19": "dawn", "b20": "light",
       "b21": "light", "b22": "cosmos", "b23": "city"}


def render_frame(fi):
    global ACTIVE_BG, CURRENT_TL
    tg = fi / FPS
    bi, tl = beat_at(tg)
    bid = BEATS[bi]["id"]
    ACTIVE_BG = BGS.get(bid, "cosmos")
    CURRENT_TL = tg
    fn = SCENES.get(bid)
    if fn is None:
        R.new(E.Camera((0, -2, 1.2), (0, 0, 0.05), fov_deg=40))
        draw_board(R.cam, None)
    else:
        fn(tl, tg, BEATS[bi]["dur"])
    img = R.flush()
    # fade from black at beat start
    if tl < 0.25:
        a = tl / 0.25
        ov = Image.new("RGBA", (W, H), (0, 0, 0, int(255 * (1 - a))))
        img.alpha_composite(ov)
    if tg > TOTAL - 1.4:
        a = clamp((tg - (TOTAL - 1.4)) / 1.4)
        img.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(255 * a))))
    out = E.Renderer().finish(img, bloom=0.7, grade=1.0, grain_amt=3.4, seed=fi, leak=0.10)
    return out


def main():
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    end = int(sys.argv[2]) if len(sys.argv) > 2 else int(TOTAL * FPS)
    for fi in range(start, end):
        p = os.path.join(OUT, f"f{fi:05d}.jpg")
        if os.path.exists(p) and os.path.getsize(p) > 1000:
            continue
        img = render_frame(fi)
        img.save(p, "JPEG", quality=90)
        if fi % 240 == 0:
            print("frame", fi, "/", end, flush=True)
    print("done", start, end, flush=True)


if __name__ == "__main__":
    main()
