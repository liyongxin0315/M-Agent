#!/bin/bash
# AgentM Core 停止脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "停止 AgentM Core 服务..."

# 读取 PID 文件
if [ -f "data/pids.txt" ]; then
    source data/pids.txt
    
    kill $event_bus 2>/dev/null || true
    kill $memory_store 2>/dev/null || true
    kill $scheduler 2>/dev/null || true
    kill $autonomous_loop 2>/dev/null || true
    kill $api_server 2>/dev/null || true
    
    echo "服务已停止"
    rm -f data/pids.txt
else
    # 尝试通过进程名停止
    pkill -f "python3 src/event_bus.py" 2>/dev/null || true
    pkill -f "python3 src/memory_store.py" 2>/dev/null || true
    pkill -f "python3 src/scheduler.py" 2>/dev/null || true
    pkill -f "python3 src/autonomous_loop.py" 2>/dev/null || true
    pkill -f "python3 src/api_server.py" 2>/dev/null || true
    pkill -f "uvicorn api_server:app" 2>/dev/null || true
    
    echo "服务已停止（通过进程名）"
fi

echo "完成"
