#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os as _os
# 4-core / 6GB cgroup: keep BLAS/torch/ffmpeg thread counts low (Lead resource rule)
for _k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    _os.environ.setdefault(_k, "2")
"""EP08 ComfyUI H3 batch runner: login -> (stats) -> upload keyframes -> generate -> poll -> download.

One sampler job at a time (RTX5090 32GB; H3 864x480/5s uses ~31GB; never parallel).
Credentials come from env vars H3_USER/H3_PASS (optionally loaded from --env file kept
outside the repo). Nothing secret is ever written to disk by this script.

Modes per shot (auto):
  - shot has "first_frame" (and the file exists)  -> FL2VA/i2v via LoadImage -> ImageScale
    -> MiniMaxH3ImageToVideo.first_frame[/last_frame]   (composition locked by code keyframe)
  - otherwise                                     -> T2V (workflows/t2v_api.json as-is)
  - runtime failure of FL2VA is retried once as T2V, and the mode is recorded in the manifest.

Workflow variable nodes (workflows/t2v_api.json, verified from the real API JSON):
  "140:131" MiniMaxH3ImageToVideo  prompt / width / height / length / first_frame / last_frame
  "140:132" ComfyMathExpression    length frames = max(5, round(a*24)) + (5 - (…%17)) % 17
  "140:133" PrimitiveFloat         duration seconds
  "140:129" RandomNoise            noise_seed
  "140:139" PrimitiveBoolean       Enable turbo LoRA (true => 8-step path, node 140:138 steps=8)
  "140:127" UNETLoader             minimax_h3_fl2va_pruned_int8_convrot.safetensors
  "140:128" CLIPLoader             qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors (type=minimax)
  "140:119"/"140:120" VAELoader    video vae fp16 / audio vae fp32 (both required)
  "92"      SaveVideo              filename_prefix (video comes from CreateVideo "140:130")
  "115"     ResolutionSelector     bypassed: literal width/height ints are injected instead

Usage:
  python3 batch_run.py --stats
  python3 batch_run.py --dry --mode auto            # no network; validate workflows/params
  python3 batch_run.py --only H01,H02 --retries 1
  python3 batch_run.py --only H03 --force --seed H03=202611160903
"""
import argparse
import copy
import datetime as _dt
import json
import os
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "tools"))
from comfy_client import ComfyClient, AppDownError  # noqa: E402

DEFAULT_ENV = "/home/admin/.h3.env"
DEFAULT_WORKFLOW = HERE / "workflows" / "t2v_api.json"
DEFAULT_SHOTS = HERE / "shots-ep08-run.json"
DEFAULT_RAW = HERE.parent / "assets" / "h3" / "raw"
DEFAULT_MANIFEST = HERE.parent / "assets" / "h3" / "manifest.json"
LOG_PATH = HERE / "run.log"

# node ids in workflows/t2v_api.json (see docstring)
N_PROMPT = "140:131"     # MiniMaxH3ImageToVideo: prompt/width/height/length (+ first_frame/last_frame)
N_LENGTH = "140:132"     # ComfyMathExpression: frame count
N_DURATION = "140:133"   # PrimitiveFloat duration seconds
N_SEED = "140:129"       # RandomNoise
N_LIGHTNING = "140:139"  # PrimitiveBoolean turbo LoRA switch
N_SAVE = "92"            # SaveVideo
N_STEPS_TURBO = "140:138"
N_UNET = "140:127"
N_CLIP = "140:128"
N_VAE_VIDEO = "140:119"
N_VAE_AUDIO = "140:120"
N_RES_SELECTOR = "115"

# injected FL2VA helper node ids (kept out of the template so T2V stays byte-identical)
N_LOAD_FIRST = "900"
N_SCALE_FIRST = "901"
N_LOAD_LAST = "910"
N_SCALE_LAST = "911"

IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp")


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
    """workspace-relative path when possible, absolute otherwise."""
    try:
        return str(Path(p).relative_to(HERE.parent))
    except ValueError:
        return str(p)


