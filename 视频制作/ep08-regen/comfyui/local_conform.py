#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os as _os
# 4-core / 6GB cgroup: keep BLAS/torch/ffmpeg thread counts low (Lead resource rule)
for _k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    _os.environ.setdefault(_k, "2")
"""EP08 local 1080p conform: 864x480 / 1280x736 H3 raw -> 1920x1080 (ffmpeg lanczos).

No GPU work: the rented instance is only used for generation. This is the PLAN §4
"本地 lanczos 1080p" step, run right after each raw lands (conform_watch_ep08.py) and
again as a fill-missing pass before verification.

  python3 local_conform.py --dry
  python3 local_conform.py --only H01,H02
  python3 local_conform.py --fill-missing

Writes atomically (<name>.tmp.mp4 -> rename) so the compositor never sees a partial file
and updates assets/h3/manifest.json after each clip.
"""
import argparse
import datetime as _dt
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from probe_util import probe_video  # noqa: E402

DEFAULT_SHOTS = HERE / "shots-ep08-run.json"
DEFAULT_RAW = HERE.parent / "assets" / "h3" / "raw"
DEFAULT_FINAL = HERE.parent / "assets" / "h3"
DEFAULT_MANIFEST = HERE.parent / "assets" / "h3" / "manifest.json"


def now():
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(p, default=None):
    p = Path(p)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def save_json(p, obj):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(p)


