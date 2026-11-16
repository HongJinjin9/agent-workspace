#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os as _os
# 4-core / 6GB cgroup: keep BLAS/torch/ffmpeg thread counts low (Lead resource rule)
for _k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    _os.environ.setdefault(_k, "2")
"""EP08 H3 capability probe (window step 2, read-only except optional upload smoke test).

Checks against the live instance:
  - required node classes present (MiniMaxH3ImageToVideo / LoadImage / ImageScale / SaveVideo …)
  - FL2VA (first/last-frame) capability: MiniMaxH3ImageToVideo optional inputs
    first_frame / last_frame present => keyframe-locked generation is possible.
    Absent => downgrade plan to T2V and record it (never fail the window on this).
  - required model files present in the loader enums (UNET / turbo LoRA / CLIP / video+audio VAE)
  - upload/image endpoint reachable (uploads a 64x36 PNG then deletes nothing; it is only
    a probe file named ep08_upload_probe.png in the instance input dir)
  - GPU / VRAM / ComfyUI version from /system_stats

Writes:
  assets/h3/node_probe_raw.json     full /object_info dump (for audit)
  assets/h3/capability.json         focused capability + model presence + decision
Prints one machine-readable line:
  RESULT: CAPABILITY fl2va=OK models=OK upload=OK   (or FALLBACK / DEGRADED)
"""
import argparse
import datetime as _dt
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "tools"))
from comfy_client import ComfyClient  # noqa: E402

A = HERE.parent / "assets" / "h3"

REQUIRED_NODES = [
    "MiniMaxH3ImageToVideo", "SaveVideo", "CreateVideo", "RandomNoise", "BasicScheduler",
    "SamplerCustomAdvanced", "KSamplerSelect", "BasicGuider", "LoraLoaderModelOnly",
    "CLIPLoader", "UNETLoader", "VAELoader", "ResolutionSelector", "ComfyMathExpression",
    "ComfySwitchNode", "PrimitiveFloat", "PrimitiveInt", "PrimitiveBoolean",
    "LoadImage", "ImageScale",
]

# names from the ep05/ep07 production runs; the instance image has stayed the same,
# but we verify against the live enum each window and fall back to the first match.
MODEL_WANT = {
    "unet": ("UNETLoader", "unet_name", "minimax_h3_fl2va_pruned_int8_convrot.safetensors"),
    "lora_turbo": ("LoraLoaderModelOnly", "lora_name",
                   "minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors"),
    "clip": ("CLIPLoader", "clip_name", "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"),
    "vae_video": ("VAELoader", "vae_name", "minimax_h3_video_vae_fp16.safetensors"),
    "vae_audio": ("VAELoader", "vae_name", "minimax_h3_audio_vae_fp32.safetensors"),
}

def make_tiny_png(w=64, h=36):
    """Valid grey PNG (16:9) built in memory — no binary asset needed for the upload probe."""
    import struct
    import zlib
    rows = b"".join(b"\x00" + bytes([112 + (y * 3) % 40]) * w for y in range(h))
    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 0, 0, 0, 0)  # 8-bit greyscale
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b""))


def now():
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def enum_choices(info, node, key):
    try:
        spec = (info.get(node) or {})["input"]["required"][key]
        if isinstance(spec, list) and spec and isinstance(spec[0], list):
            return spec[0]
    except Exception:  # noqa: BLE001
        pass
    return []


