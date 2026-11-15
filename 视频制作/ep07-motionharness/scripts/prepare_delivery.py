#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 07 期交付物生成：10 张静帧 + 联系表 + 16:9/1:1/3:4 三版封面。

用法：
  python3 scripts/prepare_delivery.py                        # out/ep07-mh.mp4 -> delivery/
  python3 scripts/prepare_delivery.py --film /tmp/x.mp4 --out /tmp/delivery
  python3 scripts/prepare_delivery.py --beats work/qa/beats.json   # 自定义静帧时间点

默认静帧按「场景设计表」的关键落点取：冷却开场评估单→盖章→数据墙→计算器→三本账→
价签森林→电池→榜单→车场黄昏→片尾双声明卡；若成片时长与设计不同，用 fraction 自适应。
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FF = os.environ.get("FFMPEG", "/home/admin/.local/bin/ffmpeg")
OUT = os.path.join(ROOT, "out", "ep07-mh.mp4")
DELIVERY = os.path.join(ROOT, "delivery")
STILLS = os.path.join(DELIVERY, "stills")

# (fraction_of_duration, name)；fraction 允许以 int/float 表示，按成片实测时长换算
DEFAULT_BEATS = [
    (0.020, "still-01-cover"),
    (0.055, "still-02-appraisal-sheet"),
    (0.078, "still-03-stamp"),
    (0.140, "still-04-data-wall"),
    (0.240, "still-05-calculator"),
    (0.330, "still-06-three-ledgers"),
    (0.460, "still-07-battery-check"),
    (0.630, "still-08-price-tag-forest"),
    (0.750, "still-09-lists"),
    (0.985, "still-10-end-card"),
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


def sha256(path, n=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(n), b""):
            h.update(chunk)
    return h.hexdigest()


def grab(film, t, path):
    r = run(FF, "-v", "error", "-y", "-an", "-ss", "%.3f" % t, "-i", film,
            "-frames:v", "1", "-q:v", "2", path)
    if r.returncode != 0 or not os.path.isfile(path):
        raise SystemExit("抽帧失败 t=%.3f: %s" % (t, (r.stderr or "")[-400:]))
    return path


def beats_from_shots(path):
    """按分镜数据（shots.json）挑选 10 个关键落点，返回 [(abs, name)]。"""
    if not os.path.isfile(path):
        return None
    try:
        sh = json.load(open(path, encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(sh, list) or not sh:
        return None

    def mid(s):
        return float(s.get("start", 0)) + float(s.get("dur", 0)) / 2.0

    def pick(pred, fallback_frac=None):
        for s in sh:
            if pred(s):
                return mid(s)
        return None

    picks = []
    used = set()

    def add(name, t, frac=None):
        if t is None:
            return
        key = round(t, 2)
        if key in used:
            t = t + 0.6
            key = round(t, 2)
        used.add(key)
        picks.append(("abs", t, name))

    first = sh[0]
    add("still-01-cover", mid(first))
    add("still-02-appraisal-sheet", pick(lambda s: s.get("h3") == "H01" and s is not first) or
        float(sh[1].get("start", 0)) + float(sh[1].get("dur", 0)) / 2)
    add("still-03-stamp", pick(lambda s: s.get("h3") == "H02"))
    add("still-04-data-wall", pick(lambda s: s.get("space") == "B"))
    add("still-05-calculator", pick(lambda s: s.get("h3") == "H12"))
    add("still-06-three-ledgers", next((mid(s) for s in sh if s.get("seg") == "ACT2"), None))
    add("still-07-battery-check", pick(lambda s: s.get("h3") in ("H03", "H04", "H05")))
    add("still-08-price-tag-forest",
        next((mid(s) for s in sh if s.get("seg") == "ACT3" and s.get("space") == "C"), None))
    act3 = [s for s in sh if s.get("seg") == "ACT3"]
    add("still-09-lists", mid(act3[int(len(act3) * 0.65)]) if act3 else None)
    last = sh[-1]
    add("still-10-end-card", float(last.get("end", last.get("start", 0) + 4)) - 2.0)
    return picks


def load_beats(path):
    if not path:
        return DEFAULT_BEATS
    data = json.load(open(path, encoding="utf-8"))
    out = []
    for item in data if isinstance(data, list) else data.get("beats", []):
        if "t" in item:
            out.append(("abs", float(item["t"]), item.get("name", "still")))
        else:
            out.append(("frac", float(item.get("fraction", item.get("f", 0))),
                        item.get("name", "still")))
    return out


def crop_center(im, tw, th):
    w, h = im.size
    target = tw / th
    if w / h > target:
        nw = int(h * target)
        box = ((w - nw) // 2, 0, (w + nw) // 2, h)
    else:
        nh = int(w / target)
        box = (0, (h - nh) // 2, w, (h + nh) // 2)
    return im.crop(box).resize((tw, th), Image.LANCZOS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--film", default=OUT)
    ap.add_argument("--out", default=DELIVERY)
    ap.add_argument("--beats", default=None, help="JSON 覆盖静帧时间点")
    ap.add_argument("--cover-source", default=None,
                    help="可选：用作封面的图（默认 still-01）；MH 的 Poster 帧可先 preview 导出")
    ap.add_argument("--from-shots", action="store_true",
                    help="从 src/data/shots.json 自动挑 10 个关键落点（优先于默认 fraction）")
    args = ap.parse_args()
    film = os.path.abspath(args.film)
    dst = os.path.abspath(args.out)
    stills_dir = os.path.join(dst, "stills")
    os.makedirs(stills_dir, exist_ok=True)
    if not os.path.isfile(film):
        raise SystemExit("找不到成片: %s" % film)
    dur = duration(film)
    beats = load_beats(args.beats)
    beats = [("frac", b[0], b[1]) if len(b) == 2 else b for b in beats]
    if args.from_shots and not args.beats:
        auto = beats_from_shots(os.path.join(ROOT, "src", "data", "shots.json"))
        if auto:
            beats = auto
            print("beats: 由 src/data/shots.json 自动生成 %d 个落点" % len(auto))
    made, manifest = [], []
    for kind, v, name in beats:
        t = v if kind == "abs" else max(0.2, min(dur - 0.2, v * dur))
        p = os.path.join(stills_dir, name + ".jpg")
        grab(film, t, p)
        made.append((t, p))
        manifest.append({"name": name, "time": round(t, 3), "file": os.path.relpath(p, dst)})
        print("still %-24s t=%7.3fs" % (name, t))

    # 联系表（5 列 × 2 行）
    TW, TH, COLS = 480, 270, 5
    rows = (len(made) + COLS - 1) // COLS
    sheet = Image.new("RGB", (COLS * TW, rows * (TH + 26)), (8, 9, 12))
    d = ImageDraw.Draw(sheet)
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
    for i, (t, p) in enumerate(made):
        im = Image.open(p).convert("RGB").resize((TW, TH))
        x, y = (i % COLS) * TW, (i // COLS) * (TH + 26)
        sheet.paste(im, (x, y))
        d.text((x + 6, y + TH + 5), "%s  %.1fs" % (os.path.basename(p)[:-4], t),
               font=font, fill=(190, 196, 204))
    cs = os.path.join(dst, "contact-sheet.jpg")
    sheet.save(cs, quality=90)
    print("contact sheet -> %s (%dx%d)" % (cs, *sheet.size))

    # 封面：16:9 取封面帧；1:1 / 3:4 居中安全裁切
    src = args.cover_source or made[0][1]
    cover = Image.open(src).convert("RGB")
    cover.save(os.path.join(dst, "cover-16x9.jpg"), quality=92)
    for name, (cw, ch) in {"cover-1x1.jpg": (1080, 1080),
                           "cover-3x4.jpg": (1080, 1440)}.items():
        crop_center(cover, cw, ch).save(os.path.join(dst, name), quality=92)
    print("covers -> cover-16x9 / cover-1x1 / cover-3x4 (cover-src=%s)" % os.path.basename(src))

    meta = {"film": os.path.relpath(film, ROOT), "film_duration": round(dur, 3),
            "film_size_mb": round(os.path.getsize(film) / 1e6, 2),
            "film_sha256": sha256(film), "beats": manifest,
            "contact_sheet": "contact-sheet.jpg",
            "covers": ["cover-16x9.jpg", "cover-1x1.jpg", "cover-3x4.jpg"]}
    json.dump(meta, open(os.path.join(dst, "delivery-manifest.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("delivery manifest -> %s" % os.path.join(dst, "delivery-manifest.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
