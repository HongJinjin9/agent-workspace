#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 08 期《电动车松开油门为什么能充电》成片收尾（交付 owner 专用）。

职责：
  1) 全片渲染编排的收尾：把逐镜视频（engine-dev 的渲染产物）拼成一条时间轴；
  2) 统一调色 + 2.35:1 上下 132px 遮幅 + 胶片颗粒 + ASS 字幕 + 首尾淡入淡出；
  3) 用 audio-engineer 的音频母带 `audio/work/audio.m4a` remux（不重新混音）；
  4) 输出 master `out/ep08-regen.mp4` + web 版 `out/ep08-regen-web.mp4`；
  5) 写 `work/finalize.json`（模式 / 输入 / 耗时 / 体积 / sha256 / 编码命令）。

并发纪律：全程持 `flock(/tmp/ep08-finalize.lock)`——同一时刻只允许一个全片编码/拼接进程。
（engine-dev 的逐镜渲染由 `scripts/render_all.sh` 的 `/tmp/ep08-render.lock` 管，两把锁互不替代。）

用法：
  python3 scripts/finalize.py                     # clips 模式：work/clips/<id>.mp4 → master + web
  python3 scripts/finalize.py --draft             # 草稿：veryfast/crf27，快速看片用
  python3 scripts/finalize.py --wait 600          # 等 clips 齐（最多 600s）
  python3 scripts/finalize.py --input work/film-raw.mp4           # raw 模式：整合渲染产出的全片
  python3 scripts/finalize.py --input work/film-raw.mp4 --baked    # 已烘焙遮幅/字幕：视频流 copy 后 remux
  python3 scripts/finalize.py --no-subs --no-grade                 # 仅拼接+母带（调试）
  python3 scripts/finalize.py --web-only                           # 从已有 master 重做 web 版
  python3 scripts/finalize.py --verify                             # 收尾完顺带跑 verify_ep08.py
