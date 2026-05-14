# AgentM 整合指南

## 项目整合完成 ✅

### 整合内容

#### 1. 核心模块（src/core/）
- `event_bus.py` - 事件总线
- `memory_store.py` - 记忆存储
- `scheduler.py` - 任务调度器
- `autonomous_loop.py` - 自主决策循环
- `api_server.py` - HTTP API 服务

#### 2. 启动脚本
- `start_agentm.sh` - 启动所有服务
- `stop_agentm.sh` - 停止所有服务
- `status_agentm.sh` - 状态检查

#### 3. 配置文件
- `config.agentm_core.yaml` - 自主 Agent 配置

### 启动方式

#### 方式 1：启动完整系统
```bash
cd /home/liyongxin/.openclaw/workspace/agentm
./start_agentm.sh
```

#### 方式 2：只启动 WebUI
```bash
cd /home/liyongxin/.openclaw/workspace/agentm/webui
npm run dev
```

#### 方式 3：只启动自主 Agent
```bash
cd /home/liyongxin/.openclaw/workspace/agentm
python3 src/core/api_server.py
```

### 项目结构

```
agentm/
├── src/
│   ├── core/              # 自主 Agent 核心（新增）
│   │   ├── event_bus.py
│   │   ├── memory_store.py
│   │   ├── scheduler.py
│   │   ├── autonomous_loop.py
│   │   └── api_server.py
│   ├── middleware.py      # 工作流中间件
│   ├── sandbox.py         # 沙箱系统
│   ├── memory.py          # 记忆系统
│   └── ...
├── webui/                 # Web 界面
├── workflows/             # 工作流示例
├── docs/                  # 文档
└── config.yaml            # 配置文件
```

### 下一步

1. **启动系统** - `./start_agentm.sh`
2. **访问 WebUI** - http://localhost:3000
3. **创建工作流** - 导入姜恒踏仙途世界观
4. **生成小说章节** - 运行工作流

### 注意事项

- 数据目录 `agentm_data/` 会自动创建
- 首次启动需要安装依赖：`pip install -r requirements.txt`
- WebUI 需要 Node.js 和 npm