def local_conform(raw, fin, w=1920, h=1080, keep_audio=True):
    """Fast no-GPU 1080p conform (lanczos + light unsharp), keeps H3 ambient audio."""
    fin = Path(fin)
    raw = Path(raw)
    fin.parent.mkdir(parents=True, exist_ok=True)
    tmp = fin.parent / (fin.stem + ".tmp.mp4")
    # cover-scale then centre-crop: H3 native 864x480 is 9:5 (1.8) and 1280x736 is 1.739,
    # neither is exactly 16:9 — cropping <=2.3% of the frame avoids stretching the picture.
    cmd = ["ffmpeg", "-v", "error", "-y", "-filter_threads", "2", "-i", str(raw), "-vf",
           f"scale={w}:{h}:flags=lanczos+accurate_rnd+full_chroma_int:"
           f"force_original_aspect_ratio=increase,"
           f"crop={w}:{h},"
           f"unsharp=5:5:0.45:5:5:0.0",
           "-c:v", "libx264", "-preset", "fast", "-crf", "17", "-pix_fmt", "yuv420p",
           "-r", "24", "-threads", "2", "-filter_threads", "2"]
    if keep_audio:
        cmd += ["-c:a", "aac", "-b:a", "192k"]
    else:
        cmd += ["-an"]
    cmd += [str(tmp)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode == 0 and tmp.exists():
        tmp.replace(fin)
        return True, f"local-ffmpeg-lanczos {w}x{h}"
    if tmp.exists():
        tmp.unlink()
    return False, (r.stderr or "ffmpeg failed")[:300]


def update_manifest(manifest_path, sid, fields):
    m = load_json(manifest_path, default=None) or {"series": "ep08-regen", "shots": {}}
    m.setdefault("shots", {}).setdefault(sid, {}).update(fields)
    m["updated_utc"] = now()
    save_json(manifest_path, m)


def final_path(final_dir, sid):
    return Path(final_dir) / f"{sid}.mp4"


def _shot_map(shots_path):
    """id -> engine 'shot' (Sxx/SPARE) map from the run orders, for the dual naming."""
    doc = load_json(shots_path, default=None) or {}
    m = {}
    for sh in doc.get("shots", []):
        if sh.get("shot"):
            m[sh["id"]] = sh["shot"]
    return m


def ensure_shot_alias(final_dir, sid, shot):
    """Hardlink Hxx.mp4 -> Sxx.mp4 so both PLAN §3 and engine's shot naming resolve."""
    if not shot or shot == sid or str(shot).upper() in ("SPARE", "H24"):
        return None  # spare keeps the PLAN-contract H24.mp4 name only
    src = final_path(final_dir, sid)
    alias = Path(final_dir) / f"{shot}.mp4"
    if not src.exists():
        return None
    try:
        if alias.exists() or alias.is_symlink():
            alias.unlink()
        alias.hardlink_to(src)
        return alias
    except OSError:
        # cross-device or fs without hardlinks: fall back to a copy
        try:
            import shutil
            shutil.copyfile(src, alias)
            return alias
        except OSError:
            return None


def conform_one(sid, raw_dir, final_dir, manifest_path, w=1920, h=1080, shot=None):
    raw = Path(raw_dir) / f"{sid}_raw.mp4"
    fin = final_path(final_dir, sid)
    existing = sorted(Path(raw_dir).glob(f"{sid}_raw.*"))
    if not existing:
        return {"id": sid, "status": "no_raw"}
    raw = existing[0]
    ok, method = local_conform(raw, fin, w, h)
    pr = probe_video(fin) if ok else {}
    if ok:
        alias = ensure_shot_alias(final_dir, sid, shot)
        update_manifest(manifest_path, sid, {
            "conformed": True, "conform_method": method,
            "final": str(fin), "final_res": [pr.get("width"), pr.get("height")],
            "final_duration_s": pr.get("duration_s"),
            "final_fps": pr.get("fps"), "final_audio": pr.get("audio"),
            "final_alias": str(alias) if alias else None,
            "finalized_utc": now()})
        print(f"[conform] {now()} {sid} -> {fin.name} "
              f"({pr.get('width')}x{pr.get('height')}, {pr.get('duration_s')}s, "
              f"{pr.get('fps')}fps, audio={pr.get('audio')})"
              + (f" + {alias.name}" if alias else ""), flush=True)
        return {"id": sid, "status": "ok", "res": [pr.get("width"), pr.get("height")],
                "duration": pr.get("duration_s"), "method": method}
    update_manifest(manifest_path, sid, {"conform_error": method, "status": "conform_failed"})
    print(f"[conform] {now()} {sid} FAILED: {method}", flush=True)
    return {"id": sid, "status": "failed", "error": method}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", default=str(DEFAULT_SHOTS))
    ap.add_argument("--raw-dir", default=str(DEFAULT_RAW))
    ap.add_argument("--final-dir", default=str(DEFAULT_FINAL))
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    ap.add_argument("--only", default="")
    ap.add_argument("--fill-missing", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    doc = load_json(args.shots, default=None)
    if doc is None:
        raise SystemExit(f"missing shots file: {args.shots}")
    shot_map = _shot_map(args.shots)
    ids = [s["id"] for s in doc["shots"]]
    order = [x.strip() for x in args.only.split(",") if x.strip()] or ids
    rows = []
    for sid in order:
        raw = sorted(Path(args.raw_dir).glob(f"{sid}_raw.*"))
        fin = final_path(args.final_dir, sid)
        rows.append((sid, raw[0] if raw else None, fin))
    if args.dry:
        for sid, raw, fin in rows:
            print(f"{sid}: raw={'yes' if raw else 'NO'} final={'exists' if fin.exists() else 'missing'}")
        print(f"RESULT: CONFORM_DRY raw={sum(1 for _, r, _ in rows if r)}/{len(rows)} "
              f"final={sum(1 for _, _, f in rows if f.exists())}/{len(rows)}")
        return

    results = []
    for sid, raw, fin in rows:
        if fin.exists() and not args.force:
            results.append({"id": sid, "status": "skipped"})
            continue
        if not raw:
            results.append({"id": sid, "status": "no_raw"})
            continue
        results.append(conform_one(sid, args.raw_dir, args.final_dir, args.manifest,
                                   args.width, args.height, shot_map.get(sid)))
    ok = [r for r in results if r["status"] == "ok"]
    print(json.dumps(results, ensure_ascii=False, indent=1))
    print(f"RESULT: CONFORM_DONE {len(ok)}/{len(results)} conformed")
    raise SystemExit(0 if all(r["status"] in ("ok", "skipped") for r in results) else 4)


if __name__ == "__main__":
    main()
