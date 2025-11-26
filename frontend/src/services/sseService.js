/**
 * SSEService - Server-Sent Events 服务
 *
 * 基于 EventSource 的实时通信服务，支持自动重连、心跳检测、降级轮询
 */
import EventEmitter from 'eventemitter3'

class SSEService extends EventEmitter {
  constructor(config = {}) {
    super()

    this.config = {
      withCredentials: true,
      reconnect: true,
      reconnectInterval: 1000,        // 初始重连间隔 (ms)
      reconnectDecay: 1.5,            // 退避系数
      maxReconnectInterval: 30000,    // 最大重连间隔 (ms)
      maxReconnectAttempts: Infinity, // 最大重连次数
      heartbeatInterval: 30000,       // 心跳间隔 (ms)
      heartbeatTimeout: 10000,        // 心跳超时 (ms)
      messageQueueSize: 100,          // 消息队列大小
      enableDedup: true,              // 启用去重
      fallbackToPolling: true,        // 降级到轮询
      pollingInterval: 5000,          // 轮询间隔 (ms)
      ...config
    }

    // 连接状态
    this.eventSource = null
    this.status = 'disconnected'
    this.reconnectCount = 0
    this.currentReconnectInterval = this.config.reconnectInterval
    this.messageQueue = []
    this.lastMessageId = null

    // 定时器
    this.heartbeatTimer = null
    this.reconnectTimer = null
    this.pollingTimer = null

    // 统计信息
    this.stats = {
      messagesReceived: 0,
      lastMessageTime: null,
      connectedAt: null
    }

    // 去重集合
    this.processedMessageIds = new Set()

    console.log('[SSEService] 服务已初始化')
  }

  /**
   * 连接到 SSE 端点
   * @param {string} url SSE URL
   * @param {Object} config 配置选项
   */
  connect(url, config = {}) {
    if (this.status === 'connected' || this.status === 'connecting') {
      console.warn('[SSEService] 已经连接或正在连接')
      return
    }

    // 更新配置
    if (url) this.config.url = url
    Object.assign(this.config, config)

    if (!this.config.url) {
      console.error('[SSEService] 未指定 URL')
      return
    }

    this.setStatus('connecting')
    this.createEventSource()
  }

  /**
   * 创建 EventSource 连接
   */
  createEventSource() {
    try {
      // 构建 URL（包含 Last-Event-ID）
      const url = new URL(this.config.url, window.location.origin)
      if (this.lastMessageId) {
        url.searchParams.set('lastEventId', this.lastMessageId)
      }

      this.eventSource = new EventSource(url.toString(), {
        withCredentials: this.config.withCredentials
      })

      // 连接打开
      this.eventSource.onopen = () => {
        console.log('[SSEService] 连接成功')
        this.setStatus('connected')
        this.reconnectCount = 0
        this.currentReconnectInterval = this.config.reconnectInterval
        this.stats.connectedAt = Date.now()
        this.emit('connected')
        this.startHeartbeat()
        this.processMessageQueue()
      }

      // 接收通用消息
      this.eventSource.onmessage = (event) => {
        this.handleMessage('message', event)
      }

      // 连接错误
      this.eventSource.onerror = (error) => {
        console.error('[SSEService] 连接错误:', error)
        this.handleError(error)
      }

      // 注册自定义事件监听器
      this.registerCustomEvents()
    } catch (error) {
      console.error('[SSEService] 创建 EventSource 失败:', error)
      this.handleError(error)
    }
  }

  /**
   * 注册自定义事件类型
   */
  registerCustomEvents() {
    if (!this.eventSource) return

    // 任务进度事件
    this.eventSource.addEventListener('task_progress', (event) => {
      this.handleMessage('task_progress', event)
    })

    // 任务完成事件
    this.eventSource.addEventListener('task_complete', (event) => {
      this.handleMessage('task_complete', event)
    })

    // 任务失败事件
    this.eventSource.addEventListener('task_failed', (event) => {
      this.handleMessage('task_failed', event)
    })

    // 心跳事件
    this.eventSource.addEventListener('heartbeat', (event) => {
      this.handleHeartbeat(event)
    })
  }

