#!/bin/bash
# EP08 red-line / quality fix pass: regenerate 6 shots, reconform, re-verify, re-report.
# Detached because the harness reaps background jobs at turn boundaries.
set -u
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 NUMEXPR_NUM_THREADS=2
cd /app/vedio/ep08-regen/comfyui || exit 1
set -a
. /home/admin/.h3.env
set +a
A=/app/vedio/ep08-regen/assets/h3
FR=$A/frames
IDS="${IDS:-H06,H08,H14,H18,H19,H22}"
FIX=shots-ep08-fix.json
ts() { date -u +%FT%TZ; }
say() { echo "[$(ts)] $*"; }

say "FIX start ids=$IDS"
python3 batch_run.py --shots "$FIX" --only "$IDS" --force --retries 1 --deadline 00:10
say "fix_gen_exit=$?"
say "STEP conform"
python3 local_conform.py --shots "$FIX" --only "$IDS" --force
say "fix_conform_exit=$?"
say "STEP verify all"
python3 verify_clip.py "$A"/raw/H*_raw.mp4 --frames-dir "$FR" > "$A/verify-raw.json" 2>/dev/null
python3 verify_clip.py "$A"/H??.mp4 --frames-dir "$FR" --expect 1920x1080 > "$A/verify-final.json" 2>/dev/null
python3 frame_sheet.py --frames-dir "$FR" --out-dir "$FR/sheets" >/dev/null 2>&1 || true
python3 keyframe_adherence.py || true
say "STEP report"
python3 make_report_ep08.py
say "FIX_DONE $(ts)"
ls -la "$A"/H06.mp4 "$A"/H08.mp4 "$A"/H14.mp4 "$A"/H18.mp4 "$A"/H19.mp4 "$A"/H22.mp4 2>/dev/null | awk '{print $6, $7, $8, $9}'
echo "RESULT: FIX_DONE"
