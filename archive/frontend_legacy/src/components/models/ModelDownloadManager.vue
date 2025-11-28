<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="$emit('update:modelValue', $event)"
    title="🤖 模型下载管理"
    width="900px"
    :close-on-click-modal="false"
    destroy-on-close
    center
  >
    <div class="model-download-manager">
      <!-- SSE连接状态指示器 -->
      <div v-if="!modelStore.sseConnected" class="connection-warning">
        <el-alert
          title="SSE连接未建立"
          type="warning"
          :closable="false"
          show-icon
        >
          实时进度更新可能不可用，请刷新页面重试
        </el-alert>
      </div>

      <!-- Whisper模型区域 -->
      <div class="model-section">
        <div class="section-header">
          <el-icon><Microphone /></el-icon>
          <h3>Whisper 转录模型</h3>
          <span class="section-subtitle">选择下载所需的语音识别模型</span>
        </div>

        <div class="model-grid">
          <div
            v-for="model in modelStore.whisperModels"
            :key="model.model_id"
            class="model-card"
            :class="{
              'model-ready': model.status === 'ready',
              'model-downloading': model.status === 'downloading',
              'model-error': model.status === 'error' || model.status === 'incomplete'
            }"
          >
            <!-- 模型头部 -->
            <div class="model-header">
              <div class="model-title">
                <span class="model-name">{{ model.model_id }}</span>
                <el-tag :type="getStatusTagType(model.status)" size="small">
                  {{ getStatusText(model.status) }}
                </el-tag>
              </div>
              <div class="model-meta">
                <span class="model-size">{{ model.size_mb }} MB</span>
                <span class="model-desc">{{ model.description }}</span>
              </div>
            </div>

            <!-- 下载进度条 -->
            <div v-if="model.status === 'downloading'" class="progress-section">
              <el-progress
                :percentage="Math.round(model.download_progress)"
                :stroke-width="6"
                :status="model.download_progress === 100 ? 'success' : ''"
              />
              <div class="progress-text">
                {{ model.download_progress.toFixed(1) }}%
              </div>
            </div>

            <!-- 操作按钮 -->
            <div class="model-actions">
              <!-- 未下载 -->
              <el-button
                v-if="model.status === 'not_downloaded'"
                type="primary"
                size="small"
                @click="downloadWhisperModel(model.model_id)"
                :icon="Download"
              >
                下载
              </el-button>

              <!-- 下载中 -->
              <el-button
                v-else-if="model.status === 'downloading'"
                type="info"
                size="small"
                loading
                disabled
              >
                下载中...
              </el-button>

              <!-- 已下载 -->
              <template v-else-if="model.status === 'ready'">
                <el-tag type="success" size="small">
                  <el-icon><CircleCheckFilled /></el-icon>
                  已安装
                </el-tag>
                <el-button
                  type="danger"
                  size="small"
                  @click="deleteWhisperModel(model.model_id)"
                  :icon="Delete"
                >
                  删除
                </el-button>
              </template>

              <!-- 错误或不完整 -->
              <template v-else-if="model.status === 'error' || model.status === 'incomplete'">
                <el-button
                  type="warning"
                  size="small"
                  @click="downloadWhisperModel(model.model_id)"
                  :icon="Refresh"
                >
                  重新下载
                </el-button>
              </template>
            </div>
          </div>
        </div>
      </div>

      <!-- 对齐模型区域 -->
      <div class="model-section">
        <div class="section-header">
          <el-icon><Connection /></el-icon>
          <h3>语言对齐模型</h3>
          <span class="section-subtitle">用于提高特定语言的识别精度</span>
        </div>

        <div class="align-grid">
          <div
            v-for="model in modelStore.alignModels"
            :key="model.language"
            class="align-card"
            :class="{
              'model-ready': model.status === 'ready',
              'model-downloading': model.status === 'downloading',
              'model-error': model.status === 'error' || model.status === 'incomplete'
            }"
          >
            <div class="align-header">
              <span class="align-name">{{ model.language_name }}</span>
              <el-tag :type="getStatusTagType(model.status)" size="small">
                {{ getStatusText(model.status) }}
              </el-tag>
            </div>

            <!-- 下载进度 -->
            <div v-if="model.status === 'downloading'" class="progress-section">
              <el-progress
                :percentage="Math.round(model.download_progress)"
                :stroke-width="4"
                :status="model.download_progress === 100 ? 'success' : ''"
              />
            </div>

            <!-- 操作按钮 -->
            <div class="align-actions">
              <el-button
                v-if="model.status === 'not_downloaded'"
                type="primary"
                size="small"
                @click="downloadAlignModel(model.language)"
              >
                下载
              </el-button>

              <el-button
                v-else-if="model.status === 'downloading'"
                type="info"
                size="small"
                loading
                disabled
              >
                下载中
              </el-button>

              <template v-else-if="model.status === 'ready'">
                <el-button
                  type="danger"
                  size="small"
                  @click="deleteAlignModel(model.language)"
                >
                  删除
                </el-button>
              </template>

              <el-button
                v-else-if="model.status === 'error' || model.status === 'incomplete'"
                type="warning"
                size="small"
                @click="downloadAlignModel(model.language)"
              >
                重试
              </el-button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
import { onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Download,
  Delete,
  Refresh,
  CircleCheckFilled,
  Microphone,
  Connection
} from '@element-plus/icons-vue'
import { useModelStore } from '../../stores/modelStore.js'

// Props 和 Emits
const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue'])

// 使用全局模型状态store
const modelStore = useModelStore()

