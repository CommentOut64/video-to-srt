/**
 * API 服务基础配置
 */
import axios from 'axios'

// 创建 axios 实例
const apiClient = axios.create({
  baseURL: '/api',
  timeout: 300000, // 5分钟超时，因为转录可能很慢
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器
apiClient.interceptors.request.use(
  config => {
    return config
  },
  error => {
    return Promise.reject(error)
  }
)

// 响应拦截器
apiClient.interceptors.response.use(
  response => {
    return response
  },
  error => {
    console.error('API请求失败:', error)
    return Promise.reject(error)
  }
)

export default apiClient