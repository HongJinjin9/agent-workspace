#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate workflows/fl2va_api.json (first/last-frame reference template) from t2v_api.json.

The batch runner injects the LoadImage/ImageScale helper nodes per shot at runtime
(see batch_run.py build_workflow(mode="fl2va")), so this file is the *expanded reference*
of that same structure: open it to inspect the exact graph, or import it in the ComfyUI UI
and manually pick keyframes. Image names are PLACEHOLDERs — it is not meant to be submitted
as-is.

  python3 build_fl2va_template.py
"""
import copy
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
WF = HERE / "workflows" / "t2v_api.json"
OUT = HERE / "workflows" / "fl2va_api.json"

N_PROMPT = "140:131"
N_LOAD_FIRST, N_SCALE_FIRST = "900", "901"
N_LOAD_LAST, N_SCALE_LAST = "910", "911"


def main():
    wf = json.loads(WF.read_text(encoding="utf-8"))
    w = copy.deepcopy(wf)
    inp = w[N_PROMPT]["inputs"]

    # keep the ResolutionSelector graph untouched (it is bypassed by literal ints at runtime)
    width = "115"  # placeholder link preserved for UI; the runner injects literal pixels
    w[N_LOAD_FIRST] = {"class_type": "LoadImage",
                       "inputs": {"image": "PLACEHOLDER_first_frame.png"},
                       "_meta": {"title": "first frame (upload via /upload/image)"}}
    w[N_SCALE_FIRST] = {"class_type": "ImageScale",
                        "inputs": {"image": [N_LOAD_FIRST, 0], "upscale_method": "lanczos",
                                   "width": [width, 0], "height": [width, 1],
                                   "crop": "disabled"},
                        "_meta": {"title": "scale first frame to generation pixels"}}
    w[N_PROMPT]["inputs"]["first_frame"] = [N_SCALE_FIRST, 0]

    w[N_LOAD_LAST] = {"class_type": "LoadImage",
                      "inputs": {"image": "PLACEHOLDER_last_frame.png"},
                      "_meta": {"title": "last frame (optional)"}}
    w[N_SCALE_LAST] = {"class_type": "ImageScale",
                       "inputs": {"image": [N_LOAD_LAST, 0], "upscale_method": "lanczos",
                                  "width": [width, 0], "height": [width, 1],
                                  "crop": "disabled"},
                       "_meta": {"title": "scale last frame to generation pixels"}}
    w[N_PROMPT]["inputs"]["last_frame"] = [N_SCALE_LAST, 0]

    # flat API-format dict, same shape as t2v_api.json (ready for /prompt once image
    # names are real; batch_run.py builds the per-shot version dynamically)
    OUT.write_text(json.dumps(w, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({len(w)} nodes); placeholders: "
          f"{w[N_LOAD_FIRST]['inputs']['image']}, {w[N_LOAD_LAST]['inputs']['image']}")


if __name__ == "__main__":
    main()
