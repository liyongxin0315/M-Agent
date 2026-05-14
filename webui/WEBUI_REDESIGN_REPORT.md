# AgentM WebUI 重做报告

**版本**: 2.0  
**日期**: 2026-04-01  
**作者**: AgentM Development Team

---

## 📋 执行摘要

### 问题背景

原有 WebUI 存在以下问题：
- ❌ 没有拖拽画布 - 只能填写表单
- ❌ 界面简陋 - 缺乏现代工作流编辑器的视觉体验
- ❌ 无法可视化编排 - 不支持节点拖拽、连接
- ❌ 与 n8n/扣子差距大 - 用户体验落后

### 解决方案

采用 **Vue 3 + Vue Flow** 技术栈，完全重写工作流编辑器，实现：
- ✅ 拖拽式节点编排
- ✅ 可视化连接线（贝塞尔曲线）
- ✅ 画布缩放/平移
- ✅ 24 种节点类型
- ✅ 属性配置面板
- ✅ 工作流保存/加载

---

## 🔍 竞品分析

### n8n 架构分析

**技术栈**:
- 前端：Vue 3 + Vite + Pinia
- 画布库：Vue Flow（@vue-flow/core）
- UI 组件：Element Plus
- 样式：SCSS + Tailwind CSS

**核心特性**:
1. 节点拖拽：从左侧面板拖拽节点到画布
2. 节点连接：通过 Handle 组件实现输入/输出端口
3. 画布交互：支持缩放、平移、框选
4. 属性面板：右侧显示选中节点的配置表单
5. 数据持久化：工作流导出为 JSON

**源码结构**（packages/frontend/editor-ui）:
```
editor-ui/
├── src/
│   ├── components/
│   │   ├── NodeCanvas/       # 画布组件
│   │   ├── NodeDetails/      # 节点详情面板
│   │   ├── NodeCreator/      # 节点创建器
│   │   └── Modals/           # 模态框
│   ├── composables/          # Vue 组合式 API
│   ├── stores/               # Pinia 状态管理
│   ├── types/                # TypeScript 类型定义
│   └── utils/                # 工具函数
```

### 扣子工作流分析

**设计特点**:
- 简洁的深色主题
- 左侧节点库分类清晰
- 画布区域占据主要空间
- 右侧属性面板采用折叠式设计
- 节点连接线使用平滑贝塞尔曲线

---

## 🏗️ 新 WebUI 架构设计

### 技术选型

| 组件 | 技术 | 说明 |
|------|------|------|
| 前端框架 | Vue 3.4+ | 组合式 API + 响应式系统 |
| 画布引擎 | Vue Flow 1.9+ | 专业的流程图画布库 |
| UI 组件库 | Element Plus | 成熟的 Vue 3 UI 库 |
| 样式方案 | Tailwind CSS + SCSS | 原子化 CSS + 预处理器 |
| 状态管理 | Pinia | Vue 官方推荐状态管理 |
| HTTP 客户端 | Axios | API 请求封装 |
| 构建工具 | Vite 5+ | 快速开发和构建 |

### 架构分层

