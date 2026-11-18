#!/usr/bin/env bash
# 第 08 期逐镜/全片渲染编排（交付 owner 用）。
#
# 背景：逐镜或整合渲染由 engine-dev 提供入口（默认场景：python3 scene_body.py --all）。
# 本脚本只负责「同一时刻只跑一个全片渲染」的纪律 + 记录耗时/失败原因/降级方案。
# 资源纪律：H3 窗口内不得跑本脚本（窗口内不做 CPU 重活）；本机 128 核可并发，
#          但同一时刻只允许一个全片渲染进程（flock）。
#
# 用法：
#   scripts/render_all.sh                          # 默认：python3 scene_body.py --all
#   scripts/render_all.sh --force                  # 透传参数给 engine 渲染器
#   EP08_RENDER_CMD="python3 scene_body.py --all --jobs 8" scripts/render_all.sh
#   scripts/render_all.sh --cmd "python3 scene_body.py --all --jobs 8"
#
# 产物：
#   work/render.log        渲染日志
#   work/render.json       开始/结束/耗时/rc/命令/降级记录
#   flock /tmp/ep08-render.lock
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
LOCK=/tmp/ep08-render.lock
FINALIZE_LOCK=/tmp/ep08-finalize.lock
LOG="$ROOT/work/render.log"
META="$ROOT/work/render.json"
mkdir -p "$ROOT/work" "$ROOT/out"

CMD="${EP08_RENDER_CMD:-python3 scene_body.py --all}"
if [[ "${1:-}" == "--cmd" ]]; then
  CMD="$2"; shift 2
fi
# 兼容透传：未用 --cmd 时，把额外参数追加给默认命令
if [[ $# -gt 0 ]]; then CMD="$CMD $*"; fi

export PATH="/home/admin/.local/bin:$PATH"
export EP08_RENDER_CMD="$CMD"

echo "[render_all] $(date -u +%Y-%m-%dT%H:%M:%SZ) cmd: $CMD" | tee -a "$LOG"

# 与 finalize 互斥：finalize 持 /tmp/ep08-finalize.lock 时先等它结束（最多 1800s）
if [[ -e "$FINALIZE_LOCK" ]]; then
  if ! flock -n "$FINALIZE_LOCK" true 2>/dev/null; then
    echo "[render_all] finalize 正在跑（$FINALIZE_LOCK），等待其结束……" | tee -a "$LOG"
    timeout 1800 bash -c "while ! flock -n '$FINALIZE_LOCK' true 2>/dev/null; do sleep 5; done" || true
  fi
fi

# flock -w 7200：最多排队 2 小时；同一时刻只允许一个全片渲染
exec 9>"$LOCK"
if ! flock -n 9; then
  echo "[render_all] 已有全片渲染在跑，排队等待（flock $LOCK）……" | tee -a "$LOG"
  flock -w 7200 9 || { echo "[render_all] 等待超时，退出" | tee -a "$LOG"; exit 3; }
fi

T0=$(date +%s)
set +e
bash -c "$CMD" 2>&1 | tee -a "$LOG"
RC=${PIPESTATUS[0]}
set -e
T1=$(date +%s)
ELAPSED=$((T1-T0))

python3 - "$CMD" "$RC" "$ELAPSED" "$META" "$LOG" <<'PY'
import datetime, json, os, sys
cmd, rc, elapsed, meta, log = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4], sys.argv[5]
now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()
rec = {"cmd": cmd, "rc": rc, "elapsed_s": elapsed, "finished_utc": now,
       "log": os.path.relpath(log), "mode": "render-all"}
if os.path.isfile(meta):
    try:
        old = json.load(open(meta, encoding="utf-8"))
        if isinstance(old, dict) and old.get("cmd"):
            rec.setdefault("history", []).append(old)
    except Exception:
        pass
json.dump(rec, open(meta, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("[render_all] rc=%d elapsed=%ds -> %s" % (rc, elapsed, meta))
PY

if [[ "$RC" -ne 0 ]]; then
  echo "[render_all] 渲染失败 rc=$RC；降级方案：分段渲染 + ffmpeg concat（见 work/RUNBOOK.md）" | tee -a "$LOG"
  exit "$RC"
fi
echo "[render_all] 渲染完成，耗时 ${ELAPSED}s" | tee -a "$LOG"