def shots_index(doc):
    return {s["id"]: s for s in doc["shots"]}


def resolve_path(p, base=None):
    """Resolve a shots-json path: absolute as-is, else relative to comfyui/ then ep08 root."""
    if not p:
        return None
    pp = Path(p)
    if pp.is_absolute():
        return pp
    for cand in ([base] if base else []) + [HERE, HERE.parent]:
        if (Path(cand) / pp).exists():
            return Path(cand) / pp
    return HERE / pp  # report as missing under comfyui/


def frame_of(shot, which):
    """Return existing local keyframe path or None. `which` is 'first_frame'/'last_frame'."""
    return resolve_path(shot.get(which))


def build_workflow(wf, shot, filename_prefix, mode="auto", uploaded=None):
    """Deep-copy template and inject per-shot variables. Never mutates the template.

    mode: "t2v" | "fl2va" (fl2va requires keyframe(s) and uploaded remote names).
    """
    w = copy.deepcopy(wf)
    inp = w[N_PROMPT]["inputs"]
    inp["prompt"] = shot["prompt"]
    # explicit literal ints replace the ResolutionSelector links: exact pixels, no aspect math
    inp["width"] = int(shot["width"])
    inp["height"] = int(shot["height"])
    w[N_DURATION]["inputs"]["value"] = float(shot["duration"])
    w[N_SEED]["inputs"]["noise_seed"] = int(shot["seed"])
    w[N_LIGHTNING]["inputs"]["value"] = bool(shot.get("enable_lightning_lora", True))
    w[N_SAVE]["inputs"]["filename_prefix"] = filename_prefix
    for k in ("width", "height"):
        if int(inp[k]) % 32:
            raise SystemExit(f"{shot['id']}: {k}={inp[k]} not a multiple of 32")

    if mode == "fl2va":
        w[N_PROMPT]["inputs"].pop("first_frame", None)
        w[N_PROMPT]["inputs"].pop("last_frame", None)
        first = (uploaded or {}).get("first_frame")
        last = (uploaded or {}).get("last_frame")
        if not first and not last:
            raise SystemExit(f"{shot['id']}: fl2va mode requested without any keyframe")
        if first:
            w[N_LOAD_FIRST] = {"class_type": "LoadImage",
                               "inputs": {"image": first},
                               "_meta": {"title": f"first frame {shot['id']}"}}
            w[N_SCALE_FIRST] = {"class_type": "ImageScale",
                                "inputs": {"image": [N_LOAD_FIRST, 0],
                                           "upscale_method": "lanczos",
                                           "width": int(shot["width"]),
                                           "height": int(shot["height"]),
                                           "crop": "disabled"},
                                "_meta": {"title": "scale first frame to gen res"}}
            w[N_PROMPT]["inputs"]["first_frame"] = [N_SCALE_FIRST, 0]
        if last:
            w[N_LOAD_LAST] = {"class_type": "LoadImage",
                              "inputs": {"image": last},
                              "_meta": {"title": f"last frame {shot['id']}"}}
            w[N_SCALE_LAST] = {"class_type": "ImageScale",
                               "inputs": {"image": [N_LOAD_LAST, 0],
                                          "upscale_method": "lanczos",
                                          "width": int(shot["width"]),
                                          "height": int(shot["height"]),
                                          "crop": "disabled"},
                               "_meta": {"title": "scale last frame to gen res"}}
            w[N_PROMPT]["inputs"]["last_frame"] = [N_SCALE_LAST, 0]
    else:
        w[N_PROMPT]["inputs"].pop("first_frame", None)
        w[N_PROMPT]["inputs"].pop("last_frame", None)
    return w


