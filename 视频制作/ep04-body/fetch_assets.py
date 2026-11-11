#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第 04 期《你的身体，比参数表更懂车》B-roll 素材抓取
=====================================================
流程：
  stage search     Pexels API 搜索 8 个缺失题材，结果缓存在 /tmp/ep04_assets_cache/
  stage stock      按题材排名下载 1920x1080 mp4 → assets/stock/（已有同名文件跳过）
  stage verify     ffmpeg -i 解析元数据 + 全片解码校验（分辨率/时长/fps/可解码）
  stage backdrops  每条新素材在中段窗口抽 4 帧评分选 3 帧 → 1920x1080 JPG → assets/backdrops/
                   （只做等比缩放 + 中心裁切，不调色）
  stage manifest   合并既有 9 条 stock + 新素材 + 底片 → assets/manifest.json

用法：
    source /app/vedio/china-aigc/keys.env      # 取 $PEXELS_API_KEY
    python3 fetch_assets.py                    # 全流程
    python3 fetch_assets.py --stage search --dump
    python3 fetch_assets.py --stage stock
    python3 fetch_assets.py --force            # 重新下载（仍不会覆盖既有 9 条）

约束（4 CPU / 6GB cgroup）：
  - PEXELS_API_KEY 只从环境变量读，绝不硬编码；也支持从 keys.env 读取（不落盘 key）。
  - 下载并发 ≤2；ffmpeg 统一 -threads 2。
  - 本期新增下载总量硬上限 400MB（BUDGET_BYTES）。
  - 已有 9 条 stock 视为只读输入，不修改。

依赖：ffmpeg/ffprobe（/home/admin/.local/bin，ffprobe 实为 ffmpeg 软链，故用 ffmpeg -i 解析）、
      numpy、Pillow、curl。
