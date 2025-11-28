/**
 * CacheService - 多级缓存服务
 *
 * 提供 L1 内存缓存 (LRU) + L2 IndexedDB 持久化的两级缓存机制
 */
import localforage from 'localforage'
import { LRUCache } from 'lru-cache'

class CacheService {
  constructor(config = {}) {
    this.config = {
      memory: {
        max: 100,
        maxSize: 50 * 1024 * 1024, // 50MB
        ttl: 60 * 60 * 1000, // 1 hour
        ...config.memory
      },
      indexedDB: {
        name: 'subtitle-editor-cache',
        storeName: 'cache',
        version: 1,
        ...config.indexedDB
      },
      enableCompression: config.enableCompression ?? false, // 简化版不使用压缩
      autoCleanup: config.autoCleanup ?? true,
      cleanupInterval: config.cleanupInterval ?? 5 * 60 * 1000 // 5 minutes
    }

    // 初始化 L1 内存缓存
    this.memoryCache = new LRUCache({
      max: this.config.memory.max,
      maxSize: this.config.memory.maxSize,
      ttl: this.config.memory.ttl,
      sizeCalculation: (value) => {
        try {
          return JSON.stringify(value).length
        } catch {
          return 1000 // 默认大小估计
        }
      },
      dispose: (value, key) => {
        console.log(`[CacheService] 内存淘汰: ${key}`)
      }
    })

    // 初始化 L2 IndexedDB
    this.diskCache = localforage.createInstance({
      name: this.config.indexedDB.name,
      storeName: this.config.indexedDB.storeName,
      version: this.config.indexedDB.version
    })

    // 统计信息
    this.stats = {
      hits: 0,
      misses: 0
    }

    // 自动清理定时器
    this.cleanupTimer = null

    // 启动自动清理
    if (this.config.autoCleanup) {
      this.startAutoCleanup()
    }

    console.log('[CacheService] 缓存服务已初始化')
  }

  /**
   * 获取缓存值
   * @param {string} key 缓存键
   * @param {Object} options 选项
   * @returns {Promise<any>} 缓存值或 null
   */
  async get(key, options = {}) {
    const { preferMemory = true, skipIndexedDB = false } = options

    // L1: 内存缓存查询
    if (preferMemory && this.memoryCache.has(key)) {
      const cached = this.memoryCache.get(key)
      if (this.isValid(cached)) {
        this.stats.hits++
        console.log(`[CacheService] 内存命中: ${key}`)
        return cached.value
      }
    }

    // L2: IndexedDB 查询
    if (!skipIndexedDB) {
      try {
        const cached = await this.diskCache.getItem(key)
        if (cached && this.isValid(cached)) {
          this.stats.hits++
          console.log(`[CacheService] 磁盘命中: ${key}`)

          // 提升到内存缓存
          this.memoryCache.set(key, cached)

          return cached.value
        }
      } catch (error) {
        console.error('[CacheService] IndexedDB 读取失败:', error)
      }
    }

    this.stats.misses++
    return null
  }

  /**
   * 设置缓存值
   * @param {string} key 缓存键
   * @param {any} value 缓存值
   * @param {Object} options 选项
   */
  async set(key, value, options = {}) {
    const {
      ttl = this.config.memory.ttl,
      priority = 5,
      persistToDisk = true
    } = options

    const cached = {
      value,
      timestamp: Date.now(),
      ttl,
      priority
    }

    // L1: 写入内存缓存
    this.memoryCache.set(key, cached)

    // L2: 写入 IndexedDB
    if (persistToDisk) {
      try {
        await this.diskCache.setItem(key, cached)
        console.log(`[CacheService] 已持久化: ${key}`)
      } catch (error) {
        console.error('[CacheService] IndexedDB 写入失败:', error)
      }
    }
  }

  /**
   * 删除缓存值
   * @param {string} key 缓存键
   */
  async delete(key) {
    this.memoryCache.delete(key)
    try {
      await this.diskCache.removeItem(key)
      console.log(`[CacheService] 已删除: ${key}`)
    } catch (error) {
      console.error('[CacheService] 删除失败:', error)
    }
  }

