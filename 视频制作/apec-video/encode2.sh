#!/bin/bash
set -e
cd /app/vedio/apec-video
rm -f out/apec-qimen-v2.mp4 out/encode2.done
/home/admin/.local/bin/ffmpeg -hide_banner -loglevel error -y \
  -framerate 24 -i work/frames2/f%05d.jpg -i work/audio.m4a \
  -vf "scale=1080:1920:flags=lanczos,unsharp=5:5:0.5:5:5:0.0" \
  -c:v libx264 -preset veryfast -crf 21 -pix_fmt yuv420p -profile:v high \
  -c:a aac -b:a 160k -movflags +faststart -shortest out/apec-qimen-v2.mp4
echo "OK $(date -u) $(stat -c%s out/apec-qimen-v2.mp4)" > out/encode2.done
