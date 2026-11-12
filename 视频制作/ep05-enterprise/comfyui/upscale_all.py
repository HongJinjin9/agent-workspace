#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Upscale EP05 H3 raw clips to 1920x1080 on the rented app, one job at a time.

Chain (same as tools/upscale_video.py, measured 107.5s for 864x480 -> 1080p):
  LoadVideo -> GetVideoComponents -> 4x-UltraSharp (ImageUpscaleWithModel)
  -> ImageScale lanczos to 1920x1080 -> CreateVideo (keeps original audio) -> SaveVideo

Behaviour:
  - priority order (default c1,c4,c5,c3,c2,c6,c7,c8); skip clips already final unless --force
  - hard deadline (default 14:35 UTC): once passed, stop app upscales
  - --fill-missing (default on): any clip without a final gets the raw copied to
    assets/comfy/cN.mp4 and is marked upscaled=false (native fallback) so the pipeline
    always has 8 files; report tells which are native
  - writes every final atomically (<name>.part -> rename) so the compositor never
    reads a partial file; updates assets/comfy/manifest.json after each clip
"""
import argparse
import datetime as _dt
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "tools"))
from comfy_client import ComfyClient  # noqa: E402
from upscale_video import build_graph, upload_video  # noqa: E402
from batch_run import load_env, load_json, save_json, log, utcnow, \
    DEFAULT_ENV, DEFAULT_SHOTS, DEFAULT_MANIFEST  # noqa: E402

ROOT = HERE.parent
RAW_DIR = ROOT / "assets" / "comfy" / "raw"
FINAL_DIR = ROOT / "assets" / "comfy"


from probe_util import probe_video  # ffmpeg-based probe (no real ffprobe on this box)


def atomic_write_bytes(dst: Path, data: bytes):
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + ".part")
    tmp.write_bytes(data)
    tmp.replace(dst)


def atomic_copy(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + ".part")
    shutil.copyfile(src, tmp)
    tmp.replace(dst)


def local_conform(raw: Path, fin: Path, w: int, h: int):
    """Fast no-GPU 1080p conform (lanczos + light unsharp), keeps audio, atomic write."""
    fin.parent.mkdir(parents=True, exist_ok=True)
    tmp = fin.parent / (fin.stem + ".tmp.mp4")
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-vf",
           f"scale={w}:{h}:flags=lanczos+accurate_rnd+full_chroma_int,"
           f"unsharp=5:5:0.45:5:5:0.0",
           "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
           "-r", "24", "-c:a", "aac", "-b:a", "192k", str(tmp)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode == 0 and tmp.exists():
        tmp.replace(fin)
        return True, f"local-ffmpeg-lanczos {w}x{h}"
    if tmp.exists():
        tmp.unlink()
    return False, (r.stderr or "ffmpeg failed")[:300]


def update_manifest(manifest_path, sid, fields):
    m = load_json(manifest_path, default=None) or {"series": "ep05-enterprise", "shots": {}}
    m.setdefault("shots", {}).setdefault(sid, {}).update(fields)
    m["updated_utc"] = utcnow()
    save_json(manifest_path, m)


def pick_video_output(outs):
    for o in outs:
        if o["filename"].lower().endswith((".mp4", ".webm", ".mov")):
            return o
    return outs[0] if outs else None


def deadline_epoch(hhmm):
    now = _dt.datetime.now(_dt.timezone.utc)
    h, mnt = map(int, hhmm.split(":"))
    dl = now.replace(hour=h, minute=mnt, second=0, microsecond=0)
    return dl.timestamp()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", default=str(DEFAULT_SHOTS))
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    ap.add_argument("--env", default=DEFAULT_ENV)
    ap.add_argument("--order", default="c1,c4,c5,c3,c2,c6,c7,c8")
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--model", default="4x-UltraSharp.pth")
    ap.add_argument("--deadline", default="14:35", help="UTC HH:MM hard stop for app upscales")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--no-fill-missing", dest="fill_missing", action="store_false")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--local-ids", default="c1,c3",
                    help="clips conformed locally (no GPU 4x); hero sources already 1280x736")
    ap.add_argument("--raw-dir", default=str(RAW_DIR))
    ap.add_argument("--final-dir", default=str(FINAL_DIR))
    args = ap.parse_args()
    raw_dir, final_dir = Path(args.raw_dir), Path(args.final_dir)
    local_ids = {x.strip() for x in args.local_ids.split(",") if x.strip()}
    raw_dir.mkdir(parents=True, exist_ok=True)
    final_dir.mkdir(parents=True, exist_ok=True)

    load_env(args.env)
    doc = load_json(args.shots)
    ids = [s["id"] for s in doc["shots"]]
    order = [x.strip() for x in args.order.split(",") if x.strip()]
    if args.only:
        order = [x.strip() for x in args.only.split(",") if x.strip()]
    order = [s for s in order if s in ids]
    if args.only:
        order = [x.strip() for x in args.only.split(",") if x.strip() in ids]
    else:
        order += [s for s in ids if s not in order]  # unlisted clips still filled/upscaled last
    dl = deadline_epoch(args.deadline)
    log(f"upscale target {args.width}x{args.height}, order={order}, "
        f"deadline={args.deadline}Z (in {(dl-time.time())/60:.1f} min), force={args.force}")

    if args.dry:
        for sid in order:
            raw = raw_dir / f"{sid}_raw.mp4"
            fin = final_dir / f"{sid}.mp4"
            print(f"{sid}: raw={'yes' if raw.exists() else 'NO'} "
                  f"final={'exists' if fin.exists() else 'missing'}")
        return

    client = ComfyClient(os.environ.get("H3_BASE", "https://wp08.unicorn.org.cn:24909"),
                         os.environ.get("H3_USER", ""), os.environ.get("H3_PASS", ""))
    client.login()
    log("upscale login OK")
    results = []
    for sid in order:
        raw = raw_dir / f"{sid}_raw.mp4"
        fin = final_dir / f"{sid}.mp4"
        if fin.exists() and not args.force:
            log(f"{sid}: final already exists, skip upscale")
            results.append({"id": sid, "status": "skipped"})
            continue
        if not raw.exists():
            log(f"{sid}: NO RAW FILE, cannot upscale")
            results.append({"id": sid, "status": "no_raw"})
            continue
        if time.time() > dl:
            log(f"{sid}: deadline {args.deadline}Z passed, stopping app upscales")
            results.append({"id": sid, "status": "deadline"})
            continue
        t0 = time.time()
        if sid in local_ids:
            ok_l, method = local_conform(raw, fin, args.width, args.height)
            pr = probe_video(fin) if ok_l else {}
            log(f"{sid}: LOCAL hero conform {'OK' if ok_l else 'FAILED'} in {time.time()-t0:.1f}s "
                f"-> {fin.name} ({pr.get('width')}x{pr.get('height')})")
            if ok_l:
                fpath = str(fin.relative_to(ROOT)) if str(fin).startswith(str(ROOT)) else str(fin)
                update_manifest(args.manifest, sid, {
                    "upscaled": True, "upscale_method": method + " (hero, local)",
                    "upscale_elapsed_s": round(time.time() - t0, 1),
                    "upscale_job_id": None, "final": fpath,
                    "final_res": [pr.get("width"), pr.get("height")],
                    "final_duration_s": pr.get("duration_s"), "status": "ok",
                    "finalized_utc": utcnow()})
                results.append({"id": sid, "status": "local",
                                "res": [pr.get("width"), pr.get("height")]})
            else:
                results.append({"id": sid, "status": "failed", "error": method})
            continue
        try:
            name = upload_video(client, raw)
            graph = build_graph(name, args.width, args.height, args.model, f"upscale/ep05_{sid}")
            pid = client.submit(graph)
            log(f"{sid}: upscale submitted ({raw.stat().st_size/1048576:.1f} MB -> "
                f"{args.width}x{args.height}, model={args.model}) prompt_id={pid}")
            entry = client.wait(pid, timeout=args.timeout, quiet=True)
            el = time.time() - t0
            outs = client.outputs_of(entry)
            o = pick_video_output(outs)
            if not o:
                raise RuntimeError("upscale job produced no video output")
            data = client.download(o["filename"], o.get("subfolder", ""), o.get("type", "output"))
            if len(data) < 100_000:
                raise RuntimeError(f"upscale output too small: {len(data)} bytes")
            atomic_write_bytes(fin, data)
            pr = probe_video(fin)
            log(f"{sid}: upsale done in {el:.1f}s -> {fin.name} "
                f"({len(data)/1048576:.2f} MB, {pr.get('width')}x{pr.get('height')}, "
                f"{pr.get('duration_s')}s)")
            update_manifest(args.manifest, sid, {
                "upscaled": True, "upscale_method": f"app:4x-UltraSharp+lanczos "
                f"{args.width}x{args.height}", "upscale_elapsed_s": round(el, 1),
                "upscale_job_id": pid, "final": str(fin.relative_to(ROOT)) if str(fin).startswith(str(ROOT)) else str(fin),
                "final_res": [pr.get("width"), pr.get("height")],
                "final_duration_s": pr.get("duration_s"), "status": "ok",
                "finalized_utc": utcnow()})
            results.append({"id": sid, "status": "upscaled", "elapsed": round(el, 1),
                            "job": pid, "res": [pr.get("width"), pr.get("height")]})
        except Exception as e:  # noqa: BLE001
            log(f"{sid}: UPSCALE FAILED after {time.time()-t0:.1f}s: "
                f"{type(e).__name__}: {str(e)[:300]}")
            update_manifest(args.manifest, sid,
                            {"upscale_error": f"{type(e).__name__}: {str(e)[:300]}"})
            results.append({"id": sid, "status": "failed", "error": str(e)[:300]})

    if args.fill_missing:
        for sid in ids:
            raw = raw_dir / f"{sid}_raw.mp4"
            fin = final_dir / f"{sid}.mp4"
            if fin.exists() or not raw.exists():
                continue
            ok_l, method = local_conform(raw, fin, args.width, args.height)
            src = "raw"
            if not ok_l:
                log(f"{sid}: local ffmpeg conform failed ({method}); native copy")
                atomic_copy(raw, fin)
                method, src = "none (native raw fallback; local conform failed)", "raw-native"
            pr = probe_video(fin)
            log(f"{sid}: fallback {method} -> {fin.name} "
                f"({pr.get('width')}x{pr.get('height')}, {pr.get('duration_s')}s)")
            update_manifest(args.manifest, sid, {
                "upscaled": (src == "raw"), "upscale_method": method,
                "final": str(fin.relative_to(ROOT)) if str(fin).startswith(str(ROOT)) else str(fin),
                "final_res": [pr.get("width"), pr.get("height")],
                "final_duration_s": pr.get("duration_s"), "status": "ok",
                "finalized_utc": utcnow()})

    ok = [r for r in results if r["status"] in ("upscaled", "skipped", "local")]
    log(f"upscale batch: {len(ok)}/{len(results)} ok, {sum(1 for r in results if r['status']=='failed')} failed")
    print(json.dumps(results, ensure_ascii=False, indent=1))
    print("RESULT: UPSCALE_DONE" if len(ok) == len(results) else "RESULT: UPSCALE_PARTIAL")
    raise SystemExit(0 if len(ok) == len(results) else 4)


if __name__ == "__main__":
    main()
