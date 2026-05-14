<template>
  <div class="workflows-view">
    <div class="page-header">
      <h1>📁 工作流管理</h1>
      <el-button type="primary" @click="handleCreate">
        <el-icon><Plus /></el-icon>
        新建工作流
      </el-button>
    </div>
    
    <el-table :data="workflows" style="width: 100%" v-loading="loading">
      <el-table-column prop="name" label="名称" width="250" />
      <el-table-column prop="type" label="类型" width="150" />
      <el-table-column prop="created_at" label="创建时间" width="180" />
      <el-table-column label="操作" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="handleEdit(row)">编辑</el-button>
          <el-button size="small" type="success" @click="handleRun(row)">运行</el-button>
          <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Plus } from '@element-plus/icons-vue'
import { workflowApi } from '@/services/api'

const router = useRouter()
const workflows = ref([])
const loading = ref(false)

const loadWorkflows = async () => {
  loading.value = true
  try {
    workflows.value = await workflowApi.getAll()
  } catch (error) {
    ElMessage.error('加载工作流失败：' + error.message)
  } finally {
    loading.value = false
  }
}

const handleCreate = () => {
  router.push('/')
}

const handleEdit = (row) => {
  // TODO: 加载工作流到编辑器
  ElMessage.info('编辑功能开发中')
}

const handleRun = async (row) => {
  try {
    await workflowApi.execute(row.id)
    ElMessage.success('工作流已执行')
  } catch (error) {
    ElMessage.error('执行失败：' + error.message)
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除此工作流吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    await workflowApi.delete(row.id)
    ElMessage.success('删除成功')
    loadWorkflows()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败：' + error.message)
    }
  }
}

onMounted(() => {
  loadWorkflows()
})
</script>

<style lang="scss" scoped>
.workflows-view {
  padding: 20px;
  
  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
    
    h1 {
      font-size: 24px;
      font-weight: 600;
      color: #1f2937;
    }
  }
}
</style>