def describe_workflow(w):
    """Human summary of the injected variable values (for --dry output)."""
    inp = w[N_PROMPT]["inputs"]
    fl = "first_frame" in inp
    lf = "last_frame" in inp
    return {
        "prompt_node": N_PROMPT,
        "width": inp["width"], "height": inp["height"],
        "length_expr": w[N_LENGTH]["inputs"]["expression"],
        "duration_s": w[N_DURATION]["inputs"]["value"],
        "seed": w[N_SEED]["inputs"]["noise_seed"],
        "turbo": w[N_LIGHTNING]["inputs"]["value"],
        "steps": w[N_STEPS_TURBO]["inputs"]["value"],
        "unet": w[N_UNET]["inputs"]["unet_name"],
        "clip": w[N_CLIP]["inputs"]["clip_name"],
        "vae_video": w[N_VAE_VIDEO]["inputs"]["vae_name"],
        "vae_audio": w[N_VAE_AUDIO]["inputs"]["vae_name"],
        "save_prefix": w[N_SAVE]["inputs"]["filename_prefix"],
        "prompt_chars": len(inp["prompt"]),
        "first_frame": (inp.get("first_frame") or [None])[0] if fl else None,
        "last_frame": (inp.get("last_frame") or [None])[0] if lf else None,
    }


def stats(client):
    st = client.system_stats()
    print(json.dumps(st, ensure_ascii=False, indent=1)[:2000])
    return st


REQUIRED_NODES = ["MiniMaxH3ImageToVideo", "SaveVideo", "CreateVideo", "RandomNoise",
                  "BasicScheduler", "SamplerCustomAdvanced", "KSamplerSelect",
                  "LoraLoaderModelOnly", "CLIPLoader", "UNETLoader", "VAELoader",
                  "ResolutionSelector", "ComfyMathExpression", "ComfySwitchNode",
                  "LoadImage", "ImageScale"]


def required_nodes(client):
    info = client.object_info()
    missing = [n for n in REQUIRED_NODES if n not in info]
    print(f"object_info: {len(info)} nodes; missing required: {missing}")
    # FL2VA capability: does MiniMaxH3ImageToVideo accept first_frame/last_frame links?
    cap = {"fl2va_optional_inputs": False}
    node = info.get("MiniMaxH3ImageToVideo") or {}
    opt = (node.get("input") or {}).get("optional") or {}
    cap["fl2va_optional_inputs"] = "first_frame" in opt and "last_frame" in opt
    print(f"FL2VA capability: MiniMaxH3ImageToVideo first/last_frame = "
          f"{cap['fl2va_optional_inputs']}")
    return not missing, cap


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


def upload_image(client, path, remote_name=None):
    """Upload a local keyframe PNG into the ComfyUI input dir; returns the remote name."""
    path = Path(path)
    name = remote_name or path.name
    with path.open("rb") as fh:
        r = client.s.post(
            client.base + "/upload/image",
            files={"image": (name, fh, "image/png")},
            data={"overwrite": "true", "type": "input"},
            timeout=180,
        )
    if r.status_code >= 400:
        raise RuntimeError(f"upload/image {path.name} -> {r.status_code}: {r.text[:300]}")
    out = r.json()
    return out.get("name") or name


SANITIZE_PATH = HERE / "keyframe-sanitize.json"


def _sanitize_boxes(shot, which):
    """Blur small brand logos / printed labels before upload (red-line control, PDF §6)."""
    if which != "first":
        return []
    try:
        doc = json.loads(SANITIZE_PATH.read_text(encoding="utf-8"))
        boxes = (doc.get("boxes") or {})
        keys = [str(shot.get("shot")), str(shot.get("id"))]
        for k in keys:
            if k and k in boxes:
                return boxes[k]
    except Exception:  # noqa: BLE001
        pass
    return []


