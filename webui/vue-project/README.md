# AgentM WebUI - 可视化工作流编辑器

🤖 基于 Vue 3 + Vue Flow 的现代化工作流编辑器

![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)
![Vue](https://img.shields.io/badge/vue-3.4+-green.svg)
![Vue Flow](https://img.shields.io/badge/vue--flow-1.9+-blue.svg)

---

## ✨ 特性

- 🎨 **现代化界面** - 参考 n8n/扣子设计风格
- 🖱️ **拖拽编辑** - 从节点库拖拽节点到画布
- 🔗 **可视化连接** - 贝塞尔曲线连接节点
- 🔍 **缩放平移** - 画布支持缩放和平移
- ⚙️ **属性配置** - 右侧面板配置节点属性
- 💾 **保存加载** - 工作流 JSON 导入导出
- 📦 **24 种节点** - 触发器、动作、AI、集成四大类

---

## 🚀 快速开始

### 环境要求

- Node.js >= 18.0.0
- npm >= 9.0.0

### 安装

```bash
cd vue-project
npm install
```

### 开发

```bash
npm run dev
```

访问 http://localhost:5173

### 构建

```bash
npm run build
```

### 预览

```bash
npm run preview
```

---

## 📦 节点类型

### 触发器（4 种）
- Webhook - HTTP Webhook 触发
- 定时任务 - Cron 定时触发
- 手动触发 - 手动执行工作流
- 事件监听 - 监听特定事件

### 动作（12 种）
- HTTP 请求、代码执行、数据库查询
- 文件操作、邮件发送、API 调用
- 数据转换、条件判断、循环迭代
- 等待延迟、日志记录、错误处理

### AI（4 种）
- LLM 调用、文本生成、图像生成、语音合成

### 集成（4 种）
- 飞书消息、钉钉消息、Slack 消息、企业微信

---

## 📁 项目结构

```
vue-project/
├── src/
│   ├── main.js                 # 应用入口
│   ├── App.vue                 # 根组件
│   ├── components/
│   │   ├── layout/
│   │   │   ├── Header.vue      # 顶部工具栏
│   │   │   └── Footer.vue      # 底部状态栏
│   │   ├── canvas/
│   │   │   ├── CanvasArea.vue  # 画布区域
│   │   │   └── CustomNode.vue  # 自定义节点
│   │   └── panel/
│   │       ├── NodePanel.vue   # 节点库面板
│   │       └── PropsPanel.vue  # 属性面板
│   ├── stores/
│   │   ├── workflow.js         # 工作流状态
│   │   └── ui.js               # UI 状态
│   ├── services/
│   │   └── api.js              # API 服务
│   ├── utils/
│   │   └── nodeTypes.js        # 节点类型定义
│   ├── styles/
│   │   ├── variables.scss      # SCSS 变量
│   │   └── main.scss           # 主样式
│   └── views/
│       ├── ExecutionsView.vue  # 执行历史
│       └── WorkflowsView.vue   # 工作流管理
├── index.html
├── package.json
├── vite.config.js
└── README.md
```

---

## 🎨 技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| Vue.js | 3.4+ | 核心框架 |
| Vue Flow | 1.9+ | 流程图画布 |
| Pinia | 2.1+ | 状态管理 |
| Element Plus | 2.4+ | UI 组件 |
| Tailwind CSS | 3.4+ | 样式 |
| Vite | 5.0+ | 构建工具 |

---

## 📖 文档

- [使用指南](./USER_GUIDE.md) - 详细使用说明
- [技术栈说明](../TECH_STACK.md) - 技术架构文档
- [重做报告](../WEBUI_REDESIGN_REPORT.md) - 设计思路

---

## 🔧 开发命令

```bash
# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 生产构建
npm run build

# 预览构建结果
npm run preview

# 代码检查
npm run lint

# 代码格式化
npm run format

# 运行测试
npm run test
```

---

## 🎯 快捷键

| 快捷键 | 功能 |
|--------|------|
| `Ctrl/Cmd + S` | 保存工作流 |
| `Ctrl/Cmd + Enter` | 运行工作流 |
| `Delete/Backspace` | 删除选中节点 |
| `Ctrl/Cmd + 0` | 重置缩放 |
| `Ctrl/Cmd + +` | 放大 |
| `Ctrl/Cmd + -` | 缩小 |

---

## 📝 更新日志

### v2.0.0 (2026-04-01)

- ✨ 完全重写 WebUI，采用 Vue 3 + Vue Flow
- ✨ 新增拖拽式节点编辑器
- ✨ 新增 24 种节点类型
- ✨ 新增画布缩放/平移功能
- ✨ 新增属性配置面板
- 🎨 优化界面设计，参考 n8n/扣子风格
- 🐛 修复原有 WebUI 的模板继承问题

### v1.0.0 (2026-03-25)

- 初始版本，基于 Flask 的简单 WebUI

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

## 📄 许可证

MIT License

---

**开发团队**: AgentM Team  
**最后更新**: 2026-04-01
