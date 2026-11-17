#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 08 期交付物生成：10 张静帧 + 联系表 + 16:9/1:1/3:4 三版封面 + delivery-manifest.json。

静帧落点优先按「场景设计表」的语义从 work/shots.json 自动挑（钩子 / 能量流 / 电机剖面 /
逆变器电池 / 能量账 / 四限制 / 单踏板 / 续航 / 数据 / 片尾声明卡），无分镜数据时按
fraction 自适应；抽到黑帧会自动后移重试，保证交付静帧不是黑场。

manifest 记录素材来源与授权（Pexels License / AI 生成 / 程序化 / 原创合成），供 Release 核对。

用法：
  python3 scripts/prepare_delivery.py                     # out/ep08-regen.mp4 -> delivery/
  python3 scripts/prepare_delivery.py --film /tmp/x.mp4 --out /tmp/delivery
  python3 scripts/prepare_delivery.py --beats work/qa/beats.json
  python3 scripts/prepare_delivery.py --cover-source delivery/stills/still-03-motor.png
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FF = os.environ.get("FFMPEG", "/home/admin/.local/bin/ffmpeg")
OUT = os.path.join(ROOT, "out", "ep08-regen.mp4")
WEB = os.path.join(ROOT, "out", "ep08-regen-web.mp4")
DELIVERY = os.path.join(ROOT, "delivery")
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# (name, 关键词, 目标 fraction)；fraction 与锁定稿分镜对齐（S01/S24/S15/S20/S36/S42/S53/S56/S61/S67）
BEAT_PLAN = [
    ("still-01-cover", ["hook", "钩子", "松油门", "车在充电", "cover"], 0.012),
    ("still-02-energy-flow", ["反向", "四站", "能量流", "通道", "可逆", "regen", "flow"], 0.320),
    ("still-03-motor-cutaway", ["电机", "转动", "三件套", "剖面", "motor", "cutaway"], 0.203),
    ("still-04-inverter-battery", ["电池", "逆变器", "bms", "电芯", "battery", "inverter"], 0.267),
    ("still-05-energy-account", ["sankey", "能量损失", "损耗", "效率", "能量账"], 0.508),
    ("still-06-limits", ["限制", "满电", "低温", "高速", "抓地", "abs"], 0.615),
    ("still-07-one-pedal", ["单踏板", "踏板", "pedal", "逻辑"], 0.785),
    ("still-08-range", ["续航", "城市", "range", "里程"], 0.825),
    ("still-09-data", ["曲线", "数据", "提前松", "重刹", "data", "chart"], 0.885),
    ("still-10-end-card", ["end", "片尾", "声明", "outro", "declaration"], 0.985),
]


def run(*a):
    return subprocess.run(a, capture_output=True, text=True, errors="replace")


def duration(film):
    r = run(FF, "-hide_banner", "-i", film)
    import re
    m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", r.stderr or "")
    if not m:
        raise SystemExit("无法读取时长: %s" % film)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def grab_clip_frame(t, path):
    """按成片绝对时间 t 找到对应镜头，从 work/clips/<shot>.mp4 抽全画幅帧作封面底图。
    返回 (ok, local_t, shot_id)。逐镜 clip 无遮幅，16:9 构图不会被裁两侧。"""
    tl_path = os.path.join(ROOT, "work", "timeline.json")
    clips = os.path.join(ROOT, "work", "clips")
    if not os.path.isfile(tl_path):
        return False, None, None
    try:
        tl = json.load(open(tl_path, encoding="utf-8"))
        shots = tl.get("shots") or []
    except Exception:
        return False, None, None
    for sh in shots:
        st, du = float(sh.get("start", 0)), float(sh.get("dur", 0))
        if st <= t < st + du:
            sid = str(sh.get("id") or sh.get("shot"))
            clip = os.path.join(clips, sid + ".mp4")
            if not os.path.isfile(clip):
                return False, None, sid
            local = max(0.05, min(du - 0.05, t - st))
            r = run(FF, "-v", "error", "-y", "-an", "-threads", "1", "-ss", "%.3f" % local,
                    "-i", clip, "-frames:v", "1", path)
            return (r.returncode == 0 and os.path.isfile(path)), round(local, 3), sid
    return False, None, None


def sha256(path, n=1 << 20):
    if not os.path.isfile(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(n), b""):
            h.update(chunk)
    return h.hexdigest()


