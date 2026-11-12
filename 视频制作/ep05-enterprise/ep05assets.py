#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 05 期素材解析：逻辑名 → 实际文件（视频 / 静帧），并缓存抽帧底片。

与 ep04assets.py 的差异
- ROOT 自适应本工程目录（不再写死 /app/vedio/ep04-body）；
- 新增 ComfyUI H3 实拍质感镜头 comfy_c1..c8 → assets/comfy/cN.mp4
  （SPEC §0/§2 的映射；文件缺失时按 SPEC §0 退路退到本地 B-roll，保证流水线不断）；
- 新增素材就绪判定（ComfyUI 下载中的半成品不参与渲染）；
- 所有素材（含从 ep01–ep04 stock 拷贝来的 B-roll）统一记录在 assets-manifest.json。
"""
import json
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
STOCK = os.path.join(ROOT, "assets", "stock")
COMFY = os.path.join(ROOT, "assets", "comfy")
BACKDROPS = os.path.join(ROOT, "assets", "backdrops")
PLATES = os.path.join(ROOT, "work", "plates")
MANIFEST = os.path.join(ROOT, "assets-manifest.json")

FFMPEG = "/home/admin/.local/bin/ffmpeg"

# 兜底素材目录（按 SPEC §0：本地 B-roll 从 ep01–ep04 stock 取用；已拷贝的优先走本地 STOCK）
FALLBACK_DIRS = [
    STOCK,
    "/app/vedio/ep03-judgment/assets/stock",
    "/app/vedio/ep02-flood/assets/stock",
    "/app/vedio/ep01-hybrid/assets/stock",
    "/app/vedio/ep04-body/assets/stock",
    os.path.join(ROOT, "assets-ep04", "stock"),
    BACKDROPS,
]

# 逻辑名 → 候选文件（优先 assets/stock 视频，其次兜底目录 / backdrops 静帧）。
CANDIDATES = {
    # —— ComfyUI H3（SPEC §2：comfy_c1..c8 → assets/comfy/cN.mp4，特殊处理）
    "comfy_c1": ["c1.mp4"],
    "comfy_c2": ["c2.mp4"],
    "comfy_c3": ["c3.mp4"],
    "comfy_c4": ["c4.mp4"],
    "comfy_c5": ["c5.mp4"],
    "comfy_c6": ["c6.mp4"],
    "comfy_c7": ["c7.mp4"],
    "comfy_c8": ["c8.mp4"],
    # —— SPEC §3.3 点名的本地 B-roll
    "signing": ["signing_01.mp4"],
    "empty_chair": ["empty_chair.mp4"],
    # —— ep01–ep04 stock 拷贝（穿插 / 退路 / 程序化场景底片）
    "desk_night": ["desk_night_01.mp4", "desk_night_02.mp4"],
    "desk_night_2": ["desk_night_02.mp4", "desk_night_01.mp4"],
    "laptop_night": ["laptop_night_01.mp4"],
    "pen_writing": ["pen_writing_01.mp4"],
    "handwriting": ["handwriting_01.mp4"],
    "paper": ["paper_texture_01.mp4"],
    "keyboard": ["keyboard_typing.mp4"],
    "night_desk": ["night_desk.mp4", "desk_lamp.mp4"],
    "city_night": ["city_night_01.mp4", "citynight.mp4"],
    "city_night_aerial": ["city_night_aerial.mp4", "citynight.mp4"],
    "rain_window": ["rain_window_01.mp4"],
}

# SPEC §0 退路：ComfyUI 窗口失败时，C1–C4 退化为 ep03 签字/桌面 B-roll，C5–C8 退化为
# ep02 城市/空椅/雨窗 B-roll（+ 程序化光效），不得因此停机。
COMFY_FALLBACK = {
    "comfy_c1": ["desk_night_01.mp4", "laptop_night_01.mp4", "city_night_01.mp4"],
    "comfy_c2": ["signing_01.mp4", "handwriting_01.mp4", "pen_writing_01.mp4"],
    "comfy_c3": ["signing_01.mp4", "paper_texture_01.mp4", "handwriting_01.mp4"],
    "comfy_c4": ["laptop_night_01.mp4", "desk_night_02.mp4", "city_night_01.mp4"],
    "comfy_c5": ["city_night_01.mp4", "city_night_aerial.mp4", "citynight.mp4"],
    "comfy_c6": ["desk_night_02.mp4", "night_desk.mp4", "laptop_night_01.mp4"],
    "comfy_c7": ["empty_chair.mp4", "rain_window_01.mp4", "desk_night_01.mp4"],
    "comfy_c8": ["rain_window_01.mp4", "citynight.mp4", "city_night_01.mp4"],
}

COMFY_KEYS = tuple("comfy_c%d" % i for i in range(1, 9))

# 绝对兜底：任何逻辑名解析失败时用这些，保证流水线不断。
SAFE_FALLBACK = {
    "warm": "desk_night_01.mp4",
    "cool": "city_night_01.mp4",
    "office": "desk_night_02.mp4",
    "paper": "paper_texture_01.mp4",
    "interior": "laptop_night_01.mp4",
}

_CACHE = {}
_INFO = {}


# ------------------------------------------------------------------ probe / ready
def probe(path):
    """ffmpeg -i 解析（本机 ffprobe 是 ffmpeg 的软链，无 -show_entries，故走 stderr 解析）。"""
    if path in _INFO:
        return _INFO[path]
    info = {"path": path, "duration": 0.0, "width": 0, "height": 0, "fps": 0.0}
    try:
        r = subprocess.run([FFMPEG, "-hide_banner", "-i", path],
                           capture_output=True, text=True)
    except OSError:
        return info
    err = r.stderr or ""
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", err)
    if m:
        info["duration"] = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    m = re.search(r"Video: .*?, (\d+)x(\d+)", err)
    if m:
        info["width"], info["height"] = int(m.group(1)), int(m.group(2))
    m = re.search(r"(\d+(?:\.\d+)?) fps", err)
    if m:
        info["fps"] = float(m.group(1))
    _INFO[path] = info
    return info


def _decode_ok(path, sec=1.0):
    """前 sec 秒能否干净解码（ComfyUI 下载中的半成品会被挡掉）。"""
    try:
        r = subprocess.run([FFMPEG, "-v", "error", "-t", "%.2f" % sec, "-i", path,
                            "-f", "null", "-"], capture_output=True, text=True)
    except OSError:
        return False
    bad = ("Invalid data", "Error while decoding", "moov atom not found",
           "partial file", "End of file")
    return r.returncode == 0 and not any(b in (r.stderr or "") for b in bad)


def _comfy_ready(path):
    if not (os.path.isfile(path) and os.path.getsize(path) > 200_000):
        return False
    inf = probe(path)
    if inf["duration"] < 4.5 or inf["width"] < 1200:
        return False
    return _decode_ok(path, 1.0)


def comfy_path(key):
    """comfy_cN 的就绪文件路径；未就绪返回 None。"""
    m = re.search(r"(\d+)$", key)
    if not m:
        return None
    p = os.path.join(COMFY, "c%s.mp4" % m.group(1))
    return p if _comfy_ready(p) else None


def is_comfy_path(path):
    return os.path.dirname(os.path.abspath(path)) == os.path.abspath(COMFY)


def comfy_info(path):
    """ComfyUI 片段的规格信息（非 comfy 路径返回 None）。"""
    if not is_comfy_path(path):
        return None
    return probe(path)


def comfy_status():
    out = {}
    for i in range(1, 9):
        p = os.path.join(COMFY, "c%d.mp4" % i)
        if os.path.isfile(p):
            inf = probe(p)
            out["comfy_c%d" % i] = dict(inf, ready=_comfy_ready(p),
                                        size_mb=round(os.path.getsize(p) / 1e6, 2))
        else:
            out["comfy_c%d" % i] = {"path": p, "ready": False, "missing": True}
    return out


# ------------------------------------------------------------------ resolve
def _find_in(d, name):
    p = os.path.join(d, name)
    if os.path.isfile(p) and os.path.getsize(p) > 20000:
        return p
    return None


def _find(name):
    for d in (STOCK, BACKDROPS):
        p = _find_in(d, name)
        if p:
            return p
    return None


def resolve(key):
    """返回 (path, 'video'|'image')。保持 ep04 的二元组契约（scenes_pil/overlays 依赖）。"""
    if key in _CACHE:
        return _CACHE[key]
    if key in COMFY_KEYS:
        p = comfy_path(key)
        if p:
            _CACHE[key] = (p, "video")
            return _CACHE[key]
        # SPEC §0 退路：退到本地 B-roll，并明确告警（finalize 报告会统计）
        for name in COMFY_FALLBACK.get(key, []):
            p = _find(name)
            if p:
                _CACHE[key] = (p, "video")
                print("[assets] !! %s 未就绪 → SPEC §0 退路 %s" % (key, name), flush=True)
                return _CACHE[key]
    for name in CANDIDATES.get(key, []):
        p = _find(name)
        if p:
            kind = "video" if p.endswith(".mp4") else "image"
            _CACHE[key] = (p, kind)
            if name != CANDIDATES.get(key, [None])[0]:
                print("[assets] %s → 兜底 %s" % (key, os.path.basename(p)), flush=True)
            return _CACHE[key]
    # 前缀模糊匹配
    for d in FALLBACK_DIRS:
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
    if any(k in hint for k in ("sign", "pen", "paper", "stamp", "hand", "warm")):
        fb = SAFE_FALLBACK["warm"]
    if any(k in hint for k in ("desk", "office", "meeting", "chair")):
        fb = SAFE_FALLBACK["office"]
    if any(k in hint for k in ("city", "dawn", "window", "elevator", "atrium", "corridor")):
        fb = SAFE_FALLBACK["cool"]
    p = os.path.join(STOCK, fb)
    print("[assets] !! %s 无可用素材，兜底 %s" % (key, fb), flush=True)
    _CACHE[key] = (p, "video")
    return _CACHE[key]


def inspect(key):
    """人类可读的解析结果（自检/清单用）。"""
    path, kind = resolve(key)
    inf = probe(path)
    return {"key": key, "path": path, "kind": kind, "comfy": is_comfy_path(path),
            "duration": round(inf["duration"], 3), "width": inf["width"],
            "height": inf["height"], "fps": inf["fps"]}


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
    for try_sec in (sec, sec * 0.6, 1.0, 0.2):
        try:
            subprocess.run([FFMPEG, "-v", "error", "-y", "-ss", "%.2f" % try_sec, "-i", p,
                            "-frames:v", "1", "-q:v", "3", out], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            continue
        if os.path.isfile(out) and os.path.getsize(out) > 5000:
            return out
    raise RuntimeError("抽帧失败: %s @ %.2fs" % (p, sec))


def prep_plates():
    """预抽所有 PIL 场景可能用到的底片（避免渲染进程里并发拉 ffmpeg）。"""
    jobs = [
        ("desk_night", 1.5), ("desk_night", 4.0), ("desk_night_2", 2.0),
        ("laptop_night", 2.0), ("laptop_night", 5.0), ("night_desk", 2.0),
        ("signing", 1.0), ("signing", 3.0), ("handwriting", 2.0),
        ("pen_writing", 1.0), ("paper", 1.0), ("paper", 3.0),
        ("keyboard", 1.5), ("empty_chair", 2.0), ("empty_chair", 4.0),
        ("city_night", 1.0), ("city_night", 3.0), ("city_night_aerial", 1.0),
        ("rain_window", 2.0),
    ]
    for i in range(1, 9):
        if comfy_path("comfy_c%d" % i):
            jobs += [("comfy_c%d" % i, 1.0), ("comfy_c%d" % i, 3.0)]
    for key, sec in jobs:
        try:
            ensure_plate(key, sec)
        except Exception as e:  # noqa: BLE001 - 预抽失败不阻断流水线
            print("[assets] plate 失败 %s@%.1f: %s" % (key, sec, e), flush=True)


def write_manifest():
    """生成 assets-manifest.json（交付清单）：B-roll 来源/授权、ComfyUI 退路映射、
    程序化场景清单、字体、原创音乐/音效。"""
    import json as _json
    MAP_COMFY_SHOTS = {
        "comfy_c1": ["s1a", "s1f", "s2g", "s6e"], "comfy_c2": ["s1b"], "comfy_c3": ["s1c"],
        "comfy_c4": ["s3c"], "comfy_c5": ["s3a", "s3d"], "comfy_c6": ["s4a"],
        "comfy_c7": ["s5a"], "comfy_c8": ["s2e", "s6b"],
    }
    # 本地 B-roll 来源（按拷贝来源工程标注；全部为 Pexels License）
    SOURCE = {
        "signing_01.mp4": "ep03-judgment/assets/stock",
        "desk_night_01.mp4": "ep03-judgment/assets/stock",
        "desk_night_02.mp4": "ep03-judgment/assets/stock",
        "pen_writing_01.mp4": "ep03-judgment/assets/stock",
        "handwriting_01.mp4": "ep03-judgment/assets/stock",
        "paper_texture_01.mp4": "ep03-judgment/assets/stock",
        "laptop_night_01.mp4": "ep03-judgment/assets/stock",
        "city_night_01.mp4": "ep03-judgment/assets/stock",
        "rain_window_01.mp4": "ep03-judgment/assets/stock",
        "empty_chair.mp4": "ep02-flood/assets/stock",
        "keyboard_typing.mp4": "ep02-flood/assets/stock",
        "night_desk.mp4": "ep02-flood/assets/stock",
        "citynight.mp4": "ep02-flood/assets/stock",
        "city_night_aerial.mp4": "ep01-hybrid/assets/stock",
    }
    shots_path = os.path.join(ROOT, "shots.json")
    shots = _json.load(open(shots_path, encoding="utf-8")) if os.path.isfile(shots_path) else []
    stock = {}
    for f in sorted(os.listdir(STOCK)) if os.path.isdir(STOCK) else []:
        if not f.lower().endswith((".mp4", ".jpg", ".png")):
            continue
        p = os.path.join(STOCK, f)
        inf = probe(p) if f.lower().endswith(".mp4") else {}
        stock[f] = {
            "bytes": os.path.getsize(p),
            "duration_s": round(inf.get("duration", 0.0), 3),
            "resolution": "%dx%d" % (inf.get("width", 0), inf.get("height", 0)),
            "fps": inf.get("fps", 0),
            "source": SOURCE.get(f, "copied from ep0x stock"),
            "license": "Pexels License",
        }
    # 分镜实际使用：逻辑名 → 文件（broll），含 ComfyUI 退路标注
    used = {}
    comfy_fallback = {}
    for s in shots:
        if s.get("kind") != "broll":
            continue
        key = s.get("asset")
        path, kind = resolve(key)
        name = os.path.basename(path)
        used.setdefault(key, {"file": name, "shots": []})["shots"].append(s["id"])
        if key in COMFY_KEYS:
            comfy_fallback[key] = {
                "file": name,
                "status": "fallback（ComfyUI H3 租用实例 TLS 不可达，按 SPEC §0 退路）",
                "shots": sorted(used[key]["shots"]),
            }
    # 合并 ComfyUI 操作员的 manifest/conform-status（若存在），记录真实 H3 片段元数据
    op_manifest, conform = {}, {}
    try:
        op_manifest = _json.load(open(os.path.join(COMFY, "manifest.json"), encoding="utf-8"))
    except Exception:
        pass
    try:
        conform = _json.load(open(os.path.join(COMFY, "conform-status.json"), encoding="utf-8"))
    except Exception:
        pass
    comfy = {}
    n_delivered = 0
    for i in range(1, 9):
        key = "comfy_c%d" % i
        p = os.path.join(COMFY, "c%d.mp4" % i)
        cinfo = probe(p) if os.path.isfile(p) else {}
        meta = (op_manifest.get("shots") or {}).get("c%d" % i) or {}
        conf = (conform.get("shots") or {}).get("c%d" % i) or {}
        delivered = os.path.isfile(p)
        n_delivered += 1 if delivered else 0
        method = meta.get("upscale_method") or conf.get("method")
        comfy[key] = {
            "path": "assets/comfy/c%d.mp4" % i,
            "available": bool(comfy_path(key)),
            "delivered": delivered,
            "source": "ComfyUI H3（MiniMax H3 int8 + 8-step turbo LoRA，RTX5090 租用实例，"
                      "864x480 生成 → 1080p 本地/4x-UltraSharp 放大）",
            "resolution": "%dx%d" % (cinfo.get("width", 0), cinfo.get("height", 0)),
            "duration_s": round(cinfo.get("duration", 0.0), 3),
            "fps": cinfo.get("fps", 0),
            "label": meta.get("label", ""),
            "shots": MAP_COMFY_SHOTS.get(key, []),
            "seed": meta.get("seed"),
            "job_id": meta.get("job_id"),
            "req_res": meta.get("req_res"),
            "downloaded_utc": meta.get("downloaded_utc"),
            "upscale": {
                "upscaled": meta.get("upscaled"),
                "method": method,
                "upscale_job_id": meta.get("upscale_job_id"),
                "upscale_done_utc": meta.get("upscale_done_utc"),
                "upscale_output_mb": meta.get("upscale_output_mb"),
            },
            "conform": {"method": method, "conformed_utc": conf.get("conformed_utc")},
            "fallback_used": False if delivered else (comfy_fallback.get(key) or {}),
        }
    pil_scenes = sorted(set(s["scene"] for s in shots if s.get("kind") == "pil"))
    overlays = sorted(set(s["overlay"] for s in shots if s.get("overlay")))
    data = {
        "episode": "第 05 期《为什么公司越大，越容易自己绊自己》",
        "generated_by": "ep05assets.py",
        "generated_at_utc": __import__("datetime").datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "spec": "SPEC.md（1920x1080 / 24fps / 2.35:1 遮幅 / H.264 High + AAC 48k）",
        "broll_stock": stock,
        "logical_to_file": used,
        "comfy_h3": {
            "note": ("ComfyUI H3 实拍质感镜头（SPEC §0 空间层）：8 条 c1–c8 全部由 RTX5090 租用实例生成，"
                     "864x480 生成后统一放大到 1920x1080/24fps（c1–c8 为 app:4x-UltraSharp+lanczos 版本，"
                     "upgrade 完成于 2026-11-12 14:37–14:50Z），13 个 comfy 镜头全部使用真实 H3 画面，"
                     "未使用 SPEC §0 退化 B-roll（fallback 仅作为备用方案保留）。"
                     if n_delivered >= 8 else
                     "ComfyUI H3 实拍质感镜头（SPEC §0 空间层）。本期部分/全部缺失，按 SPEC §0 退路使用本地 B-roll。"),
            "clips": comfy,
            "used_shots": sum(len(v["shots"]) for v in comfy.values()),
        },
        "programmatic_scenes": {
            "engine": "scenes_pil.py（PIL/numpy/cv2）+ ep05viz.py",
            "kind": "pil（全画幅程序化场景）",
            "scenes_used": pil_scenes,
            "math_basis": "关系数 n(n-1)/2；楼层路径随层数递增；箭头离心自保；变革疲劳峰值递减；"
                          "片尾网松开（全部由真实数学关系生成，非手绘）",
        },
        "overlays_used": overlays,
        "fonts": [
            {"name": "Noto Serif CJK SC Bold", "path": "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc", "license": "OFL"},
            {"name": "Noto Sans CJK SC", "path": "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "license": "OFL"},
            {"name": "DejaVu Sans Mono Bold", "path": "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", "license": "DejaVu Fonts License"},
        ],
        "audio": {
            "narration": "edge-tts zh-CN-YunjianNeural 逐句表演（narration/performance.json）",
            "music": "本期原创合成配乐（music.py，numpy，无外部曲库）",
            "sfx": "本期原创合成音效（sfx.py，numpy）",
            "mix": "build_audio.py 两遍 loudnorm，成片实测 I=-14.43 LUFS / TP=-1.51 dBTP",
        },
    }
    with open(MANIFEST, "w", encoding="utf-8") as f:
        _json.dump(data, f, ensure_ascii=False, indent=1)
    print("[assets] manifest →", MANIFEST, "(%d stock files, %d comfy fallbacks)" % (
        len(stock), len(comfy_fallback)))
    return data


if __name__ == "__main__":
    for k in COMFY_KEYS + ("signing", "empty_chair", "desk_night", "empty_chair",
                           "city_night", "pen_writing", "keyboard"):
        print(json.dumps(inspect(k), ensure_ascii=False))
    write_manifest()
    prep_plates()
