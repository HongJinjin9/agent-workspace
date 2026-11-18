#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 08 期素材解析：H3 逻辑名 → assets/h3 实拍片段（缺失时返回 None，由渲染器降级代码）。"""
import json
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
H3 = os.path.join(ROOT, "assets", "h3")
MANIFEST = os.path.join(H3, "manifest.json")
FFMPEG = "/home/admin/.local/bin/ffmpeg"

_CACHE = {}
_INFO = {}


def probe(path):
    if path in _INFO:
        return _INFO[path]
    info = {"path": path, "duration": 0.0, "width": 0, "height": 0, "fps": 0.0}
    try:
        r = subprocess.run([FFMPEG, "-hide_banner", "-i", path], capture_output=True, text=True)
    except OSError:
        return info
    e = r.stderr or ""
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", e)
    if m:
        info["duration"] = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    m = re.search(r"Video: .*?, (\d+)x(\d+)", e)
    if m:
        info["width"], info["height"] = int(m.group(1)), int(m.group(2))
    m = re.search(r"(\d+(?:\.\d+)?) fps", e)
    if m:
        info["fps"] = float(m.group(1))
    _INFO[path] = info
    return info


def _decode_ok(path, sec=1.0):
    try:
        r = subprocess.run([FFMPEG, "-v", "error", "-t", "%.2f" % sec, "-i", path,
                            "-f", "null", "-"], capture_output=True, text=True)
    except OSError:
        return False
    bad = ("Invalid data", "Error while decoding", "moov atom not found", "partial file")
    return r.returncode == 0 and not any(b in (r.stderr or "") for b in bad)


def ready(path):
    if not (os.path.isfile(path) and os.path.getsize(path) > 200000):
        return False
    inf = probe(path)
    if inf["duration"] < 4.2 or inf["width"] < 1200:
        return False
    r = subprocess.run([FFMPEG, "-v", "error", "-i", path, "-f", "null", "-"],
                       capture_output=True, text=True)
    return not (r.stderr or "").strip()


def h3_path(key):
    """逻辑名 h3_S02 → assets/h3/S02.mp4（优先）或 H02.mp4（兼容 PLAN 命名）。"""
    m = re.search(r"([SH])(\d+)$", key)
    if not m:
        return None
    num = int(m.group(2))
    cands = [os.path.join(H3, "S%02d.mp4" % num), os.path.join(H3, "H%02d.mp4" % num)]
    for p in cands:
        if ready(p):
            return p
    return None


def resolve(key):
    """返回 (path, kind) 或 (None, None)。kind 目前恒为 'video'。"""
    if key in _CACHE:
        return _CACHE[key]
    if key.startswith("h3_"):
        p = h3_path(key)
        _CACHE[key] = (p, "video" if p else None)
        return _CACHE[key]
    _CACHE[key] = (None, None)
    return _CACHE[key]


def h3_status():
    out = {}
    for p in sorted(os.listdir(H3)) if os.path.isdir(H3) else []:
        if p.endswith(".mp4"):
            full = os.path.join(H3, p)
            out[p] = dict(probe(full), ready=ready(full))
    return out


def load_manifest():
    if os.path.isfile(MANIFEST):
        try:
            return json.load(open(MANIFEST, encoding="utf-8"))
        except Exception:
            return {}
    return {}


def summary(timeline):
    """统计成片中 H3 可用/降级镜头（供渲染报告）。"""
    used, fallback = [], []
    for sh in timeline["shots"]:
        if not sh.get("h3"):
            continue
        p, _ = resolve(sh["asset"])
        (used if p else fallback).append(sh["id"])
    return {"h3_used": used, "h3_fallback": fallback,
            "h3_share_planned": timeline.get("h3_share")}
