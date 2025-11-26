<template>
  <div class="test-view">
    <h1>新前端服务测试</h1>

    <!-- 后端连接测试 -->
    <el-card class="test-section">
      <template #header>
        <div class="card-header">
          <span>后端连接测试</span>
          <el-button type="primary" @click="checkBackend" :loading="backendLoading">
            检测连接
          </el-button>
        </div>
      </template>
      <div class="status-item">
        <span>状态:</span>
        <el-tag :type="backendStatus === 'connected' ? 'success' : backendStatus === 'error' ? 'danger' : 'info'">
          {{ backendStatusText }}
        </el-tag>
      </div>
      <div v-if="backendError" class="error-message">
        {{ backendError }}
      </div>
    </el-card>

    <!-- 缓存服务测试 -->
    <el-card class="test-section">
      <template #header>
        <div class="card-header">
          <span>CacheService 测试</span>
          <el-button-group>
            <el-button @click="testCacheSet">写入</el-button>
            <el-button @click="testCacheGet">读取</el-button>
            <el-button @click="testCacheClear">清空</el-button>
            <el-button @click="refreshCacheStats">刷新统计</el-button>
          </el-button-group>
        </div>
      </template>
      <div class="cache-stats">
        <div class="stat-item">
          <span class="label">内存条目数:</span>
          <span class="value">{{ cacheStats.memory?.size || 0 }}</span>
        </div>
        <div class="stat-item">
          <span class="label">内存占用:</span>
          <span class="value">{{ formatBytes(cacheStats.memory?.bytes || 0) }}</span>
        </div>
        <div class="stat-item">
          <span class="label">命中率:</span>
          <span class="value">{{ ((cacheStats.memory?.hitRate || 0) * 100).toFixed(1) }}%</span>
        </div>
        <div class="stat-item">
          <span class="label">磁盘条目数:</span>
          <span class="value">{{ cacheStats.indexedDB?.size || 0 }}</span>
        </div>
        <div class="stat-item">
          <span class="label">总命中:</span>
          <span class="value">{{ cacheStats.total?.hits || 0 }}</span>
        </div>
        <div class="stat-item">
          <span class="label">总未命中:</span>
          <span class="value">{{ cacheStats.total?.misses || 0 }}</span>
        </div>
      </div>
      <div v-if="cacheTestResult" class="test-result">
        {{ cacheTestResult }}
      </div>
    </el-card>

    <!-- SSE 服务测试 -->
    <el-card class="test-section">
      <template #header>
        <div class="card-header">
          <span>SSEService 测试</span>
          <el-button-group>
            <el-button @click="connectSSE" :disabled="sseStatus.connected">
              连接
            </el-button>
            <el-button @click="disconnectSSE" :disabled="!sseStatus.connected">
              断开
            </el-button>
          </el-button-group>
        </div>
      </template>
      <div class="sse-stats">
        <div class="stat-item">
          <span class="label">连接状态:</span>
          <el-tag :type="sseStatus.connected ? 'success' : 'info'">
            {{ sseStatus.status }}
          </el-tag>
        </div>
        <div class="stat-item">
          <span class="label">重连次数:</span>
          <span class="value">{{ sseStats.reconnectCount }}</span>
        </div>
        <div class="stat-item">
          <span class="label">接收消息数:</span>
          <span class="value">{{ sseStats.messagesReceived }}</span>
        </div>
        <div class="stat-item">
          <span class="label">连接时长:</span>
          <span class="value">{{ formatDuration(sseStats.uptime) }}</span>
        </div>
      </div>
      <div class="sse-messages">
        <h4>接收的消息:</h4>
        <el-scrollbar height="200px">
          <div v-for="(msg, index) in sseMessages" :key="index" class="message-item">
            <el-tag size="small" :type="getMessageTagType(msg.type)">{{ msg.type }}</el-tag>
            <span class="message-content">{{ JSON.stringify(msg.data) }}</span>
            <span class="message-time">{{ formatTime(msg.timestamp) }}</span>
          </div>
          <div v-if="sseMessages.length === 0" class="no-messages">
            暂无消息
          </div>
        </el-scrollbar>
      </div>
    </el-card>

    <!-- 主题测试 -->
    <el-card class="test-section">
      <template #header>
        <div class="card-header">
          <span>主题切换测试</span>
          <el-switch
            v-model="isDark"
            active-text="深色"
            inactive-text="浅色"
            @change="toggleTheme"
          />
        </div>
      </template>
      <p>当前主题: {{ isDark ? '深色模式' : '浅色模式' }}</p>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import cacheService from '@/services/cacheService'
import sseService from '@/services/sseService'

// 后端连接状态
const backendStatus = ref('unknown')
const backendStatusText = ref('未检测')
const backendLoading = ref(false)
const backendError = ref('')

// 缓存统计
const cacheStats = reactive({
  memory: { size: 0, bytes: 0, hitRate: 0 },
  indexedDB: { size: 0 },
  total: { hits: 0, misses: 0 }
})
const cacheTestResult = ref('')

// SSE 状态
const sseStatus = reactive({ status: 'disconnected', connected: false })
const sseStats = reactive({ reconnectCount: 0, messagesReceived: 0, uptime: 0 })
const sseMessages = ref([])
let sseUnsubscribers = []
let sseStatsTimer = null

// 主题状态
const isDark = ref(true)

