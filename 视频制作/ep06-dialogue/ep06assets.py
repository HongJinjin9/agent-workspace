#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 06 期素材解析：逻辑名 → 实际文件（视频 / 静帧），并缓存抽帧底片。

角色：N 旁白 / M 老规矩（手册方）/ L 小账本（账本方）；素材来源：
- ComfyUI H3 角色/物件镜头 comfy_c1..c14 → assets/comfy/cN.mp4（SPEC §1；缺则按 SPEC §0 退路）；
- 本地 B-roll：ep03（手册/纸张/笔/桌面/署名/放大镜）、ep05（借 c4 电梯 / c6 会议桌 / c8 百叶窗，
  城市）、ep02（空椅/键盘/夜桌/台灯/城市）——全部 Pexels License，拷贝进 assets/stock/ 并记录；
- 程序化场景（scenes_pil.py）与叠加层（overlays.py）不入本模块，见 ep06viz.py / scenes_pil.py。
"""
import json
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
STOCK = os.path.join(ROOT, "assets", "stock")
COMFY = os.path.join(ROOT, "assets", "comfy")
STILLS = os.path.join(ROOT, "assets", "comfy-stills")
AGNES = os.path.join(ROOT, "assets", "agnes")
BACKDROPS = os.path.join(ROOT, "assets", "backdrops")
PLATES = os.path.join(ROOT, "work", "plates")
MANIFEST = os.path.join(ROOT, "assets-manifest.json")

FFMPEG = "/home/admin/.local/bin/ffmpeg"

# 兜底素材目录（本地 B-roll 从 ep0x stock 取用；已拷贝的优先走本地 STOCK）
FALLBACK_DIRS = [
    STOCK,
    "/app/vedio/ep03-judgment/assets/stock",
    "/app/vedio/ep05-enterprise/assets/stock",
    "/app/vedio/ep02-flood/assets/stock",
    "/app/vedio/ep04-body/assets/stock",
    BACKDROPS,
]

COUNT_COMFY = 14

# 逻辑名 → 候选文件
CANDIDATES = {
    # —— ComfyUI H3 角色/物件镜头（SPEC §1 C1–C14）
    **{"comfy_c%d" % i: ["c%d.mp4" % i] for i in range(1, COUNT_COMFY + 1)},
    # —— ep03 手册/纸张/笔/桌面母题
    "old_books": ["old_books_01.mp4"],
    "paper": ["paper_texture_01.mp4"],
    "pen_writing": ["pen_writing_01.mp4"],
    "signing": ["signing_01.mp4"],
    "desk_night": ["desk_night_01.mp4", "desk_night_02.mp4"],
    "desk_night_2": ["desk_night_02.mp4", "desk_night_01.mp4"],
    "magnifier": ["magnifier_01.mp4"],
    "handwriting": ["handwriting_01.mp4"],
    "laptop_night": ["laptop_night_01.mp4"],
    "city_night": ["city_night_01.mp4", "citynight.mp4"],
    "rain_window": ["rain_window_01.mp4"],
    # —— ep02 空镜
    "empty_chair": ["empty_chair.mp4"],
    "keyboard": ["keyboard_typing.mp4"],
    "night_desk": ["night_desk.mp4"],
    "desk_lamp": ["desk_lamp.mp4"],
    "citynight": ["citynight.mp4"],
    # —— ep05 借用的 H3 镜头（电梯/会议桌/百叶窗）与城市航拍
    "ep05_elevator": ["ep05_elevator.mp4"],
    "ep05_meeting": ["ep05_meeting.mp4"],
    "ep05_blinds": ["ep05_blinds.mp4"],
    "city_aerial": ["city_aerial.mp4"],
}

# SPEC §0 退路：ComfyUI 失败/缺片时，C 系列退到本地 B-roll，不得停机。
COMFY_FALLBACK = {
    "comfy_c1": ["ep05_meeting.mp4", "desk_night_02.mp4", "night_desk.mp4"],
    "comfy_c2": ["old_books_01.mp4", "desk_night_01.mp4", "paper_texture_01.mp4"],
    "comfy_c3": ["signing_01.mp4", "paper_texture_01.mp4", "handwriting_01.mp4"],
    "comfy_c4": ["laptop_night_01.mp4", "keyboard_typing.mp4", "night_desk.mp4"],
    "comfy_c5": ["signing_01.mp4", "paper_texture_01.mp4", "handwriting_01.mp4"],
    "comfy_c6": ["old_books_01.mp4", "paper_texture_01.mp4", "pen_writing_01.mp4"],
    "comfy_c7": ["ep05_meeting.mp4", "desk_night_02.mp4", "night_desk.mp4"],
    "comfy_c8": ["laptop_night_01.mp4", "keyboard_typing.mp4", "magnifier_01.mp4"],
    "comfy_c9": ["pen_writing_01.mp4", "handwriting_01.mp4", "paper_texture_01.mp4"],
    "comfy_c10": ["signing_01.mp4", "paper_texture_01.mp4", "old_books_01.mp4"],
    "comfy_c11": ["paper_texture_01.mp4", "old_books_01.mp4", "desk_night_02.mp4"],
    "comfy_c12": ["old_books_01.mp4", "pen_writing_01.mp4", "paper_texture_01.mp4"],
    "comfy_c13": ["ep05_meeting.mp4", "empty_chair.mp4", "citynight.mp4"],
    "comfy_c14": ["ep05_meeting.mp4", "desk_night_02.mp4", "night_desk.mp4"],
}

COMFY_KEYS = tuple("comfy_c%d" % i for i in range(1, COUNT_COMFY + 1))

# 绝对兜底
SAFE_FALLBACK = {
    "warm": "desk_night_01.mp4",
    "cool": "desk_night_02.mp4",
    "paper": "paper_texture_01.mp4",
    "office": "ep05_meeting.mp4",
    "interior": "night_desk.mp4",
}

_CACHE = {}
_INFO = {}


# ------------------------------------------------------------------ probe / ready
def probe(path):
    """ffmpeg -i 解析（本机 ffprobe 是 ffmpeg 软链，无 -show_entries）。"""
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
    m = re.search(r"(\d+)$", key)
    if not m:
        return None
    p = os.path.join(COMFY, "c%s.mp4" % m.group(1))
    return p if _comfy_ready(p) else None


def comfy_still_path(key):
    """H3 视频未到时的 AI 静态图兜底：assets/comfy-stills/cN.jpg(.png) 或 assets/agnes/cN.png
    （china-aigc agnes t2i，aigc-stills agent 产出）。"""
    m = re.search(r"(\d+)$", key)
    if not m:
        return None
    for d in (STILLS, AGNES):
        for ext in (".jpg", ".png"):
            p = os.path.join(d, "c%s%s" % (m.group(1), ext))
            if os.path.isfile(p) and os.path.getsize(p) > 20000:
                return p
    return None


def comfy_stills_status():
    out = {}
    for i in range(1, COUNT_COMFY + 1):
        p = comfy_still_path("comfy_c%d" % i)
        out["comfy_c%d" % i] = {"path": p, "available": bool(p),
                                "bytes": os.path.getsize(p) if p else 0}
    return out


def is_comfy_path(path):
    return os.path.dirname(os.path.abspath(path)) == os.path.abspath(COMFY)


def comfy_info(path):
    if not is_comfy_path(path):
        return None
    return probe(path)


def comfy_status():
    out = {}
    for i in range(1, COUNT_COMFY + 1):
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
    """返回 (path, 'video'|'image')。保持 ep04/ep05 的二元组契约。"""
    if key in _CACHE:
        return _CACHE[key]
    if key in COMFY_KEYS:
        p = comfy_path(key)
        if p:
            _CACHE[key] = (p, "video")
            return _CACHE[key]
        # Lead 兜底：H3 视频未到时用 AI 静态图（china-aigc），scene_body 用 zoompan 缓推
        sp = comfy_still_path(key)
        if sp:
            _CACHE[key] = (sp, "image")
            print("[assets] !! %s 视频未就绪 → AI 静态图兜底 %s" % (key, os.path.basename(sp)),
                  flush=True)
            return _CACHE[key]
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
    hint = key
    fb = SAFE_FALLBACK["cool"]
    if any(k in hint for k in ("sign", "pen", "paper", "stamp", "hand", "warm")):
        fb = SAFE_FALLBACK["warm"]
    if any(k in hint for k in ("desk", "office", "meeting", "chair", "table")):
        fb = SAFE_FALLBACK["office"]
    if any(k in hint for k in ("city", "window", "elevator", "conference", "dusk")):
        fb = SAFE_FALLBACK["cool"]
    p = os.path.join(STOCK, fb)
    print("[assets] !! %s 无可用素材，兜底 %s" % (key, fb), flush=True)
    _CACHE[key] = (p, "video")
    return _CACHE[key]


def inspect(key):
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
    """预抽程序化场景可能用到的底片。"""
    jobs = [
        ("old_books", 1.0), ("old_books", 3.0), ("paper", 1.0), ("paper", 3.0),
        ("pen_writing", 1.0), ("signing", 1.0), ("desk_night", 1.5), ("desk_night", 4.0),
        ("desk_night_2", 2.0), ("laptop_night", 2.0), ("magnifier", 1.0),
        ("night_desk", 2.0), ("ep05_meeting", 1.0), ("ep05_blinds", 2.0),
        ("city_night", 1.0), ("empty_chair", 2.0), ("rain_window", 2.0),
    ]
    for i in range(1, COUNT_COMFY + 1):
        if comfy_path("comfy_c%d" % i):
            jobs += [("comfy_c%d" % i, 1.0), ("comfy_c%d" % i, 3.0)]
    for key, sec in jobs:
        try:
            ensure_plate(key, sec)
        except Exception as e:  # noqa: BLE001
            print("[assets] plate 失败 %s@%.1f: %s" % (key, sec, e), flush=True)


# ------------------------------------------------------------------ manifest
SOURCE = {
    "old_books_01.mp4": "ep03-judgment/assets/stock",
    "paper_texture_01.mp4": "ep03-judgment/assets/stock",
    "pen_writing_01.mp4": "ep03-judgment/assets/stock",
    "signing_01.mp4": "ep03-judgment/assets/stock",
    "desk_night_01.mp4": "ep03-judgment/assets/stock",
    "desk_night_02.mp4": "ep03-judgment/assets/stock",
    "magnifier_01.mp4": "ep03-judgment/assets/stock",
    "handwriting_01.mp4": "ep03-judgment/assets/stock",
    "laptop_night_01.mp4": "ep03-judgment/assets/stock",
    "city_night_01.mp4": "ep03-judgment/assets/stock",
    "rain_window_01.mp4": "ep03-judgment/assets/stock",
    "empty_chair.mp4": "ep02-flood/assets/stock",
    "keyboard_typing.mp4": "ep02-flood/assets/stock",
    "night_desk.mp4": "ep02-flood/assets/stock",
    "desk_lamp.mp4": "ep02-flood/assets/stock",
    "citynight.mp4": "ep02-flood/assets/stock",
    "ep05_meeting.mp4": "ep05-enterprise/assets/comfy/c6.mp4（借用 H3 会议桌镜头）",
    "ep05_elevator.mp4": "ep05-enterprise/assets/comfy/c4.mp4（借用 H3 电梯镜头）",
    "ep05_blinds.mp4": "ep05-enterprise/assets/comfy/c8.mp4（借用 H3 百叶窗光）",
    "city_aerial.mp4": "ep05-enterprise/assets/stock",
}


def write_manifest():
    """生成 assets-manifest.json（交付清单）。"""
    import json as _json
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
    # 分镜实际使用：逻辑名 → 文件（broll）
    used = {}
    for s in shots:
        if s.get("kind") != "broll":
            continue
        key = s.get("asset")
        path, kind = resolve(key)
        name = os.path.basename(path)
        used.setdefault(key, {"file": name, "shots": []})["shots"].append(s["id"])
    # 合并 operator manifest/conform-status（真实 H3 元数据）
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
    for i in range(1, COUNT_COMFY + 1):
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
                      "864x480 生成 → 1080p 放大）",
            "resolution": "%dx%d" % (cinfo.get("width", 0), cinfo.get("height", 0)),
            "duration_s": round(cinfo.get("duration", 0.0), 3),
            "fps": cinfo.get("fps", 0),
            "label": meta.get("label", ""),
            "shots": sorted(used.get(key, {}).get("shots", [])),
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
            "still_fallback": os.path.basename(comfy_still_path(key) or "") or None,
            "fallback_used": False if delivered else (
                {"file": os.path.basename(comfy_still_path(key) or "")} if comfy_still_path(key)
                else (used.get(key, {}) or {"file": (COMFY_FALLBACK.get(key) or [None])[0]})),
        }
    pil_scenes = sorted(set(s["scene"] for s in shots if s.get("kind") == "pil"))
    overlays = []
    for s in shots:
        ov = s.get("overlay") or s.get("overlays")
        if not ov:
            continue
        overlays += ov if isinstance(ov, list) else [ov]
    data = {
        "episode": "第 06 期《他们说，这是最糟糕的方案》",
        "generated_by": "ep06assets.py",
        "generated_at_utc": __import__("datetime").datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "spec": "SPEC.md（1920x1080 / 24fps / 2.35:1 遮幅 / H.264 High + AAC 48k）",
        "characters": {
            "note": "两位角色（老规矩 M / 小账本 L）均为 AI 生成的虚构形象，不代表、不模拟、不影射任何真实人物；"
                    "正脸不清晰（侧影/背影/过肩/手部），引述均由旁白转述并标注时间出处。",
            "voices": "N=zh-CN-YunjianNeural（旁白）/ M=zh-CN-YunyangNeural（老规矩）/ L=zh-CN-XiaoxiaoNeural（小账本）",
        },
        "broll_stock": stock,
        "logical_to_file": used,
        "comfy_stills": comfy_stills_status(),
        "stills_dirs": ["assets/comfy-stills", "assets/agnes"],
        "comfy_h3": {
            "note": ("ComfyUI H3 角色/物件镜头（SPEC §1 C1–C14）：%d/14 条交付，864x480 生成后统一放大到 "
                     "1920x1080/24fps；缺失条目按 SPEC §0 使用本地 B-roll 退路。") % n_delivered,
            "clips": comfy,
            "used_shots": sum(len(v["shots"]) for v in comfy.values()),
        },
        "programmatic_scenes": {
            "engine": "scenes_pil.py（PIL/numpy/cv2）+ ep06viz.py",
            "kind": "pil（全画幅程序化场景）",
            "scenes_used": pil_scenes,
            "math_basis": "柱状条高度严格 ∝ 销量（13438/12445，差值 993）；份额/销量曲线与同比数据按乘联会口径；"
                          "引述卡打字机逐字 + 时间出处小字；片尾双声明卡",
        },
        "overlays_used": sorted(set(overlays)),
        "fonts": [
            {"name": "Noto Serif CJK SC Bold", "path": "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc", "license": "OFL"},
            {"name": "Noto Sans CJK SC", "path": "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "license": "OFL"},
            {"name": "DejaVu Sans Mono Bold", "path": "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", "license": "DejaVu Fonts License"},
        ],
        "audio": {
            "narration": "edge-tts 三声部逐句表演（narration/performance.json：N/M/L 音色 + 逐句 rate/pitch/pause）",
            "music": "本期原创合成配乐（music.py，numpy；单一主题变奏：低音提琴→脉冲→大调→单音钢琴→再现）",
            "sfx": "本期原创合成音效（sfx.py，numpy；翻页/盖章/笔尖/点击 ≤6 处）",
            "mix": "build_audio.py 两遍 loudnorm，成片目标 I=-14 LUFS / TP≤-1.0 dBTP",
        },
    }
    with open(MANIFEST, "w", encoding="utf-8") as f:
        _json.dump(data, f, ensure_ascii=False, indent=1)
    print("[assets] manifest →", MANIFEST, "(%d stock files, %d/14 comfy)"
          % (len(stock), n_delivered))
    return data


if __name__ == "__main__":
    for k in COMFY_KEYS + ("old_books", "paper", "pen_writing", "signing", "ep05_meeting"):
        print(json.dumps(inspect(k), ensure_ascii=False))
    write_manifest()
    prep_plates()