def prepare_upload_image(src: Path, shot: dict, dst_dir: Path, which: str = "first") -> Path:
    """Downscale/cover-crop the code keyframe to the exact generation pixels before upload.

    Faster upload, and composition is pixel-locked to what the generator will output;
    ImageScale still sits in the graph as a defensive no-op. Falls back to the original
    file if PIL is unavailable or the image cannot be read.
    """
    try:
        from PIL import Image
        im = Image.open(src).convert("RGB")
        tw, th = int(shot["width"]), int(shot["height"])
        boxes = _sanitize_boxes(shot, which)
        if im.size != (tw, th):
            sw, sh = im.size
            scale = max(tw / sw, th / sh)
            nw, nh = max(tw, round(sw * scale)), max(th, round(sh * scale))
            im = im.resize((nw, nh), Image.LANCZOS)
            left = (nw - tw) // 2
            top = (nh - th) // 2
            im = im.crop((left, top, left + tw, top + th))
        elif not boxes:
            return src
        if boxes:
            from PIL import ImageFilter
            radius = max(12, int(tw * 0.05))  # ~43px at 864 wide: unreadable, texture stays
            for b in boxes:
                if not (isinstance(b, (list, tuple)) and len(b) == 4):
                    continue
                x0, y0, x1, y1 = [int(round(v * d)) for v, d in
                                  zip(b, (tw, th, tw, th))]
                x0, x1 = max(0, min(x0, x1)), min(tw, max(x0, x1))
                y0, y1 = max(0, min(y0, y1)), min(th, max(y0, y1))
                if x1 - x0 < 4 or y1 - y0 < 4:
                    continue
                region = im.crop((x0, y0, x1, y1)).filter(ImageFilter.GaussianBlur(radius))
                im.paste(region, (x0, y0))
            log(f"{shot.get('id')}: sanitized {len(boxes)} region(s) on keyframe "
                f"(logo/printed text blur)")
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / f"{shot['id']}_{which}{src.suffix.lower()}"
        im.save(dst, optimize=False)
        return dst
    except Exception as e:  # noqa: BLE001
        log(f"{shot.get('id')}: keyframe prep skipped ({type(e).__name__}: {e})")
        return src


def preupload_keyframes(client, shots):
    """Upload every needed keyframe once. Returns {(shot_id, which): remote name}."""
    mapping = {}
    prep_dir = HERE.parent / "assets" / "h3" / "keyframes-upload"
    for s in shots:
        for which in ("first_frame", "last_frame"):
            p = frame_of(s, which)
            if not p:
                continue
            up_src = prepare_upload_image(p, s, prep_dir, which.replace("_frame", ""))
            remote = f"ep08_{s['id']}_{which.replace('_frame', '')}{up_src.suffix.lower()}"
            try:
                t0 = time.time()
                got = upload_image(client, up_src, remote)
                mapping[(s["id"], which)] = got
                log(f"{s['id']}: uploaded {which} {up_src.name} -> {got} "
                    f"({time.time()-t0:.1f}s)")
            except Exception as e:  # noqa: BLE001 — a broken keyframe just drops to T2V
                log(f"{s['id']}: KEYFRAME UPLOAD FAILED {which} {up_src.name}: "
                    f"{type(e).__name__}: {str(e)[:200]}")
    return mapping


def pick_video_output(outs):
    for o in outs:
        if o["filename"].lower().endswith((".mp4", ".webm", ".mov")):
            return o
    return outs[0] if outs else None


def update_manifest(manifest_path, shot, fields):
    m = load_json(manifest_path, default=None) or {
        "series": "ep08-regen",
        "generator": "ComfyUI H3 (MiniMax H3 FL2VA int8 + 8-step turbo LoRA, RTX5090)",
        "shots": {},
    }
    m.setdefault("shots", {}).setdefault(shot["id"], {}).update(fields)
    m["updated_utc"] = utcnow()
    save_json(manifest_path, m)
    return m


def submit_once(client, wf, shot, mode, filename_prefix, raw_dir, manifest_path,
                poll_timeout, uploaded):
    t0 = time.time()
    w = build_workflow(wf, shot, filename_prefix, mode=mode, uploaded=uploaded)
    log(f"{shot['id']}: submit ({mode}) "
        f"({shot['width']}x{shot['height']}, {shot['duration']}s, seed={shot['seed']})")
    pid = client.submit(w)
    log(f"{shot['id']}: prompt_id={pid}")
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
    dst = raw_dir / f"{shot['id']}_raw{ext}"
    tmp = dst.with_name(dst.name + ".part")
    tmp.write_bytes(data)
    tmp.replace(dst)
    log(f"{shot['id']}: saved {dst.name} ({len(data)/1048576:.2f} MB) in {el:.1f}s [{mode}]")
    return {"pid": pid, "elapsed": el, "dst": dst, "filename": o["filename"], "mode": mode,
            "bytes": len(data)}


