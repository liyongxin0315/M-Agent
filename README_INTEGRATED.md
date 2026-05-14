# AgentM 整合版 - 自主 Agent 工作流平台

## 项目结构

```
agentm/
├── src/
│   ├── core/              # 自主 Agent 核心（新增）
│   │   ├── event_bus.py   # 事件总线
│   │   ├── memory_store.py # 记忆存储
│   │   ├── scheduler.py   # 任务调度器
│   │   ├── autonomous_loop.py # 自主决策
│   │   └── api_server.py  # HTTP API 服务
│   ├── middleware.py      # 中间件链
│   ├── sandbox.py         # 沙箱系统
│   ├── memory.py          # 记忆系统
│   ├── sse_server.py      # SSE 流式
│   └── ...
├── skills/                # 内部技能
├── skills_external/       # 外部技能
├── webui/                 # Web 界面
├── workflows/             # 工作流示例
└── docs/                  # 文档
```

## 启动方式

### 方式 1：启动完整系统（工作流 + 自主 Agent）
```bash
cd /home/liyongxin/.openclaw/workspace/agentm
./start_agentm.sh
```

### 方式 2：只启动工作流平台
```bash
cd /home/liyongxin/.openclaw/workspace/agentm/webui
npm run dev
```

### 方式 3：只启动自主 Agent 核心
```bash
cd /home/liyongxin/.openclaw/workspace/agentm
python3 src/core/api_server.py
```

## 功能特性

### 工作流平台
- ✅ 可视化工作流编辑器
- ✅ 24+ 种节点类型
- ✅ Skill 系统集成
- ✅ 工作流执行引擎

### 自主 Agent 核心
- ✅ 事件驱动机制
- ✅ 记忆共享系统
- ✅ 任务调度器
- ✅ 自主决策循环

## API 接口

### 工作流 API
- `POST /api/v1/workflows` - 创建工作流
- `GET /api/v1/workflows` - 获取工作流列表
- `POST /api/v1/workflows/{id}/run` - 运行工作流

### 自主 Agent API
- `POST /api/v1/goals` - 设置目标
- `GET /api/v1/memories` - 检索记忆
- `GET /api/v1/status` - 系统状态

## 快速开始

### 1. 启动系统
```bash
./start_agentm.sh
```

### 2. 访问 WebUI
http://localhost:3000

### 3. 访问 API
```bash
curl http://127.0.0.1:8765/api/v1/status
```

## 文档

- [架构设计](docs/agentm_core_ARCHITECTURE.md)
- [API 参考](docs/agentm_core_API_REFERENCE.md)
- [部署指南](docs/agentm_core_DEPLOYMENT.md)
- [使用指南](docs/agentm_core_USER_GUIDE.md)
```
echo "✅ README 已更新"
