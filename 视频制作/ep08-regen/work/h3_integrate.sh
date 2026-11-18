#!/usr/bin/env bash
# 第 08 期：H3 素材到货后的混合镜整合重渲（Lead 通知窗口产出完成后执行）。
# 幂等：缺素材的镜会以 fallback 渲染；全部素材齐备时 22 镜重渲约 3–5 分钟（2 进程）。
set -eu
cd /app/vedio/ep08-regen
H3_SHOTS="S02,S05,S07,S10,S20,S25,S30,S35,S39,S40,S44,S48,S49,S50,S53,S55,S56,S57,S58,S59,S60,S66"
PATCH_SHOTS="$H3_SHOTS,S67"   # S67 片尾卡一并修复（content_present）
echo "[h3] $(date -u +%FT%TZ) check assets"
python3 - <<'PY'
import os, sys
sys.path.insert(0, "/app/vedio/ep08-regen")
import json, ep08assets as A
tl = json.load(open("work/timeline.json"))
need = [s for s in tl["shots"] if s.get("h3")]
ok, miss = [], []
for s in need:
    p, _ = A.resolve(s["asset"])
    (ok if p else miss).append(s["id"])
print("[h3] ready %d/%d; missing: %s" % (len(ok), len(need), " ".join(miss)))
json.dump({"ready": ok, "missing": miss, "total": len(need)},
          open("work/h3-status.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
if os.environ.get("H3_STRICT") == "1" and miss:
    raise SystemExit("[h3] strict: missing %d, abort" % len(miss))
PY
echo "[h3] render 22 mixed shots (force, 2 jobs)"
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  python3 scene_body.py --all --jobs 2 --force --only "$PATCH_SHOTS"
echo "[h3] verify clips"
python3 verify_clips.py | tail -6
echo "[h3] done $(date -u +%FT%TZ)"
