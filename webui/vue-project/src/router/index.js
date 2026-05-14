import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'Editor',
    component: () => import('@/App.vue')
  },
  {
    path: '/executions',
    name: 'Executions',
    component: () => import('@/views/ExecutionsView.vue')
  },
  {
    path: '/workflows',
    name: 'Workflows',
    component: () => import('@/views/WorkflowsView.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
