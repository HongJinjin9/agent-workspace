#!/usr/bin/env bash
# 第 08 期工程包（Release 资产之一）：只打包可复现的源码/文档/时间轴/SRT/清单，不含成片与素材。
#
# 用法：
#   scripts/make_engine_package.sh                 # -> out/ep08-regen-engine-pack.tar.gz
#   scripts/make_engine_package.sh --with-stills   # 附带 delivery 静帧/封面（体积仍很小）
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
REPO="${EP08_REPO:-/home/admin/.dsh/state/superagent/work/episode-eight-video-f134d482e964}"
DST="$REPO/视频制作/ep08-regen"
STAMP="$(date -u +%Y%m%d)"
OUT="${1:-out/ep08-regen-engine-pack.tar.gz}"
WITH_STILLS=0
[[ "${1:-}" == "--with-stills" ]] && { OUT="out/ep08-regen-engine-pack.tar.gz"; WITH_STILLS=1; }

if [[ ! -d "$DST" ]]; then
  echo "仓库同步目录不存在：$DST（先跑 scripts/sync_repo.sh）" >&2
  exit 2
fi

mkdir -p out
rm -f "$OUT"
PACK="ep08-regen-engine-pack-$STAMP"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
mkdir -p "$STAGE/$PACK"

# 1) 仓库已同步的可复现内容（scripts/work/delivery 清单/README）
cp -a "$DST/." "$STAGE/$PACK/" 2>/dev/null || true
# 2) 生产侧 work 报告/清单（sync 可能漏项时兜底）
mkdir -p "$STAGE/$PACK/work"
for f in final-check.json finalize.json render.json final-report.md assets-manifest.json \
         notes.md RUNBOOK.md cover-config.json; do
  [[ -f "work/$f" ]] && cp -f "work/$f" "$STAGE/$PACK/work/" || true
done
[[ -f audio/work/audio-report.md ]] && cp -f audio/work/audio-report.md "$STAGE/$PACK/work/"
[[ -d work/srt ]] && mkdir -p "$STAGE/$PACK/work/srt" && cp -f work/srt/*.srt "$STAGE/$PACK/work/srt/" 2>/dev/null || true
# 3) 可选：静帧/封面（交付图片，体积小，方便工程包自带）
if [[ "$WITH_STILLS" -eq 1 && -d delivery ]]; then
  mkdir -p "$STAGE/$PACK/delivery"
  find delivery -maxdepth 2 -type f \( -name '*.jpg' -o -name '*.json' \) \
    -exec cp --parents {} "$STAGE/$PACK/" \; 2>/dev/null || true
fi
# 4) 不要大文件/成片
find "$STAGE/$PACK" -type f \( -name '*.mp4' -o -name '*.wav' -o -name '*.m4a' -o -name '*.mov' \) -delete
find "$STAGE/$PACK" -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true

( cd "$STAGE" && tar -czf "$ROOT/$OUT" "$PACK" )
SIZE=$(du -h "$OUT" | cut -f1)
SHA=$(sha256sum "$OUT" | cut -d' ' -f1)
echo "engine pack -> $OUT ($SIZE)"
echo "sha256: $SHA"
cat > out/ep08-regen-engine-pack.json <<EOF
{
  "file": "$OUT",
  "size_human": "$SIZE",
  "sha256": "$SHA",
  "generated_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "contents": "scripts/ + work 报告/时间轴/SRT/清单 + README（不含成片与素材）",
  "with_stills": $WITH_STILLS
}
EOF
echo "manifest -> out/ep08-regen-engine-pack.json"
