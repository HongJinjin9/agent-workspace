#!/usr/bin/env bash
# 第 08 期仓库同步（不 commit；Lead 统一提交）。
#
# 只同步 .gitignore 允许入库的「小文件」：
#   delivery/**（静帧/联系表/封面/delivery-manifest.json）
#   work/*.json（final-check.json / finalize.json / assets-manifest.json / render.json）
#   work/*.md（final-report.md / audio-report.md / RUNBOOK.md / notes.md）
#   work/srt/**（句级 SRT）
# 成片（out/）、素材（assets/）、QA png（work/qa/）、音频大文件一律不同步。
#
# 用法：
#   scripts/sync_repo.sh                    # 同步交付物/报告 + scripts/（交付脚本归 delivery）
#   scripts/sync_repo.sh --no-scripts       # 只同步交付物/报告
#   EP08_REPO=/path/to/worktree scripts/sync_repo.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="${EP08_REPO:-/home/admin/.dsh/state/superagent/work/episode-eight-video-f134d482e964}"
DST="$REPO/视频制作/ep08-regen"
SYNC_SCRIPTS=1
[[ "${1:-}" == "--no-scripts" ]] && SYNC_SCRIPTS=0

if [[ ! -d "$REPO/.git" && ! -f "$REPO/.git" ]]; then
  echo "找不到 ticket worktree: $REPO（用 EP08_REPO 指定）" >&2
  exit 2
fi
mkdir -p "$DST/work" "$DST/delivery"

copy() { # copy <src> <dst>
  if [[ -f "$1" ]]; then
    mkdir -p "$(dirname "$2")"
    cp -f "$1" "$2"
    echo "  + ${2#"$REPO"/}"
  fi
}

echo "[sync] $ROOT -> $DST"

# 1) delivery（静帧/联系表/封面/manifest）
if [[ -d "$ROOT/delivery" ]]; then
  ( cd "$ROOT/delivery" && find . -type f \( -name '*.jpg' -o -name '*.png' -o -name '*.json' \) ) | \
  while read -r f; do copy "$ROOT/delivery/$f" "$DST/delivery/$f"; done
fi

# 2) work 报告/清单/SRT
copy "$ROOT/work/final-check.json"          "$DST/work/final-check.json"
copy "$ROOT/work/finalize.json"             "$DST/work/finalize.json"
copy "$ROOT/work/render.json"               "$DST/work/render.json"
copy "$ROOT/work/final-report.md"           "$DST/work/final-report.md"
copy "$ROOT/work/assets-manifest.json"      "$DST/work/assets-manifest.json"
copy "$ROOT/work/notes.md"                  "$DST/work/notes.md"
copy "$ROOT/work/cover-config.json"          "$DST/work/cover-config.json"
copy "$ROOT/work/RUNBOOK.md"                "$DST/work/RUNBOOK.md"
copy "$ROOT/audio/work/audio-report.md"     "$DST/work/audio-report.md"
if [[ -d "$ROOT/work/srt" ]]; then
  for f in "$ROOT/work/srt"/*.srt; do [[ -f "$f" ]] && copy "$f" "$DST/work/srt/$(basename "$f")"; done
fi

# 2.5) assets-manifest.json：仓库项目根目录（若 engine 已有则不覆盖）
if [[ -f "$ROOT/work/assets-manifest.json" && ! -f "$DST/assets-manifest.json" ]]; then
  copy "$ROOT/work/assets-manifest.json" "$DST/assets-manifest.json"
fi

# 3) 交付/验收脚本（Lead 裁决：视频制作/ep08-regen/scripts/ 归 delivery-engineer）
if [[ "$SYNC_SCRIPTS" -eq 1 && -d "$ROOT/scripts" ]]; then
  for f in "$ROOT/scripts"/*.py "$ROOT/scripts"/*.sh; do
    [[ -f "$f" ]] && copy "$f" "$DST/scripts/$(basename "$f")"
  done
fi

echo "[sync] done；未 commit（Lead 统一提交）。"
