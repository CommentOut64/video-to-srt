/**
 * 工具函数
 */

/**
 * 格式化文件大小
 */
export function formatFileSize(bytes) {
  if (bytes === 0) return "0 Bytes"
  const k = 1024
  const sizes = ["Bytes", "KB", "MB", "GB"]
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i]
}

/**
 * 阶段映射
 */
export const phaseMap = {
  extract: "提取音频",
  split: "分段处理",
  transcribe: "语音转录",
  srt: "生成字幕",
  pending: "等待处理",
  "": "等待处理"
}

/**
 * 获取进度条状态
 */
export function getProgressStatus(status) {
  if (status === 'finished') return 'success'
  if (status === 'failed') return 'exception'
  return 'active'
}

/**
 * 获取状态标签类型
 */
export function getStatusType(status) {
  switch (status) {
    case 'finished': return 'success'
    case 'failed': return 'danger'
    case 'canceled': return 'warning'
    case 'processing': return 'primary'
    default: return 'info'
  }
}