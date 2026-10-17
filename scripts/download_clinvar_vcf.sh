#!/usr/bin/env bash
# Download the NCBI ClinVar weekly release VCF for the variant-evidence engine
# and build its tabix index. Fully offline at query time afterwards.
#
# Usage:
#   ./scripts/download_clinvar_vcf.sh            # stores under backend/storage/evidence/clinvar/
#   CLINVAR_EVIDENCE_VCF=/custom/clinvar.vcf.gz ./scripts/download_clinvar_vcf.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST_DIR="${CLINVAR_EVIDENCE_VCF_DIR:-$ROOT/backend/storage/evidence/clinvar}"
mkdir -p "$DEST_DIR"

URL="https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/clinvar.vcf.gz"
DEST="$DEST_DIR/clinvar.vcf.gz"

if [ -f "$DEST" ]; then
  echo "Already present: $DEST"
else
  echo "Downloading ClinVar (GRCh38) ..."
  curl -L --fail --retry 3 -o "$DEST.part" "$URL"
  mv "$DEST.part" "$DEST"
fi

echo "Building tabix index ..."
if [ -x "$ROOT/backend/.venv/bin/tabix" ]; then
  "$ROOT/backend/.venv/bin/tabix" -f -p vcf "$DEST"
elif command -v tabix >/dev/null 2>&1; then
  tabix -f -p vcf "$DEST"
else
  "$ROOT/backend/.venv/bin/python" - <<'PY'
import pysam
import os
pysam.tabix_index(os.environ["_CLINVAR_DEST"], preset="vcf", force=True)
PY
fi

echo "Done: $DEST"
echo "Set CLINVAR_EVIDENCE_VCF=$DEST in backend/.env (or rely on auto-detection)."
echo "Note: this is the GRCh38 VCF; the provider also accepts a GRCh37 file if set explicitly."
