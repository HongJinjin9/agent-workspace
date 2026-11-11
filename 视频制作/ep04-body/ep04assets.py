#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 04 期素材解析：逻辑名 → 实际文件（视频 / 静帧），并缓存抽帧底片。"""
import os
import subprocess
import sys

ROOT = "/app/vedio/ep04-body"
STOCK = os.path.join(ROOT, "assets", "stock")
BACKDROPS = os.path.join(ROOT, "assets", "backdrops")
PLATES = os.path.join(ROOT, "work", "plates")
FFMPEG = "/home/admin/.local/bin/ffmpeg"
FFPROBE = "/home/admin/.local/bin/ffprobe"

# 逻辑名 → 候选文件（优先 assets/stock 视频，其次 assets/backdrops 静帧）。
CANDIDATES = {
    # —— 已有（第 01 期素材）
    "steering_night": ["steering_night.mp4"],
    "car_dash": ["car_dash.mp4"],
    "car_interior_night": ["car_interior_night.mp4"],
    "car_engine": ["car_engine.mp4"],
    "rain_window": ["rain_window_01.mp4", "rain_window.mp4"],
    "city_night_aerial": ["city_night_aerial.mp4"],
    "battery": ["battery.mp4"],
    "brake_pedal": ["brake_pedal.mp4"],
    "metro_window": ["metro_window.mp4"],
    "night_pov": ["night_driving_01.mp4", "car_interior_night.mp4"],
    "night_car": ["night_driving_02.mp4", "night_driving_01.mp4"],
    "wheel_suspension": ["wheel_suspension_02.mp4", "wheel_suspension_01.mp4"],
    "rearview_mirror_2": ["rearview_mirror_02.mp4", "rearview_mirror_01.mp4"],
    "winding_road_2": ["winding_road_03.mp4", "winding_road_02.mp4"],
    # —— 本期补拍（Pexels 下载，文件名以 assets/manifest.json 为准）
    "hands_grip": ["hands_steering_01.mp4", "hands_grip_01.mp4", "hands_wheel_01.mp4",
                   "steering_wheel_hands_01.mp4", "steering_night.mp4"],
    "hands_feel": ["hands_steering_02.mp4", "hands_wheel_02.mp4", "hands_steering_01.mp4",
                   "hands_grip_01.mp4", "steering_night.mp4"],
    "steering_hands": ["steering_hands_01.mp4", "hands_steering_01.mp4",
                       "hands_wheel_01.mp4", "steering_night.mp4"],
    "speed_bump": ["speed_bump_01.mp4", "speed_bump_02.mp4", "speedbump_01.mp4",
                   "bump_road_01.mp4", "road_bump_01.mp4"],
    "wheel_bump_1": ["wheel_suspension_01.mp4", "wheel_suspension_02.mp4",
                     "wheel_bump_01.mp4", "suspension_01.mp4", "wheel_close_01.mp4"],
    "wheel_bump_2": ["wheel_suspension_02.mp4", "wheel_suspension_03.mp4",
                     "wheel_bump_02.mp4", "bumpy_road_01.mp4", "speed_bump_02.mp4"],
    "puddle_night": ["wet_road_night_01.mp4", "wet_road_night_02.mp4", "wet_road_night_03.mp4",
                     "puddle_night_01.mp4", "rain_road_01.mp4", "rain_window.mp4"],
    "winding_road": ["winding_road_01.mp4", "winding_road_02.mp4", "winding_road_03.mp4",
                     "mountain_road_01.mp4", "bend_road_01.mp4"],
    "rearview_mirror": ["rearview_mirror_01.mp4", "rearview_mirror_02.mp4", "mirror_01.mp4"],
    "rain_drive": ["windshield_rain_01.mp4", "windshield_rain_02.mp4", "windshield_rain_03.mp4",
                   "rain_windshield_01.mp4", "rain_window_01.mp4"],
    "road_ahead_night": ["night_driving_01.mp4", "night_driving_02.mp4", "road_night_01.mp4",
                         "driving_night_01.mp4", "steering_night.mp4"],
    "ev_charge": ["ev_charging_01.mp4", "charging_01.mp4", "electric_car_charge_01.mp4",
                  "battery.mp4"],
    "ev_dash": ["ev_dash_01.mp4", "electric_car_dash_01.mp4", "car_dash_02.mp4",
                "car_dash.mp4"],
}

