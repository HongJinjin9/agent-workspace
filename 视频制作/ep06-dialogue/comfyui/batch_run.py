#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EP05 ComfyUI H3 batch runner: login -> (stats/check) -> submit -> poll -> download.

One sampler job at a time (RTX5090 32GB, H3 768p uses ~31GB; never parallel).
Credentials come from env vars H3_USER/H3_PASS (optionally loaded from --env file,
which is kept outside the repo). Nothing secret is ever written to disk by this script.

Usage:
  python3 batch_run.py --stats
  python3 batch_run.py --stats --wait-ready 600
  python3 batch_run.py --dry --only c1
  python3 batch_run.py --only c1,c2,c3,c4,c5,c6 --retries 1
  python3 batch_run.py --only c7,c8 --retries 1
  python3 batch_run.py --only c3 --force --seed c3=202611120903   # regenerate
"""
import argparse
import copy
import datetime as _dt
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "tools"))
from comfy_client import ComfyClient, AppDownError  # noqa: E402

DEFAULT_ENV = "/home/admin/.h3.env"
DEFAULT_WORKFLOW = HERE / "workflows" / "t2v_api.json"
DEFAULT_SHOTS = HERE / "shots-ep05.json"
DEFAULT_RAW = HERE.parent / "assets" / "comfy" / "raw"
DEFAULT_MANIFEST = HERE.parent / "assets" / "comfy" / "manifest.json"
LOG_PATH = HERE / "run.log"

# node ids in workflows/t2v_api.json (see README §二)
N_PROMPT = "140:131"   # MiniMaxH3ImageToVideo: prompt/width/height/length
N_DURATION = "140:133"  # PrimitiveFloat duration seconds
N_SEED = "140:129"     # RandomNoise
N_LIGHTNING = "140:139"  # PrimitiveBoolean "Enable Lightning LoRA" -> true => 8 step turbo
N_SAVE = "92"          # SaveVideo


def utcnow():
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(msg):
    line = f"[{utcnow()}] {msg}"
    print(line, flush=True)
    try:
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def load_env(path):
    """Load 'export K=V' lines from path only for keys not already in os.environ."""
    p = Path(path)
    if not p.exists():
        return 0
    loaded = 0
    for ln in p.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        m = re.match(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$", ln)
        if not m:
            continue
        k, v = m.group(1), m.group(2).strip().strip('"').strip("'")
        if k not in os.environ or not os.environ.get(k):
            os.environ[k] = v
            loaded += 1
    return loaded


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


def rel(p):
    """workspace-relative path when possible, absolute otherwise (tests use /tmp)."""
    try:
        return str(Path(p).relative_to(HERE.parent))
    except ValueError:
        return str(p)


def shots_index(doc):
    idx = {}
    for s in doc["shots"]:
        idx[s["id"]] = s
    return idx


def build_workflow(wf, shot, filename_prefix):
    w = copy.deepcopy(wf)
    inp = w[N_PROMPT]["inputs"]
    inp["prompt"] = shot["prompt"]
    # explicit literal ints replace the ResolutionSelector links: exact pixels, no aspect math
    inp["width"] = int(shot["width"])
    inp["height"] = int(shot["height"])
    w[N_DURATION]["inputs"]["value"] = float(shot["duration"])
    w[N_SEED]["inputs"]["noise_seed"] = int(shot["seed"])
    w[N_LIGHTNING]["inputs"]["value"] = True  # 8-step turbo LoRA path
    w[N_SAVE]["inputs"]["filename_prefix"] = filename_prefix
    for k in ("width", "height"):
        if int(inp[k]) % 32:
            raise SystemExit(f"{shot['id']}: {k}={inp[k]} not a multiple of 32")
    return w


def stats(client):
    st = client.system_stats()
    print(json.dumps(st, ensure_ascii=False, indent=1)[:2000])
    return st


def required_nodes(client):
    info = client.object_info()
    need = ["MiniMaxH3ImageToVideo", "SaveVideo", "CreateVideo", "RandomNoise",
            "BasicScheduler", "SamplerCustomAdvanced", "KSamplerSelect",
            "LoraLoaderModelOnly", "CLIPLoader", "UNETLoader", "VAELoader",
            "ResolutionSelector", "ComfyMathExpression", "ComfySwitchNode"]
    missing = [n for n in need if n not in info]
    print(f"object_info: {len(info)} nodes; missing required: {missing}")
    return not missing


def wait_ready(client, budget_s):
    t0 = time.time()
    delay = 15.0
    while True:
        try:
            stats(client)
            return True
        except AppDownError as e:
            log(f"APP DOWN (gate ok, backend not up): {e}")
        except SystemExit:
            raise
        except Exception as e:  # unreachable TLS / DNS / timeouts
            log(f"endpoint not reachable yet: {type(e).__name__}: {str(e)[:160]}")
        if time.time() - t0 >= budget_s:
            log(f"wait-ready budget {budget_s}s exhausted")
            return False
        time.sleep(delay)
        delay = min(delay * 1.3, 30.0)


def pick_video_output(outs):
    for o in outs:
        if o["filename"].lower().endswith((".mp4", ".webm", ".mov")):
            return o
    return outs[0] if outs else None


def update_manifest(manifest_path, shot, fields):
    m = load_json(manifest_path, default=None) or {
        "series": "ep05-enterprise",
        "window_utc": "2026-11-12T13:50:00Z/14:50:00Z",
        "generator": "ComfyUI H3 (MiniMax H3 int8 + 8-step turbo LoRA, RTX5090)",
        "shots": {},
    }
    m.setdefault("shots", {}).setdefault(shot["id"], {}).update(fields)
    m["updated_utc"] = utcnow()
    save_json(manifest_path, m)
    return m


def run_shot(client, wf, shot, raw_dir, manifest_path, retries, poll_timeout,
             force, filename_prefix):
    sid = shot["id"]
    raw_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(raw_dir.glob(f"{sid}_raw.*"))
    if existing and not force:
        p = existing[0]
        log(f"{sid}: SKIP, raw exists {p.name} ({p.stat().st_size/1048576:.1f} MB)")
        rec = update_manifest(manifest_path, shot, {
            "id": sid, "raw": rel(p), "status": "downloaded"})
        return {"id": sid, "status": "skipped", "raw": str(p)}

    w = build_workflow(wf, shot, filename_prefix)
    attempts = int(retries) + 1
    last_err = None
    for attempt in range(1, attempts + 1):
        t0 = time.time()
        try:
            log(f"{sid}: submit attempt {attempt}/{attempts} "
                f"({shot['width']}x{shot['height']}, {shot['duration']}s, seed={shot['seed']})")
            pid = client.submit(w)
            log(f"{sid}: prompt_id={pid}")
            entry = client.wait(pid, timeout=poll_timeout, interval=2.0)
            el = time.time() - t0
            st = (entry.get("status") or {})
            if st.get("status_str") == "error" or not entry.get("outputs"):
                raise RuntimeError(f"job finished without outputs: status={json.dumps(st)[:400]}")
            outs = client.outputs_of(entry)
            o = pick_video_output(outs)
            if not o:
                raise RuntimeError("no video output in history entry")
            data = client.download(o["filename"], o.get("subfolder", ""), o.get("type", "output"))
            if len(data) < 100_000:
                raise RuntimeError(f"downloaded file suspiciously small: {len(data)} bytes")
            ext = Path(o["filename"]).suffix or ".mp4"
            dst = raw_dir / f"{sid}_raw{ext}"
            tmp = dst.with_name(dst.name + ".part")
            tmp.write_bytes(data)
            tmp.replace(dst)
            log(f"{sid}: saved {dst.name} ({len(data)/1048576:.2f} MB) in {el:.1f}s")
            try:
                update_manifest(manifest_path, shot, {
                    "id": sid,
                    "label": shot.get("title", ""),
                    "segments": shot.get("seg", ""),
                    "spec": shot.get("md", ""),
                    "prompt": shot["prompt"],
                    "source_filename": o["filename"],
                    "job_id": pid,
                    "seed": shot["seed"],
                    "req_res": [shot["width"], shot["height"]],
                    "req_duration_s": shot["duration"],
                    "elapsed_s": round(el, 1),
                    "downloaded_utc": utcnow(),
                    "raw": rel(dst),
                    "status": "downloaded",
                })
            except Exception as me:  # noqa: BLE001 - manifest must not invalidate a good download
                log(f"{sid}: WARN manifest update failed: {me}")
            return {"id": sid, "status": "ok", "raw": str(dst), "elapsed": round(el, 1),
                    "job_id": pid, "filename": o["filename"]}
        except Exception as e:  # noqa: BLE001
            last_err = e
            log(f"{sid}: attempt {attempt} FAILED after {time.time()-t0:.1f}s: "
                f"{type(e).__name__}: {str(e)[:300]}")
            if isinstance(e, SystemExit):
                raise
            if attempt < attempts:
                time.sleep(10 if not isinstance(e, AppDownError) else 30)
    update_manifest(manifest_path, shot, {
        "id": sid, "status": "failed", "error": f"{type(last_err).__name__}: {str(last_err)[:300]}",
        "failed_utc": utcnow()})
    return {"id": sid, "status": "failed", "error": str(last_err)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", default=str(DEFAULT_SHOTS))
    ap.add_argument("--workflow", default=str(DEFAULT_WORKFLOW))
    ap.add_argument("--raw-dir", default=str(DEFAULT_RAW))
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    ap.add_argument("--env", default=DEFAULT_ENV)
    ap.add_argument("--only", default="", help="comma list of shot ids, e.g. c1,c2")
    ap.add_argument("--prefix", default="video/ep05_", help="SaveVideo filename_prefix base")
    ap.add_argument("--retries", type=int, default=1)
    ap.add_argument("--poll-timeout", type=int, default=900)
    ap.add_argument("--force", action="store_true", help="regenerate even if raw exists")
    ap.add_argument("--seed", action="append", default=[], metavar="ID=N", help="override seed")
    ap.add_argument("--res", action="append", default=[], metavar="ID=WxH",
                    help="override resolution for a shot, e.g. c3=864x480 (hero downgrade)")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--check", action="store_true", help="login only")
    ap.add_argument("--wait-ready", type=int, default=0, metavar="SECONDS")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    loaded = load_env(args.env)
    doc = load_json(args.shots)
    idx = shots_index(doc)
    ids = [s.strip() for s in args.only.split(",") if s.strip()] or [s["id"] for s in doc["shots"]]
    for bad in [i for i in ids if i not in idx]:
        raise SystemExit(f"unknown shot id {bad}; known={list(idx)}")
    seeds = {}
    for spec in args.seed:
        k, _, v = spec.partition("=")
        seeds[k] = int(v)
    ress = {}
    for spec in args.res:
        k, _, v = spec.partition("=")
        w, h = v.lower().split("x")
        ress[k] = (int(w), int(h))
    shots = []
    for i in ids:
        s = dict(idx[i])
        if i in seeds:
            s["seed"] = seeds[i]
        if i in ress:
            s["width"], s["height"] = ress[i]
        shots.append(s)

    if args.list or args.dry:
        wf = load_json(args.workflow)
        for s in shots:
            w = build_workflow(wf, s, args.prefix + s["id"])
            print(f"{s['id']}: {s['width']}x{s['height']} {s['duration']}s seed={s['seed']} "
                  f"prompt={len(s['prompt'])}ch save_prefix={w[N_SAVE]['inputs']['filename_prefix']} "
                  f"lightning={w[N_LIGHTNING]['inputs']['value']} "
                  f"len_expr={w[N_PROMPT]['inputs']['length']}")
        if args.dry or args.list:
            if not (args.stats or args.check):
                return

    log(f"env loaded {loaded} keys from {args.env}; user={'set' if os.environ.get('H3_USER') else 'MISSING'} "
        f"base={os.environ.get('H3_BASE', 'default')}")
    client = ComfyClient(os.environ.get("H3_BASE", "https://wp08.unicorn.org.cn:24909"),
                         os.environ.get("H3_USER", ""), os.environ.get("H3_PASS", ""))
    try:
        client.login()
        log("login OK (wyfgate cookie obtained)")
    except SystemExit as e:
        log(f"LOGIN REJECTED: {e}")
        print("RESULT: LOGIN_REJECTED", flush=True)
        raise SystemExit(3)
    except Exception as e:  # noqa: BLE001
        log(f"ENDPOINT UNREACHABLE at login: {type(e).__name__}: {str(e)[:200]}")
        if args.wait_ready:
            if not wait_ready(client, args.wait_ready):
                print("RESULT: UNREACHABLE", flush=True)
                raise SystemExit(2)
        else:
            print("RESULT: UNREACHABLE", flush=True)
            raise SystemExit(2)

    if args.check:
        print("RESULT: LOGIN_OK")
        return
    if args.wait_ready:
        wait_ready(client, args.wait_ready)
    if args.stats or args.list:
        try:
            stats(client)
            ok = required_nodes(client)
            print(f"RESULT: STATS_OK nodes_ok={ok}")
        except Exception as e:  # noqa: BLE001
            log(f"stats failed: {type(e).__name__}: {str(e)[:200]}")
            print("RESULT: APP_DOWN_OR_ERROR", flush=True)
            raise SystemExit(2)
        if args.stats or args.list:
            return

    wf = load_json(args.workflow)
    raw_dir = Path(args.raw_dir)
    manifest = Path(args.manifest)
    results = []
    t_all = time.time()
    for s in shots:
        r = run_shot(client, wf, s, raw_dir, manifest, args.retries, args.poll_timeout,
                     args.force, args.prefix)
        results.append(r)
        log(f"progress: {json.dumps(r, ensure_ascii=False)[:400]}")
    log(f"batch done in {time.time()-t_all:.1f}s: "
        f"{sum(1 for r in results if r['status'] in ('ok','skipped'))}/{len(results)} ok")
    print(json.dumps(results, ensure_ascii=False, indent=1))
    ok = all(r["status"] in ("ok", "skipped") for r in results)
    print("RESULT: BATCH_OK" if ok else "RESULT: BATCH_PARTIAL")
    raise SystemExit(0 if ok else 4)


if __name__ == "__main__":
    try:
        main()
    except AppDownError as e:
        print(f"[APP DOWN] {e}", file=sys.stderr)
        sys.exit(2)
