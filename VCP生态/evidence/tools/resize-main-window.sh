#!/bin/bash
# Restore the VCPChat main window to the BEFORE-capture size (inner 2300x843, frame 8px).
# After a restart, xvfb-run may pick a new display; this script discovers the Xvfb
# display/auth that owns the "VCPChat" window and resizes it with xdotool to 2308x847
# (Chromium adds an 8px frame -> innerWidth 2300 x innerHeight 843).
set -u
TARGET_OUTER_W=2308
TARGET_OUTER_H=847

pairs=$(ps -eo args= | awk '/Xvfb :[0-9]+/ {
  disp=""; auth="";
  for (i=1; i<=NF; i++) {
    if ($i ~ /^:[0-9]+$/) disp=$i;
    if ($i=="-auth") auth=$(i+1);
  }
  if (disp != "") print disp" "auth;
}')

found=0
while read -r disp auth; do
  [ -z "$disp" ] && continue
  export DISPLAY="$disp"
  if [ -n "$auth" ] && [ -f "$auth" ]; then export XAUTHORITY="$auth"; else unset XAUTHORITY; fi
  wins=$(xdotool search --name '^VCPChat$' 2>/dev/null || true)
  for w in $wins; do
    echo "display=$disp win=$w -> resizing to ${TARGET_OUTER_W}x${TARGET_OUTER_H}"
    xdotool windowsize "$w" "$TARGET_OUTER_W" "$TARGET_OUTER_H" 2>/dev/null || true
    xdotool windowactivate "$w" 2>/dev/null || true
    xdotool getwindowgeometry "$w" 2>/dev/null | sed 's/^/  /'
    found=1
  done
done <<< "$pairs"

if [ "$found" = 0 ]; then
  echo "ERROR: no VCPChat X window found" >&2
  exit 1
fi
echo OK
