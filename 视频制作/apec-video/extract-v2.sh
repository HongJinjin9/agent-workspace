#!/bin/bash
set -e
cd /app/vedio/apec-video
F=out/apec-qimen-v2.mp4
mkdir -p delivery
for pair in "4.0:still-v2-hook" "57.5:still-v2-board" "104.5:still-v2-move" "133.5:still-v2-kong" "232:still-v2-timeline"; do
  t=${pair%%:*}; n=${pair##*:}
  /home/admin/.local/bin/ffmpeg -hide_banner -loglevel error -y -ss $t -i "$F" -frames:v 1 -q:v 2 "delivery/$n.jpg"
done
ls -la delivery/still-v2-*.jpg
