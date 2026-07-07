#!/bin/bash
# 名片管理系统 - 一键部署/更新脚本
# 在阿里云服务器上运行

set -e

cd "$(dirname "$0")"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}📇 名片管理系统 - 一键部署${NC}"
echo ""

# 检查是否是第一次部署
if [ ! -d ".git" ]; then
    echo -e "${YELLOW}⚠️  检测到非 git 仓库，请先 clone 项目${NC}"
    echo ""
    echo -e "${BLUE}首次部署步骤：${NC}"
    echo "  git clone <你的仓库地址> /opt/business-card"
    echo "  cd /opt/business-card"
    echo "  ./deploy.sh"
    exit 1
fi

# 1. 备份当前数据
echo -e "${YELLOW}📦 备份当前数据...${NC}"
if [ -d "data" ]; then
    BACKUP_NAME="backup_$(date +%Y%m%d_%H%M%S).tar.gz"
    tar -czf "$BACKUP_NAME" data/ 2>/dev/null || true
    echo -e "${GREEN}   备份已保存到: $BACKUP_NAME${NC}"
fi

# 2. 拉取最新代码
echo -e "${YELLOW}🔄 拉取最新代码...${NC}"
git pull origin main || git pull origin master || true

# 3. 构建并启动服务
echo -e "${YELLOW}🐳 构建并启动 Docker 服务...${NC}"
docker-compose -f docker-compose.prod.yml pull || true
docker-compose -f docker-compose.prod.yml up -d --build

# 4. 等待服务启动
echo -e "${YELLOW}⏳ 等待服务启动...${NC}"
sleep 5

# 5. 检查服务状态
echo -e ""
echo -e "${GREEN}✅ 部署完成！${NC}"
echo ""
echo -e "${BLUE}🌐 访问地址：${NC}"
echo "   https://ai-codify.com"
echo ""
echo -e "${BLUE}📋 常用命令：${NC}"
echo "   查看日志: docker-compose -f docker-compose.prod.yml logs -f"
echo "   重启服务: docker-compose -f docker-compose.prod.yml restart"
echo "   停止服务: docker-compose -f docker-compose.prod.yml stop"
echo ""
echo -e "${YELLOW}🔄 下次更新只需再次运行: ./deploy.sh${NC}"
