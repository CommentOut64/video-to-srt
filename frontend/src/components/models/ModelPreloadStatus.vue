<template>
  <div class="model-preload-status">
    <div class="status-header">
      <h3>
        <i class="fas fa-brain"></i>
        模型预加载状态
      </h3>
      <div class="status-actions">
        <button
          @click="refreshStatus"
          class="btn btn-secondary btn-sm"
          :disabled="isRefreshing"
        >
          <i class="fas fa-sync" :class="{ 'fa-spin': isRefreshing }"></i>
          刷新
        </button>
        <button
          @click="startPreload"
          class="btn btn-primary btn-sm"
          :disabled="preloadStatus.is_preloading || isStartingPreload"
        >
          <i class="fas fa-play"></i>
          {{ preloadStatus.is_preloading ? "预加载中..." : "开始预加载" }}
        </button>
        <button
          @click="clearCache"
          class="btn btn-warning btn-sm"
          :disabled="isClearingCache"
        >
          <i class="fas fa-trash"></i>
          清空缓存
        </button>
      </div>
    </div>

    <!-- 预加载进度 -->
    <div v-if="preloadStatus.is_preloading" class="preload-progress">
      <div class="progress-info">
        <span>正在加载: {{ preloadStatus.current_model || "准备中..." }}</span>
        <span
          >{{ preloadStatus.loaded_models }}/{{
            preloadStatus.total_models
          }}</span
        >
      </div>
      <div class="progress">
        <div
          class="progress-bar progress-bar-striped progress-bar-animated"
          :style="{ width: preloadStatus.progress + '%' }"
        >
          {{ Math.round(preloadStatus.progress) }}%
        </div>
      </div>
    </div>

    <!-- 错误信息 -->
    <div
      v-if="preloadStatus.errors && preloadStatus.errors.length > 0"
      class="alert alert-warning"
    >
      <h6><i class="fas fa-exclamation-triangle"></i> 预加载警告:</h6>
      <ul class="mb-0">
        <li v-for="error in preloadStatus.errors" :key="error">{{ error }}</li>
      </ul>
    </div>

    <!-- 缓存状态 -->
    <div class="cache-status">
      <div class="row">
        <!-- Whisper模型缓存 -->
        <div class="col-md-6">
          <div class="card">
            <div class="card-header">
              <h6><i class="fas fa-microphone"></i> Whisper模型缓存</h6>
            </div>
            <div class="card-body">
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
                    <strong>{{ model.key[0] }}</strong>
                    <small class="text-muted">
                      {{ model.key[1] }} / {{ model.key[2] }}
                    </small>
                  </div>
                  <div class="model-stats">
                    <span class="badge badge-info"
                      >{{ model.memory_mb }}MB</span
                    >
                    <small class="text-muted">
                      加载耗时: {{ model.load_time?.toFixed(2) }}s
                    </small>
                  </div>
                </div>
              </div>
              <div v-else class="text-muted text-center">
                <i class="fas fa-inbox"></i> 暂无缓存的模型
              </div>
            </div>
          </div>
        </div>

        <!-- 对齐模型缓存 -->
        <div class="col-md-6">
          <div class="card">
            <div class="card-header">
              <h6><i class="fas fa-language"></i> 对齐模型缓存</h6>
            </div>
            <div class="card-body">
              <div
                v-if="
                  cacheStatus.align_models &&
                  cacheStatus.align_models.length > 0
                "
              >
                <div
                  v-for="lang in cacheStatus.align_models"
                  :key="lang"
                  class="align-model-item"
                >
                  <span class="badge badge-secondary">{{ lang }}</span>
                </div>
              </div>
              <div v-else class="text-muted text-center">
                <i class="fas fa-inbox"></i> 暂无缓存的对齐模型
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 内存使用情况 -->
      <div class="memory-status mt-3">
        <div class="card">
          <div class="card-header">
            <h6><i class="fas fa-memory"></i> 内存使用情况</h6>
          </div>
          <div class="card-body">
            <div class="row">
              <div class="col-md-6">
                <div class="memory-info">
                  <div class="memory-label">系统内存</div>
                  <div class="progress mb-2">
                    <div
                      class="progress-bar"
                      :class="
                        getMemoryBarClass(memoryInfo.system_memory_percent)
                      "
                      :style="{
                        width: (memoryInfo.system_memory_percent || 0) + '%',
                      }"
                    >
                      {{ Math.round(memoryInfo.system_memory_percent || 0) }}%
                    </div>
                  </div>
                  <small class="text-muted">
                    {{ (memoryInfo.system_memory_used || 0).toFixed(1) }}GB /
                    {{ (memoryInfo.system_memory_total || 0).toFixed(1) }}GB
                  </small>
                </div>
              </div>
              <div class="col-md-6" v-if="memoryInfo.gpu_memory_total">
                <div class="memory-info">
                  <div class="memory-label">GPU内存</div>
                  <div class="progress mb-2">
                    <div
                      class="progress-bar"
                      :class="getMemoryBarClass(gpuMemoryPercent)"
                      :style="{ width: gpuMemoryPercent + '%' }"
                    >
                      {{ Math.round(gpuMemoryPercent) }}%
                    </div>
                  </div>
                  <small class="text-muted">
                    {{ (memoryInfo.gpu_memory_allocated || 0).toFixed(1) }}GB /
                    {{ (memoryInfo.gpu_memory_total || 0).toFixed(1) }}GB
                  </small>
                </div>
              </div>
            </div>

            <!-- 模型缓存内存统计 -->
            <div class="mt-3">
              <div class="cache-memory-stats">
                <span class="stat-item">
                  <strong>模型缓存总计:</strong>
                  {{ cacheStatus.total_memory_mb || 0 }}MB
                </span>
                <span class="stat-item">
                  <strong>最大缓存数量:</strong>
                  {{ cacheStatus.max_cache_size || 0 }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { modelAPI } from "../../services/api.js";

export default {
  name: "ModelPreloadStatus",
  data() {
    return {
      preloadStatus: {
        is_preloading: false,
        progress: 0,
        current_model: "",
        total_models: 0,
        loaded_models: 0,
        errors: [],
      },
      cacheStatus: {
        whisper_models: [],
        align_models: [],
        total_memory_mb: 0,
        max_cache_size: 0,
        memory_info: {},
      },
      isRefreshing: false,
      isStartingPreload: false,
      isClearingCache: false,
      updateInterval: null,
    };
  },
  computed: {
    memoryInfo() {
      return this.cacheStatus.memory_info || {};
    },
    gpuMemoryPercent() {
      const total = this.memoryInfo.gpu_memory_total;
      const allocated = this.memoryInfo.gpu_memory_allocated;
      return total > 0 ? (allocated / total) * 100 : 0;
    },
  },
  mounted() {
    this.loadStatus();
    // 定期更新状态
    this.updateInterval = setInterval(() => {
      if (!this.isRefreshing) {
        this.loadStatus();
      }
    }, 5000);
  },
  beforeUnmount() {
    if (this.updateInterval) {
      clearInterval(this.updateInterval);
    }
  },
  methods: {
    async loadStatus() {
      try {
        // 并行加载预加载状态和缓存状态
        const [preloadRes, cacheRes] = await Promise.all([
          modelAPI.getPreloadStatus(),
          modelAPI.getCacheStatus(),
        ]);

        if (preloadRes.success) {
          this.preloadStatus = preloadRes.data;
        }

        if (cacheRes.success) {
          this.cacheStatus = cacheRes.data;
        }
      } catch (error) {
        console.error("加载模型状态失败:", error);
        this.$emit("error", "加载模型状态失败: " + error.message);
      }
    },

    async refreshStatus() {
      this.isRefreshing = true;
      try {
        await this.loadStatus();
        this.$emit("message", "状态已刷新");
      } catch (error) {
        this.$emit("error", "刷新状态失败: " + error.message);
      } finally {
        this.isRefreshing = false;
      }
    },

    async startPreload() {
      this.isStartingPreload = true;
      try {
        const result = await modelAPI.startPreload();
        if (result.success) {
          this.$emit("message", "预加载已启动");
          // 开始更频繁地更新状态
          this.startProgressUpdates();
        } else {
          this.$emit("error", result.message || "启动预加载失败");
        }
      } catch (error) {
        this.$emit("error", "启动预加载失败: " + error.message);
      } finally {
        this.isStartingPreload = false;
      }
    },

    async clearCache() {
      if (
        !confirm("确定要清空所有模型缓存吗？这将释放内存但需要重新加载模型。")
      ) {
        return;
      }

      this.isClearingCache = true;
      try {
        const result = await modelAPI.clearCache();
        if (result.success) {
          this.$emit("message", "模型缓存已清空");
          await this.loadStatus();
        } else {
          this.$emit("error", result.message || "清空缓存失败");
        }
      } catch (error) {
        this.$emit("error", "清空缓存失败: " + error.message);
      } finally {
        this.isClearingCache = false;
      }
    },

    startProgressUpdates() {
      // 预加载期间更频繁地更新状态
      const progressInterval = setInterval(async () => {
        try {
          const result = await modelAPI.getPreloadStatus();
          if (result.success) {
            this.preloadStatus = result.data;

            // 预加载完成时停止频繁更新
            if (!result.data.is_preloading) {
              clearInterval(progressInterval);
              await this.loadStatus(); // 最终状态更新
            }
          }
        } catch (error) {
          console.error("更新预加载进度失败:", error);
          clearInterval(progressInterval);
        }
      }, 1000);
    },

    getMemoryBarClass(percent) {
      if (percent < 50) return "bg-success";
      if (percent < 75) return "bg-warning";
      return "bg-danger";
    },
  },
};
</script>

<style scoped>
.model-preload-status {
  padding: 1rem;
}

.status-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid #dee2e6;
}

