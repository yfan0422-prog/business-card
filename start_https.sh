#!/bin/bash
# 名片管理系统一键启动脚本（HTTPS版本，支持摄像头功能）

cd "$(dirname "$0")"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}📇 名片管理系统启动脚本（HTTPS版本）${NC}"
echo ""

# 获取本机 IP 地址
LOCAL_IP=$(ifconfig | grep "inet " | grep -v 127.0.0.1 | awk '{print $2}' | head -n1 2>/dev/null || true)
if [ -z "$LOCAL_IP" ]; then
    LOCAL_IP="127.0.0.1"
fi

# 检查是否安装 Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ 请先安装 Python 3${NC}"
    exit 1
fi

# 检查虚拟环境，没有则创建
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}🔧 正在创建虚拟环境...${NC}"
    python3 -m venv venv
fi

# 激活虚拟环境并安装依赖
echo -e "${YELLOW}📦 检查依赖...${NC}"
source venv/bin/activate
pip install -q -r requirements.txt

echo ""
echo -e "${GREEN}🌐 访问地址：${NC}"
echo -e "   本机（推荐）：${YELLOW}https://localhost:8443/${NC}"
if [ "$LOCAL_IP" != "127.0.0.1" ]; then
    echo -e "   手机局域网访问：${YELLOW}https://$LOCAL_IP:8443/${NC}"
fi
echo ""
echo -e "${YELLOW}⚠️  注意：${NC}"
echo -e "   1. 浏览器会提示「不安全」，这是自签名证书导致的，点击「继续访问」即可"
echo -e "   2. HTTPS是使用摄像头的前提（浏览器安全策略要求）"
echo -e "   3. 建议用 Safari、Chrome、Edge 等现代浏览器"
echo ""
echo -e "${GREEN}📱 手机使用说明：${NC}"
echo -e "   1. 确保手机和 Mac 在同一 WiFi"
echo -e "   2. 在手机浏览器打开上面的局域网地址"
echo -e "   3. 点击浏览器菜单 →「添加到主屏幕」，像 App 一样使用"
echo ""
echo -e "${YELLOW}⏳ 正在启动服务...${NC}"
echo ""

# 启动服务（使用HTTPS）
uvicorn app.main:app --reload --host 0.0.0.0 --port 8443 --ssl-keyfile=certs/key.pem --ssl-certfile=certs/cert.pem
