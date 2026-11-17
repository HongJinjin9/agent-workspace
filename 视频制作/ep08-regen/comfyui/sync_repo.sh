#!/bin/bash
# Sync the EP08 H3 handoff pack (scripts/docs/prompts/workflows only, no media) into the
# ticket worktree: 视频制作/ep08-regen/comfyui/. Idempotent; never commits, never touches
# engine-dev's own files outside comfyui/.
set -u
SRC=/app/vedio/ep08-regen/comfyui
REPO=/home/admin/.dsh/state/superagent/work/episode-eight-video-f134d482e964/视频制作/ep08-regen/comfyui
[ -d "$SRC" ] || { echo "missing $SRC"; exit 1; }
mkdir -p "$REPO/workflows" "$REPO/tools"

FILES=(
  README.md RUNBOOK.md
  batch_run.py build_run_orders.py build_fl2va_template.py capability_probe.py check_pack.py
  conform_watch_ep08.py frame_sheet.py keyframe_adherence.py local_conform.py
  make_prompts_ep08.py make_report_ep08.py probe_util.py resolve_base.py selftest_local.py
  verify_clip.py window_run.sh
  shots-ep08-run.json prompt-overrides-ep08.json prompts-ep08.md report.md report.json
  keyframe-audit.md keyframe-sanitize.json keyframe-blocklist.json run-policy.json
  sync_repo.sh window_run_resume.sh fix_redline.sh shots-ep08-fix.json
)
for f in "${FILES[@]}"; do
  [ -f "$SRC/$f" ] || continue
  cp -p "$SRC/$f" "$REPO/$f"
done
# reference copies of the engine work order + pipeline templates (text only)
for f in shots-ep08.json shots-ep05-reference.json; do
  [ -f "$SRC/$f" ] && cp -p "$SRC/$f" "$REPO/$f"
done
for f in t2v_api.json fl2va_api.json; do
  [ -f "$SRC/workflows/$f" ] && cp -p "$SRC/workflows/$f" "$REPO/workflows/$f"
done
for f in comfy_client.py upscale_video.py probe_util.py; do
  [ -f "$SRC/tools/$f" ] && cp -p "$SRC/tools/$f" "$REPO/tools/$f"
done
echo "synced -> $REPO"
ls -la "$REPO" | head -30
echo "NOTE: no git commit/push (Lead 统一提交)"
