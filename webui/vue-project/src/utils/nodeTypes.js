// 24 种节点类型定义

export const NODE_TYPES = {
  // 触发器节点 (4 种)
  TRIGGER_WEBHOOK: {
    id: 'trigger_webhook',
    name: 'Webhook',
    icon: 'Link',
    category: 'trigger',
    color: '#9b59b6',
    description: 'HTTP Webhook 触发'
  },
  TRIGGER_TIMER: {
    id: 'trigger_timer',
    name: '定时任务',
    icon: 'Timer',
    category: 'trigger',
    color: '#9b59b6',
    description: 'Cron 定时触发'
  },
  TRIGGER_MANUAL: {
    id: 'trigger_manual',
    name: '手动触发',
    icon: 'VideoPlay',
    category: 'trigger',
    color: '#9b59b6',
    description: '手动执行工作流'
  },
  TRIGGER_EVENT: {
    id: 'trigger_event',
    name: '事件监听',
    icon: 'Satellite',
    category: 'trigger',
    color: '#9b59b6',
    description: '监听特定事件'
  },
  
  // 动作节点 (12 种)
  ACTION_HTTP: {
    id: 'action_http',
    name: 'HTTP 请求',
    icon: 'Global',
    category: 'action',
    color: '#3498db',
    description: '发送 HTTP 请求'
  },
  ACTION_CODE: {
    id: 'action_code',
    name: '代码执行',
    icon: 'Code',
    category: 'action',
    color: '#3498db',
    description: '执行 JavaScript/Python'
  },
  ACTION_DATABASE: {
    id: 'action_database',
    name: '数据库查询',
    icon: 'Database',
    category: 'action',
    color: '#3498db',
    description: 'SQL 查询操作'
  },
  ACTION_FILE: {
    id: 'action_file',
    name: '文件操作',
    icon: 'Folder',
    category: 'action',
    color: '#3498db',
    description: '文件读写'
  },
  ACTION_EMAIL: {
    id: 'action_email',
    name: '邮件发送',
    icon: 'Message',
    category: 'action',
    color: '#3498db',
    description: '发送邮件'
  },
  ACTION_API: {
    id: 'action_api',
    name: 'API 调用',
    icon: 'Connection',
    category: 'action',
    color: '#3498db',
    description: '调用第三方 API'
  },
  ACTION_TRANSFORM: {
    id: 'action_transform',
    name: '数据转换',
    icon: 'Refresh',
    category: 'action',
    color: '#3498db',
    description: '数据格式转换'
  },
  ACTION_CONDITION: {
    id: 'action_condition',
    name: '条件判断',
    icon: 'Question',
    category: 'action',
    color: '#3498db',
    description: 'IF/ELSE 分支'
  },
  ACTION_LOOP: {
    id: 'action_loop',
    name: '循环迭代',
    icon: 'RefreshLeft',
    category: 'action',
    color: '#3498db',
    description: 'FOR/WHILE 循环'
  },
  ACTION_DELAY: {
    id: 'action_delay',
    name: '等待延迟',
    icon: 'Clock',
    category: 'action',
    color: '#3498db',
    description: '延迟执行'
  },
  ACTION_LOG: {
    id: 'action_log',
    name: '日志记录',
    icon: 'Document',
    category: 'action',
    color: '#3498db',
    description: '记录日志'
  },
  ACTION_ERROR: {
    id: 'action_error',
    name: '错误处理',
    icon: 'Warning',
    category: 'action',
    color: '#3498db',
    description: '异常捕获处理'
  },
  
  // AI 节点 (4 种)
  AI_LLM: {
    id: 'ai_llm',
    name: 'LLM 调用',
    icon: 'Robot',
    category: 'ai',
    color: '#e74c3c',
    description: '调用大语言模型'
  },
  AI_TEXT: {
    id: 'ai_text',
    name: '文本生成',
    icon: 'Edit',
    category: 'ai',
    color: '#e74c3c',
    description: 'AI 文本生成'
  },
  AI_IMAGE: {
    id: 'ai_image',
    name: '图像生成',
    icon: 'Picture',
    category: 'ai',
    color: '#e74c3c',
    description: 'AI 图像生成'
  },
  AI_SPEECH: {
    id: 'ai_speech',
    name: '语音合成',
    icon: 'Microphone',
    category: 'ai',
    color: '#e74c3c',
    description: 'TTS 语音合成'
  },
  
  // 集成节点 (4 种)
  INTEGRATION_FEISHU: {
    id: 'integration_feishu',
    name: '飞书消息',
    icon: 'ChatDotSquare',
    category: 'integration',
    color: '#27ae60',
    description: '发送飞书消息'
  },
  INTEGRATION_DINGTALK: {
    id: 'integration_dingtalk',
    name: '钉钉消息',
    icon: 'ChatDotRound',
    category: 'integration',
    color: '#27ae60',
    description: '发送钉钉消息'
  },
  INTEGRATION_SLACK: {
    id: 'integration_slack',
    name: 'Slack 消息',
    icon: 'ChatLeftQuote',
    category: 'integration',
    color: '#27ae60',
    description: '发送 Slack 消息'
  },
  INTEGRATION_WECOM: {
    id: 'integration_wecom',
    name: '企业微信',
    icon: 'Enterprise',
    category: 'integration',
    color: '#27ae60',
    description: '发送企业微信消息'
  }
}

// 按类别分组
export const NODE_CATEGORIES = {
  trigger: {
    name: '触发器',
    icon: 'Lightning',
    nodes: ['TRIGGER_WEBHOOK', 'TRIGGER_TIMER', 'TRIGGER_MANUAL', 'TRIGGER_EVENT']
  },
  action: {
    name: '动作',
    icon: 'Tools',
    nodes: ['ACTION_HTTP', 'ACTION_CODE', 'ACTION_DATABASE', 'ACTION_FILE', 'ACTION_EMAIL', 'ACTION_API', 'ACTION_TRANSFORM', 'ACTION_CONDITION', 'ACTION_LOOP', 'ACTION_DELAY', 'ACTION_LOG', 'ACTION_ERROR']
  },
  ai: {
    name: 'AI',
    icon: 'Brain',
    nodes: ['AI_LLM', 'AI_TEXT', 'AI_IMAGE', 'AI_SPEECH']
  },
  integration: {
    name: '集成',
    icon: 'Plug',
    nodes: ['INTEGRATION_FEISHU', 'INTEGRATION_DINGTALK', 'INTEGRATION_SLACK', 'INTEGRATION_WECOM']
  }
}

// 获取节点类型配置
export function getNodeType(typeId) {
  return Object.values(NODE_TYPES).find(t => t.id === typeId)
}

// 获取类别下的所有节点
export function getNodesByCategory(categoryId) {
  const category = NODE_CATEGORIES[categoryId]
  if (!category) return []
  return category.nodes.map(id => NODE_TYPES[id])
}
