#!/usr/bin/env bash
# Build a self-contained macOS .app and .dmg (Apple Silicon).
#
# Bundles: CPython (uv-managed, relocatable), Node distribution, pip
# dependencies (site-packages), backend source, and the prebuilt Next.js
# standalone server. No system Python/Node is required on the target machine.
#
# Usage: ./scripts/build_macos_dmg.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="$ROOT/packaging/macos/build"
APP="$BUILD/Bravo.app"
RES="$APP/Contents/Resources"
STAGE="$BUILD/dmg"
DMG="$ROOT/packaging/macos/Bravo-macOS-arm64.dmg"

NODE_DIR="${NODE_DIR:-$HOME/.local/share/neoantigen/node}"
PYTHON_PREFIX="${PYTHON_PREFIX:-$("$ROOT/backend/.venv/bin/python" -c 'import sys; print(sys.base_prefix)')}"

export PATH="$NODE_DIR/bin:$PATH"

[ -d "$NODE_DIR/bin" ] || { echo "错误：未找到 Node 发行版（NODE_DIR=$NODE_DIR）" >&2; exit 1; }
[ -x "$PYTHON_PREFIX/bin/python3" ] || { echo "错误：未找到可再分发的 Python（PYTHON_PREFIX=$PYTHON_PREFIX）" >&2; exit 1; }

echo "==> 1/7 构建前端（standalone）"
pkill -f "next dev" 2>/dev/null || true
pkill -f "next-server" 2>/dev/null || true
sleep 1
rm -rf "$ROOT/frontend/.next"
( cd "$ROOT/frontend" && NEXT_PUBLIC_API_URL="" npm run build )

echo "==> 2/7 准备目录"
rm -rf "$BUILD"
mkdir -p "$APP/Contents/MacOS" "$RES/runtime" "$RES/node" "$RES/site-packages" "$RES/app/backend" "$RES/app/storage"

echo "==> 3/7 复制 Python 运行时"
cp -R "$PYTHON_PREFIX/." "$RES/runtime/"

echo "==> 4/7 安装依赖到 site-packages（较慢，含 torch）"
"$RES/runtime/bin/python3" -m pip install --quiet --disable-pip-version-check \
  --target "$RES/site-packages" -r "$ROOT/packaging/macos/requirements-mac.txt"

echo "==> 5/7 复制 Node、后端与前端"
cp -R "$NODE_DIR/." "$RES/node/"
cp -R "$ROOT/backend/app" "$ROOT/backend/alembic" "$ROOT/backend/alembic.ini" "$ROOT/backend/scripts" "$RES/app/backend/"
cp -R "$ROOT/frontend/.next/standalone/." "$RES/app/frontend/"
mkdir -p "$RES/app/frontend/.next"
cp -R "$ROOT/frontend/.next/static" "$RES/app/frontend/.next/static"
if [ -d "$ROOT/frontend/public" ]; then
  cp -R "$ROOT/frontend/public" "$RES/app/frontend/public"
fi
find "$RES/app" -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true
cp "$ROOT/packaging/macos/launcher.py" "$RES/launcher.py"
cp "$ROOT/LICENSE" "$ROOT/README.md" "$RES/"

echo "==> 6/7 生成 .app 元数据与启动器"
cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Bravo</string>
  <key>CFBundleDisplayName</key><string>Bravo</string>
  <key>CFBundleIdentifier</key><string>ai.research.bravo.bundle</string>
  <key>CFBundleVersion</key><string>1.0.0</string>
  <key>CFBundleShortVersionString</key><string>1.0.0</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>Bravo</string>
  <key>CFBundleIconFile</key><string>Bravo</string>
  <key>LSMinimumSystemVersion</key><string>12.0</string>
  <key>LSApplicationCategoryType</key><string>public.app-category.medical</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>NSAppTransportSecurity</key>
  <dict><key>NSAllowsLocalNetworking</key><true/></dict>
</dict>
</plist>
PLIST

ICON_SRC="$ROOT/desktop/bravo-icon-1024.png"
if [ -f "$ICON_SRC" ]; then
  ICONSET="$BUILD/Bravo.iconset"
  mkdir -p "$ICONSET"
  for s in 16 32 128 256 512; do
    sips -z $s $s "$ICON_SRC" --out "$ICONSET/icon_${s}x${s}.png" >/dev/null 2>&1
    sips -z $((s*2)) $((s*2)) "$ICON_SRC" --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null 2>&1
  done
  iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/Bravo.icns" 2>/dev/null || true
fi

cat > "$APP/Contents/MacOS/Bravo" <<'LAUNCH'
#!/bin/bash
DIR="$(cd "$(dirname "$0")/../Resources" && pwd)"
export PYTHONPATH="$DIR/site-packages${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONDONTWRITEBYTECODE=1
exec "$DIR/runtime/bin/python3" "$DIR/launcher.py" >> "$HOME/Library/Logs/Bravo-launcher.log" 2>&1
LAUNCH
chmod +x "$APP/Contents/MacOS/Bravo"
printf 'APPL????' > "$APP/Contents/PkgInfo"

xattr -cr "$APP" 2>/dev/null || true
codesign --force --deep --sign - "$APP" >/dev/null 2>&1 || true

echo "==> 7/7 生成 DMG"
rm -rf "$STAGE"
mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
rm -f "$DMG"
hdiutil create -volname "Bravo" -srcfolder "$STAGE" -ov -format UDZO "$DMG" >/dev/null

echo "完成：$DMG"
du -sh "$DMG"