"""
import os
import re
import sys
import json
import time
import math
import hashlib
import argparse
import subprocess
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
from PIL import Image

ROOT = "/app/vedio/ep04-body"
ASSETS = os.path.join(ROOT, "assets")
STOCK = os.path.join(ASSETS, "stock")
BACKDROPS = os.path.join(ASSETS, "backdrops")
CACHE = "/tmp/ep04_assets_cache"
FRAMES = os.path.join(CACHE, "frames")
QA = os.path.join(CACHE, "qa")
KEYS_ENV = "/app/vedio/china-aigc/keys.env"

FFMPEG = "/home/admin/.local/bin/ffmpeg"
FFPROBE = "/home/admin/.local/bin/ffprobe"

# 4 CPU / 6GB cgroup：抽帧与解码每个进程 -threads 2，下载并发 2
FFMPEG_THREADS = 2
DOWNLOAD_JOBS = 2
BUDGET_BYTES = 400 * 1024 * 1024
# 单文件上限（1080p 十几秒的片段远小于此，避免误下 4K 大文件）
MAX_FILE_BYTES = 120 * 1024 * 1024

# 既有 9 条素材（ep01-hybrid 转到本期，只读）：题材 → (中文名, 用途)
LEGACY_STOCK = {
    "car_engine": ("发动机舱", "S4 燃油车扭矩爬升（转速缓慢上爬的实拍）"),
    "car_dash": ("仪表盘", "S1 参数表对照、S4 速度感/数字与现实对照"),
    "brake_pedal": ("刹车踏板", "S2 减速动作、S4 动能回收松油门"),
    "car_interior_night": ("夜间车内", "S3 过弯车内视角、S5 收束"),
    "steering_night": ("夜间方向盘", "S3 方向盘回正力矩/信息提前量"),
    "battery": ("电池包", "S4 电动化转场（油→电）"),
    "rain_window": ("雨窗", "S4 雨滴/视线模糊，jerk 的情绪铺垫"),
    "metro_window": ("地铁车窗", "S1 通勤/城市日常，困惑开场"),
    "city_night_aerial": ("城市夜景航拍", "S1/S5 城市夜景、情绪留白"),
}

# 8 个缺口题材：英文搜索词（Pexels 英文检索效果最好），每个题材多轮查询合并去重
THEME_QUERIES = {
    "speed_bump": [
        "car driving over speed bump",
        "speed bump road",
        "car crossing speed bump",
        "driving over bumpy road",
        "car driving mud road",
        "car driving dirt road",
        "car moving on sloppy road",
        "car on gravel road",
    ],
    "wheel_suspension": [
        "car wheel close up",
        "car suspension",
        "shock absorber",
        "car tire close up",
        "wheel suspension car",
        "car wheel on dirt road",
        "rain on car tire",
    ],
    "wet_road_night": [
        "wet road night",
        "rain road reflection",
        "puddle reflection night",
        "wet asphalt night",
    ],
    "winding_road": [
        "winding mountain road aerial",
        "curved road",
        "mountain road drive",
        "bend road aerial",
    ],
    "rearview_mirror": [
        "rear view mirror driving",
        "car side mirror road",
        "mirror car driving",
    ],
    "windshield_rain": [
        "rain on windshield",
        "rain windshield driving",
        "raindrops windshield",
        "rain drops car window driving",
    ],
    "hands_steering": [
        "hands on steering wheel",
        "steering wheel close up",
        "driver hands steering wheel",
        "hand steering wheel driving",
    ],
    "night_driving": [
        "night driving car",
        "car driving night road",
        "night road headlights",
        "driving at night",
    ],
}

THEME_CN = {
    "speed_bump": "减速带/过坎",
    "wheel_suspension": "车轮/悬架特写",
    "wet_road_night": "雨夜路面积水倒影",
    "winding_road": "弯道/山路",
    "rearview_mirror": "后视镜",
    "windshield_rain": "挡风玻璃雨滴（行驶中）",
    "hands_steering": "手握方向盘特写",
    "night_driving": "夜间行车",
    "car_engine": "发动机舱",
    "car_dash": "仪表盘",
    "brake_pedal": "刹车踏板",
    "car_interior_night": "夜间车内",
    "steering_night": "夜间方向盘",
    "battery": "电池包",
    "rain_window": "雨窗",
    "metro_window": "地铁车窗",
    "city_night_aerial": "城市夜景航拍",
}

# 题材 → 建议适配的段落/镜头（写进 manifest，供 Lead 分镜取用）
USE_HINT = {
    "speed_bump": "S2 核心画面：车轮压过减速带；“咚/咣当”的实拍锚点，可接阻尼振荡曲线",
    "wheel_suspension": "S2 车轮-弹簧-减振器结构解释的实拍底；100mm 微距质感（胎面/轮拱）",
    "wet_road_night": "S2 阻尼曲线载体：车身倒影在积水里荡开又收敛；S4 雨夜路面",
    "winding_road": "S3 过弯：弯道路面/山路俯拍，接侧倾角—横向加速度曲线",
    "rearview_mirror": "S3 核心观察界面：后视镜里车身与地平线夹角，侧倾角曲线依附其上",
    "windshield_rain": "S4 jerk 载体：加速瞬间雨滴被甩出的轨迹；S5 情绪收束",
    "hands_steering": "S1/S3/S5 身体层：手握方向盘微调、回正力矩的触感特写",
    "night_driving": "S1/S5 夜间行车氛围；S3 信心与信息提前量的长镜头",
}

# 人工精选（Pexels video id 优先，按搜索阶段人工看过 slug/alt 后填入）
CURATED = {
    # 人工看过 Pexels 预览图后选定（见 assets/manifest.json 的 pexels_id）。
    # 说明：Pexels 上没有可直接命中的真实减速带片段（关键词命中被"fist bump"等污染），
    # 按稿件 §6 的退路，用"车辆过水坑 / 过烂路时车轮与车身动作"替代 S2 的过坎镜头，
    # 再叠加程序化二自由度振动 + 阻尼曲线（渲染端负责）。以下为最终采用。
    "speed_bump": [19516511, 11794068],
    "wheel_suspension": [10358974, 29902177, 40300734],
    "wet_road_night": [40863419, 12570193, 11785816],
    "winding_road": [15952966, 39306857, 13126809],
    "rearview_mirror": [4974625, 34001033],
    "windshield_rain": [3913495, 34479250, 6194746],
    "hands_steering": [9130073, 11675556],
    "night_driving": [19830439, 13643105],
}

# 每个题材下载几条（1—3 条）
QUOTA = {
    "speed_bump": 2,
    "wheel_suspension": 3,
    "wet_road_night": 3,
    "winding_road": 3,
    "rearview_mirror": 2,
    "windshield_rain": 3,
    "hands_steering": 2,
    "night_driving": 2,
}

NEW_STOCK_THEMES = list(QUOTA.keys())


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ---------------------------------------------------------------- 基础工具


def load_key():
    key = os.environ.get("PEXELS_API_KEY", "").strip()
    if key:
        return key
    if os.path.exists(KEYS_ENV):
        with open(KEYS_ENV, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                m = re.match(r"export\s+PEXELS_API_KEY\s*=\s*(.+)", line)
                if m:
                    return m.group(1).strip().strip('"').strip("'")
    raise SystemExit("找不到 PEXELS_API_KEY：先 source keys.env（本脚本只从环境变量/keys.env 读，不硬编码）")


def http_json(url, key, timeout=30, retries=4):
    """带退避重试（403/429 重点退避 2/4/8s）。"""
    last = None
    for attempt in range(retries):
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": key,
                "User-Agent": "ep04-asset-fetcher/1.0 (Pexels API)",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
            if e.code in (403, 429) and attempt < retries - 1:
                wait = 2 ** (attempt + 1)
                log(f"  {last}，{wait}s 后重试（{url[:90]}…）")
                time.sleep(wait)
                continue
            raise
        except Exception as e:  # 网络抖动
            last = f"{type(e).__name__}: {e}"
            if attempt < retries - 1:
                time.sleep(2 ** (attempt + 1))
                continue
            raise
    raise RuntimeError(f"HTTP 重试失败：{last}")


def run(cmd, timeout=600):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    return p.returncode, p.stdout.decode("utf-8", "ignore"), p.stderr.decode("utf-8", "ignore")


def ffmpeg_meta(path):
    """本机 ffprobe 软链实为 ffmpeg，用 ffmpeg -i 解析元数据。"""
    rc, out, err = run([FFMPEG, "-hide_banner", "-i", path], timeout=90)
    text = err
    m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", text)
    if not m:
        raise RuntimeError(f"无法解析视频元数据: {path}\n{text[-500:]}")
    duration = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    vids = re.findall(r"Video:.*?(\d{2,5})x(\d{2,5})", text, re.S)
    if not vids:
        raise RuntimeError(f"无法解析视频分辨率: {path}\n{text[-500:]}")
    width, height = int(vids[0][0]), int(vids[0][1])
    mf = re.search(r",\s*([\d.]+)\s*fps", text)
    fps = mf.group(1) if mf else "0"
    mcodec = re.search(r"Video:\s*([a-z0-9]+)", text)
    return {
        "width": width,
        "height": height,
        "fps": fps,
        "duration": round(duration, 3),
        "codec": mcodec.group(1) if mcodec else "unknown",
        "size": os.path.getsize(path),
    }


def decode_check(path, timeout=240):
    """全片解码到 null，确认可解码；失败抛异常。"""
    rc, out, err = run(
        [FFMPEG, "-hide_banner", "-loglevel", "error", "-threads", str(FFMPEG_THREADS),
         "-i", path, "-map", "0:v:0", "-f", "null", "-"],
        timeout=timeout,
    )
    if rc != 0 or err.strip():
        raise RuntimeError(f"解码校验失败 rc={rc}: {err.strip()[-400:]}")
    return True


# ---------------------------------------------------------------- Pexels 搜索


def search_cache(theme, query, key):
    os.makedirs(CACHE, exist_ok=True)
    h = hashlib.md5(f"{query}|landscape|v2".encode()).hexdigest()[:12]
    path = os.path.join(CACHE, f"search_{theme}_{h}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    url = (
        "https://api.pexels.com/videos/search?"
        + urllib.parse.urlencode(
            {"query": query, "orientation": "landscape", "per_page": 30}
        )
    )
    data = http_json(url, key)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    time.sleep(0.35)  # 温和限速，避免 429
    return data


def pick_files(video):
    """按优先级返回该视频所有 ≥1920x1080 的 mp4 文件（首发不通过时依次回退）。

    Pexels 存在元数据与实际不符的情况（例如文件名带 hd_1920_1080，实际流是 1280x720），
    所以下载后必须用 ffmpeg 实测分辨率，不通过就换下一档文件（2560/3840）再试。
    """
    opts = []
    for f in video.get("video_files", []) or []:
        if f.get("file_type") != "video/mp4":
            continue
        w = int(f.get("width") or 0)
        h = int(f.get("height") or 0)
        size = int(f.get("size") or 0)
        if w < 1920 or h < 1080:
            continue
        if size and size > MAX_FILE_BYTES:
            continue
        # 距离 1920 越近越好；同宽取小文件；优先 16:9
        score = -abs(w - 1920) * 10.0
        if abs(w / max(h, 1) - 16 / 9) < 0.02:
            score += 50.0
        score -= size / (1024 * 1024) * 0.05
        opts.append((score, f))
    opts.sort(key=lambda x: -x[0])
    return [f for _, f in opts]


def pick_file(video):
    files = pick_files(video)
    return files[0] if files else None


def video_by_id(vid, key):
    """用 Pexels 单条视频接口取元数据（人工精选 id 不在搜索结果里时兜底，保证可复现）。"""
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, f"video_{int(vid)}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    data = http_json(f"https://api.pexels.com/videos/videos/{int(vid)}", key)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    time.sleep(0.35)
    return data


def video_candidates(theme, key, seen=None):
    """合并该题材多轮搜索，过滤 landscape / ≥1920 宽 / ≥6s，按题材内排名。"""
    seen = seen if seen is not None else {}
    for q in THEME_QUERIES.get(theme, []):
        try:
            data = search_cache(theme, q, key)
        except Exception as e:
            log(f"  搜索失败 [{theme}/{q}]：{e}")
            continue
        for v in data.get("videos", []) or []:
            try:
                vid = int(v.get("id"))
            except (TypeError, ValueError):
                continue
            w = int(v.get("width") or 0)
            h = int(v.get("height") or 0)
            dur = float(v.get("duration") or 0)
            if w <= h or w < 1920 or h < 1080:
                continue
            if dur < 6:
                continue
            files = pick_files(v)
            if not files:
                continue
            if vid not in seen:
                seen[vid] = {"video": v, "file": files[0], "files": files,
                             "query": q, "theme": theme}
    # 人工精选：搜索结果里没出现的 id，走单条视频接口补齐（人工 QA 后定稿，见 CURATED）
    for vid in CURATED.get(theme, []):
        if vid in seen:
            continue
        try:
            v = video_by_id(vid, key)
        except Exception as e:
            log(f"  精选 id {vid} 获取失败：{e}")
            continue
        w = int(v.get("width") or 0)
        h = int(v.get("height") or 0)
        dur = float(v.get("duration") or 0)
        files = pick_files(v)
        if not files or w <= h or w < 1920 or h < 1080 or dur < 6:
            log(f"  精选 id {vid} 不合规，跳过（{w}x{h} {dur}s）")
            continue
        seen[vid] = {"video": v, "file": files[0], "files": files,
                     "query": "manual-pick", "theme": theme}
    out = []
    curated = CURATED.get(theme, [])
    for vid, item in seen.items():
        v = item["video"]
        dur = float(v.get("duration") or 0)
        f = item["file"]
        fw = int(f.get("width") or 0)
        fh = int(f.get("height") or 0)
        fsize = int(f.get("size") or 0)
        score = 0.0
        if vid in curated:
            score += 100.0 - curated.index(vid) * 10.0
        if fw == 1920 and fh == 1080:
            score += 8.0
        elif abs(fw / max(fh, 1) - 16 / 9) < 0.02:
            score += 5.0
        if 6 <= dur <= 20:
            score += 4.0
        elif dur <= 35:
            score += 2.0
        else:
            score -= 1.0
        if 0 < fsize <= 40 * 1024 * 1024:
            score += 1.5
        # url slug 里出现相关词的加权（Pexels url 带描述）
        slug = (v.get("url") or "").lower()
        for kw in {
            "speed_bump": ["speed-bump", "bump", "pothole"],
            "wheel_suspension": ["wheel", "tire", "suspension", "shock"],
            "wet_road_night": ["wet", "rain", "puddle", "reflection", "night"],
            "winding_road": ["road", "mountain", "curve", "winding", "aerial"],
            "rearview_mirror": ["mirror"],
            "windshield_rain": ["rain", "windshield", "window"],
            "hands_steering": ["steering", "hands", "driver"],
            "night_driving": ["night", "driving", "headlight"],
        }.get(theme, []):
            if kw in slug:
                score += 1.0
        out.append((score, item))
    out.sort(key=lambda x: -x[0])
    return [item for _, item in out]


def dump_candidates():
    key = load_key()
    os.makedirs(CACHE, exist_ok=True)
    summary = {}
    for theme in NEW_STOCK_THEMES:
        cands = video_candidates(theme, key)
        rows = []
        for item in cands[:8]:
            v, f = item["video"], item["file"]
            rows.append({
                "id": int(v["id"]),
                "size": f"{f.get('width')}x{f.get('height')}",
                "dur": v.get("duration"),
                "mb": round(int(f.get("size") or 0) / 1048576, 1),
                "url": v.get("url"),
            })
        summary[theme] = rows
        print(f"\n## {theme}（{THEME_CN[theme]}）候选 {len(cands)} 条")
        for r in rows:
            print(f"  {r['id']:>9} {r['size']:>10} {r['dur']:>5}s {r['mb']:>6}MB  {r['url']}")
    with open(os.path.join(CACHE, "candidates.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    log(f"候选清单：{os.path.join(CACHE, 'candidates.json')}")


# ---------------------------------------------------------------- 下载


def download(url, dest, timeout=300):
    tmp = dest + ".part"
    rc, out, err = run(
        ["/usr/bin/env", "curl", "-sSL", "--fail", "--retry", "2",
         "--max-time", str(timeout), "-o", tmp, url],
        timeout=timeout + 30,
    )
    if rc != 0 or not os.path.exists(tmp) or os.path.getsize(tmp) < 300 * 1024:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise RuntimeError(f"下载失败 rc={rc}: {err[-300:]}")
    os.replace(tmp, dest)
    return os.path.getsize(dest)


def _new_download_bytes():
    """只统计本期新下载文件（排除既有 9 条只读素材）。"""
    total = 0
    for f in os.listdir(STOCK):
        if f.endswith(".mp4") and f[:-4] not in LEGACY_STOCK:
            total += os.path.getsize(os.path.join(STOCK, f))
    return total


def stage_stock(force=False):
    key = load_key()
    os.makedirs(STOCK, exist_ok=True)
    total_new = _new_download_bytes()
    n_stock = sum(1 for f in os.listdir(STOCK) if f.endswith(".mp4"))
    log(f"stock 目录现有 {n_stock} 条（本期新下载 {total_new / 1048576:.1f}MB）")

    # 先把已有新素材的元数据登记（重跑时沿用）
    entries = []
    new_files = set()
    for theme in NEW_STOCK_THEMES:
        cands = video_candidates(theme, key)
        if not cands:
            log(f"!! {theme} 无候选，跳过")
            continue
        qu = QUOTA.get(theme, 1)
        already = []
        for i in range(1, 4):
            p = os.path.join(STOCK, f"{theme}_{i:02d}.mp4")
            if os.path.exists(p) and os.path.getsize(p) > 300 * 1024:
                already.append(p)
        need = qu - len(already)
        if need <= 0 and not force:
            for p in already:
                new_files.add(p)
            log(f"{theme}: 已有 {len(already)} 条，跳过下载")
            continue
        if force:
            for p in already:
                os.remove(p)
            already = []
            need = qu
            total_new = _new_download_bytes()
        log(f"{theme}: 需下载 {need} 条（候选 {len(cands)}）")
        downloaded_here = []
        for item in cands:
            if len(downloaded_here) >= need:
                break
            v = item["video"]
            vid = int(v["id"])
            idx = len(already) + len(downloaded_here) + 1
            dest = os.path.join(STOCK, f"{theme}_{idx:02d}.mp4")
            ok = False
            # 依次尝试该视频的各个 ≥1920 文件档位：
            # Pexels 元数据与实际流分辨率可能不符（如 1920 档实为 720p），实测不过就换 1440/2160 档
            for f in item.get("files") or [item["file"]]:
                if total_new + int(f.get("size") or 0) > BUDGET_BYTES:
                    log(f"  预算不足（已 {total_new / 1048576:.0f}MB），停止")
                    break
                try:
                    log(f"  下载 {theme} <- pexels {vid} 声明 {f.get('width')}x{f.get('height')} "
                        f"{v.get('duration')}s {int(f.get('size') or 0) / 1048576:.1f}MB")
                    size = download(f["link"], dest)
                    meta = ffmpeg_meta(dest)
                    if meta["width"] < 1920 or meta["height"] < 1080:
                        raise RuntimeError(f"实测分辨率不足 {meta['width']}x{meta['height']}")
                    if meta["duration"] < 5.5:
                        raise RuntimeError(f"时长不足 {meta['duration']}s")
                    decode_check(dest)
                    item["meta"] = meta
                    item["downloaded_size"] = size
                    item["chosen_file"] = {k: f.get(k) for k in ("width", "height", "size", "link")}
                    total_new += size
                    downloaded_here.append((dest, item))
                    ok = True
                    log(f"  ✓ {os.path.basename(dest)} {meta['width']}x{meta['height']} "
                        f"{meta['duration']}s {meta['fps']}fps {size / 1048576:.1f}MB")
                    break
                except Exception as e:
                    log(f"  ✗ 该档位放弃（pexels {vid}）：{e}")
                    if os.path.exists(dest):
                        os.remove(dest)
                    continue
            if not ok:
                log(f"  ✗ 整条素材放弃：pexels {vid}")
        entries.extend(downloaded_here)
        with open(os.path.join(CACHE, "download_log.json"), "a", encoding="utf-8") as f:
            json.dump(
                [{"file": d, "pexels_id": int(it["video"]["id"]), "theme": theme,
                  "query": it["query"], "source": it["video"].get("url")}
                 for d, it in downloaded_here],
                f, ensure_ascii=False,
            )
    total = sum(
        os.path.getsize(os.path.join(STOCK, f))
        for f in os.listdir(STOCK) if f.endswith(".mp4")
    )
    log(f"stock 阶段完成：新增 {len(entries)} 条；stock 总计 {total / 1048576:.1f}MB")
    return entries


# ---------------------------------------------------------------- 抽帧（底片）


def frame_score(jpg_path):
    """清晰度 + 亮度健康度评分；黑帧/纯色帧给负分。"""
    im = Image.open(jpg_path).convert("RGB")
    small = im.resize((480, 270), Image.BILINEAR)
    a = np.asarray(small, dtype=np.float32) / 255.0
    g = a @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    k = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float32)
    lap = (
        g[:-2, 1:-1] * k[0, 1] + g[2:, 1:-1] * k[2, 1]
        + g[1:-1, :-2] * k[1, 0] + g[1:-1, 2:] * k[1, 2]
        + g[1:-1, 1:-1] * k[1, 1]
    )
    sharp = float(lap.var() * 1000.0)
    mean = float(g.mean())
    std = float(g.std())
    score = min(sharp, 2.5) + 0.5 * min(std / 0.2, 1.0)
    if mean < 0.025:
        score -= 3.0  # 黑帧
    if mean > 0.88:
        score -= 1.0  # 过曝白屏
    if std < 0.02:
        score -= 2.0  # 纯色
    return score, {"sharp": round(sharp, 2), "mean": round(mean, 3), "std": round(std, 3)}


def extract_backdrops(video_path, stem, count=3, tag=""):
    """在中段 15%–85% 窗口抽 4 帧 → 评分选 count 帧 → 1920x1080 JPG（仅缩放+中心裁切）。"""
    meta = ffmpeg_meta(video_path)
    dur = max(meta["duration"], 1.0)
    start = 0.15 * dur
    span = 0.70 * dur
    os.makedirs(FRAMES, exist_ok=True)
    os.makedirs(BACKDROPS, exist_ok=True)
    pattern = os.path.join(FRAMES, f"{tag or stem}_c%02d.jpg")
    for old in [p for p in os.listdir(FRAMES) if p.startswith((tag or stem) + "_c")]:
        os.remove(os.path.join(FRAMES, old))
    n_cand = max(count + 1, 4)
    fps = n_cand / max(span, 0.1)
    vf = (
        f"fps={fps:.6f},"
        "scale=1920:1080:force_original_aspect_ratio=increase,"
        "crop=1920:1080"
    )
    rc, out, err = run(
        [FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
         "-threads", str(FFMPEG_THREADS),
         "-ss", f"{start:.3f}", "-t", f"{span:.3f}", "-i", video_path,
         "-vf", vf, "-frames:v", str(n_cand), "-q:v", "2", "-an", pattern],
        timeout=600,
    )
    if rc != 0:
        raise RuntimeError(f"抽帧失败 {video_path}: {err[-300:]}")
    cands = sorted(p for p in os.listdir(FRAMES) if p.startswith((tag or stem) + "_c"))
    scored = []
    for p in cands:
        sp = os.path.join(FRAMES, p)
        try:
            sc, info = frame_score(sp)
        except Exception:
            continue
        t = start + (span / n_cand) * (int(re.search(r"_c(\d+)", p).group(1)) - 1)
        scored.append((sc, t, sp, info))
    scored.sort(key=lambda x: -x[0])
    picked = scored[:count]
    picked.sort(key=lambda x: x[1])  # 按时间排序命名
    results = []
    for i, (sc, t, sp, info) in enumerate(picked, 1):
        out_path = os.path.join(BACKDROPS, f"{stem}_{i:02d}.jpg")
        im = Image.open(sp).convert("RGB")
        if im.size != (1920, 1080):
            im = im.resize((1920, 1080), Image.LANCZOS)
        im.save(out_path, "JPEG", quality=92, subsampling=1)
        results.append({
            "file": os.path.relpath(out_path, ROOT),
            "frame_time": round(t, 2),
            "width": 1920,
            "height": 1080,
            "score": round(sc, 2),
        })
    # 另存 3 张候选 QA 图（不参与交付，仅人工复核用，在 /tmp 内）
    os.makedirs(QA, exist_ok=True)
    for j, (sc, t, sp, info) in enumerate(scored, 1):
        im = Image.open(sp).convert("RGB")
        im.resize((480, 270), Image.LANCZOS).save(
            os.path.join(QA, f"{tag or stem}_q{j}_{sc:.1f}.jpg"), quality=82)
    return meta, results


def stage_backdrops(force=False):
    """新素材每条 3 帧；既有 9 条各抽 2 帧（同规则，供 Ken Burns 背景层）。"""
    key = load_key()
    mapping = {}
    # 新素材：从 stock 文件名推断题材
    for f in sorted(os.listdir(STOCK)):
        if not f.endswith(".mp4"):
            continue
        stem = f[:-4]
        theme = None
        for t in NEW_STOCK_THEMES:
            if stem.startswith(t + "_"):
                theme = t
                break
        if theme:
            mapping[stem] = {"theme": theme, "count": 3}
    # 既有素材：只读，各抽 2 帧
    legacy_stems = [f[:-4] for f in sorted(os.listdir(STOCK))
                    if f.endswith(".mp4") and f[:-4] in LEGACY_STOCK]
    for stem in legacy_stems:
        mapping.setdefault(stem, {"theme": stem, "count": 2})

    results = []
    for stem, info in mapping.items():
        path = os.path.join(STOCK, stem + ".mp4")
        tag = "legacy_" + stem if stem in LEGACY_STOCK else stem
        existing = [p for p in os.listdir(BACKDROPS) if p.startswith(stem + "_")]
        if existing and not force:
            frames = []
            for p in sorted(existing):
                frames.append({"file": os.path.relpath(os.path.join(BACKDROPS, p), ROOT),
                               "width": 1920, "height": 1080})
            results.append({"stem": stem, "theme": info["theme"], "frames": frames,
                            "meta": ffmpeg_meta(path), "skipped": True})
            continue
        for p in existing:
            os.remove(os.path.join(BACKDROPS, p))
        log(f"抽帧 {stem}（{THEME_CN.get(info['theme'], info['theme'])}，{info['count']} 帧）")
        try:
            meta, frames = extract_backdrops(path, stem, count=info["count"], tag=tag)
            results.append({"stem": stem, "theme": info["theme"], "frames": frames, "meta": meta})
        except Exception as e:
            log(f"  ✗ 抽帧失败 {stem}: {e}")
            results.append({"stem": stem, "theme": info["theme"], "frames": [], "meta": None})
    log(f"backdrops 阶段完成：{len(results)} 条素材，"
        f"{sum(len(r['frames']) for r in results)} 张底片")
    return results


# ---------------------------------------------------------------- manifest


def load_new_source_log():
    """从下载日志 + 搜索缓存重建新素材的 Pexels 出处。"""
    log_path = os.path.join(CACHE, "download_log.json")
    out = {}
    if not os.path.exists(log_path):
        return out
    with open(log_path, "r", encoding="utf-8") as f:
        text = f.read()
    dec = json.JSONDecoder()
    i = 0
    while i < len(text):
        while i < len(text) and text[i] in " \n\r\t":
            i += 1
        if i >= len(text):
            break
        try:
            obj, j = dec.raw_decode(text, i)
        except json.JSONDecodeError:
            break
        i = j
        for rec in obj if isinstance(obj, list) else [obj]:
            out[os.path.basename(rec["file"])] = rec
    return out


def build_stock_entry(stem, theme, meta, frames, src=None):
    entry = {
        "file": f"assets/stock/{stem}.mp4",
        "theme": theme,
        "theme_cn": THEME_CN.get(theme, theme),
        "width": meta["width"],
        "height": meta["height"],
        "duration": meta["duration"],
        "fps": meta["fps"],
        "filesize": meta["size"],
        "use_hint": USE_HINT.get(theme, LEGACY_STOCK.get(theme, ("", ""))[1]),
        "frames": [fr["file"] for fr in frames],
    }
    if src:
        entry.update({
            "source": src.get("source"),
            "pexels_id": src.get("pexels_id"),
            "query": src.get("query"),
            "author": src.get("author"),
            "author_url": src.get("author_url"),
            "license": "Pexels License",
        })
    else:
        entry.update({
            "source": "legacy: /app/vedio/ep01-hybrid/assets/stock/（ep01 fetch_stock.py 从 Pexels 获取，原始出处未记录）",
            "pexels_id": None,
            "author": None,
            "author_url": None,
            "license": "Pexels License（经 ep01-hybrid 获取；原始作者信息未留存）",
        })
    return entry


def stage_manifest(backdrop_results=None):
    # 若未传入，则从磁盘重建
    if backdrop_results is None:
        backdrop_results = []
    src_log = load_new_source_log()
    # 从 search cache 全量读取（含 user 作者信息）
    id2video = {}
    for fn in os.listdir(CACHE) if os.path.isdir(CACHE) else []:
        if not fn.startswith("search_") or not fn.endswith(".json"):
            continue
        try:
            with open(os.path.join(CACHE, fn), "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        for v in data.get("videos", []) or []:
            try:
                id2video[int(v["id"])] = v
            except (TypeError, ValueError):
                continue

    stock = []
    backdrops = []
    done = set()
    # 新素材（Pexels）
    for f in sorted(os.listdir(STOCK)):
        if not f.endswith(".mp4"):
            continue
        stem = f[:-4]
        theme = next((t for t in NEW_STOCK_THEMES if stem.startswith(t + "_")), None)
        if not theme:
            continue
        path = os.path.join(STOCK, f)
        meta = ffmpeg_meta(path)
        frames = [r for r in backdrop_results if r["stem"] == stem]
        frames = frames[0]["frames"] if frames else []
        rec = src_log.get(f, {})
        vid = id2video.get(int(rec["pexels_id"])) if rec.get("pexels_id") else None
        src = {
            "source": rec.get("source") or (vid.get("url") if vid else None),
            "pexels_id": rec.get("pexels_id"),
            "query": rec.get("query"),
            "author": (vid or {}).get("user", {}).get("name") if vid else None,
            "author_url": (vid or {}).get("user", {}).get("url") if vid else None,
        }
        stock.append(build_stock_entry(stem, theme, meta, frames, src))
        for fr in frames:
            backdrops.append({
                "file": fr["file"], "theme": theme,
                "theme_cn": THEME_CN.get(theme, theme),
                "source_stock": f"assets/stock/{stem}.mp4",
                "frame_time": fr.get("frame_time"),
                "width": 1920, "height": 1080,
                "note": "仅等比缩放+中心裁切，未做最终调色",
            })
        done.add(stem)
    # 既有 9 条
    for stem in LEGACY_STOCK:
        path = os.path.join(STOCK, stem + ".mp4")
        if not os.path.exists(path):
            log(f"!! 既有素材缺失：{path}")
            continue
        meta = ffmpeg_meta(path)
        frames = [r for r in backdrop_results if r["stem"] == stem]
        frames = frames[0]["frames"] if frames else []
        stock.append(build_stock_entry(stem, stem, meta, frames, None))
        for fr in frames:
            backdrops.append({
                "file": fr["file"], "theme": stem,
                "theme_cn": LEGACY_STOCK[stem][0],
                "source_stock": f"assets/stock/{stem}.mp4",
                "frame_time": fr.get("frame_time"),
                "width": 1920, "height": 1080,
                "note": "仅等比缩放+中心裁切，未做最终调色",
            })
    new_bytes = sum(
        os.path.getsize(os.path.join(STOCK, f)) for f in os.listdir(STOCK)
        if f.endswith(".mp4") and not (f[:-4] in LEGACY_STOCK)
    )
    total_bytes = sum(
        os.path.getsize(os.path.join(STOCK, f)) for f in os.listdir(STOCK)
        if f.endswith(".mp4")
    )
    manifest = {
        "episode": "第04期-你的身体，比参数表更懂车",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "canvas": {"film": "1920x1080", "fps": 24, "backdrop": "1920x1080 JPG",
                   "note": "成片 2.35:1 遮幅；底片供 Ken Burns/背景层，未调色"},
        "visual_direction": "真实 B-roll 路面/车内/手部 + 程序化数据层；S2 减速带阻尼、S3 过弯侧倾/后视镜、S4 雨滴/jerk 是视觉核心",
        "themes": {
            t: {"theme_cn": THEME_CN[t], "queries": THEME_QUERIES[t], "use_hint": USE_HINT[t]}
            for t in NEW_STOCK_THEMES
        },
        "stock": stock,
        "backdrops": backdrops,
        "summary": {
            "stock_total": len(stock),
            "stock_new_pexels": sum(1 for s in stock if s["pexels_id"]),
            "stock_legacy": sum(1 for s in stock if not s["pexels_id"]),
            "backdrops_total": len(backdrops),
            "download_mb": round(new_bytes / 1048576, 1),
            "stock_total_mb": round(total_bytes / 1048576, 1),
            "budget_mb": 400,
        },
    }
    path = os.path.join(ASSETS, "manifest.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    log(f"manifest 写入：{path}（stock {len(stock)} / backdrops {len(backdrops)}，"
        f"新增下载 {new_bytes / 1048576:.1f}MB）")
    return manifest


# ---------------------------------------------------------------- main


def main():
    ap = argparse.ArgumentParser(description="第04期 B-roll 素材抓取")
    ap.add_argument("--stage", default="all",
                    choices=["all", "search", "stock", "verify", "backdrops", "manifest"])
    ap.add_argument("--force", action="store_true", help="强制重新执行该阶段")
    ap.add_argument("--dump", action="store_true", help="search 阶段打印候选清单")
    args = ap.parse_args()

    os.makedirs(STOCK, exist_ok=True)
    os.makedirs(BACKDROPS, exist_ok=True)
    os.makedirs(CACHE, exist_ok=True)

    if args.stage == "search":
        if args.dump:
            dump_candidates()
        else:
            key = load_key()
            for theme in NEW_STOCK_THEMES:
                c = video_candidates(theme, key)
                log(f"{theme}: {len(c)} 条候选")
        return

    if args.stage in ("all", "stock"):
        stage_stock(args.force)
        if args.stage == "stock":
            return
    if args.stage == "verify":
        ok = True
        for f in sorted(os.listdir(STOCK)):
            if not f.endswith(".mp4"):
                continue
            p = os.path.join(STOCK, f)
            try:
                meta = ffmpeg_meta(p)
                decode_check(p)
                log(f"✓ {f} {meta['width']}x{meta['height']} {meta['duration']}s "
                    f"{meta['fps']}fps {meta['size'] / 1048576:.1f}MB")
            except Exception as e:
                ok = False
                log(f"✗ {f}: {e}")
        log("verify 完成" if ok else "verify 有失败项")
        return
    if args.stage in ("all", "backdrops"):
        bd = stage_backdrops(args.force)
        if args.stage == "backdrops":
            return
    else:
        bd = None
    if args.stage in ("all", "manifest"):
        stage_manifest(bd)
    log("全部完成")


if __name__ == "__main__":
    main()