  /**
   * 处理消息
   * @param {string} type 消息类型
   * @param {MessageEvent} event 消息事件
   */
  handleMessage(type, event) {
    try {
      const data = JSON.parse(event.data)

      // 更新统计
      this.stats.messagesReceived++
      this.stats.lastMessageTime = Date.now()

      // 记录最后的消息 ID
      if (event.lastEventId) {
        this.lastMessageId = event.lastEventId
      }

      // 去重检查
      if (this.config.enableDedup && data.id) {
        if (this.processedMessageIds.has(data.id)) {
          console.log(`[SSEService] 忽略重复消息: ${data.id}`)
          return
        }
        this.processedMessageIds.add(data.id)

        // 限制集合大小
        if (this.processedMessageIds.size > 1000) {
          const firstItem = this.processedMessageIds.values().next().value
          this.processedMessageIds.delete(firstItem)
        }
      }

      // 触发事件
      this.emit(type, data)
      this.emit('message', { type, data })

      console.log(`[SSEService] 收到消息 [${type}]:`, data)
    } catch (error) {
      console.error('[SSEService] 消息解析失败:', error, event.data)
    }
  }

  /**
   * 处理心跳
   * @param {MessageEvent} event 心跳事件
   */
  handleHeartbeat(event) {
    console.log('[SSEService] 心跳响应')
    this.resetHeartbeat()
  }

  /**
   * 处理错误
   * @param {Event} error 错误事件
   */
  handleError(error) {
    this.emit('error', error)

    // 如果连接已关闭
    if (this.eventSource?.readyState === EventSource.CLOSED) {
      this.setStatus('disconnected')
      this.stopHeartbeat()

      // 尝试重连
      if (this.config.reconnect && this.reconnectCount < this.config.maxReconnectAttempts) {
        this.scheduleReconnect()
      } else {
        this.setStatus('failed')
        console.error('[SSEService] 连接失败，不再重连')

        // 降级到轮询
        if (this.config.fallbackToPolling) {
          this.startPolling()
        }
      }
    }
  }

  /**
   * 计划重连
   */
  scheduleReconnect() {
    this.setStatus('reconnecting')
    this.reconnectCount++

    console.log(`[SSEService] ${this.currentReconnectInterval}ms 后尝试第 ${this.reconnectCount} 次重连`)

    this.reconnectTimer = setTimeout(() => {
      if (this.status === 'reconnecting') {
        this.createEventSource()

        // 指数退避
        this.currentReconnectInterval = Math.min(
          this.currentReconnectInterval * this.config.reconnectDecay,
          this.config.maxReconnectInterval
        )
      }
    }, this.currentReconnectInterval)
  }

  /**
   * 手动重连
   */
  reconnect() {
    this.disconnect()
    this.reconnectCount = 0
    this.currentReconnectInterval = this.config.reconnectInterval
    this.connect()
  }

  /**
   * 断开连接
   */
  disconnect() {
    console.log('[SSEService] 断开连接')

    if (this.eventSource) {
      this.eventSource.close()
      this.eventSource = null
    }

    this.stopHeartbeat()
    this.stopPolling()
    this.clearReconnectTimer()
    this.setStatus('disconnected')
    this.emit('disconnected')
  }

