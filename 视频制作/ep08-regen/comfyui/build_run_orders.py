#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build EP08 executable H3 run orders.

Source of truth for CONTENT is the frozen scene-design H3 list (SCENE-DESIGN.md §5),
carried in prompt-overrides-ep08.json keyed by shot id Sxx (S01…S66 + spare H24).
engine-dev's shots-ep08.json supplies H-numbering, timing anchors (md), seeds and the
keyframe paths; a keyframe is mounted only when its filename matches the Sxx it belongs
to (content match), otherwise that shot runs T2V (`first_frame: null`).

Outputs:
  shots-ep08-run.json   what batch_run.py consumes
  prompts-ep08.md       human-readable prompt sheet
Then runs check_pack.py (static gate).

  python3 build_run_orders.py
  python3 build_run_orders.py --check-only
"""
import argparse
import datetime as _dt
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ENGINE = HERE / "shots-ep08.json"
OVERRIDES = HERE / "prompt-overrides-ep08.json"
RUN = HERE / "shots-ep08-run.json"
A = ROOT / "assets" / "h3"
KF = HERE / "keyframes"

# scene-design H↔Sxx mapping (fallback when engine has not renumbered yet)
DEFAULT_MAP = [("H01", "S01"), ("H02", "S02"), ("H03", "S05"), ("H04", "S07"),
               ("H05", "S10"), ("H06", "S20"), ("H07", "S25"), ("H08", "S30"),
               ("H09", "S35"), ("H10", "S39"), ("H11", "S40"), ("H12", "S44"),
               ("H13", "S48"), ("H14", "S49"), ("H15", "S50"), ("H16", "S53"),
               ("H17", "S55"), ("H18", "S56"), ("H19", "S57"), ("H20", "S58"),
               ("H21", "S59"), ("H22", "S60"), ("H23", "S66"), ("H24", "SPARE")]


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


def norm_shot_key(sid):
    """Map engine shot to scene key: 'S01'..'S66' or 'H24' for the spare; None otherwise."""
    t = str(sid or "")
    m = re.search(r"\bS(\d{2})\b", t)
    if m:
        return f"S{m.group(1)}"
    if re.search(r"\b(SPARE|H24|backup)\b", t, re.I):
        return "H24"
    return None


def engine_index(eng):
    """Return {'S01': shot, ..., 'H24': spare_shot} from engine json (may be partial/old)."""
    idx = {}
    for sh in (eng or {}).get("shots", []):
        keys = [sh.get("shot"), sh.get("md"), sh.get("id"), sh.get("seg")]
        for k in keys:
            kk = norm_shot_key(k)
            if kk and kk not in idx:
                idx[kk] = sh
                break
        kk = norm_shot_key(sh.get("id"))
        if kk:
            idx.setdefault(kk, sh)
    return idx


_LOADED_BLOCKLIST = {}


def _load_blocklist():
    p = HERE / "keyframe-blocklist.json"
    try:
        return (json.loads(p.read_text(encoding="utf-8")) or {}).get("blocked", {})
    except Exception:  # noqa: BLE001
        return {}


def _blocked(sxx, path, blocklist):
    """A keyframe audited as content-mismatched is skipped until the file is replaced."""
    import hashlib
    rec = blocklist.get(sxx) or {}
    if not rec or not path:
        return False
    try:
        h = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return False
    return h == rec.get("sha256")


def find_keyframe(sxx, sh, which="first"):
    """Mount a keyframe only when its filename matches this shot's Sxx (content match)."""
    suffix = f"_{which}"
    spare = (sxx == "H24")

    def name_matches(name):
        return re.search(r"\b(SPARE|H24|backup)\b", name, re.I) if spare \
            else (sxx in name)

    # 1) engine-declared path, trusted only if its filename names this same shot
    if sh and sh.get(f"{which}_frame"):
        c = Path(sh[f"{which}_frame"])
        c = c if c.is_absolute() else (ROOT / c if (ROOT / c).exists() else HERE / c)
        if c.exists() and name_matches(c.name):
            if _blocked(sxx, c, _LOADED_BLOCKLIST):
                return None
            return c
    # 2) canonical keyframes/<Sxx>_first.png (or SPARE/H24/backup for the spare)
    names = ([f"SPARE{suffix}.png", f"H24{suffix}.png", f"backup{suffix}.png"]
             if spare else [f"{sxx}{suffix}.png"])
    found = None
    for n in names:
        c = KF / n
        if c.exists():
            found = c
            break
    if found is not None and _blocked(sxx, found, _LOADED_BLOCKLIST):
        return None
    return found


def adapt_prompt_for_t2v(prompt):
    """When a shot has no keyframe, drop FL2VA-only phrasing so the T2V prompt is coherent."""
    import re as _re
    out = _re.sub(r"Animate from the locked first frame;.*?unchanged\.\s*", "", prompt)
    out = out.replace(
        "Animate from the locked first frame; keep its composition, camera height, lighting and "
        "colour grade unchanged. ", "")
    out = out.replace(
        "Animate from the locked first frame; keep its framing, camera height and colour grade "
        "unchanged. ", "")
    out = out.replace(
        "Animate from the locked first frame; keep its framing and colour grade unchanged. ", "")
    out = out.replace(
        "Animate from the locked first frame; keep its composition and colour grade unchanged. ", "")
    out = out.replace(
        "Animate from the locked first frame; keep its composition, camera height and framing "
        "unchanged, and pull the colour toward a cold grey dusk grade. ",
        "Pull the colour toward a cold grey dusk grade. ")
    out = out.replace(
        "Keep the first frame's structure and colour palette unchanged.", 
        "Keep a consistent cold-grey palette and composition throughout.")
    out = out.replace(
        "Keep the first frame's structure and colour palette unchanged;",
        "Keep a consistent cold-grey palette and composition throughout;")
    out = out.replace(
        "Keep the first frame's structure and colour palette unchanged. ",
        "Keep a consistent cold-grey palette and composition throughout. ")
    return out


