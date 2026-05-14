<template>
  <header class="toolbar">
    <div class="toolbar-left">
      <div class="logo">🤖 AgentM</div>
      <div class="workflow-name">
        <el-input
          v-model="workflowName"
          size="small"
          placeholder="工作流名称"
          style="width: 200px"
          @change="handleNameChange"
        />
      </div>
    </div>
    
    <div class="toolbar-right">
      <el-button size="small" @click="handleNew">
        <el-icon><DocumentAdd /></el-icon>
        新建
      </el-button>
      <el-button size="small" @click="handleSave">
        <el-icon><Check /></el-icon>
        保存
      </el-button>
      <el-button size="small" @click="handleLoad">
        <el-icon><FolderOpened /></el-icon>
        打开
      </el-button>
      <el-button size="small" type="primary" @click="handleRun">
        <el-icon><VideoPlay /></el-icon>
        运行
      </el-button>
      <el-divider direction="vertical" />
      <el-button size="small" @click="handleZoomIn">
        <el-icon><ZoomIn /></el-icon>
      </el-button>
      <el-button size="small" @click="handleZoomOut">
        <el-icon><ZoomOut /></el-icon>
      </el-button>
      <el-button size="small" @click="handleFitView">
        <el-icon><FullScreen /></el-icon>
      </el-button>
    </div>
  </header>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useWorkflowStore } from '@/stores/workflow'
import { useUiStore } from '@/stores/ui'
import { 
  DocumentAdd, Check, FolderOpened, VideoPlay,
  ZoomIn, ZoomOut, FullScreen
} from '@element-plus/icons-vue'
import { ElMessageBox } from 'element-plus'

const workflowStore = useWorkflowStore()
const uiStore = useUiStore()

const workflowName = ref(workflowStore.workflowName)

watch(() => workflowStore.workflowName, (newVal) => {
  workflowName.value = newVal
})

const handleNameChange = () => {
  workflowStore.setWorkflowName(workflowName.value)
}

const handleNew = () => {
  if (workflowStore.isDirty) {
    ElMessageBox.confirm('当前工作流未保存，确定要新建吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }).then(() => {
      workflowStore.reset()
      workflowName.value = '未命名工作流'
    })
  } else {
    workflowStore.reset()
    workflowName.value = '未命名工作流'
  }
}

const handleSave = async () => {
  try {
    const data = workflowStore.exportWorkflow()
    // TODO: 调用 API 保存
    console.log('保存工作流:', data)
    uiStore.addNotification('success', '工作流已保存')
  } catch (error) {
    uiStore.addNotification('error', '保存失败：' + error.message)
  }
}

const handleLoad = () => {
  // TODO: 打开文件选择器或从列表选择
  uiStore.addNotification('info', '打开工作流功能开发中')
}

const handleRun = async () => {
  try {
    uiStore.showLoading('正在执行工作流...')
    // TODO: 调用 API 执行
    await new Promise(resolve => setTimeout(resolve, 1000))
    uiStore.hideLoading()
    uiStore.addNotification('success', '工作流执行成功')
  } catch (error) {
    uiStore.hideLoading()
    uiStore.addNotification('error', '执行失败：' + error.message)
  }
}

const handleZoomIn = () => {
  uiStore.setZoom(Math.min(uiStore.zoomLevel + 0.1, 4))
}

const handleZoomOut = () => {
  uiStore.setZoom(Math.max(uiStore.zoomLevel - 0.1, 0.2))
}

const handleFitView = () => {
  uiStore.setZoom(1)
}
</script>

<style lang="scss" scoped>
.toolbar {
  height: 56px;
  background: white;
  border-bottom: 1px solid #e5e7eb;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  
  .logo {
    font-size: 20px;
    font-weight: 700;
    color: #3498db;
  }
  
  .workflow-name {
    margin-left: 20px;
  }
}
</style>
