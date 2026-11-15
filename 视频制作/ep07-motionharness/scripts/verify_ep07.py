#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 07 期成片硬校验（MotionHarness Pro 导出 MP4）。

检查项（全部实测，不依赖人耳）：
  1. 规格：1920×1080 / 24fps / 时长 ≈ 期望（默认 197.0s，优先读 work/timeline.json 或 work/ep07-meta.json）
  2. 帧数：round(duration*24) ±2；全片解码 0 错误
  3. 响度：I = -14.31 ±0.5 LUFS（系列目标 -14±0.5）/ TP ≤ -1.0 dBTP / LRA
  4. 2.35:1 遮幅：上/下 132px 黑边均值 < 6（下黑边允许字幕像素，单独看字幕带）
  5. 字幕带：下黑边内（y≈950–1045）文字像素存在；有 SRT 时按句时间点抽检覆盖
  6. 片尾双声明卡：末尾 4–10s 中心区文字像素密度 + 保存静帧供人工目检（本机无 OCR）
  7. 尾部淡出：最后 ~1s 均值 < 3（若项目以黑场收束）
  8. 抽帧联系表：work/qa/verify-contact-sheet.jpg（PIL 拼图）

输出：work/final-check.json（机器可读）+ 控制台 PASS/FAIL + 退出码。
用法：
  python3 scripts/verify_ep07.py                       # 默认 out/ep07-mh.mp4
  python3 scripts/verify_ep07.py path/to/film.mp4
  python3 scripts/verify_ep07.py --expect-duration 197.3 --expect-i -14.31
