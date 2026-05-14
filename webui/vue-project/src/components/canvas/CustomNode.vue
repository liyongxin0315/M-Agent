<template>
  <div class="custom-node" :class="[data.nodeType, { selected }]">
    <div class="node-header">
      <el-icon class="node-icon">
        <component :is="getIcon(data)" />
      </el-icon>
      <span class="node-label">{{ data.label || '未命名节点' }}</span>
    </div>
    
    <div class="node-body">
      <div v-if="data.description" class="node-description">
        {{ data.description }}
      </div>
      <div v-if="data.status" :class="['node-status', data.status]"></div>
    </div>
    
    <!-- 输入输出端口 -->
    <Handle 
      type="target" 
      :position="Position.Left" 
      class="custom-handle target"
    />
    <Handle 
      type="source" 
      :position="Position.Right" 
      class="custom-handle source"
    />
  </div>
</template>

<script setup>
import { Handle, Position } from '@vue-flow/core'
import { ElIcon } from 'element-plus'

const props = defineProps({
  id: String,
  data: Object,
  selected: Boolean
})

// 获取图标组件名
const getIcon = (data) => {
  const iconMap = {
    // 触发器
    TRIGGER_WEBHOOK: 'Link',
    TRIGGER_TIMER: 'Timer',
    TRIGGER_MANUAL: 'VideoPlay',
    TRIGGER_EVENT: 'Satellite',
    // 动作
    ACTION_HTTP: 'Global',
    ACTION_CODE: 'Code',
    ACTION_DATABASE: 'Database',
    ACTION_FILE: 'Folder',
    ACTION_EMAIL: 'Message',
    ACTION_API: 'Connection',
    ACTION_TRANSFORM: 'Refresh',
    ACTION_CONDITION: 'Question',
    ACTION_LOOP: 'RefreshLeft',
    ACTION_DELAY: 'Clock',
    ACTION_LOG: 'Document',
    ACTION_ERROR: 'Warning',
    // AI
    AI_LLM: 'Robot',
    AI_TEXT: 'Edit',
    AI_IMAGE: 'Picture',
    AI_SPEECH: 'Microphone',
    // 集成
    INTEGRATION_FEISHU: 'ChatDotSquare',
    INTEGRATION_DINGTALK: 'ChatDotRound',
    INTEGRATION_SLACK: 'ChatLeftQuote',
    INTEGRATION_WECOM: 'Enterprise'
  }
  
  const nodeTypeId = data.config?.nodeTypeId
  return iconMap[nodeTypeId] || 'Setting'
}
</script>

<style lang="scss">
.custom-node {
  min-width: 180px;
  min-height: 60px;
  border-radius: 8px;
  border: 2px solid transparent;
  background: white;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  transition: all 0.2s ease;
  cursor: grab;
  
  &:hover {
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
  }
  
  &.selected {
    border-color: #3498db;
    box-shadow: 0 0 0 4px rgba(52, 152, 219, 0.2);
  }
  
  &.trigger { border-left: 4px solid #9b59b6; }
  &.action { border-left: 4px solid #3498db; }
  &.ai { border-left: 4px solid #e74c3c; }
  &.integration { border-left: 4px solid #27ae60; }
  
  .node-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 12px;
    background: #f9fafb;
    border-bottom: 1px solid #e5e7eb;
    border-radius: 8px 8px 0 0;
    
    .node-icon {
      font-size: 18px;
      color: #3498db;
    }
    
    .node-label {
      font-weight: 600;
      font-size: 14px;
      color: #374151;
    }
  }
  
  .node-body {
    padding: 10px 12px;
    position: relative;
    
    .node-description {
      font-size: 12px;
      color: #6b7280;
      line-height: 1.4;
    }
    
    .node-status {
      position: absolute;
      top: 8px;
      right: 8px;
      width: 8px;
      height: 8px;
      border-radius: 50%;
      
      &.success { background: #27ae60; }
      &.running { background: #3498db; }
      &.failed { background: #e74c3c; }
      &.pending { background: #f39c12; }
    }
  }
  
  .custom-handle {
    width: 12px;
    height: 12px;
    background: #3498db;
    border: 2px solid white;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
    
    &.target {
      background: #27ae60;
    }
    
    &.source {
      background: #3498db;
    }
  }
}
</style>
