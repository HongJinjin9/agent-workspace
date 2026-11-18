#!/bin/bash
# EP08 H3 window RESUME (session-detached): continue from H07 after the first run was reaped.
# Runs remaining shots only (those without raw), keeps existing raws/conforms, then
# fill-missing 1080p -> verify -> adherence -> report. Writes comfyui/resume.log.
set -u
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 NUMEXPR_NUM_THREADS=2
export VECLIB_MAXIMUM_THREADS=2
cd /app/vedio/ep08-regen/comfyui || exit 1
set -a
. /home/admin/.h3.env
set +a
A=/app/vedio/ep08-regen/assets/h3
FR=$A/frames
SHOTS=shots-ep08-run.json
DEADLINE="${DEADLINE:-23:58}"
mkdir -p "$A/raw" "$FR"
ts() { date -u +%FT%TZ; }
say() { echo "[$(ts)] $*"; }

say "RESUME start deadline=$DEADLINE"
[ -f "$SHOTS" ] || { say "FATAL: $SHOTS missing"; exit 1; }

IDS=$(python3 - <<'PY'
import json
from pathlib import Path
run = json.load(open('shots-ep08-run.json'))
raw = Path('/app/vedio/ep08-regen/assets/h3/raw')
ids = [s['id'] for s in run['shots'] if not list(raw.glob(f"{s['id']}_raw.*"))]
print(','.join(ids))
PY
)
if [ -z "$IDS" ]; then
  say "all raws already present -> skip generation"
else
  say "remaining ids: $IDS"
  python3 conform_watch_ep08.py 2400 &
  CW=$!
  python3 batch_run.py --only "$IDS" --retries 1 --deadline "$DEADLINE"
  GEN_RC=$?
  say "gen_exit=$GEN_RC"
  sleep 3
  kill -TERM $CW 2>/dev/null || true
  wait $CW 2>/dev/null || true
fi

say "STEP fill-missing 1080p"
python3 local_conform.py --fill-missing
say "fill_exit=$?"

say "STEP verify"
python3 verify_clip.py "$A"/raw/H*_raw.mp4 --frames-dir "$FR" > "$A/verify-raw.json" 2>/dev/null
say "verify_raw_exit=$?"
python3 verify_clip.py "$A"/H??.mp4 --frames-dir "$FR" --expect 1920x1080 > "$A/verify-final.json" 2>/dev/null
say "verify_final_exit=$?"
python3 frame_sheet.py --frames-dir "$FR" --out-dir "$FR/sheets" >/dev/null 2>&1
python3 keyframe_adherence.py || true

say "STEP report"
python3 make_report_ep08.py
say "report_exit=$?"

RAW_N=$(ls "$A"/raw/*_raw.* 2>/dev/null | wc -l)
FIN_N=$(ls "$A"/H*.mp4 2>/dev/null | wc -l)
TOTAL_N=$(python3 -c "import json;print(len(json.load(open('$SHOTS'))['shots']))" 2>/dev/null || echo 0)
say "SUMMARY raw=$RAW_N/$TOTAL_N final=$FIN_N/$TOTAL_N"
say "RESUME_DONE $(ts)"
if [ "$RAW_N" -eq "$TOTAL_N" ] && [ "$FIN_N" -eq "$TOTAL_N" ]; then
  echo "RESULT: RESUME_OK all=$TOTAL_N"
else
  echo "RESULT: RESUME_PARTIAL raw=$RAW_N final=$FIN_N total=$TOTAL_N"
fi