# 绝对兜底：任何逻辑名解析失败时用这些，保证流水线不断。
SAFE_FALLBACK = {
    "warm": "car_dash.mp4",
    "cool": "steering_night.mp4",
    "engine": "car_engine.mp4",
    "interior": "car_interior_night.mp4",
}

_CACHE = {}


def _find(name):
    for d in (STOCK, BACKDROPS):
        p = os.path.join(d, name)
        if os.path.isfile(p) and os.path.getsize(p) > 20000:
            return p
    return None


def resolve(key):
    """返回 (path, 'video'|'image')。"""
    if key in _CACHE:
        return _CACHE[key]
    for name in CANDIDATES.get(key, []):
        p = _find(name)
        if p:
            kind = "video" if p.endswith(".mp4") else "image"
            _CACHE[key] = (p, kind)
            if name != CANDIDATES.get(key, [None])[0]:
                print("[assets] %s → 兜底 %s" % (key, os.path.basename(p)), flush=True)
            return _CACHE[key]
    # 前缀模糊匹配（Pexels 命名不完全可控）
    for d in (STOCK, BACKDROPS):
        try:
            files = sorted(os.listdir(d))
        except FileNotFoundError:
            continue
        for f in files:
            if f.startswith(key):
                p = os.path.join(d, f)
                if os.path.isfile(p) and os.path.getsize(p) > 20000:
                    kind = "video" if f.endswith(".mp4") else "image"
                    _CACHE[key] = (p, kind)
                    print("[assets] %s → 前缀匹配 %s" % (key, f), flush=True)
                    return _CACHE[key]
    # 绝对兜底
    hint = key
    fb = SAFE_FALLBACK["cool"]
    if any(k in hint for k in ("dash", "engine", "ev_", "wheel", "bump")):
        fb = SAFE_FALLBACK["engine"] if "engine" in hint or "ev_" in hint else SAFE_FALLBACK["warm"]
    if any(k in hint for k in ("interior", "mirror", "puddle", "rain")):
        fb = SAFE_FALLBACK["interior"]
    p = os.path.join(STOCK, fb)
    print("[assets] !! %s 无可用素材，兜底 %s" % (key, fb), flush=True)
    _CACHE[key] = (p, "video")
    return _CACHE[key]


def ensure_plate(key, sec):
    """从视频素材抽一帧作为底片缓存，返回 jpg 路径。"""
    os.makedirs(PLATES, exist_ok=True)
    p, kind = resolve(key)
    if kind == "image":
        return p
    out = os.path.join(PLATES, "%s_%05.2f.jpg" % (key, sec))
    if os.path.isfile(out) and os.path.getsize(out) > 20000:
        return out
    os.makedirs(os.path.dirname(out), exist_ok=True)
    for try_sec in (sec, sec * 0.6, 1.0):
        try:
            subprocess.run([FFMPEG, "-v", "error", "-y", "-ss", "%.2f" % try_sec, "-i", p,
                            "-frames:v", "1", "-q:v", "3", out], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            continue
        if os.path.isfile(out) and os.path.getsize(out) > 5000:
            return out
    raise RuntimeError("抽帧失败: %s @ %.2fs" % (p, sec))


def probe(path):
    out = subprocess.run([FFPROBE, "-v", "error", "-show_entries",
                          "format=duration:stream=width,height,r_frame_rate,codec_name",
                          "-of", "default=noprint_wrappers=1", path],
                         capture_output=True, text=True).stdout
    info = {}
    for line in out.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            info[k] = v
    return info


def prep_plates():
    """预抽所有 PIL 场景需要的底片（避免渲染进程里并发拉 ffmpeg）。"""
    jobs = [
        ("car_interior_night", 2.0), ("car_interior_night", 5.0),
        ("car_interior_night", 8.0), ("car_interior_night", 6.0),
        ("steering_night", 1.0), ("steering_night", 7.0),
        ("car_engine", 1.0), ("car_dash", 2.0),
        ("city_night_aerial", 1.0), ("city_night_aerial", 3.0),
        ("rain_window", 2.0), ("rain_drive", 2.0), ("winding_road", 1.0),
        ("puddle_night", 1.0), ("rearview_mirror", 1.0),
    ]
    for key, sec in jobs:
        try:
            ensure_plate(key, sec)
        except Exception as e:
            print("[assets] plate 失败 %s@%.1f: %s" % (key, sec, e), flush=True)


if __name__ == "__main__":
    for k in CANDIDATES:
        print(k, "→", resolve(k))
    prep_plates()
