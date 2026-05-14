#!/bin/bash
# AgentM Core 状态检查脚本

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "================================"
echo "  AgentM Core 状态检查"
echo "================================"

# 检查 PID 文件
if [ -f "data/pids.txt" ]; then
    source data/pids.txt
    
    check_service() {
        local name=$1
        local pid=$2
        if kill -0 $pid 2>/dev/null; then
            echo "  ✓ $name (PID: $pid) - 运行中"
        else
            echo "  ✗ $name (PID: $pid) - 已停止"
        fi
    }
    
    check_service "事件总线" $event_bus
    check_service "记忆存储" $memory_store
    check_service "任务调度器" $scheduler
    check_service "自主决策" $autonomous_loop
    check_service "API 服务器" $api_server
else
    echo "  PID 文件不存在，尝试通过进程名检查..."
    
    pgrep -f "python3 src/event_bus.py" > /dev/null && echo "  ✓ 事件总线 - 运行中" || echo "  ✗ 事件总线 - 未运行"
    pgrep -f "python3 src/memory_store.py" > /dev/null && echo "  ✓ 记忆存储 - 运行中" || echo "  ✗ 记忆存储 - 未运行"
    pgrep -f "python3 src/scheduler.py" > /dev/null && echo "  ✓ 任务调度器 - 运行中" || echo "  ✗ 任务调度器 - 未运行"
    pgrep -f "python3 src/autonomous_loop.py" > /dev/null && echo "  ✓ 自主决策 - 运行中" || echo "  ✗ 自主决策 - 未运行"
    pgrep -f "uvicorn api_server:app" > /dev/null && echo "  ✓ API 服务器 - 运行中" || echo "  ✗ API 服务器 - 未运行"
fi

# 检查 API 服务器
echo -e "\nAPI 服务器检查:"
if curl -s http://127.0.0.1:8765/ > /dev/null 2>&1; then
    echo "  ✓ API 服务器可访问 (http://127.0.0.1:8765)"
    
    # 获取状态
    STATUS=$(curl -s http://127.0.0.1:8765/api/v1/status -H "X-API-Key: agentm-secret-key-change-me" 2>/dev/null)
    if [ -n "$STATUS" ]; then
        echo -e "\n  系统状态:"
        echo "  $STATUS" | python3 -m json.tool 2>/dev/null | sed 's/^/    /'
    fi
else
    echo "  ✗ API 服务器不可访问"
fi

# 磁盘使用
echo -e "\n磁盘使用:"
du -sh data/ 2>/dev/null | awk '{print "  数据目录: " $1}'

echo -e "\n================================"
