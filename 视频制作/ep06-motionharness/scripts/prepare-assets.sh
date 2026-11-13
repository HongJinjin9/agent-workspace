#!/bin/bash
# 从第 06 期既有工程重建 MotionHarness 工程所需素材（大素材不入库）
set -euo pipefail
SRC="${SRC:-/app/vedio/ep06-dialogue}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$HERE/assets/footage" "$HERE/assets/stills"

for i in $(seq 1 14); do
  cp -f "$SRC/assets/comfy/c$i.mp4"       "$HERE/assets/footage/c$i.mp4"
  cp -f "$SRC/assets/comfy-stills/c$i.jpg" "$HERE/assets/stills/c$i.jpg"
done
# 关键帧冻结帧（用于静帧镜头与证据照片）
for i in 1 2 3 6 7 10 11 12 13 14; do
  /home/admin/.local/bin/ffmpeg -v error -y -ss 2.4 -i "$HERE/assets/footage/c$i.mp4" -frames:v 1 -q:v 2 "$HERE/assets/stills/f$i.jpg"
done
cp -f "$SRC/work/mix.wav" "$HERE/assets/audio.wav"
echo "assets ready: $(du -sh "$HERE/assets" | cut -f1)"
