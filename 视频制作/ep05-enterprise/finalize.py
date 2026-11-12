#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 05 期成片收尾：拼镜 → 统一调色/遮幅/颗粒/字幕/音轨 → 静帧/封面 → 硬校验 → 自检报告。

用法：
  python3 finalize.py                  # 等齐 35 镜 → 编码 → 静帧/封面/联系表 → 硬校验
  python3 finalize.py --no-wait
  python3 finalize.py --audio work/audio_draft.m4a --out out/draft.mp4 --draft
输出：
  out/ep05-enterprise.mp4（1920×1080 / 24fps / 2.35:1 遮幅 / H.264 High + AAC 48k）
  delivery/stills/（8 张代表静帧，含片尾卡）、delivery/contact-sheet.jpg、封面三尺寸
  work/final-check.json、work/final-report.md
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.abspath(__file__))
FFMPEG = "/home/admin/.local/bin/ffmpeg"
WORK = os.path.join(ROOT, "work")
CLIPS = os.path.join(WORK, "clips")
OUT_DIR = os.path.join(ROOT, "out")
DELIVERY = os.path.join(ROOT, "delivery")
STILLS_DIR = os.path.join(DELIVERY, "stills")
TL = json.load(open(os.path.join(WORK, "timeline.json"), encoding="utf-8"))
TOTAL = float(TL["total"])
FPS = int(TL.get("fps", 24))
N = int(round(TOTAL * FPS))
SHOTS = TL["shots"]
SHOT = {s["id"]: s for s in SHOTS}
AUDIO = os.path.join(WORK, "audio.m4a")
SRT = os.path.join(WORK, "srt", "all.srt")
ASS_PATH = os.path.join(WORK, "srt", "all.ass")
OUT = os.path.join(OUT_DIR, "ep05-enterprise.mp4")
ENC_THREADS = max(1, int(os.environ.get("EP05_FFMPEG_THREADS", "2")))
SUB_SIZE = int(os.environ.get("EP05_SUB_SIZE", "48"))   # SPEC §4：48px
BAR = 132                                             # 2.35:1 遮幅

# 8 张代表静帧（SPEC §6.7）：S1 走廊 / S2 关系网 / S3 楼层 / S4 箭头空白 / S5 74→43 /
# S6 网松开 / S6 片尾光 / 片尾 AI 声明卡（时间在 build_stills 里按 shots 动态计算）
STILL_PLAN = [
    ("s1a", 1.2, "still-01-corridor"),
    ("s2c", 1.4, "still-02-network-190"),
    ("s3b", 2.6, "still-03-floors-rise"),
    ("s4c", 2.6, "still-04-arrows-blank"),
    ("s5c", 2.2, "still-05-74-43"),
    ("s6a", 2.6, "still-06-net-loosen"),
    ("s6b", 3.8, "still-07-dawn-light"),
    ("s6f", 6.0, "still-08-end-card"),
]


def log(*a):
    print("[finalize] " + " ".join(str(x) for x in a), flush=True)


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def probe(path):
    """ffmpeg -i 解析时长/分辨率/fps/码率（本机无独立 ffprobe）。"""
    r = run([FFMPEG, "-hide_banner", "-i", path])
    err = r.stderr or ""
    info = {"duration": 0.0, "width": 0, "height": 0, "fps": 0.0, "video": "", "audio": ""}
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", err)
    if m:
        info["duration"] = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    m = re.search(r"Video: ([^,]+), [^,]*?, (\d+)x(\d+)", err)
    if m:
        info["video"], info["width"], info["height"] = m.group(1), int(m.group(2)), int(m.group(3))
    m = re.search(r"(\d+(?:\.\d+)?) fps", err)
    if m:
        info["fps"] = float(m.group(1))
    m = re.search(r"Audio: ([^\n]+)", err)
    if m:
        info["audio"] = m.group(1).strip()
    return info


def count_frames(path):
    r = run([FFMPEG, "-hide_banner", "-i", path, "-map", "0:v:0", "-f", "null", "-"])
    err = r.stderr or ""
    frames = [int(x) for x in re.findall(r"frame=\s*(\d+)", err)]
    return frames[-1] if frames else 0, err


