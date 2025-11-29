<template>
  <div class="task-monitor">
    <div class="monitor-header">
      <h3>后台任务</h3>
      <span class="task-count">{{ filteredTasks.length }}</span>
    </div>

    <div class="task-list" v-if="filteredTasks.length > 0">
      <!-- 可拖动的排队任务区域 -->
      <draggable
        v-model="queuedTasks"
        :disabled="queuedTasks.length < 2"
        item-key="job_id"
        handle=".drag-handle"
        ghost-class="task-item--ghost"
        drag-class="task-item--dragging"
        @end="onDragEnd"
        class="draggable-list"
      >
        <template #item="{ element: task }">
          <div
            class="task-item is-queued"
            :class="{
              'is-current': task.job_id === currentJobId,
              'is-finished': task.status === 'finished'
            }"
          >
            <!-- 拖动手柄 -->
            <div class="drag-handle" :title="queuedTasks.length >= 2 ? '拖动排序' : '单任务无法拖动'">
              <svg viewBox="0 0 24 24" fill="currentColor">
                <path d="M11 18c0 1.1-.9 2-2 2s-2-.9-2-2 .9-2 2-2 2 .9 2 2zm-2-8c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm0-6c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm6 4c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm0 2c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm0 6c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2z"/>
              </svg>
            </div>

            <!-- 任务内容 -->
            <div class="task-info">
              <div class="task-header">
                <span class="task-name" :title="task.title || task.filename">
                  {{ task.title || task.filename }}
                </span>
                <!-- 使用阶段标签替代简单状态 -->
                <span
                  class="task-phase-tag"
                  :style="{
                    background: getPhaseStyle(task).bgColor,
                    color: getPhaseStyle(task).color
                  }"
                >
                  {{ getPhaseLabel(task) }}
                </span>
              </div>

              <!-- 进度条 -->
              <div v-if="['processing', 'queued', 'paused'].includes(task.status)" class="task-progress">
                <div class="progress-bar">
                  <div class="progress-fill" :style="{ width: task.progress + '%' }"></div>
                </div>
                <span class="progress-text">{{ formatProgress(task.progress) }}%</span>
              </div>

              <!-- SSE断开指示器 -->
              <div v-if="!task.sseConnected && task.status === 'processing'" class="sse-disconnected">
                <span class="warning-dot"></span>
                <span class="warning-text">连接中断，等待重连...</span>
              </div>

              <!-- 错误指示器 -->
              <div v-if="task.lastError && task.status !== 'failed'" class="task-error-indicator">
                <svg class="error-icon" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/>
                </svg>
                <span class="error-text">{{ task.lastError }}</span>
              </div>

              <!-- 完成时间 -->
              <div v-else-if="task.status === 'finished'" class="task-meta">
                <svg class="icon" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M9 16.2L4.8 12l-1.4 1.4L9 19 21 7l-1.4-1.4L9 16.2z"/>
                </svg>
                <span>{{ formatTime(task.updatedAt) }}</span>
              </div>

              <!-- 失败原因 -->
              <div v-else-if="task.status === 'failed'" class="task-error">
                <svg class="icon" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/>
                </svg>
                <span>{{ task.message || '转录失败' }}</span>
              </div>
            </div>

            <!-- 操作按钮 -->
            <div class="task-actions">
              <!-- 暂停按钮（仅处理中任务） -->
              <button
                v-if="task.status === 'processing'"
                class="action-btn"
                @click="pauseTask(task.job_id)"
                title="暂停"
              >
                <svg viewBox="0 0 24 24" fill="currentColor">
                  <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>
                </svg>
              </button>

              <!-- 恢复按钮（仅暂停任务） -->
              <button
                v-if="task.status === 'paused'"
                class="action-btn action-btn--success"
                @click="resumeTask(task.job_id)"
                title="恢复"
              >
                <svg viewBox="0 0 24 24" fill="currentColor">
                  <path d="M8 5v14l11-7z"/>
                </svg>
              </button>

              <!-- 取消按钮（处理中、排队中或暂停） -->
              <button
                v-if="['processing', 'queued', 'paused'].includes(task.status)"
                class="action-btn action-btn--danger"
                @click="cancelTask(task.job_id)"
                title="取消"
              >
                <svg viewBox="0 0 24 24" fill="currentColor">
                  <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
                </svg>
              </button>

              <!-- 打开编辑器按钮（已完成且非当前任务） -->
              <button
                v-if="task.status === 'finished' && task.job_id !== currentJobId"
                class="action-btn action-btn--primary"
                @click="openEditor(task.job_id)"
                title="打开编辑器"
              >
                <svg viewBox="0 0 24 24" fill="currentColor">
                  <path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/>
                </svg>
              </button>

              <!-- 从列表移除按钮（已完成任务） -->
              <button
                v-if="task.status === 'finished'"
                class="action-btn"
                @click="removeTask(task.job_id)"
                title="从列表移除"
              >
                <svg viewBox="0 0 24 24" fill="currentColor">
                  <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/>
                </svg>
              </button>
            </div>
          </div>
        </template>
      </draggable>

      <!-- 非排队状态的任务（不可拖动） -->
      <div
        v-for="task in nonQueuedTasks"
        :key="task.job_id"
        class="task-item"
        :class="{
          'is-current': task.job_id === currentJobId,
          'is-finished': task.status === 'finished',
          'is-processing': task.status === 'processing',
          'is-paused': task.status === 'paused'
        }"
      >
        <!-- 任务信息 -->
        <div class="task-info">
          <div class="task-header">
            <span class="task-name" :title="task.title || task.filename">
              {{ task.title || task.filename }}
            </span>
            <!-- 使用阶段标签替代简单状态 -->
            <span
              class="task-phase-tag"
              :style="{
                background: getPhaseStyle(task).bgColor,
                color: getPhaseStyle(task).color
              }"
            >
              {{ getPhaseLabel(task) }}
            </span>
          </div>

          <!-- 进度条 -->
          <div v-if="['processing', 'queued', 'paused'].includes(task.status)" class="task-progress">
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: task.progress + '%' }"></div>
            </div>
            <span class="progress-text">{{ formatProgress(task.progress) }}%</span>
          </div>

          <!-- SSE断开指示器 -->
          <div v-if="!task.sseConnected && task.status === 'processing'" class="sse-disconnected">
            <span class="warning-dot"></span>
            <span class="warning-text">连接中断，等待重连...</span>
          </div>

          <!-- 错误指示器 -->
          <div v-if="task.lastError && task.status !== 'failed'" class="task-error-indicator">
            <svg class="error-icon" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/>
            </svg>
            <span class="error-text">{{ task.lastError }}</span>
          </div>

          <!-- 完成时间 -->
          <div v-else-if="task.status === 'finished'" class="task-meta">
            <svg class="icon" viewBox="0 0 24 24" fill="currentColor">
              <path d="M9 16.2L4.8 12l-1.4 1.4L9 19 21 7l-1.4-1.4L9 16.2z"/>
            </svg>
            <span>{{ formatTime(task.updatedAt) }}</span>
          </div>

          <!-- 失败原因 -->
          <div v-else-if="task.status === 'failed'" class="task-error">
            <svg class="icon" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/>
            </svg>
            <span>{{ task.message || '转录失败' }}</span>
          </div>
        </div>

        <!-- 操作按钮 -->
        <div class="task-actions">
          <!-- 暂停按钮（仅处理中任务） -->
          <button
            v-if="task.status === 'processing'"
            class="action-btn"
            @click="pauseTask(task.job_id)"
            title="暂停"
          >
            <svg viewBox="0 0 24 24" fill="currentColor">
              <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>
            </svg>
          </button>

          <!-- 恢复按钮（仅暂停任务） -->
          <button
            v-if="task.status === 'paused'"
            class="action-btn action-btn--success"
            @click="resumeTask(task.job_id)"
            title="恢复"
          >
            <svg viewBox="0 0 24 24" fill="currentColor">
              <path d="M8 5v14l11-7z"/>
            </svg>
          </button>

          <!-- 取消按钮（处理中、排队中或暂停） -->
          <button
            v-if="['processing', 'queued', 'paused'].includes(task.status)"
            class="action-btn action-btn--danger"
            @click="cancelTask(task.job_id)"
            title="取消"
          >
            <svg viewBox="0 0 24 24" fill="currentColor">
              <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
            </svg>
          </button>

          <!-- 打开编辑器按钮（已完成且非当前任务） -->
          <button
            v-if="task.status === 'finished' && task.job_id !== currentJobId"
            class="action-btn action-btn--primary"
            @click="openEditor(task.job_id)"
            title="打开编辑器"
          >
            <svg viewBox="0 0 24 24" fill="currentColor">
              <path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/>
            </svg>
          </button>

          <!-- 从列表移除按钮（已完成任务） -->
          <button
            v-if="task.status === 'finished'"
            class="action-btn"
            @click="removeTask(task.job_id)"
            title="从列表移除"
          >
            <svg viewBox="0 0 24 24" fill="currentColor">
              <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/>
            </svg>
          </button>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else class="empty-state">
      <svg viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
      </svg>
      <p>暂无后台任务</p>
    </div>

    <!-- 底部操作 -->
    <div class="monitor-footer" v-if="hasFinishedTasks">
      <button class="clear-btn" @click="clearFinished">
        清除已完成 ({{ finishedCount }})
      </button>
    </div>
  </div>