// 组件挂载时，如果数据为空则加载一次
onMounted(() => {
  if (modelStore.whisperModels.length === 0 || modelStore.alignModels.length === 0) {
    console.log('[ModelDownloadManager] 首次加载模型列表')
    modelStore.loadModels().catch(error => {
      console.error('[ModelDownloadManager] 加载失败:', error)
      ElMessage.error('加载模型列表失败：' + (error.message || '未知错误'))
    })
  }
})

// 下载Whisper模型
async function downloadWhisperModel(modelId) {
  try {
    await modelStore.downloadWhisperModel(modelId)
  } catch (error) {
    console.error(`下载模型失败: ${modelId}`, error)
    ElMessage.error(
      `下载失败：${error.response?.data?.detail || error.message || '未知错误'}`
    )
  }
}

// 下载对齐模型
async function downloadAlignModel(language) {
  try {
    await modelStore.downloadAlignModel(language)
  } catch (error) {
    console.error(`下载对齐模型失败: ${language}`, error)
    ElMessage.error(
      `下载失败：${error.response?.data?.detail || error.message || '未知错误'}`
    )
  }
}

// 删除Whisper模型
async function deleteWhisperModel(modelId) {
  try {
    await ElMessageBox.confirm(
      `确定要删除模型 ${modelId} 吗？这将释放磁盘空间，但需要重新下载才能使用。`,
      '确认删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    await modelStore.deleteWhisperModel(modelId)
  } catch (error) {
    if (error !== 'cancel') {
      console.error(`删除模型失败: ${modelId}`, error)
      ElMessage.error(
        `删除失败：${error.response?.data?.detail || error.message || '未知错误'}`
      )
    }
  }
}

// 删除对齐模型
async function deleteAlignModel(language) {
  try {
    await ElMessageBox.confirm(
      `确定要删除对齐模型 ${language} 吗？`,
      '确认删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    await modelStore.deleteAlignModel(language)
  } catch (error) {
    if (error !== 'cancel') {
      console.error(`删除对齐模型失败: ${language}`, error)
      ElMessage.error(
        `删除失败：${error.response?.data?.detail || error.message || '未知错误'}`
      )
    }
  }
}

// 获取状态标签类型
function getStatusTagType(status) {
  const typeMap = {
    'ready': 'success',
    'downloading': 'info',
    'not_downloaded': 'info',
    'error': 'danger',
    'incomplete': 'warning'
  }
  return typeMap[status] || 'info'
}

// 获取状态文本
function getStatusText(status) {
  const textMap = {
    'ready': '已安装',
    'downloading': '下载中',
    'not_downloaded': '未下载',
    'error': '错误',
    'incomplete': '不完整'
  }
  return textMap[status] || status
}
</script>

<style scoped>
.model-download-manager {
  max-height: 70vh;
  overflow-y: auto;
  padding: 10px;
}

.connection-warning {
  margin-bottom: 16px;
}

.model-section {
  margin-bottom: 30px;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 2px solid var(--el-border-color-light);
}

.section-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.section-subtitle {
  margin-left: auto;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

/* Whisper模型网格 */
.model-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.model-card {
  border: 2px solid var(--el-border-color-light);
  border-radius: 12px;
  padding: 16px;
  background: var(--el-fill-color-blank);
  transition: all 0.3s ease;
}

.model-card:hover {
  border-color: var(--el-color-primary);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.model-card.model-ready {
  border-color: var(--el-color-success);
  background: rgba(103, 194, 58, 0.05);
}

.model-card.model-downloading {
  border-color: var(--el-color-info);
  background: rgba(144, 147, 153, 0.05);
}

.model-card.model-error {
  border-color: var(--el-color-danger);
  background: rgba(245, 108, 108, 0.05);
}

.model-header {
  margin-bottom: 12px;
}

.model-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.model-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.model-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.model-size {
  font-weight: 500;
  color: var(--el-color-primary);
}

.model-desc {
  flex: 1;
}

.progress-section {
  margin: 12px 0;
}

.progress-text {
  text-align: center;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
}

.model-actions {
  display: flex;
  gap: 8px;
  align-items: center;
  justify-content: flex-end;
  margin-top: 12px;
}

/* 对齐模型网格 */
.align-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}

.align-card {
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  padding: 12px;
  background: var(--el-fill-color-blank);
  transition: all 0.3s ease;
}

.align-card:hover {
  border-color: var(--el-color-primary);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.align-card.model-ready {
  border-color: var(--el-color-success);
  background: rgba(103, 194, 58, 0.05);
}

.align-card.model-downloading {
  border-color: var(--el-color-info);
}

.align-card.model-error {
  border-color: var(--el-color-danger);
}

.align-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.align-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--el-text-color-primary);
}

.align-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 8px;
}

/* 滚动条样式 */
.model-download-manager::-webkit-scrollbar {
  width: 8px;
}

.model-download-manager::-webkit-scrollbar-track {
  background: var(--el-fill-color-lighter);
  border-radius: 4px;
}

.model-download-manager::-webkit-scrollbar-thumb {
  background: var(--el-fill-color-dark);
  border-radius: 4px;
}

.model-download-manager::-webkit-scrollbar-thumb:hover {
  background: var(--el-color-primary);
}

/* 响应式设计 */
@media (max-width: 768px) {
  .model-grid {
    grid-template-columns: 1fr;
  }

  .align-grid {
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  }

  .section-header {
    flex-wrap: wrap;
  }

  .section-subtitle {
    margin-left: 0;
    width: 100%;
    margin-top: 4px;
  }
}
</style>
