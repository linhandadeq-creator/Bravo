#!/usr/bin/env bash
# 下载 MHCflurry 官方 Class I Presentation 模型（models_class1_presentation）。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND="$ROOT/backend"

if [ ! -x "$BACKEND/.venv/bin/mhcflurry-downloads" ]; then
  echo "错误：未找到 mhcflurry（$BACKEND/.venv）。请先安装后端依赖。" >&2
  exit 1
fi

echo "下载 models_class1_presentation …"
"$BACKEND/.venv/bin/mhcflurry-downloads" fetch models_class1_presentation
echo "模型目录：$("$BACKEND/.venv/bin/mhcflurry-downloads" path models_class1_presentation)"