</template>

<script setup>
/**
 * TaskMonitor - 任务监控器组件
 *
 * 类似 Edge 浏览器的下载中心，用于管理多任务并行转录
 * 功能：
 * - 显示所有后台任务列表
 * - 实时显示转录进度
 * - 暂停/取消进行中的任务
 * - 打开已完成任务的编辑器
 * - 清除已完成任务
 * - 拖动排序队列中的任务
 */
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useUnifiedTaskStore } from '@/stores/unifiedTaskStore'
import { transcriptionApi } from '@/services/api'
import { PHASE_CONFIG, STATUS_CONFIG, formatProgress } from '@/constants/taskPhases'
import draggable from 'vuedraggable'

const props = defineProps({
  currentJobId: { type: String, default: '' }
})

const router = useRouter()
const taskStore = useUnifiedTaskStore()

// 拖动排序相关状态
const queuedTasks = ref([])

// 过滤显示的任务（排除未创建的）
const filteredTasks = computed(() => {
  return taskStore.tasks.filter(t => t.status !== 'created')
})

// 非排队状态的任务（不可拖动）
const nonQueuedTasks = computed(() => {
  return filteredTasks.value.filter(t => t.status !== 'queued')
})

// 是否有已完成的任务
const hasFinishedTasks = computed(() => {
  return filteredTasks.value.some(t => t.status === 'finished')
})