  /**
   * 清除重连定时器
   */
  clearReconnectTimer() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
  }

  /**
   * 启动心跳检测
   */
  startHeartbeat() {
    this.stopHeartbeat()

    this.heartbeatTimer = setTimeout(() => {
      console.warn('[SSEService] 心跳超时，触发重连')
      this.handleError(new Error('心跳超时'))
    }, this.config.heartbeatInterval + this.config.heartbeatTimeout)
  }

  /**
   * 重置心跳
   */
  resetHeartbeat() {
    this.startHeartbeat()
  }

  /**
   * 停止心跳
   */
  stopHeartbeat() {
    if (this.heartbeatTimer) {
      clearTimeout(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
  }

  /**
   * 启动降级轮询
   */
  startPolling() {
    console.log('[SSEService] 启动轮询模式')
    this.stopPolling()

    this.pollingTimer = setInterval(async () => {
      try {
        // 替换 /stream 为 /poll
        const pollUrl = this.config.url.replace('/stream', '/poll')
        const response = await fetch(pollUrl, {
          method: 'GET',
          credentials: this.config.withCredentials ? 'include' : 'omit',
          headers: {
            'Last-Event-ID': this.lastMessageId || ''
          }
        })

        if (!response.ok) throw new Error(`HTTP ${response.status}`)

        const data = await response.json()

        if (data.events && Array.isArray(data.events)) {
          data.events.forEach(event => {
            this.handleMessage(event.type || 'message', {
              data: JSON.stringify(event.data),
              lastEventId: event.id
            })
          })
        }
      } catch (error) {
        console.error('[SSEService] 轮询失败:', error)
      }
    }, this.config.pollingInterval)
  }

  /**
   * 停止轮询
   */
  stopPolling() {
    if (this.pollingTimer) {
      clearInterval(this.pollingTimer)
      this.pollingTimer = null
    }
  }

  /**
   * 消息入队
   * @param {string} type 消息类型
   * @param {any} data 消息数据
   */
  queueMessage(type, data) {
    this.messageQueue.push({ type, data, timestamp: Date.now() })

    // 限制队列大小
    if (this.messageQueue.length > this.config.messageQueueSize) {
      this.messageQueue.shift()
    }
  }

  /**
   * 处理消息队列
   */
  processMessageQueue() {
    while (this.messageQueue.length > 0) {
      const message = this.messageQueue.shift()
      this.emit(message.type, message.data)
    }
  }

  /**
   * 清空消息队列
   */
  clearQueue() {
    this.messageQueue = []
  }

  /**
   * 订阅事件
   * @param {string} event 事件类型
   * @param {Function} handler 处理函数
   * @returns {Function} 取消订阅函数
   */
  subscribe(event, handler) {
    this.on(event, handler)

    // 返回取消订阅函数
    return () => {
      this.off(event, handler)
    }
  }

  /**
   * 取消订阅
   * @param {string} event 事件类型
   * @param {Function} handler 处理函数
   */
  unsubscribe(event, handler) {
    if (handler) {
      this.off(event, handler)
    } else {
      this.removeAllListeners(event)
    }
  }

  /**
   * 设置连接状态
   * @param {string} status 状态
   */
  setStatus(status) {
    if (this.status !== status) {
      const oldStatus = this.status
      this.status = status
      this.emit('status', { old: oldStatus, new: status })
    }
  }

  /**
   * 获取连接状态
   * @returns {Object}
   */
  getStatus() {
    return {
      status: this.status,
      connected: this.status === 'connected',
      reconnecting: this.status === 'reconnecting'
    }
  }

  /**
   * 获取统计信息
   * @returns {Object}
   */
  getStats() {
    return {
      status: this.status,
      connected: this.status === 'connected',
      reconnectCount: this.reconnectCount,
      messagesReceived: this.stats.messagesReceived,
      lastMessageTime: this.stats.lastMessageTime,
      uptime: this.stats.connectedAt ? Date.now() - this.stats.connectedAt : 0
    }
  }

  /**
   * 销毁服务
   */
  destroy() {
    this.disconnect()
    this.removeAllListeners()
    this.messageQueue = []
    this.processedMessageIds.clear()
    console.log('[SSEService] 服务已销毁')
  }
}

// 导出单例
export const sseService = new SSEService()
export default sseService
