/**
 * 文件管理相关API服务
 */
import apiClient from './api.js'

export class FileService {
  /**
   * 获取input目录中的文件列表
   */
  static async getFiles() {
    const response = await apiClient.get('/files')
    return response.data
  }

  /**
   * 删除input目录中的文件
   */
  static async deleteFile(filename) {
    const response = await apiClient.delete(`/files/${filename}`)
    return response.data
  }

  /**
   * 检查文件类型是否支持
   */
  static isSupportedFile(filename) {
    const videoExtensions = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v']
    const audioExtensions = ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.wma']
    const ext = filename.toLowerCase().substring(filename.lastIndexOf('.'))
    return [...videoExtensions, ...audioExtensions].includes(ext)
  }

  /**
   * 检查是否为视频文件
   */
  static isVideoFile(filename) {
    const videoExtensions = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v']
    const ext = filename.toLowerCase().substring(filename.lastIndexOf('.'))
    return videoExtensions.includes(ext)
  }
}