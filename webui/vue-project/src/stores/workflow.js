import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { v4 as uuidv4 } from 'uuid'

export const useWorkflowStore = defineStore('workflow', () => {
  // 状态
  const nodes = ref([])
  const edges = ref([])
  const selectedNodeId = ref(null)
  const workflowName = ref('未命名工作流')
  const isDirty = ref(false)
  
  // 计算属性
  const selectedNode = computed(() => {
    return nodes.value.find(n => n.id === selectedNodeId.value)
  })
  
  const nodeCount = computed(() => nodes.value.length)
  
  const edgeCount = computed(() => edges.value.length)
  
  // 方法
  function addNode(node) {
    const newNode = {
      id: uuidv4(),
      position: node.position || { x: 100, y: 100 },
      type: node.type || 'default',
      data: {
        label: node.label || '新节点',
        nodeType: node.nodeType || 'action',
        config: node.config || {}
      },
      class: `workflow-node ${node.nodeType || 'action'}`
    }
    nodes.value.push(newNode)
    isDirty.value = true
    return newNode
  }
  
  function removeNode(nodeId) {
    const index = nodes.value.findIndex(n => n.id === nodeId)
    if (index !== -1) {
      nodes.value.splice(index, 1)
      // 同时删除相关的连接
      edges.value = edges.value.filter(e => 
        e.source !== nodeId && e.target !== nodeId
      )
      if (selectedNodeId.value === nodeId) {
        selectedNodeId.value = null
      }
      isDirty.value = true
    }
  }
  
  function updateNode(nodeId, data) {
    const node = nodes.value.find(n => n.id === nodeId)
    if (node) {
      node.data = { ...node.data, ...data }
      isDirty.value = true
    }
  }
  
  function updateNodePosition(nodeId, position) {
    const node = nodes.value.find(n => n.id === nodeId)
    if (node) {
      node.position = position
    }
  }
  
  function addEdge(connection) {
    const newEdge = {
      id: uuidv4(),
      source: connection.source,
      target: connection.target,
      sourceHandle: connection.sourceHandle,
      targetHandle: connection.targetHandle,
      type: 'smoothstep',
      animated: true,
      style: { stroke: '#3498db', strokeWidth: 2 }
    }
    edges.value.push(newEdge)
    isDirty.value = true
    return newEdge
  }
  
  function removeEdge(edgeId) {
    const index = edges.value.findIndex(e => e.id === edgeId)
    if (index !== -1) {
      edges.value.splice(index, 1)
      isDirty.value = true
    }
  }
  
  function selectNode(nodeId) {
    selectedNodeId.value = nodeId
  }
  
  function clearSelection() {
    selectedNodeId.value = null
  }
  
  function setWorkflowName(name) {
    workflowName.value = name
  }
  
  function exportWorkflow() {
    return {
      name: workflowName.value,
      nodes: nodes.value.map(n => ({
        id: n.id,
        type: n.type,
        position: n.position,
        data: n.data
      })),
      edges: edges.value.map(e => ({
        id: e.id,
        source: e.source,
        target: e.target,
        sourceHandle: e.sourceHandle,
        targetHandle: e.targetHandle,
        type: e.type
      }))
    }
  }
  
  function importWorkflow(data) {
    workflowName.value = data.name || '导入的工作流'
    nodes.value = data.nodes || []
    edges.value = data.edges || []
    isDirty.value = false
  }
  
  function reset() {
    nodes.value = []
    edges.value = []
    selectedNodeId.value = null
    workflowName.value = '未命名工作流'
    isDirty.value = false
  }
  
  return {
    // 状态
    nodes,
    edges,
    selectedNodeId,
    workflowName,
    isDirty,
    // 计算属性
    selectedNode,
    nodeCount,
    edgeCount,
    // 方法
    addNode,
    removeNode,
    updateNode,
    updateNodePosition,
    addEdge,
    removeEdge,
    selectNode,
    clearSelection,
    setWorkflowName,
    exportWorkflow,
    importWorkflow,
    reset
  }
})