```
┌─────────────────────────────────────────────────────────┐
│                    表现层 (Presentation)                 │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ 节点面板     │  │ 画布区域      │  │ 属性面板       │  │
│  │ NodePanel   │  │ CanvasArea   │  │ PropsPanel    │  │
│  └─────────────┘  └──────────────┘  └───────────────┘  │
├─────────────────────────────────────────────────────────┤
│                    业务层 (Business Logic)               │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ 工作流状态   │  │ 节点管理      │  │ 连接管理       │  │
│  │ WorkflowStore│  │ NodeManager  │  │ EdgeManager   │  │
│  └─────────────┘  └──────────────┘  └───────────────┘  │
├─────────────────────────────────────────────────────────┤
│                    数据层 (Data Layer)                   │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ API 服务     │  │ 本地存储      │  │ 工作流导入导出  │  │
│  │ ApiService  │  │ LocalStorage │  │ ImportExport  │  │
│  └─────────────┘  └──────────────┘  └───────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 目录结构

```
webui/
├── index.html                    # 入口 HTML
├── package.json                  # 依赖配置
├── vite.config.js               # Vite 配置
├── tailwind.config.js           # Tailwind 配置
├── src/
│   ├── main.js                  # 应用入口
│   ├── App.vue                  # 根组件
│   ├── components/
│   │   ├── NodePanel.vue        # 左侧节点面板
│   │   ├── CanvasArea.vue       # 中间画布区域
│   │   ├── PropsPanel.vue       # 右侧属性面板
│   │   ├── CustomNode.vue       # 自定义节点组件
│   │   └── Toolbar.vue          # 顶部工具栏
│   ├── stores/
│   │   ├── workflow.js          # 工作流状态管理
│   │   └── ui.js                # UI 状态管理
│   ├── services/
│   │   ├── api.js               # API 服务
│   │   └── storage.js           # 本地存储服务
│   ├── utils/
│   │   ├── nodeTypes.js         # 24 种节点类型定义
│   │   └── workflowUtils.js     # 工作流工具函数
│   └── styles/
│       ├── main.scss            # 主样式
│       └── variables.scss       # SCSS 变量
├── public/
│   └── icons/                   # 节点图标
└── README.md                    # 使用说明
```

---

## 🎨 节点类型设计 (24 种)

### 触发器节点 (4 种)

| 节点 | 图标 | 说明 |
|------|------|------|
| Webhook | 🔗 | HTTP Webhook 触发 |
| 定时任务 | ⏰ | Cron 定时触发 |
| 手动触发 | ▶️ | 手动执行工作流 |
| 事件监听 | 📡 | 监听特定事件 |

### 动作节点 (12 种)

| 节点 | 图标 | 说明 |
|------|------|------|
| HTTP 请求 | 🌐 | 发送 HTTP 请求 |
| 代码执行 | 💻 | 执行 JavaScript/Python |
| 数据库查询 | 🗄️ | SQL 查询操作 |
| 文件操作 | 📁 | 文件读写 |
| 邮件发送 | 📧 | 发送邮件 |
| API 调用 | 🔌 | 调用第三方 API |
| 数据转换 | 🔄 | 数据格式转换 |
| 条件判断 | ⚖️ | IF/ELSE 分支 |
| 循环迭代 | 🔁 | FOR/WHILE 循环 |
| 等待延迟 | ⏳ | 延迟执行 |
| 日志记录 | 📝 | 记录日志 |
| 错误处理 | ⚠️ | 异常捕获处理 |

### AI 节点 (4 种)

| 节点 | 图标 | 说明 |
|------|------|------|
| LLM 调用 | 🤖 | 调用大语言模型 |
| 文本生成 | ✍️ | AI 文本生成 |
| 图像生成 | 🎨 | AI 图像生成 |
| 语音合成 | 🎤 | TTS 语音合成 |

### 集成节点 (4 种)

| 节点 | 图标 | 说明 |
|------|------|------|
| 飞书消息 | 💬 | 发送飞书消息 |
| 钉钉消息 | 📱 | 发送钉钉消息 |
| Slack 消息 | 💭 | 发送 Slack 消息 |
| 企业微信 | 🏢 | 发送企业微信消息 |

---

## 🔧 核心功能实现

### 1. 拖拽画布

**实现方式**:
```vue
<template>
  <VueFlow
    v-model:nodes="nodes"
    v-model:edges="edges"
    :default-zoom="1"
    :min-zoom="0.2"
    :max-zoom="4"
    :fit-view-on-init="true"
    :nodes-connectable="true"
    :nodes-draggable="true"
    :edges-updatable="true"
    :edges-focusable="true"
    @node-drag-stop="onNodeDragStop"
    @connect="onConnect"
  >
    <Background pattern-color="#aaa" :gap="16" />
    <Controls />
    <MiniMap />
  </VueFlow>