"""
import argparse
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
import time

# 资源纪律（Lead 裁决）：cgroup 实际 4 核 / 6GB（nproc=128 是宿主核数）。
# Python 侧限制 BLAS/OMP 线程；ffmpeg 侧统一 -threads 2 / -filter_threads 2；x264 -threads 4。
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FF = os.environ.get("FFMPEG", "/home/admin/.local/bin/ffmpeg")
FP = os.environ.get("FFPROBE", "/home/admin/.local/bin/ffprobe-real")
WORK = os.path.join(ROOT, "work")
OUT_DIR = os.path.join(ROOT, "out")
CLIPS_DIR = os.environ.get("EP08_CLIPS", os.path.join(WORK, "clips"))
ASS_PATH = os.path.join(WORK, "srt", "all.ass")
MASTER = os.path.join(OUT_DIR, "ep08-regen.mp4")
WEB = os.path.join(OUT_DIR, "ep08-regen-web.mp4")
LOG = os.path.join(WORK, "finalize.log")
LOCK = "/tmp/ep08-finalize.lock"
RENDER_LOCK = "/tmp/ep08-render.lock"
# cgroup 实测：cpu.max=4 核 / memory.max=6GB（nproc 报 128 是宿主核数）。
# x264 -threads 0 会在 128 核上开满线程缓冲，本机多次被 OOM kill；固定线程上限。
THREADS = max(1, min(4, int(os.environ.get("EP08_FFMPEG_THREADS", "4"))))
MEM_LIMIT_GB = 6.0

SPEC = {
    "w": 1920, "h": 1080, "fps": 24, "bar": 132,
    "sub_size": 48,           # SPEC：该系列 46–48px，第 05 期定 48
    "master_crf": 19,
    "web_crf": 23,
}
AUDIO_CANDIDATES = [
    os.path.join(ROOT, "audio", "work", "audio.m4a"),
    os.path.join(ROOT, "audio", "audio.m4a"),
    os.path.join(WORK, "audio.m4a"),
    os.path.join(ROOT, "audio", "work", "master.m4a"),
]
SRT_CANDIDATES = [
    os.path.join(WORK, "srt", "all.srt"),
    os.path.join(ROOT, "audio", "work", "srt", "all.srt"),
    os.path.join(ROOT, "audio", "srt", "all.srt"),
    os.path.join(ROOT, "narration", "all.srt"),
]


def log(msg):
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
    print(line, flush=True)
    try:
        os.makedirs(WORK, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def run(*a, **kw):
    return subprocess.run(a, capture_output=True, text=True, errors="replace", **kw)


def sha256(path, n=1 << 20):
    if not os.path.isfile(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(n), b""):
            h.update(chunk)
    return h.hexdigest()


def wait_render_lock(timeout=1800):
    """engine 逐镜渲染持 /tmp/ep08-render.lock；finalize 启动前等它释放（最多 timeout 秒）。"""
    if not os.path.exists(RENDER_LOCK):
        return True
    f = open(RENDER_LOCK, "w")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(f, fcntl.LOCK_UN)
        f.close()
        return True
    except BlockingIOError:
        log("engine 逐镜渲染进行中（%s 被占用），等待其结束（最多 %ds）……"
            % (RENDER_LOCK, timeout))
        deadline = time.time() + timeout
        while time.time() < deadline:
            time.sleep(5)
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(f, fcntl.LOCK_UN)
                f.close()
                log("渲染锁已释放，继续 finalize")
                return True
            except BlockingIOError:
                continue
        log("警告：等待渲染锁超时，仍继续 finalize（可能与 render 争抢 CPU/内存）")
        return False


def require_lock():
    os.makedirs(WORK, exist_ok=True)
    f = open(LOCK, "w")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        log("另一个全片渲染/编码正在运行（%s 被占用），排队等待……" % LOCK)
        fcntl.flock(f, fcntl.LOCK_EX)
    f.write(str(os.getpid()))
    f.flush()
    return f


# ------------------------------------------------------------------ resolve inputs
def probe(path):
    r = run(FP, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path)
    if r.returncode == 0 and r.stdout.strip():
        return json.loads(r.stdout)
    info = {"format": {"duration": 0.0}, "streams": []}
    e = (run(FF, "-hide_banner", "-i", path).stderr or "")
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", e)
    if m:
        info["format"]["duration"] = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    m = re.search(r"Video: ([^,]+),.*?, (\d+)x(\d+)", e)
    if m:
        info["streams"].append({"codec_type": "video", "codec_name": m.group(1).strip(),
                                "width": int(m.group(2)), "height": int(m.group(3)),
                                "r_frame_rate": "24/1"})
    return info


def probe_duration(path):
    try:
        return float(probe(path)["format"]["duration"])
    except Exception:
        return 0.0


def load_timeline():
    """返回 (total, fps, shots, source)。shots=[{id,dur,start?}]，按时间顺序。"""
    cands = [
        (os.path.join(WORK, "timeline.json"), "work/timeline.json"),
        (os.path.join(WORK, "shots.json"), "work/shots.json"),
        (os.path.join(ROOT, "shots.json"), "shots.json"),
    ]
    for path, label in cands:
        if not os.path.isfile(path):
            continue
        try:
            d = json.load(open(path, encoding="utf-8"))
        except Exception:
            continue
        shots = None
        total = None
        fps = None
        if isinstance(d, dict):
            for k in ("shots", "beats", "scenes", "clips"):
                if isinstance(d.get(k), list) and d[k]:
                    shots = d[k]
                    break
            for k in ("total", "duration", "duration_s", "total_s"):
                if d.get(k):
                    total = float(d[k])
                    break
            fps = d.get("fps") or d.get("frame_rate")
        elif isinstance(d, list):
            shots = d
        if not shots:
            continue
        norm = []
        for s in shots:
            if not isinstance(s, dict) or not (s.get("id") or s.get("shot")):
                continue
            sid = str(s.get("id") or s.get("shot"))
            norm.append({
                "id": sid,
                "start": float(s.get("start", s.get("start_s", 0)) or 0),
                "dur": float(s.get("dur", s.get("duration", s.get("duration_s", 0))) or 0),
                "end": float(s.get("end", 0) or 0),
                "h3": s.get("h3") or s.get("clip") or s.get("asset"),
            })
        if not norm:
            continue
        norm = [p for _, p in sorted(enumerate(norm), key=lambda kv: (kv[1]["start"], kv[0]))]
        if not total:
            total = max((x["start"] + x["dur"]) if x["dur"] else x["end"] for x in norm)
        return float(total), float(fps or SPEC["fps"]), norm, label
    return None, None, None, None


def resolve_audio(path=None):
    if path:
        return path if os.path.isfile(path) else None
    for c in AUDIO_CANDIDATES:
        if os.path.isfile(c) and os.path.getsize(c) > 50000:
            return c
    return None


def resolve_srt(path=None):
    if path:
        return path if os.path.isfile(path) else None
    for c in SRT_CANDIDATES:
        if os.path.isfile(c) and os.path.getsize(c) > 200:
            return c
    return None


# ------------------------------------------------------------------ subtitle
def parse_srt(path):
    cues = []
    raw = open(path, encoding="utf-8", errors="ignore").read().strip().split("\n\n")
    for block in raw:
        lines = [x for x in block.splitlines() if x.strip()]
        if len(lines) < 2:
            continue
        m = re.match(r"(\d+):(\d+):(\d+)[,.](\d+) --> (\d+):(\d+):(\d+)[,.](\d+)", lines[1])
        if not m:
            continue
        g = [int(x) for x in m.groups()]
        a = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000.0
        b = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000.0
        text = "\n".join(lines[2:])
        cues.append((a, b, text))
    return cues


def srt_to_ass(srt, ass, sub_size=48):
    cues = parse_srt(srt)
    if not cues:
        raise SystemExit("SRT 解析到 0 条: %s" % srt)

    def ts(t):
        return "%d:%02d:%05.2f" % (int(t // 3600), int((t % 3600) // 60), t % 60)

    def esc(t):
        return (t.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
                .replace("\n", "\\N"))

    # 字幕落在下方黑边内：132px 黑边，48px 字，MarginV=50（白字上沿 ~950px，下沿 ~1010px）
    margin_v = 50 if sub_size <= 48 else 44
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,Noto Sans CJK SC,{size},&H00F2EEE5,&H00FFFFFF,&H50000000,&H64000000,0,0,0,0,100,100,0.5,0,1,2.4,1.2,2,120,120,{mv},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""".format(size=int(sub_size), mv=margin_v)
    lines = [header]
    for a, b, text in cues:
        lines.append("Dialogue: 0,%s,%s,Sub,,0,0,0,,%s" % (
            ts(max(0.0, a)), ts(max(a + 0.05, b)), esc(text)))
    os.makedirs(os.path.dirname(ass), exist_ok=True)
    open(ass, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    log("ASS 字幕 → %s（%d 条，%dpx，MarginV=%d）" % (ass, len(cues), sub_size, margin_v))
    return len(cues)


# ------------------------------------------------------------------ video assembly
def concat_clips(shots, clips_dir):
    missing = []
    files = []
    for s in shots:
        p = os.path.join(clips_dir, s["id"] + ".mp4")
        if not (os.path.isfile(p) and os.path.getsize(p) > 10000):
            missing.append(s["id"])
        files.append(p)
    if missing:
        raise SystemExit("还有 %d 个镜头未渲染：%s（先跑 scripts/render_all.sh 或等 engine-dev）"
                         % (len(missing), " ".join(missing[:12])))
    lst = os.path.join(WORK, "concat.txt")
    with open(lst, "w", encoding="utf-8") as f:
        for p in files:
            f.write("file '%s'\n" % p.replace("'", "'\\''"))
    concat = os.path.join(WORK, "video-concat.mp4")
    t0 = time.time()
    r = run(FF, "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
            "-i", lst, "-c", "copy", "-threads", "2", concat)
    if r.returncode != 0:
        raise SystemExit("concat 失败：\n" + (r.stderr or "")[-2000:])
    d = probe_duration(concat)
    log("拼接完成：%d 镜 → %.3fs（%.1fs）" % (len(shots), d, time.time() - t0))
    return concat, d


def detect_letterbox(path, bar):
    """抽一帧看上下 bar 区域是否已黑（判断 engine 是否已烘焙遮幅）。"""
    r = subprocess.run([FF, "-v", "error", "-ss", "1.0", "-i", path, "-frames:v", "1",
                        "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True)
    if r.returncode != 0 or len(r.stdout) < 1920 * 1080:
        return False, None
    try:
        import numpy as np
        a = np.frombuffer(r.stdout[:1920 * 1080], dtype=np.uint8).reshape(1080, 1920)
        top, bot = float(a[:bar].mean()), float(a[1080 - bar:].mean())
        return (top < 6.0 and bot < 8.0), (top, bot)
    except Exception:
        return False, None


def build_vf(grade=True, bars=True, ass=None, fade=True, total=None, draft=False, pad=0.0):
    parts = []
    if grade:
        parts += [
            "eq=contrast=1.045:brightness=0.012:saturation=1.06:gamma=1.003",
            "colorbalance=rs=-0.012:gs=0.0:bs=0.022:rh=0.012:bh=-0.012",
            "vignette=PI/5.2",
            "noise=alls=5:allf=t+u",
        ]
    if bars:
        parts += [
            "drawbox=x=0:y=0:w=iw:h=%d:color=black:t=fill" % SPEC["bar"],
            "drawbox=x=0:y=ih-%d:w=iw:h=%d:color=black:t=fill" % (SPEC["bar"], SPEC["bar"]),
        ]
    if ass:
        parts.append("ass=filename=%s:fontsdir=/usr/share/fonts/opentype/noto" % ass)
    if pad and pad > 0.05:
        # 逐镜帧数取整可能让拼接时长略短于时间轴：克隆末帧补齐，保证成片时长=时间轴
        parts.append("tpad=stop_mode=clone:stop_duration=%.3f" % pad)
    if fade and total:
        parts.append("fade=t=in:st=0:d=0.6")
        parts.append("fade=t=out:st=%.3f:d=1.2" % max(0.0, total - 1.25))
    parts.append("format=yuv420p")
    return ",".join(parts)


def x264_args(crf, draft=False):
    if draft:
        return ["-preset", "veryfast", "-crf", str(max(23, crf + 8)),
                "-threads", str(THREADS)]
    return ["-preset", "fast", "-crf", str(crf), "-tune", "film",
            "-threads", str(THREADS)]


def encode_master(src, audio, srt, total, out, draft=False,
                  grade=True, bars=True, fade=True, baked=False, pad=0.0):
    os.makedirs(os.path.dirname(out), exist_ok=True)
    ass = None
    if srt and not baked:
        ass = os.path.join(WORK, "srt", "all.ass")
        srt_to_ass(srt, ass, SPEC["sub_size"])
    vf = build_vf(grade=grade, bars=bars, ass=ass, fade=fade, total=total, draft=draft, pad=pad)
    cmd = [FF, "-hide_banner", "-loglevel", "error", "-y",
           "-i", src, "-i", audio,
           "-filter_threads", str(THREADS), "-filter_complex", "[0:v]%s[v]" % vf,
           "-map", "[v]", "-map", "1:a",
           "-t", "%.3f" % total,
           "-threads", "2", "-c:v", "libx264"] + x264_args(SPEC["master_crf"], draft) + [
           "-profile:v", "high", "-level", "4.1",
           "-x264-params", "rc-lookahead=12:sync-lookahead=0",
           "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
           "-movflags", "+faststart", out]
    t0 = time.time()
    log("编码 master（%s 模式）→ %s" % ("draft" if draft else "delivery", out))
    r = run(*cmd)
    if r.returncode != 0:
        raise SystemExit("master 编码失败：\n" + (r.stderr or "")[-3000:])
    dt = time.time() - t0
    size = os.path.getsize(out) / 1e6
    log("master 完成：%s  %.1f MB  %.1fs" % (out, size, dt))
    return {"cmd": " ".join(cmd), "elapsed_s": round(dt, 1), "size_mb": round(size, 2)}


def encode_web(master, out, draft=False):
    os.makedirs(os.path.dirname(out), exist_ok=True)
    cmd = [FF, "-hide_banner", "-loglevel", "error", "-y", "-threads", "2",
           "-i", master, "-filter_threads", str(THREADS),
           "-vf", "scale=1280:720:flags=lanczos",
           "-c:v", "libx264",
           "-preset", "fast", "-crf", str(SPEC["web_crf"] + (6 if draft else 0)),
           "-profile:v", "high", "-level", "4.1",
           "-x264-params", "rc-lookahead=12:sync-lookahead=0",
           "-threads", str(THREADS),
           "-c:a", "aac", "-b:a", "128k", "-ar", "48000",
           "-movflags", "+faststart", out]
    t0 = time.time()
    log("编码 web 版 → %s" % out)
    r = run(*cmd)
    if r.returncode != 0:
        raise SystemExit("web 编码失败：\n" + (r.stderr or "")[-3000:])
    dt = time.time() - t0
    size = os.path.getsize(out) / 1e6
    log("web 完成：%s  %.1f MB  %.1fs" % (out, size, dt))
    return {"cmd": " ".join(cmd), "elapsed_s": round(dt, 1), "size_mb": round(size, 2)}


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=None, help="raw 模式：整合渲染产出的全片视频")
    ap.add_argument("--baked", action="store_true",
                    help="raw 模式：全片已烘焙遮幅/字幕/调色（仅 remux 母带，视频流 copy）")
    ap.add_argument("--no-bars", action="store_true", help="不叠加 2.35:1 遮幅")
    ap.add_argument("--no-grade", action="store_true", help="不套统一调色链")
    ap.add_argument("--no-fade", action="store_true", help="不做首尾淡入淡出")
    ap.add_argument("--no-subs", action="store_true", help="不烧 ASS 字幕")
    ap.add_argument("--srt", default=None)
    ap.add_argument("--audio", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--web-out", default=None)
    ap.add_argument("--draft", action="store_true")
    ap.add_argument("--web-only", action="store_true")
    ap.add_argument("--wait", type=float, default=0.0, help="clips 模式等待镜头齐全的秒数")
    ap.add_argument("--allow-short", action="store_true", help="拼接时长明显短于时间轴时仍继续")
    ap.add_argument("--allow-audio-mismatch", action="store_true",
                    help="母带与时间轴差 >0.5s 时仍继续（默认中止）")
    ap.add_argument("--verify", action="store_true", help="收尾后跑 verify_ep08.py")
    args = ap.parse_args()

    t_all = time.time()
    os.makedirs(WORK, exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)
    wait_render_lock(float(os.environ.get("EP08_WAIT_RENDER_LOCK", "1800")))
    lock = require_lock()
    global THREADS
    try:
        lim = int(open("/sys/fs/cgroup/memory.max").read().strip()) / 1e9
        cur = int(open("/sys/fs/cgroup/memory.current").read().strip()) / 1e9
        anon = None
        try:
            for line in open("/sys/fs/cgroup/memory.stat"):
                if line.startswith("anon "):
                    anon = int(line.split()[1]) / 1e9
                    break
        except Exception:
            pass
        # 判据用 anon 真实占用（memory.current 含可回收 page cache，会误判紧张）
        use = anon if anon is not None else cur
        if use > lim * 0.72:
            THREADS = min(THREADS, 2)
            log("内存紧张（anon %.1fGB / %.1fGB >72%%）：x264 线程降到 %d"
                % (use, lim, THREADS))
        log("cgroup 内存：anon %.1fGB / current %.1fGB / max %.1fGB；x264 线程上限 %d"
            % (use, cur, lim, THREADS))
        if use > lim * 0.90:
            log("警告：anon 内存 >90%%，可能被 OOM；建议先让其他 agent 收尾")
    except Exception:
        pass
    log("=" * 78)
    log("finalize 开始：%s（pid=%d）" % (time.strftime("%Y-%m-%d %H:%M:%S"), os.getpid()))

    master = os.path.abspath(args.out) if args.out else MASTER
    web = os.path.abspath(args.web_out) if args.web_out else WEB
    srt = None if args.no_subs else resolve_srt(args.srt)
    audio = resolve_audio(args.audio)

    if args.web_only:
        if not os.path.isfile(master):
            raise SystemExit("web-only 模式找不到 master: %s" % master)
        winfo = encode_web(master, web, args.draft)
        res = {"mode": "web-only", "master": master, "web": web, "web_info": winfo,
               "elapsed_s": round(time.time() - t_all, 1)}
        json.dump(res, open(os.path.join(WORK, "finalize.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        log("web-only 完成")
        return 0

    res = {"started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "spec": SPEC}

    # ---------------- clips 模式 ----------------
    if not args.input:
        total, fps, shots, tl_src = load_timeline()
        if not shots:
            raise SystemExit("找不到时间轴：work/timeline.json / work/shots.json 均不可用（等 engine-dev）")
        res.update({"mode": "clips", "timeline": tl_src, "total": total, "fps": fps,
                    "shots": len(shots)})
        log("时间轴 %s：%d 镜 / %.3fs / %.1ffps" % (tl_src, len(shots), total, fps))
        # 等待镜头齐全
        if args.wait > 0:
            deadline = time.time() + args.wait
            while time.time() < deadline:
                miss = [s["id"] for s in shots
                        if not (os.path.isfile(os.path.join(CLIPS_DIR, s["id"] + ".mp4")))]
                if not miss:
                    break
                log("等待 %d 个镜头（余 %.0fs）：%s" % (len(miss), deadline - time.time(),
                                                      " ".join(miss[:8])))
                time.sleep(5)
        concat, concat_dur = concat_clips(shots, CLIPS_DIR)
        res["concat_duration"] = round(concat_dur, 3)
        if concat_dur < total - 1.0 and not args.allow_short:
            raise SystemExit("拼接时长 %.3fs 明显短于时间轴 %.3fs（差 %.2fs），"
                             "疑似缺帧；确认后可加 --allow-short" % (concat_dur, total, total - concat_dur))
        if not audio:
            raise SystemExit("缺少音频母带（audio/work/audio.m4a）。等 audio-engineer，"
                             "或用 --audio 指定")
        if not srt:
            log("警告：未找到 SRT，成片将无字幕（%s）" % SRT_CANDIDATES)
        adur = probe_duration(audio)
        res.update({"audio": audio, "srt": srt, "audio_duration": round(adur, 3)})
        log("母带：%s（%.3fs；时间轴 %.3fs，差 %+.3fs）"
            % (audio, adur, total, adur - total))
        # Lead 契约：母带总长与时间轴 total 一致（±0.1s）；>0.5s 视为未就绪直接中止
        adiff = adur - total
        if abs(adiff) > 0.5 and not args.allow_audio_mismatch:
            raise SystemExit("母带时长 %.3fs 与时间轴 %.3fs 差 %+.2fs（>0.5s），"
                             "疑似母带未按锁定稿重出；确认后可加 --allow-audio-mismatch"
                             % (adur, total, adiff))
        if abs(adiff) > 0.1:
            log("警告：母带与时间轴差 %+.3fs（应在 ±0.1s 内）；成片仍按时间轴 %.3fs 输出"
                % (adiff, total))
        # 成片时长以时间轴为准；拼接略短时用 tpad 克隆末帧补齐（差 <0.5s 级）
        target = total
        pad = max(0.0, total - concat_dur) if concat_dur else 0.0
        if pad > 0.5:
            log("警告：拼接比时间轴短 %.2fs，tpad 补齐；请核对是否缺帧" % pad)
        minfo = encode_master(concat, audio, srt, target, master, args.draft,
                              grade=not args.no_grade, bars=not args.no_bars,
                              fade=not args.no_fade, pad=pad)
        res["master_info"] = minfo
        res["master"] = master
        res["duration"] = probe_duration(master)
        res["size_mb"] = round(os.path.getsize(master) / 1e6, 2)
        res["sha256"] = sha256(master)
        winfo = encode_web(master, web, args.draft)
        res["web"] = web
        res["web_info"] = winfo
        res["web_sha256"] = sha256(web)
        res["web_duration"] = probe_duration(web)

    # ---------------- raw 模式 ----------------
    else:
        src = os.path.abspath(args.input)
        if not os.path.isfile(src):
            raise SystemExit("找不到 raw 全片: %s" % src)
        p = probe(src)
        v = next((s for s in p["streams"] if s.get("codec_type") == "video"), {})
        dur = float(p["format"]["duration"])
        total, fps, shots, tl_src = load_timeline()
        if total and abs(dur - total) > 1.0 and not args.allow_short:
            raise SystemExit("raw 时长 %.3fs 与时间轴 %.3fs 不一致（差 %.2fs）；"
                             "确认可加 --allow-short" % (dur, total, abs(dur - total)))
        target = total or dur
        baked_bars, bar_means = detect_letterbox(src, SPEC["bar"])
        if args.baked:
            log("raw/baked 模式：视频流 copy + 母带 remux（不再套滤镜链）")
            if not audio:
                raise SystemExit("baked 模式需要音频母带（audio/work/audio.m4a）")
            cmd = [FF, "-hide_banner", "-loglevel", "error", "-y", "-i", src, "-i", audio,
                   "-threads", "2", "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
                   "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                   "-t", "%.3f" % target, "-movflags", "+faststart", master]
            t0 = time.time()
            r = run(*cmd)
            if r.returncode != 0:
                raise SystemExit("remux 失败：\n" + (r.stderr or "")[-3000:])
            minfo = {"cmd": " ".join(cmd), "elapsed_s": round(time.time() - t0, 1),
                     "size_mb": round(os.path.getsize(master) / 1e6, 2)}
        else:
            if not audio:
                raise SystemExit("raw 模式需要音频母带（audio/work/audio.m4a）")
            if not srt:
                log("警告：未找到 SRT，成片将无字幕")
            minfo = encode_master(src, audio, srt, target, master, args.draft,
                                  grade=not args.no_grade,
                                  bars=(not args.no_bars) and not baked_bars,
                                  fade=not args.no_fade)
        res.update({"mode": "raw-baked" if args.baked else "raw",
                    "input": src, "input_duration": round(dur, 3),
                    "input_resolution": [v.get("width"), v.get("height")],
                    "bars_detected": baked_bars, "bar_means": bar_means,
                    "timeline": tl_src, "total": total, "audio": audio, "srt": srt,
                    "master": master, "master_info": minfo,
                    "duration": probe_duration(master),
                    "size_mb": round(os.path.getsize(master) / 1e6, 2),
                    "sha256": sha256(master)})
        winfo = encode_web(master, web, args.draft)
        res.update({"web": web, "web_info": winfo, "web_sha256": sha256(web),
                    "web_duration": probe_duration(web)})

    res["elapsed_s"] = round(time.time() - t_all, 1)
    res["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    res["draft"] = bool(args.draft) or master != MASTER
    meta_name = "finalize-draft.json" if res["draft"] else "finalize.json"
    json.dump(res, open(os.path.join(WORK, meta_name), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    res["meta"] = os.path.join(WORK, meta_name)
    log("finalize 完成：master=%s（%.2fs / %.1fMB）web=%.1fMB 总耗时 %.1fs"
        % (master, res.get("duration") or 0, res.get("size_mb") or 0,
           (res.get("web_info") or {}).get("size_mb") or 0, res["elapsed_s"]))
    log("清单 → %s" % res.get("meta", os.path.join(WORK, "finalize.json")))
    lock.close()

    if args.verify:
        log("调用 verify_ep08.py ……")
        rc = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "verify_ep08.py")],
                            cwd=ROOT).returncode
        return rc
    return 0


if __name__ == "__main__":
    sys.exit(main())
