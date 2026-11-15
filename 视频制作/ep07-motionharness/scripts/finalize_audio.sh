#!/bin/bash
# 第 07 期交付主路径：MH 导出视频（内嵌音频仅用于同步预览/兜底）→ 用 audio 母带 remux。
# 视频流 copy（画质无损、秒级完成），音频流优先 copy（母带为 AAC），非 AAC 时重编码 aac 192k。
#
# 用法：
#   bash scripts/finalize_audio.sh                                   # raw=out/ep07-mh.raw.mp4 master=audio/work/audio.m4a out=out/ep07-mh.mp4
#   bash scripts/finalize_audio.sh out/ep07-mh.raw.mp4 audio/work/audio.m4a out/ep07-mh.mp4
set -euo pipefail
ROOT=${ROOT:-/app/vedio/ep07-mh}
RAW=${1:-out/ep07-mh.raw.mp4}
MASTER=${2:-audio/work/audio.m4a}
OUT=${3:-out/ep07-mh.mp4}

export PATH=/home/admin/.nvm/versions/node/v24.21.0/bin:/home/admin/.local/bin:$PATH
FF=${FFMPEG:-/home/admin/.local/bin/ffmpeg}
FP=${FFPROBE:-/home/admin/.local/bin/ffprobe-real}

cd "$ROOT"
mkdir -p out work

DUR=$(python3 -c "import json;print(json.load(open('work/ep07-meta.json'))['expected_duration'])" 2>/dev/null || echo "")
[ -z "$DUR" ] && DUR=$(python3 -c "import json;print(json.load(open('audio/work/timeline_audio.json'))['total'])" 2>/dev/null) || true
[ -z "$DUR" ] && { echo "[finalize] 无法确定期望时长" >&2; exit 1; }

if [ ! -f "$RAW" ]; then echo "[finalize] 缺少 MH 导出: $RAW" >&2; exit 1; fi
if [ ! -f "$MASTER" ]; then
  echo "[finalize] 缺少音频母带 $MASTER —— 退回 MH 内嵌音频（如实记录，交付前应重跑）"
  cp -f "$RAW" "$OUT"
  python3 - "$OUT" "$RAW" "$MASTER" "$DUR" <<'PY'
import json, os, sys
out, raw, master, dur = sys.argv[1:5]
json.dump({"mode": "fallback-mh-embedded-audio", "out": out, "raw": raw,
           "master": master, "expected_duration": float(dur),
           "note": "母带缺失，直接使用 MH 内嵌音轨；loudness 需复核"},
          open("work/remux.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
PY
  exit 0
fi

ACODEC=$("$FP" -v error -select_streams a:0 -show_entries stream=codec_name -of csv=p=0 "$MASTER" | head -1)
ACODEC=${ACODEC:-aac}
if [ "$ACODEC" = "aac" ]; then
  AOPTS=(-c:a copy)
else
  AOPTS=(-c:a aac -b:a 192k -ar 48000)
fi
echo "[finalize] remux: video copy + audio $ACODEC $([ "$ACODEC" = "aac" ] && echo '(copy)' || echo '(aac 192k)')"

START=$(date +%s)
"$FF" -hide_banner -loglevel error -y \
  -i "$RAW" -i "$MASTER" \
  -map 0:v:0 -map 1:a:0 \
  -c:v copy "${AOPTS[@]}" \
  -t "$DUR" -movflags +faststart "$OUT"
END=$(date +%s)

python3 - "$OUT" "$RAW" "$MASTER" "$DUR" "$ACODEC" "$((END - START))" <<'PY'
import hashlib, json, os, subprocess, sys
out, raw, master, dur, acodec, elapsed = sys.argv[1:7]
size = os.path.getsize(out)
h = hashlib.sha256()
with open(out, "rb") as f:
    for chunk in iter(lambda: f.read(1 << 20), b""):
        h.update(chunk)
json.dump({"mode": "remux-video-copy+master-audio", "out": out, "raw": raw,
           "master": master, "audio_codec": acodec,
           "expected_duration": float(dur), "size_bytes": size,
           "size_mb": round(size / 1e6, 2), "sha256": h.hexdigest(),
           "elapsed_s": int(elapsed)},
          open("work/remux.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("[finalize] out=%s %.2f MB (video copy + master audio %s) in %ss"
      % (out, size / 1e6, acodec, elapsed))
PY