</template>
```

### 2. 自定义节点

**实现方式**:
```vue
<template>
  <div :class="['custom-node', nodeType, { selected }]">
    <div class="node-header">
      <span class="node-icon">{{ icon }}</span>
      <span class="node-label">{{ label }}</span>
    </div>
    <div class="node-body">
      <slot />
    </div>
    <Handle type="target" :position="Position.Left" />
    <Handle type="source" :position="Position.Right" />
  </div>
</template>
```

### 3. 节点连接

**实现方式**:
```javascript
import { ConnectionMode, MarkerType } from '@vue-flow/core'

const onConnect = (params) => {
  addEdges({
    ...params,
    type: 'smoothstep',
    animated: true,
    markerEnd: MarkerType.ArrowClosed,
  })
}
```

### 4. 属性面板

**实现方式**:
```vue
<template>
  <div class="props-panel">
    <div v-if="selectedNode">
      <h3>{{ selectedNode.data.label }}</h3>
      <el-form :model="selectedNode.data">
        <el-form-item label="名称">
          <el-input v-model="selectedNode.data.label" />
        </el-form-item>
        <!-- 动态表单字段 -->
      </el-form>
    </div>
  </div>
</template>
```

### 5. 工作流保存/加载

**实现方式**:
```javascript
// 保存工作流
const saveWorkflow = async () => {
  const workflowData = {
    name: workflowName.value,
    nodes: nodes.value.map(n => ({
      id: n.id,
      type: n.type,
      position: n.position,
      data: n.data
    })),
    edges: edges.value.map(e => ({
      id: e.id,
      source: e.source,
      target: e.target,
      type: e.type
    }))
  }
  
  await api.saveWorkflow(workflowData)
}

// 加载工作流
const loadWorkflow = async (workflowId) => {
  const workflow = await api.loadWorkflow(workflowId)
  nodes.value = workflow.nodes
  edges.value = workflow.edges
}
```

---

## 🎯 验收标准

| 标准 | 状态 | 说明 |
|------|------|------|
| 支持节点拖拽 | ✅ | 从左侧面板拖拽到画布 |
| 支持节点连接 | ✅ | 通过 Handle 连接节点 |
| 支持画布缩放/平移 | ✅ | 鼠标滚轮缩放，拖拽平移 |
| 界面美观 | ✅ | 参考 n8n/扣子设计 |
| 24 种节点可用 | ✅ | 所有节点类型已定义 |
| 保存/加载工作流 | ✅ | 支持 JSON 导入导出 |

---

## 📊 性能指标

| 指标 | 目标值 | 说明 |
|------|--------|------|
| 首屏加载 | < 2s | 冷启动时间 |
| 节点渲染 | < 100ms | 单个节点渲染时间 |
| 画布帧率 | 60 FPS | 拖拽/缩放流畅度 |
| 工作流加载 | < 500ms | 100 节点工作流加载时间 |

---

## 🚀 部署指南

### 开发环境

```bash
cd webui
npm install
npm run dev
```

访问 http://localhost:5173

### 生产环境

```bash
npm run build
# 输出到 dist/ 目录
# 使用 Nginx 或其他 Web 服务器托管
```

### Docker 部署

```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
```

---

## 📝 后续优化

1. **性能优化**
   - 虚拟滚动（大量节点时）
   - 懒加载节点组件
   - Web Worker 处理复杂计算

2. **功能增强**
   - 工作流版本管理
   - 协作编辑（WebSocket）
   - 工作流模板市场

3. **用户体验**
   - 快捷键支持
   - 撤销/重做
   - 节点搜索/过滤

---

**报告生成时间**: 2026-04-01  
**WebUI 版本**: 2.0.0  
**状态**: 🟢 开发完成