// 已完成任务数量
const finishedCount = computed(() => {
  return filteredTasks.value.filter(t => t.status === 'finished').length
})

// 监听 store 变化，更新可拖动列表
watch(
  () => taskStore.tasks,
  (tasks) => {
    queuedTasks.value = tasks.filter(t => t.status === 'queued')
  },
  { immediate: true, deep: true }
)

// 拖动结束处理
async function onDragEnd(event) {
  // 如果没有真正移动位置，直接返回
  if (event.oldIndex === event.newIndex) {
    return
  }

  // 获取新的任务ID顺序
  const newOrder = queuedTasks.value.map(t => t.job_id)

  console.log('[TaskMonitor] 队列重排:', {
    from: event.oldIndex,
    to: event.newIndex,
    newOrder
  })

  try {
    const result = await transcriptionApi.reorderQueue(newOrder)
    if (!result.reordered) {
      console.error('[TaskMonitor] 队列重排失败，恢复原顺序')
      // 恢复原顺序
      queuedTasks.value = taskStore.tasks.filter(t => t.status === 'queued')
    } else {
      console.log('[TaskMonitor] 队列重排成功')
    }
  } catch (error) {
    console.error('[TaskMonitor] 队列重排请求失败:', error)
    // 恢复原顺序
    queuedTasks.value = taskStore.tasks.filter(t => t.status === 'queued')
  }
}