// 后端连接检测
async function checkBackend() {
  backendLoading.value = true
  backendError.value = ''

  try {
    const res = await fetch('/api/ping')
    if (res.ok) {
      const data = await res.json()
      backendStatus.value = 'connected'
      backendStatusText.value = '连接成功'
      console.log('[TestView] 后端连接检查:', data)
    } else {
      backendStatus.value = 'error'
      backendStatusText.value = `连接失败: ${res.status}`
    }
  } catch (e) {
    backendStatus.value = 'error'
    backendStatusText.value = '连接错误'
    backendError.value = e.message
    console.error('[TestView] 后端连接错误:', e)
  } finally {
    backendLoading.value = false
  }
}

// 缓存测试
async function testCacheSet() {
  const testKey = `test-${Date.now()}`
  const testValue = { message: '测试数据', timestamp: Date.now() }

  await cacheService.set(testKey, testValue, { ttl: 60000 })
  cacheTestResult.value = `已写入: ${testKey} = ${JSON.stringify(testValue)}`
  await refreshCacheStats()
}

async function testCacheGet() {
  const stats = await cacheService.getStats()
  // 尝试获取最近写入的数据
  const keys = Array.from({ length: 10 }, (_, i) => `test-${Date.now() - i * 1000}`)

  let found = null
  for (const key of keys) {
    const value = await cacheService.get(key)
    if (value) {
      found = { key, value }
      break
    }
  }

  if (found) {
    cacheTestResult.value = `已读取: ${found.key} = ${JSON.stringify(found.value)}`
  } else {
    cacheTestResult.value = '未找到测试数据'
  }
  await refreshCacheStats()
}

async function testCacheClear() {
  await cacheService.clear()
  cacheTestResult.value = '缓存已清空'
  await refreshCacheStats()
}

async function refreshCacheStats() {
  const stats = await cacheService.getStats()
  Object.assign(cacheStats, stats)
}

// SSE 测试
function connectSSE() {
  sseService.connect('/api/test/stream')

  // 监听连接状态
  const unsubStatus = sseService.subscribe('status', (status) => {
    Object.assign(sseStatus, sseService.getStatus())
  })
  sseUnsubscribers.push(unsubStatus)

  // 监听所有消息
  const unsubMessage = sseService.subscribe('message', (msg) => {
    sseMessages.value.unshift({
      ...msg,
      timestamp: Date.now()
    })
    // 限制消息数量
    if (sseMessages.value.length > 50) {
      sseMessages.value.pop()
    }
  })
  sseUnsubscribers.push(unsubMessage)

  // 监听连接成功
  const unsubConnected = sseService.subscribe('connected', () => {
    Object.assign(sseStatus, sseService.getStatus())
  })
  sseUnsubscribers.push(unsubConnected)

  // 监听断开
  const unsubDisconnected = sseService.subscribe('disconnected', () => {
    Object.assign(sseStatus, sseService.getStatus())
  })
  sseUnsubscribers.push(unsubDisconnected)

  // 定时更新统计
  sseStatsTimer = setInterval(() => {
    Object.assign(sseStats, sseService.getStats())
  }, 1000)
}

function disconnectSSE() {
  sseService.disconnect()
  sseUnsubscribers.forEach(unsub => unsub())
  sseUnsubscribers = []
  if (sseStatsTimer) {
    clearInterval(sseStatsTimer)
    sseStatsTimer = null
  }
  Object.assign(sseStatus, sseService.getStatus())
}

// 主题切换
function toggleTheme() {
  if (isDark.value) {
    document.documentElement.removeAttribute('data-theme')
  } else {
    document.documentElement.setAttribute('data-theme', 'light')
  }
}

// 辅助函数
function formatBytes(bytes) {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

function formatDuration(ms) {
  if (ms < 1000) return `${ms}ms`
  const seconds = Math.floor(ms / 1000)
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  return `${minutes}m ${seconds % 60}s`
}

function formatTime(timestamp) {
  return new Date(timestamp).toLocaleTimeString()
}

function getMessageTagType(type) {
  const typeMap = {
    'task_progress': 'primary',
    'task_complete': 'success',
    'task_failed': 'danger',
    'heartbeat': 'info'
  }
  return typeMap[type] || 'default'
}

// 生命周期
onMounted(async () => {
  await refreshCacheStats()
  // 初始化主题
  if (!isDark.value) {
    document.documentElement.setAttribute('data-theme', 'light')
  }
})

onUnmounted(() => {
  disconnectSSE()
})
</script>

<style lang="scss" scoped>
.test-view {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;

  h1 {
    margin-bottom: 24px;
    color: var(--text-bright);
  }
}

.test-section {
  margin-bottom: 24px;
  background: var(--bg-secondary);
  border-color: var(--border-color);

  :deep(.el-card__header) {
    background: var(--bg-tertiary);
    border-color: var(--border-color);
  }

  :deep(.el-card__body) {
    color: var(--text-normal);
  }
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.status-item,
.stat-item {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;

  .label {
    color: var(--text-muted);
    min-width: 100px;
  }

  .value {
    color: var(--text-normal);
    font-family: monospace;
  }
}

.cache-stats,
.sse-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}

.test-result {
  padding: 12px;
  background: var(--bg-tertiary);
  border-radius: 4px;
  font-family: monospace;
  font-size: 13px;
  color: var(--accent-green);
}

.error-message {
  padding: 12px;
  background: rgba(245, 108, 108, 0.1);
  border-radius: 4px;
  color: var(--accent-red);
}

.sse-messages {
  h4 {
    margin-bottom: 12px;
    color: var(--text-muted);
  }
}

.message-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px;
  border-bottom: 1px solid var(--border-color);

  .message-content {
    flex: 1;
    font-family: monospace;
    font-size: 12px;
    color: var(--text-normal);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .message-time {
    font-size: 12px;
    color: var(--text-muted);
  }
}

.no-messages {
  padding: 24px;
  text-align: center;
  color: var(--text-muted);
}
</style>
