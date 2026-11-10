#!/usr/bin/env python3
"""第 03 期《AI 时代最贵的债，是判断力》渲染器。

设计原则（对应《视频制作优化意见》）：
- 运动承担叙事：纸张从屏幕里滑出、答案覆盖初判、账页落笔、欠条盖章、答案翻面成反例，
  每个显著运动都回答「为什么现在动」。
- 视觉层级：一屏一个第一视觉重点；字幕是辅助；不加进度条、章节卡常驻、闪白、逐镜 whoosh。
- 真实质感：程序化 3D 桌面/纸张/印章负责概念镜头，Pexels B-roll 负责氛围镜头；
  统一冷靛蓝 × 暖纸黄 × 朱红影调 + 胶片颗粒 + 景深/暗角。

用法：
  python3 scene_judgment.py --still s1c 12.0 --out /tmp/a.png       # 单帧预览
  python3 scene_judgment.py --range 0 400 --outdir work/frames      # 渲染帧区间
  python3 scene_judgment.py --bench s1a                             # 单帧耗时

并发：--range 进程共享渲染槽位，默认最多 2 个同时渲染（EP03_RENDER_JOBS 可覆盖，1 为串行）。
"""
import argparse
import fcntl
import json
import re
import math
import os
import random
import sys
import time

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import engine3d as E

W, H, FPS = 900, 1600, 24
TL = json.load(open(os.path.join(ROOT, "work", "timeline.json"), encoding="utf-8"))
TOTAL = float(TL["total"])
SHOTS = TL["shots"]
SHOT_MAP = {s["id"]: s for s in SHOTS}
SENTENCES = TL.get("sentences", [])

# ---------------------------------------------------------------- 并发闸门
# 本机 cgroup 只有 6 GB。2026-11-10 一次 8 段并行渲染把内存顶到上限，内核 OOM 杀掉了
# 3082/3080 等进程。渲染槽位是进程级互斥：不论 README、run_render.sh 还是临时命令起了
# 多少段，同一台机器上真正在渲染的 scene_judgment 进程都不超过 RENDER_JOBS 个。
# 默认 2；可用环境变量 EP03_RENDER_JOBS 覆盖（1 即完全串行）。
RENDER_JOBS = max(1, int(os.environ.get("EP03_RENDER_JOBS", "2")))
SLOT_DIR = os.environ.get("EP03_RENDER_SLOT_DIR", "/tmp/ep03-render-slots")


def acquire_render_slot():
    """占用一个渲染槽位；占不到就阻塞等待。返回的 fd 需保持打开，进程退出时锁自动释放。"""
    os.makedirs(SLOT_DIR, exist_ok=True)
    waited = 0
    while True:
        for i in range(RENDER_JOBS):
            fd = os.open(os.path.join(SLOT_DIR, "slot-%02d.lock" % i), os.O_CREAT | os.O_RDWR, 0o644)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return fd, i
            except OSError:
                os.close(fd)
        # 长时间排队时每 60s 提示一次，避免日志刷屏
        if waited % 20 == 0:
            print("[render] 渲染并发已满（上限 %d），等待空槽 …" % RENDER_JOBS, flush=True)
        waited += 1
        time.sleep(3)

# ---------------------------------------------------------------- 基础常量
F_SERIF = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc"
F_SERIF_B = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc"
F_SANS = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
F_SANS_B = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"

BG = (8, 10, 14)
INK = (39, 37, 33)
INK_SOFT = (64, 60, 54)
INK_LIGHT = (118, 112, 102)
PAPER_INK = (26, 24, 21)
RED = (176, 54, 46)
RED_LIGHT = (206, 92, 78)
GOLD = (208, 172, 108)
WHITE = (235, 240, 244)
COOL = (146, 190, 226)
COOL_DIM = (96, 130, 160)
GREY = (150, 155, 160)

FPS_T = 1.0 / FPS


def clamp(v, a=0.0, b=1.0):
    return a if v < a else (b if v > b else v)


def smooth(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)


def ease_out(t):
    t = clamp(t)
    return 1 - (1 - t) ** 3


def ease_in(t):
    t = clamp(t)
    return t ** 3


def lerp(a, b, t):
    return a + (b - a) * t


def ft(path, size):
    return ImageFont.truetype(path, max(8, int(size)))


_FONT_CACHE = {}


def font(path, size):
    key = (path, int(size))
    f = _FONT_CACHE.get(key)
    if f is None:
        f = ft(path, size)
        _FONT_CACHE[key] = f
    return f


# ---------------------------------------------------------------- 文本纹理
_TEX = {}


def text_tex(s, size, color=INK, fnt=F_SANS, stroke=0, stroke_fill=(0, 0, 0), glow=0,
             glow_color=None, glow_strength=0.8, pad=None):
    key = ("t", s, int(size), color, fnt, stroke, glow, glow_color, glow_strength)
    im = _TEX.get(key)
    if im is not None:
        return im
    f = font(fnt, size)
    d = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
    bb = d.textbbox((0, 0), s, font=f)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    p = int(pad if pad is not None else max(8, size * 0.22 + glow * 2 + stroke))
    im = Image.new("RGBA", (max(2, tw + 2 * p), max(2, th + 2 * p)), (0, 0, 0, 0))
    dd = ImageDraw.Draw(im)
    tx, ty = p - bb[0], p - bb[1]
    if glow > 0:
        gl = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ImageDraw.Draw(gl).text((tx, ty), s, font=f, fill=(glow_color or color) + (255,),
                                stroke_width=stroke, stroke_fill=(glow_color or color) + (255,))
        gl = gl.filter(ImageFilter.GaussianBlur(glow))
        gl.putalpha(gl.getchannel("A").point(lambda v: int(v * glow_strength)))
        im.alpha_composite(gl)
    dd.text((tx, ty), s, font=f, fill=color + (255,), stroke_width=stroke,
            stroke_fill=stroke_fill + (255,))
    if len(_TEX) > 900:
        _TEX.clear()
    _TEX[key] = im
    return im


def put(img, tex, x, y, anchor="mm", alpha=1.0):
    if alpha <= 0.004:
        return
    if alpha < 0.999:
        t2 = tex.copy()
        t2.putalpha(t2.getchannel("A").point(lambda v: int(v * alpha)))
        tex = t2
    if anchor == "mm":
        bx, by = int(x - tex.width / 2), int(y - tex.height / 2)
    elif anchor == "la":
        bx, by = int(x), int(y)
    elif anchor == "lm":
        bx, by = int(x), int(y - tex.height / 2)
    elif anchor == "cm":
        bx, by = int(x - tex.width / 2), int(y - tex.height / 2)
    elif anchor == "rm":
        bx, by = int(x - tex.width), int(y - tex.height / 2)
    else:
        bx, by = int(x), int(y)
    img.alpha_composite(tex, (bx, by))


def draw_soft_shadow(img, pts, strength=0.5, blur=16, spread=1.0):
    pts = np.asarray(pts, dtype=np.float64)
    x0, y0 = pts.min(axis=0) - blur * 2
    x1, y1 = pts.max(axis=0) + blur * 2
    bw, bh = int(x1 - x0), int(y1 - y0)
    if bw < 2 or bh < 2 or bw > W * 2 or bh > H * 2:
        return
    ds = 4
    sw, sh = max(2, bw // ds), max(2, bh // ds)
    lay = Image.new("L", (sw, sh), 0)
    d = ImageDraw.Draw(lay)
    poly = [((p[0] - x0) / ds, (p[1] - y0) / ds) for p in pts]
    d.polygon(poly, fill=255)
    lay = lay.filter(ImageFilter.GaussianBlur(max(1.2, blur / ds)))
    lay = lay.resize((bw, bh), Image.BILINEAR)
    a = lay.point(lambda v: int(v * strength))
    sh = Image.new("RGBA", (bw, bh), (0, 0, 0, 255))
    sh.putalpha(a)
    img.alpha_composite(sh, (int(x0), int(y0)))


# ---------------------------------------------------------------- 相机与 3D
class Cam:
    """世界坐标：x 右，y 上，z 远离相机。桌面在 y=0。"""

    def __init__(self, pos, target, fov=42.0):
        self.pos = np.array(pos, dtype=np.float64)
        self.target = np.array(target, dtype=np.float64)
        f = self.target - self.pos
        self.fwd = f / np.linalg.norm(f)
        upw = np.array([0.0, 1.0, 0.0])
        r = np.cross(upw, self.fwd)
        n = np.linalg.norm(r)
        self.right = r / n if n > 1e-6 else np.array([1.0, 0.0, 0.0])
        self.up = np.cross(self.fwd, self.right)
        self.f = (H / 2.0) / math.tan(math.radians(fov) / 2.0)

    def project(self, pts):
        p = np.asarray(pts, dtype=np.float64) - self.pos
        xc = p @ self.right
        yc = p @ self.up
        zc = p @ self.fwd
        z = np.maximum(zc, 1e-5)
        sx = W / 2.0 + self.f * xc / z
        sy = H / 2.0 - self.f * yc / z
        return np.stack([sx, sy], axis=-1), zc

    def dist(self, p):
        return float(np.linalg.norm(np.asarray(p) - self.pos))


def cam_path(t, keys):
    """keys: [(t, pos, target, fov), ...] 平滑插值。"""
    if t <= keys[0][0]:
        k = keys[0]
        return Cam(k[1], k[2], k[3])
    if t >= keys[-1][0]:
        k = keys[-1]
        return Cam(k[1], k[2], k[3])
    for i in range(len(keys) - 1):
        a, b = keys[i], keys[i + 1]
        if a[0] <= t <= b[0]:
            u = smooth((t - a[0]) / (b[0] - a[0]))
            return Cam(tuple(lerp(a[1][j], b[1][j], u) for j in range(3)),
                       tuple(lerp(a[2][j], b[2][j], u) for j in range(3)),
                       lerp(a[3], b[3], u))
    return Cam(keys[-1][1], keys[-1][2], keys[-1][3])


# 标准机位（按纸张屏幕占比论证后固定；镜头运动交给 apply_move）
CAM_PROPPED = ((0.0, 2.15, -2.16), (0.0, 0.62, 0.32), 41)   # 近竖直阅读角度（图纸/账单）
CAM_FLAT = ((0.0, 2.15, -1.08), (0.0, 0.0, 0.42), 41)        # 俯视 55° 平铺（账单）
CAM_WRITE = ((0.0, 2.18, -1.10), (0.0, 0.0, 0.40), 41)       # 俯视 55° 书写（三问）
CAM_LYING = ((0.0, 1.90, -0.91), (0.0, 0.0, 0.36), 41)       # 较低俯角（压在桌上的纸）
CAM_DESK2 = ((0.18, 2.55, -1.72), (0.0, 0.02, 0.34), 42)      # 桌面双纸（答案盖住初判）


def paper_corners(center, w, h, yaw_deg=0.0, tilt_deg=75.0):
    """tilt=0: 竖直面向相机；tilt=90: 平铺桌面。yaw 绕竖轴。"""
    yaw = math.radians(yaw_deg)
    tilt = math.radians(tilt_deg)
    normal = np.array([0.0, math.sin(tilt), -math.cos(tilt)])
    u = np.array([math.cos(yaw), 0.0, math.sin(yaw)])
    v = np.cross(normal, u)
    v = v / np.linalg.norm(v)
    u = u * w * 0.5
    v = v * h * 0.5
    c = np.array(center, dtype=np.float64)
    return np.array([c - u - v, c + u - v, c + u + v, c - u + v])  # TL TR BR BL


def quad_layer(cam, corners, tex, alpha=1.0, shade=1.0, blur=0.0):
    pts, dep = cam.project(corners)
    if np.any(dep <= 0.05):
        return None
    q = E.quad_texture(pts, tex, alpha=alpha, shade=shade, blur=blur)
    return q


def paper_rect_screen(cam, center, w, h, yaw=0.0, tilt=75.0):
    pts, _ = cam.project(paper_corners(center, w, h, yaw, tilt))
    x0, y0 = pts.min(axis=0)
    x1, y1 = pts.max(axis=0)
    return x0, y0, x1, y1


# ---------------------------------------------------------------- 场景
class Scene:
    def __init__(self, cam, bg):
        self.img = bg.convert("RGBA")
        self.cam = cam
        self.items = []

    def add(self, depth, fn):
        self.items.append((float(depth), fn))

    def paper(self, tex, center, w=1.06, h=1.5, yaw=0.0, tilt=75.0, alpha=1.0,
              shade=1.0, shadow=0.55, soff=(0.16, 0.0), sblur=18, zlift=0.0):
        c = np.array(center, dtype=np.float64) + np.array([0.0, zlift, 0.0])
        corners = paper_corners(c, w, h, yaw, tilt)
        pts, dep = self.cam.project(corners)
        if np.any(dep <= 0.05):
            return
        depth = float(dep.mean()) - 20.0 * float(c[1])
        cam = self.cam
        shadow_pts = None
        if shadow > 0:
            sc = c + np.array([soff[0], 0.0, soff[1]])
            shadow_pts, _ = cam.project(paper_corners(sc, w, h, yaw, tilt))

        def _draw(img):
            if shadow_pts is not None:
                draw_soft_shadow(img, shadow_pts, strength=shadow, blur=sblur)
            q = quad_layer(cam, corners, tex, alpha=alpha, shade=shade)
            if q is not None:
                lay, bx, by = q
                img.alpha_composite(lay, (bx, by))
        self.add(depth, _draw)

    def flush(self):
        for depth, fn in sorted(self.items, key=lambda x: -x[0]):
            fn(self.img)
        self.items = []


# ---------------------------------------------------------------- 资产纹理
_ASSETS = os.path.join(ROOT, "assets")
_BACKDROP_CACHE = {}


def load_backdrop(name, size=(2160, 3840)):
    key = (name, size)
    im = _BACKDROP_CACHE.get(key)
    if im is not None:
        return im
    for cand in (os.path.join(_ASSETS, "backdrops", name + ".jpg"),
                 os.path.join(_ASSETS, "backdrops", name + ".png")):
        if os.path.exists(cand):
            im = Image.open(cand).convert("RGB")
            break
    if im is None:
        im = _procedural_backdrop(name)
    im = im.resize(size, Image.LANCZOS)
    _BACKDROP_CACHE[key] = im
    return im


def _procedural_backdrop(name):
    rng = random.Random(hash(name) & 0xFFFF)
    w, h = 2160, 3840
    yy, xx = np.ogrid[:h, :w]
    nx = (xx - w * 0.5) / (w * 0.5)
    ny = (yy - h * 0.5) / (h * 0.5)
    d = np.sqrt(nx ** 2 + ny ** 2)
    base = np.zeros((h, w, 3), dtype=np.float32)
    glow = np.exp(-(d ** 2) * 1.6)
    if "warm" in name:
        col = (86, 62, 40)
    elif "city" in name:
        col = (26, 34, 52)
    else:
        col = (28, 40, 56)
    for i in range(3):
        base[..., i] = col[i] * (0.25 + 1.5 * glow)
    # 散布 bokeh 光斑
    lay = Image.new("RGB", (w, h), (0, 0, 0))
    dd = ImageDraw.Draw(lay)
    for _ in range(26):
        cx, cy = rng.uniform(0, w), rng.uniform(0, h)
        r = rng.uniform(60, 260)
        c = (rng.randint(20, 60), rng.randint(18, 50), rng.randint(14, 40))
        dd.ellipse((cx - r, cy - r, cx + r, cy + r), fill=c)
    lay = lay.filter(ImageFilter.GaussianBlur(70))
    arr = np.clip(base + np.asarray(lay, dtype=np.float32), 0, 255)
    return Image.fromarray(arr.astype(np.uint8))


def load_texture(name):
    for cand in (os.path.join(_ASSETS, "textures", name + ".png"),
                 os.path.join(_ASSETS, "textures", name + ".jpg")):
        if os.path.exists(cand):
            return Image.open(cand).convert("RGBA")
    return None


_WOOD = None


def wood_texture():
    global _WOOD
    if _WOOD is not None:
        return _WOOD
    im = load_texture("desk_wood")
    if im is None:
        w, h = 1600, 2400
        rng = np.random.default_rng(11)
        yy, xx = np.mgrid[:h, :w].astype(np.float32)
        base = 62 + 26 * np.sin(xx * 0.004 + 2.2 * np.sin(yy * 0.0016)) ** 2
        base += 10 * np.sin(yy * 0.0009 + 1.3)
        grain = rng.normal(0, 7, (h, w))
        arr = np.stack([base * 1.18, base * 0.86, base * 0.66], axis=-1) + grain[..., None]
        im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGBA")
    if im.width > 1800:
        im = im.resize((1800, int(im.height * 1800 / im.width)), Image.LANCZOS)
    _WOOD = im
    return im


_BOKEH = {}


def bokeh_layer(mode="cool"):
    lay = _BOKEH.get(mode)
    if lay is not None:
        return lay
    rng = random.Random(7 if mode == "cool" else 19)
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for _ in range(38):
        cx = rng.uniform(-100, W + 100)
        cy = rng.uniform(-80, H * 0.55)
        r = rng.uniform(18, 120)
        if mode == "warm":
            c = (rng.randint(90, 150), rng.randint(60, 100), rng.randint(24, 50), rng.randint(16, 46))
        else:
            c = (rng.randint(40, 80), rng.randint(60, 100), rng.randint(80, 130), rng.randint(14, 40))
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=c)
    lay = lay.filter(ImageFilter.GaussianBlur(26))
    _BOKEH[mode] = lay
    return lay


