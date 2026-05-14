<template>
  <div class="executions-view">
    <div class="page-header">
      <h1>📋 执行历史</h1>
      <el-button type="primary" @click="handleRefresh">
        <el-icon><Refresh /></el-icon>
        刷新
      </el-button>
    </div>
    
    <el-table :data="executions" style="width: 100%" v-loading="loading">
      <el-table-column prop="id" label="ID" width="180" />
      <el-table-column prop="workflow_name" label="工作流" width="200" />
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="getStatusType(row.status)">
            {{ row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="start_time" label="开始时间" width="180" />
      <el-table-column prop="total_duration" label="耗时 (s)" width="100" />
      <el-table-column label="操作" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="handleView(row)">详情</el-button>
          <el-button size="small" type="success" @click="handleRerun(row)">重跑</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Refresh } from '@element-plus/icons-vue'
import { executionApi } from '@/services/api'

const router = useRouter()
const executions = ref([])
const loading = ref(false)

const getStatusType = (status) => {
  const map = {
    completed: 'success',
    running: 'primary',
    failed: 'danger',
    pending: 'warning'
  }
  return map[status] || 'info'
}

const loadExecutions = async () => {
  loading.value = true
  try {
    executions.value = await executionApi.getAll()
  } catch (error) {
    ElMessage.error('加载执行记录失败：' + error.message)
  } finally {
    loading.value = false
  }
}

const handleRefresh = () => {
  loadExecutions()
}

const handleView = (row) => {
  router.push(`/executions/${row.id}`)
}

const handleRerun = async (row) => {
  try {
    await executionApi.stop(row.id)
    ElMessage.success('已重新执行')
    loadExecutions()
  } catch (error) {
    ElMessage.error('重跑失败：' + error.message)
  }
}

onMounted(() => {
  loadExecutions()
})
</script>

<style lang="scss" scoped>
.executions-view {
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