def rel_comfy(p):
    try:
        return str(Path(p).relative_to(HERE))
    except ValueError:
        try:
            return str(Path(p).relative_to(ROOT))
        except ValueError:
            return str(p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default=str(ENGINE))
    ap.add_argument("--overrides", default=str(OVERRIDES))
    ap.add_argument("--out", default=str(RUN))
    ap.add_argument("--prompts-out", default=str(HERE / "prompts-ep08.md"))
    ap.add_argument("--check-only", action="store_true")
    args = ap.parse_args()

    global _LOADED_BLOCKLIST
    _LOADED_BLOCKLIST = _load_blocklist()
    ov_doc = load_json(args.overrides)
    if ov_doc is None:
        raise SystemExit(f"missing prompt overrides {args.overrides}")
    ov = ov_doc.get("shots", ov_doc)
    pol = load_json(HERE / "run-policy.json", default={}) or {}
    exclude = {str(x) for x in pol.get("exclude", [])}
    force_t2v = {str(x) for x in pol.get("force_t2v", [])}
    eng = load_json(args.engine, default=None) or {}
    eidx = engine_index(eng)
    defaults = {"width": 864, "height": 480, "duration": 5.0, "steps": 8, "fps": 24,
                "enable_lightning_lora": True}
    defaults.update(eng.get("defaults") or {})

    shots, notes = [], []
    n = -1
    for key, o in ov.items():
        sxx = key
        if sxx in exclude:
            notes.append(f"{sxx}: excluded from H3 generation by Lead ruling (pure code shot)")
            continue
        n += 1
        sh = eidx.get(sxx) or {}
        sid = sh.get("id") or sh.get("shot") or f"H{n+1:02d}"
        if str(sh.get("mode", "")).upper() in ("T2V", "CODE") or sxx in force_t2v:
            first, last = None, None  # engine QA / Lead ruling: no usable keyframe
        else:
            first = find_keyframe(sxx, sh, "first")
            last = find_keyframe(sxx, sh, "last")
        if first is None:
            notes.append(f"{sid}({sxx}): no matching keyframe -> T2V")
        if sh and sh.get("first_frame") and first is None:
            if sxx in force_t2v:
                notes.append(f"{sid}({sxx}): forced T2V by Lead ruling "
                             f"(engine first_frame {sh.get('first_frame')} unused)")
            else:
                notes.append(f"{sid}({sxx}): engine first_frame {sh.get('first_frame')} "
                             f"does not match content -> ignored")
        width = int(o.get("width", defaults["width"]))
        height = int(o.get("height", defaults["height"]))
        prompt = o["prompt"] if first else adapt_prompt_for_t2v(o["prompt"])
        shots.append({
            "id": sid,
            "shot": sxx if sxx != "H24" else "SPARE",
            "seg": sh.get("seg") or sxx.split("S")[0] or "",
            "title": o.get("title") or sh.get("title") or sid,
            "md": sh.get("md") or sxx,
            "width": width, "height": height,
            "duration": float(o.get("duration", defaults["duration"])),
            "seed": int(sh.get("seed") or (202611160101 + n)),
            "prompt": prompt,
            "first_frame": rel_comfy(first) if first else None,
            "last_frame": rel_comfy(last) if last else None,
            "hero": bool(o.get("hero", sh.get("hero", False))),
            "hero_target_res": o.get("hero_target_res"),
            "fallback": sh.get("fallback", "code"),
            "enable_lightning_lora": bool(defaults.get("enable_lightning_lora", True)),
        })
    if len(shots) not in (23, 24):
        notes.append(f"WARNING: expected 23-24 H3 shots, built {len(shots)}")

    run = {
        "series": "ep08-regen",
        "created_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "content_source": "视频制作/ep08-scene-design/SCENE-DESIGN.md §5 (frozen H3 list, by Sxx)",
        "engine_work_order": Path(args.engine).name,
        "workflow": "workflows/t2v_api.json",
        "defaults": defaults,
        "style": eng.get("style", ""),
        "notes": notes,
        "shots": shots,
    }
    fl = sum(1 for s in shots if s["first_frame"])
    if args.check_only:
        print(f"would write {len(shots)} shots ({fl} FL2VA / {len(shots)-fl} T2V, "
              f"{sum(1 for s in shots if s['hero'])} hero candidates)")
        for n in notes:
            print(f"NOTE  {n}")
        return

    save_json(args.out, run)
    print(f"wrote {args.out}: {len(shots)} shots, {fl} FL2VA, {len(shots)-fl} T2V, "
          f"{sum(1 for s in shots if s['hero'])} hero candidates")
    for n in notes:
        print(f"NOTE  {n}")
    rc = subprocess.run([sys.executable, str(HERE / "make_prompts_ep08.py"),
                         "--shots", str(args.out),
                         "--out", str(args.prompts_out)]).returncode
    if rc != 0:
        raise SystemExit("make_prompts_ep08.py failed")
    rc = subprocess.run([sys.executable, str(HERE / "check_pack.py"),
                         "--run", str(args.out)]).returncode
    raise SystemExit(rc)


if __name__ == "__main__":
    main()
