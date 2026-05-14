# M-Agent

**本地思考 · 自进化 · 数字分身**

> 一个具备离线思考能力的 Agent 框架，核心设计面向 AGI 时代

---

## 核心架构

```
M-Agent = ⟨G, S, M, K, F, π, U, L, Φ_C, Φ_M, Φ_V⟩

G  - 目标空间      任务目标 + 自进化目标
S  - 状态空间      外部态 + 自身结构态
M  - 记忆空间      任务轨迹 + 进化历史
K  - 知识空间      领域知识 + 自修改公理
F  - 动作空间      任务动作 + 自修改动作
π  - 策略         任务策略 + 进化决策策略
U  - 效用函数     任务效用 + 结构效用
L  - 学习算子     任务学习 + 元学习
Φ_C - 元认知      自诊断
Φ_M - 元修改      自重构
Φ_V - 元验证      自校验
```

## 核心特性

- 🌐 **离线优先** - 无网络可用时仍能思考
- 🔄 **自进化闭环** - Φ_C → Φ_M → Φ_V 持续自我改进
- 🛡️ **符号验证** - Z3 形式化验证，代码正确性有数学保证
- 🧠 **双脑推理** - LLM（创意）+ Z3（验证）混合架构
- 📈 **渐进式升级** - 简单任务快速响应，复杂任务自动深入

## 技术栈

| 模块 | 技术 |
|------|------|
| LLM 推理 | Ollama + qwen3:8b + deepseek-coder:6.7b |
| 符号引擎 | Z3 SMT Solver |
| 记忆 | ChromaDB + Sentence-Transformers |
| API | FastAPI |
| 接口 | CLI / API / Web / ROS2 |

## 快速开始

```bash
# 1. 安装依赖
pip install -e D:\agentm

# 2. 下载模型
ollama pull qwen3:8b-q4_K_M
ollama pull deepseek-coder:6.7b-instruct-q4_K_M

# 3. 启动 Ollama
ollama serve

# 4. 启动 API（端口 8766）
python -m agentm.interfaces.api.main

# 5. 访问网页界面
# http://localhost:8766
```

## 目录结构

```
D:\agentm\
├── src/agentm/           # 核心源码
│   ├── core/             # 核心引擎（LLM / Z3 / 路由）
│   ├── agents/          # 子Agent（执行Agent）
│   ├── main_agent/       # 主Agent（协调层）
│   ├── memory/          # 记忆系统（ChromaDB）
│   ├── knowledge/       # 知识库（代码规范）
│   ├── evaluation/      # 评估系统（Benchmark）
│   ├── learning/        # 学习系统（策略学习）
│   ├── evolution/        # 自进化系统
│   └── interfaces/      # 接口层（CLI/API/Web/ROS2）
├── configs/              # 配置文件
├── models/              # Ollama 模型（需单独下载）
├── sandbox/             # 沙箱（自进化用）
├── logs/                # 日志
└── tests/              # 测试
```

## 执行流程

```
任务进来
    ↓
默认简单模式（LLM → Z3 抽检）
    ↓
通过？→ 结束，存入记忆
失败？→ 自动升级复杂模式（LLM多候选 → Z3严格验证）
    ↓
任务结束 / 项目结束
    ↓
自进化系统检查：这次比上次进步了吗？
```

## 模型说明

| 模型 | 用途 | VRAM |
|------|------|------|
| qwen3:8b-q4_K_M | 通用推理、意图理解 | ~6GB |
| deepseek-coder:6.7b | 代码生成、审查、调试 | ~5.5GB |

## 状态

🟡 **开发中** - 所有核心模块已完成，待实际运行验证
