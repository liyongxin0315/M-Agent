import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器
api.interceptors.request.use(
  config => {
    return config
  },
  error => {
    return Promise.reject(error)
  }
)

// 响应拦截器
api.interceptors.response.use(
  response => {
    return response.data
  },
  error => {
    console.error('API Error:', error)
    return Promise.reject(error)
  }
)

export const workflowApi = {
  // 获取所有工作流
  getAll() {
    return api.get('/workflows')
  },
  
  // 获取单个工作流
  getById(id) {
    return api.get(`/workflows/${id}`)
  },
  
  // 保存工作流
  save(data) {
    return api.post('/workflows', data)
  },
  
  // 更新工作流
  update(id, data) {
    return api.put(`/workflows/${id}`, data)
  },
  
  // 删除工作流
  delete(id) {
    return api.delete(`/workflows/${id}`)
  },
  
  // 执行工作流
  execute(id, params = {}) {
    return api.post(`/workflows/${id}/execute`, params)
  }
}

export const executionApi = {
  // 获取所有执行记录
  getAll() {
    return api.get('/executions')
  },
  
  // 获取执行详情
  getById(id) {
    return api.get(`/executions/${id}`)
  },
  
  // 停止执行
  stop(id) {
    return api.post(`/executions/${id}/stop`)
  }
}

export default api
