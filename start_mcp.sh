#!/bin/bash
# 名片管理系统 MCP Server 启动脚本
# 供 Claude Desktop / Claude Code / 其他 AI Agent 调用

cd "$(dirname "$0")"

# 激活虚拟环境
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# 启动 MCP Server (JSON-RPC over stdio)
exec python -m app.mcp_server