def run_shot(client, wf, shot, raw_dir, manifest_path, retries, poll_timeout,
             force, filename_prefix, uploaded, deadline, forced_mode=None):
    sid = shot["id"]
    raw_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(raw_dir.glob(f"{sid}_raw.*"))
    if existing and not force:
        p = existing[0]
        log(f"{sid}: SKIP, raw exists {p.name} ({p.stat().st_size/1048576:.1f} MB)")
        update_manifest(manifest_path, shot, {
            "id": sid, "raw": rel(p), "status": "downloaded"})
        return {"id": sid, "status": "skipped", "raw": str(p)}
    if deadline and time.time() > deadline:
        log(f"{sid}: WINDOW DEADLINE passed before submit -> deferred")
        update_manifest(manifest_path, shot, {"id": sid, "status": "deferred",
                                              "deferred_utc": utcnow()})
        return {"id": sid, "status": "deferred"}

    # mode decision: FL2VA only when a keyframe exists AND it uploaded fine
    has_first = bool((uploaded or {}).get("first_frame") or (uploaded or {}).get("last_frame"))
    primary = "fl2va" if has_first else "t2v"
    if forced_mode == "t2v":
        primary = "t2v"
    plan = [primary] + (["t2v"] if primary == "fl2va" else [])
    plan = plan[: max(1, int(retries) + 1)]
    last_err = None
    for attempt, mode in enumerate(plan, start=1):
        t0 = time.time()
        try:
            r = submit_once(client, wf, shot, mode, filename_prefix, raw_dir,
                            manifest_path, poll_timeout, uploaded)
            update_manifest(manifest_path, shot, {
                "id": sid,
                "shot": shot.get("shot"),
                "label": shot.get("title", ""),
                "segments": shot.get("seg", ""),
                "spec": shot.get("md", ""),
                "prompt": shot["prompt"],
                "mode": mode,
                "keyframes_used": {k: v for k, v in (uploaded or {}).items()},
                "source_filename": r["filename"],
                "job_id": r["pid"],
                "seed": shot["seed"],
                "req_res": [shot["width"], shot["height"]],
                "req_duration_s": shot["duration"],
                "elapsed_s": round(r["elapsed"], 1),
                "downloaded_utc": utcnow(),
                "raw": rel(r["dst"]),
                "status": "downloaded",
            })
            return {"id": sid, "status": "ok", "raw": str(r["dst"]),
                    "elapsed": round(r["elapsed"], 1), "job_id": r["pid"],
                    "filename": r["filename"], "mode": mode}
        except Exception as e:  # noqa: BLE001
            last_err = e
            log(f"{sid}: attempt {attempt} ({mode}) FAILED after {time.time()-t0:.1f}s: "
                f"{type(e).__name__}: {str(e)[:300]}")
            if isinstance(e, SystemExit):
                raise
            net_err = isinstance(e, AppDownError) or type(e).__name__ in (
                "ConnectionError", "ConnectTimeout", "ReadTimeout", "Timeout", "SSLError",
                "ConnectTimeoutError", "ConnectionTimeout", "NewConnectionError",
                "MaxRetryError", "ChunkedEncodingError")
            if net_err:
                # backend/network died mid-window: stop burning the paid hour on doomed submits
                update_manifest(manifest_path, shot, {
                    "id": sid, "status": "deferred", "error": str(e)[:300],
                    "deferred_utc": utcnow()})
                return {"id": sid, "status": "app_down", "error": str(e)[:300]}
            if attempt < len(plan):
                time.sleep(8)
    update_manifest(manifest_path, shot, {
        "id": sid, "status": "failed",
        "error": f"{type(last_err).__name__}: {str(last_err)[:300]}",
        "failed_utc": utcnow()})
    return {"id": sid, "status": "failed", "error": str(last_err)}


