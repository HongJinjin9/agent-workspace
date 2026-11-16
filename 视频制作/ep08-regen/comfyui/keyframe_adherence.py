#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EP08 keyframe adherence check: did FL2VA actually start from the code keyframe?

For every shot with a keyframe (assets/h3/keyframes-upload/<ID>_first.png preferred, else the
path recorded in shots-ep08-run.json), compare the first decoded frame of the generated raw
clip against that keyframe:

  - grey 96x54 Pearson correlation (structure/composition)
  - mean absolute colour difference (tone)
  - hue/colour histogram correlation (palette)

i2v/FL2VA working => first frame close to the keyframe (corr usually >0.7).
T2V fallback => composition is model-invented, corr lower; that is expected and only
recorded (not a hard failure) unless --strict.

  python3 keyframe_adherence.py                 # writes assets/h3/keyframe-adherence.json
  python3 keyframe_adherence.py --strict        # exit 1 if a fl2va shot drifts below min-corr
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
A = ROOT / "assets" / "h3"
RUN = HERE / "shots-ep08-run.json"
UPLOAD_DIR = A / "keyframes-upload"


def load_json(p, default=None):
    p = Path(p)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def save_json(p, obj):
    p = Path(p)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(p)


def first_frame_png(clip: Path, out: Path):
    out.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-threads", "2", "-ss", "0.05", "-i", str(clip),
         "-frames:v", "1", "-q:v", "2", str(out)],
        capture_output=True, text=True)
    return r.returncode == 0 and out.exists()


def compare(key_png: Path, frame_png: Path):
    """Return correlation metrics between keyframe and generated first frame."""
    import cv2
    import numpy as np
    try:
        cv2.setNumThreads(2)
    except Exception:  # noqa: BLE001
        pass
    a = cv2.imread(str(key_png))
    b = cv2.imread(str(frame_png))
    if a is None or b is None:
        return {"ok": False, "error": "unreadable image"}
    a = cv2.resize(a, (96, 54), interpolation=cv2.INTER_AREA)
    b = cv2.resize(b, (96, 54), interpolation=cv2.INTER_AREA)
    ga = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY).astype(np.float32).ravel()
    gb = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY).astype(np.float32).ravel()
    if ga.std() < 1e-3 or gb.std() < 1e-3:
        return {"ok": False, "error": "flat image (no structure)"}
    corr = float(np.corrcoef(ga, gb)[0, 1])
    mad = float(np.abs(ga - gb).mean())
    ha = cv2.calcHist([a], [0, 1], None, [16, 16], [0, 256, 0, 256])
    hb = cv2.calcHist([b], [0, 1], None, [16, 16], [0, 256, 0, 256])
    cv2.normalize(ha, ha)
    cv2.normalize(hb, hb)
    hist_corr = float(cv2.compareHist(ha, hb, cv2.HISTCMP_CORREL))
    return {"ok": True, "gray_corr": round(corr, 3), "gray_mad": round(mad, 2),
            "hist_corr": round(hist_corr, 3)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", default=str(RUN))
    ap.add_argument("--min-corr", type=float, default=0.45)
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    doc = load_json(args.shots, default=None)
    if doc is None:
        raise SystemExit(f"missing {args.shots}")
    frames_dir = A / "frames" / "keyframe-first"
    rows, flagged = [], []
    for s in doc["shots"]:
        sid = s["id"]
        raw = sorted((A / "raw").glob(f"{sid}_raw.*"))
        if not raw:
            rows.append({"id": sid, "status": "no_raw"})
            continue
        if not (s.get("first_frame") or s.get("last_frame")):
            rows.append({"id": sid, "status": "t2v"})
            continue
        # preferred: the exact image uploaded for generation
        which = "first" if s.get("first_frame") else "last"
        up = None
        if UPLOAD_DIR.exists():
            for cand in sorted(UPLOAD_DIR.glob(f"{sid}_{which}.*")):
                up = cand
                break
        key = up
        if key is None:
            rel = s.get("first_frame") or s.get("last_frame")
            for base in (HERE, ROOT):
                cand = base / rel
                if cand.exists():
                    key = cand
                    break
        if key is None:
            rows.append({"id": sid, "status": "keyframe_missing"})
            continue
        fp = frames_dir / f"{sid}_firstframe.png"
        if not first_frame_png(raw[0], fp):
            rows.append({"id": sid, "status": "decode_failed"})
            continue
        m = compare(key, fp)
        m.update({"id": sid, "raw": str(raw[0]), "keyframe": str(key),
                  "mode": "fl2va" if s.get("first_frame") else "fl2va-last-only",
                  "adherent": bool(m.get("ok") and m.get("gray_corr", -1) >= args.min_corr)})
        if m.get("ok") and not m["adherent"]:
            flagged.append(sid)
        rows.append(m)

    fl = [r for r in rows if r.get("mode")]
    adh = [r for r in fl if r.get("adherent")]
    out = {"checked_utc": __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc).isoformat(timespec="seconds"),
        "min_corr": args.min_corr, "fl2va_shots": len(fl), "adherent": len(adh),
        "flagged": flagged, "shots": rows}
    A.mkdir(parents=True, exist_ok=True)
    save_json(A / "keyframe-adherence.json", out)
    print(json.dumps({"fl2va_shots": len(fl), "adherent": len(adh),
                      "flagged": flagged}, ensure_ascii=False))
    for r in rows:
        if r.get("mode"):
            print(f"{r['id']}: corr={r.get('gray_corr')} hist={r.get('hist_corr')} "
                  f"adherent={r.get('adherent')}")
    print(f"RESULT: KEYFRAME_ADHERENCE {'OK' if not flagged else 'FLAGGED'}")
    if args.strict and flagged:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
