/**
 * 模型管理全局状态 Store
 * 统一管理SSE连接和模型状态，确保单例模式
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { ModelManagerService } from '../services/modelManagerService.js'

export const useModelStore = defineStore('model', () => {
  // ========== 状态定义 ==========

  // Whisper模型列表
  const whisperModels = ref([])

  // 对齐模型列表
  const alignModels = ref([])

  // SSE连接实例（单例）
  let eventSource = null

  // SSE连接状态
  const sseConnected = ref(false)

  // 最后更新时间
  const lastUpdate = ref(0)

  // 加载状态
  const loading = ref(false)

  // ========== 计算属性 ==========

  // 获取正在下载的模型数量
  const downloadingCount = computed(() => {
    const whisperDownloading = whisperModels.value.filter(m => m.status === 'downloading').length
    const alignDownloading = alignModels.value.filter(m => m.status === 'downloading').length
    return whisperDownloading + alignDownloading
  })

  // 获取已就绪的Whisper模型数量
  const readyWhisperCount = computed(() => {
    return whisperModels.value.filter(m => m.status === 'ready').length
  })

  // 获取已就绪的对齐模型数量
  const readyAlignCount = computed(() => {
    return alignModels.value.filter(m => m.status === 'ready').length
  })

  // ========== 方法定义 ==========

  /**
   * 加载所有模型列表
   */
  async function loadModels() {
    loading.value = true
    try {
      const [whisper, align] = await Promise.all([
        ModelManagerService.getWhisperModels(),
        ModelManagerService.getAlignModels()
      ])

      whisperModels.value = whisper
      alignModels.value = align
      lastUpdate.value = Date.now()

      console.log('[ModelStore] 模型列表已加载:', {
        whisper: whisper.length,
        align: align.length
      })
    } catch (error) {
      console.error('[ModelStore] 加载模型列表失败:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  /**
   * 更新单个模型的状态
   */
  function updateModelProgress(type, modelId, progress, status) {
    if (type === 'whisper') {
      const model = whisperModels.value.find(m => m.model_id === modelId)
      if (model) {
        model.download_progress = progress
        model.status = status
        lastUpdate.value = Date.now()
        console.log(`[ModelStore] Whisper模型更新: ${modelId} - ${status} (${progress}%)`)
      }
    } else if (type === 'align') {
      const model = alignModels.value.find(m => m.language === modelId)
      if (model) {
        model.download_progress = progress
        model.status = status
        lastUpdate.value = Date.now()
        console.log(`[ModelStore] 对齐模型更新: ${modelId} - ${status} (${progress}%)`)
      }
    }
  }

  /**
   * 建立SSE连接（单例模式）
   */
  function connectSSE() {
    // 如果已有连接，直接返回
    if (eventSource) {
      console.log("[ModelStore] SSE连接已存在，跳过创建");
      return;
    }

    console.log("[ModelStore] 建立全局SSE连接...");
    eventSource = ModelManagerService.createProgressSSE();

    // 连接打开
    eventSource.onopen = () => {
      console.log("[ModelStore] SSE连接已建立");
      sseConnected.value = true;
    };

    // 监听初始状态
    eventSource.addEventListener("initial_state", (e) => {
      const data = JSON.parse(e.data);
      console.log("[ModelStore] 收到初始状态:", data);

      // 更新Whisper模型状态
      if (data.whisper) {
        Object.entries(data.whisper).forEach(([modelId, state]) => {
          updateModelProgress("whisper", modelId, state.progress, state.status);
        });
      }

      // 更新对齐模型状态
      if (data.align) {
        Object.entries(data.align).forEach(([lang, state]) => {
          updateModelProgress("align", lang, state.progress, state.status);
        });
      }
    });

    // 监听进度更新
    eventSource.addEventListener("model_progress", (e) => {
      const data = JSON.parse(e.data);
      console.log("[ModelStore] 进度更新:", data);
      updateModelProgress(data.type, data.model_id, data.progress, data.status);
    });

    // 监听下载完成
    eventSource.addEventListener("model_complete", (e) => {
      const data = JSON.parse(e.data);
      console.log("[ModelStore] 下载完成:", data);
      updateModelProgress(data.type, data.model_id, 100, "ready");
      ElMessage.success(`模型 ${data.model_id} 下载完成！`);
    });

    // 监听下载失败
    eventSource.addEventListener("model_error", (e) => {
      const data = JSON.parse(e.data);
      console.log("[ModelStore] 下载失败:", data);
      updateModelProgress(data.type, data.model_id, 0, "error");
      ElMessage.error(
        `模型 ${data.model_id} 下载失败：${data.message || "未知错误"}`
      );
    });

    // 监听模型不完整
    eventSource.addEventListener("model_incomplete", (e) => {
      const data = JSON.parse(e.data);
      console.log("[ModelStore] 模型不完整:", data);
      updateModelProgress(data.type, data.model_id, 0, "incomplete");
      ElMessage.warning({
        message: `模型 ${data.model_id} 文件不完整，请重新下载`,
        duration: 5000,
      });
    });

    // 监听心跳
    eventSource.addEventListener("heartbeat", (e) => {
      // 心跳不打印日志，避免刷屏
    });

    // 监听连接错误
    eventSource.onerror = (error) => {
      console.error("[ModelStore] SSE连接错误:", error);
      sseConnected.value = false;
      // SSE会自动重连，无需手动处理
    };
  }

  /**
   * 断开SSE连接（仅在应用卸载时调用）
   */
  function disconnectSSE() {
    if (eventSource) {
      eventSource.close();
      eventSource = null;
      sseConnected.value = false;
      console.log("[ModelStore] SSE连接已断开");
    }
  }

  /**
   * 下载Whisper模型
   */
  async function downloadWhisperModel(modelId) {
    try {
      await ModelManagerService.downloadWhisperModel(modelId);
      ElMessage.success(`开始下载模型 ${modelId}`);
    } catch (error) {
      console.error(`[ModelStore] 下载模型失败: ${modelId}`, error);
      throw error;
    }
  }

  /**
   * 下载对齐模型
   */
  async function downloadAlignModel(language) {
    try {
      await ModelManagerService.downloadAlignModel(language);
      ElMessage.success(`开始下载对齐模型 ${language}`);
    } catch (error) {
      console.error(`[ModelStore] 下载对齐模型失败: ${language}`, error);
      throw error;
    }
  }

  /**
   * 删除Whisper模型
   */
  async function deleteWhisperModel(modelId) {
    try {
      await ModelManagerService.deleteWhisperModel(modelId);
      ElMessage.success(`模型 ${modelId} 已删除`);
      // 重新加载列表
      await loadModels();
    } catch (error) {
      console.error(`[ModelStore] 删除模型失败: ${modelId}`, error);
      throw error;
    }
  }

  /**
   * 删除对齐模型
   */
  async function deleteAlignModel(language) {
    try {
      await ModelManagerService.deleteAlignModel(language);
      ElMessage.success(`对齐模型 ${language} 已删除`);
      // 重新加载列表
      await loadModels();
    } catch (error) {
      console.error(`[ModelStore] 删除对齐模型失败: ${language}`, error);
      throw error;
    }
  }

  /**
   * 初始化（应用启动时调用一次）
   */
  async function initialize() {
    console.log("[ModelStore]  初始化模型管理器...");

    try {
      // 加载模型列表
      await loadModels();

      // 建立SSE连接
      connectSSE();

      console.log("[ModelStore] 初始化完成");
    } catch (error) {
      console.error("[ModelStore] ❌ 初始化失败:", error);
      throw error;
    }
  }

  // ========== 返回公共接口 ==========

  return {
    // 状态
    whisperModels,
    alignModels,
    sseConnected,
    lastUpdate,
    loading,

    // 计算属性
    downloadingCount,
    readyWhisperCount,
    readyAlignCount,

    // 方法
    loadModels,
    updateModelProgress,
    connectSSE,
    disconnectSSE,
    downloadWhisperModel,
    downloadAlignModel,
    deleteWhisperModel,
    deleteAlignModel,
    initialize
  }
})