  /**
   * 检查键是否存在
   * @param {string} key 缓存键
   * @returns {Promise<boolean>}
   */
  async has(key) {
    if (this.memoryCache.has(key)) return true

    try {
      const value = await this.diskCache.getItem(key)
      return value !== null
    } catch {
      return false
    }
  }

  /**
   * 清空所有缓存
   */
  async clear() {
    this.memoryCache.clear()
    try {
      await this.diskCache.clear()
    } catch (error) {
      console.error('[CacheService] 清空失败:', error)
    }
    this.stats.hits = 0
    this.stats.misses = 0
    console.log('[CacheService] 已清空所有缓存')
  }

  /**
   * 批量获取
   * @param {string[]} keys 键数组
   * @returns {Promise<Map>}
   */
  async getMany(keys) {
    const results = new Map()

    for (const key of keys) {
      const value = await this.get(key)
      if (value !== null) {
        results.set(key, value)
      }
    }

    return results
  }

  /**
   * 批量设置
   * @param {Array} entries 键值对数组
   * @param {Object} options 选项
   */
  async setMany(entries, options = {}) {
    const promises = entries.map(([key, value]) =>
      this.set(key, value, options)
    )

    await Promise.all(promises)
  }

  /**
   * 预加载数据
   * @param {string[]} keys 需要预加载的键
   */
  async preload(keys) {
    console.log(`[CacheService] 预加载 ${keys.length} 个键`)
    await this.getMany(keys)
  }

  /**
   * 获取统计信息
   * @returns {Promise<Object>}
   */
  async getStats() {
    const memorySize = this.memoryCache.size
    const memoryBytes = this.memoryCache.calculatedSize || 0

    // 估算 IndexedDB 大小
    let diskSize = 0
    try {
      const keys = await this.diskCache.keys()
      diskSize = keys.length
    } catch (error) {
      console.error('[CacheService] 获取磁盘统计失败:', error)
    }

    const totalRequests = this.stats.hits + this.stats.misses
    const hitRate = totalRequests > 0 ? this.stats.hits / totalRequests : 0

    return {
      memory: {
        size: memorySize,
        bytes: memoryBytes,
        hitRate
      },
      indexedDB: {
        size: diskSize,
        bytes: 0 // 无法精确计算
      },
      total: {
        hits: this.stats.hits,
        misses: this.stats.misses
      }
    }
  }

  /**
   * 手动清理过期缓存
   */
  async cleanup() {
    console.log('[CacheService] 执行清理')

    try {
      const keys = await this.diskCache.keys()

      for (const key of keys) {
        const cached = await this.diskCache.getItem(key)
        if (!this.isValid(cached)) {
          await this.diskCache.removeItem(key)
          console.log(`[CacheService] 清理过期: ${key}`)
        }
      }
    } catch (error) {
      console.error('[CacheService] 清理失败:', error)
    }
  }

  /**
   * 启动自动清理
   */
  startAutoCleanup() {
    this.stopAutoCleanup()

    this.cleanupTimer = setInterval(() => {
      this.cleanup()
    }, this.config.cleanupInterval)
  }

  /**
   * 停止自动清理
   */
  stopAutoCleanup() {
    if (this.cleanupTimer) {
      clearInterval(this.cleanupTimer)
      this.cleanupTimer = null
    }
  }

  /**
   * 检查缓存是否有效
   * @param {Object} cached 缓存对象
   * @returns {boolean}
   */
  isValid(cached) {
    if (!cached || !cached.timestamp) return false

    const age = Date.now() - cached.timestamp
    return age < cached.ttl
  }

  /**
   * 销毁服务
   */
  destroy() {
    this.stopAutoCleanup()
    this.memoryCache.clear()
    console.log('[CacheService] 缓存服务已销毁')
  }
}

// 导出单例
export const cacheService = new CacheService()
export default cacheService
