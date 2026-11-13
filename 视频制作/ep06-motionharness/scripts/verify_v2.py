#!/usr/bin/env python3
"""Lead 独立验收：对 MotionHarness 导出的 v2 成片做硬校验。"""
import json, subprocess, sys, os, re
from PIL import Image, ImageStat

FF = "/home/admin/.local/bin/ffmpeg"
FP = "/home/admin/.local/bin/ffprobe-real"
FILM = sys.argv[1] if len(sys.argv) > 1 else "/app/vedio/ep06-mh/out/ep06-mh-v2.mp4"
EXPECT = {"w": 1920, "h": 1080, "fps": 24.0, "dur": 230.2056}
TMP = "/tmp/v2verify"

def run(*a):
    return subprocess.run(a, capture_output=True, text=True, errors="replace")

def probe():
    return json.loads(run(FP, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", FILM).stdout)

def frame_at(t, out):
    run(FF, "-v", "error", "-y", "-ss", str(t), "-i", FILM, "-frames:v", "1", out)

def region_stats(png, box):
    im = Image.open(png).convert("L").crop(box)
    st = ImageStat.Stat(im)
    return st.mean[0], im.getextrema()

def main():
    os.makedirs(TMP, exist_ok=True)
    p = probe()
    v = next(s for s in p["streams"] if s["codec_type"] == "video")
    a = [s for s in p["streams"] if s["codec_type"] == "audio"]
    dur = float(p["format"]["duration"])
    fps = eval(v["r_frame_rate"])
    print(json.dumps({"file": FILM, "size_mb": round(os.path.getsize(FILM)/1e6, 2),
        "width": v["width"], "height": v["height"], "fps": fps, "codec": v["codec_name"],
        "duration": dur, "nb_frames": v.get("nb_frames"),
        "audio": [{"codec": s["codec_name"], "ch": s["channels"], "sr": s["sample_rate"]} for s in a]},
        ensure_ascii=False, indent=1))
    ok = True
    def check(name, cond, detail=""):
        nonlocal ok
        print(("PASS " if cond else "FAIL ") + name + (" " + detail if detail else ""))
        ok = ok and cond
    check("resolution", v["width"] == EXPECT["w"] and v["height"] == EXPECT["h"])
    check("fps", abs(fps - EXPECT["fps"]) < 0.01, f"{fps}")
    check("duration", abs(dur - EXPECT["dur"]) < 0.2, f"{dur:.3f}")
    check("has_audio", bool(a))
    r = run(FF, "-v", "error", "-i", FILM, "-f", "null", "-")
    check("decode_clean", r.returncode == 0 and not r.stderr.strip(), r.stderr.strip()[:160])
    # loudness
    r = run(FF, "-hide_banner", "-nostats", "-i", FILM, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-")
    m = re.findall(r"\{[^{}]*\"input_i\"[\s\S]*?\}", r.stderr)
    try:
        j = json.loads(m[-1]); i, tp = float(j["input_i"]), float(j["input_tp"])
        check("loudness_I", -15.0 <= i <= -13.5, f"{i}")
        check("true_peak", tp <= -1.0, f"{tp}")
        print(f"    loudness: I={i} LUFS TP={tp} dBTP LRA={j.get('input_lra')}")
    except Exception as e:
        check("loudness_parse", False, str(e) + " stderr_tail=" + r.stderr[-300:])
    # letterbox + content + motion
    times = [1.0, 22.5, 61.0, 86.8, 137.0, 182.0, 216.0]
    for t in times:
        f = f"{TMP}/f{t}.png"; frame_at(t, f)
        top, _ = region_stats(f, (0, 0, 1920, 60))
        bot, _ = region_stats(f, (0, 1020, 1920, 1080))
        mid, _ = region_stats(f, (0, 400, 1920, 600))
        check(f"letterbox@{t}", top < 6 and bot < 6, f"top={top:.1f} bot={bot:.1f}")
        check(f"content@{t}", mid > 4, f"mid={mid:.1f}")
    # subtitle band during speech vs gap
    def band_var(t):
        f = f"{TMP}/s{t}.png"; frame_at(t, f)
        return region_stats(f, (160, 930, 1760, 1000))[1]
    lo, hi = band_var(5.0), band_var(16.2)
    check("subtitle_present", hi - lo > 40, f"range={hi-lo}")
    check("subtitle_absent_in_gap", hi - lo < 40, f"range={hi-lo}")
    # vertical motion: frames differ
    f1, f2 = f"{TMP}/m1.png", f"{TMP}/m2.png"
    frame_at(80.0, f1); frame_at(80.5, f2)
    d = ImageStat.Stat(Image.open(f1).convert("L")).mean[0] - ImageStat.Stat(Image.open(f2).convert("L")).mean[0]
    check("motion", abs(d) > 0.01, f"mean_diff={abs(d):.3f}")
    print("\nRESULT:", "ALL OK" if ok else "PROBLEMS")
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
