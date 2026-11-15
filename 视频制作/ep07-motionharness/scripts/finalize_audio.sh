#!/bin/bash
# 第 07 期交付主路径（v3+）：MH 导出视频（内嵌音频仅预览）→ 末尾补帧 pad 到母带长度 → 母带 remux。
# 修复：MH raw 末段只出整秒帧（实测 4992 帧 / 208.0s，母带 208.966s）→ tpad stop_mode=clone 补齐 0.9584s
# 后再 mux，使成片视频轨与音频轨等长（5015 帧 @24fps）。
set -euo pipefail
ROOT=${ROOT:-/app/vedio/ep07-mh}
RAW=${1:-out/ep07-mh.raw.mp4}
MASTER=${2:-audio/work/audio.m4a}
OUT=${3:-out/ep07-mh.mp4}
export PATH=/home/admin/.nvm/versions/node/v24.21.0/bin:/home/admin/.local/bin:$PATH
FF=${FFMPEG:-/home/admin/.local/bin/ffmpeg}
FP=${FFPROBE:-/home/admin/.local/bin/ffprobe-real}
cd "$ROOT"; mkdir -p out work
DUR=$(python3 -c "import json;print(json.load(open('work/ep07-meta.json'))['expected_duration'])" 2>/dev/null || python3 -c "import json;print(json.load(open('audio/work/timeline_audio.json'))['total'])" 2>/dev/null)
[ -z "$DUR" ] && { echo "[finalize] 无法确定期望时长" >&2; exit 1; }
[ -f "$RAW" ] || { echo "[finalize] 缺少 MH 导出: $RAW" >&2; exit 1; }

VDUR=$("$FP" -v error -show_entries format=duration -of csv=p=0 "$RAW" | head -1)
VN=$("$FP" -v error -select_streams v:0 -show_entries stream=nb_frames -of csv=p=0 "$RAW" | head -1)
PAD=$(python3 -c "print(max(0.0, round($DUR - $VDUR, 4)))")
echo "[finalize] raw dur=$VDUR frames=$VN target=$DUR pad=${PAD}s"

PADDED=/tmp/ep07-padded-$(basename "$RAW")
if python3 -c "import sys; sys.exit(0 if $PAD > 0.03 else 1)"; then
  echo "[finalize] padding video tail by ${PAD}s (tpad clone) + re-encode video"
  "$FF" -hide_banner -loglevel error -y -i "$RAW" \
    -vf "tpad=stop_mode=clone:stop_duration=${PAD}" -r 24 \
    -c:v libx264 -preset fast -crf 18 -pix_fmt yuv420p -an "$PADDED"
  SRCVID=$PADDED
else
  SRCVID=$RAW
fi

ACODEC=$("$FP" -v error -select_streams a:0 -show_entries stream=codec_name -of csv=p=0 "$MASTER" | head -1)
ACODEC=${ACODEC:-aac}
if [ "$ACODEC" = "aac" ]; then AOPTS=(-c:a copy); else AOPTS=(-c:a aac -b:a 192k -ar 48000); fi
echo "[finalize] remux: video copy + audio $ACODEC"
"$FF" -hide_banner -loglevel error -y -i "$SRCVID" -i "$MASTER" \
  -map 0:v:0 -map 1:a:0 -c:v copy "${AOPTS[@]}" -t "$DUR" -movflags +faststart "$OUT"

FN=$("$FP" -v error -select_streams v:0 -show_entries stream=nb_frames -of csv=p=0 "$OUT" | head -1)
FD=$("$FP" -v error -show_entries format=duration -of csv=p=0 "$OUT" | head -1)
python3 - "$OUT" "$RAW" "$MASTER" "$DUR" "$VDUR" "$PAD" "$ACODEC" "$FN" "$FD" <<'PY'
import hashlib, json, os, sys
out, raw, master, dur, vdur, pad, codec, frames, fdur = sys.argv[1:10]
size = os.path.getsize(out)
h = hashlib.sha256()
with open(out, "rb") as f:
    for chunk in iter(lambda: f.read(1 << 20), b""):
        h.update(chunk)
json.dump({"mode": "remux-video-copy+pad+master-audio", "out": out, "raw": raw,
           "master": master, "raw_video_duration": float(vdur), "pad_seconds": float(pad),
           "audio_codec": codec, "expected_duration": float(dur),
           "out_frames": int(frames or 0), "out_duration": float(fdur),
           "size_bytes": size, "size_mb": round(size / 1e6, 2), "sha256": h.hexdigest()},
          open("work/remux.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("[finalize] out=%s %.2f MB frames=%s dur=%s pad=%.4fs" % (out, size / 1e6, frames, fdur, float(pad)))
PY
rm -f "$PADDED" 2>/dev/null || true