def deadline_epoch(hhmm):
    now = _dt.datetime.now(_dt.timezone.utc)
    h, mnt = map(int, hhmm.split(":"))
    dl = now.replace(hour=h, minute=mnt, second=0, microsecond=0)
    return dl.timestamp()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", default=str(DEFAULT_SHOTS))
    ap.add_argument("--workflow", default=str(DEFAULT_WORKFLOW))
    ap.add_argument("--raw-dir", default=str(DEFAULT_RAW))
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    ap.add_argument("--env", default=DEFAULT_ENV)
    ap.add_argument("--only", default="", help="comma list of shot ids, e.g. H01,H02")
    ap.add_argument("--prefix", default="video/ep08_", help="SaveVideo filename_prefix base")
    ap.add_argument("--retries", type=int, default=1)
    ap.add_argument("--poll-timeout", type=int, default=900)
    ap.add_argument("--force", action="store_true", help="regenerate even if raw exists")
    ap.add_argument("--mode", choices=("auto", "t2v", "fl2va"), default="auto",
                    help="auto: fl2va when keyframe present else t2v")
    ap.add_argument("--seed", action="append", default=[], metavar="ID=N", help="override seed")
    ap.add_argument("--res", action="append", default=[], metavar="ID=WxH",
                    help="override resolution for a shot, e.g. H01=1280x736")
    ap.add_argument("--deadline", default="", metavar="HH:MM",
                    help="UTC hard stop for new submissions (window discipline)")
    ap.add_argument("--emit-dir", default="", metavar="DIR",
                    help="with --dry: write each built API workflow JSON here for inspection")
    ap.add_argument("--dry", action="store_true", help="build workflows only; no network")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--check", action="store_true", help="login only")
    ap.add_argument("--wait-ready", type=int, default=0, metavar="SECONDS")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    load_env(args.env)
    doc = load_json(args.shots)
    if doc is None:
        raise SystemExit(f"missing shots file: {args.shots}")
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

    plan_rows = []
    for s in shots:
        local = {w: frame_of(s, w) for w in ("first_frame", "last_frame")}
        have_first = bool(local["first_frame"] and local["first_frame"].exists())
        have_last = bool(local["last_frame"] and local["last_frame"].exists())
        if args.mode == "fl2va":
            mode = "fl2va"
        elif args.mode == "t2v":
            mode = "t2v"
        else:
            mode = "fl2va" if (have_first or have_last) else "t2v"
        uploaded = ({"first_frame": "DRY_RUN_fake-name.png"} if have_first else {})
        uploaded.update({"last_frame": "DRY_RUN_fake-name.png"} if have_last else {})
        try:
            w = build_workflow(load_json(args.workflow), s, args.prefix + s["id"],
                               mode=mode, uploaded=uploaded)
            d = describe_workflow(w)
            ok = True
            err = ""
        except Exception as e:  # noqa: BLE001
            d = {"ERROR": f"{type(e).__name__}: {e}"}
            ok, err = False, str(e)
        plan_rows.append({"id": s["id"], "mode": mode, "have_first": have_first,
                          "have_last": have_last, "first_frame": str(local["first_frame"] or ""),
                          "last_frame": str(local["last_frame"] or ""),
                          "ok": ok, "err": err, "workflow": d, "wf": w if ok else None})

    if args.list or args.dry:
        if args.emit_dir:
            outdir = Path(args.emit_dir)
            outdir.mkdir(parents=True, exist_ok=True)
            for row in plan_rows:
                if row.get("wf"):
                    save_json(outdir / f"{row['id']}_api.json", row["wf"])
            print(f"emitted {sum(1 for r in plan_rows if r.get('wf'))} workflows -> {outdir}")
        for row in plan_rows:
            d = row["workflow"]
            print(f"{row['id']}: mode={row['mode']} first={'Y' if row['have_first'] else '-'} "
                  f"last={'Y' if row['have_last'] else '-'} "
                  f"{d.get('width')}x{d.get('height')} {d.get('duration_s')}s "
                  f"seed={d.get('seed')} len_expr={d.get('length_expr')!r} "
                  f"turbo={d.get('turbo')} steps={d.get('steps')} "
                  f"save_prefix={d.get('save_prefix')} prompt={d.get('prompt_chars', 0)}ch"
                  + ("" if row["ok"] else f"  ERROR={row['err']}"))
        if args.dry or args.list:
            if not (args.stats or args.check):
                nfl = sum(1 for r in plan_rows if r["mode"] == "fl2va")
                print(f"PLAN: {len(plan_rows)} shots, fl2va={nfl}, t2v={len(plan_rows)-nfl}, "
                      f"all_built={all(r['ok'] for r in plan_rows)}")
                print("RESULT: DRY_OK" if all(r["ok"] for r in plan_rows) else "RESULT: DRY_ERROR")
                return

    log(f"env loaded {loaded} keys from {args.env}; "
        f"user={'set' if os.environ.get('H3_USER') else 'MISSING'} "
        f"base={'set' if os.environ.get('H3_BASE') else 'default'}")
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
            ok, cap = required_nodes(client)
            print(f"RESULT: STATS_OK nodes_ok={ok} fl2va={cap['fl2va_optional_inputs']}")
        except Exception as e:  # noqa: BLE001
            log(f"stats failed: {type(e).__name__}: {str(e)[:200]}")
            print("RESULT: APP_DOWN_OR_ERROR", flush=True)
            raise SystemExit(2)
        if args.stats or args.list:
            return

    wf = load_json(args.workflow)
    raw_dir = Path(args.raw_dir)
    manifest = Path(args.manifest)
    dl = deadline_epoch(args.deadline) if args.deadline else None

    # upload keyframes once (cheap) before burning GPU time
    queued = []
    for s in shots:
        up = {}
        for which in ("first_frame", "last_frame"):
            p = frame_of(s, which)
            if p and p.exists():
                up[which] = p
        if args.mode == "t2v":
            up = {}
        queued.append((s, up))
    upload_map = {}
    if any(up for _, up in queued):
        remote = preupload_keyframes(client, [s for s, _ in queued if up])
        for (sid, which), remote_name in remote.items():
            upload_map.setdefault(sid, {})[which] = remote_name
    # sanity: fail the batch early if keyframes were required and none uploaded
    if any(up for _, up in queued) and not upload_map:
        log("WARN: keyframes exist but none uploaded -> every shot will run T2V")

    results = []
    t_all = time.time()
    forced_mode = None
    fl_fail = 0
    for qi, (s, up) in enumerate(queued):
        r = run_shot(client, wf, s, raw_dir, manifest, args.retries, args.poll_timeout,
                     args.force, args.prefix, upload_map.get(s["id"], {}), dl,
                     forced_mode=forced_mode)
        results.append(r)
        log(f"progress: {json.dumps(r, ensure_ascii=False)[:400]}")
        # if FL2VA kept failing, stop paying its overhead on every shot
        kf = upload_map.get(s["id"], {})
        if kf and r.get("status") in ("ok", "failed") and r.get("mode") != "fl2va":
            fl_fail += 1
            if fl_fail >= 2 and forced_mode != "t2v":
                forced_mode = "t2v"
                log("FL2VA failed twice -> forcing T2V for remaining shots")
                try:
                    m = load_json(manifest, default=None) or {}
                    m["fl2va_downgraded"] = {"reason": "2 consecutive FL2VA job failures",
                                             "at_shot": s["id"], "utc": utcnow()}
                    save_json(manifest, m)
                except Exception:  # noqa: BLE001
                    pass
        if r["status"] == "app_down":
            log("APP DOWN mid-batch -> deferring remaining shots (retry the window later)")
            for rest, _ in queued[qi + 1:]:
                update_manifest(manifest, rest, {"id": rest["id"], "status": "deferred",
                                                 "deferred_utc": utcnow()})
                results.append({"id": rest["id"], "status": "deferred"})
            break
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
