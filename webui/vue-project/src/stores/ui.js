import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useUiStore = defineStore('ui', () => {
  // 状态
  const sidebarCollapsed = ref(false)
  const propsPanelVisible = ref(true)
  const theme = ref('light')
  const zoomLevel = ref(1)
  const loading = ref(false)
  const notifications = ref([])
  
  // 方法
  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }
  
  function togglePropsPanel() {
    propsPanelVisible.value = !propsPanelVisible.value
  }
  
  function setTheme(newTheme) {
    theme.value = newTheme
    document.documentElement.setAttribute('data-theme', newTheme)
  }
  
  function setZoom(level) {
    zoomLevel.value = level
  }
  
  function showLoading(message = '加载中...') {
    loading.value = true
    addNotification('info', message)
  }
  
  function hideLoading() {
    loading.value = false
  }
  
  function addNotification(type, message) {
    const id = Date.now()
    notifications.value.push({ id, type, message })
    setTimeout(() => {
      removeNotification(id)
    }, 3000)
  }
  
  function removeNotification(id) {
    notifications.value = notifications.value.filter(n => n.id !== id)
  }
  
  return {
    // 状态
    sidebarCollapsed,
    propsPanelVisible,
    theme,
    zoomLevel,
    loading,
    notifications,
    // 方法
    toggleSidebar,
    togglePropsPanel,
    setTheme,
    setZoom,
    showLoading,
    hideLoading,
    addNotification,
    removeNotification
  }
})
