#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Conform each completed H3 raw to 1920x1080 locally the moment it lands.

Runs concurrently with batch_run.py (generation = GPU, this = CPU ffmpeg, ~6s/clip).
Writes assets/comfy/cN.mp4 atomically (never partial) so the compositor can poll.
Status goes to assets/comfy/conform-status.json (no lock contention with manifest.json).
"""
import datetime as dt
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from upscale_all import local_conform  # noqa: E402
from probe_util import probe_video  # noqa: E402

ROOT = HERE.parent
A = ROOT / "assets" / "comfy"
RAW = A / "raw"
STATUS = A / "conform-status.json"


def now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    deadline = time.time() + float(sys.argv[1] if len(sys.argv) > 1 else 1800)
    ids = [f"c{i}" for i in range(1, 9)]
    status = {}
    if STATUS.exists():
        status = json.loads(STATUS.read_text(encoding="utf-8"))
    done = set(status.get("conformed", []))
    print(f"[conform-watch] {now()} start; deadline in {(deadline-time.time())/60:.1f} min; "
          f"already done={sorted(done)}", flush=True)
    while time.time() < deadline:
        progressed = False
        for sid in ids:
            if sid in done:
                continue
            raw = RAW / f"{sid}_raw.mp4"
            final = A / f"{sid}.mp4"
            if not raw.exists() or raw.stat().st_size < 200_000:
                continue
            t0 = time.time()
            ok, method = local_conform(raw, final, 1920, 1080)
            pr = probe_video(final) if ok else {}
            status.setdefault("shots", {})[sid] = {
                "status": "ok" if ok else "failed", "method": method,
                "final": str(final), "final_res": [pr.get("width"), pr.get("height")],
                "final_duration_s": pr.get("duration_s"),
                "conformed_utc": now(), "elapsed_s": round(time.time() - t0, 1),
            }
            if ok:
                done.add(sid)
                status["conformed"] = sorted(done)
                print(f"[conform-watch] {now()} {sid} -> {final.name} "
                      f"({pr.get('width')}x{pr.get('height')}, {pr.get('duration_s')}s, "
                      f"{time.time()-t0:.1f}s) [{len(done)}/8]", flush=True)
            else:
                print(f"[conform-watch] {now()} {sid} FAILED: {method}", flush=True)
            STATUS.write_text(json.dumps(status, ensure_ascii=False, indent=1), encoding="utf-8")
            progressed = True
        if len(done) >= 8:
            print(f"[conform-watch] {now()} ALL 8 CONFORMED", flush=True)
            return
        if not progressed:
            time.sleep(4)
    print(f"[conform-watch] {now()} deadline; conformed={sorted(done)}", flush=True)


if __name__ == "__main__":
    main()
