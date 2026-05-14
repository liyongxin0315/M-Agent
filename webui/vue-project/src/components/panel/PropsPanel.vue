<template>
  <div class="props-panel">
    <div class="panel-header">
      <h2>⚙️ 属性配置</h2>
    </div>
    
    <div class="panel-content">
      <div v-if="selectedNode" class="node-config">
        <el-form :model="formData" label-position="top" size="small">
          <el-form-item label="节点名称">
            <el-input 
              v-model="formData.label" 
              placeholder="输入节点名称"
              @change="handleUpdate"
            />
          </el-form-item>
          
          <el-form-item label="节点类型">
            <el-tag :type="getTypeTag(selectedNode.data.nodeType)">
              {{ getTypeName(selectedNode.data.nodeType) }}
            </el-tag>
          </el-form-item>
          
          <el-form-item label="描述">
            <el-input
              v-model="formData.description"
              type="textarea"
              :rows="3"
              placeholder="节点描述"
              @change="handleUpdate"
            />
          </el-form-item>
          
          <el-divider />
          
          <el-form-item label="节点 ID">
            <el-input :model-value="selectedNode.id" disabled />
          </el-form-item>
          
          <el-form-item label="位置">
            <div class="position-info">
              X: {{ Math.round(selectedNode.position.x) }}, 
              Y: {{ Math.round(selectedNode.position.y) }}
            </div>
          </el-form-item>
          
          <el-divider />
          
          <el-form-item>
            <el-button 
              type="danger" 
              size="small" 
              @click="handleDelete"
              style="width: 100%"
            >
              <el-icon><Delete /></el-icon>
              删除节点
            </el-button>
          </el-form-item>
        </el-form>
      </div>
      
      <div v-else class="empty-state">
        <el-icon class="icon"><Setting /></el-icon>
        <div class="text">选择节点以配置属性</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useWorkflowStore } from '@/stores/workflow'
import { Setting, Delete } from '@element-plus/icons-vue'
import { ElMessageBox } from 'element-plus'

const workflowStore = useWorkflowStore()

const selectedNode = computed(() => workflowStore.selectedNode)

const formData = ref({
  label: '',
  description: ''
})

// 监听选中节点变化
watch(selectedNode, (node) => {
  if (node) {
    formData.value = {
      label: node.data.label || '',
      description: node.data.description || ''
    }
  }
}, { immediate: true })

// 获取类型标签
const getTypeTag = (type) => {
  const map = {
    trigger: 'warning',
    action: 'primary',
    ai: 'danger',
    integration: 'success'
  }
  return map[type] || 'info'
}

// 获取类型名称
const getTypeName = (type) => {
  const map = {
    trigger: '触发器',
    action: '动作',
    ai: 'AI',
    integration: '集成'
  }
  return map[type] || '未知'
}

// 更新节点
const handleUpdate = () => {
  if (selectedNode.value) {
    workflowStore.updateNode(selectedNode.value.id, {
      label: formData.value.label,
      description: formData.value.description
    })
  }
}

// 删除节点
const handleDelete = () => {
  if (selectedNode.value) {
    ElMessageBox.confirm('确定要删除此节点吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }).then(() => {
      workflowStore.removeNode(selectedNode.value.id)
    })
  }
}
</script>

<style lang="scss" scoped>
.props-panel {
  width: 320px;
  background: white;
  border-left: 1px solid #e5e7eb;
  display: flex;
  flex-direction: column;
  
  .panel-header {
    padding: 16px;
    border-bottom: 1px solid #e5e7eb;
    
    h2 {
      font-size: 16px;
      font-weight: 600;
      color: #1f2937;
    }
  }
  
  .panel-content {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
  }
  
  .node-config {
    :deep(.el-form-item) {
      margin-bottom: 16px;
    }
    
    :deep(.el-form-item__label) {
      font-weight: 600;
      color: #374151;
    }
  }
  
  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: #9ca3af;
    
    .icon {
      font-size: 48px;
      margin-bottom: 16px;
    }
    
    .text {
      font-size: 14px;
    }
  }
  
  .position-info {
    font-family: monospace;
    color: #6b7280;
    padding: 8px;
    background: #f9fafb;
    border-radius: 4px;
  }
}
</style>
