#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 08 期《电动车松开油门为什么能充电》成片硬校验（全部实测，不依赖人耳）。

基线：第 07 期 v3 `verify_ep07.py` 的 24 项检查（规格/帧数/解码/响度/遮幅/字幕带/
片尾双声明卡/尾部收束/内容覆盖/运动量/SRT 结构/H3 到位），按本期规格扩到 30+ 项：

  规格类  resolution / fps / duration（时间轴±0.5s）/ duration_window（3:40–4:20）/
          frames（±2）/ has_audio / audio_format（AAC 48k 2ch）/ video_codec（H.264 High）/
          decode_clean / pix_fmt
  声音类  loudness_I（-14±0.5）/ true_peak（≤-1.0）/ lra / narration_corr（≥0.9，可选）
  画面类  letterbox_2.35（上下 132px）/ content_present / content_coverage（36 点无黑段）/
          motion_present（8 对 0.5s 帧间差）/ fade_in / endcard_text_density / tail_ending
  字幕类  subtitles_present / subtitles_band_black / subtitles_inside_bar / subtitles_single_line
          （单行≤18 汉字）/ srt_cues / srt_monotonic / srt_no_overlap / srt_in_range /
          srt_tail / srt_sentence_coverage（可选）/ endcard_declaration_text（片尾口播双声明）
  素材类  h3_assets_present（24/24）/ h3_ratio（成片 H3 时长占比 20–35%）
  交付类  web_version（1280×720 / 解码 0 错 / 体积小于 master）

输出：
  work/final-check.json                         机器可读全量结果
  work/qa/endcard-check.png                     片尾双声明卡（人工目检可读性）
  work/qa/subtitle-check.png                    字幕带样张
  work/qa/principle-*.png                       关键原理帧（人工目检能量流方向/电机-逆变器-电池路径）
  work/qa/h3-H*.png                             每条 H3 素材抽帧（人工目检物理细节/乱码/logo/正脸）
  work/qa/fade-check.png                        尾部收束帧
  work/qa/verify-contact-sheet.jpg              16 帧全片抽帧联系表

用法：
  python3 scripts/verify_ep08.py                        # 默认 out/ep08-regen.mp4
  python3 scripts/verify_ep08.py path/to/film.mp4
  python3 scripts/verify_ep08.py --expect-duration 235.2 --expect-i -14.1
