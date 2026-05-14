# AgentM WebUI 使用指南

**版本**: 2.0  
**日期**: 2026-04-01

---

## 🚀 快速开始

### 安装依赖

```bash
cd vue-project
npm install
```

### 启动开发服务器

```bash
npm run dev
```

访问 http://localhost:5173

### 生产构建

```bash
npm run build
```

构建产物输出到 `dist/` 目录

---

## 📖 功能说明

### 1. 工作流编辑器

**访问路径**: http://localhost:5173/

**功能**:
- 从左侧节点库拖拽节点到画布
- 连接节点（从源节点拖拽到目标节点）
- 点击节点选中并配置属性
- 画布缩放（鼠标滚轮）和平移（拖拽空白处）
- 保存/加载工作流

**快捷键**:
- `Delete/Backspace`: 删除选中节点
- `Ctrl/Cmd + S`: 保存工作流
- `Ctrl/Cmd + Enter`: 运行工作流
- `Ctrl/Cmd + 0`: 重置缩放
- `Ctrl/Cmd + +`: 放大
- `Ctrl/Cmd + -`: 缩小

### 2. 节点类型

系统提供 24 种节点类型，分为 4 大类：

#### 触发器节点（紫色）
- **Webhook**: HTTP Webhook 触发
- **定时任务**: Cron 定时触发
- **手动触发**: 手动执行工作流
- **事件监听**: 监听特定事件

#### 动作节点（蓝色）
- **HTTP 请求**: 发送 HTTP 请求
- **代码执行**: 执行 JavaScript/Python
- **数据库查询**: SQL 查询操作
- **文件操作**: 文件读写
- **邮件发送**: 发送邮件
- **API 调用**: 调用第三方 API
- **数据转换**: 数据格式转换
- **条件判断**: IF/ELSE 分支
- **循环迭代**: FOR/WHILE 循环
- **等待延迟**: 延迟执行
- **日志记录**: 记录日志
- **错误处理**: 异常捕获处理

#### AI 节点（红色）
- **LLM 调用**: 调用大语言模型
- **文本生成**: AI 文本生成
- **图像生成**: AI 图像生成
- **语音合成**: TTS 语音合成

#### 集成节点（绿色）
- **飞书消息**: 发送飞书消息
- **钉钉消息**: 发送钉钉消息
- **Slack 消息**: 发送 Slack 消息
- **企业微信**: 发送企业微信消息

### 3. 节点配置

选中节点后，右侧属性面板显示配置项：

- **节点名称**: 自定义节点显示名称
- **节点类型**: 只读，显示节点类别
- **描述**: 节点功能描述
- **节点 ID**: 只读，系统自动生成
- **位置**: 只读，显示节点在画布中的坐标

### 4. 工作流操作

#### 新建工作流
1. 点击顶部工具栏"新建"按钮
2. 如果当前工作流未保存，会提示确认
3. 新建后画布清空，可重新开始设计

#### 保存工作流
1. 点击顶部工具栏"保存"按钮
2. 或使用快捷键 `Ctrl/Cmd + S`
3. 工作流导出为 JSON 格式

#### 打开工作流
1. 点击顶部工具栏"打开"按钮
2. 从列表中选择已有工作流
3. 工作流加载到画布

#### 运行工作流
1. 点击顶部工具栏"运行"按钮
2. 或使用快捷键 `Ctrl/Cmd + Enter`
3. 查看执行结果

---

## 🎨 界面说明

### 顶部工具栏

```
┌─────────────────────────────────────────────────────────────┐
│ 🤖 AgentM  [工作流名称]    新建  保存  打开  运行  |  🔍🔍⛶  │
└─────────────────────────────────────────────────────────────┘
```

- **工作流名称**: 可编辑，双击修改
- **新建**: 创建新工作流
- **保存**: 保存当前工作流
- **打开**: 加载已有工作流
- **运行**: 执行当前工作流
- **缩放控制**: 放大/缩小/适应屏幕

### 左侧节点库

```
┌─────────────────────┐
│ 📦 节点库            │
├─────────────────────┤
│ ⚡ 触发器            │
│  🔗 Webhook         │
│  ⏰ 定时任务        │
│  ▶️ 手动触发        │
│  📡 事件监听        │
├─────────────────────┤
│ 🛠️ 动作             │
│  🌐 HTTP 请求       │
│  💻 代码执行        │
│  ...                │
└─────────────────────┘
```

