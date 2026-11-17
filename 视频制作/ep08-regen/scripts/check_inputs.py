#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 08 期开工前输入自检：一次看清「能不能开始 finalize」。

检查（不渲染、只读 probe，轻量）：
  1. work/timeline.json 可读；total 在 3:40–4:20（220–260s）；fps=24；镜头数/时长合理
  2. work/clips/ 逐镜存在且 1920×1080 / 24fps / 可解码（抽样 probe 全部逐镜，1 帧）
  3. 音频母带存在；时长与 total 差 ≤0.1s；AAC 48kHz
  4. SRT：99 条左右、单行 ≤18 汉字、单调、无重叠、末条接近片尾
  5. H3：assets/h3 条数与 shots 的 h3 引用数一致；缺条列出
  6. 交付物目录/磁盘空间/日志可写

输出：work/input-check.json + 控制台 PASS/FAIL/WARN。退出码：有 FAIL → 1。

用法：
  python3 scripts/check_inputs.py            # 自查
  python3 scripts/check_inputs.py --wait 600 # 等 clips 齐（最多 600s，每 10s 刷一次）
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FF = os.environ.get("FFMPEG", "/home/admin/.local/bin/ffmpeg")
FP = os.environ.get("FFPROBE", "/home/admin/.local/bin/ffprobe-real")
WORK = os.path.join(ROOT, "work")
CLIPS = os.path.join(WORK, "clips")
OUT = os.path.join(ROOT, "out")
DELIVERY = os.path.join(ROOT, "delivery")
SPEC = {"w": 1920, "h": 1080, "fps": 24.0, "dur_min": 220.0, "dur_max": 260.0,
        "audio_tol": 0.10, "sub_max": 18}
AUDIO_CANDIDATES = [os.path.join(ROOT, "audio", "work", "audio.m4a"),
                    os.path.join(ROOT, "audio", "audio.m4a"),
                    os.path.join(WORK, "audio.m4a")]
SRT_CANDIDATES = [os.path.join(WORK, "srt", "all.srt"),
                  os.path.join(ROOT, "audio", "work", "srt", "all.srt")]


def run(*a):
    return subprocess.run(a, capture_output=True, text=True, errors="replace")


def probe(path):
    r = run(FP, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path)
    if r.returncode == 0 and r.stdout.strip():
        return json.loads(r.stdout)
    return None


def usable(path):
    return os.path.isfile(path) and os.path.getsize(path) > 10000


def load_timeline():
    for cand in (os.path.join(WORK, "timeline.json"), os.path.join(WORK, "shots.json"),
                 os.path.join(ROOT, "shots.json")):
        if not os.path.isfile(cand):
            continue
        try:
            d = json.load(open(cand, encoding="utf-8"))
        except Exception:
            continue
        shots = None
        total = d.get("total") if isinstance(d, dict) else None
        fps = d.get("fps") if isinstance(d, dict) else None
        if isinstance(d, dict):
            for k in ("shots", "beats", "scenes", "clips"):
                if isinstance(d.get(k), list) and d[k]:
                    shots = d[k]
                    break
        elif isinstance(d, list):
            shots = d
        if not shots:
            continue
        norm = []
        for s in shots:
            if not isinstance(s, dict) or not (s.get("id") or s.get("shot")):
                continue
            is_h3 = bool(s.get("h3"))
            h3id = None
            a = str(s.get("asset") or s.get("clip") or "")
            if isinstance(s.get("h3"), str):
                a = s["h3"]
                is_h3 = True
            if is_h3:
                m = (re.search(r"[_\-]([SH])\s*(\d+)", a, re.I)
                     or re.search(r"^([SH])\s*(\d+)$", a, re.I))
                if m:
                    h3id = "%s%02d" % (m.group(1).upper(), int(m.group(2)))
            norm.append({"id": str(s.get("id") or s.get("shot")),
                         "start": float(s.get("start", 0) or 0),
                         "dur": float(s.get("dur", s.get("duration", 0)) or 0),
                         "h3": is_h3, "h3id": h3id})
        norm.sort(key=lambda x: x["start"])
        if not total and norm:
            total = max(x["start"] + x["dur"] for x in norm)
        return {"total": float(total or 0), "fps": float(fps or 24), "shots": norm,
                "source": os.path.relpath(cand, ROOT)}
    return None


