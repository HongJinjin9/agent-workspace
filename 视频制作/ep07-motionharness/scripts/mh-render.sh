#!/bin/bash
# 第 07 期最终导出（单实例）：flock 串行化；日志写 /tmp（避免渲染期间向项目目录写入），
# 导出完成后写 work/mh-render.json 供自检报告引用。MH raw 无音轨（视频优先），交付由 finalize_audio.sh remux 母带。
set -euo pipefail
ROOT=${ROOT:-/app/vedio/ep07-mh}
OUT=${1:-out/ep07-mh.raw.mp4}
LOCK=${LOCK:-/tmp/mh-ep07.lock}
JSON=${JSON:-'{"quality":"master","fps":24}'}
LOG=${LOG:-/tmp/ep07-render.log}

export PATH=/home/admin/.nvm/versions/node/v24.21.0/bin:/home/admin/.local/bin:$PATH
export MH_BROWSER_PATH=${MH_BROWSER_PATH:-/home/admin/.cache/mh-chrome/chrome-nosandbox}
export MH_FFPROBE=${MH_FFPROBE:-/home/admin/.local/bin/ffprobe-real}

cd "$ROOT"
mkdir -p out work
echo "[mh-render] lock=$LOCK out=$OUT payload=$JSON" | tee -a "$LOG"

exec 9>"$LOCK"
flock 9
echo "[mh-render] lock acquired $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$LOG"

if [ -f "$OUT" ]; then
  echo "[mh-render] ERROR: $OUT already exists（不覆盖；如需重渲先移走）" | tee -a "$LOG" >&2
  exit 2
fi

START=$(date +%s)
set +e
mh render "$OUT" --json "$JSON" >> "$LOG" 2>&1
RC=$?
set -e
END=$(date +%s)
ELAPSED=$((END - START))

python3 - "$OUT" "$JSON" "$START" "$END" "$RC" <<'PY'
import hashlib, json, os, sys
out, payload, start, end, rc = sys.argv[1:6]
size = os.path.getsize(out) if os.path.isfile(out) else 0
meta = {"command": "mh render %s --json %s" % (out, payload),
        "quality": (json.loads(payload).get("quality") if payload.strip().startswith("{") else None),
        "fps": (json.loads(payload).get("fps") if payload.strip().startswith("{") else None),
        "started_utc": None, "started_unix": int(start), "finished_unix": int(end),
        "elapsed_s": int(end) - int(start), "rc": int(rc),
        "output": out, "size_bytes": size, "size_mb": round(size / 1e6, 2),
        "exists": bool(size)}
if size:
    h = hashlib.sha256()
    with open(out, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    meta["sha256"] = h.hexdigest()
json.dump(meta, open("work/mh-render.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("[mh-render] meta -> work/mh-render.json rc=%d elapsed=%ds size=%.2fMB"
      % (int(rc), meta["elapsed_s"], meta["size_mb"]))
sys.exit(0 if int(rc) == 0 and size else 1)
PY