### 中间画布

- 显示工作流节点和连接
- 支持拖拽节点
- 支持缩放和平移
- 右下角显示小地图

### 右侧属性面板

```
┌─────────────────────┐
│ ⚙️ 属性配置          │
├─────────────────────┤
│ 节点名称：[输入框]   │
│ 节点类型：[标签]     │
│ 描述：[文本域]      │
│ ─────────────────── │
│ 节点 ID: [只读]      │
│ 位置：[只读]        │
│ ─────────────────── │
│ [删除节点]          │
└─────────────────────┘
```

### 底部状态栏

```
┌─────────────────────────────────────────────────────────────┐
│ 📊 节点数：5  |  🔗 连接数：3  |  ● 已保存  |  Zoom: 100%   │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔧 高级功能

### 工作流导入导出

#### 导出工作流

```javascript
import { useWorkflowStore } from '@/stores/workflow'

const workflowStore = useWorkflowStore()
const workflowData = workflowStore.exportWorkflow()

// 下载为 JSON 文件
const blob = new Blob([JSON.stringify(workflowData, null, 2)], {
  type: 'application/json'
})
const url = URL.createObjectURL(blob)
const a = document.createElement('a')
a.href = url
a.download = `${workflowData.name}.json`
a.click()
```

#### 导入工作流

```javascript
const handleFileImport = (event) => {
  const file = event.target.files[0]
  const reader = new FileReader()
  
  reader.onload = (e) => {
    const workflowData = JSON.parse(e.target.result)
    workflowStore.importWorkflow(workflowData)
  }
  
  reader.readAsText(file)
}
```

### 自定义节点

创建自定义节点组件：

```vue
<!-- src/components/canvas/MyCustomNode.vue -->
<template>
  <div class="my-custom-node">
    <div class="node-header">{{ data.label }}</div>
    <div class="node-body">
      <!-- 自定义内容 -->
    </div>
    <Handle type="target" :position="Position.Left" />
    <Handle type="source" :position="Position.Right" />
  </div>
</template>

<script setup>
import { Handle, Position } from '@vue-flow/core'

defineProps({
  id: String,
  data: Object,
  selected: Boolean
})
</script>
```

注册自定义节点：

```javascript
// CanvasArea.vue
import MyCustomNode from './MyCustomNode.vue'

const nodeTypes = {
  custom: CustomNode,
  myCustom: MyCustomNode  // 注册新类型
}
```

### 节点验证

在保存工作流前验证节点配置：

```javascript
function validateWorkflow() {
  const errors = []
  
  // 检查是否有节点
  if (nodes.value.length === 0) {
    errors.push('工作流至少需要一个节点')
  }
  
  // 检查是否有触发器节点
  const hasTrigger = nodes.value.some(n => 
    n.data.nodeType === 'trigger'
  )
  if (!hasTrigger) {
    errors.push('工作流需要一个触发器节点')
  }
  
  // 检查每个节点的配置
  nodes.value.forEach(node => {
    if (!node.data.label) {
      errors.push(`节点 ${node.id} 缺少名称`)
    }
  })
  
  return errors
}
```

---

## 🐛 常见问题

### Q: 拖拽节点没反应？

A: 确保从左侧节点库拖拽，并且拖拽时鼠标指针显示为"抓取"状态。

### Q: 无法连接节点？

A: 确保：
1. 源节点有输出端口（右侧）
2. 目标节点有输入端口（左侧）
3. 从一个节点的输出端口拖拽到另一个节点的输入端口

### Q: 画布缩放失效？

A: 使用鼠标滚轮缩放，或点击工具栏的缩放按钮。

### Q: 保存的工作流在哪里？

A: 默认保存到浏览器的 LocalStorage，也可以导出为 JSON 文件。

---

## 📞 技术支持

- **文档**: 查看 `TECH_STACK.md` 了解技术架构
- **重做报告**: 查看 `WEBUI_REDESIGN_REPORT.md` 了解设计思路
- **问题反馈**: 提交 Issue 或联系开发团队

---

**最后更新**: 2026-04-01  
**维护团队**: AgentM Development Team
