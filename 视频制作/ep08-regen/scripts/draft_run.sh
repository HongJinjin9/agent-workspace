#!/usr/bin/env bash
# 第 08 期 draft 链路（code-only 内部验证；跨回合存活由调用方 setsid/nohup 保证）。
# finalize(--draft --no-grade) -> verify(--allow-missing-h3) -> work/draft-run.json(rc/耗时/异常)
#
# 用法（独立于会话，避免随 agent 回合结束被回收）：
#   setsid nohup bash scripts/draft_run.sh > work/draft-finalize.log 2>&1 < /dev/null &
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PATH="/home/admin/.local/bin:$PATH"
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2
export EP08_FFMPEG_THREADS="${EP08_FFMPEG_THREADS:-2}"

DRAFT=out/ep08-draft.mp4
DRAFT_WEB=out/ep08-draft-web.mp4
META=work/draft-run.json
rm -f "$DRAFT" "$DRAFT_WEB" work/finalize-draft.json work/final-check-draft.json
T0=$(date +%s)

echo "=== [$(date -u +%Y-%m-%dT%H:%M:%SZ)] draft finalize 开始（threads=$EP08_FFMPEG_THREADS）==="
python3 scripts/finalize.py --draft --no-grade --out "$DRAFT" --web-out "$DRAFT_WEB"
F_RC=$?
F_ELAPSED=$(($(date +%s) - T0))
echo "finalize_rc=$F_RC elapsed=${F_ELAPSED}s"

V_RC=99
V_T0=$(date +%s)
if [[ "$F_RC" -eq 0 ]]; then
  echo "=== [$(date -u +%Y-%m-%dT%H:%M:%SZ)] draft verify ==="
  python3 scripts/verify_ep08.py "$DRAFT" --web "$DRAFT_WEB" --allow-missing-h3
  V_RC=$?
  echo "verify_rc=$V_RC"
else
  echo "finalize 失败，跳过 verify"
fi
V_ELAPSED=$(($(date +%s) - V_T0))

# 汇总 draft 运行元数据（无论成败都写，供跨回合核对）
python3 - "$F_RC" "$F_ELAPSED" "$V_RC" "$V_ELAPSED" "$META" "$DRAFT" "$DRAFT_WEB" <<'PY'
import datetime, json, os, sys
f_rc, f_el, v_rc, v_el, meta, draft, draft_web = (
    int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]),
    sys.argv[5], sys.argv[6], sys.argv[7])
def info(p):
    if not os.path.isfile(p):
        return None
    return {"path": p, "size_mb": round(os.path.getsize(p) / 1e6, 2),
            "mtime_utc": datetime.datetime.fromtimestamp(
                os.path.getmtime(p), datetime.timezone.utc).replace(microsecond=0).isoformat()}
rec = {
    "mode": "draft-code-only",
    "generated_by": "scripts/draft_run.sh",
    "finalize_rc": f_rc, "finalize_elapsed_s": f_el,
    "verify_rc": v_rc, "verify_elapsed_s": v_el,
    "draft": info(draft), "draft_web": info(draft_web),
    "finalize_meta": "work/finalize-draft.json" if os.path.isfile("work/finalize-draft.json") else None,
    "final_check": "work/final-check-draft.json" if os.path.isfile("work/final-check-draft.json") else None,
    "finished_utc": datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat(),
    "result": "PASS" if (f_rc == 0 and v_rc == 0) else "FAIL",
}
json.dump(rec, open(meta, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("draft-run.json ->", meta, rec["result"])
PY
echo "=== [$(date -u +%Y-%m-%dT%H:%M:%SZ)] DONE finalize_rc=$F_RC verify_rc=$V_RC ==="
[[ "$F_RC" -eq 0 && "$V_RC" -eq 0 ]]
