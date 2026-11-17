#!/usr/bin/env bash
# 第 08 期一键交付链（Lead 通知开工后执行）：
#   finalize（master+web）→ verify（硬校验）→ prepare_delivery（静帧/联系表/封面/manifest）
#   → write_report（final-report.md + assets-manifest.json）→ sync_repo（仓库小文件）
#   → make_engine_package（工程包）
#
# 纪律：finalize 内部持 /tmp/ep08-finalize.lock，并与 engine 的 /tmp/ep08-render.lock 互斥。
# 用法（**必须脱离会话启动**，否则长进程会随 agent 回合结束被回收）：
#   setsid nohup bash scripts/deliver_all.sh > work/deliver-all.log 2>&1 < /dev/null &
#   scripts/deliver_all.sh                 # 完整链（clips 模式）
#   scripts/deliver_all.sh --draft         # 草稿（veryfast/crf27，快速看片）
#   scripts/deliver_all.sh --input work/film-raw.mp4 [--baked]   # raw 模式
#   scripts/deliver_all.sh --skip-sync     # 不写仓库（只看片）
# 汇总：work/deliver-all.json（rc/耗时/产物/校验结论）
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PATH="/home/admin/.local/bin:$PATH"
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2

FINALIZE_ARGS=()
VERIFY_ARGS=()
SKIP_SYNC=0
for a in "$@"; do
  case "$a" in
    --skip-sync) SKIP_SYNC=1 ;;
    --allow-missing-h3) VERIFY_ARGS+=("--allow-missing-h3") ;;   # code-only 备选交付（Lead 批准时用）
    *) FINALIZE_ARGS+=("$a") ;;
  esac
done

echo "=============================================================="
echo "[deliver] $(date -u +%Y-%m-%dT%H:%M:%SZ) 开始；finalize 参数：${FINALIZE_ARGS[*]:-clips 默认}"
echo "=============================================================="

MODE_RAW=0
for a in "${FINALIZE_ARGS[@]:-}"; do [[ "$a" == "--input" ]] && MODE_RAW=1; done

if [[ "$MODE_RAW" -eq 0 ]]; then
  echo "---- 0/6 输入自检（timeline/clips/母带/SRT/H3）----"
  CHECK_ARGS=()
  [[ " ${VERIFY_ARGS[*]:-} " == *" --allow-missing-h3 "* ]] && CHECK_ARGS+=("--allow-missing-h3")
  if [[ ${#CHECK_ARGS[@]} -gt 0 ]]; then
    python3 scripts/check_inputs.py --wait 900 "${CHECK_ARGS[@]}" || { echo "[deliver] 输入未就绪，中止（work/input-check.json）"; exit 1; }
  else
    python3 scripts/check_inputs.py --wait 900 || { echo "[deliver] 输入未就绪，中止（work/input-check.json）"; exit 1; }
  fi
else
  echo "[deliver] raw 模式，跳过 clips 输入自检"
fi

echo "---- 1/6 finalize ----"
python3 scripts/finalize.py "${FINALIZE_ARGS[@]}" --wait 900 || { echo "[deliver] finalize 失败，中止"; exit 1; }

echo "---- 2/6 verify_ep08 ----"
VERIFY_RC=0
if [[ ${#VERIFY_ARGS[@]} -gt 0 ]]; then
  python3 scripts/verify_ep08.py "${VERIFY_ARGS[@]}" || VERIFY_RC=$?
else
  python3 scripts/verify_ep08.py || VERIFY_RC=$?
fi
if [[ "$VERIFY_RC" -ne 0 ]]; then
  echo "[deliver] ⚠️ verify 有未通过项（见 work/final-check.json）；继续出交付物与报告，但不会同步仓库"
fi

echo "---- 3/6 prepare_delivery ----"
python3 scripts/prepare_delivery.py || echo "[deliver] ⚠️ prepare_delivery 失败"

echo "---- 4/6 write_report ----"
python3 scripts/write_report.py --notes work/notes.md || echo "[deliver] ⚠️ write_report 失败"

if [[ "$VERIFY_RC" -eq 0 && "$SKIP_SYNC" -eq 0 ]]; then
  echo "---- 5/6 sync_repo ----"
  scripts/sync_repo.sh || echo "[deliver] ⚠️ sync_repo 失败"
  echo "---- 6/6 engine package ----"
  scripts/make_engine_package.sh --with-stills || echo "[deliver] ⚠️ 工程包失败"
else
  echo "---- 5-6/6 跳过仓库同步/工程包（verify 未全 PASS 或 --skip-sync）----"
fi

# 汇总 JSON（跨回合核对）
python3 - "$VERIFY_RC" "$SKIP_SYNC" <<'PY'
import datetime, json, os, sys
v_rc, skip = int(sys.argv[1]), int(sys.argv[2])
rec = {"mode": "delivery", "verify_rc": v_rc, "skip_sync": skip,
       "master": os.path.relpath("out/ep08-regen.mp4") if os.path.isfile("out/ep08-regen.mp4") else None,
       "master_size_mb": round(os.path.getsize("out/ep08-regen.mp4") / 1e6, 2) if os.path.isfile("out/ep08-regen.mp4") else None,
       "web": os.path.relpath("out/ep08-regen-web.mp4") if os.path.isfile("out/ep08-regen-web.mp4") else None,
       "final_check": "work/final-check.json" if os.path.isfile("work/final-check.json") else None,
       "final_report": "work/final-report.md" if os.path.isfile("work/final-report.md") else None,
       "delivery_manifest": "delivery/delivery-manifest.json" if os.path.isfile("delivery/delivery-manifest.json") else None,
       "finished_utc": datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat(),
       "result": "PASS" if v_rc == 0 else "PROBLEMS"}
json.dump(rec, open("work/deliver-all.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("deliver-all.json ->", rec["result"])
PY

echo "=============================================================="
if [[ "$VERIFY_RC" -eq 0 ]]; then
  echo "[deliver] ✅ 全链路完成：out/ep08-regen.mp4（master）+ out/ep08-regen-web.mp4（web）"
  echo "[deliver]    报告 work/final-report.md；清单 work/final-check.json；交付 delivery/"
else
  echo "[deliver] ❌ 校验未全 PASS，见 work/final-check.json 的 problems；处理后可重跑 deliver_all.sh"
fi
echo "=============================================================="
exit "$VERIFY_RC"