def grab(film, t, path, min_mean=3.0):
    """抽帧；若抽到近黑帧，向后找一帧亮的（避免交付静帧是黑场）。"""
    for attempt in range(4):
        tt = t + attempt * 1.5
        r = run(FF, "-v", "error", "-y", "-an", "-threads", "1", "-ss", "%.3f" % tt,
                "-i", film, "-frames:v", "1", "-q:v", "2", path)
        if r.returncode != 0 or not os.path.isfile(path):
            continue
        try:
            mean = float(np.asarray(Image.open(path).convert("L"), np.float32).mean())
        except Exception:
            mean = 0.0
        if mean >= min_mean:
            return path, tt
    return path, t


def load_shots():
    for cand in (os.path.join(ROOT, "work", "shots.json"),
                 os.path.join(ROOT, "work", "timeline.json"),
                 os.path.join(ROOT, "shots.json")):
        if not os.path.isfile(cand):
            continue
        try:
            d = json.load(open(cand, encoding="utf-8"))
        except Exception:
            continue
        shots = None
        if isinstance(d, dict):
            for k in ("shots", "beats", "scenes", "clips"):
                if isinstance(d.get(k), list) and d[k]:
                    shots = d[k]
                    break
        elif isinstance(d, list):
            shots = d
        if not shots:
            continue
        out = []
        for s in shots:
            if not isinstance(s, dict) or not (s.get("id") or s.get("shot")):
                continue
            out.append({
                "id": str(s.get("id") or s.get("shot")),
                "start": float(s.get("start", 0) or 0),
                "dur": float(s.get("dur", s.get("duration", 3.0)) or 3.0),
                "tag": " ".join(str(s.get(k, "")) for k in
                                ("id", "scene", "title", "tag", "tags", "note",
                                 "headline", "key", "seg", "section")).lower(),
            })
        out.sort(key=lambda x: x["start"])
        return out, cand
    return [], None


def beats_from_shots(shots, film_dur):
    """每个落点在目标 fraction ±12% 时间窗内按关键词挑镜；窗内无匹配则取最接近目标时间的镜。
    保证 10 张静帧铺满全片，而不是各 beat 各挑各的（曾出现 still-09 跑到 6.1s）。"""
    picks = []
    used = []
    for name, keys, frac in BEAT_PLAN:
        target = frac * film_dur
        if name.startswith("still-10"):            # 片尾卡固定最后 12s
            cands = [s for s in shots if s["start"] >= film_dur - 12]
            best = max(cands, key=lambda s: s["start"]) if cands else None
            if best:
                picks.append((name, float(best["start"] + best["dur"] * 0.55)))
            else:
                picks.append((name, max(0.3, film_dur - 2.0)))
            continue
        lo, hi = target - 0.12 * film_dur, target + 0.12 * film_dur
        window = [s for s in shots if lo <= s["start"] <= hi]
        pool = window or shots
        best = None
        for s in pool:
            score = sum(1 for k in keys if k.lower() in s["tag"])
            dist = abs(s["start"] + s["dur"] / 2 - target) / max(1.0, 0.12 * film_dur)
            if any(abs(s["start"] - u) < 2.5 for u in used):
                continue
            cand = (score - 0.35 * dist, s)
            if best is None or cand[0] > best[0]:
                best = cand
        if best is None:
            cands = sorted(shots, key=lambda s: abs(s["start"] + s["dur"] / 2 - target))
            best = (0, cands[0]) if cands else None
        if best:
            s = best[1]
            picks.append((name, float(s["start"] + s["dur"] * 0.5)))
            used.append(s["start"])
        else:
            picks.append((name, float(target)))
    return picks


def resolve_beats(film_dur, shots, beats_file=None):
    if beats_file and os.path.isfile(beats_file):
        data = json.load(open(beats_file, encoding="utf-8"))
        out = []
        for item in data if isinstance(data, list) else data.get("beats", []):
            if "t" in item:
                out.append((str(item.get("name", "still")), float(item["t"])))
            else:
                out.append((str(item.get("name", "still")),
                            float(item.get("fraction", 0)) * film_dur))
        if out:
            return out, "beats-file"
    if shots:
        picks = beats_from_shots(shots, film_dur)
        # 换算到成片时长（分镜时间轴与成片一致；成片若更短则裁到片内）
        out = []
        for name, t in picks:
            out.append((name, max(0.3, min(film_dur - 0.3, t))))
        return out, "shots"
    # 纯 fraction 兜底
    return [(name, max(0.3, min(film_dur - 0.3, frac * film_dur)))
            for name, _keys, frac in BEAT_PLAN], "fractions"


