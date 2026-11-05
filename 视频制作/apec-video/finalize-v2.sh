#!/bin/bash
cd /app/vedio/apec-video
for i in $(seq 1 600); do
  p=$(pgrep -fc 'scene3d.py 54' || true)
  n=$(ls work/frames2 2>/dev/null | wc -l)
  if [ "$p" -eq 0 ] && [ "$n" -ge 7733 ]; then break; fi
  sleep 5
done
n=$(ls work/frames2 | wc -l); echo "frames=$n" > /tmp/final-v2.log
if [ "$n" -lt 7733 ]; then echo "ERROR: frames $n < 7733" >> /tmp/final-v2.log; exit 1; fi
rm -f out/apec-qimen-v2f.mp4 out/final-v2.done
/home/admin/.local/bin/ffmpeg -hide_banner -loglevel error -y \
  -framerate 24 -i work/frames2/f%05d.jpg -i work/audio.m4a \
  -vf "scale=1080:1920:flags=lanczos,unsharp=5:5:0.4:5:5:0.0" \
  -c:v libx264 -preset veryfast -crf 25 -pix_fmt yuv420p -profile:v high \
  -c:a aac -b:a 128k -movflags +faststart -shortest out/apec-qimen-v2f.mp4
SIZE=$(stat -c%s out/apec-qimen-v2f.mp4)
echo "encoded size=$SIZE" >> /tmp/final-v2.log
mkdir -p delivery
for pair in "4.0:still-v2-hook" "57.5:still-v2-board" "104.5:still-v2-move" "133.5:still-v2-kong" "232:still-v2-timeline"; do
  t=${pair%%:*}; nm=${pair##*:}
  /home/admin/.local/bin/ffmpeg -hide_banner -loglevel error -y -ss $t -i out/apec-qimen-v2f.mp4 -frames:v 1 -q:v 2 "delivery/$nm.jpg"
done
echo "FINISHED $(date -u) size=$SIZE" > /tmp/final-v2.done
