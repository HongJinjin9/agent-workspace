#!/bin/bash
# EP08 ComfyUI H3 window runner — PLAN §4 discipline (manual boot, billed 1 hour).
#
#   ./window_run.sh preflight            # NO network: validate pack/scripts/local chain
#   ./window_run.sh run [WAIT_UNTIL]      # real window; WAIT_UNTIL=HH:MM (UTC) optional
#
# Run only after the Lead says the window is open (user has booted the instance).
# Credentials are read from /home/admin/.h3.env / environment only and never written.
# CPU-heavy work outside this pack must not run during the window (PLAN §4.4).
set -u
# cgroup 4 cores / 6GB (Lead 2026-11-16): cap BLAS/ffmpeg threads, serial local work only
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 NUMEXPR_NUM_THREADS=2
export VECLIB_MAXIMUM_THREADS=2
cd /app/vedio/ep08-regen/comfyui || exit 1

MODE="${1:-run}"
WAIT_UNTIL="${2:-}"
A=/app/vedio/ep08-regen/assets/h3
FR=$A/frames
SHOTS=shots-ep08-run.json
GEN_BUDGET_MIN="${GEN_BUDGET_MIN:-30}"   # stop submitting new shots after this many minutes
CONFORM_BUDGET_S="${CONFORM_BUDGET_S:-3000}"
mkdir -p "$A/raw" "$FR"

ts() { date -u +%FT%TZ; }
say() { echo "[$(ts)] $*"; }

# ------------------------------------------------------------------ preflight
if [ "$MODE" = "preflight" ]; then
  say "PREFLIGHT (no network, no GPU)"
  rc=0
  echo "--- 1) python syntax ---"
  python3 -m py_compile batch_run.py capability_probe.py check_pack.py local_conform.py \
      conform_watch_ep08.py make_prompts_ep08.py make_report_ep08.py resolve_base.py \
      verify_clip.py frame_sheet.py selftest_local.py probe_util.py keyframe_adherence.py \
      build_run_orders.py build_fl2va_template.py \
      tools/comfy_client.py tools/upscale_video.py || rc=1
  echo "--- 2) shell syntax ---"
  bash -n window_run.sh || rc=1
  echo "--- 3) workflow + shots + keyframe static validation ---"
  python3 check_pack.py || rc=1
  echo "--- 4) batch workflow build dry-run (no network) ---"
  python3 batch_run.py --dry || rc=1
  echo "--- 5) local 1080p/verify chain self-test (no network) ---"
  python3 selftest_local.py || rc=1
  echo "--- 6) conform plan dry-run ---"
  python3 local_conform.py --dry || rc=1
  say "PREFLIGHT rc=$rc"
  if [ "$rc" -eq 0 ]; then echo "RESULT: PREFLIGHT_OK"; else echo "RESULT: PREFLIGHT_FAIL"; fi
  exit "$rc"
fi

# ------------------------------------------------------------------ real window
say "WINDOW RUN start (mode=run wait_until=${WAIT_UNTIL:-none})"
[ -f "$SHOTS" ] || { say "FATAL: $SHOTS missing — handoff pack incomplete, do NOT submit"; exit 1; }
python3 check_pack.py || { say "FATAL: check_pack failed — fix pack before submitting"; exit 1; }

# optional scheduled wait (same idea as ep05/ep07 window_start.sh)
if [ -n "$WAIT_UNTIL" ]; then
  python3 - "$WAIT_UNTIL" <<'PY'
import datetime as dt, sys, time
target = dt.datetime.strptime(sys.argv[1], "%H:%M").replace(
    year=dt.datetime.now(dt.timezone.utc).year,
    month=dt.datetime.now(dt.timezone.utc).month,
    day=dt.datetime.now(dt.timezone.utc).day, tzinfo=dt.timezone.utc)
while True:
    now = dt.datetime.now(dt.timezone.utc)
    if now >= target:
        break
    time.sleep(min(2.0, (target - now).total_seconds()))
print(f"[wait] window start {now.isoformat()}", flush=True)
PY
fi

set -a
. /home/admin/.h3.env
set +a

say "=== STEP 1: entry resolve + login + /system_stats ($(ts)) ==="
BASE=$(python3 resolve_base.py 1500 | tee /tmp/ep08_resolve.log | tail -1)
say "resolved_base=[$BASE]"
if [ -z "$BASE" ] || ! echo "$BASE" | grep -q "https://"; then
  say "WINDOW: NOT_REACHABLE (see /tmp/ep08_resolve.log) — instance not booted yet"
  echo "RESULT: WINDOW_NOT_REACHABLE"
  exit 0