def cover_source(stills_made, explicit=None, film=None, cfg=None, work_dir=None):
    if explicit and os.path.isfile(explicit):
        return explicit
    # work/cover-config.json：cover_time（成片绝对秒，优先）或 cover_still（静帧名）
    cfg = cfg or {}
    cover_time = cfg.get("cover_time")
    if cover_time is not None:
        qa_dir = os.path.join(work_dir or os.path.join(ROOT, "work"), "qa")
        os.makedirs(qa_dir, exist_ok=True)
        p = os.path.join(qa_dir, "cover-base.jpg")
        try:
            ok, local_t, sid = grab_clip_frame(float(cover_time), p)
            if ok:
                print("封面底图：成片 %.2fs = %s 镜内 %.2fs（全画幅 clip，无遮幅）-> %s"
                      % (float(cover_time), sid, local_t, os.path.basename(p)))
                return p
        except Exception:
            pass
        if film and os.path.isfile(film):
            try:
                _, real_t = grab(film, float(cover_time), p)
                print("封面底图：成片 %.2fs（master，含遮幅，会裁两侧）-> %s"
                      % (real_t, os.path.basename(p)))
                return p
            except Exception:
                pass
    wanted = cfg.get("cover_still")
    if wanted:
        for name, t, p in stills_made:
            if name == wanted and os.path.isfile(p):
                return p
    for name, t, p in stills_made:
        if name.startswith("still-01") or name.startswith("still-02"):
            try:
                if float(np.asarray(Image.open(p).convert("L"), np.float32).mean()) >= 6:
                    return p
            except Exception:
                pass
    for name, t, p in stills_made:
        if os.path.isfile(p):
            return p
    return None