_GRAD = {}


def bg_gradient(mode="cool"):
    g = _GRAD.get(mode)
    if g is not None:
        return g
    yy, xx = np.ogrid[:H, :W]
    ny = yy / H
    if mode == "warm":
        top = (20, 17, 15)
        bot = (9, 8, 8)
    elif mode == "deep":
        top = (6, 8, 12)
        bot = (3, 4, 6)
    else:
        top = (13, 19, 27)
        bot = (5, 7, 10)
    arr = np.zeros((H, W, 3), dtype=np.float32)
    for i in range(3):
        arr[..., i] = lerp(top[i], bot[i], ny)
    # 中心微弱冷光
    nx = (xx - W * 0.5) / (W * 0.5)
    glow = np.exp(-((nx ** 2) * 1.6 + ((ny - 0.18) ** 2) * 6.0))
    arr[..., 2] += glow * 26
    arr[..., 1] += glow * 12
    g = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGBA")
    _GRAD[mode] = g
    return g


# ---------------------------------------------------------------- 桌面底
_FLOOR_CACHE = {}
_CUR_SHOT = {"id": ""}


def _floor_np(cam, tex, scale=0.62, lamp=(-2.0, 2.4, 0.3)):
    """透视光栅化水平桌面：逐像素求视线与 y=0 求交，采样木纹贴图并加灯光/雾。"""
    tw, th = tex.size
    arr = np.asarray(tex.convert("RGB"), dtype=np.float32)
    xs = (np.arange(W) + 0.5 - W / 2) / cam.f
    ys = (np.arange(H) + 0.5 - H / 2) / cam.f
    dirx = cam.fwd[0] + cam.right[0] * xs[None, :] + cam.up[0] * (-ys)[:, None]
    diry = cam.fwd[1] + cam.up[1] * (-ys)
    dirz = cam.fwd[2] + cam.right[2] * xs[None, :] + cam.up[2] * (-ys)[:, None]
    valid = diry < -1e-4
    t = np.where(valid, -cam.pos[1] / np.where(valid, diry, -1.0), -1.0)
    t = np.where(t > 0, t, -1.0)[:, None]
    wx = cam.pos[0] + t * dirx
    wz = cam.pos[2] + t * dirz
    u = (wx * scale) % tw
    v = (wz * scale) % th
    ui = np.clip(u.astype(np.int32), 0, tw - 1)
    vi = np.clip(v.astype(np.int32), 0, th - 1)
    rgb = arr[vi, ui]
    # 灯光：桌面上一盏暖灯 + 环境冷光
    lx, ly, lz = lamp
    dd = np.sqrt((wx - lx) ** 2 + (wz - lz) ** 2 + 1.6)
    light = 0.30 + 0.95 / (1.0 + dd / 2.2)
    warm = np.clip(1.35 - dd / 8.0, 0.35, 1.15)
    rgb = rgb * light[..., None]
    rgb[..., 0] *= warm
    rgb[..., 1] *= (warm * 0.92 + 0.08)
    rgb[..., 2] *= (warm * 0.72 + 0.28)
    # 远处压暗（景深渐隐）
    t = np.broadcast_to(t, (H, W))
    fog = np.clip((t - 1.2) / 7.0, 0, 1) ** 1.2
    rgb = rgb * (1 - 0.85 * fog[..., None])
    alpha = np.where((t > 0), 255.0, 0.0).astype(np.float32)
    out = np.dstack([np.clip(rgb, 0, 255), alpha]).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def desk_base(cam, mode="cool", lamp=0.5, screen=None, horizon_z=-1.2):
    key = (_CUR_SHOT["id"], mode, round(cam.pos[0], 3), round(cam.pos[1], 3), round(cam.pos[2], 3),
           round(cam.target[0], 3), round(cam.target[1], 3), round(cam.target[2], 3))
    cached = _FLOOR_CACHE.get(key)
    if cached is not None:
        return cached.copy()
    img = bg_gradient(mode).copy()
    img.alpha_composite(bokeh_layer("warm" if mode == "warm" else "cool"))
    floor = _floor_np(cam, wood_texture(), scale=0.62,
                      lamp=(-2.0, 2.4, 0.3) if mode == "warm" else (-2.4, 2.4, 0.6))
    img.alpha_composite(floor)
    if len(_FLOOR_CACHE) > 60:
        _FLOOR_CACHE.clear()
    _FLOOR_CACHE[key] = img
    return img.copy()


_LIGHT_CACHE = {}


def _light_field(mode):
    f = _LIGHT_CACHE.get(mode)
    if f is not None:
        return f
    yy, xx = np.ogrid[:H, :W]
    if mode == "desk_lamp":
        gx, gy = W * 0.16, H * 0.30
        warm = np.exp(-(((xx - gx) ** 2) / (2 * (W * 0.42) ** 2) + ((yy - gy) ** 2) / (2 * (H * 0.40) ** 2)))
        cool = np.exp(-(((xx - W * 0.88) ** 2) / (2 * (W * 0.34) ** 2) + ((yy - H * 0.16) ** 2) / (2 * (H * 0.30) ** 2)))
        add = np.stack([warm * 32, warm * 21, warm * 10], axis=-1) + np.stack([cool * 7, cool * 15, cool * 28], axis=-1)
    elif mode == "screen":
        cool = np.exp(-(((xx - W * 0.5) ** 2) / (2 * (W * 0.55) ** 2) + ((yy - H * 0.18) ** 2) / (2 * (H * 0.34) ** 2)))
        warm = np.exp(-(((xx - W * 0.14) ** 2) / (2 * (W * 0.30) ** 2) + ((yy - H * 0.72) ** 2) / (2 * (H * 0.30) ** 2)))
        add = np.stack([cool * 8, cool * 20, cool * 38], axis=-1) + np.stack([warm * 28, warm * 17, warm * 7], axis=-1)
    elif mode == "red":
        gx, gy = W * 0.78, H * 0.42
        warm = np.exp(-(((xx - gx) ** 2) / (2 * (W * 0.40) ** 2) + ((yy - gy) ** 2) / (2 * (H * 0.36) ** 2)))
        add = np.stack([warm * 46, warm * 12, warm * 10], axis=-1)
    else:
        warm = np.exp(-(((xx - W * 0.5) ** 2) / (2 * (W * 0.7) ** 2) + ((yy - H * 0.45) ** 2) / (2 * (H * 0.55) ** 2)))
        add = np.stack([warm * 20, warm * 18, warm * 16], axis=-1)
    f = add.astype(np.float32)
    _LIGHT_CACHE[mode] = f
    return f


def add_light(img, mode="desk_lamp", t=0.0, strength=1.0):
    arr = np.array(img, dtype=np.float32)
    arr[..., :3] = np.clip(arr[..., :3] + _light_field(mode) * strength, 0, 255)
    return Image.fromarray(arr.astype(np.uint8), "RGBA")


_GRADE_LUT = {}


