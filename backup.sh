#!/bin/bash
# 名片管理系统 - 数据备份脚本

cd "$(dirname "$0")"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

BACKUP_DIR="./backups"
BACKUP_NAME="backup_$(date +%Y%m%d_%H%M%S).tar.gz"

mkdir -p "$BACKUP_DIR"

echo -e "${GREEN}📦 正在备份数据...${NC}"

if [ -d "data" ]; then
    tar -czf "$BACKUP_DIR/$BACKUP_NAME" data/
    echo -e "${GREEN}✅ 备份完成: $BACKUP_DIR/$BACKUP_NAME${NC}"

    # 只保留最近7天的备份
    echo -e "${YELLOW}🗑️  清理旧备份（保留最近7天）...${NC}"
    find "$BACKUP_DIR" -name "backup_*.tar.gz" -mtime +7 -delete

    # 显示当前备份列表
    echo ""
    echo -e "${GREEN}📋 当前备份列表：${NC}"
    ls -lh "$BACKUP_DIR"
else
    echo -e "${RED}❌ 未找到 data 目录${NC}"
    exit 1
fi
