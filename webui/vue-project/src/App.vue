<template>
  <div class="app-container">
    <Header />
    <div class="main-content">
      <NodePanel />
      <CanvasArea />
      <PropsPanel />
    </div>
    <Footer />
  </div>
</template>

<script setup>
import Header from './components/layout/Header.vue'
import NodePanel from './components/panel/NodePanel.vue'
import CanvasArea from './components/canvas/CanvasArea.vue'
import PropsPanel from './components/panel/PropsPanel.vue'
import Footer from './components/layout/Footer.vue'
</script>

<style lang="scss">
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body, #app {
  height: 100%;
  width: 100%;
  overflow: hidden;
}

.app-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #f5f7fa;
}

.main-content {
  flex: 1;
  display: flex;
  overflow: hidden;
}
</style>
