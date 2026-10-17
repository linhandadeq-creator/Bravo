#!/usr/bin/env bash
# 构建 Bravo 桌面应用（macOS .app，原生窗口 + 本地后端/前端）。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DESKTOP="${DESKTOP_DIR:-$HOME/Desktop}"
APP_NAME="Bravo"
APP="$DESKTOP/$APP_NAME.app"
NODE_DIR="$HOME/.local/share/neoantigen/node/bin"
UV="$HOME/.local/bin/uv"
[ -x "$UV" ] || UV="$(command -v uv || true)"
[ -x "$UV" ] || UV=""

export PATH="$NODE_DIR:$PATH"

echo "==> 1/4 构建前端（next build）"
pkill -f "next dev" 2>/dev/null || true
pkill -f "next-server" 2>/dev/null || true
sleep 1
rm -rf "$ROOT/frontend/.next"
( cd "$ROOT/frontend" && npm run build )

echo "==> 2/4 准备桌面运行时（pywebview）"
PY="$ROOT/desktop/.venv/bin/python"
if [ ! -x "$PY" ]; then
  if [ -x "$UV" ]; then
    "$UV" venv --python 3.12 "$ROOT/desktop/.venv"
  else
    echo "错误：桌面运行时缺失且未找到 uv，无法创建 desktop/.venv。" >&2
    exit 1
  fi
fi
if ! "$PY" -c "import webview" >/dev/null 2>&1; then
  if [ -x "$UV" ]; then
    "$UV" pip install --python "$PY" -r "$ROOT/desktop/requirements.txt" >/dev/null
  else
    echo "错误：pywebview 未安装且未找到 uv。" >&2
    exit 1
  fi
fi

echo "==> 3/4 生成 .app 包：$APP"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

# 应用图标（源图：desktop/bravo-icon-1024.png）
ICON_SRC="$ROOT/desktop/bravo-icon-1024.png"
ICON="$ROOT/desktop/Bravo.icns"
if [ ! -f "$ICON" ] && [ -f "$ICON_SRC" ]; then
  ICONSET="$(mktemp -d)/Bravo.iconset"
  mkdir -p "$ICONSET"
  for s in 16 32 128 256 512; do
    sips -z $s $s "$ICON_SRC" --out "$ICONSET/icon_${s}x${s}.png" >/dev/null 2>&1
    sips -z $((s*2)) $((s*2)) "$ICON_SRC" --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null 2>&1
  done
  iconutil -c icns "$ICONSET" -o "$ICON"
fi
if [ -f "$ICON" ]; then
  cp "$ICON" "$APP/Contents/Resources/Bravo.icns"
fi

cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Bravo</string>
  <key>CFBundleDisplayName</key><string>Bravo</string>
  <key>CFBundleIdentifier</key><string>ai.research.bravo.desktop</string>
  <key>CFBundleVersion</key><string>1.0.0</string>
  <key>CFBundleShortVersionString</key><string>1.0.0</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>Bravo</string>
  <key>CFBundleIconFile</key><string>Bravo</string>
  <key>LSMinimumSystemVersion</key><string>12.0</string>
  <key>LSApplicationCategoryType</key><string>public.app-category.medical</string>
  <key>LSUIElement</key><true/>
  <key>NSPrincipalClass</key><string>NSApplication</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>NSAppTransportSecurity</key>
  <dict>
    <key>NSAllowsLocalNetworking</key><true/>
    <key>NSAllowsArbitraryLoads</key><true/>
  </dict>
</dict>
</plist>
PLIST

# 主可执行文件：编译一个原生 Mach-O 启动器（可签名，Finder 双击可靠）。
cat > "$APP/Contents/MacOS/launcher.c" <<EOF
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
int main(void) {
    system("mkdir -p '$ROOT/.run'");
    freopen("$ROOT/.run/desktop.log", "a", stdout);
    freopen("$ROOT/.run/desktop.log", "a", stderr);
    execl("$ROOT/desktop/.venv/bin/python", "python",
          "$ROOT/desktop/launcher.py", (char *)0);
    return 127;
}
EOF

if command -v clang >/dev/null 2>&1; then
  clang -O2 -o "$APP/Contents/MacOS/Bravo" "$APP/Contents/MacOS/launcher.c"
  rm -f "$APP/Contents/MacOS/launcher.c"
else
  echo "警告：未找到 clang，回退到 shell 启动器。" >&2
  cat > "$APP/Contents/MacOS/Bravo" <<EOF
#!/bin/bash
mkdir -p "$ROOT/.run"
exec "$ROOT/desktop/.venv/bin/python" "$ROOT/desktop/launcher.py" >>"$ROOT/.run/desktop.log" 2>&1
EOF
  chmod +x "$APP/Contents/MacOS/Bravo"
fi
printf 'APPL????' > "$APP/Contents/PkgInfo"

# 去除隔离属性并本地 ad-hoc 签名，避免 Finder 双击被 Gatekeeper 拦截。
xattr -cr "$APP" 2>/dev/null || true
codesign --force --sign - "$APP" >/dev/null 2>&1 || true

# 兼容旧的 .command 入口
cat > "$DESKTOP/$APP_NAME.command" <<EOF
#!/bin/bash
"$ROOT/desktop/.venv/bin/python" "$ROOT/desktop/launcher.py"
EOF
chmod +x "$DESKTOP/$APP_NAME.command"

echo "==> 4/4 完成"
echo "桌面应用：$APP"
echo "（双击启动；日志：$ROOT/.run/desktop.log）"
