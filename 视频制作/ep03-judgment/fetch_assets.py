#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第 03 期《AI 时代最贵的债，是判断力》素材抓取与背景底片生成
================================================================
阶段 1（stock）：Pexels API 搜索并下载 12-16 段 landscape B-roll → assets/stock/
阶段 2（backdrops）：从每段素材抽 7 帧，按清晰度/负空间评分选取 1-3 帧，
                     裁 9:16 → 2160x3840 电影感调色 → assets/backdrops/
                     同时输出 900x1600 预览 → assets/backdrops_preview/
阶段 3：写 assets/manifest.json（stock + backdrops 部分，textures 由 gen_textures.py 追加）

用法：
    source /app/vedio/china-aigc/keys.env
    python3 fetch_assets.py            # 全流程（已有文件自动跳过）
    python3 fetch_assets.py --force    # 强制重新下载/生成
    python3 fetch_assets.py --stage stock
    python3 fetch_assets.py --stage backdrops

依赖：ffmpeg/ffprobe（/home/admin/.local/bin），numpy，Pillow
"""
import os
import sys
import json
import math
import time
import hashlib
import subprocess
import argparse
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
from PIL import Image, ImageFilter

ROOT = "/app/vedio/ep03-judgment"
ASSETS = os.path.join(ROOT, "assets")
STOCK = os.path.join(ASSETS, "stock")
BACKDROPS = os.path.join(ASSETS, "backdrops")
PREVIEW = os.path.join(ASSETS, "backdrops_preview")
CACHE = "/tmp/ep03_assets_cache"
FRAMES = os.path.join(CACHE, "frames")
KEYS_ENV = "/app/vedio/china-aigc/keys.env"

FFMPEG = "/home/admin/.local/bin/ffmpeg"
FFPROBE = "/home/admin/.local/bin/ffprobe"

# 本机 6 GB cgroup：抽帧分析阶段每个线程都会拉起一个 ffmpeg，默认只允许 2 个并发。
# 2026-11-10 的 OOM 与此类并行峰值有关；可用 EP03_FFMPEG_JOBS 覆盖（1 为串行）。
FFMPEG_JOBS = max(1, int(os.environ.get("EP03_FFMPEG_JOBS", "2")))

KEY_NAMES = {
    "desk_night": "夜晚书桌",
    "laptop_night": "暗处笔记本冷光",
    "handwriting": "手写纸面",
    "pen_writing": "钢笔书写",
    "magnifier": "放大镜",
    "calculator": "计算器",
    "navigation": "手机导航",
    "city_night": "城市夜景",
    "old_books": "旧书档案",
    "paper_texture": "纸张质感",
    "signing": "签文件/盖章",
    "rain_window": "雨窗",
}

# 每个题材的英文搜索词（Pexels 以英文检索效果最好），命中即用，可多轮
THEME_QUERIES = {
    "desk_night": ["night desk lamp", "desk lamp dark room", "workspace night lamp"],
    "laptop_night": ["laptop screen dark room", "laptop glow night", "computer screen dark"],
    "handwriting": ["handwriting paper close up", "writing in notebook", "hand writing notes",
                    "writing notebook close up", "hand writing with pen", "calligraphy writing paper"],
    "pen_writing": ["fountain pen writing paper", "pen writing close up", "ink pen letter",
                    "fountain pen ink", "writing letter pen", "pen writing notebook close up"],
    "magnifier": ["magnifying glass document", "magnifying glass paper", "loupe documents"],
    "calculator": ["calculator close up", "calculator buttons", "accounting calculator desk"],
    "navigation": ["smartphone navigation map", "gps navigation phone", "car navigation screen"],
    "city_night": ["city night lights", "city skyline night", "night city street lights"],
    "old_books": ["old books library", "antique books archive", "vintage books shelf"],
    "paper_texture": ["paper texture close up", "stack of paper", "blank paper sheets"],
    "signing": ["signing document contract", "stamping document", "hand signing paper"],
    "rain_window": ["rain on window", "raindrops window glass night", "rain window night city"],
}

# 额外备选（若时间充裕且主题材不合适时使用）
EXTRA_THEMES = {}

# 人工精选素材（Pexels video id）：优先使用画质有保证的片段
CURATED = {
    "handwriting": [33350902, 6781562],   # 竖屏裁切用的手写特写（4K）
    "pen_writing": [7744350, 9388054],    # 钢笔书写特写（4K）
    "rain_window": [4065100, 3266040],
}

# 每个题材想要的股票素材数量 / 背景底片数量
STOCK_COUNT = {
    "desk_night": 2,
    "laptop_night": 2,
    "handwriting": 1,
    "pen_writing": 1,
    "magnifier": 1,
    "calculator": 1,
    "navigation": 1,
    "city_night": 1,
    "old_books": 1,
    "paper_texture": 1,
    "signing": 1,
    "rain_window": 1,
}
BACKDROP_COUNT = {
    "desk_night": 3,
    "laptop_night": 2,
    "handwriting": 2,
    "pen_writing": 2,
    "magnifier": 2,
    "calculator": 2,
    "navigation": 2,
    "city_night": 3,
    "old_books": 2,
    "paper_texture": 2,
    "signing": 2,
    "rain_window": 2,
}

# 题材 → 适合的镜头意图（写进 manifest，供 Lead 分镜取用）
USE_HINT = {
    "desk_night": "S1 夜晚书桌（开场/收束静坐）；也可做全片章节卡的暗底",
    "laptop_night": "S1/S2 屏幕冷光（答案生成、生成账单所依托的空间光）",
    "handwriting": "S2/S6 手写清单、三问便签；核验清单的书写动作",
    "pen_writing": "S4/S6 落笔、签字瞬间（关键判断落笔）",
    "magnifier": "S3 核验（放大镜靠近条款/来源）；S6 逐项核验",
    "calculator": "S2/S5 成本核算、生成账单旁的算账动作",
    "navigation": "S2 导航/方向感（判断被外包时的“跟着走”）",
    "city_night": "S5 历史纵深、城市夜间全景；情绪留白",
    "old_books": "S5 旧书/档案（历史参照、判断力谱系）",
    "paper_texture": "S2/S3 纸张特写（账单底、纸纤维质感）",
    "signing": "S6 核验盖章/签收（核验账单结清）",
    "rain_window": "S1/S4 情绪镜头（雨窗、思绪、迟疑）",
}

# ---------------------------------------------------------------- 基础工具


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def load_key():
    key = os.environ.get("PEXELS_API_KEY", "").strip()
    if key:
        return key
    if os.path.exists(KEYS_ENV):
        with open(KEYS_ENV, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("export PEXELS_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("找不到 PEXELS_API_KEY（先 source keys.env 或写进环境变量）")


def http_json(url, key, timeout=30):
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": key,
            "User-Agent": "ep03-asset-fetcher/1.0 (Pexels API)",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def run(cmd, timeout=600):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    return p.returncode, p.stdout.decode("utf-8", "ignore"), p.stderr.decode("utf-8", "ignore")


def ffprobe_meta(path):
    """本机没有独立 ffprobe（ffprobe 软链指向 ffmpeg），用 ffmpeg -i 解析元数据。"""
    import re
    rc, out, err = run([FFMPEG, "-hide_banner", "-i", path], timeout=60)
    text = err  # ffmpeg 把信息打到 stderr
    m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", text)
    if not m:
        raise RuntimeError(f"无法解析视频元数据: {path}\n{text[-400:]}")
    duration = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    vids = re.findall(r"Video:.*?(\d{2,5})x(\d{2,5})", text, re.S)
    if not vids:
        raise RuntimeError(f"无法解析视频分辨率: {path}\n{text[-400:]}")
    width, height = int(vids[0][0]), int(vids[0][1])
    mf = re.search(r",\s*([\d.]+)\s*fps", text)
    fps = mf.group(1) if mf else "0"
    return {
        "width": width,
        "height": height,
        "fps": fps,
        "duration": round(duration, 3),
        "size": os.path.getsize(path),
    }


def search_cache(theme, query, key):
    os.makedirs(CACHE, exist_ok=True)
    h = hashlib.md5(f"{query}|landscape".encode()).hexdigest()[:12]
    path = os.path.join(CACHE, f"search_{theme}_{h}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    url = (
        "https://api.pexels.com/videos/search?"
        + urllib.parse.urlencode(
            {"query": query, "orientation": "landscape", "size": "large", "per_page": 20}
        )
    )
    data = http_json(url, key)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return data


MAX_WIDTH = {"rain_window": 1920, "pen_writing": 3000}  # 源站 4K 慢，取 1080p/1440p


def pick_file(video, max_w=4096):
    """在 video_files 里挑质量与体积平衡最好的一档：优先 ≥1920 宽，同档取较小的。"""
    best = None
    for f in video.get("video_files", []):
        if f.get("file_type") != "video/mp4":
            continue
        w = f.get("width") or 0
        size = f.get("size") or 0
        if w < 1280 or w > max_w:
            continue
        if size > 250 * 1024 * 1024:  # 太大不下载
            continue
        pref = 0.0
        if w >= 1920:
            pref += 50.0
        if w >= 2560:
            pref += 20.0
        if w >= 3840:
            pref += 10.0
        score = pref + w * 0.01 - size / (1024 * 1024) * 0.01
        if best is None or score > best[0]:
            best = (score, f)
    return best[1] if best else None


def video_candidates(theme, key):
    seen = {}
    for q in THEME_QUERIES.get(theme, []):
        try:
            data = search_cache(theme, q, key)
        except Exception as e:
            log(f"  搜索失败 [{q}]：{e}")
            continue
        for v in data.get("videos", []):
            if v.get("width", 0) <= v.get("height", 0):
                continue
            if v.get("width", 0) < 1280:
                continue
            if not (4 <= v.get("duration", 0) <= 60):
                continue
            f = pick_file(v, MAX_WIDTH.get(theme, 3840))
            if not f:
                continue
            if v["id"] not in seen:
                seen[v["id"]] = (v, f, q, data.get("page", 1))
    out = []
    for vid, (v, f, q, page) in seen.items():
        has4k = any(x.get("width", 0) >= 3840 and (x.get("size") or 0) < 220 * 1024 * 1024
                    for x in v.get("video_files", []))
        has1080 = any(x.get("width", 0) >= 1920 for x in v.get("video_files", []))
        dur = v.get("duration", 0)
        score = 0.0
        if vid in CURATED.get(theme, []):
            score += 100.0 - CURATED.get(theme, []).index(vid) * 10.0
        score += 3.0 if has4k else 0.0
        score += 1.5 if has1080 else 0.0
        score += 1.0 if 8 <= dur <= 30 else 0.0
        score -= 0.4 if dur < 6 else 0.0
        out.append((score, v, f, q, page))
    out.sort(key=lambda x: -x[0])
    return out


def download(video, file_info, dest, timeout=300):
    tmp = dest + ".part"
    rc, out, err = run(
        ["/usr/bin/env", "curl", "-sSL", "--fail", "--retry", "2",
         "--max-time", str(timeout), "-o", tmp, file_info["link"]],
        timeout=timeout + 30,
    )
    if rc != 0 or not os.path.exists(tmp) or os.path.getsize(tmp) < 200 * 1024:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise RuntimeError(f"下载失败 rc={rc}: {err[-300:]}")
    os.replace(tmp, dest)
    return dest


# ---------------------------------------------------------------- 抽帧与评分


def extract_frames(video_path, n=7, tag="x"):
    """一次顺序解码，均匀抽 n 帧（全分辨率 JPEG，比多次 -ss 快 3-4 倍）。

    返回 (meta, [(t, path), ...])，t 为估算的时间点（fps 滤镜按均匀时间取帧）。
    """
    import glob
    meta = ffprobe_meta(video_path)
    dur = max(meta["duration"], 0.5)
    os.makedirs(FRAMES, exist_ok=True)
    # 有缓存则直接复用（同一片段重复跑时省时间）
    cached = sorted(glob.glob(os.path.join(FRAMES, f"{tag}_f*.jpg")))
    if len(cached) >= n:
        fps = (n + 0.55) / dur
        return meta, [((i + 0.5) / fps, path) for i, path in enumerate(cached[:n])]
    for f in cached + glob.glob(os.path.join(FRAMES, f"{tag}_f*.png")):
        try:
            os.remove(f)
        except OSError:
            pass
    fps = (n + 0.55) / dur  # 略多取，保证至少 n 帧
    pattern = os.path.join(FRAMES, f"{tag}_f%02d.jpg")
    rc, out, err = run(
        [FFMPEG, "-y", "-loglevel", "error", "-i", video_path,
         "-vf", f"fps={fps:.6f}", "-frames:v", str(n), "-q:v", "2", "-an", pattern],
        timeout=600,
    )
    files = sorted(glob.glob(os.path.join(FRAMES, f"{tag}_f*.jpg")))
    res = [((i + 0.5) / fps, path) for i, path in enumerate(files)]
    return meta, res


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0 + 1e-9), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def frame_score(png_path):
    """返回 (score, info)：清晰度高、上部够暗、下部有内容层次的帧得分高。"""
    im = Image.open(png_path).convert("RGB")
    small = im.resize((480, max(1, round(480 * im.height / im.width))), Image.BILINEAR)
    a = np.asarray(small, dtype=np.float32) / 255.0
    g = a @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    H, W = g.shape
    # 清晰度：拉普拉斯方差（边缘越多越清晰）
    k = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float32)
    lap = (
        g[:-2, 1:-1] * k[0, 1] + g[2:, 1:-1] * k[2, 1]
        + g[1:-1, :-2] * k[1, 0] + g[1:-1, 2:] * k[1, 2]
        + g[1:-1, 1:-1] * k[1, 1]
    )
    sharp = float(lap.var() * 1000.0)
    # 上部 42% 的亮度（越低越适合放字）与平坦度
    top = g[: int(H * 0.42), :]
    top_mean = float(top.mean())
    top_flat = float(top.std())
    # 中部/下部内容层次
    low = g[int(H * 0.40):, :]
    low_std = float(low.std())
    # 太暗或太亮都不好
    mean = float(g.mean())
    penalty = 0.0
    if mean < 0.045:
        penalty += 2.0
    if mean > 0.62:
        penalty += (mean - 0.62) * 4.0
    score = (
        min(sharp, 2.0) * 1.0
        + smoothstep(0.30, 0.02, top_mean) * 1.6
        + smoothstep(0.10, 0.005, top_flat) * 0.5
        + smoothstep(0.03, 0.22, low_std) * 0.9
        + smoothstep(0.02, 0.12, mean) * 0.4
        - penalty
    )
    return score, {"sharp": sharp, "top_mean": top_mean, "low_std": low_std, "mean": mean}


def crop_9x16(im, focus_frac=None):
    """从横屏帧裁 9:16 竖条；focus_frac 为兴趣点水平位置(0-1)，默认按边缘能量找。"""
    W, H = im.size
    cw = max(2, round(H * 9 / 16))
    if focus_frac is None:
        g = np.asarray(im.convert("L").resize((360, max(1, round(360 * H / W)))), dtype=np.float32)
        e = np.abs(np.diff(g, axis=1)).mean(axis=0)
        ker = np.ones(21) / 21.0
        e = np.convolve(np.pad(e, 10, mode="edge"), ker, mode="valid")
        focus_frac = float((e * np.linspace(0, 1, len(e))).sum() / (e.sum() + 1e-9))
    left = int(round(focus_frac * W - cw / 2))
    left = max(0, min(W - cw, left))
    return im.crop((left, 0, left + cw, H))


def grade_to_backdrop(im, seed=0):
    """电影感调色：压暗 / 去饱和 / 冷青阴影+暖高光分离 / 顶部负空间 / 暗角 / 轻虚化 / 颗粒。"""
    # 轻虚化（软焦点），让 4K 抽帧裁切后的数字感减弱
    blur = im.filter(ImageFilter.GaussianBlur(1.6))
    a = (np.asarray(im, dtype=np.float32) * 0.58 + np.asarray(blur, dtype=np.float32) * 0.42) / 255.0
    H, W = a.shape[:2]

    # 曝光 + 对比 S 曲线
    a = np.clip(a * 0.84, 0, 1) ** 1.04
    a = np.clip((a - 0.40) * 1.18 + 0.40, 0, 1)

    # 去饱和 26%，向亮度混合
    lum = (a @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32))[..., None]
    a = lum + (a - lum) * 0.74

    # 分离色调：阴影偏靛蓝/冷青，高光偏暖纸黄
    lum = (a @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32))[..., None]
    shadow = np.clip(1.0 - lum * 2.4, 0, 1)
    high = np.clip((lum - 0.30) * 1.7, 0, 1)
    a = a + shadow * np.array([0.008, 0.020, 0.046], dtype=np.float32)
    a = a + high * np.array([0.050, 0.022, -0.004], dtype=np.float32)

    # 顶部负空间渐变（0 顶 → 0.62 处恢复），保证上方压字可读
    yy = np.arange(H, dtype=np.float32) / max(1, H - 1)
    g = (0.50 + 0.50 * smoothstep(0.0, 0.62, yy))[:, None, None]
    a = a * g

    # 自适应：源片顶部本身很亮（纸面/雨窗等），再压一层，确保负空间够暗
    top_after = float(a[: int(H * 0.40)].mean())
    if top_after > 0.22:
        k = float(np.clip(0.22 / top_after, 0.55, 0.86))
        extra = 1.0 - (1.0 - k) * smoothstep(0.55, 0.0, yy)
        a = a * extra[:, None, None]

    # 底部也轻微压一点，避免字幕区太亮
    gb = (1.0 - 0.10 * smoothstep(0.80, 1.0, yy) ** 1.5)[:, None, None]
    a = a * gb

    # 暗角
    Y, X = np.mgrid[0:H, 0:W].astype(np.float32)
    cx, cy = (W - 1) / 2.0, (H - 1) / 2.0
    r = np.sqrt(((X - cx) / cx * 0.98) ** 2 + ((Y - cy) / cy * 0.72) ** 2)
    v = 1.0 - 0.40 * np.clip(r, 0, 1.25) ** 1.7
    a = a * v[..., None]

    # 胶片颗粒（低强度）+ 极轻微色噪
    rng = np.random.default_rng(seed)
    grain = rng.normal(0.0, 0.0105, (H, W, 1)).astype(np.float32)
    chroma = rng.normal(0.0, 0.0035, (H, W, 3)).astype(np.float32)
    a = a + grain + chroma

    a = np.clip(a, 0, 1)
    return Image.fromarray((a * 255.0 + 0.5).astype(np.uint8), "RGB")


# ---------------------------------------------------------------- 主流程


def stage_stock(force=False, themes=None):
    key = load_key()
    os.makedirs(STOCK, exist_ok=True)
    manifest_stock = []
    used_ids = set()
    # 复用旧 manifest 里的来源信息（重跑时不丢 Pexels 出处）
    old_by_file = {}
    mpath = os.path.join(ASSETS, "manifest.json")
    if os.path.exists(mpath):
        try:
            with open(mpath, "r", encoding="utf-8") as f:
                for e in json.load(f).get("stock", []):
                    old_by_file[e["file"].split("/")[-1]] = e
        except Exception:
            old_by_file = {}

    # 逐题材生成下载计划（顺序执行，便于去重；实际下载并行）
    plans = []
    todo = [t for t in STOCK_COUNT if not themes or t in themes]
    for theme in todo:
        want = STOCK_COUNT[theme]
        existing = sorted(
            f for f in os.listdir(STOCK)
            if f.startswith(theme + "_") and f.endswith(".mp4")
        ) if os.path.isdir(STOCK) else []
        if len(existing) >= want and not force:
            log(f"{theme}: 已存在 {len(existing)} 段，跳过")
            for f in existing:
                p = os.path.join(STOCK, f)
                meta = ffprobe_meta(p)
                old = old_by_file.get(f, {})
                manifest_stock.append({
                    "file": f"assets/stock/{f}", "theme": theme,
                    "theme_cn": KEY_NAMES.get(theme, theme),
                    "source": old.get("source"), "author": old.get("author"),
                    "author_url": old.get("author_url"), "pexels_id": old.get("pexels_id"),
                    "query": old.get("query"), "license": "Pexels License",
                    "width": meta["width"], "height": meta["height"],
                    "duration": meta["duration"], "fps": meta["fps"],
                    "filesize": meta["size"], "use_hint": USE_HINT.get(theme, ""),
                })
            continue
        cands = video_candidates(theme, key)
        if not cands:
            log(f"{theme}: !!! 没搜到候选素材")
            continue
        picked = []
        for score, v, f, q, page in cands:
            if v["id"] in used_ids:
                continue
            picked.append((score, v, f, q, page))
            if len(picked) >= want:
                break
        for score, v, f, q, page in picked:
            used_ids.add(v["id"])
            base = 0 if force else len(existing)
            idx = len([p for p in plans if p[0] == theme]) + base + 1
            fn = f"{theme}_{idx:02d}.mp4"
            dest = os.path.join(STOCK, fn)
            plans.append((theme, fn, dest, v, f, q, score))

    def do_download(plan):
        theme, fn, dest, v, f, q, score = plan
        if os.path.exists(dest) and not force and os.path.getsize(dest) > 200 * 1024:
            return ("skip", plan, None)
        try:
            download(v, f, dest)
            return ("ok", plan, None)
        except Exception as e:
            # 降级：换更小的分辨率再试（部分 4K 源站很慢/超时）
            alts = sorted(
                [x for x in v.get("video_files", [])
                 if x.get("file_type") == "video/mp4"
                 and 1280 <= (x.get("width") or 0) < (f.get("width") or 0)
                 and (x.get("size") or 0) < 220 * 1024 * 1024],
                key=lambda x: -(x.get("width") or 0),
            )
            for alt in alts:
                try:
                    download(v, alt, dest)
                    log(f"  ↺ {fn} 降级到 {alt.get('width')}x{alt.get('height')}")
                    return ("ok", plan, None)
                except Exception:
                    continue
            return ("err", plan, str(e))

    log(f"开始并行下载 {len(plans)} 段 …")
    results = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(do_download, p) for p in plans]
        for fut in as_completed(futs):
            st, plan, err = fut.result()
            theme, fn = plan[0], plan[1]
            if st == "err":
                log(f"  ✗ {fn}: {err}")
            else:
                log(f"  {'=' if st == 'skip' else '↓'} {fn}")
            results.append((st, plan, err))

    # 汇总 manifest（重新 ffprobe 全部 stock）
    manifest_stock = []
    by_name = {}
    for st, plan, err in results:
        theme, fn, dest, v, f, q, score = plan
        by_name[fn] = (v, f, q, st)
    for fn in sorted(os.listdir(STOCK)):
        if not fn.endswith(".mp4"):
            continue
        theme = fn.rsplit("_", 1)[0]
        p = os.path.join(STOCK, fn)
        try:
            meta = ffprobe_meta(p)
        except Exception as e:
            log(f"跳过损坏文件 {fn}: {e}")
            continue
        v, f, q, st = by_name.get(fn, (None, None, None, None))
        old = old_by_file.get(fn, {})
        entry = {
            "file": f"assets/stock/{fn}",
            "theme": theme,
            "theme_cn": KEY_NAMES.get(theme, theme),
            "source": (v or {}).get("url") or old.get("source"),
            "pexels_id": (v or {}).get("id") or old.get("pexels_id"),
            "author": ((v or {}).get("user") or {}).get("name") or old.get("author"),
            "author_url": ((v or {}).get("user") or {}).get("url") or old.get("author_url"),
            "query": q or old.get("query"),
            "license": "Pexels License",
            "width": meta["width"],
            "height": meta["height"],
            "duration": meta["duration"],
            "fps": meta["fps"],
            "filesize": meta["size"],
            "use_hint": USE_HINT.get(theme, ""),
        }
        manifest_stock.append(entry)
    log(f"stock 完成：{len(manifest_stock)} 段")
    return manifest_stock


def stage_backdrops(force=False):
    os.makedirs(BACKDROPS, exist_ok=True)
    os.makedirs(PREVIEW, exist_ok=True)
    stock_files = sorted(f for f in os.listdir(STOCK) if f.endswith(".mp4"))
    if not stock_files:
        raise SystemExit("assets/stock 为空，先跑 --stage stock")

    # 计划：对每个题材的每段素材抽帧 → 全局按题材配额分配
    tasks = []
    for fn in stock_files:
        theme = fn.rsplit("_", 1)[0]
        tasks.append((theme, fn))

    def analyze(task):
        theme, fn = task
        path = os.path.join(STOCK, fn)
        try:
            meta, frames = extract_frames(path, n=7, tag=fn[:-4])
        except Exception as e:
            return (task, None, str(e))
        scored = []
        for t, fp in frames:
            try:
                s, info = frame_score(fp)
            except Exception:
                continue
            scored.append((s, t, fp, info))
        scored.sort(key=lambda x: -x[0])
        return (task, (meta, scored), None)

    log(f"抽帧分析 {len(tasks)} 段素材（每段 7 帧，ffmpeg 并发上限 {FFMPEG_JOBS}）…")
    analyzed = []
    with ThreadPoolExecutor(max_workers=FFMPEG_JOBS) as ex:
        for r in ex.map(analyze, tasks):
            task, data, err = r
            if err:
                log(f"  ✗ {task[1]}: {err}")
                continue
            analyzed.append((task, data))
            top = data[1][0][0] if data[1] else float("nan")
            log(f"  ✓ {task[1]} 帧数={len(data[1])} 最佳分={top:.2f}")
    if not analyzed:
        raise SystemExit("没有任何素材可用于生成背景底片")

    # 每个题材按配额从该题材所有素材的帧里挑（每段素材最多取 2 帧）
    by_theme = {}
    for (theme, fn), (meta, scored) in analyzed:
        by_theme.setdefault(theme, []).append((fn, meta, scored))

    backdrop_meta = []
    for theme in sorted(by_theme):
        quota = BACKDROP_COUNT.get(theme, 2)
        pool = []
        for fn, meta, scored in by_theme[theme]:
            for s, t, fp, info in scored[:3]:
                pool.append((s, t, fp, info, fn, meta))
        pool.sort(key=lambda x: -x[0])
        chosen = []
        used_src = {}
        for item in pool:
            if len(chosen) >= quota:
                break
            src = item[4]
            if used_src.get(src, 0) >= 2:  # 同一段素材最多出 2 张，避免重复感
                continue
            chosen.append(item)
            used_src[src] = used_src.get(src, 0) + 1
        for i, (s, t, fp, info, fn, meta) in enumerate(chosen, 1):
            name = f"{theme}_{i:02d}"
            out = os.path.join(BACKDROPS, name + ".jpg")
            prev = os.path.join(PREVIEW, name + ".jpg")
            if os.path.exists(out) and not force:
                log(f"  = {name}.jpg 已存在")
            else:
                im = Image.open(fp).convert("RGB")
                im = crop_9x16(im)
                im = im.resize((2160, 3840), Image.LANCZOS)
                im = grade_to_backdrop(im, seed=abs(hash(name)) % (2 ** 32))
                im.save(out, quality=92, subsampling=1, optimize=True)
                im.resize((900, 1600), Image.LANCZOS).save(prev, quality=86, optimize=True)
                log(f"  ✓ {name}.jpg  (源 {fn} t={t:.1f}s score={s:.2f} 顶亮={info['top_mean']:.3f})")
            backdrop_meta.append({
                "file": f"assets/backdrops/{name}.jpg",
                "preview": f"assets/backdrops_preview/{name}.jpg",
                "theme": theme,
                "theme_cn": KEY_NAMES.get(theme, theme),
                "source_stock": f"assets/stock/{fn}",
                "frame_time": round(t, 2),
                "width": 2160,
                "height": 3840,
                "grade": "压暗/去饱和26%/阴影偏靛蓝冷青+高光暖纸黄/顶部负空间渐变/暗角/软焦点/胶片颗粒",
                "use_hint": USE_HINT.get(theme, ""),
            })
    log(f"backdrops 完成：{len(backdrop_meta)} 张")
    return backdrop_meta


def write_manifest(stock, backdrops):
    path = os.path.join(ASSETS, "manifest.json")
    old = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                old = json.load(f)
        except Exception:
            old = {}
    m = {
        "episode": "第 03 期《AI 时代最贵的债，是判断力》",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "canvas": {
            "film": "1080x1920 @ 24fps",
            "backdrop": "2160x3840 (9:16)",
            "preview": "900x1600",
        },
        "visual_direction": (
            "竖屏暗调：靛蓝/冷青灰屏幕光 × 暖纸黄（纸张/台灯），朱红只用于印章；"
            "整体低饱和、胶片颗粒；背景底片上方/中部留低对比负空间供压字；一屏一个第一视觉重点。"
        ),
        "stock": stock,
        "backdrops": backdrops,
        "textures": old.get("textures", []),
        "contact_sheet": old.get("contact_sheet"),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False, indent=2)
    log(f"manifest 写入：{path}（stock {len(stock)} / backdrops {len(backdrops)}）")


def backfill_stock_sources():
    """从缓存的 Pexels 搜索结果回填 stock 的来源 URL / 作者 / 关键词。

    依据：同名缓存 search_{theme}_{md5(query)}.json + 已下载文件的分辨率/时长匹配。
    用于中途重启或分多次下载后，保证 manifest 中每段素材都可溯源。
    """
    man_path = os.path.join(ASSETS, "manifest.json")
    if not os.path.exists(man_path):
        raise SystemExit("manifest.json 不存在")
    with open(man_path, "r", encoding="utf-8") as f:
        m = json.load(f)

    # theme -> [(query, video)]
    pool = {}
    for theme, queries in THEME_QUERIES.items():
        for q in queries:
            h = hashlib.md5(f"{q}|landscape".encode()).hexdigest()[:12]
            cp = os.path.join(CACHE, f"search_{theme}_{h}.json")
            if not os.path.exists(cp):
                continue
            try:
                with open(cp, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue
            for v in data.get("videos", []):
                pool.setdefault(theme, []).append((q, v))

    fixed = 0
    for e in m.get("stock", []):
        path = os.path.join(ROOT, e["file"])
        if not os.path.exists(path):
            continue
        meta = ffprobe_meta(path)
        cands = []
        for q, v in pool.get(e.get("theme"), []):
            dt = abs(float(v.get("duration", 0)) - meta["duration"])
            if dt > 1.5:
                continue
            res_ok = any(
                abs((vf.get("width") or 0) - meta["width"]) <= 2
                and abs((vf.get("height") or 0) - meta["height"]) <= 2
                for vf in v.get("video_files", [])
            )
            if not res_ok:
                continue
            cands.append((dt, v, q))
        if not cands:
            log(f"  ! 无匹配来源：{e['file']} ({meta['width']}x{meta['height']} {meta['duration']}s)")
            continue
        cands.sort(key=lambda x: x[0])
        dt, v, q = cands[0]
        e["source"] = v.get("url")
        e["pexels_id"] = v.get("id")
        e["author"] = (v.get("user") or {}).get("name")
        e["author_url"] = (v.get("user") or {}).get("url")
        e["query"] = q
        e["license"] = "Pexels License"
        e["width"], e["height"] = meta["width"], meta["height"]
        e["duration"], e["fps"] = meta["duration"], meta["fps"]
        e["filesize"] = meta["size"]
        fixed += 1
    with open(man_path, "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False, indent=2)
    log(f"来源回填完成：{fixed}/{len(m.get('stock', []))} 段")
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="all", choices=["all", "stock", "backdrops", "sources"])
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--themes", default=None, help="只处理指定题材，逗号分隔")
    args = ap.parse_args()
    themes = set(args.themes.split(",")) if args.themes else None
    t0 = time.time()
    if args.stage == "sources":
        backfill_stock_sources()
        log(f"完成，用时 {time.time()-t0:.1f}s")
        return
    stock, backdrops = [], []
    if args.stage in ("all", "stock"):
        stock = stage_stock(force=args.force, themes=themes)
    if args.stage in ("all", "backdrops"):
        if args.stage == "backdrops":
            # 只跑背景时沿用已有 manifest 的 stock 信息
            p = os.path.join(ASSETS, "manifest.json")
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    stock = json.load(f).get("stock", [])
        backdrops = stage_backdrops(force=args.force)
    if not stock:
        p = os.path.join(ASSETS, "manifest.json")
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                stock = json.load(f).get("stock", [])
    write_manifest(stock, backdrops)
    log(f"全部完成，用时 {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