// 获取阶段样式
function getPhaseStyle(task) {
  // 如果任务失败，使用失败状态样式
  if (task.status === 'failed') {
    return STATUS_CONFIG.failed
  }
  // 如果任务正在处理且有阶段信息，使用阶段样式
  if (task.status === 'processing' && task.phase) {
    return PHASE_CONFIG[task.phase] || PHASE_CONFIG.pending
  }
  // 其他情况使用状态样式
  return STATUS_CONFIG[task.status] || STATUS_CONFIG.created
}

// 获取阶段标签文本
function getPhaseLabel(task) {
  // 如果任务失败，显示失败
  if (task.status === 'failed') {
    return '失败'
  }
  // 如果任务正在处理且有阶段信息，显示阶段标签
  if (task.status === 'processing' && task.phase) {
    return PHASE_CONFIG[task.phase]?.label || '处理中'
  }
  // 其他情况显示状态标签
  return STATUS_CONFIG[task.status]?.label || task.status
}

// 暂停任务
async function pauseTask(jobId) {
  try {
    await transcriptionApi.pauseJob(jobId)
    // 更新本地状态
    taskStore.updateTaskStatus(jobId, 'paused')
  } catch (error) {
    console.error('暂停任务失败:', error)
  }
}

// 恢复任务
async function resumeTask(jobId) {
  try {
    // 使用新的 resumeJob API，恢复暂停的任务（重新加入队列）
    const result = await transcriptionApi.resumeJob(jobId)
    // 根据后端返回值设置状态（应该是 queued，而不是 processing）
    taskStore.updateTaskStatus(jobId, result.status || 'queued')
    console.log('[TaskMonitor] 任务已恢复，状态:', result.status, '队列位置:', result.queue_position)
  } catch (error) {
    console.error('恢复任务失败:', error)
  }
}

// 取消任务
async function cancelTask(jobId) {
  if (!confirm('确定要取消这个任务吗?')) return

  try {
    await transcriptionApi.cancelJob(jobId, false)
    taskStore.updateTaskStatus(jobId, 'canceled')
  } catch (error) {
    console.error('取消任务失败:', error)
  }
}

// 打开编辑器
function openEditor(jobId) {
  router.push(`/editor/${jobId}`)
}

// 从列表移除任务
async function removeTask(jobId) {
  try {
    await taskStore.deleteTask(jobId)
  } catch (error) {
    console.error('移除任务失败:', error)
  }
}

// 清除所有已完成任务
async function clearFinished() {
  const finished = filteredTasks.value.filter(t => t.status === 'finished')
  for (const task of finished) {
    try {
      await taskStore.deleteTask(task.job_id)
    } catch (error) {
      console.error('清除任务失败:', error)
    }
  }
}

