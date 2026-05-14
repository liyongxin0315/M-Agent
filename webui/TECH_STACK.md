# AgentM WebUI 技术栈说明

**版本**: 2.0  
**日期**: 2026-04-01

---

## 📦 核心技术栈

### 前端框架

| 技术 | 版本 | 用途 | 官网 |
|------|------|------|------|
| Vue.js | 3.4+ | 核心框架 | https://vuejs.org |
| Vite | 5.0+ | 构建工具 | https://vitejs.dev |
| Vue Router | 4.2+ | 路由管理 | https://router.vuejs.org |
| Pinia | 2.1+ | 状态管理 | https://pinia.vuejs.org |

### 画布引擎

| 技术 | 版本 | 用途 | 官网 |
|------|------|------|------|
| Vue Flow | 1.9+ | 流程图画布 | https://vueflow.dev |
| @vue-flow/core | 1.9+ | 核心功能 | - |
| @vue-flow/background | 1.9+ | 背景网格 | - |
| @vue-flow/controls | 1.9+ | 缩放控件 | - |
| @vue-flow/minimap | 1.9+ | 小地图 | - |

### UI 组件库

| 技术 | 版本 | 用途 | 官网 |
|------|------|------|------|
| Element Plus | 2.4+ | UI 组件 | https://element-plus.org |
| @element-plus/icons-vue | 2.3+ | 图标库 | - |

### 样式方案

| 技术 | 版本 | 用途 | 官网 |
|------|------|------|------|
| Tailwind CSS | 3.4+ | 原子化 CSS | https://tailwindcss.com |
| SCSS | 1.69+ | CSS 预处理器 | https://sass-lang.com |
| Autoprefixer | 10.4+ | CSS 前缀自动添加 | - |

### 工具库

| 技术 | 版本 | 用途 | 官网 |
|------|------|------|------|
| Axios | 1.6+ | HTTP 客户端 | https://axios-http.com |
| Day.js | 1.11+ | 日期处理 | https://day.js.org |
| Lodash-es | 4.17+ | 工具函数 | https://lodash.com |
| UUID | 9.0+ | 唯一 ID 生成 | https://github.com/uuidjs/uuid |

### 开发工具

| 技术 | 版本 | 用途 |
|------|------|------|
| TypeScript | 5.3+ | 类型系统 |
| ESLint | 8.55+ | 代码检查 |
| Prettier | 3.1+ | 代码格式化 |
| Vitest | 1.1+ | 单元测试 |
| Playwright | 1.40+ | E2E 测试 |

---

## 🏗️ 架构设计

### 分层架构

```
┌─────────────────────────────────────────┐
│          View Layer (视图层)             │
│  ┌─────────┐ ┌──────────┐ ┌──────────┐ │
│  │NodePanel│ │CanvasArea│ │PropsPanel│ │
│  └─────────┘ └──────────┘ └──────────┘ │
├─────────────────────────────────────────┤
│       ViewModel Layer (视图模型层)        │
│  ┌─────────────────────────────────┐   │
│  │     Composables (组合式 API)     │   │
│  │  - useWorkflow                  │   │
│  │  - useNodeDrag                  │   │
│  │  - useConnection                │   │
│  └─────────────────────────────────┘   │
├─────────────────────────────────────────┤
│        Store Layer (状态管理层)          │
│  ┌─────────────┐ ┌─────────────────┐   │
│  │workflowStore│ │     uiStore     │   │
│  └─────────────┘ └─────────────────┘   │
├─────────────────────────────────────────┤
│         Service Layer (服务层)           │
│  ┌─────────────┐ ┌─────────────────┐   │
│  │  apiService │ │  storageService │   │
│  └─────────────┘ └─────────────────┘   │
└─────────────────────────────────────────┘
```

### 数据流

```
用户操作 → 组件事件 → Composables → Store → Service → API
    ↑                                              ↓
    └────────────── 响应式更新 ←───────────────────┘
```

---

## 📁 目录结构详解

