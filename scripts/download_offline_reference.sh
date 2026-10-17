#!/usr/bin/env bash
# 下载并构建「完全离线注释」所需的本地参考数据（Ensembl GTF + CDS FASTA），
# 并预编译注释索引。构建完成后注释提供方 offline 即可在无网络时使用。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="${1:-GRCh38}"

case "$BUILD" in
  GRCh38) RELEASE=112; BASE="https://ftp.ensembl.org/pub/release-112" ;;
  GRCh37) RELEASE=87; BASE="https://ftp.ensembl.org/pub/grch37/release-87" ;;
  *) echo "不支持的参考版本：$BUILD（仅 GRCh38 / GRCh37）" >&2; exit 1 ;;
esac

DEST="$ROOT/backend/storage/reference/$BUILD"
mkdir -p "$DEST"
GTF="Homo_sapiens.$BUILD.$RELEASE.gtf.gz"
CDS="Homo_sapiens.$BUILD.cds.all.fa.gz"

echo "==> 下载 GTF ($GTF)"
curl -fL --retry 8 --retry-delay 3 --retry-all-errors -C - \
  --speed-time 60 --speed-limit 1024 -o "$DEST/$GTF" "$BASE/gtf/homo_sapiens/$GTF"

echo "==> 下载 CDS FASTA ($CDS)"
curl -fL --retry 8 --retry-delay 3 --retry-all-errors -C - \
  --speed-time 60 --speed-limit 1024 -o "$DEST/$CDS" "$BASE/fasta/homo_sapiens/cds/$CDS"

echo "==> 下载 ClinVar 临床相关变异（离线临床意义/rsID）"
CLIN="homo_sapiens_clinically_associated.vcf.gz"
if [ "$BUILD" = "GRCh38" ]; then
  curl -fL --retry 8 --retry-delay 3 --retry-all-errors -C - \
    -o "$DEST/$CLIN" "$BASE/variation/vcf/homo_sapiens/$CLIN"
fi

echo "==> 预编译注释索引"
( cd "$ROOT/backend" && ./.venv/bin/python - "$BUILD" <<'PY'
import sys
from app.annotation.offline import _load_index

build = sys.argv[1]
index = _load_index(build)
print(
    f"索引就绪：{len(index.transcripts)} 个转录本，Ensembl release {index.release} "
    f"（genome build {index.genome_build}）"
)
PY
)

echo "完成：$DEST"
