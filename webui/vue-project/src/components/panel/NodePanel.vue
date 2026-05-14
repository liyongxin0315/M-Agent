<template>
  <div class="node-panel">
    <div class="panel-header">
      <h2>📦 节点库</h2>
    </div>
    
    <div class="panel-content">
      <div 
        v-for="(category, catKey) in NODE_CATEGORIES" 
        :key="catKey"
        class="node-category"
      >
        <div class="category-title">
          <el-icon style="vertical-align: middle; margin-right: 4px;">
            <component :is="category.icon" />
          </el-icon>
          {{ category.name }}
        </div>
        
        <div
          v-for="nodeType in category.nodes"
          :key="nodeType"
          class="node-item"
          draggable="true"
          @dragstart="onDragStart($event, NODE_TYPES[nodeType])"
        >
          <el-icon class="node-item-icon" :style="{ color: NODE_TYPES[nodeType].color }">
            <component :is="NODE_TYPES[nodeType].icon" />
          </el-icon>
          <span class="node-item-name">{{ NODE_TYPES[nodeType].name }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { NODE_TYPES, NODE_CATEGORIES } from '@/utils/nodeTypes'

const onDragStart = (event, nodeType) => {
  event.dataTransfer.effectAllowed = 'move'
  event.dataTransfer.setData('application/json', JSON.stringify(nodeType))
}
</script>

<style lang="scss" scoped>
.node-panel {
  width: 280px;
  background: white;
  border-right: 1px solid #e5e7eb;
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
    padding: 12px;
  }
  
  .node-category {
    margin-bottom: 20px;
    
    .category-title {
      font-size: 12px;
      font-weight: 600;
      color: #6b7280;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-bottom: 10px;
      display: flex;
      align-items: center;
    }
    
    .node-item {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 10px 12px;
      margin-bottom: 8px;
      background: #f9fafb;
      border-radius: 8px;
      cursor: grab;
      transition: all 0.2s ease;
      
      &:hover {
        background: #3498db;
        color: white;
        transform: translateX(4px);
        
        .node-item-name {
          color: white;
        }
      }
      
      .node-item-icon {
        font-size: 18px;
      }
      
      .node-item-name {
        font-size: 13px;
        font-weight: 500;
        color: #374151;
      }
    }
  }
}
</style>