"""
import argparse
import json
import os
import re
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont, ImageStat

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FF = os.environ.get("FFMPEG", "/home/admin/.local/bin/ffmpeg")
FP = os.environ.get("FFPROBE", "/home/admin/.local/bin/ffprobe-real")
FILM = os.path.join(ROOT, "out", "ep07-mh.mp4")
WORK = os.path.join(ROOT, "work")
QA = os.path.join(WORK, "qa")
TMP = os.path.join(QA, "verify-frames")

SPEC = {
    "w": 1920, "h": 1080, "fps": 24.0, "bar": 132,
    "i_target": -14.31, "i_tol": 0.5, "tp_max": -1.0,
    "duration": None,       # 由 resolve_expected() 决定
}
DEFAULT_DURATION = 197.0     # 设计值 3:17；TTS 实测后以 timeline/meta 为准


def run(*a):
    return subprocess.run(a, capture_output=True, text=True, errors="replace")


def resolve_expected(args):
    """期望时长优先级：CLI > work/ep07-meta.json > work/timeline.json > src/data/timeline.json > 197.0"""
    if args.expect_duration:
        return float(args.expect_duration), "cli"
    meta = os.path.join(WORK, "ep07-meta.json")
    if os.path.isfile(meta):
        try:
            m = json.load(open(meta, encoding="utf-8"))
            for k in ("duration", "total", "duration_s"):
                if m.get(k):
                    return float(m[k]), "work/ep07-meta.json"
        except Exception:
            pass
    for cand in (os.path.join(WORK, "timeline.json"),
                 os.path.join(ROOT, "src", "data", "timeline.json")):
        if os.path.isfile(cand):
            try:
                d = json.load(open(cand, encoding="utf-8"))
                for k in ("total", "duration", "duration_s"):
                    if isinstance(d, dict) and d.get(k):
                        return float(d[k]), os.path.relpath(cand, ROOT)
            except Exception:
                pass
    return DEFAULT_DURATION, "design-default"


def probe(film):
    r = run(FP, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", film)
    if r.returncode != 0 or not r.stdout.strip():
        raise SystemExit("ffprobe 失败: %s" % (r.stderr or r.stdout)[-500:])
    return json.loads(r.stdout)


def count_frames(film):
    r = run(FF, "-v", "error", "-i", film, "-map", "0:v:0", "-f", "null", "-")
    fr = re.findall(r"frame=\s*(\d+)", r.stderr or "")
    return int(fr[-1]) if fr else 0


def frame_at(film, t, path):
    run(FF, "-v", "error", "-y", "-an", "-ss", "%.3f" % t, "-i", film,
        "-frames:v", "1", path)
    return path


def region(png, box):
    im = Image.open(png).convert("L").crop(box)
    st = ImageStat.Stat(im)
    hist = im.histogram()
    mean = st.mean[0]
    mx = max(i for i, c in enumerate(hist) if c) if any(hist) else 0
    bright = sum(hist[170:])          # luma >= 170 的像素数
    return {"mean": mean, "max": mx, "bright": bright, "box": box}


def loudness(film):
    r = run(FF, "-hide_banner", "-nostats", "-i", film, "-af",
            "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-")
    tail = r.stderr or ""
    try:
        j = json.loads(tail[tail.rindex("{"):tail.rindex("}") + 1])
        return {"I": float(j["input_i"]), "TP": float(j["input_tp"]),
                "LRA": float(j["input_lra"]), "thresh": float(j["input_thresh"])}
    except Exception:
        return {"I": None, "TP": None, "LRA": None, "thresh": None}


def load_srt_cues():
    """优先 work/srt/all.srt，其次 src/data/srt.json；返回 [(start, end), ...]。"""
    srt = os.path.join(WORK, "srt", "all.srt")
    if not os.path.isfile(srt):
        srt = os.path.join(ROOT, "work", "srt", "all.srt")
    cues = []
    if os.path.isfile(srt):
        for line in open(srt, encoding="utf-8", errors="ignore"):
            m = re.search(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)", line)
            if m:
                g = [int(x) for x in m.groups()]
                cues.append((g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000.0,
                             g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000.0))
        return cues
    js = os.path.join(ROOT, "src", "data", "srt.json")
    if os.path.isfile(js):
        try:
            data = json.load(open(js, encoding="utf-8"))
            for c in data if isinstance(data, list) else data.get("cues", []):
                cues.append((float(c.get("start", 0)), float(c.get("end", 0))))
        except Exception:
            pass
    return cues


def load_shots_h3():
    """从 src/data/shots.json 读取实际引用的 H3 clip 集合（大写 H01…H20）。"""
    cands = [os.path.join(ROOT, "src", "data", "shots.json"),
             os.path.join(ROOT, "src", "data", "h3_manifest.json")]
    clips = []
    for c in cands:
        if not os.path.isfile(c):
            continue
        try:
            d = json.load(open(c, encoding="utf-8"))
        except Exception:
            continue
        if isinstance(d, list):
            for sh in d:
                if sh.get("h3"):
                    clips.append(str(sh["h3"]))
        elif isinstance(d, dict):
            for m in d.get("mapping") or []:
                if m.get("clip"):
                    clips.append(str(m["clip"]))
    return sorted(set(clips))


def load_srt_texts():
    srt = os.path.join(WORK, "srt", "all.srt")
    if not os.path.isfile(srt):
        return []
    out = []
    for block in open(srt, encoding="utf-8", errors="ignore").read().split("\n\n"):
        lines = [x.strip() for x in block.strip().splitlines() if x.strip()]
        if len(lines) >= 3 and "-->" in lines[1]:
            out.append(" ".join(lines[2:]))
    return out


def contact_sheet(film, dur):
    """16 帧 4×4 联系表，供人工过一眼全片。"""
    os.makedirs(TMP, exist_ok=True)
    n, cols = 16, 4
    times = [dur * (i + 0.5) / n for i in range(n)]
    TW, TH = 480, 270
    rows = (n + cols - 1) // cols
    sheet = Image.new("RGB", (cols * TW, rows * (TH + 22)), (8, 9, 12))
    d = ImageDraw.Draw(sheet)
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
    for i, t in enumerate(times):
        p = os.path.join(TMP, "cs%02d.jpg" % i)
        frame_at(film, t, p)
        im = Image.open(p).convert("RGB").resize((TW, TH))
        x, y = (i % cols) * TW, (i // cols) * (TH + 22)
        sheet.paste(im, (x, y))
        d.text((x + 6, y + TH + 3), "%.1fs" % t, font=font, fill=(190, 196, 204))
    out = os.path.join(QA, "verify-contact-sheet.jpg")
    sheet.save(out, quality=88)
    return out, times


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("film", nargs="?", default=FILM)
    ap.add_argument("--expect-duration", type=float, default=None)
    ap.add_argument("--expect-i", type=float, default=None)
    ap.add_argument("--no-contact-sheet", action="store_true")
    args = ap.parse_args()
    film = os.path.abspath(args.film)
    if not os.path.isfile(film):
        raise SystemExit("找不到成片: %s" % film)
    os.makedirs(QA, exist_ok=True)
    os.makedirs(TMP, exist_ok=True)
    exp_dur, exp_src = resolve_expected(args)
    spec = dict(SPEC)
    spec["duration"] = exp_dur
    if args.expect_i is not None:
        spec["i_target"] = args.expect_i

    res = {"film": film, "expected": spec, "expected_duration_source": exp_src}
    ok = True
    checks = []

    def check(name, cond, detail=""):
        nonlocal ok
        checks.append({"name": name, "pass": bool(cond), "detail": str(detail)})
        print(("PASS " if cond else "FAIL ") + "%-26s %s" % (name, detail))
        ok = ok and bool(cond)

    p = probe(film)
    v = next(s for s in p["streams"] if s["codec_type"] == "video")
    a = [s for s in p["streams"] if s["codec_type"] == "audio"]
    dur = float(p["format"]["duration"])
    fps = eval(v["r_frame_rate"])
    nb = int(v.get("nb_frames") or 0)
    frames = nb or count_frames(film)
    size_mb = round(os.path.getsize(film) / 1e6, 2)
    exp_frames = int(round(exp_dur * spec["fps"]))
    res.update({"size_mb": size_mb, "width": v["width"], "height": v["height"],
                "fps": fps, "duration": dur, "frames": frames,
                "expected_duration": exp_dur, "expected_frames": exp_frames,
                "video_codec": v["codec_name"], "pix_fmt": v.get("pix_fmt"),
                "audio": [{"codec": s["codec_name"], "ch": s["channels"],
                           "sr": s["sample_rate"]} for s in a]})
    print(json.dumps({k: res[k] for k in ("film", "duration", "frames", "width", "height",
                                          "fps", "size_mb", "video_codec")},
                     ensure_ascii=False, indent=1))

    check("resolution", v["width"] == spec["w"] and v["height"] == spec["h"],
          "%dx%d" % (v["width"], v["height"]))
    check("fps", abs(fps - spec["fps"]) < 0.01, "%.3f" % fps)
    check("duration", abs(dur - exp_dur) <= 0.5,
          "%.3f vs %.3f (%s)" % (dur, exp_dur, exp_src))
    check("frames", abs(frames - exp_frames) <= 2, "%d vs %d" % (frames, exp_frames))
    check("has_audio", bool(a), json.dumps(res["audio"], ensure_ascii=False))
    r = run(FF, "-v", "error", "-i", film, "-f", "null", "-")
    err = (r.stderr or "").strip()
    check("decode_clean", r.returncode == 0 and not err, err[:160])
    res["decode_errors"] = err[:2000]

    lw = loudness(film)
    res["loudness"] = lw
    if lw["I"] is None:
        check("loudness_parse", False, "无法解析 loudnorm 输出")
    else:
        lo = spec["i_target"] - spec["i_tol"]
        hi = spec["i_target"] + spec["i_tol"]
        check("loudness_I", lo <= lw["I"] <= hi, "%.2f (%.2f..%.2f)" % (lw["I"], lo, hi))
        check("true_peak", lw["TP"] <= spec["tp_max"], "%.2f" % lw["TP"])
        check("lra", 0 < lw["LRA"] < 20, "%.2f" % lw["LRA"])

    # ---- 抽帧检查：遮幅 / 画面 / 字幕带 / 片尾卡 / 淡出 ----
    bar = spec["bar"]
    cues = load_srt_cues()
    res["srt_cues"] = len(cues)
    times = [1.0, dur * 0.05, dur * 0.12, dur * 0.20, dur * 0.30, dur * 0.42,
             dur * 0.55, dur * 0.66, dur * 0.78, dur * 0.88, dur - 6.0, dur - 2.0]
    if cues:
        times += [((s + e) / 2.0) for s, e in cues[:8]]
    times = sorted({round(min(max(t, 0.2), dur - 0.3), 3) for t in times})
    bars_ok, content_ok = True, True
    sub_frames = []
    end_frames = []
    for i, t in enumerate(times):
        png = os.path.join(TMP, "v%02d.png" % i)
        frame_at(film, t, png)
        top = region(png, (0, 0, spec["w"], bar))
        bot = region(png, (0, spec["h"] - bar, spec["w"], spec["h"]))
        mid = region(png, (0, 360, spec["w"], 720))
        sub = region(png, (120, spec["h"] - bar + 4, spec["w"] - 120, spec["h"] - 6))
        sub_hi = region(png, (120, spec["h"] - 200, spec["w"] - 120, spec["h"] - bar))
        sub = dict(sub, bright=max(sub["bright"], sub_hi["bright"]),
                   mean=min(sub["mean"], sub_hi["mean"]))
        bars_ok = bars_ok and top["mean"] < 6 and bot["mean"] < 8
        content_ok = content_ok and mid["mean"] > 4
        sub_frames.append({"t": t, "bright": sub["bright"], "mean": sub["mean"]})
        if t >= dur - 10:
            end_frames.append({"t": t, "center_bright": region(
                png, (360, 300, spec["w"] - 360, spec["h"] - 300))["bright"]})
    check("letterbox_2.35", bars_ok, "上下 %dpx 黑边" % bar)
    check("content_present", content_ok, "中部画面均值 > 4")
    res["subtitle_frames"] = sub_frames

    # 字幕：至少 30%（且 >=2）抽检帧在字幕带有明显文字像素
    # 阈值 1200 来自 ep06 实测校准（字幕帧 bright170≈2100–2700，无字幕帧 <300）
    has_sub = [f for f in sub_frames if f["bright"] >= 1200]
    need = max(2, int(0.3 * len(sub_frames)))
    check("subtitles_present", len(has_sub) >= need,
          "%d/%d 帧字幕带 bright>=1200（需 %d）" % (len(has_sub), len(sub_frames), need))
    check("subtitles_band_black", min(f["mean"] for f in sub_frames) < 12,
          "字幕带最低均值 %.1f" % min(f["mean"] for f in sub_frames))

    # ---- SRT 结构（字幕内容层面；MH 用 DOM 字幕，无 ASS 文件）----
    texts = load_srt_texts()
    if texts:
        starts = [c[0] for c in cues]
        ends = [c[1] for c in cues]
        monotonic = all(starts[i] <= starts[i + 1] for i in range(len(starts) - 1))
        overlaps = sum(1 for i in range(len(starts) - 1) if ends[i] > starts[i + 1] + 1e-6)
        out_of_range = [c for c in cues if c[0] < 0 or c[1] > dur + 0.05]
        long_lines = [t for t in texts if len(t) > 20]
        check("srt_cues", len(cues) >= 50, "%d 条（期望约 98）" % len(cues))
        check("srt_monotonic", monotonic, "start 单调")
        check("srt_no_overlap", overlaps == 0, "重叠对 %d" % overlaps)
        check("srt_in_range", not out_of_range, "%d 条越界" % len(out_of_range))
        check("srt_line_len", not long_lines, ">20 字行 %d（最长 %d）"
              % (len(long_lines), max((len(t) for t in texts), default=0)))
        check("srt_tail", abs(ends[-1] - dur) <= 2.5,
              "末条结束 %.2fs vs 成片 %.2fs" % (ends[-1], dur))
        res["srt"] = {"cues": len(cues), "monotonic": monotonic, "overlaps": overlaps,
                      "out_of_range": len(out_of_range),
                      "max_line_chars": max((len(t) for t in texts), default=0),
                      "last_end": ends[-1]}
    else:
        check("srt_cues", False, "未找到字幕文本")

    # ---- H3 素材到位检查（FootageLayer 缺失时静默隐藏，但交付要求全部到位）----
    want = load_shots_h3()
    have = []
    h3dir = os.path.join(ROOT, "assets", "h3")
    if os.path.isdir(h3dir):
        have = [os.path.splitext(f)[0].upper() for f in os.listdir(h3dir) if f.lower().endswith(".mp4")]
    missing = [c for c in want if c.upper() not in have]
    res["h3"] = {"expected": want, "present": sorted(have), "missing": missing}
    check("h3_assets_present", bool(want) and not missing,
          "%d/%d clip 到位%s" % (len(want) - len(missing), len(want),
                                 ("；缺 " + ", ".join(missing)) if missing else ""))

    # 片尾双声明卡：末尾 4–10s 内中心区文字像素
    os.makedirs(QA, exist_ok=True)
    ec_png = os.path.join(QA, "endcard-check.png")
    if end_frames:
        best = max(end_frames, key=lambda f: f["center_bright"])
        frame_at(film, best["t"], ec_png)
        check("endcard_text_density", best["center_bright"] >= 6000,
              "t=%.1fs center_bright=%d (帧存 work/qa/endcard-check.png，供人工目检)"
              % (best["t"], best["center_bright"]))
        res["endcard"] = best
    else:
        check("endcard_text_density", False, "无片尾抽帧")

    # 淡出：最后 0.8s 均值 < 3（若为黑场收束；非黑场收束则仅记录）
    p1 = os.path.join(TMP, "fade.png")
    frame_at(film, max(0.0, dur - 0.8), p1)
    fade_mean = region(p1, (0, 0, spec["w"], spec["h"]))["mean"]
    res["fade_mean"] = fade_mean
    check("fade_out_black", fade_mean < 3, "末帧均值 %.2f（若项目非黑场收束可在报告中注明）" % fade_mean)

    if not args.no_contact_sheet:
        cs, cs_times = contact_sheet(film, dur)
        res["contact_sheet"] = os.path.relpath(cs, ROOT)
        print("contact sheet -> %s" % res["contact_sheet"])
        res["contact_sheet_times"] = cs_times

    # ---- 结构化问题清单 ----
    res["checks"] = checks
    res["problems"] = [c["name"] for c in checks if not c["pass"]]
    os.makedirs(WORK, exist_ok=True)
    out_json = os.path.join(WORK, "final-check.json")
    json.dump(res, open(out_json, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("\n%d/%d checks PASS; problems: %s"
          % (len(checks) - len(res["problems"]), len(checks), res["problems"] or "none"))
    print("JSON -> %s" % out_json)
    print("RESULT:", "ALL OK" if ok else "PROBLEMS")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