fi
export H3_BASE="$BASE"
say "using H3_BASE=$H3_BASE"

say "=== STEP 2: capability probe (nodes/models/FL2VA/upload) ($(ts)) ==="
python3 capability_probe.py
CAP_RC=$?
if [ "$CAP_RC" -ge 5 ]; then
  say "WINDOW: CAPABILITY_FAILED rc=$CAP_RC — required nodes/models/upload missing, stopping before burning the hour"
  echo "RESULT: WINDOW_CAPABILITY_FAILED"
  exit 0
fi
MODE_FLAG=""
if [ -f "$A/capability.json" ]; then
  FL_MODE=$(python3 -c "import json;print(json.load(open('$A/capability.json'))['decision']['fl2va_mode'])" 2>/dev/null || echo fl2va)
  say "capability decision fl2va_mode=$FL_MODE cap_rc=$CAP_RC"
  if [ "$FL_MODE" != "fl2va" ]; then MODE_FLAG="--mode t2v"; say "FL2VA unavailable -> forcing T2V"; fi
fi

say "=== STEP 3: generate all shots (FL2VA first, T2V fallback) + local conform watcher ($(ts)) ==="
python3 conform_watch_ep08.py "$CONFORM_BUDGET_S" &
CW=$!
DEADLINE=$(date -u -d "+${GEN_BUDGET_MIN} minutes" +%H:%M)
say "generation deadline ${DEADLINE}Z (${GEN_BUDGET_MIN} min budget)"
python3 batch_run.py --retries 1 --deadline "$DEADLINE" $MODE_FLAG
GEN_RC=$?
say "gen_exit=$GEN_RC at $(ts)"
# stop the watcher once generation is over (it would otherwise wait for missing shots
# until its own deadline); fill-missing below picks up whatever is left, atomically.
sleep 3
kill -TERM $CW 2>/dev/null || true
wait $CW 2>/dev/null || true
say "conform watcher stopped at $(ts); raw=$(ls $A/raw/*_raw.* 2>/dev/null | wc -l) final=$(ls $A/H*.mp4 2>/dev/null | wc -l)"

say "=== STEP 4: fill any missing 1080p finals (local lanczos) ($(ts)) ==="
python3 local_conform.py --fill-missing
say "fill_exit=$? at $(ts)"

say "=== STEP 5: per-clip hard verification + frames + sheets ($(ts)) ==="
mkdir -p "$FR"
python3 verify_clip.py "$A"/raw/H*_raw.mp4 --frames-dir "$FR" > "$A/verify-raw.json" 2>/dev/null
say "verify_raw_exit=$?"
python3 verify_clip.py "$A"/H??.mp4 --frames-dir "$FR" --expect 1920x1080 \
    > "$A/verify-final.json" 2>/dev/null
say "verify_final_exit=$?"
python3 frame_sheet.py --frames-dir "$FR" --out-dir "$FR/sheets" >/dev/null 2>&1
say "frames done"
say "--- keyframe adherence (FL2VA 是否真从首帧长出来) ---"
python3 keyframe_adherence.py
say "adherence_exit=$?"

say "=== STEP 6: manifest finalize + report ($(ts)) ==="
python3 make_report_ep08.py
say "report_exit=$?"

# window summary for the Lead message
RAW_N=$(ls "$A"/raw/*_raw.* 2>/dev/null | wc -l)
FIN_N=$(ls "$A"/H*.mp4 2>/dev/null | wc -l)
TOTAL_N=$(python3 -c "import json;print(len(json.load(open('$SHOTS'))['shots']))" 2>/dev/null || echo 0)
OK_N=$(python3 - <<PY
import json
try:
    m=json.load(open('$A/manifest.json'))
    print(sum(1 for s in m.get('shots',{}).values() if s.get('status') in ('downloaded','ok')))
except Exception:
    print(0)
PY
)
say "SUMMARY raw=$RAW_N/$TOTAL_N final=$FIN_N/$TOTAL_N manifest_ok=$OK_N gen_rc=$GEN_RC"
say "WINDOW END $(ts)"
if [ "$RAW_N" -eq "$TOTAL_N" ] && [ "$FIN_N" -eq "$TOTAL_N" ]; then
  echo "RESULT: WINDOW_DONE all=$TOTAL_N"
else
  echo "RESULT: WINDOW_PARTIAL raw=$RAW_N final=$FIN_N total=$TOTAL_N"
fi
ls -la "$A" | head -40