```
webui/
├── index.html                    # HTML 入口
├── package.json                  # 依赖配置
├── pnpm-lock.yaml               # 依赖锁定
├── vite.config.js               # Vite 配置
├── tailwind.config.js           # Tailwind 配置
├── postcss.config.js            # PostCSS 配置
├── tsconfig.json                # TypeScript 配置
├── .eslintrc.cjs                # ESLint 配置
├── .prettierrc                  # Prettier 配置
│
├── public/                       # 静态资源
│   ├── favicon.ico
│   └── icons/                   # 节点图标
│       ├── webhook.svg
│       ├── timer.svg
│       ├── http.svg
│       └── ...
│
├── src/                          # 源代码
│   ├── main.js                  # 应用入口
│   ├── App.vue                  # 根组件
│   │
│   ├── components/              # 组件
│   │   ├── layout/
│   │   │   ├── Header.vue       # 顶部导航
│   │   │   ├── Sidebar.vue      # 侧边栏
│   │   │   └── Footer.vue       # 底部状态栏
│   │   │
│   │   ├── canvas/
│   │   │   ├── WorkflowCanvas.vue  # 主画布
│   │   │   ├── CustomNode.vue      # 自定义节点
│   │   │   ├── NodeToolbar.vue     # 节点工具栏
│   │   │   └── ConnectionLine.vue  # 连接线
│   │   │
│   │   ├── panel/
│   │   │   ├── NodePanel.vue       # 节点库面板
│   │   │   ├── PropsPanel.vue      # 属性配置面板
│   │   │   └── ExecPanel.vue       # 执行结果面板
│   │   │
│   │   ├── node/
│   │   │   ├── TriggerNode.vue     # 触发器节点
│   │   │   ├── ActionNode.vue      # 动作节点
│   │   │   ├── AINode.vue          # AI 节点
│   │   │   └── IntegrationNode.vue # 集成节点
│   │   │
│   │   └── common/
│   │       ├── Modal.vue           # 模态框
│   │       ├── Confirm.vue         # 确认框
│   │       └── Loading.vue         # 加载动画
│   │
│   ├── stores/                  # Pinia 状态管理
│   │   ├── workflow.js          # 工作流状态
│   │   ├── ui.js                # UI 状态
│   │   └── user.js              # 用户状态
│   │
│   ├── composables/             # 组合式 API
│   │   ├── useWorkflow.js       # 工作流逻辑
│   │   ├── useNodeDrag.js       # 拖拽逻辑
│   │   ├── useConnection.js     # 连接逻辑
│   │   ├── useKeyboard.js       # 快捷键
│   │   └── useLocalStorage.js   # 本地存储
│   │
│   ├── services/                # 服务层
│   │   ├── api.js               # API 封装
│   │   ├── workflow.js          # 工作流服务
│   │   ├── execution.js         # 执行服务
│   │   └── storage.js           # 存储服务
│   │
│   ├── utils/                   # 工具函数
│   │   ├── nodeTypes.js         # 节点类型定义
│   │   ├── workflowUtils.js     # 工作流工具
│   │   ├── validators.js        # 验证器
│   │   └── constants.js         # 常量定义
│   │
│   ├── styles/                  # 样式
│   │   ├── main.scss            # 主样式
│   │   ├── variables.scss       # SCSS 变量
│   │   ├── mixins.scss          # SCSS 混合
│   │   └── themes/
│   │       ├── light.scss       # 浅色主题
│   │       └── dark.scss        # 深色主题
│   │
│   └── router/                  # 路由配置
│       └── index.js
│
├── tests/                        # 测试
│   ├── unit/                    # 单元测试
│   │   ├── components/
│   │   ├── stores/
│   │   └── utils/
│   │
│   └── e2e/                     # E2E 测试
│       ├── specs/
│       └── fixtures/
│
└── docs/                         # 文档
    ├── API.md                   # API 文档
    ├── COMPONENTS.md            # 组件文档
    └── DEPLOYMENT.md            # 部署文档
```

---

## 🔌 Vue Flow 核心 API

### 基础用法

```javascript
import { VueFlow, useVueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'

const { 
  addNodes, 
  removeNodes, 
  addEdges, 
  removeEdges,
  onConnect,
  onNodeDragStop
} = useVueFlow()
```

### 自定义节点

```javascript
// 注册自定义节点
import CustomNode from './CustomNode.vue'

const nodeTypes = {
  custom: CustomNode,
  trigger: TriggerNode,
  action: ActionNode,
  ai: AINode
}

// 在 VueFlow 中使用
<VueFlow :node-types="nodeTypes" />
```

### 节点数据结构

```javascript
const nodes = ref([
  {
    id: '1',
    type: 'custom',
    position: { x: 100, y: 100 },
    data: {
      label: 'HTTP 请求',
      nodeType: 'action',
      config: {
        method: 'GET',
        url: 'https://api.example.com'
      }
    },
    class: 'node-http'
  }
])

const edges = ref([
  {
    id: 'e1-2',
    source: '1',
    target: '2',
    type: 'smoothstep',
    label: '成功',
    style: { stroke: '#27ae60' }
  }
])
```

