/**
 * 转录任务相关API服务
 */
import apiClient from './api.js'

export class TranscriptionService {
  /**
   * 上传文件并创建转录任务
   */
  static async uploadFile(file, onProgress) {
    const formData = new FormData()
    formData.append('file', file)
    
    const response = await apiClient.post('/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      },
      onUploadProgress: onProgress
    })
    return response.data
  }

  /**
   * 为本地文件创建转录任务
   */
  static async createJob(filename) {
    const formData = new FormData()
    formData.append('filename', filename)
    
    const response = await apiClient.post('/create-job', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
    return response.data
  }

  /**
   * 启动转录任务
   */
  static async startJob(jobId, settings) {
    const formData = new FormData()
    formData.append('job_id', jobId)
    formData.append('settings', JSON.stringify(settings))
    
    const response = await apiClient.post('/start', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
    return response.data
  }

  /**
   * 取消转录任务
   */
  static async cancelJob(jobId) {
    const response = await apiClient.post(`/cancel/${jobId}`)
    return response.data
  }

  /**
   * 获取任务状态
   */
  static async getJobStatus(jobId) {
    const response = await apiClient.get(`/status/${jobId}`)
    return response.data
  }

  /**
   * 复制结果到源文件目录
   */
  static async copyResultToSource(jobId) {
    const response = await apiClient.post(`/copy-result/${jobId}`)
    return response.data
  }

  /**
   * 获取下载链接
   */
  static getDownloadUrl(jobId) {
    return `/api/download/${jobId}`
  }
}