#!/usr/bin/env bash
# 在桌面创建 Bravo 桌面应用入口（原生窗口）。
# 现统一由 build_desktop_app.sh 构建原生 .app + 运行时。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec "$ROOT/scripts/build_desktop_app.sh"
