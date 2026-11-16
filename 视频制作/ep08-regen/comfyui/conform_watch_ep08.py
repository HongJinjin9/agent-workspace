#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os as _os
# 4-core / 6GB cgroup: keep BLAS/torch/ffmpeg thread counts low (Lead resource rule)
for _k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    _os.environ.setdefault(_k, "2")
"""EP08 conform watcher: as each H3 raw (assets/h3/raw/Hxx_raw.mp4) lands, conform it
locally to 1920x1080 (ffmpeg lanczos, keeps audio) atomically as assets/h3/Hxx.mp4.
Runs in parallel with batch_run.py inside the GPU window (pure CPU, does not touch the app).

Status file: assets/h3/conform-status.json. Exits when all shots are conformed or deadline.

  python3 conform_watch_ep08.py 2700
"""
import datetime as dt
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from local_conform import local_conform, ensure_shot_alias  # noqa: E402
from probe_util import probe_video  # noqa: E402

ROOT = HERE.parent
A = ROOT / "assets" / "h3"
RAW = A / "raw"
STATUS = A / "conform-status.json"
SHOTS = HERE / "shots-ep08-run.json"


def now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    budget = float(sys.argv[1] if len(sys.argv) > 1 else 2700)
    deadline = time.time() + budget
    if not SHOTS.exists():
        print(f"[conform-ep08] {now()} no {SHOTS.name}; nothing to watch", flush=True)
        return
    doc = json.loads(SHOTS.read_text(encoding="utf-8"))
    ids = [s["id"] for s in doc["shots"]]
    shot_map = {s["id"]: s.get("shot") for s in doc["shots"] if s.get("shot")}
    status = {}
    if STATUS.exists():
        try:
            status = json.loads(STATUS.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            status = {}
    done = set(status.get("conformed", []))
    print(f"[conform-ep08] {now()} start; {len(ids)} shots; "
          f"deadline in {budget/60:.1f} min; done={sorted(done)}", flush=True)
    while time.time() < deadline:
        progressed = False
        for sid in ids:
            if sid in done:
                continue
            raws = sorted(RAW.glob(f"{sid}_raw.*"))
            final = A / f"{sid}.mp4"
            if not raws or raws[0].stat().st_size < 150_000:
                continue
            t0 = time.time()
            ok, method = local_conform(raws[0], final, 1920, 1080)
            alias = ensure_shot_alias(A, sid, shot_map.get(sid)) if ok else None
            pr = probe_video(final) if ok else {}
            status.setdefault("shots", {})[sid] = {
                "status": "ok" if ok else "failed", "method": method, "final": str(final),
                "final_res": [pr.get("width"), pr.get("height")],
                "final_duration_s": pr.get("duration_s"), "final_fps": pr.get("fps"),
                "final_alias": str(alias) if alias else None,
                "conformed_utc": now(), "elapsed_s": round(time.time() - t0, 1)}
            if ok:
                done.add(sid)
                status["conformed"] = sorted(done)
                print(f"[conform-ep08] {now()} {sid} -> {final.name} "
                      f"({pr.get('width')}x{pr.get('height')}, {pr.get('duration_s')}s, "
                      f"{time.time()-t0:.1f}s) [{len(done)}/{len(ids)}]", flush=True)
            else:
                print(f"[conform-ep08] {now()} {sid} FAILED: {method}", flush=True)
            STATUS.write_text(json.dumps(status, ensure_ascii=False, indent=1), encoding="utf-8")
            progressed = True
        if len(done) >= len(ids):
            print(f"[conform-ep08] {now()} ALL {len(ids)} CONFORMED", flush=True)
            return
        if not progressed:
            time.sleep(3)
    print(f"[conform-ep08] {now()} deadline; conformed={sorted(done)} "
          f"missing={sorted(set(ids)-done)}", flush=True)


if __name__ == "__main__":
    main()
