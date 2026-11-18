#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os as _os
# 4-core / 6GB cgroup: keep BLAS/torch/ffmpeg thread counts low (Lead resource rule)
for _k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    _os.environ.setdefault(_k, "2")
"""EP08 local pipeline self-test (no network, no GPU): proves the post-generation chain
works before the paid window opens.

Builds a synthetic 864x480 / 5.167s / 24fps / AAC tone clip with ffmpeg, then:
  1. local_conform -> 1920x1080 (centre-crop, keeps audio)
  2. probe_util.probe_video on raw + final (resolution / fps / duration / audio)
  3. verify_clip.check on both (hard checks: duration / fps / size / frozen)
  4. frame_sheet.sheet_for output
  5. local_conform CLI --dry on the real shot list
  6. verify_clip CLI exit code on the synthetic final
Cleans up /tmp/ep08_selftest afterwards. Exit 0 = LOCAL_CHAIN_OK.
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from local_conform import local_conform  # noqa: E402
from probe_util import probe_video  # noqa: E402
import verify_clip  # noqa: E402
import frame_sheet  # noqa: E402


def sh(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        raise SystemExit(f"FAILED {' '.join(map(str, cmd))[:200]}\n{r.stderr[:800]}")
    return r


def main():
    problems = []
    tmp = Path(tempfile.mkdtemp(prefix="ep08_selftest_"))
    raw = tmp / "H99_raw.mp4"
    fin = tmp / "H99.mp4"
    frames = tmp / "frames"
    sheets = tmp / "sheets"
    try:
        print("[selftest] building synthetic H3-like raw (864x480/24fps/5.167s/AAC)…")
        sh(["ffmpeg", "-v", "error", "-y", "-threads", "2", "-filter_threads", "2",
            "-f", "lavfi", "-i", "testsrc2=size=864x480:rate=24:duration=5.167",
            "-f", "lavfi", "-i", "sine=frequency=220:sample_rate=32000:duration=5.167",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
            "-threads", "2",
            "-c:a", "aac", "-b:a", "128k", "-shortest", str(raw)])
        print(f"[selftest] raw: {raw.stat().st_size/1048576:.2f} MB")
        ok, method = local_conform(raw, fin, 1920, 1080)
        if not ok:
            problems.append(f"local_conform failed: {method}")
        else:
            print(f"[selftest] conform OK: {method}")
        for label, p in (("raw", raw), ("final", fin)):
            info = probe_video(p)
            print(f"[selftest] {label}: {info.get('width')}x{info.get('height')} "
                  f"{info.get('fps')}fps {info.get('duration_s')}s "
                  f"audio={info.get('audio')} ({info.get('audio_codec')})")
            if label == "final":
                if (info.get("width"), info.get("height")) != (1920, 1080):
                    problems.append(f"final res {info.get('width')}x{info.get('height')} != 1920x1080")
                if not info.get("audio"):
                    problems.append("final lost audio stream")
            if not (4.5 <= (info.get("duration_s") or 0) <= 6.0):
                problems.append(f"{label} duration {info.get('duration_s')} outside 5s window")
            if not (20 <= (info.get("fps") or 0) <= 30):
                problems.append(f"{label} fps {info.get('fps')} outside [20,30]")
        # verify_clip hard checks (reuse the production checker)
        frames.mkdir(exist_ok=True)
        vraw = verify_clip.check(raw, frames)
        vfin = verify_clip.check(fin, frames, 1920, 1080)
        print(f"[selftest] verify raw pass={vraw['pass']} problems={vraw['problems']}")
        print(f"[selftest] verify final pass={vfin['pass']} problems={vfin['problems']} "
              f"motion={vfin['motion'].get('mean_consec_diff')}")
        if not vraw["pass"]:
            problems.append(f"verify raw failed: {vraw['problems']}")
        if not vfin["pass"]:
            problems.append(f"verify final failed: {vfin['problems']}")
        sheets.mkdir(parents=True, exist_ok=True)
        sheet = frame_sheet.sheet_for("H99", frames, sheets)
        if not sheet:
            problems.append("frame_sheet failed")
        else:
            print(f"[selftest] frame sheet OK: {sheet.name}")
        # CLI smoke: local_conform --dry against real shot list
        shots = HERE / "shots-ep08-run.json"
        if shots.exists():
            r = subprocess.run([sys.executable, str(HERE / "local_conform.py"), "--dry"],
                               capture_output=True, text=True, cwd=str(HERE))
            print(f"[selftest] local_conform --dry rc={r.returncode} "
                  f"({r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ''})")
            if r.returncode != 0:
                problems.append("local_conform --dry failed")
        # verify_clip CLI exit code smoke
        r = subprocess.run([sys.executable, str(HERE / "verify_clip.py"), str(fin),
                            "--frames-dir", str(frames), "--expect", "1920x1080"],
                           capture_output=True, text=True, cwd=str(HERE))
        print(f"[selftest] verify_clip CLI rc={r.returncode}")
        if r.returncode != 0:
            problems.append(f"verify_clip CLI failed: {r.stdout[-400:]}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    for p in problems:
        print(f"FAIL  {p}")
    print(f"[selftest] problems={len(problems)}")
    print("RESULT: LOCAL_CHAIN_OK" if not problems else "RESULT: LOCAL_CHAIN_FAIL")
    raise SystemExit(0 if not problems else 1)


if __name__ == "__main__":
    main()