def pick_available(choices, wanted):
    """Exact name or same-family fallback; returns (name, exact?) or (None, False)."""
    if wanted in choices:
        return wanted, True
    fam = wanted.split("_")[0]
    cands = [c for c in choices if isinstance(c, str) and fam and fam in c.lower()]
    return (cands[0], False) if cands else (None, False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default="/home/admin/.h3.env")
    ap.add_argument("--no-upload-test", action="store_true")
    args = ap.parse_args()

    # env (credentials only via env; never logged)
    if Path(args.env).exists():
        for ln in Path(args.env).read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if ln.startswith("export "):
                ln = ln[len("export "):]
            if "=" in ln:
                k, _, v = ln.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

    A.mkdir(parents=True, exist_ok=True)
    c = ComfyClient(os.environ.get("H3_BASE", "https://wp08.unicorn.org.cn:24909"),
                    os.environ.get("H3_USER", ""), os.environ.get("H3_PASS", ""))
    c.login()
    st = c.system_stats()
    dev = (st.get("devices") or [{}])[0]
    info = c.object_info()
    caps = {
        "probed_utc": now(),
        "base": os.environ.get("H3_BASE", "default"),
        "comfyui_version": (st.get("system") or {}).get("comfyui_version"),
        "gpu": dev.get("name"), "vram_total": dev.get("vram_total"),
        "vram_free": dev.get("vram_free"),
        "nodes_total": len(info),
        "required_nodes_missing": [n for n in REQUIRED_NODES if n not in info],
        "fl2va": {},
        "models": {},
        "upload": {},
        "decision": {},
    }

    # ---- FL2VA capability ----
    node = info.get("MiniMaxH3ImageToVideo") or {}
    opt = (node.get("input") or {}).get("optional") or {}
    has_first = "first_frame" in opt
    has_last = "last_frame" in opt
    has_load = "LoadImage" in info
    has_scale = "ImageScale" in info
    fl_ok = has_first and has_last and has_load and has_scale
    caps["fl2va"] = {
        "node_has_first_frame": has_first,
        "node_has_last_frame": has_last,
        "load_image": has_load,
        "image_scale": has_scale,
        "supported": fl_ok,
    }

    # ---- model presence ----
    model_ok = True
    for role, (node_name, key, wanted) in MODEL_WANT.items():
        choices = enum_choices(info, node_name, key)
        name, exact = pick_available(choices, wanted)
        caps["models"][role] = {"wanted": wanted, "chosen": name, "exact": exact,
                                "available_count": len(choices)}
        if not name:
            model_ok = False

    # ---- upload endpoint smoke test ----
    if not args.no_upload_test:
        try:
            png = make_tiny_png()
            r = c.s.post(c.base + "/upload/image",
                         files={"image": ("ep08_upload_probe.png", png, "image/png")},
                         data={"overwrite": "true", "type": "input"}, timeout=60)
            caps["upload"] = {"ok": r.status_code < 400,
                              "status": r.status_code,
                              "name": (r.json().get("name") if r.status_code < 400 else None)}
        except Exception as e:  # noqa: BLE001
            caps["upload"] = {"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}
    else:
        caps["upload"] = {"ok": None, "skipped": True}

    upload_ok = caps["upload"].get("ok") is not False
    ok = not caps["required_nodes_missing"] and model_ok and upload_ok
    caps["decision"] = {
        "fl2va_mode": "fl2va" if fl_ok else "t2v",
        "degraded": (not fl_ok) or (not model_ok) or (not upload_ok),
        "degrade_reasons": [
            *([] if fl_ok else ["FL2VA optional first_frame/last_frame or LoadImage/ImageScale missing"]),
            *([] if model_ok else ["required H3 model file missing from loader enum"]),
            *([] if upload_ok else ["/upload/image endpoint rejected keyframe upload"]),
        ],
        "ready": ok,
    }

    (A / "node_probe_raw.json").write_text(json.dumps(info, ensure_ascii=False),
                                           encoding="utf-8")
    (A / "capability.json").write_text(json.dumps(caps, ensure_ascii=False, indent=1),
                                       encoding="utf-8")
    print(f"comfyui={caps['comfyui_version']} gpu={caps['gpu']} "
          f"vram_free={(dev.get('vram_free') or 0)/1e9:.1f}GB nodes={len(info)}")
    print(f"required_nodes_missing={caps['required_nodes_missing']}")
    print(f"fl2va_supported={fl_ok} upload_ok={upload_ok} models_ok={model_ok}")
    for role, v in caps["models"].items():
        print(f"  model {role}: {v['chosen']} (exact={v['exact']})")
    tag = "OK" if ok and fl_ok else ("FALLBACK" if ok else "DEGRADED")
    print(f"RESULT: CAPABILITY fl2va={'OK' if fl_ok else 'FALLBACK'} "
          f"models={'OK' if model_ok else 'MISSING'} upload={'OK' if upload_ok else 'FAIL'} "
          f"tag={tag}")
    return 0 if ok else 5


if __name__ == "__main__":
    sys.exit(main())
