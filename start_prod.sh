#!/bin/bash
# 名片管理系统 - 生产环境启动脚本（阿里云轻量服务器）
# 使用方式: ./start_prod.sh

cd "$(dirname "$0")"

# 激活虚拟环境
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "首次运行，正在创建虚拟环境..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
fi

# 确保 data 目录存在（从 .env 读取路径，默认项目内 data/）
if [ -f ".env" ]; then
    DATA_DIR=$(grep -oP 'DATA_DIR=\K.*' .env || echo "data")
else
    DATA_DIR="data"
fi
mkdir -p "$DATA_DIR/db" "$DATA_DIR/photos" "$DATA_DIR/avatars"

# 启动服务
python3 -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 2