def finish(img, seed=0, bloom=0.24, grain=3.0, vignette=0.55, sat=1.0, warm_hi=1.04, cool_sh=1.02):
    rgb = img.convert("RGB")
    arr = np.asarray(rgb, dtype=np.float32)
    # 辉光：只对高光做小图模糊再叠加
    small = rgb.resize((W // 8, H // 8), Image.BILINEAR)
    sarr = np.asarray(small, dtype=np.float32)
    lum = sarr.mean(axis=2, keepdims=True)
    bright = np.clip((lum - 152.0) / (255.0 - 152.0), 0, 1) ** 1.6
    bl = Image.fromarray(np.clip(sarr * bright, 0, 255).astype(np.uint8)).convert("RGB")
    bl = bl.filter(ImageFilter.GaussianBlur(7)).resize((W, H), Image.BILINEAR)
    if bloom > 0:
        arr = arr + np.asarray(bl, dtype=np.float32) * bloom
    # 调色（冷阴影 / 暖高光 / 轻微对比）
    arr = np.clip(arr / 255.0, 0, 1) ** (1.0 / 1.04)
    arr[..., 0] = np.clip(arr[..., 0] * warm_hi * 1.02 + 0.004, 0, 1)
    arr[..., 1] = np.clip(arr[..., 1] * 1.01 + 0.002, 0, 1)
    arr[..., 2] = np.clip(arr[..., 2] * cool_sh * 0.94, 0, 1)
    if sat != 1.0:
        g = arr.mean(axis=2, keepdims=True)
        arr = np.clip(g + (arr - g) * sat, 0, 1)
    arr = np.clip((arr - 0.5) * 1.055 + 0.5, 0, 1)
    if vignette > 0:
        yy, xx = np.ogrid[:H, :W]
        nx = (xx - W / 2) / (W / 2)
        ny = (yy - H / 2) / (H / 2)
        d = np.sqrt(nx ** 2 + ny ** 2) / 1.414
        arr *= np.clip(1 - vignette * (d ** 2.1), 0, 1)[:, :, None]
    out = np.clip(arr * 255, 0, 255)
    if grain > 0:
        rng = np.random.default_rng(seed + 11)
        noise = rng.integers(-6, 7, (H, W), dtype=np.int16)
        out = np.clip(out.astype(np.int16) + (noise[:, :, None] * (grain / 6.0)).astype(np.int16), 0, 255)
    return Image.fromarray(out.astype(np.uint8))


# ---------------------------------------------------------------- 纸张内容
_PAPER_CACHE = {}


def paper_base_kind(kind="warm"):
    key = ("base", kind)
    im = _PAPER_CACHE.get(key)
    if im is not None:
        return im
    ext = load_texture("paper_" + kind)
    if ext is not None:
        im = ext.resize((1000, 1414), Image.LANCZOS)
    else:
        rng = np.random.default_rng(3 if kind == "warm" else 5)
        yy, xx = np.mgrid[:1414, :1000].astype(np.float32)
        base = 214.0 if kind == "warm" else 226.0
        fiber = rng.normal(0, 6, (1414, 1000))
        bands = 4 * np.sin(xx * 0.008 + yy * 0.002)
        arr = np.stack([base + fiber + bands, base * 0.955 + fiber + bands, base * 0.84 + fiber * 0.8 + bands], axis=-1)
        im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGBA")
    arr = np.asarray(im.convert("RGB"), dtype=np.float32)
    m = float(arr.mean())
    target = 206.0 if kind != "warm" else 188.0
    if m > 1:
        arr = np.clip(arr * (target / m), 0, 255)
    im = Image.fromarray(arr.astype(np.uint8)).convert("RGBA")
    _PAPER_CACHE[key] = im
    return im


def new_page(kind="warm"):
    return paper_base_kind(kind).copy()


def txt(d, xy, s, size, color=INK, fnt=F_SANS, anchor="la", stroke=0):
    d.text(xy, s, font=font(fnt, size), fill=color + (255,), anchor=anchor,
           stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
    return d


def rule(d, x0, y0, x1, y1, color=(120, 112, 100), width=1):
    d.line((x0, y0, x1, y1), fill=color + (200,), width=int(width))


def wrap_cn(s, maxchars):
    out, line = [], ""
    for ch in s:
        line += ch
        if len(line) >= maxchars and ch in "，。；！？、：":
            out.append(line)
            line = ""
    if line:
        out.append(line)
    # 二次硬切
    res = []
    for l in out:
        while len(l) > maxchars + 2:
            res.append(l[:maxchars])
            l = l[maxchars:]
        if l:
            res.append(l)
    return res


def seal_texture():
    im = load_texture("seal_red")
    if im is not None:
        return im
    # 兜底：程序化方印
    s = 640
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    red = (168, 42, 36, 235)
    d.rounded_rectangle((18, 18, s - 18, s - 18), radius=10, outline=red, width=14)
    d.rounded_rectangle((48, 48, s - 48, s - 48), radius=6, outline=red, width=6)
    f = ft(F_SERIF_B, 170)
    for i, ch in enumerate("判断力"):
        d.text((s / 2, 155 + i * 175), ch, font=f, fill=red, anchor="mm")
    im = im.filter(ImageFilter.GaussianBlur(0.6))
    return im


_SEAL = None


def seal():
    global _SEAL
    if _SEAL is None:
        _SEAL = seal_texture()
    return _SEAL


def stamp_tex(label, color=RED, circular=True, size=520):
    """圆形/方形印章纹理（透明底）。"""
    key = ("stamp", label, color, circular, size)
    im = _TEX.get(key)
    if im is not None:
        return im
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = color + (225,)
    if circular:
        m = 26
        d.ellipse((m, m, size - m, size - m), outline=c, width=12)
        d.ellipse((m + 22, m + 22, size - m - 22, size - m - 22), outline=c, width=4)
        f = ft(F_SANS_B, int(size * 0.20))
        d.text((size / 2, size * 0.40), label[:3], font=f, fill=c, anchor="mm")
        if len(label) > 3:
            d.text((size / 2, size * 0.66), label[3:6], font=ft(F_SANS_B, int(size * 0.16)), fill=c, anchor="mm")
    else:
        d.rectangle((20, 20, size - 20, size - 20), outline=c, width=14)
        f = ft(F_SANS_B, int(size * 0.30))
        d.text((size / 2, size / 2), label, font=f, fill=c, anchor="mm")
    # 做旧：随机擦除斑点
    rng = np.random.default_rng(len(label) + size)
    alpha = np.asarray(im.getchannel("A")).copy()
    for _ in range(int(size * 0.5)):
        x, y = rng.integers(0, size), rng.integers(0, size)
        r = int(rng.integers(1, 6))
        alpha[max(0, y - r):y + r, max(0, x - r):x + r] = (alpha[max(0, y - r):y + r, max(0, x - r):x + r] * 0.15).astype(np.uint8)
    im.putalpha(Image.fromarray(alpha))
    _TEX[key] = im
    return im


def composite_stamp(page, label, x, y, size=380, angle=-8, alpha=0.85, color=RED, circular=True, scale=1.0):
    st = stamp_tex(label, color, circular, 520).resize((int(size * scale), int(size * scale)), Image.LANCZOS)
    st = st.rotate(angle, expand=True, resample=Image.BICUBIC)
    if alpha < 0.999:
        st2 = st.copy()
        st2.putalpha(st2.getchannel("A").point(lambda v: int(v * alpha)))
        st = st2
    page.alpha_composite(st, (int(x - st.width / 2), int(y - st.height / 2)))


# ---------------------------------------------------------------- 字幕
_CAPS = None


_CAP_CACHE = None


def _cap_width(s):
    return sum(0.58 if ord(c) < 128 else 1.0 for c in s)


def cap_chunks(text, maxw=12.0):
    """按可读宽度切句：英文单词/数字不拆，中文按字累加。"""
    tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9\.\-/%']*|\s+|.", text)
    lines, cur, curw = [], "", 0.0
    for tk in tokens:
        tw = _cap_width(tk)
        if cur.strip() and curw + tw > maxw:
            lines.append(cur.strip())
            cur, curw = "", 0.0
            if tk.isspace():
                continue
        cur += tk
        curw += tw
    if cur.strip():
        lines.append(cur.strip())
    return lines


def build_captions():
    global _CAP_CACHE
    if _CAP_CACHE is not None:
        return _CAP_CACHE
    caps = []
    for s in SENTENCES:
        chunks = cap_chunks(s["text"], 12.0)
        if not chunks:
            continue
        total = sum(max(1.0, _cap_width(c)) for c in chunks)
        t = float(s["start"])
        dur = max(0.2, float(s["end"]) - float(s["start"]))
        for c in chunks:
            d = dur * max(1.0, _cap_width(c)) / total
            caps.append((round(t, 3), round(t + d, 3), c))
            t += d
    caps.sort()
    for i in range(1, len(caps)):
        if caps[i][0] < caps[i - 1][1]:
            caps[i - 1] = (caps[i - 1][0], caps[i][0], caps[i - 1][2])
    _CAP_CACHE = caps
    return caps


def draw_caption(img, t):
    for (a, b, text) in build_captions():
        if a <= t < b:
            alpha = clamp((t - a) / 0.12) * clamp((b - t) / 0.12 + 0.55)
            tex = text_tex(text, 42, (240, 242, 246), fnt=F_SANS_B, stroke=3,
                           stroke_fill=(0, 0, 0), pad=18)
            put(img, tex, W / 2, H - 168, alpha=0.94 * min(1.0, alpha))
            return


# ---------------------------------------------------------------- 通用绘制
def solid_overlay(alpha=120, color=(0, 0, 0)):
    lay = Image.new("RGBA", (W, H), color + (alpha,))
    return lay


def v_grad(top_a=0, bot_a=200, color=(0, 0, 0), h=H):
    lay = Image.new("RGBA", (W, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for y in range(h):
        a = int(lerp(top_a, bot_a, y / max(1, h - 1)))
        d.line((0, y, W, y), fill=color + (a,))
    return lay


def screen_text(img, s, y, size=54, color=WHITE, fnt=F_SERIF, glow=18, glow_color=None,
                t0=0.0, t=0.0, alpha=1.0, x=None, anchor="mm", rise=26):
    a = clamp((t - t0) / 0.6) * alpha
    if a <= 0:
        return
    tex = text_tex(s, size, color, fnt=fnt, glow=glow, glow_color=glow_color or color,
                   glow_strength=0.42, stroke=2, stroke_fill=(0, 0, 0))
    put(img, tex, x if x is not None else W / 2, y + (1 - a) * rise, anchor=anchor, alpha=a)


def backdrop_shot(scene, t, name, zoom=(1.04, 1.10), pan=(0.0, 0.0), darken=110, blur=0.0):
    im = load_backdrop(name)
    bw, bh = im.size
    z = lerp(zoom[0], zoom[1], clamp(t / max(0.1, 6.0)))
    cw, ch = int(bw / z), int(bh / z)
    cx = int((bw - cw) / 2 + pan[0] * (bw - cw) * smooth(clamp(t / 8.0)))
    cy = int((bh - ch) / 2 + pan[1] * (bh - ch) * smooth(clamp(t / 8.0)))
    crop = im.crop((cx, cy, cx + cw, cy + ch)).resize((W, H), Image.LANCZOS)
    if blur > 0:
        crop = crop.filter(ImageFilter.GaussianBlur(blur))
    arr = np.asarray(crop, dtype=np.float32) * (1.0 - darken / 255.0)
    out = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGBA")
    scene.img = out


def line_progress(d, x0, y0, x1, y1, prog, color=INK, width=3):
    if prog <= 0:
        return
    x = lerp(x0, x1, clamp(prog))
    y = lerp(y0, y1, clamp(prog))
    d.line((x0, y0, x, y), fill=color + (235,), width=int(width))


_PEN = None


def pen_tex():
    global _PEN
    if _PEN is not None:
        return _PEN
    w, h = 90, 300
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    # 笔杆（深棕）与金属笔尖，笔尖朝下
    d.rounded_rectangle((30, 12, 60, 210), radius=14, fill=(28, 24, 20, 255))
    d.rounded_rectangle((34, 18, 43, 200), radius=4, fill=(58, 50, 42, 255))
    d.polygon([(30, 208), (60, 208), (52, 262), (45, 292), (38, 262)], fill=(196, 178, 142, 255))
    d.polygon([(45, 250), (45, 292), (38, 262), (38, 250)], fill=(120, 106, 82, 255))
    _PEN = im
    return im


def pen_nib(img, x, y, angle=0.0, scale=1.0, alpha=1.0):
    pen = pen_tex()
    if scale != 1.0:
        pen = pen.resize((int(pen.width * scale), int(pen.height * scale)), Image.LANCZOS)
    pen = pen.rotate(angle, expand=True, resample=Image.BICUBIC)
    if alpha < 0.999:
        pen = pen.copy()
        pen.putalpha(pen.getchannel("A").point(lambda v: int(v * alpha)))
    # 锚点：笔尖约在图片底部中央
    img.alpha_composite(pen, (int(x - pen.width / 2), int(y - pen.height * 0.94)))

def shot_cold_open(scene, t, shot):
    cam = Cam((0, 2.30, -3.45), (0, 0.18, 0.35), 40)
    scene.cam = cam
    scene.img = desk_base(cam, "warm")
    a = ease_out((t - 0.30) / 0.90)
    b = ease_out((t - 0.55) / 0.90)
    if a > 0:
        scene.paper(tex_gen_bill_mini(), (-0.52 + 0.03 * (1 - a), 0.010, 0.48 + (1 - a) * 1.6),
                    w=0.88, h=1.24, yaw=-8, tilt=72, shade=0.97, shadow=0.5,
                    alpha=clamp(a * 1.4))
    if b > 0:
        scene.paper(tex_verify_bill_mini(), (0.50 - 0.03 * (1 - b), 0.012, 0.56 + (1 - b) * 1.6),
                    w=0.88, h=1.24, yaw=7, tilt=72, shade=0.97, shadow=0.5,
                    alpha=clamp(b * 1.4))
    if t > 1.85:
        scene.add(0.05, lambda img: _stamp_on_paper(
            img, cam, t, 1.85, (0.50, 0.012, 0.56), 0.88, 1.24, 7, 72,
            label="欠", off=(0.07, 0.10), size=0.15, angle=-6))
    scene.flush()
    scene.img = add_light(scene.img, "desk_lamp", t, 1.0)
    if t > 2.30:
        a2 = clamp((t - 2.30) / 0.70)
        scene.img.alpha_composite(v_grad(0, int(150 * a2)), (0, 0))
        screen_text(scene.img, "AI 时代最贵的债", 300, 78, WHITE, t0=2.30, t=t,
                    glow=22, glow_color=GOLD)
        screen_text(scene.img, "是判断力", 408, 104, GOLD, t0=2.48, t=t, glow=26,
                    glow_color=GOLD)
        tex = text_tex("答案越来越便宜，核验却越来越贵", 32, (214, 210, 202), fnt=F_SANS, glow=8)
        put(scene.img, tex, W / 2, 520, alpha=clamp((t - 2.90) / 0.6) * 0.95)
    return scene.img

def _stamp_on_paper(img, cam, t, t0, center, w, h, yaw, tilt, label, off, size,
                    scale_from=1.8, color=RED, circular=None, angle=-7):
    prog = clamp((t - t0) / 0.22)
    if prog <= 0:
        return
    pts, dep = cam.project(paper_corners(center, w, h, yaw, tilt))
    u = pts[1] - pts[0]
    v = pts[3] - pts[0]
    x = pts[0][0] + u[0] * (0.5 + off[0]) + v[0] * (0.5 + off[1])
    y = pts[0][1] + u[1] * (0.5 + off[0]) + v[1] * (0.5 + off[1])
    if circular is None:
        circular = len(label) > 2
    st0 = seal() if label == "判断力" else stamp_tex(label, color, circular=circular, size=480)
    sc = lerp(scale_from, 1.0, ease_in(prog))
    px = int(W * size * sc)
    st = st0.resize((px, px), Image.LANCZOS).rotate(angle, expand=True, resample=Image.BICUBIC)
    a = clamp(prog * 2.2)
    if a < 0.999:
        st = st.copy()
        st.putalpha(st.getchannel("A").point(lambda q: int(q * a)))
    img.alpha_composite(st, (int(x - st.width / 2), int(y - st.height / 2)))


# ---------------- 纸张内容：账单
def tex_gen_bill_mini():
    key = "gen_bill_mini"
    if key in _PAPER_CACHE:
        return _PAPER_CACHE[key]
    p = new_page("warm")
    d = ImageDraw.Draw(p)
    txt(d, (80, 92), "生成账单", 66, PAPER_INK, F_SERIF_B)
    rule(d, 80, 190, 920, 190, (120, 108, 92), 3)
    txt(d, (80, 240), "项目", 30, INK_SOFT)
    txt(d, (700, 240), "费用", 30, INK_SOFT)
    rows = [("版式", "¥0.00"), ("文案", "¥0.00"), ("逻辑", "¥0.00")]
    for i, (k, v) in enumerate(rows):
        txt(d, (80, 320 + i * 110), k, 44, PAPER_INK)
        txt(d, (700, 320 + i * 110), v, 44, INK_SOFT)
    rule(d, 80, 700, 920, 700, (120, 108, 92), 2)
    txt(d, (80, 760), "合计", 40, INK_SOFT)
    txt(d, (760, 750), "¥0.00", 64, PAPER_INK, F_SERIF_B)
    txt(d, (80, 920), "生成用时 8 秒", 30, INK_SOFT)
    txt(d, (80, 970), "一次通过", 30, INK_SOFT)
    _PAPER_CACHE[key] = p
    return p


def tex_verify_bill_mini():
    key = "verify_bill_mini"
    if key in _PAPER_CACHE:
        return _PAPER_CACHE[key]
    p = new_page("white")
    d = ImageDraw.Draw(p)
    txt(d, (80, 92), "核验账单", 66, PAPER_INK, F_SERIF_B)
    rule(d, 80, 190, 920, 190, (120, 108, 92), 3)
    rows = ["来源", "事实", "边界", "反例"]
    for i, k in enumerate(rows):
        y = 300 + i * 120
        d.rectangle((80, y, 128, y + 48), outline=RED + (255,), width=3)
        txt(d, (170, y - 4), k, 44, PAPER_INK)
        txt(d, (700, y - 4), "待核", 36, RED)
    rule(d, 80, 830, 920, 830, (120, 108, 92), 2)
    txt(d, (80, 890), "合计", 40, INK_SOFT)
    txt(d, (720, 880), "待结", 60, RED, F_SERIF_B)
    txt(d, (80, 1040), "逐项检查 · 需要时间", 30, INK_SOFT)
    _PAPER_CACHE[key] = p
    return p


# ---------------- 纸张内容：答案与初判
def tex_answer():
    key = "answer"
    if key in _PAPER_CACHE:
        return _PAPER_CACHE[key]
    p = new_page("white")
    d = ImageDraw.Draw(p)
    txt(d, (80, 84), "方案建议书", 62, PAPER_INK, F_SERIF_B)
    txt(d, (80, 172), "（AI 生成 · 可直接使用）", 28, INK_SOFT)
    rule(d, 80, 226, 920, 226, (120, 108, 92), 2)
    lines = ["一、目标与范围", "二、三步实施路径", "三、预算与排期", "四、风险与备用方案"]
    y = 280
    for h in lines:
        txt(d, (80, y), h, 36, PAPER_INK, F_SANS_B)
        y += 62
        for k in range(3):
            w = int(760 - k * 60 - (y % 3) * 20)
            rule(d, 80, y, 80 + w, y, (150, 144, 132), 6)
            y += 34
        y += 22
    txt(d, (80, 1180), "结构完整 · 逻辑清晰 · 可直接提交", 30, INK_SOFT)
    txt(d, (80, 1240), "生成用时 8 秒", 28, INK_LIGHT)
    _PAPER_CACHE[key] = p
    return p


def tex_first_judgment():
    key = "first_judgment"
    if key in _PAPER_CACHE:
        return _PAPER_CACHE[key]
    p = new_page("warm")
    d = ImageDraw.Draw(p)
    txt(d, (80, 92), "我的初判", 60, PAPER_INK, F_SERIF_B)
    rule(d, 80, 186, 920, 186, (120, 108, 92), 2)
    for i, s in enumerate(["先问：这个方案替谁省事？", "再问：哪一步最容易出错？", "最后：如果错了，我能发现吗？"]):
        txt(d, (96, 280 + i * 130), s, 38, PAPER_INK)
    # 红框空白判断
    d.rectangle((96, 760, 900, 1120), outline=RED + (235,), width=5)
    txt(d, (498, 880), "判断", 70, RED, F_SERIF_B, anchor="mm")
    txt(d, (498, 980), "？", 90, RED, F_SERIF_B, anchor="mm")
    _PAPER_CACHE[key] = p
    return p


def shot_s1a(scene, t, shot):
    cam = Cam((0.95, 1.85, -3.05), (0.02, 0.52, 0.42), 42)
    scene.cam = cam
    scene.img = desk_base(cam, "cool")
    scr_c = np.array([0.92, 1.06, 1.95])
    scene.add(9.0, lambda img: _draw_screen(img, cam, paper_corners(scr_c, 1.5, 0.94, -16, 10), t))
    grow = clamp((t - 0.35) / 2.0)
    k = ease_in_out2(grow)
    center = (lerp(0.92, 0.0, k), lerp(1.02, 0.015, k), lerp(1.85, 0.60, k))
    scene.paper(tex_answer(), center, w=1.02, h=1.44, yaw=lerp(-16, -4, k), tilt=lerp(10, 76, k),
                shade=lerp(1.22, 0.99, k), shadow=0.5 * k)
    scene.flush()
    scene.img = add_light(scene.img, "screen", t, 1.0)
    return scene.img

_SCREEN = None


def screen_tex():
    global _SCREEN
    if _SCREEN is not None:
        return _SCREEN
    w, h = 640, 400
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((6, 6, w - 6, h - 6), radius=18, fill=(13, 19, 27, 252),
                        outline=(96, 148, 196, 230), width=3)
    d.rounded_rectangle((26, 24, 130, 46), radius=9, fill=(44, 62, 80, 255))
    d.rounded_rectangle((146, 24, 252, 46), radius=9, fill=(33, 46, 60, 255))
    for i in range(7):
        y = 92 + i * 38
        ww = 560 - (i % 3) * 86
        d.rounded_rectangle((40, y, 40 + ww, y + 14), radius=7, fill=(72, 112, 142, 218))
    d.rounded_rectangle((40, 92 + 7 * 38 + 16, 250, 92 + 7 * 38 + 60), radius=11,
                        fill=(58, 146, 214, 240))
    d.rectangle((534, 96, 540, 138), fill=(160, 222, 255, 255))
    gl = im.filter(ImageFilter.GaussianBlur(12))
    gl.putalpha(gl.getchannel("A").point(lambda v: int(v * 0.6)))
    out = Image.new("RGBA", (w + 44, h + 44), (0, 0, 0, 0))
    out.alpha_composite(gl, (22, 22))
    out.alpha_composite(im, (22, 22))
    _SCREEN = out
    return out


def _draw_screen(img, cam, corners, t):
    q = quad_layer(cam, corners, screen_tex(), alpha=1.0)
    if q is None:
        return
    lay, bx, by = q
    glow = lay.filter(ImageFilter.GaussianBlur(16))
    img.alpha_composite(glow, (bx, by))
    img.alpha_composite(lay, (bx, by))

def shot_s1b(scene, t, shot):
    dur = shot["dur"]
    cam = Cam(*CAM_DESK2)
    scene.cam = cam
    scene.img = desk_base(cam, "warm")
    push = smooth(clamp((t - 2.4) / 2.6)) * 0.05
    scene.paper(tex_first_judgment(), (-0.10, 0.006, 0.34), w=0.88, h=1.24, yaw=5, tilt=78,
                shade=0.78, shadow=0.5)
    scene.paper(tex_answer(), (0.06 - push, 0.022, 0.40 - push * 0.4), w=1.02, h=1.44,
                yaw=-6, tilt=80, shade=0.98, shadow=0.55)
    scene.flush()
    scene.img = add_light(scene.img, "desk_lamp", t, 0.9)
    return scene.img

def shot_s1c(scene, t, shot):
    dur = shot["dur"]
    cam = Cam(*CAM_DESK2)
    scene.cam = cam
    scene.img = desk_base(cam, "warm")
    note_c = (0.0, 0.006, 0.34)
    lift = ease_in_out2(clamp((t - 0.45) / 2.2))
    ans_c = (lerp(0.06, 1.55, lift), lerp(0.022, 0.32, lift), lerp(0.40, 0.82, lift))
    scene.paper(tex_first_judgment(), note_c, w=1.0, h=1.41, yaw=4, tilt=78, shade=0.94,
                shadow=0.5)
    if lift < 1.0:
        scene.paper(tex_answer(), ans_c, w=1.02, h=1.44, yaw=lerp(-6, 26, lift),
                    tilt=lerp(80, 44, lift), shade=1.0, shadow=0.28, alpha=1 - 0.78 * lift)
    if t > 2.55:
        scene.add(0.05, lambda img: _stamp_on_paper(
            img, cam, t, 2.55, note_c, 1.0, 1.41, 4, 78, label="欠",
            off=(0.13, 0.20), size=0.17, angle=-7))
    scene.flush()
    scene.img = add_light(scene.img, "red", t, 0.5)
    scene.img = add_light(scene.img, "desk_lamp", t, 0.6)
    return scene.img

def ease_in_out2(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


# ---------------- S2 账单与成本
def shot_s2a(scene, t, shot):
    cam = Cam(*CAM_PROPPED)
    scene.cam = cam
    scene.img = desk_base(cam, "cool")
    page = tex_cost_ledger(t)
    scene.paper(page, (0.0, 0.86, 0.30), w=1.06, h=1.5, yaw=0, tilt=18, shade=1.0, shadow=0.5)
    scene.flush()
    scene.img = add_light(scene.img, "screen", t, 0.9)
    return scene.img


def tex_cost_ledger(t):
    key = "cost_ledger_base"
    base = _PAPER_CACHE.get(key)
    if base is None:
        base = new_page("white")
        d = ImageDraw.Draw(base)
        txt(d, (72, 76), "两张账单", 62, PAPER_INK, F_SERIF_B)
        rule(d, 72, 172, 928, 172, (120, 108, 92), 2)
        txt(d, (110, 216), "生成", 40, INK_SOFT, F_SANS_B)
        txt(d, (560, 216), "核验", 40, INK_SOFT, F_SANS_B)
        rule(d, 490, 230, 490, 1240, (150, 144, 130), 2)
        _PAPER_CACHE[key] = base
    p = base.copy()
    d = ImageDraw.Draw(p)
    # 生成成本曲线：快速下降并贴地
    prog = clamp(t / 2.4)
    x0, y0 = 120, 1080
    pts = [(x0 + i * 3, y0 - 760 * math.exp(-(i / 38.0) * (1 + t * 0.25))) for i in range(0, int(112 * prog))]
    if len(pts) > 1:
        d.line(pts, fill=(78, 116, 148, 255), width=8)
    if prog >= 1:
        txt(d, (110, 1060), "成本 → 0", 38, (78, 116, 148), F_SANS_B)
    # 核验成本曲线：几乎水平
    prog2 = clamp((t - 0.5) / 2.4)
    x0, y0 = 540, 780
    pts2 = [(x0 + i * 3, y0 - 20 * math.sin(i / 40.0)) for i in range(0, int(112 * prog2))]
    if len(pts2) > 1:
        d.line(pts2, fill=RED + (255,), width=8)
    if prog2 >= 1:
        txt(d, (560, 650), "成本 ≠ 0", 38, RED, F_SANS_B)
    txt(d, (110, 300), "答案生产成本", 30, INK_SOFT)
    txt(d, (560, 300), "核验成本", 30, INK_SOFT)
    return p


def shot_s2b(scene, t, shot):
    cam = Cam((0.45, 2.45, -2.30), (0.0, 0.02, 0.42), 42)
    scene.cam = cam
    scene.img = desk_base(cam, "warm", lamp=0.9)
    for i in range(3):
        t0 = 0.35 + i * 0.85
        a = clamp((t - t0) / 0.45)
        if a <= 0:
            continue
        scene.paper(tex_old_step(i), (-0.34 + i * 0.05, 0.010 + i * 0.012, 0.40 + i * 0.05),
                    w=0.94, h=1.33, yaw=7 - i * 2, tilt=76, shade=0.9, shadow=0.45,
                    alpha=clamp(a * 1.5), zlift=(1 - ease_out(a)) * 0.25)
    scene.flush()
    scene.img = add_light(scene.img, "desk_lamp", t, 1.0)
    return scene.img

def tex_old_step(i):
    key = ("old_step", i)
    if key in _PAPER_CACHE:
        return _PAPER_CACHE[key]
    p = new_page("warm")
    d = ImageDraw.Draw(p)
    labels = [("查资料", "翻十几页，记下出处"), ("搭框架", "先列提纲，再改结构"), ("改几遍", "逐段重写，找人帮看")]
    h, sub = labels[i]
    txt(d, (90, 100), h, 64, PAPER_INK, F_SERIF_B)
    rule(d, 90, 200, 910, 200, (120, 108, 92), 2)
    txt(d, (90, 260), sub, 34, INK_SOFT)
    for k in range(6):
        rule(d, 90, 380 + k * 90, 910 - (k % 3) * 90, 380 + k * 90, (150, 144, 132), 6)
    txt(d, (90, 980), "一份方案 · 数小时", 32, INK_LIGHT)
    _PAPER_CACHE[key] = p
    return p


def shot_s2c(scene, t, shot):
    cam = Cam((0.62, 1.82, -2.95), (0.05, 0.26, 0.48), 42)
    scene.cam = cam
    scene.img = desk_base(cam, "cool")
    scr_c = np.array([0.62, 0.98, 1.72])
    scene.add(9.0, lambda img: _draw_screen(img, cam, paper_corners(scr_c, 1.15, 0.78, -15, 10), t))
    for i in range(3):
        t0 = 0.25 + i * 0.42
        a = clamp((t - t0) / 0.5)
        if a <= 0:
            continue
        k = ease_out(a)
        scene.paper(tex_answer(), (-0.45 + i * 0.46, 0.014 + 0.008 * i, 0.66), w=0.86, h=1.21,
                    yaw=-14 + i * 12, tilt=76, shade=1.0, shadow=0.45,
                    alpha=clamp(a * 1.2), zlift=(1 - k) * 0.5)
    scene.flush()
    scene.img = add_light(scene.img, "screen", t, 1.0)
    if t > 1.3:
        screen_text(scene.img, "一分钟，三个版本", 240, 46, WHITE, fnt=F_SERIF_B, glow=14,
                    t0=1.3, t=t, alpha=0.92)
    return scene.img

def shot_s2d(scene, t, shot):
    cam = Cam(*CAM_FLAT)
    scene.cam = cam
    scene.img = desk_base(cam, "cool")
    page = tex_bill_flat("gen")
    scene.paper(page, (0.0, 0.005, 0.42), w=1.18, h=1.67, yaw=2, tilt=84, shade=1.0, shadow=0.55)
    scene.flush()
    scene.img = add_light(scene.img, "screen", t, 0.9)
    if t > 0.75:
        scene.add(0.0, lambda img: _stamp_screen(img, t, 0.75, 640, 1090, "已结", 240, GOLD, 6))
        scene.flush()
    return scene.img


def _stamp_screen(img, t, t0, x, y, label, size, color, angle, alpha=0.9):
    prog = clamp((t - t0) / 0.25)
    if prog <= 0:
        return
    st = stamp_tex(label, color, circular=True, size=480).resize((size, size), Image.LANCZOS)
    st = st.rotate(angle, expand=True, resample=Image.BICUBIC)
    st = st.resize((int(size * (1.4 - 0.4 * ease_out(prog))), int(size * (1.4 - 0.4 * ease_out(prog)))), Image.LANCZOS)
    if prog < 1:
        st = st.copy()
        st.putalpha(st.getchannel("A").point(lambda q: int(q * prog * 1.3)))
    img.alpha_composite(st, (int(x - st.width / 2), int(y - st.height / 2)))


def tex_bill_flat(mode):
    key = ("bill_flat", mode)
    if key in _PAPER_CACHE:
        return _PAPER_CACHE[key]
    p = new_page("white" if mode == "verify" else "warm")
    d = ImageDraw.Draw(p)
    if mode == "gen":
        txt(d, (80, 70), "生成账单", 74, PAPER_INK, F_SERIF_B)
        txt(d, (80, 170), "答案生产 · 一次通过", 30, INK_SOFT)
        rule(d, 80, 226, 920, 226, (120, 108, 92), 3)
        txt(d, (80, 280), "项目", 30, INK_SOFT)
        txt(d, (700, 280), "费用", 30, INK_SOFT)
        rows = [("版式", "¥0.00"), ("文案", "¥0.00"), ("逻辑", "¥0.00"), ("风险提示", "¥0.00")]
        for i, (k, v) in enumerate(rows):
            y = 360 + i * 120
            txt(d, (80, y), k, 46, PAPER_INK)
            txt(d, (690, y), v, 46, INK_SOFT)
        rule(d, 80, 880, 920, 880, (120, 108, 92), 2)
        txt(d, (80, 950), "合计", 44, INK_SOFT)
        txt(d, (720, 930), "¥0.00", 74, PAPER_INK, F_SERIF_B)
        txt(d, (80, 1130), "生成用时 8 秒", 32, INK_SOFT)
        txt(d, (80, 1190), "人工复核：未做", 32, RED)
    else:
        txt(d, (80, 70), "核验账单", 74, PAPER_INK, F_SERIF_B)
        txt(d, (80, 170), "来源 · 事实 · 边界 · 反例", 30, INK_SOFT)
        rule(d, 80, 226, 920, 226, (120, 108, 92), 3)
        rows = ["来源能不能追到", "事实有没有出入", "边界说清了吗", "反例想过没有"]
        for i, k in enumerate(rows):
            y = 320 + i * 130
            d.rectangle((80, y, 136, y + 56), outline=RED + (255,), width=4)
            txt(d, (180, y - 6), k, 40, PAPER_INK)
            txt(d, (760, y - 6), "待核", 34, RED)
        rule(d, 80, 900, 920, 900, (120, 108, 92), 2)
        txt(d, (80, 980), "合计", 44, INK_SOFT)
        txt(d, (740, 960), "待结", 70, RED, F_SERIF_B)
        txt(d, (80, 1160), "需要时间、注意力与判断", 30, INK_SOFT)
    _PAPER_CACHE[key] = p
    return p


def shot_s2e(scene, t, shot):
    cam = Cam(*CAM_FLAT)
    scene.cam = cam
    scene.img = desk_base(cam, "cool")
    scene.paper(tex_bill_flat("verify"), (0.0, 0.005, 0.42), w=1.18, h=1.67, yaw=-2, tilt=84,
                shade=1.0, shadow=0.55)
    scene.flush()
    scene.img = add_light(scene.img, "screen", t, 0.85)
    # “待结”红圈
    return scene.img


def shot_s2f(scene, t, shot):
    dur = shot["dur"]
    cam = Cam(*CAM_LYING)
    scene.cam = cam
    scene.img = desk_base(cam, "warm", lamp=0.75)
    scene.paper(tex_answer(), (0.72, 0.018, 0.58), w=0.92, h=1.30, yaw=14, tilt=78,
                shade=0.94, shadow=0.4)
    # 台账页：把判断记到名下
    page = tex_account_ledger(t)
    scene.paper(page, (-0.18, 0.006, 0.36), w=1.04, h=1.47, yaw=-4, tilt=77, shade=1.0, shadow=0.55)
    scene.flush()
    scene.img = add_light(scene.img, "desk_lamp", t, 0.9)
    return scene.img


def tex_account_ledger(t):
    key = "account_ledger"
    base = _PAPER_CACHE.get(key)
    if base is None:
        base = new_page("warm")
        d = ImageDraw.Draw(base)
        txt(d, (76, 80), "判断力 · 台账", 58, PAPER_INK, F_SERIF_B)
        rule(d, 76, 176, 924, 176, (120, 108, 92), 2)
        txt(d, (90, 230), "日期", 28, INK_SOFT)
        txt(d, (330, 230), "摘要", 28, INK_SOFT)
        txt(d, (760, 230), "余额", 28, INK_SOFT)
        rule(d, 90, 280, 924, 280, (150, 144, 130), 2)
        rows = [("11-10", "直接采用 AI 方案", "-1"), ("11-10", "未核验即提交", "-1")]
        for i, (a, b, c) in enumerate(rows):
            y = 350 + i * 120
            txt(d, (90, y), a, 32, INK_SOFT)
            txt(d, (300, y), b, 36, PAPER_INK)
            txt(d, (790, y), c, 40, RED)
        rule(d, 90, 640, 924, 640, (150, 144, 130), 2)
        _PAPER_CACHE[key] = base
    p = base.copy()
    d = ImageDraw.Draw(p)
    a = clamp((t - 0.9) / 1.6)
    if a > 0:
        s = "记到：我自己名下"
        tex = text_tex(s, 52, RED, fnt=F_SERIF_B, pad=14)
        put(p, tex, 500, 830, alpha=a * 0.95)
        rule(d, 150, 900, 150 + 620 * ease_out(a), 900, RED, 4)
    if t > 2.6:
        txt(d, (300, 980), "余额：能力，不是答案", 34, INK_SOFT)
    return p


# ---------------- S3 研究
def shot_s3a(scene, t, shot):
    cam = Cam(*CAM_PROPPED)
    scene.cam = cam
    scene.img = desk_base(cam, "cool")
    a = ease_out((t - 0.2) / 0.9)
    scene.paper(tex_citation(), (0.0 + (1 - a) * 0.9, 0.72, 0.32), w=1.06, h=1.5,
                yaw=lerp(10, 2, a), tilt=lerp(18, 22, a), shade=1.0, shadow=0.5,
                alpha=clamp(a * 1.4))
    scene.flush()
    scene.img = add_light(scene.img, "screen", t, 0.85)
    return scene.img


def tex_citation():
    key = "citation"
    if key in _PAPER_CACHE:
        return _PAPER_CACHE[key]
    p = new_page("white")
    d = ImageDraw.Draw(p)
    txt(d, (80, 90), "这不是我的推测", 54, PAPER_INK, F_SERIF_B)
    rule(d, 80, 180, 920, 180, (120, 108, 92), 2)
    txt(d, (80, 240), "Lee, et al. · CHI 2025", 40, PAPER_INK, F_SANS_B)
    txt(d, (80, 300), "The Impact of Generative AI", 30, INK_SOFT)
    txt(d, (80, 344), "on Critical Thinking", 30, INK_SOFT)
    txt(d, (80, 420), "Microsoft Research × 卡内基梅隆大学", 32, INK_SOFT)
    rule(d, 80, 500, 920, 500, (150, 144, 130), 2)
    txt(d, (80, 550), "调研对象", 30, INK_SOFT)
    txt(d, (80, 610), "319 名知识工作者", 44, PAPER_INK, F_SANS_B)
    txt(d, (80, 690), "936 个真实 AI 使用案例", 44, PAPER_INK, F_SANS_B)
    txt(d, (80, 1000), "同行评审 · 会议论文", 30, INK_LIGHT)
    _PAPER_CACHE[key] = p
    return p


def shot_s3b(scene, t, shot):
    dur = shot["dur"]
    cam = Cam(*CAM_PROPPED)
    scene.cam = cam
    scene.img = desk_base(cam, "cool")
    page = tex_numbers(t)
    scene.paper(page, (0.0, 0.72, 0.32), w=1.06, h=1.5, yaw=0, tilt=22, shade=1.0, shadow=0.55)
    scene.flush()
    scene.img = add_light(scene.img, "screen", t, 0.9)
    if t > dur * 0.6:
        screen_text(scene.img, "相关，不是证明", 320, 44, (222, 220, 214), fnt=F_SANS, glow=10,
                    t0=dur * 0.6, t=t, alpha=0.9)
    return scene.img


def tex_numbers(t):
    key = "numbers"
    base = _PAPER_CACHE.get(key)
    if base is None:
        base = new_page("white")
        d = ImageDraw.Draw(base)
        txt(d, (76, 80), "他们发现", 52, PAPER_INK, F_SERIF_B)
        rule(d, 76, 168, 924, 168, (120, 108, 92), 2)
        txt(d, (90, 240), "319", 130, PAPER_INK, F_SERIF_B)
        txt(d, (90, 400), "名知识工作者", 34, INK_SOFT)
        txt(d, (520, 240), "936", 130, PAPER_INK, F_SERIF_B)
        txt(d, (520, 400), "个真实使用案例", 34, INK_SOFT)
        rule(d, 76, 520, 924, 520, (150, 144, 130), 2)
        _PAPER_CACHE[key] = base
    p = base.copy()
    d = ImageDraw.Draw(p)
    a = clamp((t - 1.2) / 2.0)
    if a > 0:
        put(p, text_tex("对 AI 越有信心", 40, PAPER_INK, F_SANS_B, pad=10), 90, 620, anchor="la", alpha=a)
        put(p, text_tex("→ 批判性思考越少", 40, RED, F_SANS_B, pad=10), 420, 620, anchor="la", alpha=a)
        put(p, text_tex("对自己能力越有信心", 40, PAPER_INK, F_SANS_B, pad=10), 90, 730, anchor="la", alpha=a)
        put(p, text_tex("→ 批判性思考越多", 40, (120, 150, 120), F_SANS_B, pad=10), 420, 730, anchor="la", alpha=a)
        txt(d, (90, 880), "（自报研究 · 相关关系）", 28, INK_LIGHT)
    return p


def shot_s3c(scene, t, shot):
    dur = shot["dur"]
    cam = Cam(*CAM_PROPPED)
    scene.cam = cam
    scene.img = desk_base(cam, "cool")
    scene.paper(tex_confidence(t), (0.0, 0.72, 0.32), w=1.06, h=1.5, yaw=0, tilt=22,
                shade=1.0, shadow=0.55)
    scene.flush()
    scene.img = add_light(scene.img, "screen", t, 0.9)
    return scene.img


def tex_confidence(t):
    key = "confidence"
    base = _PAPER_CACHE.get(key)
    if base is None:
        base = new_page("warm")
        d = ImageDraw.Draw(base)
        txt(d, (76, 76), "信心与批判性思考", 54, PAPER_INK, F_SERIF_B)
        rule(d, 76, 162, 924, 162, (120, 108, 92), 2)
        txt(d, (90, 220), "批判性思考", 28, INK_SOFT)
        txt(d, (90, 300), "多", 30, INK_SOFT)
        txt(d, (90, 1030), "少", 30, INK_SOFT)
        rule(d, 90, 1060, 900, 1060, (150, 144, 130), 2)
        txt(d, (420, 1090), "信心", 30, INK_SOFT)
        _PAPER_CACHE[key] = base
    p = base.copy()
    d = ImageDraw.Draw(p)
    # 两条线逐段画出
    prog = clamp((t - 0.5) / 4.0)
    # 下降线：对 AI 的信心
    if prog > 0:
        x0, y0 = 200, 360
        x1, y1 = 800, 960
        line_progress(d, x0, y0, x1, y1, prog, RED, 6)
    if prog >= 1:
        txt(d, (470, 250), "对 AI 的信心 ↑", 34, RED, F_SANS_B)
        txt(d, (600, 980), "批判性思考 ↓", 30, RED)
    prog2 = clamp((t - 2.2) / 4.0)
    if prog2 > 0:
        line_progress(d, 200, 960, 800, 420, prog2, (110, 142, 110), 6)
    if prog2 >= 1:
        txt(d, (470, 1080 - 40), "对自己能力的信心 ↑", 32, (110, 142, 110), F_SANS_B)
    txt(d, (90, 1180), "（自报研究 · 相关关系）", 26, INK_LIGHT)
    return p


def shot_s3d(scene, t, shot):
    dur = shot["dur"]
    cam = Cam(*CAM_PROPPED)
    scene.cam = cam
    scene.img = desk_base(cam, "deep")
    scene.paper(tex_mit(t), (0.0, 0.72, 0.32), w=1.06, h=1.5, yaw=0, tilt=22, shade=0.98,
                shadow=0.55)
    scene.flush()
    scene.img = add_light(scene.img, "screen", t, 1.0)
    return scene.img


def tex_mit(t):
    key = "mit"
    base = _PAPER_CACHE.get(key)
    if base is None:
        base = new_page("white")
        d = ImageDraw.Draw(base)
        txt(d, (76, 76), "另一项研究", 52, PAPER_INK, F_SERIF_B)
        rule(d, 76, 162, 924, 162, (120, 108, 92), 2)
        txt(d, (88, 220), "MIT Media Lab · 54 名参与者", 38, PAPER_INK, F_SANS_B)
        txt(d, (88, 285), "分组写论文", 30, INK_SOFT)
        # EEG 波形底
        txt(d, (88, 380), "大脑连接活动（EEG 初步结果）", 28, INK_SOFT)
        rule(d, 88, 450, 912, 450, (150, 144, 130), 2)
        txt(d, (88, 980), "作品记忆与归属感", 28, INK_SOFT)
        rule(d, 88, 1050, 912, 1050, (150, 144, 130), 2)
        _PAPER_CACHE[key] = base
    p = base.copy()
    d = ImageDraw.Draw(p)
    # EEG 波形振幅随时间衰减
    amp = lerp(34.0, 8.0, clamp(t / 6.0))
    phase = t * 9.0
    pts = []
    for i in range(0, 824, 3):
        x = 88 + i
        env = 0.45 + 0.55 * math.sin(i / 90.0 + t * 1.3) ** 2
        y = 700 - amp * env * math.sin(i / 9.0 + phase) - amp * 0.4 * math.sin(i / 3.1 - phase * 1.7)
        pts.append((x, y))
    if len(pts) > 1:
        d.line(pts, fill=(78, 104, 96) + (235,), width=3)
    # 预印本标签
    if t > 1.4:
        a = clamp((t - 1.4) / 0.6)
        put(p, text_tex("预印本 · 初步结果", 40, RED, F_SANS_B, pad=12, stroke=1), 88, 1100,
            anchor="la", alpha=a)
    if t > 2.6:
        txt(d, (88, 1180), "样本有限 · 尚未同行评审", 26, INK_SOFT)
    return p


def shot_s3e(scene, t, shot):
    dur = shot["dur"]
    cam = Cam(*CAM_PROPPED)
    scene.cam = cam
    scene.img = desk_base(cam, "deep")
    scene.paper(tex_boundary(t), (0.0, 0.72, 0.32), w=1.06, h=1.5, yaw=0, tilt=22,
                shade=0.96, shadow=0.55)
    scene.flush()
    scene.img = add_light(scene.img, "screen", t, 0.7)
    return scene.img


def tex_boundary(t):
    key = "boundary"
    base = _PAPER_CACHE.get(key)
    if base is None:
        base = new_page("warm")
        d = ImageDraw.Draw(base)
        txt(d, (76, 76), "它提醒我们", 52, PAPER_INK, F_SERIF_B)
        rule(d, 76, 162, 924, 162, (120, 108, 92), 2)
        txt(d, (88, 220), "这项研究规模有限，", 40, PAPER_INK)
        txt(d, (88, 285), "还没有同行评审，", 40, PAPER_INK)
        txt(d, (88, 350), "不能当成普遍结论。", 40, PAPER_INK)
        _PAPER_CACHE[key] = base
    p = base.copy()
    d = ImageDraw.Draw(p)
    labels = ["样本有限", "未同行评审", "不能外推"]
    for i, lab in enumerate(labels):
        a = clamp((t - 0.6 - i * 0.7) / 0.5)
        if a <= 0:
            continue
        y = 520 + i * 170
        box = Image.new("RGBA", (760, 120), (0, 0, 0, 0))
        bd = ImageDraw.Draw(box)
        bd.rounded_rectangle((2, 2, 758, 118), radius=10, outline=RED + (int(230 * a),), width=4)
        put(p, text_tex(lab, 46, RED, F_SANS_B, pad=10), 500, y + 60, anchor="mm", alpha=a)
        put(p, box, 500, y + 60, anchor="mm", alpha=a)
    return p


def shot_s3f(scene, t, shot):
    cam = Cam((0.92, 1.92, -3.05), (0.10, 0.38, 0.42), 42)
    scene.cam = cam
    scene.img = desk_base(cam, "warm", lamp=0.9)
    scene.paper(tex_answer(), (-0.30, 0.010, 0.52), w=0.98, h=1.38, yaw=6, tilt=78,
                shade=0.9, shadow=0.5)
    scene.flush()
    scene.img = add_light(scene.img, "desk_lamp", t, 0.9)
    if t > 0.8:
        a = clamp((t - 0.8) / 0.7)
        scene.img.alpha_composite(v_grad(0, int(110 * a)), (0, 0))
        screen_text(scene.img, "省下来的，", 300, 52, WHITE, fnt=F_SERIF_B, glow=14,
                    t0=0.8, t=t, alpha=0.92)
        screen_text(scene.img, "不一定都是体力", 372, 52, GOLD, fnt=F_SERIF_B, glow=16,
                    t0=1.35, t=t, x=W * 0.46, alpha=0.95)
    return scene.img

def shot_s4a(scene, t, shot):
    cam = Cam((0.10, 2.05, -3.0), (0.02, 0.18, 0.42), 42)
    scene.cam = cam
    scene.img = desk_base(cam, "cool")
    poses = [(-0.68, 9, 74), (0.0, -2, 70), (0.68, -13, 76)]
    for i, (x, yaw, tilt) in enumerate(poses):
        a = clamp((t - 0.2 - i * 0.25) / 0.5)
        if a <= 0:
            continue
        scene.paper(tex_debt_slip(i), (x, 0.010 + i * 0.008, 0.60 + i * 0.05), w=0.60, h=0.85,
                    yaw=yaw, tilt=tilt, shade=0.98, shadow=0.45, alpha=clamp(a * 1.4),
                    zlift=(1 - ease_out(a)) * 0.2)
    scene.flush()
    scene.img = add_light(scene.img, "screen", t, 0.85)
    if t > 1.2:
        screen_text(scene.img, "判断力债务，从三件事开始", 215, 42, (230, 228, 222),
                    fnt=F_SANS, glow=12, t0=1.2, t=t, alpha=0.9)
    return scene.img

def tex_debt_slip(i):
    key = ("debt_slip", i)
    if key in _PAPER_CACHE:
        return _PAPER_CACHE[key]
    p = new_page("white")
    d = ImageDraw.Draw(p)
    titles = [("一", "先问后想"), ("二", "先信后验"), ("三", "先用后学")]
    num, title = titles[i]
    txt(d, (80, 110), num, 90, RED, F_SERIF_B)
    txt(d, (220, 150), title, 50, PAPER_INK, F_SERIF_B)
    rule(d, 80, 300, 920, 300, (120, 108, 92), 3)
    subs = [["问题定义", "交给 AI", "解释框架", "跟着现成"], ["答案越完整", "越容易全信", "“没发现错误”", "≠ “没有错误”"],
            ["执行变熟练", "方法没积累", "会用了", "不会做了"]]
    for k, s in enumerate(subs[i]):
        txt(d, (90, 380 + k * 130), s, 44, PAPER_INK)
    txt(d, (90, 1000), "判断力债务", 40, RED, F_SERIF_B)
    txt(d, (90, 1080), "（本稿提出的分析框架）", 24, INK_LIGHT)
    _PAPER_CACHE[key] = p
    return p


def _propped(scene, tex, t, center=(0.0, 0.80, 0.32), w=1.06, h=1.5, tilt=20, yaw=0.0,
             shade=1.0, shadow=0.55):
    scene.paper(tex, center, w=w, h=h, yaw=yaw, tilt=tilt, shade=shade, shadow=shadow)


def shot_s4b(scene, t, shot):
    dur = shot["dur"]
    cam = Cam(*CAM_PROPPED)
    scene.cam = cam
    scene.img = desk_base(cam, "cool")
    _propped(scene, tex_ask_first(t), t, tilt=20)
    scene.flush()
    scene.img = add_light(scene.img, "screen", t, 0.95)
    return scene.img


def tex_ask_first(t):
    key = "ask_first"
    base = _PAPER_CACHE.get(key)
    if base is None:
        base = new_page("warm")
        d = ImageDraw.Draw(base)
        txt(d, (76, 76), "第一，先问后想", 56, PAPER_INK, F_SERIF_B)
        rule(d, 76, 166, 924, 166, (120, 108, 92), 2)
        txt(d, (90, 250), "连问题怎么定义，", 42, PAPER_INK)
        txt(d, (90, 320), "都让 AI 替你决定。", 42, PAPER_INK)
        rule(d, 90, 430, 910, 430, (150, 144, 130), 2)
        txt(d, (90, 480), "你的问题", 30, INK_SOFT)
        _PAPER_CACHE[key] = base
    p = base.copy()
    d = ImageDraw.Draw(p)
    txt(d, (90, 545), "我的问题：先问，这个方案替谁省事？", 34, PAPER_INK)
    a = clamp((t - 1.6) / 1.0)
    if a > 0:
        # AI 生成的解释框架覆盖到纸上
        lay = Image.new("RGBA", (820, 340), (0, 0, 0, 0))
        ld = ImageDraw.Draw(lay)
        ld.rounded_rectangle((2, 2, 818, 338), radius=8, fill=(238, 236, 230, 255),
                             outline=COOL_DIM + (230,), width=3)
        for k, s in enumerate(["问题定义：已由 AI 生成", "“核心诉求：提升效率”", "“隐含前提：越快越好”"]):
            put(lay, text_tex(s, 34, PAPER_INK, F_SANS_B, pad=6), 30, 44 + k * 90, anchor="la")
        put(p, lay, 500, 800, anchor="mm", alpha=a * 0.97)
    if t > 2.8:
        put(p, text_tex("解释框架，也一起给好了", 30, RED, F_SANS, pad=8), 90, 1030,
            anchor="la", alpha=clamp((t - 2.8) / 0.6))
    return p


def shot_s4c(scene, t, shot):
    dur = shot["dur"]
    cam = Cam(*CAM_PROPPED)
    scene.cam = cam
    scene.img = desk_base(cam, "cool")
    _propped(scene, tex_believe_first(t), t, tilt=20)
    scene.flush()
    scene.img = add_light(scene.img, "screen", t, 0.95)
    return scene.img


def tex_believe_first(t):
    key = "believe_first"
    base = _PAPER_CACHE.get(key)
    if base is None:
        base = new_page("warm")
        d = ImageDraw.Draw(base)
        txt(d, (76, 76), "第二，先信后验", 56, PAPER_INK, F_SERIF_B)
        rule(d, 76, 166, 924, 166, (120, 108, 92), 2)
        txt(d, (90, 240), "答案越完整，", 42, PAPER_INK)
        txt(d, (90, 310), "人越容易把「我没发现错误」，", 42, PAPER_INK)
        txt(d, (90, 380), "当成「它没有错误」。", 42, PAPER_INK)
        _PAPER_CACHE[key] = base
    p = base.copy()
    d = ImageDraw.Draw(p)
    # 自动打勾
    for i in range(5):
        a = clamp((t - 0.5 - i * 0.22) / 0.35)
        if a <= 0:
            continue
        y = 500 + i * 92
        put(p, text_tex("✓", 52, (110, 142, 110), F_SANS_B, pad=4), 100, y, anchor="la", alpha=a)
        put(p, text_tex("已通过", 30, (110, 142, 110), F_SANS, pad=4), 170, y + 12, anchor="la", alpha=a)
        txt(d, (300, y + 6), ["结构完整", "逻辑自洽", "语言通顺", "格式规范", "看起来对"][i], 34, PAPER_INK)
    a2 = clamp((t - 1.9) / 0.7)
    if a2 > 0:
        d.rectangle((90, 1000, 900, 1110), outline=RED + (int(240 * a2),), width=5)
        put(p, text_tex("核验：未做", 46, RED, F_SANS_B, pad=8), 495, 1055, anchor="mm", alpha=a2)
    return p


def shot_s4d(scene, t, shot):
    dur = shot["dur"]
    cam = Cam(*CAM_PROPPED)
    scene.cam = cam
    scene.img = desk_base(cam, "cool")
    _propped(scene, tex_use_first(t), t, tilt=20)
    scene.flush()
    scene.img = add_light(scene.img, "screen", t, 0.95)
    return scene.img


def tex_use_first(t):
    key = "use_first"
    base = _PAPER_CACHE.get(key)
    if base is None:
        base = new_page("warm")
        d = ImageDraw.Draw(base)
        txt(d, (76, 76), "第三，先用后学", 56, PAPER_INK, F_SERIF_B)
        rule(d, 76, 166, 924, 166, (120, 108, 92), 2)
        txt(d, (90, 240), "工作让 AI 做了，你越来越熟练；", 40, PAPER_INK)
        txt(d, (90, 310), "但解决问题的方法，", 40, PAPER_INK)
        txt(d, (90, 380), "并没有跟着积累。", 40, PAPER_INK)
        txt(d, (90, 560), "熟练度", 30, INK_SOFT)
        txt(d, (90, 900), "方法", 30, INK_SOFT)
        _PAPER_CACHE[key] = base
    p = base.copy()
    d = ImageDraw.Draw(p)
    prog = clamp((t - 0.6) / 2.6)
    if prog > 0:
        pts = [(180 + i * 2, 820 - 260 * (i / 680.0) ** 0.7) for i in range(int(340 * prog))]
        if len(pts) > 1:
            d.line(pts, fill=(110, 142, 110) + (245,), width=6)
    prog2 = clamp((t - 1.8) / 2.6)
    if prog2 > 0:
        d.line((180, 1000, 180 + 680 * prog2, 1000), fill=RED + (245,), width=6)
    if t > 3.0:
        put(p, text_tex("熟练 ↑", 34, (110, 142, 110), F_SANS_B, pad=6), 760, 700, anchor="la")
        put(p, text_tex("方法 →", 34, RED, F_SANS_B, pad=6), 760, 960, anchor="la")
    return p


def shot_s4e(scene, t, shot):
    dur = shot["dur"]
    cam = Cam(*CAM_PROPPED)
    scene.cam = cam
    scene.img = desk_base(cam, "cool")
    _propped(scene, tex_out_source(t), t, tilt=22)
    scene.flush()
    scene.img = add_light(scene.img, "screen", t, 0.9)
    return scene.img


def tex_out_source(t):
    key = "out_source"
    base = _PAPER_CACHE.get(key)
    if base is None:
        base = new_page("white")
        d = ImageDraw.Draw(base)
        txt(d, (76, 76), "可以外包的，和不能外包的", 48, PAPER_INK, F_SERIF_B)
        rule(d, 76, 160, 924, 160, (120, 108, 92), 2)
        rule(d, 500, 180, 500, 1300, (150, 144, 130), 2)
        txt(d, (90, 220), "外包", 36, (100, 130, 100), F_SANS_B)
        txt(d, (560, 220), "留给自己", 36, RED, F_SANS_B)
        for i, s in enumerate(["低风险", "能验证", "随时能撤", "错了代价小"]):
            txt(d, (90, 320 + i * 110), s, 38, PAPER_INK)
        for i, s in enumerate(["高风险", "难验证", "不可逆", "错了很难发现"]):
            txt(d, (560, 320 + i * 110), s, 38, PAPER_INK)
        _PAPER_CACHE[key] = base
    p = base.copy()
    d = ImageDraw.Draw(p)
    a = clamp((t - 1.2) / 0.8)
    if a > 0:
        stamp = stamp_tex("划算", GOLD, circular=True, size=480).resize((210, 210), Image.LANCZOS).rotate(8, expand=True)
        stamp.putalpha(stamp.getchannel("A").point(lambda v: int(v * a)))
        p.alpha_composite(stamp, (150, 820))
    a2 = clamp((t - 2.4) / 0.8)
    if a2 > 0:
        stamp = stamp_tex("危险", RED, circular=True, size=480).resize((210, 210), Image.LANCZOS).rotate(-7, expand=True)
        stamp.putalpha(stamp.getchannel("A").point(lambda v: int(v * a2)))
        p.alpha_composite(stamp, (620, 820))
    if t > 3.0:
        txt(d, (90, 1120), "判断，留在自己手里", 32, RED)
        txt(d, (560, 1120), "后果，由你承担", 32, RED)
    return p


def shot_s4f(scene, t, shot):
    dur = shot["dur"]
    cam = Cam(*CAM_PROPPED)
    scene.cam = cam
    scene.img = desk_base(cam, "deep")
    scene.paper(tex_high_risk(t), (0.0, 0.72, 0.32), w=1.06, h=1.5, yaw=0, tilt=22,
                shade=0.98, shadow=0.55)
    scene.flush()
    scene.img = add_light(scene.img, "red", t, 0.8)
    scene.img = add_light(scene.img, "screen", t, 0.4)
    return scene.img


def tex_high_risk(t):
    key = "high_risk"
    base = _PAPER_CACHE.get(key)
    if base is None:
        base = new_page("white")
        d = ImageDraw.Draw(base)
        txt(d, (76, 80), "真正危险的判断", 54, PAPER_INK, F_SERIF_B)
        rule(d, 76, 166, 924, 166, (120, 108, 92), 2)
        txt(d, (90, 280), "错了，很难发现。", 48, RED, F_SERIF_B)
        txt(d, (90, 400), "后果，却由你承担。", 48, PAPER_INK, F_SERIF_B)
        txt(d, (90, 600), "它不会被自动打勾，", 34, INK_SOFT)
        txt(d, (90, 660), "也不会出现在“已通过”里。", 34, INK_SOFT)
        _PAPER_CACHE[key] = base
    p = base.copy()
    d = ImageDraw.Draw(p)
    a = clamp((t - 1.4) / 0.8)
    if a > 0:
        st = stamp_tex("留给自己", RED, circular=True, size=480).resize((320, 320), Image.LANCZOS).rotate(-9, expand=True)
        st.putalpha(st.getchannel("A").point(lambda v: int(v * a * 0.92)))
        p.alpha_composite(st, (560, 790))
    return p


# ---------------- S5 历史
def shot_s5a(scene, t, shot):
    dur = shot["dur"]
    scene.cam = Cam((0, 1.2, -2.4), (0, 0.2, 0.4))
    backdrop_shot(scene, t, "calculator_01", zoom=(1.05, 1.12), darken=120, blur=2.0)
    # 老工具剪影快速蒙太奇
    scene.img = add_light(scene.img, "desk_lamp", t, 0.8)
    if t > 1.2:
        screen_text(scene.img, "每一种通用工具", 300, 46, (236, 232, 224), fnt=F_SERIF,
                    glow=14, t0=1.2, t=t, alpha=0.92)
        screen_text(scene.img, "都重新分配过人的劳动", 370, 46, (236, 232, 224), fnt=F_SERIF,
                    glow=14, t0=2.0, t=t, alpha=0.92)
    return scene.img


def _half_backdrop(name, side, t, darken=105, zoom=1.08):
    """取背景底片中央竖切（保持 9:16 比例），用于左右分屏。"""
    im = load_backdrop(name)
    z = lerp(1.02, zoom, clamp(t / 8.0))
    cw = int(im.width / z)
    ch = int(im.height / z)
    aspect = 450.0 / 1600.0
    cwid = int(ch * aspect)
    cx = int(im.width * (0.42 if side < 0 else 0.58) - cwid / 2)
    cy = (im.height - ch) // 2
    crop = im.crop((cx, cy, cx + cwid, cy + ch)).resize((450, H), Image.LANCZOS)
    arr = np.asarray(crop, dtype=np.float32) * (1.0 - darken / 255.0)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGBA")


def shot_s5b(scene, t, shot):
    dur = shot["dur"]
    scene.cam = Cam((0, 1.2, -2.4), (0, 0.2, 0.4))
    scene.img = Image.new("RGBA", (W, H), (5, 6, 9, 255))
    scene.img.alpha_composite(_half_backdrop("calculator_01", -1, t, darken=100), (0, 0))
    scene.img.alpha_composite(_half_backdrop("navigation_01", 1, t, darken=100), (450, 0))
    # 中缝与压暗，保证文字可读
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    od.rectangle((0, 0, W // 2, H), fill=(6, 8, 12, 46))
    od.rectangle((W // 2, 0, W, H), fill=(6, 8, 12, 52))
    od.line((W // 2, 120, W // 2, H - 360), fill=(150, 160, 170, 90), width=2)
    scene.img.alpha_composite(ov)
    scene.img = add_light(scene.img, "desk_lamp", t, 0.75)
    if t > 0.7:
        screen_text(scene.img, "计算器", 330, 44, COOL, fnt=F_SANS_B, glow=10, t0=0.7, t=t,
                    x=W * 0.25, alpha=0.95)
        screen_text(scene.img, "少做口算", 385, 34, (220, 218, 212), fnt=F_SANS, glow=8,
                    t0=1.1, t=t, x=W * 0.25, alpha=0.9)
    if t > 1.9:
        screen_text(scene.img, "导航", 330, 44, COOL, fnt=F_SANS_B, glow=10, t0=1.9, t=t,
                    x=W * 0.75, alpha=0.95)
        screen_text(scene.img, "不用记路", 385, 34, (220, 218, 212), fnt=F_SANS, glow=8,
                    t0=2.3, t=t, x=W * 0.75, alpha=0.9)
    return scene.img


def shot_s5c(scene, t, shot):
    dur = shot["dur"]
    cam = Cam(*CAM_PROPPED)
    scene.cam = cam
    scene.img = desk_base(cam, "cool")
    scene.paper(tex_exec_vs_judgment(t), (0.0, 0.015, 0.40), w=1.06, h=1.5, yaw=0, tilt=78,
                shade=0.96, shadow=0.5)
    scene.flush()
    scene.img = add_light(scene.img, "screen", t, 0.9)
    return scene.img


def tex_exec_vs_judgment(t):
    key = "exec_vs_judgment"
    base = _PAPER_CACHE.get(key)
    if base is None:
        base = new_page("warm")
        d = ImageDraw.Draw(base)
        txt(d, (76, 76), "执行与判断", 54, PAPER_INK, F_SERIF_B)
        rule(d, 76, 166, 924, 166, (120, 108, 92), 2)
        txt(d, (90, 280), "执行", 44, PAPER_INK, F_SANS_B)
        txt(d, (90, 420), "→ 交给工具", 40, INK_SOFT)
        txt(d, (90, 640), "判断", 44, RED, F_SANS_B)
        _PAPER_CACHE[key] = base
    p = base.copy()
    d = ImageDraw.Draw(p)
    txt(d, (350, 425), "计算器 · 导航 · AI", 34, INK_SOFT)
    a = clamp((t - 1.6) / 0.8)
    if a > 0:
        txt(d, (350, 650), "？", 70, RED, F_SERIF_B)
        put(p, text_tex("一起交出去了吗", 34, RED, F_SANS_B, pad=6), 90, 760, anchor="la", alpha=a)
    return p


def shot_s5d(scene, t, shot):
    dur = shot["dur"]
    cam = Cam(*CAM_LYING)
    scene.cam = cam
    scene.img = desk_base(cam, "warm", lamp=0.8)
    scene.paper(tex_process(t), (0.0, 0.72, 0.32), w=1.04, h=1.47, yaw=0, tilt=24,
                shade=1.0, shadow=0.5)
    scene.flush()
    scene.img = add_light(scene.img, "desk_lamp", t, 0.85)
    return scene.img


def tex_process(t):
    key = "process"
    base = _PAPER_CACHE.get(key)
    if base is None:
        base = new_page("warm")
        d = ImageDraw.Draw(base)
        txt(d, (76, 76), "判断力，长在过程里", 52, PAPER_INK, F_SERIF_B)
        rule(d, 76, 162, 924, 162, (120, 108, 92), 2)
        steps = [("查", "找出处"), ("核", "对事实"), ("改", "补边界")]
        for i, (a, b) in enumerate(steps):
            x = 150 + i * 280
            d.ellipse((x, 300, x + 150, 450), outline=PAPER_INK + (235,), width=4)
            txt(d, (x + 75, 375), a, 64, PAPER_INK, F_SERIF_B, anchor="mm")
            txt(d, (x + 75, 510), b, 30, INK_SOFT, anchor="mm")
        _PAPER_CACHE[key] = base
    p = base.copy()
    d = ImageDraw.Draw(p)
    prog = clamp((t - 0.4) / 2.2)
    if prog > 0:
        for i in range(2):
            x0 = 300 + i * 280
            x1 = x0 + 130
            line_progress(d, x0, 375, x1, 375, clamp(prog * 2 - i), PAPER_INK, 4)
    if t > 2.0:
        put(p, text_tex("结果很好，也别跳过过程", 32, RED, F_SANS, pad=8), 500, 700, anchor="mm",
            alpha=clamp((t - 2.0) / 0.7))
    return p


def shot_s5e(scene, t, shot):
    dur = shot["dur"]
    cam = Cam(*CAM_LYING)
    scene.cam = cam
    scene.img = desk_base(cam, "warm", lamp=0.75)
    scene.paper(tex_answer(), (0.0, 0.006, 0.42), w=1.2, h=1.7, yaw=0, tilt=85, shade=0.94,
                shadow=0.55)
    scene.flush()
    scene.img = add_light(scene.img, "desk_lamp", t, 0.85)
    # 放大镜扫过：显示“过程被跳过”
    if t > 0.6:
        a = clamp((t - 0.6) / 0.6)
        mx = lerp(W * 0.26, W * 0.74, smooth(clamp((t - 1.2) / 4.0)))
        my = H * 0.52 + 20 * math.sin(t * 0.9)
        d = ImageDraw.Draw(scene.img)
        r = 150
        glass = Image.new("RGBA", (2 * r, 2 * r), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glass)
        gd.ellipse((0, 0, 2 * r, 2 * r), fill=(255, 255, 255, 0))
        scene.img.alpha_composite(glass, (int(mx - r), int(my - r)))
        d.ellipse((mx - r, my - r, mx + r, my + r), outline=(196, 172, 124, int(230 * a)), width=5)
        d.ellipse((mx - r + 10, my - r + 10, mx + r - 10, my + r - 10),
                  fill=(220, 214, 198, 40))
        put(scene.img, text_tex("过程", 30, RED, F_SANS_B, pad=6), mx, my - 10, alpha=a * 0.9)
        put(scene.img, text_tex("跳过", 30, RED, F_SANS_B, pad=6), mx, my + 42, alpha=a * 0.9)
        # 手柄
        d.line((mx + r * 0.62, my + r * 0.62, mx + r * 1.15, my + r * 1.15),
               fill=(150, 122, 80, int(240 * a)), width=18)
    if t > 2.6:
        screen_text(scene.img, "它是怎么来的？", 320, 46, (232, 228, 220), fnt=F_SERIF_B,
                    glow=12, t0=2.6, t=t, alpha=0.92)
        screen_text(scene.img, "哪里可能不对？", 385, 46, (232, 228, 220), fnt=F_SERIF_B,
                    glow=12, t0=3.5, t=t, alpha=0.92)
    return scene.img


# ---------------- S6 方法
def shot_s6a(scene, t, shot):
    cam = Cam(*CAM_WRITE)
    scene.cam = cam
    scene.img = desk_base(cam, "warm", lamp=0.9)
    scene.paper(tex_three_questions(t), (0.0, 0.006, 0.40), w=1.2, h=1.7, yaw=0, tilt=84,
                shade=1.0, shadow=0.55)
    scene.flush()
    scene.img = add_light(scene.img, "desk_lamp", t, 0.95)
    return scene.img


def tex_three_questions(t):
    key = "three_questions"
    base = _PAPER_CACHE.get(key)
    if base is None:
        base = new_page("warm")
        d = ImageDraw.Draw(base)
        txt(d, (76, 80), "交出去之前，先问三句", 52, PAPER_INK, F_SERIF_B)
        rule(d, 76, 166, 924, 166, (120, 108, 92), 2)
        for i in range(3):
            y = 320 + i * 300
            txt(d, (90, y), ["①", "②", "③"][i], 64, RED, F_SERIF_B)
            rule(d, 180, y + 250, 910, y + 250, (150, 144, 130), 3)
        _PAPER_CACHE[key] = base
    return base.copy()


def _q_text(i):
    return ["错了，能不能及时发现？",
            "后果，最后由谁承担？",
            "工具突然不在了，我还剩下什么？"][i]


def _shot_question(scene, t, shot, idx):
    dur = shot["dur"]
    # 三问使用同一机位与同一张纸，保持连续
    cam = Cam(*CAM_WRITE)
    scene.cam = cam
    scene.img = desk_base(cam, "warm", lamp=0.9)
    page = tex_three_questions(t)
    p = page
    d = ImageDraw.Draw(p)
    y = 320 + idx * 300
    # 笔尖落纸：先画下划线，再让字迹浮现
    prog = clamp((t - 0.15) / 1.1)
    x0, x1 = 180, 900
    if prog > 0:
        line_progress(d, x0, y + 250, x1, y + 250, prog, PAPER_INK, 4)
    a = clamp((t - 0.5) / 1.1)
    if a > 0:
        put(p, text_tex(_q_text(idx), 40, PAPER_INK, F_SERIF_B, pad=10), 190, y + 40,
            anchor="la", alpha=a)
    scene.paper(p, (0.0, 0.006, 0.40), w=1.2, h=1.7, yaw=0, tilt=84, shade=1.0, shadow=0.55)
    scene.flush()
    scene.img = add_light(scene.img, "desk_lamp", t, 0.95)
    # 笔尖位置（屏幕坐标：纸面 0.5+局部）
    pts, _ = cam.project(paper_corners((0.0, 0.006, 0.40), 1.2, 1.7, 0, 84))
    u = pts[1] - pts[0]
    v = pts[3] - pts[0]
    if prog > 0 and prog < 1.06:
        fx = 180 + (900 - 180) * clamp(prog)
        fy = y + 250
        sx = pts[0][0] + u[0] * (fx / 1000.0) + v[0] * (fy / 1414.0)
        sy = pts[0][1] + u[1] * (fx / 1000.0) + v[1] * (fy / 1414.0)
        pen_nib(scene.img, sx, sy, angle=28, scale=1.0, alpha=0.9)
    return scene.img


def shot_s6b(scene, t, shot):
    return _shot_question(scene, t, shot, 0)


def shot_s6c(scene, t, shot):
    return _shot_question(scene, t, shot, 1)


def shot_s6d(scene, t, shot):
    return _shot_question(scene, t, shot, 2)


def shot_s6e(scene, t, shot):
    dur = shot["dur"]
    cam = Cam(*CAM_PROPPED)
    scene.cam = cam
    scene.img = desk_base(cam, "warm", lamp=0.8)
    scene.paper(tex_out_source(t), (0.0, 0.72, 0.32), w=1.06, h=1.5, yaw=0, tilt=22,
                shade=1.0, shadow=0.55)
    scene.flush()
    scene.img = add_light(scene.img, "desk_lamp", t, 0.9)
    return scene.img


def shot_s6f(scene, t, shot):
    dur = shot["dur"]
    cam = Cam(*CAM_PROPPED)
    scene.cam = cam
    scene.img = desk_base(cam, "cool")
    # 翻面：正面“答案”，背面“反例”
    flip = clamp((t - 0.9) / 1.6)
    yaw = 180 * ease_in_out2(flip) if flip > 0 else 0.0
    if flip < 0.5:
        tex = tex_flip_front()
        alpha = 1.0
        yaw_show = lerp(0, 88, flip * 2)
        center = (0.0, 0.80, 0.36)
    else:
        tex = tex_flip_back()
        alpha = 1.0
        yaw_show = lerp(-88, 0, (flip - 0.5) * 2)
        center = (0.0, 0.80, 0.36)
    if flip >= 0.98:
        yaw_show = 0.0
    if flip <= 0.02:
        yaw_show = 0.0
    shade = 0.55 + 0.45 * abs(math.cos(math.radians(yaw_show)))
    scene.paper(tex, center, w=1.06, h=1.5, yaw=yaw_show, tilt=16, shade=shade,
                shadow=0.5 * (1 - min(1, flip) * 0.4))
    scene.flush()
    scene.img = add_light(scene.img, "screen", t, 0.95)
    return scene.img


def tex_flip_front():
    key = "flip_front"
    if key in _PAPER_CACHE:
        return _PAPER_CACHE[key]
    p = new_page("warm")
    d = ImageDraw.Draw(p)
    txt(d, (76, 90), "答案", 96, PAPER_INK, F_SERIF_B)
    rule(d, 76, 230, 924, 230, (120, 108, 92), 3)
    txt(d, (90, 300), "结构完整 · 逻辑清晰 · 可直接使用", 34, INK_SOFT)
    for k in range(8):
        rule(d, 90, 420 + k * 80, 900 - (k % 4) * 70, 420 + k * 80, (150, 144, 132), 6)
    txt(d, (90, 1180), "（AI 生成）", 28, INK_LIGHT)
    _PAPER_CACHE[key] = p
    return p


def tex_flip_back():
    key = "flip_back"
    if key in _PAPER_CACHE:
        return _PAPER_CACHE[key]
    p = new_page("white")
    d = ImageDraw.Draw(p)
    txt(d, (76, 90), "反例", 96, RED, F_SERIF_B)
    rule(d, 76, 230, 924, 230, (120, 108, 92), 3)
    items = ["如果前提不成立呢？", "如果数据过时了呢？", "如果代价由你承担呢？", "换一种方案，会更好吗？"]
    for i, s in enumerate(items):
        put(p, text_tex(s, 40, PAPER_INK, F_SERIF_B, pad=8), 110, 330 + i * 150, anchor="la")
    txt(d, (90, 1050), "让 AI 来挑战你的回答", 34, RED, F_SANS_B)
    txt(d, (90, 1140), "而不是替你把问题关掉", 30, INK_SOFT)
    _PAPER_CACHE[key] = p
    return p


def shot_s6g(scene, t, shot):
    dur = shot["dur"]
    cam = Cam(*CAM_PROPPED)
    scene.cam = cam
    scene.img = desk_base(cam, "deep")
    scene.paper(tex_gold_lines(t), (0.0, 0.72, 0.32), w=1.06, h=1.5, yaw=0, tilt=22,
                shade=1.0, shadow=0.55)
    scene.flush()
    scene.img = add_light(scene.img, "desk_lamp", t, 0.9)
    return scene.img


def tex_gold_lines(t):
    key = "gold_lines"
    base = _PAPER_CACHE.get(key)
    if base is None:
        base = new_page("warm")
        d = ImageDraw.Draw(base)
        txt(d, (76, 80), "可以外包的，和不能外包的", 46, PAPER_INK, F_SERIF_B)
        rule(d, 76, 160, 924, 160, (120, 108, 92), 2)
        _PAPER_CACHE[key] = base
    p = base.copy()
    d = ImageDraw.Draw(p)
    a1 = clamp((t - 0.5) / 1.2)
    if a1 > 0:
        put(p, text_tex("可以外包执行，", 56, (150, 112, 48), F_SERIF_B, pad=12), 110, 340,
            anchor="la", alpha=a1)
        put(p, text_tex("不外包标准。", 56, RED, F_SERIF_B, pad=12), 110, 440, anchor="la", alpha=a1)
    a2 = clamp((t - 1.8) / 1.2)
    if a2 > 0:
        put(p, text_tex("可以外包劳动，", 56, (150, 112, 48), F_SERIF_B, pad=12), 110, 700,
            anchor="la", alpha=a2)
        put(p, text_tex("不外包责任。", 56, RED, F_SERIF_B, pad=12), 110, 800, anchor="la", alpha=a2)
    a3 = clamp((t - 3.2) / 0.9)
    if a3 > 0:
        st = stamp_tex("判断", RED, circular=False, size=480).resize((220, 220), Image.LANCZOS).rotate(-6, expand=True)
        st.putalpha(st.getchannel("A").point(lambda v: int(v * a3 * 0.9)))
        p.alpha_composite(st, (640, 1020))
    return p


def shot_s6h(scene, t, shot):
    dur = shot["dur"]
    cam = Cam((0.0, 2.55, -2.40), (0.0, 0.20, 0.32), 42)
    scene.cam = cam
    scene.img = desk_base(cam, "deep")
    scene.paper(tex_title_judgment(), (-0.20, 0.010, 0.70), w=0.82, h=1.15, yaw=7, tilt=74,
                shade=0.46, shadow=0.4)
    scene.flush()
    scene.img = add_light(scene.img, "red", t, 0.55)
    scene.img = add_light(scene.img, "desk_lamp", t, 0.35)
    a = clamp((t - 0.3) / 1.0)
    scene.img.alpha_composite(v_grad(0, int(140 * a)), (0, 0))
    screen_text(scene.img, "AI 时代，最贵的不是算力，", 380, 50, (238, 234, 226), fnt=F_SERIF_B,
                glow=16, t0=0.3, t=t, alpha=0.96)
    screen_text(scene.img, "是判断。", 468, 78, GOLD, fnt=F_SERIF_B, glow=22, t0=1.0, t=t,
                alpha=0.98)
    return scene.img


def tex_title_judgment():
    key = "title_judgment"
    if key in _PAPER_CACHE:
        return _PAPER_CACHE[key]
    p = new_page("white")
    d = ImageDraw.Draw(p)
    txt(d, (80, 300), "判断力", 120, PAPER_INK, F_SERIF_B)
    txt(d, (80, 470), "欠条", 120, RED, F_SERIF_B)
    rule(d, 80, 700, 920, 700, (120, 108, 92), 3)
    txt(d, (80, 780), "今欠：判断力一份", 44, PAPER_INK)
    txt(d, (80, 860), "归还日期：明天", 44, PAPER_INK)
    txt(d, (80, 1010), "（不是惩罚，是提醒）", 28, INK_LIGHT)
    _PAPER_CACHE[key] = p
    return p


def shot_s6i(scene, t, shot):
    dur = shot["dur"]
    cam = Cam((0.0, 2.20, -2.55), (0.0, 0.30, 0.30), 42)
    scene.cam = cam
    scene.img = desk_base(cam, "deep")
    scene.flush()
    scene.img = add_light(scene.img, "desk_lamp", t, 0.55)
    scene.img.alpha_composite(v_grad(60, 225))
    a = clamp((t - 0.2) / 0.8)
    screen_text(scene.img, "你最近一次把判断交给 AI，", 400, 46, (234, 230, 222), fnt=F_SERIF,
                glow=12, t0=0.2, t=t, alpha=0.95)
    screen_text(scene.img, "事后后悔了吗？", 474, 50, (234, 230, 222), fnt=F_SERIF,
                glow=14, t0=0.9, t=t, alpha=0.95)
    a2 = clamp((t - 1.8) / 0.7)
    if a2 > 0:
        put(scene.img, text_tex("评论区说说", 42, GOLD, fnt=F_SANS_B, glow=12, glow_color=GOLD),
            W / 2, 580, alpha=a2)
        put(scene.img, text_tex("AI 时代最贵的债，是判断力", 30, (198, 194, 186), fnt=F_SERIF, glow=6),
            W / 2, 1130, alpha=a2 * 0.9)
        put(scene.img, text_tex("画面与配音有 AI 参与；选题、核实和判断是人做的。", 22,
                                (152, 150, 144), fnt=F_SANS, pad=10), W / 2, 1182, alpha=a2 * 0.85)
        put(scene.img, text_tex("第 03 期 · 判断力债务", 26, (182, 178, 170), fnt=F_SANS, pad=10),
            W / 2, 1252, alpha=a2 * 0.8)
    return scene.img


# ================================================================ 调度
SHOT_FN = {
    "c0": shot_cold_open,
    "s1a": shot_s1a, "s1b": shot_s1b, "s1c": shot_s1c,
    "s2a": shot_s2a, "s2b": shot_s2b, "s2c": shot_s2c, "s2d": shot_s2d, "s2e": shot_s2e, "s2f": shot_s2f,
    "s3a": shot_s3a, "s3b": shot_s3b, "s3c": shot_s3c, "s3d": shot_s3d, "s3e": shot_s3e, "s3f": shot_s3f,
    "s4a": shot_s4a, "s4b": shot_s4b, "s4c": shot_s4c, "s4d": shot_s4d, "s4e": shot_s4e, "s4f": shot_s4f,
    "s5a": shot_s5a, "s5b": shot_s5b, "s5c": shot_s5c, "s5d": shot_s5d, "s5e": shot_s5e,
    "s6a": shot_s6a, "s6b": shot_s6b, "s6c": shot_s6c, "s6d": shot_s6d, "s6e": shot_s6e,
    "s6f": shot_s6f, "s6g": shot_s6g, "s6h": shot_s6h, "s6i": shot_s6i,
}

# 每镜的 2.5D 镜头运动：(起始缩放, 结束缩放, 起始平移x, 结束平移x, 起始平移y, 结束平移y)
# 缩放 ≥1（推近/微推），平移为画面宽高比例；运动方向对应叙事（靠近=看清、上移=抬头、退开=交出）。
SHOT_MOVE = {
    "c0": (1.00, 1.05, 0.0, 0.0, 0.0, -0.01),
    "s1a": (1.02, 1.055, 0.0, -0.01, 0.0, 0.0),
    "s1b": (1.01, 1.07, 0.0, 0.005, 0.0, 0.01),
    "s1c": (1.01, 1.06, 0.0, -0.01, 0.0, 0.0),
    "s2a": (1.00, 1.035, 0.0, 0.0, 0.0, 0.0),
    "s2b": (1.00, 1.04, 0.01, 0.0, 0.0, 0.0),
    "s2c": (1.02, 1.05, 0.0, 0.0, 0.0, 0.0),
    "s2d": (1.00, 1.045, 0.0, 0.0, 0.0, 0.0),
    "s2e": (1.00, 1.05, 0.0, 0.0, 0.0, 0.0),
    "s2f": (1.00, 1.04, 0.0, -0.01, 0.0, 0.0),
    "s3a": (1.02, 1.055, 0.0, 0.0, 0.0, 0.0),
    "s3b": (1.00, 1.03, 0.0, 0.0, 0.0, 0.0),
    "s3c": (1.00, 1.035, 0.0, 0.0, 0.0, 0.0),
    "s3d": (1.00, 1.03, 0.0, 0.0, 0.0, 0.0),
    "s3e": (1.02, 1.05, 0.0, 0.0, 0.0, 0.0),
    "s3f": (1.00, 1.04, 0.0, 0.0, 0.0, 0.0),
    "s4a": (1.03, 1.08, 0.0, 0.0, 0.0, 0.0),
    "s4b": (1.00, 1.04, 0.0, 0.0, 0.0, 0.0),
    "s4c": (1.00, 1.04, 0.0, 0.0, 0.0, 0.0),
    "s4d": (1.00, 1.04, 0.0, 0.0, 0.0, 0.0),
    "s4e": (1.01, 1.05, 0.0, 0.0, 0.0, 0.0),
    "s4f": (1.00, 1.05, 0.0, 0.0, 0.0, 0.0),
    "s5a": (1.04, 1.10, 0.0, -0.01, 0.0, 0.0),
    "s5b": (1.03, 1.08, 0.0, 0.0, 0.0, 0.0),
    "s5c": (1.01, 1.05, 0.0, 0.0, 0.0, 0.0),
    "s5d": (1.02, 1.06, 0.0, 0.0, 0.0, 0.0),
    "s5e": (1.00, 1.05, 0.0, 0.0, 0.0, 0.0),
    "s6a": (1.00, 1.03, 0.0, 0.0, 0.0, 0.0),
    "s6b": (1.01, 1.035, 0.0, 0.0, 0.0, 0.0),
    "s6c": (1.01, 1.035, 0.0, 0.0, 0.0, 0.0),
    "s6d": (1.01, 1.04, 0.0, 0.0, 0.0, 0.0),
    "s6e": (1.00, 1.04, 0.0, 0.0, 0.0, 0.0),
    "s6f": (1.02, 1.05, 0.0, 0.0, 0.0, 0.0),
    "s6g": (1.00, 1.05, 0.0, 0.0, 0.0, 0.0),
    "s6h": (1.02, 1.06, 0.0, 0.0, 0.0, 0.0),
    "s6i": (1.00, 1.03, 0.0, 0.0, 0.0, 0.0),
}

_FRAME_CACHE = {}


def apply_move(img, z0, z1, px0, px1, py0, py1, t, dur):
    u = smooth(clamp(t / max(0.2, dur)))
    z = lerp(z0, z1, u)
    px = lerp(px0, px1, u)
    py = lerp(py0, py1, u)
    if abs(z - 1.0) < 1e-4 and abs(px) < 1e-4 and abs(py) < 1e-4:
        return img
    z = max(1.0, z)
    cw, ch = W / z, H / z
    cx = (W - cw) / 2 + px * W
    cy = (H - ch) / 2 + py * H
    cx = clamp(cx, 0, W - cw)
    cy = clamp(cy, 0, H - ch)
    return img.crop((int(cx), int(cy), int(cx + cw), int(cy + ch))).resize((W, H), Image.BILINEAR)


def shot_for_time(t):
    """返回 (shot, t_in_shot)。"""
    lo, hi = 0, len(SHOTS) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if SHOTS[mid]["start"] <= t:
            lo = mid
        else:
            hi = mid - 1
    sh = SHOTS[lo]
    return sh, t - sh["start"]


def render_frame(t):
    sh, ts = shot_for_time(t)
    fn = SHOT_FN.get(sh["id"])
    if fn is None:
        raise SystemExit("未知分镜 " + sh["id"])
    _CUR_SHOT["id"] = sh["id"]
    scene = Scene(Cam((0, 2.0, -2.6), (0, 0.4, 0.3)), bg_gradient("cool"))
    img = fn(scene, ts, sh)
    mv = SHOT_MOVE.get(sh["id"], (1.0, 1.0, 0, 0, 0, 0))
    img = apply_move(img, mv[0], mv[1], mv[2], mv[3], mv[4], mv[5], ts, sh["dur"])
    fi = int(round(t * FPS))
    out = finish(img, seed=fi + sum(ord(c) for c in sh["id"]), bloom=0.24, grain=3.0, vignette=0.55)
    out = out.convert("RGBA")
    draw_caption(out, t)
    return out.convert("RGB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--still", default=None, help="分镜 id")
    ap.add_argument("--t", type=float, default=0.0, help="镜内秒数")
    ap.add_argument("--out", default="/tmp/still.png")
    ap.add_argument("--range", nargs=2, type=int, default=None, help="全局帧起止 [a,b)")
    ap.add_argument("--outdir", default=os.path.join(ROOT, "work", "frames"))
    ap.add_argument("--bench", default=None)
    ap.add_argument("--fps", type=int, default=FPS)
    args = ap.parse_args()

    if args.still:
        sh = SHOT_MAP[args.still]
        scene = Scene(Cam((0, 2.0, -2.6), (0, 0.4, 0.3)), bg_gradient("cool"))
        t0 = time.time()
        img = SHOT_FN[sh["id"]](scene, args.t, sh)
        img = finish(img, seed=3, bloom=0.24, grain=3.0, vignette=0.55).convert("RGBA")
        draw_caption(img, sh["start"] + args.t)
        img.convert("RGB").save(args.out)
        print("saved", args.out, f"{time.time()-t0:.2f}s")
        return
    if args.bench:
        sh = SHOT_MAP[args.bench]
        n = 8
        t0 = time.time()
        for i in range(n):
            scene = Scene(Cam((0, 2.0, -2.6), (0, 0.4, 0.3)), bg_gradient("cool"))
            img = SHOT_FN[sh["id"]](scene, i * 0.5, sh)
            img = finish(img, seed=i, bloom=0.24, grain=3.0, vignette=0.55).convert("RGBA")
            draw_caption(img, sh["start"] + i * 0.5)
        print(f"{args.bench}: {(time.time()-t0)/n*1000:.0f} ms/frame")
        return
    if args.range:
        a, b = args.range
        slot_fd, slot = acquire_render_slot()
        print("[render] 槽位 %d/%d（EP03_RENDER_JOBS），range=%d..%d" % (slot + 1, RENDER_JOBS, a, b), flush=True)
        os.makedirs(args.outdir, exist_ok=True)
        for fi in range(a, b):
            t = fi / FPS
            img = render_frame(t)
            img.save(os.path.join(args.outdir, "f%05d.jpg" % fi), quality=92)
            if fi % 100 == 0:
                print("frame", fi, flush=True)
        print("done", a, b, flush=True)
        return
    print("nothing to do; use --still/--range/--bench")


if __name__ == "__main__":
    main()
