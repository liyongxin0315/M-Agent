<template>
  <footer class="footer">
    <div class="footer-left">
      <span>📊 节点数：{{ nodeCount }}</span>
      <span style="margin: 0 12px;">|</span>
      <span>🔗 连接数：{{ edgeCount }}</span>
    </div>
    
    <div class="footer-right">
      <span v-if="isDirty" style="color: #f39c12;">● 未保存</span>
      <span v-else style="color: #27ae60;">● 已保存</span>
      <span style="margin: 0 12px;">|</span>
      <span>Zoom: {{ Math.round(zoomLevel * 100) }}%</span>
      <span style="margin: 0 12px;">|</span>
      <span>AgentM v2.0</span>
    </div>
  </footer>
</template>

<script setup>
import { computed } from 'vue'
import { useWorkflowStore } from '@/stores/workflow'
import { useUiStore } from '@/stores/ui'

const workflowStore = useWorkflowStore()
const uiStore = useUiStore()

const nodeCount = computed(() => workflowStore.nodeCount)
const edgeCount = computed(() => workflowStore.edgeCount)
const isDirty = computed(() => workflowStore.isDirty)
const zoomLevel = computed(() => uiStore.zoomLevel)
</script>

<style lang="scss" scoped>
.footer {
  height: 32px;
  background: #1f2937;
  color: #9ca3af;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  font-size: 12px;
  
  .footer-left,
  .footer-right {
    display: flex;
    align-items: center;
  }
}
</style>
