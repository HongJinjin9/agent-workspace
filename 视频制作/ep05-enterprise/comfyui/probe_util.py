#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Video probing without a real ffprobe binary.

This box ships imageio-ffmpeg only (its /home/admin/.local/bin/ffprobe is a
symlink to the ffmpeg binary and rejects -print_format), so we probe with
`ffmpeg -i` stderr parsing plus an OpenCV cross-check for resolution/fps/frames.
"""
import json
import re
import subprocess
from pathlib import Path

_DUR_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
_VID_RE = re.compile(r"Stream #\d+:\d+.*?: Video: (\w+).*?, (\d{2,5})x(\d{2,5})")
_FPS_RE = re.compile(r", (\d+(?:\.\d+)?) fps")
_PIX_RE = re.compile(r"Video: \w+.*?, (\w+)(?:\(|,)")


def probe_video(path):
    """Return dict(width,height,fps,codec,pix_fmt,duration_s,video,audio,audio_codec,nb_frames)."""
    p = Path(path)
    res = {"path": str(p), "exist": p.exists()}
    if not p.exists():
        return res
    res["size_mb"] = round(p.stat().st_size / 1048576, 3)
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(p)],
                       capture_output=True, text=True)
    txt = r.stderr or ""
    m = _DUR_RE.search(txt)
    res["duration_s"] = None
    if m:
        h, mi, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
        res["duration_s"] = round(h * 3600 + mi * 60 + s, 3)
    vm = _VID_RE.search(txt)
    res.update({"video": bool(vm), "width": None, "height": None,
                "codec": None, "fps": None, "pix_fmt": None})
    if vm:
        res["codec"], res["width"], res["height"] = vm.group(1), int(vm.group(2)), int(vm.group(3))
        fm = _FPS_RE.search(txt[vm.start(): vm.start() + 300])
        if fm:
            res["fps"] = round(float(fm.group(1)), 3)
        elif vm.group(1) in ("gif",):
            res["fps"] = None
        pm = _PIX_RE.search(txt)
        if pm:
            res["pix_fmt"] = pm.group(1)
    am = re.search(r"Stream #\d+:\d+.*?: Audio: (\w+)", txt)
    res["audio"] = bool(am)
    res["audio_codec"] = am.group(1) if am else None
    # audio stream duration may extend format duration; keep format duration.

    # OpenCV cross-check (also gives frame count when container lacks it)
    try:
        import cv2  # local import, optional
        cap = cv2.VideoCapture(str(p))
        if cap.isOpened():
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
            fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
            n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            if w and h:
                res.setdefault("cv2_res", [w, h])
                if not res["width"]:
                    res["width"], res["height"] = w, h
            if fps:
                res["cv2_fps"] = round(fps, 3)
                if not res["fps"]:
                    res["fps"] = res["cv2_fps"]
            if n:
                res["nb_frames"] = n
            if not res["duration_s"] and fps and n:
                res["duration_s"] = round(n / fps, 3)
        cap.release()
    except Exception:  # noqa: BLE001
        pass
    return res


if __name__ == "__main__":
    import sys
    for f in sys.argv[1:]:
        print(json.dumps(probe_video(f), ensure_ascii=False, indent=1))