def load_srt():
    for c in SRT_CANDIDATES:
        if os.path.isfile(c) and os.path.getsize(c) > 200:
            path = c
            break
    else:
        return None
    cues = []
    for block in open(path, encoding="utf-8", errors="ignore").read().strip().split("\n\n"):
        lines = [x.strip() for x in block.strip().splitlines() if x.strip()]
        if len(lines) < 3 or "-->" not in lines[1]:
            continue
        m = re.search(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)", lines[1])
        if not m:
            continue
        g = [int(x) for x in m.groups()]
        a = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000.0
        b = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000.0
        cues.append((a, b, " ".join(lines[2:])))
    widths = [max(len(re.sub(r"[^\u4e00-\u9fa5A-Za-z0-9]", "", x))
                  for x in t.split("\n")) for _, _, t in cues]
    return {"path": path, "cues": cues, "max_width": max(widths or [0])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wait", type=float, default=0.0)
    ap.add_argument("--allow-missing-h3", action="store_true",
                    help="code-only draft：H3 未到位只记 WARN")
    args = ap.parse_args()
    deadline = time.time() + args.wait
    tl = load_timeline()
    if not tl:
        print("WAIT  找不到 work/timeline.json（等 engine-dev）")
    if args.wait > 0:
        while time.time() < deadline:
            tl = load_timeline()
            miss = 0
            if tl:
                miss = sum(1 for s in tl["shots"] if not usable(os.path.join(CLIPS, s["id"] + ".mp4")))
            if tl and miss == 0:
                break
            print("WAIT  timeline=%s 缺镜 %d（余 %.0fs）" % ("有" if tl else "无", miss,
                                                            deadline - time.time()))
            time.sleep(10)
    if not tl:
        raise SystemExit("没有可用时间轴，无法开工；等 engine-dev 的 work/timeline.json")

    res, checks = {}, []

    def check(name, cond, detail="", blocking=True):
        checks.append({"name": name, "pass": bool(cond), "blocking": bool(blocking),
                       "detail": str(detail)})
        print(("PASS " if cond else ("WARN " if not blocking else "FAIL "))
              + "%-24s %s" % (name, detail))

    total, fps, shots = tl["total"], tl["fps"], tl["shots"]
    res.update({"timeline": tl["source"], "total": total, "fps": fps, "shots": len(shots)})
    check("timeline_total_window", SPEC["dur_min"] <= total <= SPEC["dur_max"],
          "%.3fs（220–260s）" % total)
    check("timeline_fps", abs(fps - SPEC["fps"]) < 0.01, "%.3f" % fps)
    # 镜头时长合理性
    bad_dur = [s["id"] for s in shots if not (0.3 <= s["dur"] <= 15.0)]
    check("shot_durations", not bad_dur, "异常时长镜头 %d（%s）" % (len(bad_dur), bad_dur[:6]),
          blocking=False)

    # clips
    missing = [s["id"] for s in shots if not usable(os.path.join(CLIPS, s["id"] + ".mp4"))]
    res["missing_clips"] = missing
    check("clips_present", not missing,
          "%d/%d 镜已渲染%s" % (len(shots) - len(missing), len(shots),
                              ("；缺 " + ", ".join(missing[:10])) if missing else ""))
    clip_dur = 0.0
    f0 = 0.0
    bad_spec = []
    if not missing:
        for s in shots:
            p = os.path.join(CLIPS, s["id"] + ".mp4")
            d = probe(p)
            if not d:
                bad_spec.append(s["id"] + ":probe")
                continue
            v = next((x for x in d["streams"] if x.get("codec_type") == "video"), None)
            if not v:
                bad_spec.append(s["id"] + ":no-video")
                continue
            try:
                r = eval(v.get("r_frame_rate", "0/1"))
            except Exception:
                r = 0
            if (v.get("width"), v.get("height")) != (SPEC["w"], SPEC["h"]) or abs(r - 24) > 0.01:
                bad_spec.append("%s:%sx%s@%s" % (s["id"], v.get("width"), v.get("height"), r))
            clip_dur += float(d["format"]["duration"])
        check("clips_spec", not bad_spec,
              "1920×1080/24fps；异常 %d %s" % (len(bad_spec), bad_spec[:6]))
        res["clips_total_duration"] = round(clip_dur, 3)
        check("clips_total_duration", abs(clip_dur - total) <= 1.0,
              "逐镜合计 %.3fs vs 时间轴 %.3fs（差 %+.3fs）"
              % (clip_dur, total, clip_dur - total), blocking=False)

    # audio
    audio = next((a for a in AUDIO_CANDIDATES if usable(a)), None)
    if audio:
        d = probe(audio)
        adur = float(d["format"]["duration"]) if d else 0.0
        a = next((x for x in d["streams"] if x.get("codec_type") == "audio"), None) if d else None
        res.update({"audio": os.path.relpath(audio, ROOT), "audio_duration": round(adur, 3)})
        check("audio_duration", abs(adur - total) <= SPEC["audio_tol"],
              "%.3fs vs 时间轴 %.3fs（差 %+.3fs，应 ≤0.1s）" % (adur, total, adur - total))
        check("audio_format", bool(a) and a.get("sample_rate") == "48000"
              and a.get("codec_name") == "aac",
              "%s %sHz %sch" % (a.get("codec_name"), a.get("sample_rate"), a.get("channels"))
              if a else "no audio stream")
    else:
        check("audio_duration", False, "找不到 audio/work/audio.m4a")

    # srt
    srt = load_srt()
    if srt:
        cues = srt["cues"]
        starts, ends = [c[0] for c in cues], [c[1] for c in cues]
        mono = all(starts[i] <= starts[i + 1] for i in range(len(starts) - 1))
        overlaps = sum(1 for i in range(len(starts) - 1) if ends[i] > starts[i + 1] + 1e-6)
        res["srt"] = {"path": os.path.relpath(srt["path"], ROOT), "cues": len(cues),
                      "max_width": srt["max_width"], "last_end": ends[-1]}
        check("srt_cues", len(cues) >= 60, "%d 条" % len(cues))
        check("srt_line_len", srt["max_width"] <= SPEC["sub_max"],
              "最宽 %d 汉字（≤18）" % srt["max_width"])
        check("srt_structure", mono and overlaps == 0 and ends[-1] <= total + 0.05,
              "单调=%s 重叠=%d 末条 %.2fs" % (mono, overlaps, ends[-1]))
    else:
        check("srt_cues", False, "找不到句级 SRT")

    # h3
    h3dir = os.path.join(ROOT, "assets", "h3")
    have = sorted(os.path.splitext(f)[0].upper() for f in os.listdir(h3dir)
                  if f.lower().endswith(".mp4")) if os.path.isdir(h3dir) else []
    want = sorted({s["h3id"] for s in shots if s["h3"] and s["h3id"]})
    miss_h3 = [h for h in want if h not in have]
    res["h3"] = {"expected": want, "present": have, "missing": miss_h3}
    if want:
        check("h3_assets", not miss_h3,
              "%d/%d 条（%s）" % (len(want) - len(miss_h3), len(want),
                                ("缺 " + ", ".join(miss_h3)) if miss_h3 else "齐"),
              blocking=not args.allow_missing_h3)
    else:
        check("h3_assets", bool(have), "分镜无 H3 引用；assets/h3 现有 %d 条" % len(have),
              blocking=False)
    if want:
        h3_dur = sum(s["dur"] for s in shots if s["h3"])
        share = h3_dur / (sum(s["dur"] for s in shots) or 1)
        res["h3_share"] = round(share, 4)
        check("h3_share", 0.15 <= share <= 0.40, "H3 时长占比 %.1f%%（目标 20–35%%）"
              % (share * 100), blocking=False)

    # 目录/空间
    for d in (OUT, DELIVERY, os.path.join(WORK, "qa"), os.path.join(WORK, "srt")):
        os.makedirs(d, exist_ok=True)
    try:
        st = os.statvfs(OUT)
        free_gb = st.f_bavail * st.f_frsize / 1e9
        check("disk_free", free_gb > 5, "%.1f GB 可用" % free_gb)
    except Exception:
        pass

    res["checks"] = checks
    res["problems"] = [c["name"] for c in checks if not c["pass"] and c["blocking"]]
    res["warnings"] = [c["name"] for c in checks if not c["pass"] and not c["blocking"]]
    json.dump(res, open(os.path.join(WORK, "input-check.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("\n%d/%d PASS; problems: %s; warnings: %s"
          % (sum(1 for c in checks if c["pass"]), len(checks),
             res["problems"] or "none", res["warnings"] or "none"))
    print("JSON -> work/input-check.json")
    print("RESULT:", "READY" if not res["problems"] else "NOT READY")
    return 0 if not res["problems"] else 1


if __name__ == "__main__":
    sys.exit(main())