---

## 🎨 设计规范

### 颜色系统

```scss
// 主色调
$primary: #3498db;      // 蓝色
$success: #27ae60;      // 绿色
$warning: #f39c12;      // 橙色
$danger: #e74c3c;       // 红色
$info: #1abc9c;         // 青色

// 中性色
$gray-50: #f9fafb;
$gray-100: #f3f4f6;
$gray-200: #e5e7eb;
$gray-300: #d1d5db;
$gray-400: #9ca3af;
$gray-500: #6b7280;
$gray-600: #4b5563;
$gray-700: #374151;
$gray-800: #1f2937;
$gray-900: #111827;

// 节点颜色
$node-trigger: #9b59b6;   // 紫色
$node-action: #3498db;    // 蓝色
$node-ai: #e74c3c;        // 红色
$node-integration: #27ae60; // 绿色
```

### 节点样式

```scss
.workflow-node {
  min-width: 180px;
  min-height: 60px;
  border-radius: 8px;
  border: 2px solid transparent;
  background: white;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  transition: all 0.2s;

  &:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
  }

  &.selected {
    border-color: $primary;
    box-shadow: 0 0 0 4px rgba($primary, 0.2);
  }

  &.trigger { border-left: 4px solid $node-trigger; }
  &.action { border-left: 4px solid $node-action; }
  &.ai { border-left: 4px solid $node-ai; }
  &.integration { border-left: 4px solid $node-integration; }
}
```

### 画布样式

```scss
.vue-flow {
  background: #f8f9fa;
  
  .vue-flow__edge {
    stroke-width: 2px;
    
    &.selected .vue-flow__edge-path {
      stroke: $primary;
      stroke-width: 3px;
    }
  }
  
  .vue-flow__handle {
    width: 12px;
    height: 12px;
    background: $primary;
    border: 2px solid white;
    box-shadow: 0 2px 4px rgba(0,0,0,0.2);
  }
}
```

---

## 🔧 构建配置

### Vite 配置 (vite.config.js)

```javascript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src')
    }
  },
  css: {
    preprocessorOptions: {
      scss: {
        additionalData: `@use "@/styles/variables.scss" as *;`
      }
    }
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true
      }
    }
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          'vue-vendor': ['vue', 'vue-router', 'pinia'],
          'flow-vendor': ['@vue-flow/core', '@vue-flow/background'],
          'ui-vendor': ['element-plus']
        }
      }
    }
  }
})
```

### Tailwind 配置 (tailwind.config.js)

```javascript
module.exports = {
  content: [
    './index.html',
    './src/**/*.{vue,js,ts,jsx,tsx}'
  ],
  theme: {
    extend: {
      colors: {
        primary: '#3498db',
        success: '#27ae60',
        warning: '#f39c12',
        danger: '#e74c3c'
      }
    }
  },
  plugins: []
}
```

---

## 📊 性能优化

### 代码分割

```javascript
// 路由懒加载
const routes = [
  {
    path: '/editor',
    component: () => import('@/components/canvas/WorkflowCanvas.vue')
  }
]
```

### 组件懒加载

```javascript
// 自定义节点懒加载
const CustomNode = defineAsyncComponent(() =>
  import('@/components/canvas/CustomNode.vue')
)
```

### 虚拟滚动

```javascript
// 大量节点时使用虚拟滚动
import { useVirtualizer } from '@tanstack/vue-virtual'

const virtualizer = useVirtualizer({
  count: nodes.value.length,
  getScrollElement: () => scrollRef.value,
  estimateSize: () => 60
})
```

---

## 🚀 部署方案

### Docker Compose

```yaml
version: '3.8'
services:
  webui:
    build: ./webui
    ports:
      - "80:80"
    depends_on:
      - backend
  
  backend:
    build: ./agentm
    ports:
      - "5000:5000"
    environment:
      - FLASK_ENV=production
```

### Nginx 配置

```nginx
server {
    listen 80;
    server_name agentm.example.com;
    
    root /usr/share/nginx/html;
    index index.html;
    
    location / {
        try_files $uri $uri/ /index.html;
    }
    
    location /api {
        proxy_pass http://backend:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

**文档更新时间**: 2026-04-01  
**技术栈版本**: 2.0.0
