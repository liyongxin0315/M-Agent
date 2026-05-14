#!/bin/bash
# AgentM Core 启动脚本
# 启动所有核心服务

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 获取脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}  AgentM Core 启动脚本${NC}"
echo -e "${GREEN}================================${NC}"

# 检查 Python 版本
echo -e "\n${YELLOW}[1/5] 检查 Python 环境...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误：未找到 python3${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python 版本：$PYTHON_VERSION"

# 检查并安装依赖
echo -e "\n${YELLOW}[2/5] 检查依赖...${NC}"
if [ ! -d "venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
fi

echo "激活虚拟环境..."
source venv/bin/activate

echo "安装/更新依赖..."
pip install -q -r requirements.txt

# 创建数据目录
echo -e "\n${YELLOW}[3/5] 创建数据目录...${NC}"
mkdir -p data/chroma
mkdir -p data/logs
echo "数据目录已准备"

# 停止已有进程
echo -e "\n${YELLOW}[4/5] 停止已有进程...${NC}"
pkill -f "python3 src/event_bus.py" 2>/dev/null || true
pkill -f "python3 src/memory_store.py" 2>/dev/null || true
pkill -f "python3 src/scheduler.py" 2>/dev/null || true
pkill -f "python3 src/autonomous_loop.py" 2>/dev/null || true
pkill -f "python3 src/api_server.py" 2>/dev/null || true
pkill -f "uvicorn api_server:app" 2>/dev/null || true
sleep 1
echo "已有进程已停止"

# 启动服务
echo -e "\n${YELLOW}[5/5] 启动服务...${NC}"

# 启动事件总线
echo "启动事件总线..."
nohup python3 src/event_bus.py > data/logs/event_bus.log 2>&1 &
EVENT_BUS_PID=$!
echo "  事件总线 PID: $EVENT_BUS_PID"

# 启动记忆存储
echo "启动记忆存储..."
nohup python3 src/memory_store.py > data/logs/memory_store.log 2>&1 &
MEMORY_STORE_PID=$!
echo "  记忆存储 PID: $MEMORY_STORE_PID"

# 启动任务调度器
echo "启动任务调度器..."
nohup python3 src/scheduler.py > data/logs/scheduler.log 2>&1 &
SCHEDULER_PID=$!
echo "  任务调度器 PID: $SCHEDULER_PID"

# 启动自主决策循环
echo "启动自主决策循环..."
nohup python3 src/autonomous_loop.py > data/logs/autonomous_loop.log 2>&1 &
AUTONOMOUS_PID=$!
echo "  自主决策 PID: $AUTONOMOUS_PID"

# 启动 API 服务器
echo "启动 API 服务器..."
nohup python3 src/api_server.py > data/logs/api_server.log 2>&1 &
API_SERVER_PID=$!
echo "  API 服务器 PID: $API_SERVER_PID"

# 等待 API 服务器启动
echo -e "\n${YELLOW}等待 API 服务器启动...${NC}"
sleep 3

# 检查服务状态
echo -e "\n${GREEN}================================${NC}"
echo -e "${GREEN}  服务状态检查${NC}"
echo -e "${GREEN}================================${NC}"

check_service() {
    local name=$1
    local pid=$2
    if kill -0 $pid 2>/dev/null; then
        echo -e "  ${GREEN}✓${NC} $name (PID: $pid) - 运行中"
        return 0
    else
        echo -e "  ${RED}✗${NC} $name (PID: $pid) - 已停止"
        return 1
    fi
}

FAILED=0
check_service "事件总线" $EVENT_BUS_PID || FAILED=$((FAILED+1))
check_service "记忆存储" $MEMORY_STORE_PID || FAILED=$((FAILED+1))
check_service "任务调度器" $SCHEDULER_PID || FAILED=$((FAILED+1))
check_service "自主决策" $AUTONOMOUS_PID || FAILED=$((FAILED+1))
check_service "API 服务器" $API_SERVER_PID || FAILED=$((FAILED+1))

# 保存 PID 文件
echo -e "\n${YELLOW}保存 PID 文件...${NC}"
cat > data/pids.txt << EOF
event_bus=$EVENT_BUS_PID
memory_store=$MEMORY_STORE_PID
scheduler=$SCHEDULER_PID
autonomous_loop=$AUTONOMOUS_PID
api_server=$API_SERVER_PID
EOF

echo -e "\n${GREEN}================================${NC}"
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}  AgentM Core 已成功启动！${NC}"
    echo -e "${GREEN}================================${NC}"
    echo -e "\n${YELLOW}API 地址：${NC}http://127.0.0.1:8765"
    echo -e "${YELLOW}API 文档：${NC}http://127.0.0.1:8765/docs"
    echo -e "${YELLOW}日志目录：${NC}$SCRIPT_DIR/data/logs/"
    echo -e "\n${YELLOW}停止服务：${NC}./stop.sh"
    echo -e "${YELLOW}查看状态：${NC}./status.sh"
else
    echo -e "${RED}================================${NC}"
    echo -e "${RED}  部分服务启动失败 ($FAILED/5)${NC}"
    echo -e "${RED}================================${NC}"
    echo -e "\n${YELLOW}请检查日志文件：${NC}"
    echo "  - data/logs/event_bus.log"
    echo "  - data/logs/memory_store.log"
    echo "  - data/logs/scheduler.log"
    echo "  - data/logs/autonomous_loop.log"
    echo "  - data/logs/api_server.log"
    exit 1
fi
