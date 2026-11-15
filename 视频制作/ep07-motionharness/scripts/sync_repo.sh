#!/bin/bash
# Lead-only（或交付 owner 运行）：把第 07 期 MotionHarness 工程源码同步进 ticket 仓库 worktree。
# 只同步源码/数据/脚本/清单/自检报告与交付小图；H3 视频、音频母带、成片等大素材不入库。
set -euo pipefail
SRC=${SRC:-/app/vedio/ep07-mh}
DST=${DST:-/home/admin/.dsh/state/superagent/work/episode-five-comfyui-683d48ba7d6a/视频制作/ep07-motionharness}
mkdir -p "$DST"/src "$DST/scripts" "$DST/delivery" "$DST/work"
cd "$SRC"

echo "[sync] project config"
for f in mh.json document.json README.md SPEC.md; do
  [ -f "$f" ] && cp -f "$f" "$DST/" && echo "  $f" || echo "  (missing) $f"
done

echo "[sync] src tree (source only)"
if [ -d src ]; then
  # 递归同步 src 下所有源码/数据文件；assets 目录若存在则跳过（大素材不入库）
  (cd src && find . -type f \( -name '*.ts' -o -name '*.tsx' -o -name '*.js' -o -name '*.jsx' \
      -o -name '*.css' -o -name '*.json' -o -name '*.d.ts' \) -not -path './assets/*' \
      -print0 | while IFS= read -r -d '' f; do
        mkdir -p "$DST/src/$(dirname "$f")"
        cp -f "$f" "$DST/src/$f"
      done)
  echo "  src/ -> $DST/src/"
fi

echo "[sync] scripts"
for f in scripts/verify_ep07.py scripts/prepare_delivery.py scripts/write_report.py scripts/sync_repo.sh \
         scripts/mh-render.sh scripts/finalize_audio.sh scripts/RUNBOOK.md; do
  [ -f "$f" ] && cp -f "$f" "$DST/scripts/" && echo "  $f" || true
done

echo "[sync] manifests / reports"
for f in assets-manifest.json work/final-report.md work/final-check.json \
         delivery/delivery-manifest.json delivery/contact-sheet.jpg \
         delivery/cover-16x9.jpg delivery/cover-1x1.jpg delivery/cover-3x4.jpg; do
  [ -f "$f" ] && mkdir -p "$DST/$(dirname "$f")" && cp -f "$f" "$DST/$f" && echo "  $f" || true
done

if [ ! -f "$DST/.gitignore" ]; then
  cat > "$DST/.gitignore" <<'GI'
# 素材/成片/中间产物不入库（只保留源码/数据/清单/交付小图）
assets/
audio/
out/
.tmp/
.mh/
node_modules/
work/qa/
work/srt/*.wav
GI
  echo "  .gitignore"
fi

echo "[sync] done -> $DST"
