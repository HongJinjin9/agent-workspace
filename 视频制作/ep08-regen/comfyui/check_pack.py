#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os as _os
# 4-core / 6GB cgroup: keep BLAS/torch/ffmpeg thread counts low (Lead resource rule)
for _k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    _os.environ.setdefault(_k, "2")
"""EP08 H3 handoff-pack static check (no network). Run before the GPU window and again
right after engine-dev delivers keyframes/shots.

Validates:
  1. workflow templates: node ids/classes, variable nodes (prompt/width/height/length/
     duration/seed/turbo switch/SaveVideo), link integrity, both VAEs, FL2VA hooks
  2. shots-ep08-run.json: schema, id uniqueness, 32-px multiples, 16:9, duration window,
     prompt PDF §4 rules (phased timeline, single camera move, explicit sound, fixed
     prohibitions at the end, ≤15s)
  3. keyframes: exist, decode as PNG, 16:9, not smaller than the generation size, not blank
  4. engine contract shots-ep08.json vs run orders (id/res/duration/seed drift)
  5. local toolchain: ffmpeg + filters, python deps
  6. runtime estimate for the 1-hour billing window

Exit 0 = PACK_OK (warnings allowed), 1 = PACK_FAIL, --strict also fails on warnings.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
A = ROOT / "assets" / "h3"
DEFAULT_RUN = HERE / "shots-ep08-run.json"
DEFAULT_ENGINE = HERE / "shots-ep08.json"

WF_T2V = HERE / "workflows" / "t2v_api.json"
WF_FL2VA = HERE / "workflows" / "fl2va_api.json"

REQUIRED_WF = {
    "140:131": "MiniMaxH3ImageToVideo",
    "140:132": "ComfyMathExpression",
    "140:133": "PrimitiveFloat",
    "140:129": "RandomNoise",
    "140:139": "PrimitiveBoolean",
    "140:127": "UNETLoader",
    "140:128": "CLIPLoader",
    "140:119": "VAELoader",
    "140:120": "VAELoader",
    "140:138": "PrimitiveInt",
    "140:130": "CreateVideo",
    "92": "SaveVideo",
    "115": "ResolutionSelector",
}
EXPECTED_MODELS = {
    "140:127": ("unet_name", "minimax_h3_fl2va"),
    "140:128": ("clip_name", "qwen3vl_32b_minimax_h3"),
    "140:139": ("value", None),  # boolean switch, checked by type
}
PROHIBIT = ("no readable text", "no text", "no logos", "no logo", "no watermark",
            "no face", "no faces", "no human", "no people")
SOUND_HINT = ("sound", "audio", "soundscape", "ambience", "ambient")
CAMERA_HINT = ("camera", "lens", "push", "dolly", "pan", "tilt", "track", "static",
               "locked", "orbit", "crane", "handheld", "shot")


def load_json(p, default=None):
    p = Path(p)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        raise SystemExit(f"invalid JSON {p}: {e}")


def check_workflow(path, problems, warnings):
    name = path.name
    if not path.exists():
        problems.append(f"workflow missing: {name}")
        return None
    wf = load_json(path)
    # API format: flat {node_id: {class_type, inputs}}
    if not isinstance(wf, dict) or any("class_type" not in v for v in wf.values()):
        problems.append(f"{name}: not an API-format workflow (flat class_type dict)")
        return None
    for nid, cls in REQUIRED_WF.items():
        got = (wf.get(nid) or {}).get("class_type")
        if got != cls:
            problems.append(f"{name}: node {nid} expected {cls}, got {got}")
    if "first_frame" not in (wf["140:131"]["inputs"] if "140:131" in wf else {}):
        warnings.append(f"{name}: no first_frame hook (T2V-only template)")
    # link integrity
    for nid, node in wf.items():
        for k, v in (node.get("inputs") or {}).items():
            if isinstance(v, list) and len(v) == 2 and isinstance(v[0], str) and v[0] in wf:
                continue
            if isinstance(v, list) and len(v) == 2 and isinstance(v[0], str) and v[0] not in wf:
                # may be an unexpanded subgraph reference; flag as warning not problem
                warnings.append(f"{name}: node {nid}.{k} links to unknown node {v[0]}")
    # SaveVideo <- CreateVideo
    sv = (wf.get("92") or {}).get("inputs") or {}
    vid = sv.get("video")
    if not (isinstance(vid, list) and wf.get(str(vid[0]), {}).get("class_type") == "CreateVideo"):
        problems.append(f"{name}: SaveVideo.video is not linked to CreateVideo (got {vid})")
    # both VAEs
    vaes = [(wf.get("140:119") or {}).get("inputs", {}).get("vae_name", ""),
            (wf.get("140:120") or {}).get("inputs", {}).get("vae_name", "")]
    if not (any("video_vae" in v for v in vaes) and any("audio_vae" in v for v in vaes)):
        problems.append(f"{name}: video+audio VAE not both loaded ({vaes})")
    # models
    for nid, (key, frag) in EXPECTED_MODELS.items():
        val = ((wf.get(nid) or {}).get("inputs") or {}).get(key)
        if frag and not (isinstance(val, str) and frag in val):
            problems.append(f"{name}: node {nid}.{key}={val!r} does not contain {frag!r}")
    if (wf.get("140:139") or {}).get("inputs", {}).get("value") is not False:
        warnings.append(f"{name}: turbo LoRA switch 140:139 is not False in the template")
    if (wf.get("140:138") or {}).get("inputs", {}).get("value") != 8:
        problems.append(f"{name}: turbo step node 140:138 != 8")
    return wf


def check_prompt(sid, prompt, problems, warnings):
    p = prompt.strip()
    if len(p) < 120:
        problems.append(f"{sid}: prompt too short ({len(p)}ch, need >=120)")
    if len(p) > 3000:
        warnings.append(f"{sid}: prompt long ({len(p)}ch) — may dilute motion control")
    if re.search(r"[\u4e00-\u9fff]", p):
        warnings.append(f"{sid}: prompt contains CJK — English is measurably more stable on H3")
    # 1) phased timeline
    phases = re.findall(r"\[\s*\d+(?:\.\d+)?\s*-\s*\d+(?:\.\d+)?\s*s\s*\]", p)
    if not phases:
        problems.append(f"{sid}: no phased timeline like [0-2s]/[2-5s] (PDF §4.1)")
    # 2) one camera move
    # drop negated phrases ("no pan", "no zoom") before counting distinct moves
    cam_text = re.sub(r"\bno [a-z-]+(?:[ -][a-z-]+)?", " ", p.lower())
    cam = len(set(re.findall(
        r"\b(dolly|pan|tilt|track|tracking|orbit|orbital|crane|push[ -]in|pull[ -]out|"
        r"handheld|locked[ -]off)\b", cam_text)))
    if cam > 1:
        warnings.append(f"{sid}: {cam} camera-move terms — PDF §4.2 says one move per shot")
    # 3) explicit sound
    if not any(k in p.lower() for k in SOUND_HINT):
        problems.append(f"{sid}: no explicit sound description (PDF §4.3)")
    # 4) fixed prohibition tail
    tail = p[-400:].lower()
    if not any(k in tail for k in PROHIBIT):
        problems.append(f"{sid}: no fixed 'no text/logo/face' prohibitions at the end (PDF §4.4)")
    if "logo" not in p.lower():
        warnings.append(f"{sid}: add 'no logos' explicitly")
    # 5) duration handled by caller


def check_keyframes(shot, problems, warnings, keyframe_stats):
    sid = shot["id"]
    for which in ("first_frame", "last_frame"):
        rel = shot.get(which)
        if not rel:
            continue
        p = Path(rel)
        if not p.is_absolute():
            p = HERE / rel if (HERE / rel).exists() else ROOT / rel
        if not p.exists():
            problems.append(f"{sid}: {which} file missing: {rel}")
            continue
        try:
            from PIL import Image
            im = Image.open(p)
            im.load()
            w, h = im.size
            ex = im.convert("L").getextrema()
            keyframe_stats.append({"id": sid, "which": which, "file": str(p),
                                   "size": [w, h], "mode": im.mode,
                                   "blank": bool(ex[1] - ex[0] < 4)})
            if w % 32 or h % 32:
                warnings.append(f"{sid}: {which} {w}x{h} not /32 (will be lanczos-scaled at runtime)")
            dev_rel = abs(w / h - 16 / 9) / (16 / 9)
            if dev_rel > 0.03:
                problems.append(f"{sid}: {which} aspect {w}x{h} too far from 16:9 "
                                f"({dev_rel*100:.2f}%)")
            elif dev_rel > 0.008 and (w, h) not in ((864, 480), (1280, 736)):
                warnings.append(f"{sid}: {which} aspect {w}x{h} is "
                                f"{dev_rel*100:.2f}% off 16:9 "
                                f"(centre-cropped at conform, no stretch)")
            if w < shot["width"] or h < shot["height"]:
                warnings.append(f"{sid}: {which} {w}x{h} smaller than gen "
                                f"{shot['width']}x{shot['height']} (upscaled at runtime)")
            if ex[1] - ex[0] < 4:
                problems.append(f"{sid}: {which} looks blank (contrast {ex[0]}..{ex[1]})")
        except Exception as e:  # noqa: BLE001
            problems.append(f"{sid}: {which} unreadable PNG {p}: {type(e).__name__}: {e}")


def estimate_runtime(shots, keyframe_mode_ok):
    """Rough GPU-seconds from ep05/ep07 measured data (864x480/5s warm ~38-62s)."""
    total = 0.0
    rows = []
    first = True
    for s in shots:
        px = s["width"] * s["height"]
        base = 55.0 if keyframe_mode_ok else 50.0     # warm, 8-step turbo
        if px > 700_000:                              # hero 1280x736
            base = 170.0
        elif px > 500_000:                            # 960x544
            base = 95.0
        dur_factor = max(0.8, s["duration"] / 5.0)    # measured ~2.9x for 2x duration
        est = base * (dur_factor ** 1.2)
        if first:
            est += 45.0                               # cold start model load
            first = False
        total += est
        rows.append({"id": s["id"], "est_s": round(est, 1)})
    return round(total, 1), rows


def check_engine_contract(engine, run_path, problems, warnings):
    if not Path(engine).exists():
        warnings.append(f"engine contract not delivered yet: {Path(engine).name}")
        return
    eng = load_json(engine)
    run = load_json(run_path) if Path(run_path).exists() else None
    if run is None:
        return
    e_idx = {s["id"]: s for s in eng.get("shots", [])}
    r_idx = {s["id"]: s for s in run.get("shots", [])}
    missing = [i for i in e_idx if i not in r_idx]
    if missing:
        problems.append(f"run orders missing engine shots: {missing}")
    for sid, e in e_idx.items():
        r = r_idx.get(sid)
        if not r:
            continue
        hero_down = (r.get("hero") and r.get("hero_target_res") == [e.get("width"),
                                                                     e.get("height")])
        for k in ("width", "height", "duration"):
            if r.get(k) != e.get(k) and not (hero_down and k in ("width", "height")):
                warnings.append(f"{sid}: run {k}={r.get(k)} differs from engine {e.get(k)}")
        if hero_down:
            warnings.append(f"{sid}: hero primary pass at 864x480, "
                            f"upgrade target {e.get('width')}x{e.get('height')} recorded")
        seed_note = "ok" if r.get("seed") == e.get("seed") else "overridden"
        if seed_note != "ok":
            warnings.append(f"{sid}: seed overridden {e.get('seed')} -> {r.get('seed')}")


def check_toolchain(problems, warnings):
    for exe in ("ffmpeg", "ffprobe"):
        if not shutil.which(exe):
            warnings.append(f"{exe} not in PATH (probe_util falls back, video probe may be weak)")
    try:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True)
        for filt in ("scale", "unsharp", "hstack"):
            if filt not in (r.stdout or ""):
                warnings.append(f"ffmpeg filter missing: {filt}")
    except Exception as e:  # noqa: BLE001
        warnings.append(f"ffmpeg unavailable: {e}")
    for mod in ("requests", "numpy", "PIL"):
        try:
            __import__(mod)
        except Exception as e:  # noqa: BLE001
            problems.append(f"python module {mod} missing: {e}")
    try:
        __import__("cv2")
    except Exception:  # noqa: BLE001
        warnings.append("cv2 missing — probe falls back to ffmpeg -i parsing")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=str(DEFAULT_RUN))
    ap.add_argument("--engine", default=str(DEFAULT_ENGINE))
    ap.add_argument("--strict", action="store_true", help="warnings also fail")
    args = ap.parse_args()

    problems, warnings, keyframe_stats = [], [], []
    result = {"checked_utc": __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc).isoformat(timespec="seconds")}

    wf_t2v = check_workflow(WF_T2V, problems, warnings)
    wf_fl = check_workflow(WF_FL2VA, problems, warnings) if WF_FL2VA.exists() else None
    if wf_fl:
        for hook in ("first_frame", "last_frame"):
            if hook not in wf_fl["140:131"]["inputs"]:
                problems.append(f"fl2va_api.json: missing {hook} hook on 140:131")
    result["workflows"] = {
        "t2v": {"path": str(WF_T2V), "nodes": len(wf_t2v or {})},
        "fl2va": {"path": str(WF_FL2VA), "nodes": len(wf_fl or {})},
    }

    run = load_json(args.run, default=None)
    shots = []
    if run is None:
        warnings.append(f"run orders not built yet: {Path(args.run).name}")
    else:
        if not run.get("shots"):
            problems.append("run orders: no shots")
        shots = run.get("shots", [])
        ids = [s.get("id") for s in shots]
        if len(ids) != len(set(ids)):
            problems.append(f"run orders: duplicate ids {ids}")
        for s in shots:
            sid = s.get("id", "?")
            for k in ("id", "width", "height", "duration", "seed", "prompt"):
                if s.get(k) in (None, ""):
                    problems.append(f"{sid}: missing required field {k}")
            if s.get("width", 0) % 32 or s.get("height", 0) % 32:
                problems.append(f"{sid}: resolution {s.get('width')}x{s.get('height')} not /32")
            dev_rel = abs(s.get("width", 1) / s.get("height", 1) - 16 / 9) / (16 / 9)
            if dev_rel > 0.03:
                problems.append(f"{sid}: aspect not ~16:9 ({dev_rel*100:.2f}% off)")
            d = float(s.get("duration") or 0)
            if d > 15:
                problems.append(f"{sid}: duration {d}s > 15s (must split, PDF §4.5)")
            if not (4.0 <= d <= 5.5):
                warnings.append(f"{sid}: duration {d}s outside planned 5s window")
            if s.get("prompt"):
                check_prompt(sid, s["prompt"], problems, warnings)
            check_keyframes(s, problems, warnings, keyframe_stats)
        result["shots"] = {"count": len(shots),
                           "fl2va_capable": sum(1 for s in shots if s.get("first_frame")),
                           "hero": sum(1 for s in shots if s.get("hero")),
                           "total_prompt_chars": sum(len(s.get("prompt", "")) for s in shots)}

    if shots:
        n_fl = sum(1 for s in shots if s.get("first_frame"))
        est_s, est_rows = estimate_runtime(shots, n_fl == len(shots))
        result["estimate"] = {"generation_s": est_s, "generation_min": round(est_s / 60, 1),
                              "per_shot": est_rows,
                              "budget_min": 35,
                              "verdict": "OK" if est_s / 60 <= 32 else "TIGHT"}
        if est_s / 60 > 35:
            warnings.append(f"runtime estimate {est_s/60:.1f} min exceeds 35 min budget")

    check_engine_contract(args.engine, args.run, problems, warnings)
    check_toolchain(problems, warnings)

    result.update({"problems": problems, "warnings": warnings,
                   "keyframes": keyframe_stats,
                   "verdict": "PACK_FAIL" if problems else
                              ("PACK_WARN" if (warnings and args.strict) else "PACK_OK")})
    A.mkdir(parents=True, exist_ok=True)
    (A / "pack-check.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n",
                                       encoding="utf-8")

    for w in warnings:
        print(f"WARN  {w}")
    for p in problems:
        print(f"FAIL  {p}")
    if result.get("estimate"):
        e = result["estimate"]
        print(f"estimate: {e['generation_min']} min generation for {len(shots)} shots "
              f"(budget {e['budget_min']} min, {e['verdict']})")
    if result.get("shots"):
        s = result["shots"]
        print(f"shots: {s['count']} (fl2va-capable {s['fl2va_capable']}, hero {s['hero']}, "
              f"prompt chars {s['total_prompt_chars']})")
    print(f"keyframes checked: {len(keyframe_stats)}")
    print(f"problems={len(problems)} warnings={len(warnings)}")
    print(f"RESULT: {result['verdict']}")
    raise SystemExit(0 if not problems and not (args.strict and warnings) else 1)


if __name__ == "__main__":
    main()
