#!/usr/bin/env python3
"""第 01 期《人生，也是一台混动车》渲染器：B-roll 背景 + 能量光带 + 混动 3D 剖面 + 逐句字幕。"""
import os, sys, json, math, random, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import engine3d as E

ROOT = os.path.dirname(os.path.abspath(__file__))
W, H, FPS = 900, 1600, 24
TL = json.load(open(os.path.join(ROOT, "work", "timeline.json"), encoding="utf-8"))
TOTAL = TL["total"]
SHOTS = TL["shots"]
SEGS = {s["id"]: s for s in TL["segments"]}

TEAL = (61, 245, 200)
LIME = (198, 255, 61)
WHITE = (240, 244, 248)
WARM = (246, 202, 140)
GREY = (150, 158, 165)
DARK = (8, 10, 12)
F_SANS = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
F_SANS_R = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
F_SERIF = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc"

def ft(path, size):
    return ImageFont.truetype(path, size)

_TEX = {}
def text_tex(text, size, color, font=F_SANS, glow=0, glow_color=None, glow_strength=0.8, stroke=0, stroke_color=(0, 0, 0)):
    key = (text, size, color, font, glow, glow_color, stroke, stroke_color)
    if key in _TEX:
        return _TEX[key]
    f = ft(font, size)
    tmp = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
    bb = tmp.textbbox((0, 0), text, font=f, stroke_width=stroke)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    pad = int(max(20, glow * 2 + stroke * 2 + 8))
    im = Image.new("RGBA", (tw + pad * 2, th + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if glow > 0:
        gl = Image.new("RGBA", im.size, (0, 0, 0, 0))
        gd = ImageDraw.Draw(gl)
        gd.text((pad - bb[0], pad - bb[1]), text, font=f, fill=(glow_color or color) + (255,),
                stroke_width=stroke, stroke_fill=stroke_color + (255,))
        gl = gl.filter(ImageFilter.GaussianBlur(glow))
        a = gl.getchannel("A").point(lambda v: int(v * glow_strength))
        gl.putalpha(a)
        im.alpha_composite(gl)
    d.text((pad - bb[0], pad - bb[1]), text, font=f, fill=color + (255,),
           stroke_width=stroke, stroke_fill=stroke_color + (255,))
    _TEX[key] = im
    return im


class R:
    def __init__(self):
        self.img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
        self.items = []
        self.cam = E.Camera((0, -2.8, 1.2), (0, 0, 0.25), fov_deg=38)

    def new(self, bg=None):
        if bg is None:
            self.img = dark_bg()
        else:
            self.img = bg.convert("RGBA")
        self.items = []

    def add(self, layer, bx, by, depth=0.0):
        self.items.append((depth, layer, bx, by))

    def put(self, tex, x, y, alpha=1.0, anchor="mm", depth=0.5):
        if alpha <= 0.005:
            return
        layer = tex if alpha >= 0.999 else _with_alpha(tex, alpha)
        if anchor == "mm":
            bx, by = int(x - layer.width / 2), int(y - layer.height / 2)
        elif anchor == "lm":
            bx, by = int(x), int(y - layer.height / 2)
        else:
            bx, by = int(x - layer.width / 2), int(y)
        self.add(layer, bx, by, depth)

    def flush(self):
        for depth, layer, bx, by in sorted(self.items, key=lambda it: -it[0]):
            self.img.alpha_composite(layer, (bx, by))
        return self.img


RND = R()


def _with_alpha(im, a):
    out = im.copy()
    al = out.getchannel("A").point(lambda v: int(v * a))
    out.putalpha(al)
    return out


def dark_bg(t=0.0, seed=3):
    yy = np.linspace(0, 1, H)[:, None]
    top = np.array([6, 8, 10], dtype=np.float32)
    bot = np.array([12, 20, 22], dtype=np.float32)
    arr = top[None, None, :] * (1 - yy[:, :, None]) + bot[None, None, :] * yy[:, :, None]
    arr = np.repeat(arr, W, axis=1)
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGBA")
    # teal radial glow
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    d.ellipse((W * 0.15, H * 0.28, W * 0.85, H * 0.72), fill=(24, 90, 80, 40))
    ov = ov.filter(ImageFilter.GaussianBlur(180))
    img.alpha_composite(ov)
    # particles
    rng = np.random.default_rng(seed)
    for i in range(90):
        x, y = rng.uniform(0, W), rng.uniform(0, H)
        a = int(rng.uniform(12, 60))
        r = rng.uniform(0.6, 2.0)
        dd = ImageDraw.Draw(img)
        dd.ellipse((x - r, y - r, x + r, y + r), fill=(120, 220, 200, a))
    return img


# ---------------------------------------------------------------- 2D 光带
def _bezier(pts, n=80):
    out = []
    m = len(pts) - 1
    dim = len(pts[0])
    for i in range(n):
        t = i / (n - 1)
        p = [[float(q[d]) for d in range(dim)] for q in pts]
        for k in range(1, m + 1):
            p = [[(1 - t) * p[j][d] + t * p[j + 1][d] for d in range(dim)] for j in range(len(p) - 1)]
        out.append(tuple(p[0]))
    return out


def band_2d(pts, width=10, color=TEAL, alpha=1.0, glow=22, dash=None, dash_phase=0.0, depth=1.0):
    path = _bezier(pts)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    if dash:
        seg = len(path) / dash
        for k in range(dash):
            i0 = int((k + dash_phase % 1) / dash * len(path))
            i1 = int((k + 0.55 + dash_phase % 1) / dash * len(path))
            i0 %= len(path); i1 %= len(path)
            if i0 < i1:
                d.line(path[i0:i1], fill=color + (int(255 * alpha),), width=width, joint="curve")
    else:
        d.line(path, fill=color + (int(255 * alpha),), width=width, joint="curve")
    gl = layer.filter(ImageFilter.GaussianBlur(glow))
    RND.add(gl, 0, 0, depth)
    RND.add(layer, 0, 0, depth - 0.001)


def hud_frame():
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    c = (120, 220, 200, 60)
    d.line([(60, 130), (60, 60), (200, 60)], fill=c, width=2)
    d.line([(W - 60, 130), (W - 60, 60), (W - 200, 60)], fill=c, width=2)
    d.line([(60, H - 300), (60, H - 240), (150, H - 240)], fill=c, width=2)
    d.line([(W - 60, H - 300), (W - 60, H - 240), (W - 150, H - 240)], fill=c, width=2)
    RND.add(layer, 0, 0, 0.2)


# ---------------------------------------------------------------- 字幕 / 花字
def _chunks(text, maxlen=14):
    parts = re.split(r"(?<=[。；！？，、：])", text)
    out = []
    for p in parts:
        p = p.strip()
        while len(p) > maxlen:
            out.append(p[:maxlen])
            p = p[maxlen:]
        if p:
            out.append(p)
    merged = []
    for p in out:
        if merged and len(merged[-1]) + len(p) <= maxlen:
            merged[-1] += p
        else:
            merged.append(p)
    return merged


CAPS = []
try:
    import subs as _subs
    _caps = _subs.build_caps(TL)
    CAPS = [(c["start"], c["end"], c["text"]) for c in _caps]
except Exception as _e:
    print("subs fallback:", _e)
    for sid, seg in SEGS.items():
        ch = _chunks(seg["text"])
        total = sum(len(c) for c in ch)
        t = seg["vo_start"]
        for c in ch:
            d = seg["vo_dur"] * len(c) / total
            CAPS.append((t, t + d, c))
            t += d


def caption(tg):
    for (a, b, txt) in CAPS:
        if a <= tg < b:
            fade = min(1.0, (tg - a) / 0.18) * min(1.0, (b - tg) / 0.12)
            tex = text_tex(txt, 30, WHITE, F_SANS, glow=6, glow_color=(0, 0, 0),
                           glow_strength=0.9, stroke=2, stroke_color=(0, 0, 0))
            RND.put(tex, W / 2, 1388, alpha=0.95 * fade, depth=0.05)
            return


def hua_fade(shot, tg, f0=0.12, f1=0.92):
    a = shot["start"] + shot["dur"] * f0
    b = shot["start"] + shot["dur"] * f1
    if tg < a or tg > b:
        return 0.0
    return min(1.0, (tg - a) / 0.35) * min(1.0, (b - tg) / 0.3)


def hua(text, y=330, size=48, color=LIME, glow=18, alpha=1.0, sub=None, sub_size=32):
    if alpha <= 0:
        return
    tex = text_tex(text, size, color, F_SANS, glow=glow, glow_color=color, glow_strength=0.75, stroke=2)
    RND.put(tex, W / 2, y, alpha=alpha, depth=0.03)
    if sub:
        st = text_tex(sub, sub_size, WHITE, F_SANS_R, glow=8, glow_color=(0, 0, 0), glow_strength=0.8)
        RND.put(st, W / 2, y + size * 0.85, alpha=alpha * 0.95, depth=0.03)


HUA = {
    2: ("值钱的不是发动机", "是能量管理"),
    5: ("白天 · 确定", "晚上 · 热爱"),
    10: ("每度电", "放在效率最高的地方"),
    14: ("AI 可以是副驾", "方向盘在你手里"),
    17: ("最容易被忽略的", "是回收"),
    19: ("没结果", "不等于白干"),
    20: ("那些力气", "都被存了起来"),
    24: ("不是满电", "是切换自如"),
}


def hua_shot(shot, tg):
    if shot["n"] not in HUA:
        return
    a = hua_fade(shot, tg)
    if a <= 0:
        return
    h1, h2 = HUA[shot["n"]]
    if shot["n"] == 5:
        # 分屏两侧标签
        t1 = text_tex(h1, 38, TEAL, F_SANS, glow=12, glow_color=TEAL, stroke=2)
        t2 = text_tex(h2, 38, WARM, F_SANS, glow=12, glow_color=WARM, stroke=2)
        RND.put(t1, W * 0.25, 250, alpha=a, depth=0.03)
        RND.put(t2, W * 0.75, 250, alpha=a, depth=0.03)
        return
    y = 300 if shot["kind"] not in ("city", "hud", "outro") else 380
    if shot["n"] == 10:
        y = 1180
    hua(h1, y=y, size=46, color=LIME, alpha=a)
    hua(h2, y=y + 70, size=56, color=TEAL, alpha=a)


# ---------------------------------------------------------------- 3D 混动剖面
NODES = {
    "engine":    ((-0.60, 0.02, -0.02), "发动机", (240, 176, 92)),
    "generator": ((-0.30, 0.02, 0.02), "发电机", (200, 190, 160)),
    "battery":   ((0.00, 0.02, 0.08), "电池", (90, 230, 200)),
    "motor":     ((0.30, 0.02, 0.02), "电机", (120, 196, 255)),
    "wheels":    ((0.60, 0.02, -0.06), "车轮", (220, 220, 220)),
}
PATHS = {
    "ev":     [("battery", "motor"), ("motor", "wheels")],
    "parallel": [("engine", "wheels"), ("battery", "motor"), ("motor", "wheels")],
    "series": [("engine", "generator"), ("generator", "battery"), ("battery", "motor"), ("motor", "wheels")],
    "regen":  [("wheels", "motor"), ("motor", "battery")],
}
MODE_ORDER = [("ev", "纯电模式", "安静 · 专注"), ("parallel", "并联模式", "人机一起出力"),
              ("series", "串联模式", "用不产出的事充电"), ("regen", "回收模式", "把动能存回电池")]


def _proj(cam, p):
    scr, zc = cam.project(np.asarray([p], dtype=np.float64))
    return scr[0], float(zc[0])


def line3d(cam, pts, color, width=4, alpha=0.9, glow=10, depth_bias=0.0):
    scr, zc = cam.project(np.asarray(pts, dtype=np.float64))
    if (zc <= 0.05).any():
        return
    xs, ys = scr[:, 0], scr[:, 1]
    pad = int(glow * 2 + width * 2 + 6)
    x0, y0 = int(xs.min()) - pad, int(ys.min()) - pad
    x1, y1 = int(xs.max()) + pad, int(ys.max()) + pad
    if x1 <= 0 or y1 <= 0 or x0 >= W or y0 >= H:
        return
    w, h = x1 - x0, y1 - y0
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.line([(p[0] - x0, p[1] - y0) for p in scr], fill=color + (int(255 * alpha),), width=width, joint="curve")
    if glow > 0:
        gl = layer.filter(ImageFilter.GaussianBlur(glow))
        RND.add(gl, x0, y0, float(zc.mean()) + depth_bias + 0.01)
    RND.add(layer, x0, y0, float(zc.mean()) + depth_bias)


def plate3d(cam, center, tex, w=0.34, h=0.26, depth_bias=0.0, alpha=1.0):
    c = np.asarray(center, dtype=np.float64)
    r, u = cam.right, cam.up
    q = [c - r * w / 2 + u * h / 2, c + r * w / 2 + u * h / 2, c + r * w / 2 - u * h / 2, c - r * w / 2 - u * h / 2]
    scr, zc = cam.project(np.asarray(q, dtype=np.float64))
    if (zc <= 0.05).any():
        return
    res = E.quad_texture(scr, _with_alpha(tex, alpha))
    if res is None:
        return
    layer, bx, by = res
    RND.add(layer, bx, by, float(zc.mean()) + depth_bias)


def diagram(tg, tl, shot):
    # 相机与背景
    ang = 0.18 * math.sin(tl * 0.22)
    cam = E.Camera((0.08 * math.sin(ang), -2.95, 0.88), (0.0, 0.0, 0.10), fov_deg=46)
    RND.new(dark_bg(tl, seed=7))
    hud_frame()
    # 网格
    for i in range(-6, 7):
        x = i * 0.22
        pts = [(x, -0.9, -0.05), (x, 0.9, -0.05)]
        line3d(cam, pts, (80, 160, 150), width=1, alpha=0.10, glow=0, depth_bias=-1.0)
        pts = [(-1.3, i * 0.15, -0.05), (1.3, i * 0.15, -0.05)]
        line3d(cam, pts, (80, 160, 150), width=1, alpha=0.10, glow=0, depth_bias=-1.0)
    # 模式
    if shot["kind"] == "diagram_intro":
        mode = "ev"
        label_a = min(1.0, tl / 1.6)
    else:
        k = int(((tg - shot["start"]) / max(0.1, shot["dur"])) * 4)
        k = min(3, max(0, k))
        mode = MODE_ORDER[k][0]
        label_a = 1.0
    active = set()
    for a, b in PATHS[mode]:
        active.add(a); active.add(b)
    # 连接线
    order = ["engine", "generator", "battery", "motor", "wheels"]
    for i in range(len(order) - 1):
        a, b = order[i], order[i + 1]
        pa, pb = NODES[a][0], NODES[b][0]
        mid = ((pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2, max(pa[2], pb[2]) + 0.16)
        pts = _bezier([pa, mid, pb], 40)
        on = (a, b) in PATHS[mode] or (b, a) in PATHS[mode]
        col = TEAL if on else (70, 92, 92)
        w = 6 if on else 2
        al = 0.95 if on else 0.25
        if (a, b) in PATHS[mode] or (b, a) in PATHS[mode]:
            # 反向能量流：regen 时从 wheels 到 battery
            if mode == "regen" and (a, b) == ("wheels", "motor"):
                pts = pts
            phase = (tl * 0.55) % 1
            line3d(cam, pts, LIME, width=w, alpha=al * 0.9, glow=12)
            # 流动光点
            for k2 in range(4):
                t = (k2 / 4 + phase) % 1
                idx = int(t * (len(pts) - 1))
                pp, zz = _proj(cam, pts[idx])
                dot = Image.new("RGBA", (18, 18), (0, 0, 0, 0))
                dd2 = ImageDraw.Draw(dot)
                dd2.ellipse((3, 3, 15, 15), fill=(225, 255, 230, 230))
                RND.put(dot, pp[0], pp[1], alpha=0.9, depth=0.3)
        else:
            line3d(cam, pts, (92, 128, 124), width=2, alpha=0.45, glow=4)
    # 节点
    for key, (pos, name, col) in NODES.items():
        active_node = key in active
        tex = node_tex(key, col, active_node)
        plate3d(cam, pos, tex, w=0.22, h=0.17, alpha=1.0)
        scr, zc = _proj(cam, pos)
        lt = text_tex(name, 26, col if active_node else (168, 176, 176), F_SANS,
                      glow=(10 if active_node else 0), glow_color=col, glow_strength=0.8,
                      stroke=2, stroke_color=(0, 0, 0))
        RND.put(lt, scr[0], scr[1] + 84, alpha=1.0, depth=0.015)
    # 模式标签
    lab, sub = None, None
    for m, l, s in MODE_ORDER:
        if m == mode:
            lab, sub = l, s
    if lab:
        t1 = text_tex(lab, 46, TEAL, F_SANS, glow=16, glow_color=TEAL, stroke=2)
        t2 = text_tex(sub, 28, WHITE, F_SANS_R, glow=6, glow_color=(0, 0, 0))
        RND.put(t1, W / 2, 300, alpha=label_a, depth=0.02)
        RND.put(t2, W / 2, 348, alpha=label_a * 0.9, depth=0.02)


GLYPH = {"engine": "机", "generator": "电", "battery": "池", "motor": "驱", "wheels": "轮"}
_NODE_TEX = {}
def node_tex(gkey, color, active):
    key = (gkey, color, active)
    if key in _NODE_TEX:
        return _NODE_TEX[key]
    w, h = 260, 190
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((6, 6, w - 6, h - 6), radius=22, fill=(8, 16, 18, 210),
                        outline=color + (255 if active else 70,), width=3 if active else 1)
    d.text((w / 2, h / 2 - 10), GLYPH.get(gkey, "机"), font=ft(F_SANS, 58), fill=color + (255 if active else 170,), anchor="mm")
    d.text((w / 2, h / 2 + 52), "●" if active else "○", font=ft(F_SANS, 34),
           fill=color + (255 if active else 90,), anchor="mm")
    _NODE_TEX[key] = im
    return im


# ---------------------------------------------------------------- HUD 小件
def battery_hud(x, y, level, color=TEAL, label="电池"):
    layer = Image.new("RGBA", (330, 120), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((0, 0, 260, 84), radius=10, outline=(180, 220, 215, 180), width=3)
    d.rounded_rectangle((262, 22, 276, 62), radius=4, fill=(180, 220, 215, 180))
    for i in range(8):
        if i < level:
            d.rounded_rectangle((14 + i * 30, 12, 38 + i * 30, 72), radius=4, fill=color + (220,))
    d.text((0, 96), label, font=ft(F_SANS_R, 24), fill=(210, 226, 226, 220))
    RND.add(layer, x, y, 0.25)


def fourgrid(tg, tl, shot, highlight=None):
    RND.new(dark_bg(tl, seed=11))
    hud_frame()
    labels = [("EV", "纯电"), ("P", "并联"), ("S", "串联"), ("R", "回收")]
    cx, cy = W / 2, H * 0.42
    step = int(((tg - shot["start"]) / max(0.1, shot["dur"])) * 5)
    lit = min(4, step + 1)
    for i, (ic, lb) in enumerate(labels):
        x = cx - 210 + i * 140
        on = i < lit
        hi = highlight == i
        w, h = 118, 160
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        col = LIME if hi else (TEAL if on else (70, 90, 90))
        d.rounded_rectangle((4, 4, w - 4, h - 4), radius=18, fill=(8, 16, 18, 220 if on else 140),
                            outline=col + (255 if on else 70,), width=3 if on else 1)
        d.text((w / 2, 54), ic, font=ft(F_SANS, 46), fill=col + (255 if on else 80,), anchor="mm")
        d.text((w / 2, 112), lb, font=ft(F_SANS, 30), fill=(235, 242, 244, 255 if on else 90), anchor="mm")
        RND.add(layer, int(x - w / 2), int(cy - h / 2), 0.4)
    t = text_tex("四种模式", 34, GREY, F_SANS, glow=6)
    RND.put(t, W / 2, cy - 150, depth=0.02)
    if highlight is not None:
        t2 = text_tex("回收：最容易被忽略的一格", 30, LIME, F_SANS, glow=12, glow_color=LIME)
        RND.put(t2, W / 2, cy + 150, depth=0.02)


# ---------------------------------------------------------------- 各镜头
def shot_overlays(shot, tg, tl):
    n = shot["n"]; kind = shot["kind"]
    hud_frame()
    if n in (1, 2):
        if n == 1:
            fade = min(1.0, tg / 1.2)
            RND.add(Image.new("RGBA", (W, H), (0, 0, 0, int(255 * (1 - fade)))), 0, 0, 5)
        band_2d([(80, H * 0.72), (W * 0.45, H * 0.66), (W - 80, H * 0.74)], width=5, color=TEAL, alpha=0.5, glow=18, dash=10, dash_phase=tg * 0.4)
    elif kind == "regen":
        lvl = min(8, int((tg - shot["start"]) / max(0.1, shot["dur"]) * 8) + 2)
        battery_hud(70, 1180, lvl, TEAL, "电池 · 回收中")
        band_2d([(W - 120, H * 0.78), (W * 0.55, H * 0.70), (120, H * 0.62)], width=8, color=LIME, alpha=0.85, glow=22, dash=12, dash_phase=-tg * 0.6)
        t = text_tex("能量回收 +1", 30, LIME, F_SANS, glow=14, glow_color=LIME)
        RND.put(t, W - 150, 1075, alpha=min(1, tl / 0.6), depth=0.02)
    elif kind == "desk":
        warm_glow()
    elif kind == "split":
        band_2d([(W / 2, 60), (W / 2, H - 60)], width=6, color=TEAL, alpha=0.85, glow=18, depth=0.6)
    elif kind == "montage":
        pass
    elif kind == "phone":
        pass
    elif kind == "pullout":
        pass
    elif kind in ("diagram_intro", "diagram_modes"):
        diagram(tg, tl, shot)
    elif kind == "write":
        pass
    elif kind == "fourgrid":
        fourgrid(tg, tl, shot)
    elif kind == "quiet":
        warm_glow(strength=0.5)
        t = text_tex("纯电模式 · 只做一件事", 30, TEAL, F_SANS, glow=12, glow_color=TEAL)
        RND.put(t, W / 2, 300, alpha=min(1, (tg - shot["start"]) / 1.2), depth=0.02)
    elif kind == "ai":
        warm_glow(strength=0.35)
        band_2d([(100, 980), (W * 0.5, 940), (W - 100, 1000)], width=6, color=WARM, alpha=0.7, glow=18, dash=10, dash_phase=tg * 0.35)
        band_2d([(100, 1060), (W * 0.5, 1020), (W - 100, 1080)], width=6, color=TEAL, alpha=0.8, glow=18, dash=10, dash_phase=tg * 0.45)
        t = text_tex("人 + 工具", 28, GREY, F_SANS_R, glow=6)
        RND.put(t, W / 2, 900, alpha=0.8, depth=0.02)
    elif kind == "warm":
        warm_glow(strength=0.6)
        t = text_tex("串联模式 · 用一件不产出的事，给自己充电", 28, WARM, F_SANS, glow=12, glow_color=WARM)
        RND.put(t, W / 2, 300, alpha=min(1, (tg - shot["start"]) / 1.2), depth=0.02)
    elif kind == "regen2":
        lvl = min(8, int((tg - shot["start"]) / max(0.1, shot["dur"]) * 8) + 2)
        battery_hud(70, 1180, lvl, LIME, "电池 · 回收中")
        band_2d([(W - 100, H * 0.80), (W * 0.5, H * 0.7), (140, H * 0.6)], width=9, color=LIME, alpha=0.9, glow=24, dash=14, dash_phase=-tg * 0.7)
    elif kind == "fourgrid2":
        fourgrid(tg, tl, shot, highlight=3)
    elif kind in ("paper", "paper2"):
        vignette_strong()
    elif kind == "rain":
        pass
    elif kind == "write2":
        pass
    elif kind == "city":
        band_2d([(80, H * 0.80), (W * 0.45, H * 0.74), (W - 80, H * 0.82)], width=7, color=TEAL, alpha=0.65, glow=22, dash=10, dash_phase=tg * 0.3)
    elif kind == "hud":
        battery_hud(70, 1150, 6, TEAL, "混动能量流")
        band_2d([(110, 1240), (W / 2, 1200), (W - 110, 1250)], width=7, color=TEAL, alpha=0.8, glow=20, dash=10, dash_phase=tg * 0.4)
    elif kind == "outro":
        warm_glow(strength=0.5)
        band_2d([(120, 1240), (W / 2, 1180), (W - 120, 1260)], width=6, color=TEAL, alpha=max(0.0, 1 - (tg - shot["start"]) / shot["dur"]), glow=20, dash=8, dash_phase=tg * 0.3)
    elif kind == "endcard":
        endcard(tg, shot)


def warm_glow(strength=0.7):
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    d.ellipse((W * 0.1, H * 0.18, W * 0.9, H * 0.75), fill=(255, 190, 120, int(60 * strength)))
    ov = ov.filter(ImageFilter.GaussianBlur(200))
    RND.img.alpha_composite(ov)


def vignette_strong():
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    d.ellipse((-W * 0.35, -H * 0.2, W * 1.35, H * 1.2), outline=(0, 0, 0, 0))
    ov = ov.filter(ImageFilter.GaussianBlur(150))
    RND.img.alpha_composite(ov)


def endcard(tg, shot):
    a = min(1.0, max(0.0, (tg - shot["start"]) / 1.0))
    RND.new(Image.new("RGBA", (W, H), (5, 6, 8, 255)))
    t1 = text_tex("人生，也是一台混动车", 72, (238, 242, 246), F_SERIF, glow=12, glow_color=(0, 0, 0), glow_strength=0.8)
    t2 = text_tex("从一台混动车，看人的能量管理", 30, GREY, F_SANS_R, glow=4, glow_color=(0, 0, 0))
    t3 = text_tex("本片含 AI 辅助制作 · 不出镜 / 不署名", 22, (110, 118, 124), F_SANS_R)
    RND.put(t1, W / 2, H * 0.40, alpha=a, depth=0.02)
    RND.put(t2, W / 2, H * 0.47, alpha=a * 0.9, depth=0.02)
    RND.put(t3, W / 2, H * 0.62, alpha=a * 0.8, depth=0.02)
    d = ImageDraw.Draw(RND.img)
    d.line([(W / 2 - 60, H * 0.435), (W / 2 + 60, H * 0.435)], fill=(61, 245, 200, int(200 * a)), width=2)


# ---------------------------------------------------------------- 帧合成
def shot_at(tg):
    for s in SHOTS:
        if s["start"] <= tg < s["end"] or (s is SHOTS[-1] and tg >= s["start"]):
            return s
    return SHOTS[-1]


_BGIDX = []
_c = 0
for _fi in range(int(round(TOTAL * FPS))):
    if shot_at(_fi / FPS)["type"] == "dark":
        _BGIDX.append(0)
    else:
        _c += 1
        _BGIDX.append(_c)


def load_bg(fi):
    idx = _BGIDX[fi] if fi < len(_BGIDX) else 0
    if idx == 0:
        return None
    p = os.path.join(ROOT, "work", "bg", f"f{idx:05d}.jpg")
    if os.path.exists(p):
        return Image.open(p).convert("RGB")
    return None


def render_frame(fi):
    tg = fi / FPS
    shot = shot_at(tg)
    tl = tg - shot["start"]
    bg = load_bg(fi) if shot["type"] != "dark" else None
    RND.new(bg)
    # 轻微暗角 / 电影遮幅感
    shot_overlays(shot, tg, tl)
    caption(tg)
    hua_shot(shot, tg)
    img = RND.flush()
    if shot["kind"] == "endcard":
        pass
    return E.Renderer().finish(img, bloom=0.42, grade=1.0, grain_amt=3.2, seed=fi, leak=0.05)


OUT = os.path.join(ROOT, "work", "frames")


def main(start, end):
    os.makedirs(OUT, exist_ok=True)
    for fi in range(start, end):
        p = os.path.join(OUT, f"f{fi:05d}.jpg")
        if os.path.exists(p) and os.path.getsize(p) > 1000:
            continue
        im = render_frame(fi)
        im.save(p, quality=89)
        if fi % 240 == 0:
            print("frame", fi, "/", end, flush=True)


if __name__ == "__main__":
    a = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    b = int(sys.argv[2]) if len(sys.argv) > 2 else int(TOTAL * FPS)
    main(a, b)