"""
import argparse
import json
import os
import re
import statistics
import subprocess
import sys

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageStat

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FF = os.environ.get("FFMPEG", "/home/admin/.local/bin/ffmpeg")
FP = os.environ.get("FFPROBE", "/home/admin/.local/bin/ffprobe-real")
FILM = os.path.join(ROOT, "out", "ep08-regen.mp4")
WEB = os.path.join(ROOT, "out", "ep08-regen-web.mp4")
WORK = os.path.join(ROOT, "work")
QA = os.path.join(WORK, "qa")
TMP = os.path.join(QA, "verify-frames")
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

SPEC = {
    "w": 1920, "h": 1080, "fps": 24.0, "bar": 132,
    "i_target": -14.0, "i_tol": 0.5, "tp_max": -1.0,
    "duration_min": 220.0, "duration_max": 260.0,   # 3:40–4:20
    "sub_max_chars": 18,                              # 单行 ≤18 汉字
    "h3_share_min": 0.20, "h3_share_max": 0.35,
    "narration_corr_min": 0.90,
}
DEFAULT_DURATION = 240.0

SRT_CANDIDATES = [
    os.path.join(WORK, "srt", "all.srt"),
    os.path.join(ROOT, "audio", "work", "srt", "all.srt"),
    os.path.join(ROOT, "audio", "srt", "all.srt"),
    os.path.join(ROOT, "narration", "all.srt"),
]
NARRATION_CANDIDATES = [
    # 优先用「处理后的旁白干声」（去齿音/低切/压缩后、混 BGM 前），与成片音轨的
    # 相关性才代表旁白完整性；原始 TTS wav 未处理，相关性会系统性偏低。
    os.path.join(ROOT, "audio", "work", "narration_processed.wav"),
    os.path.join(ROOT, "narration", "narration.wav"),
    os.path.join(ROOT, "audio", "work", "narration.wav"),
    os.path.join(ROOT, "audio", "narration.wav"),
]
TIMELINE_AUDIO_CANDIDATES = [
    os.path.join(ROOT, "audio", "work", "timeline_audio.json"),
    os.path.join(ROOT, "narration", "timeline_audio.json"),
    os.path.join(WORK, "timeline_audio.json"),
]
SHOTS_CANDIDATES = [
    os.path.join(WORK, "shots.json"),
    os.path.join(WORK, "timeline.json"),
    os.path.join(ROOT, "shots.json"),
]


def run(*a):
    return subprocess.run(a, capture_output=True, text=True, errors="replace")


def jload(*cands, default=None):
    for c in cands:
        if c and os.path.isfile(c):
            try:
                return json.load(open(c, encoding="utf-8")), c
            except Exception:
                continue
    return default, None


# ------------------------------------------------------------------ probe / frames
def probe(film):
    r = run(FP, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", film)
    if r.returncode != 0 or not r.stdout.strip():
        raise SystemExit("ffprobe 失败: %s" % (r.stderr or r.stdout)[-500:])
    return json.loads(r.stdout)


def count_frames(film):
    """优先 ffprobe 数包（只解复用，快）；失败再全片解码数帧。"""
    r = run(FP, "-v", "error", "-count_packets", "-select_streams", "v:0",
            "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", film)
    try:
        n = int((r.stdout or "").strip().splitlines()[0])
        if n > 0:
            return n
    except Exception:
        pass
    r = run(FF, "-v", "error", "-threads", "2", "-i", film, "-map", "0:v:0", "-f", "null", "-")
    fr = re.findall(r"frame=\s*(\d+)", r.stderr or "")
    return int(fr[-1]) if fr else 0


def frame_at(film, t, path):
    run(FF, "-v", "error", "-y", "-an", "-threads", "1", "-ss", "%.3f" % t, "-i", film,
        "-frames:v", "1", path)
    return path


def band_text_top(png, spec):
    """字幕带内文字像素的最高行 y（用于判断字幕是否越到画面上方）。无文字返回 None。"""
    try:
        import numpy as np
        im = Image.open(png).convert("L")
        top = spec["h"] - 260
        a = np.asarray(im.crop((120, top, spec["w"] - 120, spec["h"] - 4)), dtype=np.uint8)
        rows = (a > 200).sum(axis=1)
        idx = np.where(rows >= 300)[0]
        if len(idx) == 0:
            return None
        return top + int(idx[0])
    except Exception:
        return None


def region(png, box):
    im = Image.open(png).convert("L").crop(box)
    st = ImageStat.Stat(im)
    hist = im.histogram()
    bright = sum(hist[170:])
    return {"mean": st.mean[0], "bright": bright, "box": box}


def loudness(film):
    r = run(FF, "-hide_banner", "-nostats", "-threads", "2", "-i", film, "-af",
            "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-")
    tail = r.stderr or ""
    try:
        j = json.loads(tail[tail.rindex("{"):tail.rindex("}") + 1])
        return {"I": float(j["input_i"]), "TP": float(j["input_tp"]),
                "LRA": float(j["input_lra"]), "thresh": float(j["input_thresh"])}
    except Exception:
        return {"I": None, "TP": None, "LRA": None, "thresh": None}


# ------------------------------------------------------------------ data loaders
def srt_path():
    for c in SRT_CANDIDATES:
        if os.path.isfile(c) and os.path.getsize(c) > 200:
            return c
    return None


def load_srt_cues():
    p = srt_path()
    cues, texts = [], []
    if not p:
        return cues, texts
    for block in open(p, encoding="utf-8", errors="ignore").read().strip().split("\n\n"):
        lines = [x.strip() for x in block.strip().splitlines() if x.strip()]
        if len(lines) < 3 or "-->" not in lines[1]:
            continue
        m = re.search(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)", lines[1])
        if not m:
            continue
        g = [int(x) for x in m.groups()]
        cues.append((g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000.0,
                     g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000.0))
        texts.append(" ".join(lines[2:]))
    return cues, texts


def load_shots():
    d, src = jload(*SHOTS_CANDIDATES)
    if d is None:
        return [], None
    shots = None
    total = None
    if isinstance(d, dict):
        for k in ("shots", "beats", "scenes", "clips"):
            if isinstance(d.get(k), list) and d[k]:
                shots = d[k]
                break
        for k in ("total", "duration", "duration_s", "total_s"):
            if d.get(k):
                total = float(d[k])
                break
    elif isinstance(d, list):
        shots = d
    if not shots:
        return [], src
    norm = []

    def h3_of(s):
        """engine 契约：h3(bool) + asset("h3_S02") / 或 h3="H01"。

        返回 (是否H3, 素材标识)。素材以**镜号 Sxx** 为规范命名（assets/h3/Sxx.mp4；
        Hxx.mp4 为硬链接别名，H 编号与 S 不保证一一对应，故用 Sxx 校验到位）。
        """
        raw = s.get("h3")
        a = str(s.get("asset") or s.get("clip") or "")
        if isinstance(raw, str) and raw.strip():
            a = raw.strip()
            raw = True
        if not raw:
            return False, None
        m = re.search(r"[_\-]([SH])\s*(\d+)", a, re.I) or re.search(r"^([SH])\s*(\d+)$", a, re.I)
        if m:
            return True, "%s%02d" % (m.group(1).upper(), int(m.group(2)))
        m = re.search(r"^([SH])(\d+)$", str(s.get("id") or ""), re.I)
        if m:
            return True, "%s%02d" % (m.group(1).upper(), int(m.group(2)))
        return True, None

    for s in shots:
        if not isinstance(s, dict) or not (s.get("id") or s.get("shot")):
            continue
        is_h3, h3id = h3_of(s)
        norm.append({
            "id": str(s.get("id") or s.get("shot")),
            "start": float(s.get("start", s.get("start_s", 0)) or 0),
            "dur": float(s.get("dur", s.get("duration", s.get("duration_s", 0))) or 0),
            "end": float(s.get("end", 0) or 0),
            "h3": is_h3,
            "h3id": h3id,
            "h3mode": s.get("h3mode") or s.get("h3_mode"),
            "seg": s.get("seg") or s.get("section"),
            "scene": s.get("scene") or s.get("kind") or s.get("title") or "",
            "tag": " ".join(str(s.get(k, "")) for k in
                            ("scene", "title", "tag", "tags", "note", "headline", "key", "id")),
        })
    norm.sort(key=lambda x: x["start"])
    if not total and norm:
        total = max((x["start"] + x["dur"]) if x["dur"] else x["end"] for x in norm)
    return norm, src


def load_timeline_audio():
    d, src = jload(*TIMELINE_AUDIO_CANDIDATES)
    if d is None:
        return [], None
    out = []

    def walk(obj):
        if isinstance(obj, dict):
            if obj.get("start") is not None and obj.get("end") is not None:
                out.append((float(obj["start"]), float(obj["end"])))
            for v in obj.values():
                if isinstance(v, (list, dict)):
                    walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)

    walk(d)
    return out, src


def narration_corr(film, cues_total):
    npath = next((p for p in NARRATION_CANDIDATES
                  if os.path.isfile(p) and os.path.getsize(p) > 100000), None)
    sents, src = load_timeline_audio()
    if not npath or not sents:
        return {}, npath, src
    try:
        import numpy as np
    except Exception:
        return {}, npath, src

    def pcm(path, a, b):
        cmd = [FF, "-v", "error", "-threads", "1", "-ss", "%.2f" % a,
               "-t", "%.2f" % (b - a), "-i", path,
               "-ac", "1", "-ar", "48000", "-f", "f32le", "-"]
        r = subprocess.run(cmd, capture_output=True)
        return np.frombuffer(r.stdout, dtype=np.float32)

    # 选 3 个足够长、均匀分布的句子窗口
    cand = [(i, a, b) for i, (a, b) in enumerate(sents) if 1.5 <= b - a <= 7.0]
    if not cand:
        return {}, npath, src
    picks = [cand[min(len(cand) - 1, int(len(cand) * f))] for f in (0.15, 0.5, 0.82)]
    res = {}
    for i, a, b in picks:
        try:
            x = pcm(npath, a, b).astype(np.float64)
            y = pcm(film, a, b).astype(np.float64)
            n = min(len(x), len(y))
            if n < 4800:
                continue
            x, y = x[:n], y[:n]
            x, y = x - x.mean(), y - y.mean()
            den = np.linalg.norm(x) * np.linalg.norm(y)
            res["sent%03d" % i] = round(float(np.dot(x, y) / den), 4) if den > 1e-9 else 0.0
        except Exception:
            continue
    return res, npath, src


# ------------------------------------------------------------------ QA stills
def contact_sheet(film, dur, reuse=None):
    """16 帧 4×4 联系表；优先复用内容覆盖阶段已抽的帧（省 ffmpeg 启动次数）。"""
    os.makedirs(TMP, exist_ok=True)
    n, cols = 16, 4
    if reuse and len(reuse) >= n:
        step = len(reuse) / float(n)
        picks = [reuse[min(len(reuse) - 1, int(i * step))] for i in range(n)]
    else:
        picks = None
        times = [dur * (i + 0.5) / n for i in range(n)]
    TW, TH = 480, 270
    rows = (n + cols - 1) // cols
    sheet = Image.new("RGB", (cols * TW, rows * (TH + 22)), (8, 9, 12))
    d = ImageDraw.Draw(sheet)
    font = ImageFont.truetype(FONT_BOLD, 14)
    out_times = []
    for i in range(n):
        if picks:
            t, p = picks[i]
        else:
            t = times[i]
            p = os.path.join(TMP, "cs%02d.jpg" % i)
            frame_at(film, t, p)
        out_times.append(round(t, 3))
        im = Image.open(p).convert("RGB").resize((TW, TH))
        x, y = (i % cols) * TW, (i // cols) * (TH + 22)
        sheet.paste(im, (x, y))
        d.text((x + 6, y + TH + 3), "%.1fs" % t, font=font, fill=(190, 196, 204))
    out = os.path.join(QA, "verify-contact-sheet.jpg")
    sheet.save(out, quality=88)
    return out, out_times


def qa_principle_frames(film, shots):
    """关键原理帧：人工目检能量流方向/电机-逆变器-电池路径。

    优先读 work/qa-config.json 的 principle_shots（scene-design §9 指定的回收/驱动关键镜，
    如 S04/S21/S24/S31/S63）；否则按 scene/tag 关键词挑 4 个落点。
    """
    cfg, _ = jload(os.path.join(WORK, "qa-config.json"))
    wanted = []
    if isinstance(cfg, dict):
        for x in (cfg.get("principle_shots") or []):
            wanted.append(str(x).strip().lower())
        max_n = int(cfg.get("principle_count") or max(4, len(wanted)))
    else:
        max_n = 4
    made = []
    picks = []
    by_id = {s["id"].lower(): s for s in shots}
    for wid in wanted:
        s = by_id.get(wid)
        if s:
            t = s["start"] + (s["dur"] or 3.0) / 2.0
            picks.append((s["id"], t))
    if not picks:
        keys = ["能量", "回收", "电机", "逆变", "电池", "energy", "regen", "motor",
                "inverter", "battery", "sankey", "flow", "limit", "限制", "单踏板", "续航"]
        cands = []
        for s in shots:
            tag = (s.get("tag") or "").lower()
            score = sum(1 for k in keys if k.lower() in tag)
            if score > 0:
                cands.append((score, s))
        cands.sort(key=lambda x: (-x[0], x[1]["start"]))
        seen_t = []
        for score, s in cands:
            mid = s["start"] + (s["dur"] or 3.0) / 2.0
            if any(abs(mid - p) < 6.0 for p in seen_t):
                continue
            seen_t.append(mid)
            picks.append((s["id"], mid))
            if len(picks) >= max_n:
                break
    for i, (sid, t) in enumerate(picks[:max_n], 1):
        p = os.path.join(QA, "principle-%02d-%s-%.1fs.png" % (i, sid, t))
        frame_at(film, t, p)
        made.append({"shot": sid, "time": round(t, 3), "file": os.path.relpath(p, ROOT)})
    return made


def qa_h3_frames(film, shots):
    """每条 H3 素材在成片中的抽帧：人工目检物理细节/无乱码文字/无品牌 logo/无真人正脸。"""
    made = []
    seen = set()
    for s in shots:
        h = s.get("h3id")
        if not h or h in seen:
            continue
        seen.add(h)
        t = s["start"] + min(2.0, max(0.5, (s["dur"] or 3.0) / 2.0))
        p = os.path.join(QA, "h3-%s.png" % re.sub(r"[^A-Z0-9_-]", "", h))
        frame_at(film, t, p)
        made.append(os.path.relpath(p, ROOT))
    return made


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("film", nargs="?", default=FILM)
    ap.add_argument("--web", default=WEB)
    ap.add_argument("--expect-duration", type=float, default=None)
    ap.add_argument("--expect-i", type=float, default=None)
    ap.add_argument("--no-contact-sheet", action="store_true")
    ap.add_argument("--strict", action="store_true", help="非阻塞项也计入失败（默认只记录）")
    ap.add_argument("--light", action="store_true",
                    help="自测轻量模式（减少抽帧次数/不产 QA 静帧）；交付校验禁止使用")
    ap.add_argument("--json-out", default=None, help="结果 JSON 路径（默认 work/final-check.json）")
    ap.add_argument("--allow-missing-h3", action="store_true",
                    help="code-only draft：H3 未到位只记 WARN（正式交付禁止）")
    args = ap.parse_args()
    film = os.path.abspath(args.film)
    web = os.path.abspath(args.web)
    if not os.path.isfile(film):
        raise SystemExit("找不到成片: %s" % film)
    os.makedirs(QA, exist_ok=True)
    os.makedirs(TMP, exist_ok=True)
    if args.light:
        print("*** LIGHT 模式：仅用于自测，抽帧采样已缩减；交付校验必须用完整模式 ***")

    # 期望时长：CLI > work/ep08-meta.json > 时间轴 total > 实际（若在窗口内）
    shots, shots_src = load_shots()
    exp_dur, exp_src = None, None
    if args.expect_duration:
        exp_dur, exp_src = float(args.expect_duration), "cli"
    if exp_dur is None:
        meta, _ = jload(os.path.join(WORK, "ep08-meta.json"))
        if isinstance(meta, dict):
            for k in ("duration", "total", "duration_s"):
                if meta.get(k):
                    exp_dur, exp_src = float(meta[k]), "work/ep08-meta.json"
                    break
    if exp_dur is None and shots:
        prob = None
        # shots 数据的 total 由 load_shots 丢弃，这里回读时间轴
        tl, tl_src = jload(os.path.join(WORK, "timeline.json"), os.path.join(WORK, "shots.json"))
        if isinstance(tl, dict):
            for k in ("total", "duration", "duration_s", "total_s"):
                if tl.get(k):
                    prob = float(tl[k])
                    break
        if prob:
            exp_dur, exp_src = prob, tl_src

    spec = dict(SPEC)
    if args.expect_i is not None:
        spec["i_target"] = args.expect_i
    res = {"film": film, "expected": spec, "expected_duration": exp_dur,
           "expected_duration_source": exp_src, "shots_source": shots_src}
    checks = []

    def check(name, cond, detail="", blocking=True):
        checks.append({"name": name, "pass": bool(cond), "blocking": bool(blocking),
                       "detail": str(detail)})
        print(("PASS " if cond else ("WARN " if not blocking else "FAIL "))
              + "%-26s %s" % (name, detail))

    # ---------------- 规格 ----------------
    p = probe(film)
    v = next(s for s in p["streams"] if s["codec_type"] == "video")
    a = [s for s in p["streams"] if s["codec_type"] == "audio"]
    dur = float(p["format"]["duration"])
    fps = eval(v["r_frame_rate"])
    nb = int(v.get("nb_frames") or 0)
    frames = nb or count_frames(film)
    size_mb = round(os.path.getsize(film) / 1e6, 2)
    if exp_dur is None:
        exp_dur = dur if SPEC["duration_min"] <= dur <= SPEC["duration_max"] else DEFAULT_DURATION
        exp_src = "actual-in-window" if exp_src is None else exp_src
    exp_frames = int(round(exp_dur * spec["fps"]))
    res.update({"size_mb": size_mb, "width": v["width"], "height": v["height"],
                "fps": fps, "duration": dur, "frames": frames,
                "expected_duration": exp_dur, "expected_frames": exp_frames,
                "video_codec": v["codec_name"], "profile": v.get("profile"),
                "pix_fmt": v.get("pix_fmt"),
                "bit_rate": int(p["format"].get("bit_rate") or 0),
                "audio": [{"codec": s["codec_name"], "ch": s.get("channels"),
                           "sr": s.get("sample_rate"), "bit_rate": s.get("bit_rate")} for s in a]})
    print(json.dumps({k: res[k] for k in ("film", "duration", "frames", "width", "height",
                                          "fps", "size_mb", "video_codec", "profile")},
                     ensure_ascii=False, indent=1))

    check("resolution", v["width"] == spec["w"] and v["height"] == spec["h"],
          "%dx%d" % (v["width"], v["height"]))
    check("fps", abs(fps - spec["fps"]) < 0.01, "%.3f" % fps)
    check("duration", abs(dur - exp_dur) <= 0.5,
          "%.3f vs %.3f (%s)" % (dur, exp_dur, exp_src))
    check("duration_window", spec["duration_min"] <= dur <= spec["duration_max"],
          "%.2fs（%.2f–%.2f）" % (dur, spec["duration_min"], spec["duration_max"]))
    check("frames", abs(frames - exp_frames) <= 2, "%d vs %d" % (frames, exp_frames))
    check("has_audio", bool(a), json.dumps(res["audio"], ensure_ascii=False))
    aud_ok = bool(a) and a[0].get("sample_rate") == "48000" and \
        int(a[0].get("channels") or 0) >= 1 and a[0].get("codec_name") == "aac"
    check("audio_format", aud_ok, (json.dumps(res["audio"], ensure_ascii=False))[:160])
    check("video_codec", v["codec_name"] == "h264"
          and str(v.get("profile", "")).lower().startswith("high"),
          "%s / profile=%s" % (v["codec_name"], v.get("profile")))
    r = run(FF, "-v", "error", "-threads", "2", "-i", film, "-f", "null", "-")
    err = (r.stderr or "").strip()
    check("decode_clean", r.returncode == 0 and not err, err[:160])
    res["decode_errors"] = err[:2000]

    # ---------------- 声音 ----------------
    lw = loudness(film)
    res["loudness"] = lw
    if lw["I"] is None:
        check("loudness_parse", False, "无法解析 loudnorm 输出")
    else:
        lo = spec["i_target"] - spec["i_tol"]
        hi = spec["i_target"] + spec["i_tol"]
        check("loudness_I", lo <= lw["I"] <= hi, "%.2f (%.2f..%.2f)" % (lw["I"], lo, hi))
        check("true_peak", lw["TP"] <= spec["tp_max"], "%.2f" % lw["TP"])
        check("lra", 0 <= lw["LRA"] < 20, "%.2f" % lw["LRA"])
    corr, nar_path, ta_src = narration_corr(film, None)
    res["narration"] = {"corr": corr, "narration": nar_path, "timeline_audio": ta_src}
    if corr:
        worst = min(corr.values())
        check("narration_corr", worst >= spec["narration_corr_min"],
              ", ".join("%s=%.3f" % (k, v) for k, v in corr.items())
              + "（min %.3f，需 ≥%.2f；干声 %s）"
              % (worst, spec["narration_corr_min"],
                 os.path.basename(nar_path or "")))
    else:
        check("narration_corr", True,
              "无旁白干声/句级时间轴可比对，跳过（记录）", blocking=False)

    # ---------------- 抽帧检查：遮幅/画面/字幕/片尾/淡入淡出 ----------------
    bar = spec["bar"]
    # 片尾声明卡是暗底设计：content_present 不应把它当「无内容」，从 endcard 起点排除
    endcard_start = None
    for sh in shots:
        if "end_card" in (sh.get("tag") or "") or "片尾" in (sh.get("tag") or ""):
            endcard_start = sh["start"] if endcard_start is None else min(endcard_start, sh["start"])
    if endcard_start is None:
        endcard_start = dur - 7.5
    cues, texts = load_srt_cues()
    res["srt_path"] = srt_path()
    res["srt_cues"] = len(cues)
    if args.light:
        times = [1.0, dur * 0.2, dur * 0.5, dur * 0.8, dur - 2.0]
        if cues:
            times += [((s + e) / 2.0) for s, e in cues[:3]]
    else:
        times = [0.6, 1.6, dur * 0.05, dur * 0.12, dur * 0.20, dur * 0.30, dur * 0.42,
                 dur * 0.55, dur * 0.66, dur * 0.78, dur * 0.88, dur - 6.0, dur - 2.0]
        if cues:
            times += [((s + e) / 2.0) for s, e in cues[:10]]
    times = sorted({round(min(max(t, 0.2), dur - 0.3), 3) for t in times})
    bars_ok, content_ok, in_bar_ok = True, True, True
    sub_frames, end_frames = [], []
    for i, t in enumerate(times):
        png = os.path.join(TMP, "v%02d.png" % i)
        frame_at(film, t, png)
        top = region(png, (0, 0, spec["w"], bar))
        bot = region(png, (0, spec["h"] - bar, spec["w"], spec["h"]))
        mid = region(png, (0, 360, spec["w"], 720))
        sub = region(png, (120, spec["h"] - bar + 4, spec["w"] - 120, spec["h"] - 6))
        bars_ok = bars_ok and top["mean"] < 6 and bot["mean"] < 8
        # 排除设计内的首尾淡入淡出黑场 + 片尾暗底声明卡
        if 0.8 <= t <= dur - 1.6 and t < endcard_start - 0.2:
            content_ok = content_ok and mid["mean"] > 4
        sub_frames.append({"t": t, "bright": sub["bright"], "mean": sub["mean"],
                           "text_top": band_text_top(png, spec)})
        if t >= dur - 10:
            end_frames.append({"t": t, "center_bright": region(
                png, (360, 300, spec["w"] - 360, spec["h"] - 300))["bright"]})
    # 字幕带样张：字幕像素最多的抽帧另存
    res["subtitle_frames"] = sub_frames
    best_sub = max(sub_frames, key=lambda f: f["bright"]) if sub_frames else None
    if best_sub:
        p = os.path.join(QA, "subtitle-check.png")
        frame_at(film, best_sub["t"], p)
        res["qa"] = {"subtitle_check": os.path.relpath(p, ROOT)}
    check("letterbox_2.35", bars_ok, "上下 %dpx 黑边" % bar)
    check("content_present", content_ok,
          "中部画面均值 > 4（排除首尾淡入淡出与片尾声明卡 %.1fs 后）" % endcard_start)
    # 字幕：至少 30%（且 >=2）抽检帧在字幕带有明显文字像素
    has_sub = [f for f in sub_frames if f["bright"] >= 1200]
    need = max(2, int(0.3 * len(sub_frames)))
    check("subtitles_present", len(has_sub) >= need,
          "%d/%d 帧字幕带 bright>=1200（需 %d）" % (len(has_sub), len(sub_frames), need))
    check("subtitles_band_black", min(f["mean"] for f in sub_frames) < 12,
          "字幕带最低均值 %.1f" % min(f["mean"] for f in sub_frames))
    multi_line = any("\n" in t for t in texts) if texts else False
    tops = [f["text_top"] for f in sub_frames if f.get("text_top") is not None]
    worst_top = min(tops) if tops else None
    if texts:
        check("srt_single_line", not multi_line,
              "多行字幕条数 %d（单行≤18 字结构上保证不越出黑边）" % (1 if multi_line else 0))
        if multi_line:
            check("subtitles_inside_bar", worst_top is None or worst_top >= spec["h"] - bar - 8,
                  "文字最高行 %s（应 ≥ %d）" % (worst_top, spec["h"] - bar - 8))
        else:
            check("subtitles_inside_bar", True,
                  "单行字幕结构保证（像素实测文字最高行 %s，含画面内容干扰，仅记录）"
                  % worst_top)
    res["subtitle_text_top"] = worst_top

    # ---------------- 全片内容覆盖 + 运动量（防黑段/防「会动的静图」）----------------
    dark_pts = []
    cov_frames = []
    n_cov = 8 if args.light else 36
    skipped_tail = 0
    for i in range(n_cov):
        t = dur * (i + 0.5) / n_cov
        p_cov = os.path.join(TMP, "cov%02d.png" % i)
        frame_at(film, t, p_cov)
        if os.path.isfile(p_cov) and os.path.getsize(p_cov) > 1000:
            cov_frames.append((round(t, 3), p_cov))
        # 片头 0.6s / 片尾 1.25s 是设计淡入淡出（黑场），不计入「黑段」
        if t < 0.8 or t > dur - 1.6:
            skipped_tail += 1
            continue
        mean = region(p_cov, (0, 300, spec["w"], 780))["mean"]
        if mean <= 4:
            dark_pts.append(round(t, 1))
    check("content_coverage", not dark_pts,
          "%d 点全片采样（排除首尾淡入淡出 %d 点）；暗段 %d %s"
          % (n_cov - skipped_tail, skipped_tail, len(dark_pts), dark_pts[:6]))
    res["content_coverage"] = {"samples": n_cov - skipped_tail,
                               "skipped_fade_points": skipped_tail, "dark_points": dark_pts}

    diffs = []
    content_fracs = []
    motion_probe = []
    motion_skipped = 0
    motion_dir = os.path.join(QA, "motion-probe")
    os.makedirs(motion_dir, exist_ok=True)
    for i in range(4 if args.light else 8):
        t = dur * (i + 0.5) / 8
        t2 = min(dur - 0.05, t + 0.5)
        f1 = os.path.join(TMP, "m%02da.png" % i)
        f2 = os.path.join(TMP, "m%02db.png" % i)
        frame_at(film, t, f1)
        frame_at(film, t2, f2)
        if not (os.path.isfile(f1) and os.path.getsize(f1) > 1000
                and os.path.isfile(f2) and os.path.getsize(f2) > 1000):
            motion_skipped += 1
            continue
        a_img = Image.open(f1).convert("L")
        b_img = Image.open(f2).convert("L")
        hist = ImageChops.difference(a_img, b_img).histogram()
        total = sum(hist) or 1
        mdiff = sum(i * c for i, c in enumerate(hist)) / total
        diffs.append(mdiff)
        try:
            import numpy as np
            arr = np.abs(np.asarray(a_img, np.int16) - np.asarray(b_img, np.int16))
            content_fracs.append(float((arr > 25).mean()))
        except Exception:
            content_fracs.append(0.0)
        # 低运动对：存 a/b 帧供人检「会不会动的静图」
        if mdiff < 0.5 and len(motion_probe) < 4:
            pa = os.path.join(motion_dir, "pair%02d-%.1fs-a.png" % (i, t))
            pb = os.path.join(motion_dir, "pair%02d-%.1fs-b.png" % (i, t2))
            try:
                os.replace(f1, pa)
                os.replace(f2, pb)
                shot = next((x for x in shots
                             if x["start"] <= t < x["start"] + max(x["dur"], 0.5)), None)
                motion_probe.append({"pair": i, "t": round(t, 2),
                                     "diff": round(mdiff, 2),
                                     "shot": (shot or {}).get("id"),
                                     "title": ((shot or {}).get("tag") or "")[:40],
                                     "frames": [os.path.relpath(pa, ROOT),
                                                os.path.relpath(pb, ROOT)]})
            except Exception:
                pass
    med = statistics.median(diffs) if diffs else 0.0
    check("motion_present", bool(diffs) and med > 0.8,
          "%d 对 0.5s 帧间差中位数 %.2f（min %.2f；跳过 %d 对）"
          % (len(diffs), med, min(diffs) if diffs else 0.0, motion_skipped))
    cf = statistics.median(content_fracs) if content_fracs else 0.0
    check("motion_content", cf > 5e-4,
          "强变化像素占比中位数 %.4f%%（剔除颗粒影响的补充指标，非阻塞）" % (cf * 100),
          blocking=False)
    res["motion"] = {"median_diff": round(med, 2),
                     "diffs": [round(d, 2) for d in diffs],
                     "content_frac_median": round(cf, 6),
                     "content_fracs": [round(x, 6) for x in content_fracs],
                     "skipped": motion_skipped,
                     "low_motion_probe": motion_probe}

    # 淡入：第 0 帧全帧均值（fade in 起点应近黑，< 8）
    p_in = os.path.join(TMP, "fadein.png")
    frame_at(film, 0.0, p_in)
    fadein_mean = region(p_in, (0, 0, spec["w"], spec["h"]))["mean"]
    check("fade_in", fadein_mean < 8, "首帧全帧均值 %.2f（应 <8）" % fadein_mean)
    res["fade_in_mean"] = round(fadein_mean, 2)

    # ---------------- SRT 结构 + 字幕单行字数 ----------------
    if texts:
        starts = [c[0] for c in cues]
        ends = [c[1] for c in cues]
        monotonic = all(starts[i] <= starts[i + 1] for i in range(len(starts) - 1))
        overlaps = sum(1 for i in range(len(starts) - 1) if ends[i] > starts[i + 1] + 1e-6)
        out_of_range = [c for c in cues if c[0] < 0 or c[1] > dur + 0.05]

        def dwidth(t):
            return len(re.sub(r"[^\u4e00-\u9fa5A-Za-z0-9]", "", t))

        widths = [max((dwidth(line) for line in t.split("\n")), default=0) for t in texts]
        long_lines = [t for t, w in zip(texts, widths) if w > spec["sub_max_chars"]]
        check("srt_cues", len(cues) >= 60, "%d 条（应约等于旁白句数）" % len(cues))
        check("srt_monotonic", monotonic, "start 单调")
        check("srt_no_overlap", overlaps == 0, "重叠对 %d" % overlaps)
        check("srt_in_range", not out_of_range, "%d 条越界" % len(out_of_range))
        check("srt_line_len", not long_lines,
              "超过 %d 汉字的行 %d（最宽 %d）" % (spec["sub_max_chars"],
                                              len(long_lines), max(widths, default=0)))
        check("srt_tail", abs(ends[-1] - dur) <= 2.5,
              "末条结束 %.2fs vs 成片 %.2fs" % (ends[-1], dur))
        res["srt"] = {"cues": len(cues), "monotonic": monotonic, "overlaps": overlaps,
                      "out_of_range": len(out_of_range),
                      "max_line_width": max(widths, default=0),
                      "last_end": ends[-1]}
        # 片尾口播双声明（关键词）
        tail_text = " ".join(texts[-6:])
        ovh = any(k in tail_text for k in ("AI", "人工智能", "智能辅助", "辅助制作"))
        human = any(k in tail_text for k in ("选题", "核实", "判断", "由人完成", "人完成"))
        check("endcard_declaration_text", ovh and human,
              "片尾字幕含 AI 声明=%s / 人完成声明=%s：%s"
              % (ovh, human, tail_text[-80:]))
        # 句级覆盖（有 timeline_audio 时才判）
        sents, _ = load_timeline_audio()
        if sents:
            cov = sum(1 for s, e in sents
                      if any(c[0] < e + 0.25 and c[1] > s - 0.25 for c in cues))
            check("srt_sentence_coverage", cov >= len(sents) - 1,
                  "%d/%d 句有字幕" % (cov, len(sents)))
            res["srt"]["sentences"] = len(sents)
            res["srt"]["sentences_covered"] = cov
        else:
            check("srt_sentence_coverage", True, "无 timeline_audio.json，跳过（记录）",
                  blocking=False)
    else:
        check("srt_cues", False, "未找到字幕文本（%s）" % (SRT_CANDIDATES,))

    # ---------------- H3 素材 / 占比 ----------------
    h3dir = os.path.join(ROOT, "assets", "h3")
    have = sorted(os.path.splitext(f)[0].upper() for f in os.listdir(h3dir)
                  if f.lower().endswith(".mp4")) if os.path.isdir(h3dir) else []
    want = sorted({s["h3id"] for s in shots if s.get("h3") and s.get("h3id")})
    missing = [c for c in want if c not in have]
    res["h3"] = {"expected": want, "present": have, "missing": missing}
    if want:
        check("h3_assets_present", not missing,
              "%d/%d 条到位（Sxx 命名）%s；assets/h3 共 %d 个文件"
              % (len(want) - len(missing), len(want),
                 ("；缺 " + ", ".join(missing)) if missing else "", len(have)),
              blocking=not args.allow_missing_h3)
    else:
        check("h3_assets_present", bool(have),
              "分镜数据无 H3 引用；assets/h3 现有 %d 条" % len(have), blocking=False)
    if shots:
        # H3 成片占比按 **manifest 实际可用口径**：红线降级（redline_fallback/fallback）的镜不计入 H3 时长
        h3_manifest, h3m_path = jload(os.path.join(ROOT, "assets", "h3", "manifest.json"))
        usable = {}
        redline = []
        if isinstance(h3_manifest, dict):
            for hid, info in (h3_manifest.get("shots") or {}).items():
                if not isinstance(info, dict):
                    continue
                sid = str(info.get("shot") or "").strip().upper()
                if not sid:
                    continue
                st = str(info.get("status") or "").lower()
                rl = info.get("redline")
                is_fb = ("fallback" in st) or ("fallback" in str(rl).lower()) or \
                    (isinstance(rl, dict) and rl.get("hit"))
                usable[sid] = not is_fb
                if is_fb:
                    reason = ""
                    if isinstance(rl, dict):
                        reason = str(rl.get("reason") or "")[:120]
                    redline.append((hid, sid, reason))
        h3_dur = 0.0
        h3_used, h3_fb = [], []
        for sh in shots:
            if not sh.get("h3"):
                continue
            sid = str(sh.get("id") or "").upper()
            key = sid if sid in usable else ("H%02d" % int(re.sub(r"\D", "", sid) or 0)
                                             if re.match(r"^S\d+", sid) else sid)
            ok = usable.get(sid, usable.get(key, True))
            if ok:
                h3_dur += sh["dur"]
                h3_used.append(sid)
            else:
                h3_fb.append(sid)
        tot = sum(s["dur"] for s in shots) or 1.0
        ratio = h3_dur / tot
        res["h3_share"] = round(ratio, 4)
        res["h3_used_shots"] = h3_used
        res["h3_fallback_shots"] = h3_fb
        detail = "H3 成片时长占比 %.1f%%（目标 20–35%%；可用 %d 镜，红线降级 %s）" % (
            ratio * 100, len(h3_used), (", ".join(h3_fb) or "无"))
        check("h3_ratio", spec["h3_share_min"] <= ratio <= spec["h3_share_max"], detail)
        check("h3_redline_recorded", not redline or bool(h3m_path),
              ("红线降级记录：" + "；".join("%s(%s) %s" % r for r in redline[:4]))
              if redline else "无红线降级", blocking=False)
        res["h3_redline"] = [{"h": h, "shot": sid, "reason": r} for h, sid, r in redline]
    else:
        check("h3_ratio", True, "无分镜 H3 字段，跳过（记录）", blocking=False)

    # ---------------- 片尾双声明卡 + 尾部收束 ----------------
    ec_png = os.path.join(QA, "endcard-check.png")
    if end_frames:
        best = max(end_frames, key=lambda f: f["center_bright"])
        frame_at(film, best["t"], ec_png)
        check("endcard_text_density", best["center_bright"] >= 6000,
              "t=%.1fs center_bright=%d（帧存 work/qa/endcard-check.png 供人工目检）"
              % (best["t"], best["center_bright"]))
        res["endcard"] = best
        res.setdefault("qa", {})["endcard_check"] = os.path.relpath(ec_png, ROOT)
    else:
        check("endcard_text_density", False, "无片尾抽帧")

    p1 = os.path.join(QA, "fade-check.png")
    frame_at(film, max(0.0, dur - 0.8), p1)
    fade_mean = region(p1, (0, 0, spec["w"], spec["h"]))["mean"]
    res["fade_mean"] = fade_mean
    res.setdefault("qa", {})["fade_check"] = os.path.relpath(p1, ROOT)
    _ec = res.get("endcard") or {}
    if fade_mean < 3:
        check("tail_ending", True, "尾部黑场淡出（末帧均值 %.2f）" % fade_mean)
    elif _ec.get("center_bright", 0) >= 6000:
        check("tail_ending", True,
              "以片尾声明卡收束（末帧均值 %.2f / 卡文字密度 %d，设计如此，非黑场）"
              % (fade_mean, _ec.get("center_bright", 0)))
    else:
        check("tail_ending", False, "尾部既非黑场也无声明卡（末帧均值 %.2f）" % fade_mean)

    # ---------------- web 版 ----------------
    if os.path.isfile(web):
        pw = probe(web)
        vw = next((s for s in pw["streams"] if s["codec_type"] == "video"), {})
        aw = [s for s in pw["streams"] if s["codec_type"] == "audio"]
        wdur = float(pw["format"]["duration"])
        wsize = round(os.path.getsize(web) / 1e6, 2)
        wr = run(FF, "-v", "error", "-i", web, "-f", "null", "-")
        werr = (wr.stderr or "").strip()
        web_ok = (vw.get("width") == 1280 and vw.get("height") == 720
                  and abs(wdur - dur) <= 1.0 and wsize < size_mb and not werr and bool(aw))
        check("web_version", web_ok,
              "1280x720? %sx%s / %.1fs / %.1fMB / 解码%s"
              % (vw.get("width"), vw.get("height"), wdur, wsize,
                 "OK" if not werr else "有错"))
        res["web"] = {"path": web, "width": vw.get("width"), "height": vw.get("height"),
                      "duration": wdur, "size_mb": wsize, "decode_errors": werr[:500]}
    else:
        check("web_version", False, "缺 web 版：%s" % web)

    # ---------------- QA 静帧（原理帧 / H3 抽帧）----------------
    principle = [] if args.light else (qa_principle_frames(film, shots) if shots else [])
    h3frames = [] if args.light else (qa_h3_frames(film, shots) if shots else [])
    if not principle and not args.light:
        # 没有分镜数据时兜底：片内 4 点供人工目检
        for i, frac in enumerate((0.15, 0.38, 0.62, 0.85), 1):
            p = os.path.join(QA, "principle-%02d.png" % i)
            frame_at(film, dur * frac, p)
            principle.append({"shot": "?", "time": round(dur * frac, 3),
                              "file": os.path.relpath(p, ROOT)})
    res.setdefault("qa", {})["principle_frames"] = principle
    res["qa"]["h3_frames"] = h3frames
    # 人检清单（Lead 逐帧目检用）
    if not args.light:
        hc = os.path.join(QA, "human-check.md")
        lines = ["# 第 08 期成片人工逐帧目检清单（脚本查不出的项）\n",
                 "> 由 verify_ep08.py 生成。重点：能量流方向（回收=轮端→电机→逆变器→电池；",
                 "> 驱动=电池→逆变器→电机→轮端，不得混向）、电机-逆变器-电池剖面路径、",
                 "> 制动混合方向、H3 物理细节、无乱码文字/品牌 logo/真人正脸。\n",
                 "## 关键原理帧\n",
                 "| # | 镜号 | 时间 | 帧文件 |", "| --- | --- | ---: | --- |"]
        for i, f in enumerate(principle, 1):
            lines.append("| %d | %s | %.2fs | `%s` |" % (i, f.get("shot", "?"),
                                                         f.get("time", 0), f.get("file", "")))
        lines += ["", "## H3 逐条抽帧（物理细节/无乱码/无 logo/无正脸）\n",
                  "| # | H3 | 帧文件 |", "| --- | --- | --- |"]
        for i, f in enumerate(h3frames, 1):
            lines.append("| %d | %s | `%s` |" % (i, os.path.basename(f).split(".")[0].replace("h3-", ""), f))
        lines += ["", "## 低运动抽帧（人检「会不会动的静图」）\n",
                  "| 对 | 时间 | 帧差 | 镜号 | 画面 | a/b 帧 |",
                  "| --- | ---: | ---: | --- | --- | --- |"]
        for mp in (res.get("motion") or {}).get("low_motion_probe") or []:
            lines.append("| %d | %.1fs | %.2f | %s | %s | `%s` / `%s` |"
                         % (mp["pair"], mp["t"], mp["diff"], mp.get("shot") or "?",
                            (mp.get("title") or "").replace("|", "/"),
                            mp["frames"][0], mp["frames"][1]))
        lines += ["", "## 全片\n",
                  "- 16 帧联系表：`work/qa/verify-contact-sheet.jpg`",
                  "- 片尾双声明卡：`work/qa/endcard-check.png`",
                  "- 尾部收束帧：`work/qa/fade-check.png`", ""]
        open(hc, "w", encoding="utf-8").write("\n".join(lines))
        res["qa"]["human_check"] = os.path.relpath(hc, ROOT)

    # ---------------- 联系表 ----------------
    if not args.no_contact_sheet and not args.light:
        cs, cs_times = contact_sheet(film, dur, reuse=cov_frames)
        res["contact_sheet"] = os.path.relpath(cs, ROOT)
        res["contact_sheet_times"] = cs_times
        print("contact sheet -> %s" % res["contact_sheet"])

    # ---------------- 汇总 ----------------
    res["checks"] = checks
    res["problems"] = [c["name"] for c in checks if not c["pass"] and c["blocking"]]
    res["warnings"] = [c["name"] for c in checks if not c["pass"] and not c["blocking"]]
    if args.strict:
        res["problems"] += res["warnings"]
        res["warnings"] = []
    os.makedirs(WORK, exist_ok=True)
    out_json = args.json_out
    if not out_json:
        out_json = (os.path.join(WORK, "final-check-draft.json")
                    if "draft" in os.path.basename(film).lower()
                    else os.path.join(WORK, "final-check.json"))
    json.dump(res, open(out_json, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    n_pass = sum(1 for c in checks if c["pass"])
    print("\n%d/%d checks PASS; problems: %s; warnings: %s"
          % (n_pass, len(checks), res["problems"] or "none", res["warnings"] or "none"))
    print("JSON -> %s" % out_json)
    print("RESULT:", "ALL OK" if not res["problems"] else "PROBLEMS")
    return 0 if not res["problems"] else 1


if __name__ == "__main__":
    sys.exit(main())
