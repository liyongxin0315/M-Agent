<template>
  <div class="canvas-area" @drop="onDrop" @dragover.prevent>
    <VueFlow
      v-model:nodes="nodes"
      v-model:edges="edges"
      :default-zoom="1"
      :min-zoom="0.2"
      :max-zoom="4"
      :fit-view-on-init="true"
      :nodes-connectable="true"
      :nodes-draggable="true"
      :edges-updatable="true"
      :edges-focusable="true"
      :node-types="nodeTypes"
      connection-line-color="#3498db"
      @node-click="onNodeClick"
      @pane-click="onPaneClick"
      @connect="onConnect"
      @node-drag-stop="onNodeDragStop"
    >
      <Background pattern-color="#aaa" :gap="16" />
      <Controls />
      <MiniMap 
        :node-color="(node) => getNodeColor(node)"
        :mask-color="'rgba(240, 240, 240, 0.6)'"
      />
      
      <!-- 自定义节点模板 -->
      <template #node-custom="props">
        <CustomNode :id="props.id" :data="props.data" :selected="props.selected" />
      </template>
    </VueFlow>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'
import { useWorkflowStore } from '@/stores/workflow'
import CustomNode from './CustomNode.vue'

const workflowStore = useWorkflowStore()
const { addEdges, onConnect: onFlowConnect } = useVueFlow()

const nodes = computed(() => workflowStore.nodes)
const edges = computed(() => workflowStore.edges)

// 注册自定义节点类型
const nodeTypes = {
  custom: CustomNode,
  trigger: CustomNode,
  action: CustomNode,
  ai: CustomNode,
  integration: CustomNode
}

// 获取节点颜色
const getNodeColor = (node) => {
  const colors = {
    trigger: '#9b59b6',
    action: '#3498db',
    ai: '#e74c3c',
    integration: '#27ae60'
  }
  return colors[node.data?.nodeType] || '#3498db'
}

// 处理拖放
const onDrop = (event) => {
  const nodeType = JSON.parse(event.dataTransfer.getData('application/json'))
  
  const flowPosition = getFlowPosition(event)
  
  workflowStore.addNode({
    type: 'custom',
    nodeType: nodeType.category,
    label: nodeType.name,
    position: flowPosition,
    config: {
      nodeTypeId: nodeType.id,
      description: nodeType.description
    }
  })
}

// 计算画布中的位置
const getFlowPosition = (event) => {
  const bounds = event.currentTarget.getBoundingClientRect()
  return {
    x: event.clientX - bounds.left,
    y: event.clientY - bounds.top
  }
}

// 节点点击
const onNodeClick = (event) => {
  workflowStore.selectNode(event.node.id)
}

// 画布点击
const onPaneClick = () => {
  workflowStore.clearSelection()
}

// 连接处理
const onConnect = (params) => {
  addEdges({
    ...params,
    type: 'smoothstep',
    animated: true,
    style: { stroke: '#3498db', strokeWidth: 2 }
  })
}

// 节点拖拽结束
const onNodeDragStop = ({ node }) => {
  workflowStore.updateNodePosition(node.id, node.position)
}
</script>

<style lang="scss" scoped>
.canvas-area {
  flex: 1;
  position: relative;
  overflow: hidden;
}

.vue-flow {
  width: 100%;
  height: 100%;
}
</style>