.status-header h3 {
  margin: 0;
  color: #495057;
}

.status-header h3 i {
  margin-right: 0.5rem;
  color: #007bff;
}

.status-actions {
  display: flex;
  gap: 0.5rem;
}

.preload-progress {
  margin-bottom: 1rem;
  padding: 1rem;
  background-color: #f8f9fa;
  border-radius: 0.375rem;
  border: 1px solid #dee2e6;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  margin-bottom: 0.5rem;
  font-size: 0.875rem;
  color: #6c757d;
}

.model-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem 0;
  border-bottom: 1px solid #f8f9fa;
}

.model-item:last-child {
  border-bottom: none;
}

.model-info strong {
  color: #495057;
}

.model-stats {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.25rem;
}

.align-model-item {
  display: inline-block;
  margin: 0.25rem;
}

.memory-status .card-header h6 {
  margin: 0;
  color: #495057;
}

.memory-info {
  margin-bottom: 1rem;
}

.memory-label {
  font-size: 0.875rem;
  font-weight: 500;
  color: #6c757d;
  margin-bottom: 0.5rem;
}

.cache-memory-stats {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
}

.stat-item {
  font-size: 0.875rem;
  color: #6c757d;
}

.btn {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
}

.alert h6 {
  margin-bottom: 0.5rem;
}

.alert ul {
  padding-left: 1.25rem;
}

@media (max-width: 768px) {
  .status-header {
    flex-direction: column;
    align-items: stretch;
    gap: 1rem;
  }

  .status-actions {
    justify-content: center;
  }

  .cache-memory-stats {
    flex-direction: column;
    gap: 0.5rem;
  }
}
</style>
