#!/bin/bash
# Test connectivity from AppVM
# Usage: bash test-connectivity.sh

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=== 连通性测试 ==="
echo ""

# Test DNS
echo -n "DNS 解析: "
if nslookup google.com > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
fi

# Test domestic sites
echo ""
echo "国内站点:"
for site in baidu.com qq.com taobao.com; do
    echo -n "  $site: "
    code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "https://www.$site" 2>/dev/null)
    if [ "$code" = "200" ] || [ "$code" = "301" ] || [ "$code" = "302" ]; then
        echo -e "${GREEN}$code${NC}"
    else
        echo -e "${RED}$code${NC}"
    fi
done

# Test foreign sites
echo ""
echo "国外站点:"
for site in google.com github.com youtube.com; do
    echo -n "  $site: "
    code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 10 --max-time 15 "https://www.$site" 2>/dev/null)
    if [ "$code" = "200" ] || [ "$code" = "301" ] || [ "$code" = "302" ]; then
        echo -e "${GREEN}$code${NC}"
    else
        echo -e "${RED}$code${NC}"
    fi
done

# Test exit IP
echo ""
echo -n "出口 IP: "
ip=$(curl -s --connect-timeout 5 https://api.ipify.org 2>/dev/null)
if [ -n "$ip" ]; then
    echo -e "${GREEN}$ip${NC}"
else
    echo -e "${RED}获取失败${NC}"
fi

echo ""
echo "=== 测试完成 ==="
