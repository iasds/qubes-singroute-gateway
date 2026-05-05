#!/bin/bash
# dom0 script: Set AppVM's NetVM to proxy gateway
# Usage: bash set-netvm.sh <appvm-name> [proxy-vm-name]

APPVM="$1"
PROXY_VM="${2:-sys-proxy}"

if [ -z "$APPVM" ]; then
    echo "用法: $0 <appvm名称> [proxy-vm名称]"
    echo ""
    echo "示例:"
    echo "  $0 work                    # 设置 work 的 NetVM 为 sys-proxy"
    echo "  $0 work my-proxy           # 设置 work 的 NetVM 为 my-proxy"
    exit 1
fi

# Check if running in dom0
if [ ! -f /etc/qubes-release ]; then
    echo "错误: 此脚本需要在 dom0 中运行"
    exit 1
fi

# Check if AppVM exists
if ! qvm-check "$APPVM" &>/dev/null; then
    echo "错误: AppVM '$APPVM' 不存在"
    exit 1
fi

# Check if Proxy VM exists
if ! qvm-check "$PROXY_VM" &>/dev/null; then
    echo "错误: Proxy VM '$PROXY_VM' 不存在"
    exit 1
fi

# Set NetVM
echo "设置 $APPVM 的 NetVM 为 $PROXY_VM..."
qvm-prefs "$APPVM" netvm "$PROXY_VM"

echo "完成!"
echo ""
echo "测试连通性:"
echo "  qvm-run $APPVM 'curl -s https://www.google.com'"
