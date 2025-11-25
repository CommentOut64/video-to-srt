<template>
  <!-- 模型管理对话框 - 复用ModelStatusButton的完整UI -->
  <el-dialog
    :model-value="modelValue"
    @update:model-value="$emit('update:modelValue', $event)"
    title="模型预加载状态"
    width="600px"
    :close-on-click-modal="false"
    destroy-on-close
    :modal="true"
    :append-to-body="true"
    :lock-scroll="false"
    center
    :modal-class="'model-status-modal'"
  >
    <div class="model-status-content">
      <!-- 预加载状态 -->
      <div class="status-section">
        <div class="status-header">
          <el-icon><Cpu /></el-icon>
          <span>预加载状态</span>
          <div
            class="status-indicator"
            :class="{
              'indicator-loading': isLoadingStatus,
              'indicator-success':
                modelStatus.loaded_models > 0 && !modelStatus.is_preloading,
              'indicator-error': modelStatus.errors.length > 0,
            }"
          >
            <div class="indicator-dot"></div>
            <span class="indicator-text">{{ getStatusIndicatorText() }}</span>
          </div>
          <div class="header-actions">
            <el-button
              type="primary"
              size="small"
              :loading="modelStatus.is_preloading"
              @click="startPreload"
              :disabled="modelStatus.is_preloading || isPreloadBlocked"
            >
              {{ getPreloadButtonText() }}
            </el-button>
            <el-button type="warning" size="small" @click="clearModelCache">
              清空缓存
            </el-button>
            <el-button
              v-if="isPreloadBlocked"
              type="danger"
              size="small"
              @click="resetPreloadAttempts"
            >
              重置重试
            </el-button>
            <el-button type="info" size="small" @click="forceUpdate">
              刷新状态
            </el-button>
          </div>
        </div>

        <!-- 预加载进度 -->
        <div v-if="modelStatus.is_preloading" class="progress-section">
          <div class="progress-info">
            <span
              >正在加载: {{ modelStatus.current_model || "准备中..." }}</span
            >
            <span
              >{{ modelStatus.loaded_models }}/{{
                modelStatus.total_models
              }}</span
            >
          </div>
          <el-progress
            :percentage="Math.round(modelStatus.progress)"
            :status="modelStatus.progress === 100 ? 'success' : ''"
            :stroke-width="8"
          />
        </div>

        <!-- 错误信息 -->
        <div v-if="modelStatus.errors.length > 0" class="error-section">
          <el-alert
            title="预加载警告"
            type="warning"
            :closable="false"
            show-icon
          >
            <ul class="error-list">
              <li v-for="error in modelStatus.errors" :key="error">
                {{ error }}
              </li>
            </ul>
          </el-alert>
        </div>

        <!-- 重试限制警告 -->
        <div v-if="isPreloadBlocked" class="retry-blocked-section">
          <el-alert
            title="预加载重试已达上限"
            type="error"
            :closable="false"
            show-icon
          >
            <template #default>
              <p>
                预加载失败次数已达到上限 ({{ modelStatus.failed_attempts }}/{{
                  modelStatus.max_retry_attempts
                }})。
              </p>
              <p>请检查系统状态后点击"重置重试"按钮重新尝试。</p>
              <p class="retry-tip">提示：模型仍可在首次使用时自动加载</p>
            </template>
          </el-alert>
        </div>

        <!-- 成功状态 -->
        <div
          v-if="
            !modelStatus.is_preloading &&
            modelStatus.loaded_models > 0 &&
            modelStatus.errors.length === 0
          "
          class="success-section"
        >
          <el-alert
            title="模型预加载完成"
            type="success"
            :closable="false"
            show-icon
          >
            已成功加载 {{ modelStatus.loaded_models }}/{{
              modelStatus.total_models
            }}
            个模型
          </el-alert>
        </div>
      </div>

      <!-- 缓存状态 -->
      <div class="cache-section">
        <div class="cache-row">
          <div class="cache-card">
            <div class="cache-header">
              <el-icon><Microphone /></el-icon>
              <span>Whisper模型缓存</span>
            </div>
            <div
              v-if="
                cacheStatus.whisper_models &&
                cacheStatus.whisper_models.length > 0
              "
            >
              <div
                v-for="model in cacheStatus.whisper_models"
                :key="model.key.join('-')"
                class="model-item"
              >
                <div class="model-info">
                  <div class="model-name">{{ model.key[0] }}</div>
                  <div class="model-details">
                    {{ model.key[1] }} / {{ model.key[2] }}
                  </div>
                </div>
                <div class="model-stats">
                  <el-tag type="info" size="small"
                    >{{ model.memory_mb }}MB</el-tag
                  >
                </div>
              </div>
            </div>
            <div v-else class="empty-state">暂无缓存的模型</div>
          </div>

          <div class="cache-card">
            <div class="cache-header">
              <el-icon><EditPen /></el-icon>
              <span>对齐模型缓存</span>
            </div>
            <div
              v-if="
                cacheStatus.align_models && cacheStatus.align_models.length > 0
              "
            >
              <div class="align-models">
                <el-tag
                  v-for="lang in cacheStatus.align_models"
                  :key="lang"
                  type="success"
                  size="small"
                  class="align-tag"
                >
                  {{ lang }}
                </el-tag>
              </div>
            </div>
            <div v-else class="empty-state">暂无缓存的对齐模型</div>
          </div>
        </div>
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Cpu, Microphone, EditPen } from '@element-plus/icons-vue'
import { modelAPI } from '../../services/api.js'

// 定义props和emits
const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue'])

