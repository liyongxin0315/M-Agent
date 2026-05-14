#!/bin/bash
# AgentM API Server 启动脚本

# 设置 PYTHONPATH
export PYTHONPATH="/home/liyongxin/.openclaw/workspace/agentm/src:$PYTHONPATH"

# 设置 Tavily API Key
export TAVILY_API_KEY="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"

# 进入目录
cd /home/liyongxin/.openclaw/workspace/agentm/src

# 启动服务
exec python3 api_server.py --port 8765
