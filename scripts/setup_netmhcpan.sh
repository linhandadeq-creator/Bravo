#!/usr/bin/env bash
# NetMHCpan / NetMHCIIpan 许可证安装助手(DTU Health Tech)。
#
# 二进制与数据**不可再分发**:需在 DTU 官网免费申请学术许可
# (https://services.healthtech.dtu.dk/services/NetMHCpan-4.1/ 与
#  NetMHCIIpan-4.3/),接受条款后通过邮件获得下载链接。
#
# 用法(二选一):
#   ./scripts/setup_netmhcpan.sh <netMHCpan压缩包或二进制> [netMHCIIpan压缩包或二进制]
#
# 会自动:解包 → 定位可执行文件 → 写入 backend/.env
#   NETMHCPAN_BIN=...
#   NETMHCIIPAN_BIN=...
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT/backend/.env"
TOOLS_DIR="$ROOT/backend/tools/netmhc"
mkdir -p "$TOOLS_DIR"

NETMHCPAN_IN="${1:-}"
NETMHCIIPAN_IN="${2:-}"

usage() {
  cat <<'EOF'
步骤:
  1. 在 DTU Health Tech 申请免费学术许可并下载软件包:
     - NetMHCpan 4.1:  https://services.healthtech.dtu.dk/services/NetMHCpan-4.1/
     - NetMHCIIpan 4.3: https://services.healthtech.dtu.dk/services/NetMHCIIpan-4.3/
  2. 运行: ./scripts/setup_netmhcpan.sh <下载的压缩包/二进制> [<IIpan 包>]
  3. 重启平台: ./scripts/start_platform.sh
配置后 netMHCpan/netMHCIIpan 会自动加入 consensus 集成。
EOF
}

if [ -z "$NETMHCPAN_IN" ] && [ -z "$NETMHCIIPAN_IN" ]; then
  usage
  exit 0
fi

install_one() {
  local src="$1" pattern="$2" varname="$3"
  [ -z "$src" ] && return 0
  if [ -d "$src" ]; then
    local found
    found="$(find "$src" -type f -name "$pattern" -perm -u+x | head -1 || true)"
    if [ -z "$found" ]; then
      echo "FAIL 在 $src 内未找到可执行文件 $pattern" >&2
      return 1
    fi
    printf '%s=%s\n' "$varname" "$found"
    return 0
  fi
  if [ -f "$src" ] && [ -x "$src" ]; then
    printf '%s=%s\n' "$varname" "$src"
    return 0
  fi
  # 压缩包:解包后定位
  local dest="$TOOLS_DIR/$(basename "$src" | sed 's/\.[^.]*$//')"
  mkdir -p "$dest"
  case "$src" in
    *.zip) unzip -q -o "$src" -d "$dest" ;;
    *.tar.gz|*.tgz) tar -xzf "$src" -C "$dest" ;;
    *.tar) tar -xf "$src" -C "$dest" ;;
    *) echo "FAIL 无法识别包格式: $src (支持 zip/tar.gz/tar/可执行文件/目录)" >&2; return 1 ;;
  esac
  local found
  found="$(find "$dest" -type f -name "$pattern" -perm -u+x | head -1 || true)"
  if [ -z "$found" ]; then
    echo "FAIL 解包后未找到 $pattern (目录: $dest)" >&2
    return 1
  fi
  printf '%s=%s\n' "$varname" "$found"
  return 0
}

I_BIN="$(install_one "$NETMHCPAN_IN" "netMHCpan" "NETMHCPAN_BIN")"
II_BIN="$(install_one "$NETMHCIIPAN_IN" "netMHCIIpan" "NETMHCIIPAN_BIN")"

touch "$ENV_FILE"
sed -i '' '/^NETMHCPAN_BIN=/d;/^NETMHCIIPAN_BIN=/d' "$ENV_FILE"
{
  [ -z "$I_BIN" ] || echo "$I_BIN"
  [ -z "$II_BIN" ] || echo "$II_BIN"
} >> "$ENV_FILE"

echo "OK 已写入 $ENV_FILE:"
[ -z "$I_BIN" ] || echo "  $I_BIN"
[ -z "$II_BIN" ] || echo "  $II_BIN"
echo "重启平台后 netMHCpan/netMHCIIpan 将自动加入 consensus 集成。"