// 模型状态数据
const modelStatus = reactive({
  is_preloading: false,
  progress: 0,
  current_model: '',
  total_models: 0,
  loaded_models: 0,
  errors: [],
  failed_attempts: 0,
  max_retry_attempts: 3,
})

const cacheStatus = reactive({
  whisper_models: [],
  align_models: [],
  total_memory_mb: 0,
  max_cache_size: 0,
  memory_info: {},
})

let pollTimer = null

// 计算属性
const isPreloadBlocked = computed(() => {
  return modelStatus.failed_attempts >= modelStatus.max_retry_attempts
})

const isLoadingStatus = computed(() => {
  return (
    modelStatus.is_preloading ||
    (modelStatus.loaded_models === 0 &&
      !modelStatus.is_preloading &&
      modelStatus.errors.length === 0)
  )
})

// 方法
function getStatusIndicatorText() {
  if (isPreloadBlocked.value) return '重试已达上限'
  if (modelStatus.is_preloading) return '预加载中'
  if (modelStatus.errors.length > 0) return '加载错误'
  if (modelStatus.loaded_models > 0) return '已加载'
  return '未加载'
}

function getPreloadButtonText() {
  if (isPreloadBlocked.value) return '重试已达上限'
  if (modelStatus.is_preloading) return '预加载中...'
  return '开始预加载'
}

async function updateModelStatus() {
  try {
    const [preloadRes, cacheRes] = await Promise.all([
      modelAPI.getPreloadStatus(),
      modelAPI.getCacheStatus(),
    ])

    if (preloadRes.success) {
      Object.assign(modelStatus, preloadRes.data)
    }

    if (cacheRes.success) {
      Object.assign(cacheStatus, cacheRes.data)
    }
  } catch (error) {
    console.error('❌ 更新模型状态失败:', error)
  }
}

async function startPreload() {
  try {
    const result = await modelAPI.startPreload()
    if (result.success) {
      ElMessage.success('预加载已启动')
      await updateModelStatus()
      // 如果正在预加载，启动轮询
      if (modelStatus.is_preloading) {
        startPolling()
      }
    } else {
      ElMessage.error(result.message || '启动预加载失败')
    }
  } catch (error) {
    ElMessage.error('启动预加载失败: ' + error.message)
  }
}

async function clearModelCache() {
  try {
    await ElMessageBox.confirm(
      '确定要清空所有模型缓存吗？这将释放内存但需要重新加载模型。',
      '清空缓存',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )

    const result = await modelAPI.clearCache()
    if (result.success) {
      ElMessage.success('模型缓存已清空')
      await updateModelStatus()
    } else {
      ElMessage.error(result.message || '清空缓存失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('清空缓存失败: ' + error.message)
    }
  }
}

async function resetPreloadAttempts() {
  // TODO: 调用后端API重置重试次数
  ElMessage.info('重置功能待实现')
}

async function forceUpdate() {
  await updateModelStatus()
  ElMessage.success('状态已刷新')
}

// 智能轮询：只在预加载时轮询
function startPolling() {
  const poll = async () => {
    const wasPreloading = modelStatus.is_preloading
    await updateModelStatus()
    const isNowPreloading = modelStatus.is_preloading

    // 只在正在预加载时继续轮询
    if (isNowPreloading) {
      pollTimer = setTimeout(poll, 1500)
    } else {
      // 预加载完成，停止轮询
      if (wasPreloading) {
        console.log('✅ 预加载已完成，停止轮询')
      }
      stopPolling()
    }
  }
  poll()
}

function stopPolling() {
  if (pollTimer) {
    clearTimeout(pollTimer)
    pollTimer = null
  }
}

// 监听对话框打开/关闭
watch(() => props.modelValue, async (newVal) => {
  if (newVal) {
    // 对话框打开时：立即更新状态，如果正在预加载才启动轮询
    await updateModelStatus()
    if (modelStatus.is_preloading) {
      startPolling()
    }
  } else {
    stopPolling()
  }
})

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.model-status-content {
  padding: 0;
}

.status-section {
  margin-bottom: 20px;
}

.status-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--el-border-color-light);
}

.status-header > span {
  font-weight: 600;
  font-size: 15px;
  flex: 1;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: 12px;
  background: var(--el-fill-color-light);
}

.indicator-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--el-color-info);
}

.indicator-loading .indicator-dot {
  background: var(--el-color-warning);
  animation: pulse 1.5s ease-in-out infinite;
}

.indicator-success .indicator-dot {
  background: var(--el-color-success);
}

.indicator-error .indicator-dot {
  background: var(--el-color-danger);
}

.indicator-text {
  font-size: 13px;
  color: var(--el-text-color-regular);
}

.header-actions {
  display: flex;
  gap: 8px;
}

.progress-section {
  margin-bottom: 16px;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 13px;
  color: var(--el-text-color-regular);
}

.error-section,
.retry-blocked-section,
.success-section {
  margin-bottom: 16px;
}

.error-list {
  margin: 0;
  padding-left: 20px;
}

.error-list li {
  margin-bottom: 4px;
}

.retry-tip {
  margin-top: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.cache-section {
  margin-top: 20px;
}

.cache-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.cache-card {
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  padding: 12px;
}

.cache-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  font-weight: 600;
  font-size: 14px;
}

.model-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.model-item:last-child {
  border-bottom: none;
}

.model-info {
  flex: 1;
}

.model-name {
  font-weight: 500;
  font-size: 14px;
  margin-bottom: 2px;
}

.model-details {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.align-models {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.empty-state {
  text-align: center;
  padding: 20px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

@media (max-width: 768px) {
  .cache-row {
    grid-template-columns: 1fr;
  }

  .header-actions {
    flex-wrap: wrap;
  }

  .status-header {
    flex-wrap: wrap;
  }
}
</style>