// 格式化时间
function formatTime(timestamp) {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  const now = new Date()
  const diff = now - date

  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`
  return date.toLocaleDateString('zh-CN')
}
</script>

<style lang="scss" scoped>
.task-monitor {
  display: flex;
  flex-direction: column;
  max-height: 500px;
  background: var(--bg-secondary);
  color: var(--text-secondary);
}

.monitor-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-default);

  h3 {
    font-size: 14px;
    font-weight: 600;
    margin: 0;
    color: var(--text-primary);
  }

  .task-count {
    padding: 2px 8px;
    background: var(--bg-tertiary);
    border-radius: 10px;
    font-size: 11px;
    font-weight: 600;
    color: var(--text-muted);
  }
}

.task-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;

  &::-webkit-scrollbar {
    width: 8px;
  }
  &::-webkit-scrollbar-track {
    background: transparent;
  }
  &::-webkit-scrollbar-thumb {
    background: var(--border-muted);
    border-radius: 4px;
    &:hover { background: var(--text-muted); }
  }
}

.task-item {
  display: flex;
  gap: 12px;
  padding: 12px;
  margin-bottom: 8px;
  background: var(--bg-tertiary);
  border: 1px solid transparent;
  border-radius: 6px;
  transition: all 0.2s;

  &:hover {
    background: var(--bg-elevated);
  }

  &.is-current {
    border-color: var(--primary);
    background: rgba(88, 166, 255, 0.1);
  }

  &.is-finished {
    opacity: 0.7;
  }
}

.task-info {
  flex: 1;
  min-width: 0;
}

.task-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  gap: 8px;

  .task-name {
    flex: 1;
    font-size: 13px;
    font-weight: 500;
    color: var(--text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .task-phase-tag {
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 10px;
    font-weight: 600;
    white-space: nowrap;
  }
}

.task-progress {
  display: flex;
  align-items: center;
  gap: 8px;

  .progress-bar {
    flex: 1;
    height: 4px;
    background: var(--border-muted);
    border-radius: 2px;
    overflow: hidden;

    .progress-fill {
      height: 100%;
      background: var(--primary);
      transition: width 0.3s ease;
    }
  }

  .progress-text {
    font-size: 11px;
    font-family: var(--font-mono);
    color: var(--text-muted);
    min-width: 35px;
    text-align: right;
  }
}

.task-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--text-muted);

  .icon {
    width: 14px;
    height: 14px;
    color: var(--success);
  }
}

.task-error {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--danger);

  .icon {
    width: 14px;
    height: 14px;
  }
}

// SSE断开指示器
.sse-disconnected {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  background: rgba(210, 153, 34, 0.1);
  border-radius: 4px;
  font-size: 11px;
  color: var(--warning);

  .warning-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--warning);
    animation: pulse 1.5s infinite;
  }

  .warning-text {
    font-size: 11px;
  }
}

// 错误指示器
.task-error-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  background: rgba(248, 81, 73, 0.1);
  border-radius: 4px;
  font-size: 11px;
  color: var(--danger);

  .error-icon {
    width: 14px;
    height: 14px;
    flex-shrink: 0;
  }

  .error-text {
    font-size: 11px;
    line-height: 1.4;
  }
}

.task-actions {
  display: flex;
  flex-direction: column;
  gap: 4px;

  .action-btn {
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: transparent;
    border: none;
    border-radius: 4px;
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.2s;

    svg {
      width: 16px;
      height: 16px;
    }

    &:hover {
      background: var(--bg-tertiary);
      color: var(--text-secondary);
    }

    &--primary {
      color: var(--primary);
      &:hover {
        background: rgba(88, 166, 255, 0.15);
      }
    }

    &--success {
      color: var(--success);
      &:hover {
        background: rgba(63, 185, 80, 0.15);
      }
    }

    &--danger {
      &:hover {
        background: rgba(248, 81, 73, 0.15);
        color: var(--danger);
      }
    }
  }
}

// 拖动排序相关样式
.draggable-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

// 拖动手柄
.drag-handle {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  cursor: grab;
  flex-shrink: 0;
  opacity: 0.5;
  transition: opacity 0.2s;

  svg {
    width: 16px;
    height: 16px;
  }

  &:hover {
    opacity: 1;
    color: var(--text-secondary);
  }

  &:active {
    cursor: grabbing;
  }
}

// 拖动中的元素样式
.task-item--dragging {
  opacity: 0.9;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  transform: scale(1.02);
  z-index: 100;
}

// 占位符样式
.task-item--ghost {
  opacity: 0.3;
  background: var(--bg-tertiary);
  border: 2px dashed var(--border-default);
}

// 排队中的任务显示拖动手柄
.task-item.is-queued {
  display: flex;
  gap: 8px;

  .drag-handle {
    display: flex;
  }
}

// 非排队任务隐藏拖动手柄（如果有的话）
.task-item:not(.is-queued) {
  .drag-handle {
    display: none;
  }
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 24px;
  color: var(--text-muted);

  svg {
    width: 48px;
    height: 48px;
    margin-bottom: 12px;
    opacity: 0.5;
  }

  p {
    font-size: 13px;
    margin: 0;
  }
}

.monitor-footer {
  padding: 12px 16px;
  border-top: 1px solid var(--border-default);

  .clear-btn {
    width: 100%;
    padding: 8px;
    background: var(--bg-tertiary);
    color: var(--text-secondary);
    border: none;
    border-radius: 6px;
    font-size: 13px;
    cursor: pointer;
    transition: background 0.2s;

    &:hover {
      background: var(--bg-elevated);
    }
  }
}
</style>