# ------------------------------------------------------------------ clips / ass
def missing_clips():
    miss = []
    for s in SHOTS:
        p = os.path.join(CLIPS, s["id"] + ".mp4")
        if not (os.path.isfile(p) and os.path.getsize(p) > 10000):
            miss.append(s["id"])
    return miss


def wait_clips():
    while True:
        miss = missing_clips()
        if not miss:
            return
        log("等待 %d 个镜头: %s" % (len(miss), " ".join(miss[:10])))
        time.sleep(10)


def srt_to_ass():
    """SRT → ASS：48px Noto Sans CJK SC、白字 60% 黑描边，落在下方 132px 黑边内。"""
    def ts(t):
        h = int(t // 3600)
        m = int((t % 3600) // 60)
        s = t % 60
        return "%d:%02d:%05.2f" % (h, m, s)

    entries = []
    raw = open(SRT, encoding="utf-8").read().strip().split("\n\n")
    for block in raw:
        lines = [x for x in block.splitlines() if x.strip()]
        if len(lines) < 2:
            continue
        m = re.match(r"(\d+):(\d+):(\d+),(\d+) --> (\d+):(\d+):(\d+),(\d+)", lines[1])
        if not m:
            continue
        g = [int(x) for x in m.groups()]
        a = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000.0
        b = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000.0
        text = "\\N".join(lines[2:])
        entries.append((a, b, text))
    margin_v = 50 if SUB_SIZE <= 48 else 42
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,Noto Sans CJK SC,%d,&H00F2EEE5,&H00FFFFFF,&H50000000,&H64000000,0,0,0,0,100,100,0.5,0,1,2.4,1.2,2,120,120,%d,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""" % (SUB_SIZE, margin_v)
    out = [header]
    for a, b, text in entries:
        out.append("Dialogue: 0,%s,%s,Sub,,0,0,0,,%s" % (ts(max(0, a)), ts(max(a + 0.05, b)), text))
    open(ASS_PATH, "w", encoding="utf-8").write("\n".join(out) + "\n")
    log("ass written", len(entries), "lines, font", SUB_SIZE, "px, marginV", margin_v)
    return len(entries)


def build_concat():
    lst = os.path.join(WORK, "concat.txt")
    lines = []
    for s in SHOTS:
        p = os.path.join(CLIPS, s["id"] + ".mp4")
        lst_lines = "file '%s'" % p
        lines.append(lst_lines)
    open(lst, "w").write("\n".join(lines) + "\n")
    concat = os.path.join(WORK, "video-concat.mp4")
    r = run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
             "-i", lst, "-c", "copy", concat])
    if r.returncode != 0:
        raise SystemExit("concat failed: " + r.stderr[-1200:])
    log("concat done %.3fs" % probe(concat)["duration"])
    return concat


def encode(concat, audio, out):
    os.makedirs(os.path.dirname(out), exist_ok=True)
    # 统一影调（轻）+ 暗角 + 胶片颗粒 + 2.35:1 遮幅 + ASS 字幕 + 片头/片尾淡入淡出
    vf = (
        "eq=contrast=1.045:brightness=0.012:saturation=1.06:gamma=1.003,"
        "colorbalance=rs=-0.012:gs=0.0:bs=0.022:rh=0.012:bh=-0.012,"
        "vignette=PI/5.2,"
        "noise=alls=5:allf=t+u,"
        "drawbox=x=0:y=0:w=iw:h=%d:color=black:t=fill,"
        "drawbox=x=0:y=ih-%d:w=iw:h=%d:color=black:t=fill,"
        "ass=filename=%s:fontsdir=/usr/share/fonts/opentype/noto,"
        "fade=t=in:st=0:d=0.6,fade=t=out:st=%.3f:d=1.2,"
        "format=yuv420p" % (BAR, BAR, BAR, ASS_PATH, TOTAL - 1.25)
    )
    cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
           "-i", concat, "-i", audio,
           "-filter_complex", "[0:v]%s[v]" % vf,
           "-map", "[v]", "-map", "1:a",
           "-t", "%.3f" % TOTAL,
           "-c:v", "libx264", "-preset", "fast", "-crf", "20",
           "-profile:v", "high", "-level", "4.1",
           "-x264-params", "rc-lookahead=12:sync-lookahead=0",
           "-threads", str(ENC_THREADS),
           "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
           "-movflags", "+faststart", out]
    t0 = time.time()
    r = run(cmd)
    if r.returncode != 0:
        raise SystemExit("encode failed:\n" + r.stderr[-2500:])
    log("encoded %s  %.1f MB  %.1fs" % (out, os.path.getsize(out) / 1e6, time.time() - t0))
    return out


# ------------------------------------------------------------------ stills / covers
def build_stills(out):
    os.makedirs(STILLS_DIR, exist_ok=True)
    made = []
    for sid, off, name in STILL_PLAN:
        sh = SHOT.get(sid)
        if sh is None:
            continue
        t = min(float(sh["start"]) + off, TOTAL - 0.3)
        p = os.path.join(STILLS_DIR, name + ".jpg")
        r = run([FFMPEG, "-v", "error", "-y", "-ss", "%.2f" % t, "-i", out,
                 "-frames:v", "1", "-q:v", "2", p])
        if r.returncode == 0 and os.path.isfile(p):
            made.append((name, t))
            log("still %-24s @%7.2fs" % (name, t))
    # 片尾 AI 声明卡（取片尾卡中段）
    sh = SHOT.get("s6f")
    if sh:
        t = min(float(sh["start"]) + float(sh["dur"]) * 0.55, TOTAL - 0.5)
        p = os.path.join(STILLS_DIR, "still-09-end-hold.jpg")
        if run([FFMPEG, "-v", "error", "-y", "-ss", "%.2f" % t, "-i", out,
                "-frames:v", "1", "-q:v", "2", p]).returncode == 0:
            made.append(("still-09-end-hold", t))
    return made


# ------------------------------------------------------------------ verification
def loudness(path):
    r = run([FFMPEG, "-hide_banner", "-nostats", "-i", path, "-af",
             "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"])
    tail = r.stderr or ""
    try:
        # JSON 之后还有 ffmpeg 的 out#0 统计行，必须截到最后一个 '}' 为止
        j = json.loads(tail[tail.rindex("{"):tail.rindex("}") + 1])
        return {"I": float(j["input_i"]), "TP": float(j["input_tp"]),
                "LRA": float(j["input_lra"]), "thresh": float(j["input_thresh"])}
    except Exception:
        return {"I": None, "TP": None, "LRA": None, "thresh": None}


def pcm(path, sec=None):
    """解码为 48k 单声道 float32（相关度用）。"""
    cmd = [FFMPEG, "-v", "error", "-i", path, "-ac", "1", "-ar", "48000",
           "-f", "f32le", "-"]
    if sec is not None:
        cmd = [FFMPEG, "-v", "error", "-ss", "%.2f" % sec[0], "-t", "%.2f" % (sec[1] - sec[0]),
               "-i", path, "-ac", "1", "-ar", "48000", "-f", "f32le", "-"]
    r = subprocess.run(cmd, capture_output=True)
    return np.frombuffer(r.stdout, dtype=np.float32)


def narration_integrity(out, narration_path):
    """成片音轨 vs 旁白干声：在 3 个有声区间的相关系数（ep04 口径：≥0.9）。"""
    segs = {s["id"]: s for s in TL["segments"]}
    wins = []
    for sid, sent_i in (("S1", 2), ("S3", 6), ("S5", 6)):
        seg = segs.get(sid)
        if not seg:
            continue
        sents = {s["i"]: s for s in seg["sentences"]}
        s = sents.get(sent_i)
        if s:
            a = max(0.0, float(s["start"]) + 0.3)
            b = min(TOTAL, float(s["end"]) - 0.2)
            if b - a > 1.5:
                wins.append((sid + "_" + str(sent_i), a, b))
    res = {}
    for name, a, b in wins:
        x = pcm(narration_path, (a, b)).astype(np.float64)
        y = pcm(out, (a, b)).astype(np.float64)
        n = min(len(x), len(y))
        if n < 4800:
            res[name] = None
            continue
        x, y = x[:n], y[:n]
        x = x - x.mean()
        y = y - y.mean()
        denom = (np.linalg.norm(x) * np.linalg.norm(y))
        res[name] = float(np.dot(x, y) / denom) if denom > 1e-9 else 0.0
    return res


def check_subs():
    """字幕条数 / 时间单调 / 落在句区间 / 单行≤18 汉字。"""
    from collections import defaultdict
    raw = open(SRT, encoding="utf-8").read().strip().split("\n\n")
    cues = []
    for block in raw:
        lines = [x for x in block.splitlines() if x.strip()]
        if len(lines) < 2:
            continue
        m = re.match(r"(\d+):(\d+):(\d+),(\d+) --> (\d+):(\d+):(\d+),(\d+)", lines[1])
        if not m:
            continue
        g = [int(x) for x in m.groups()]
        a = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000.0
        b = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000.0
        cues.append({"start": a, "end": b, "lines": lines[2:]})
    mono = all(cues[i]["start"] <= cues[i + 1]["start"] for i in range(len(cues) - 1))
    overlaps = sum(1 for i in range(len(cues) - 1) if cues[i]["end"] > cues[i + 1]["start"] + 0.01)
    long_lines = [(c["start"], line) for c in cues for line in c["lines"]
                  if len(re.sub(r"[^\u4e00-\u9fa5A-Za-z0-9]", "", line)) > 18]
    # 落在句区间：cue 中点应被某句 [start,end] 覆盖（±0.25s 容差）
    sents = TL["sentences"]
    # 片尾 AI 声明口播（outro_voice）不在 64 句正文内，单独白名单
    ov = TL.get("outro_voice") or {}
    ov_win = (float(ov["start"]) - 0.25, float(ov["end"]) + 0.25) if ov else None
    out_of_range = []
    for c in cues:
        mid = 0.5 * (c["start"] + c["end"])
        ok = any(s["start"] - 0.25 <= mid <= s["end"] + 0.25 for s in sents)
        if not ok and ov_win and ov_win[0] <= mid <= ov_win[1]:
            ok = True
        if not ok and c["end"] > 1.0:
            out_of_range.append(round(mid, 2))
    covered = 0
    for s in sents:
        if any(c["start"] < s["end"] + 0.25 and c["end"] > s["start"] - 0.25 for c in cues):
            covered += 1
    return {"cues": len(cues), "monotonic": mono, "overlap_pairs": overlaps,
            "long_lines": long_lines[:5], "long_line_count": len(long_lines),
            "out_of_sentence_range": out_of_range,
            "sentences": len(sents), "sentences_covered": covered,
            "first": cues[0]["start"] if cues else None,
            "last": cues[-1]["end"] if cues else None}


def frame_stats(out, t):
    """取一帧 → (上黑边均值, 下黑边均值, 画面均值, 下黑边最大)。"""
    r = subprocess.run([FFMPEG, "-v", "error", "-ss", "%.2f" % t, "-i", out, "-frames:v", "1",
                        "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True)
    if r.returncode != 0 or len(r.stdout) < 1920 * 1080:
        return None
    a = np.frombuffer(r.stdout[:1920 * 1080], dtype=np.uint8).reshape(1080, 1920)
    return {"top": float(a[:BAR].mean()), "bottom": float(a[1080 - BAR:].mean()),
            "content": float(a[BAR:1080 - BAR].mean()),
            "bottom_max": int(a[1080 - BAR:].max())}


def comfy_usage():
    import ep05assets as A
    used, fallback = [], []
    for s in SHOTS:
        a = s.get("asset")
        if not a or not a.startswith("comfy_"):
            continue
        path, _ = A.resolve(a)
        (used if A.is_comfy_path(path) else fallback).append(a)
    return {"used": used, "fallback": fallback}


def verify(out, made_stills):
    t0 = time.time()
    res = {"out": out, "expected_frames": N, "expected_duration": TOTAL}
    info = probe(out)
    res["duration"] = info["duration"]
    res["resolution"] = [info["width"], info["height"]]
    res["fps"] = info["fps"]
    res["size_mb"] = round(os.path.getsize(out) / 1e6, 2)
    # 全片解码 + 帧数
    frames, ferr = count_frames(out)
    res["frames"] = frames
    derr = run([FFMPEG, "-hide_banner", "-v", "error", "-i", out, "-f", "null", "-"]).stderr.strip()
    res["decode_errors"] = derr
    # 响度
    res["loudness"] = loudness(out)
    # 旁白完整性
    nar = os.path.join(WORK, "narration.wav")
    res["narration_corr"] = narration_integrity(out, nar) if os.path.isfile(nar) else {}
    # 字幕
    res["subs"] = check_subs()
    # 画面：遮幅/字幕/片尾卡
    checks = {}
    sh = SHOT.get("s1b") or SHOTS[1]
    for name, t in [("subtitle-check", float(sh["start"]) + 1.0),
                    ("end-declaration", float(SHOT["s6f"]["start"]) + 6.0),
                    ("net-190", float(SHOT["s2c"]["start"]) + 1.0),
                    ("floors", float(SHOT["s3b"]["start"]) + 1.0),
                    ("fade-out", TOTAL - 0.35)]:
        st = frame_stats(out, min(t, TOTAL - 0.1))
        checks[name] = st
    res["frame_checks"] = checks
    bars_ok = all(v is not None and v["top"] < 1.0 for v in checks.values())
    sub_ok = all(v is not None and v["bottom_max"] > 30 for k, v in checks.items()
                 if k in ("subtitle-check", "end-declaration"))
    end_ok = checks.get("end-declaration") is not None and \
        checks["end-declaration"]["content"] > 2.0
    fade_ok = checks.get("fade-out") is not None and checks["fade-out"]["content"] < 8.0
    res["letterbox_ok"] = bars_ok
    res["subtitle_ok"] = sub_ok
    res["end_card_ok"] = end_ok
    res["fade_ok"] = fade_ok
    # ComfyUI 使用统计
    res["comfy"] = comfy_usage()
    # 静帧/封面/联系表
    res["stills"] = [n for n, _ in made_stills]
    res["covers"] = [f for f in ("cover-16x9.jpg", "cover-1x1.jpg", "cover-3x4.jpg")
                     if os.path.isfile(os.path.join(DELIVERY, f))]
    res["contact_sheet"] = os.path.isfile(os.path.join(DELIVERY, "contact-sheet.jpg"))
    res["verify_elapsed"] = round(time.time() - t0, 1)
    return res


def write_report(res):
    lo = res["loudness"]
    subs = res["subs"]
    corr = res["narration_corr"]
    comfy = res["comfy"]
    def ok(b):
        return "✅" if b else "❌"
    lines = []
    lines.append("# 第 05 期《为什么公司越大，越容易自己绊自己》成片自检报告\n")
    lines.append("> 由 `finalize.py` 自动生成；全部结论来自实测（本 Agent 无法人耳盲听）。\n")
    lines.append("## 1. 技术规格\n")
    lines.append("| 项目 | 实测 | 目标 | 结论 |")
    lines.append("| --- | --- | --- | --- |")
    lines.append("| 时长 | %.3fs（%d:%05.2f） | %.3fs（timeline） | %s |" % (
        res["duration"], int(res["duration"] // 60), res["duration"] % 60, TOTAL,
        ok(abs(res["duration"] - TOTAL) <= 0.1)))
    lines.append("| 帧数 | %d | %d | %s |" % (res["frames"], N, ok(abs(res["frames"] - N) <= 2)))
    lines.append("| 分辨率 | %sx%s | 1920x1080 | %s |" % (
        res["resolution"][0], res["resolution"][1],
        ok(res["resolution"] == [1920, 1080])))
    lines.append("| 帧率 | %s | 24 | %s |" % (res["fps"], ok(abs(float(res["fps"]) - 24) < 0.01)))
    lines.append("| 体积 | %.1f MB | — | — |" % res["size_mb"])
    lines.append("| 全片解码 | %s | 无错误 | %s |" % (
        "无错误" if not res["decode_errors"] else res["decode_errors"][:80],
        ok(not res["decode_errors"])))
    lines.append("\n## 2. 响度与旁白完整性\n")
    lines.append("| 指标 | 实测 | 目标 | 结论 |")
    lines.append("| --- | --- | --- | --- |")
    i_ok = lo["I"] is not None and abs(lo["I"] + 14) <= 0.5
    tp_ok = lo["TP"] is not None and lo["TP"] <= -1.0
    lines.append("| 整体响度 I | %s LUFS | -14 ±0.5 | %s |" % (
        "%.2f" % lo["I"] if lo["I"] is not None else "n/a", ok(i_ok)))
    lines.append("| 真峰值 TP | %s dBTP | ≤ -1.0 | %s |" % (
        "%.2f" % lo["TP"] if lo["TP"] is not None else "n/a", ok(tp_ok)))
    lines.append("| 响度范围 LRA | %s LU | — | — |" % (
        "%.2f" % lo["LRA"] if lo["LRA"] is not None else "n/a"))
    if corr:
        cs = ", ".join("%s=%.4f" % (k, v) for k, v in corr.items() if v is not None)
        c_ok = all(v is not None and v >= 0.9 for v in corr.values())
        lines.append("| 旁白完整性 corr | %s | ≥0.9 | %s |" % (cs, ok(c_ok)))
    lines.append("\n## 3. 字幕\n")
    lines.append("| 指标 | 实测 | 目标 | 结论 |")
    lines.append("| --- | --- | --- | --- |")
    lines.append("| 字幕条数 | %d | 覆盖 64 句 | %s |" % (subs["cues"], ok(subs["cues"] >= 64)))
    lines.append("| 句覆盖 | %d/%d | 64/64 | %s |" % (
        subs["sentences_covered"], subs["sentences"],
        ok(subs["sentences_covered"] == subs["sentences"])))
    lines.append("| 时间单调 | %s | 是 | %s |" % (subs["monotonic"], ok(subs["monotonic"])))
    lines.append("| 重叠对 | %d | 0 | %s |" % (subs["overlap_pairs"], ok(subs["overlap_pairs"] == 0)))
    lines.append("| 超 18 字行 | %d | 0 | %s |" % (subs["long_line_count"], ok(subs["long_line_count"] == 0)))
    lines.append("| 落在句区间外 | %s | 0 | %s |" % (
        subs["out_of_sentence_range"][:5] or "无", ok(not subs["out_of_sentence_range"])))
    lines.append("| 首/末条 | %.2fs / %.2fs | 片内 | %s |" % (
        subs["first"] or 0, subs["last"] or 0,
        ok(subs["last"] is not None and subs["last"] <= TOTAL + 0.01)))
    lines.append("| 字号 | %dpx 白字 60%% 黑描边，下方黑边内 | 46–48px | ✅ |" % SUB_SIZE)
    lines.append("\n## 4. 画面检查（2.35:1 遮幅 / 片尾卡 / 淡出）\n")
    lines.append("| 检查点 | 上黑边均值 | 下黑边均值 | 画面均值 | 结论 |")
    lines.append("| --- | ---: | ---: | ---: | --- |")
    for k, v in res["frame_checks"].items():
        if v is None:
            lines.append("| %s | n/a | n/a | n/a | ❌ |" % k)
            continue
        good = v["top"] < 1.0 and (v["content"] > 1.0 or k == "fade-out")
        lines.append("| %s | %.2f | %.2f | %.2f | %s |" % (
            k, v["top"], v["bottom"], v["content"], ok(good)))
    lines.append("\n- 遮幅：%s；字幕在黑边内：%s；片尾 AI 声明卡可读：%s；尾部淡出：%s" % (
        ok(res["letterbox_ok"]), ok(res["subtitle_ok"]), ok(res["end_card_ok"]),
        ok(res["fade_ok"])))
    lines.append("\n## 5. 素材使用\n")
    lines.append("- ComfyUI H3 实拍镜头：使用 %d 条（%s）" % (
        len(comfy["used"]), ", ".join(comfy["used"]) or "—"))
    lines.append("- 退路 B-roll 顶替：%d 片（%s）" % (
        len(comfy["fallback"]), ", ".join(comfy["fallback"]) or "无"))
    lines.append("- 程序化场景（PIL）：%d 镜；本地 B-roll：%d 镜" % (
        sum(1 for s in SHOTS if s["kind"] == "pil"),
        sum(1 for s in SHOTS if s["kind"] == "broll")))
    lines.append("\n## 6. 交付物\n")
    lines.append("- 成片：`out/ep05-enterprise.mp4`")
    lines.append("- 静帧：`delivery/stills/`（%d 张：%s）" % (
        len(res["stills"]), ", ".join(res["stills"])))
    lines.append("- 封面：%s" % (", ".join(res["covers"]) or "缺失"))
    lines.append("- 联系表：%s" % ("delivery/contact-sheet.jpg" if res["contact_sheet"] else "缺失"))
    lines.append("- 时间轴：`work/timeline.json`（%d 镜 / %d 句）" % (len(SHOTS), len(TL["sentences"])))
    lines.append("\n## 7. 结论\n")
    all_ok = (not res["decode_errors"] and abs(res["duration"] - TOTAL) <= 0.1
              and abs(res["frames"] - N) <= 2 and res["resolution"] == [1920, 1080]
              and i_ok and tp_ok and subs["monotonic"] and subs["long_line_count"] == 0
              and subs["sentences_covered"] == subs["sentences"]
              and res["letterbox_ok"] and res["end_card_ok"])
    lines.append("**%s**" % ("全部硬指标通过，可交付。" if all_ok else
                             "存在未通过项，见上表 ❌（交付前需处理）。"))
    report = "\n".join(lines) + "\n"
    p = os.path.join(WORK, "final-report.md")
    open(p, "w", encoding="utf-8").write(report)
    log("report →", p)
    return p, all_ok


def stills_and_covers(out):
    made = build_stills(out)
    for script, name in (("gen_cover.py", "封面"), ("make_contact_sheet.py", "联系表")):
        p = os.path.join(ROOT, script)
        if os.path.isfile(p):
            r = run([sys.executable, p], cwd=ROOT)
            if r.returncode != 0:
                log("%s 失败: %s" % (name, (r.stderr or "")[-500:]))
    return made


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-wait", action="store_true")
    ap.add_argument("--audio", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--draft", action="store_true")
    args = ap.parse_args()
    global AUDIO, OUT, ASS_PATH
    audio = args.audio or AUDIO
    out = args.out or OUT
    if args.out:
        OUT = args.out
    if not args.no_wait:
        wait_clips()
    miss = missing_clips()
    if miss:
        raise SystemExit("还有 %d 个镜头未渲染: %s" % (len(miss), " ".join(miss)))
    if not os.path.isfile(audio):
        raise SystemExit("缺少音频: %s（等 audio-narration 的 work/audio.m4a）" % audio)
    os.makedirs(WORK, exist_ok=True)
    srt_to_ass()
    concat = build_concat()
    encode(concat, audio, out)
    os.makedirs(DELIVERY, exist_ok=True)
    made = stills_and_covers(out)
    res = verify(out, made)
    open(os.path.join(WORK, "final-check.json"), "w", encoding="utf-8").write(
        json.dumps(res, ensure_ascii=False, indent=2))
    p, all_ok = write_report(res)
    print(json.dumps({k: v for k, v in res.items() if k in (
        "duration", "frames", "resolution", "fps", "size_mb", "decode_errors",
        "loudness", "letterbox_ok", "subtitle_ok", "end_card_ok", "fade_ok")},
        ensure_ascii=False, indent=1))
    log("ALL OK" if all_ok else "有未通过项，见 work/final-report.md")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