def asset_provenance():
    """素材来源/授权清单：H3 / Pexels / 程序化 / 原创合成 / 字体。"""
    prov = {
        "procedural": {
            "desc": "原理图/能量流/剖面/数据曲线/字幕/片头片尾卡/最终合成：自研 Python(PIL/numpy) 程序化渲染",
            "license": "本仓库原创（随项目许可）",
        },
        "audio": {
            "desc": "旁白 zh-CN-YunjianNeural（edge-tts 逐句合成）；BGM/音效 numpy 原创合成（无外部曲库）",
            "license": "原创合成 / edge-tts 生成；不涉及第三方曲库",
        },
        "fonts": {
            "desc": "Noto Serif/Sans CJK（标题/字幕/数据数字）",
            "license": "OFL 1.1",
        },
    }
    h3_manifest = None
    for cand in (os.path.join(ROOT, "assets", "h3", "manifest.json"),
                 os.path.join(ROOT, "assets", "h3", "h3-manifest.json"),
                 os.path.join(ROOT, "assets", "manifest.json")):
        if os.path.isfile(cand):
            h3_manifest = cand
            break
    h3_dir = os.path.join(ROOT, "assets", "h3")
    h3_clips = sorted(os.path.splitext(f)[0] for f in os.listdir(h3_dir)
                      if f.lower().endswith(".mp4")) if os.path.isdir(h3_dir) else []
    prov["h3"] = {
        "desc": "实拍质感镜头由 ComfyUI + MiniMax H3 生成（云端 RTX 5090），本机 lanczos 1080p；"
                "H3 不承载文字/数据/原理/字幕/配音/拼接",
        "license": "MiniMax H3 生成内容；商用发布前按平台许可确认（见已知限制）",
        "clips": h3_clips,
        "manifest": os.path.relpath(h3_manifest, ROOT) if h3_manifest else None,
    }
    # Pexels / 本地 B-roll
    stock_manifest = None
    stock_dir = os.path.join(ROOT, "assets", "stock")
    for cand in (os.path.join(ROOT, "assets", "manifest.json"),
                 os.path.join(ROOT, "assets", "stock", "manifest.json"),
                 os.path.join(ROOT, "assets-manifest.json")):
        if os.path.isfile(cand):
            stock_manifest = cand
            break
    stock_files = []
    if os.path.isdir(stock_dir):
        stock_files = sorted(f for f in os.listdir(stock_dir)
                             if f.lower().endswith((".mp4", ".mov", ".jpg", ".png")))
    prov["stock"] = {
        "desc": "Pexels 实拍 B-roll（如使用）",
        "license": "Pexels License（免费商用，无需署名；不得转售原素材）",
        "count": len(stock_files),
        "manifest": os.path.relpath(stock_manifest, ROOT) if stock_manifest else None,
    }
    return prov


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--film", default=OUT)
    ap.add_argument("--web", default=WEB)
    ap.add_argument("--out", default=DELIVERY)
    ap.add_argument("--beats", default=None, help="JSON 覆盖静帧时间点")
    ap.add_argument("--cover-source", default=None)
    ap.add_argument("--no-covers", action="store_true")
    args = ap.parse_args()

    film = os.path.abspath(args.film)
    dst = os.path.abspath(args.out)
    stills_dir = os.path.join(dst, "stills")
    os.makedirs(stills_dir, exist_ok=True)
    if not os.path.isfile(film):
        raise SystemExit("找不到成片: %s" % film)
    dur = duration(film)
    shots, shots_src = load_shots()
    beats, beats_src = resolve_beats(dur, shots, args.beats)
    if args.beats is None:
        print("静帧落点来源：%s（%d 张）" % (beats_src, len(beats)))

    made, manifest = [], []
    used_times = []
    for name, t in beats:
        # 同名/近点去重（同名替换，时间点至少间隔 1.0s）
        t = max(0.3, min(dur - 0.3, float(t)))
        if any(abs(t - u) < 1.0 for u in used_times):
            t = min(dur - 0.3, t + 1.2)
        used_times.append(t)
        p = os.path.join(stills_dir, name + ".jpg")
        _, real_t = grab(film, t, p)
        made.append((name, real_t, p))
        manifest.append({"name": name, "time": round(real_t, 3),
                         "file": os.path.relpath(p, dst)})
        print("still %-26s t=%7.3fs  %s" % (name, real_t, os.path.basename(p)))

    # 联系表（5 列 × 2 行，带名称与时间码）
    TW, TH, COLS = 480, 270, 5
    rows = (len(made) + COLS - 1) // COLS
    sheet = Image.new("RGB", (COLS * TW, rows * (TH + 26)), (8, 9, 12))
    d = ImageDraw.Draw(sheet)
    fnt = ImageFont.truetype(FONT_BOLD, 14)
    for i, (name, t, p) in enumerate(made):
        im = Image.open(p).convert("RGB").resize((TW, TH), Image.LANCZOS)
        x, y = (i % COLS) * TW, (i // COLS) * (TH + 26)
        sheet.paste(im, (x, y))
        d.text((x + 6, y + TH + 5), "%s  %.1fs" % (name, t),
               font=fnt, fill=(190, 196, 204))
    cs = os.path.join(dst, "contact-sheet.jpg")
    sheet.save(cs, quality=90)
    print("contact sheet -> %s (%dx%d)" % (cs, *sheet.size))

    # 封面（16:9 / 1:1 / 3:4）
    covers = []
    if not args.no_covers:
        cfg = {}
        cfg_path = os.path.join(ROOT, "work", "cover-config.json")
        if os.path.isfile(cfg_path):
            try:
                cfg = json.load(open(cfg_path, encoding="utf-8")) or {}
            except Exception:
                cfg = {}
        src = cover_source(made, args.cover_source, film=film, cfg=cfg,
                           work_dir=os.path.join(ROOT, "work"))
        cmd = [sys.executable, os.path.join(ROOT, "scripts", "gen_cover.py"),
               "--out", dst]
        if src:
            cmd += ["--source", src]
        r = run(*cmd)
        print((r.stdout or "").strip())
        if r.returncode != 0:
            print("封面生成失败：%s" % (r.stderr or "")[-500:], file=sys.stderr)
        covers = [f for f in ("cover-16x9.jpg", "cover-1x1.jpg", "cover-3x4.jpg")
                  if os.path.isfile(os.path.join(dst, f))]

    web = os.path.abspath(args.web) if args.web else None
    meta = {
        "episode": "第08期《电动车松开油门为什么能充电》",
        "film": os.path.relpath(film, ROOT),
        "film_duration": round(dur, 3),
        "film_duration_hms": "%d:%05.2f" % (int(dur // 60), dur % 60),
        "film_size_mb": round(os.path.getsize(film) / 1e6, 2),
        "film_sha256": sha256(film),
        "web": ({"path": os.path.relpath(web, ROOT),
                 "size_mb": round(os.path.getsize(web) / 1e6, 2),
                 "sha256": sha256(web)} if web and os.path.isfile(web) else None),
        "stills_source": beats_src,
        "shots_source": os.path.relpath(shots_src, ROOT) if shots_src else None,
        "beats": manifest,
        "contact_sheet": os.path.relpath(cs, dst),
        "covers": covers,
        "assets_provenance": asset_provenance(),
        "generated_by": "scripts/prepare_delivery.py",
    }
    json.dump(meta, open(os.path.join(dst, "delivery-manifest.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("delivery manifest -> %s" % os.path.join(dst, "delivery-manifest.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
