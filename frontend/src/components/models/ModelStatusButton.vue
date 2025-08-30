<template>
  <el-button
    :type="statusType"
    size="small"
    @click="showDialog = true"
    :plain="statusType !== 'danger'"
    :loading="modelStatus.is_preloading"
  >
    <el-icon>
      <component :is="statusIcon" />
    </el-icon>
    {{ statusText }}
  </el-button>

  <!-- 模型状态对话框 -->
  <el-dialog
    v-model="showDialog"
    title="模型预加载状态"
    width="800px"
    :close-on-click-modal="false"
  >
    <div class="model-status-content">
      <!-- 预加载状态 -->
      <el-card class="status-card" shadow="never">
        <template #header>
          <div class="card-header">
            <el-icon><Cpu /></el-icon>
            <span>预加载状态</span>
            <div class="header-actions">
              <el-button
                type="primary"
                size="small"
                :loading="modelStatus.is_preloading"
                @click="startPreload"
                :disabled="modelStatus.is_preloading"
              >
                {{ modelStatus.is_preloading ? "预加载中..." : "开始预加载" }}
              </el-button>
              <el-button type="warning" size="small" @click="clearModelCache">
                清空缓存
              </el-button>
            </div>
          </div>
        </template>

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
      </el-card>

      <!-- 缓存状态 -->
      <el-row :gutter="16" class="cache-section">
        <el-col :span="12">
          <el-card class="cache-card" shadow="never">
            <template #header>
              <div class="card-header">
                <el-icon><Microphone /></el-icon>
                <span>Whisper模型缓存</span>
              </div>
            </template>
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
                  <div class="load-time">
                    加载: {{ model.load_time?.toFixed(2) }}s
                  </div>
                </div>
              </div>
            </div>
            <el-empty v-else description="暂无缓存的模型" :image-size="60" />
          </el-card>
        </el-col>

        <el-col :span="12">
          <el-card class="cache-card" shadow="never">
            <template #header>
              <div class="card-header">
                <el-icon><EditPen /></el-icon>
                <span>对齐模型缓存</span>
              </div>
            </template>
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
            <el-empty
              v-else
              description="暂无缓存的对齐模型"
              :image-size="60"
            />
          </el-card>
        </el-col>
      </el-row>

      <!-- 内存使用情况 -->
      <el-card class="memory-card" shadow="never">
        <template #header>
          <div class="card-header">
            <el-icon><Monitor /></el-icon>
            <span>内存使用情况</span>
          </div>
        </template>
        <el-row :gutter="16">
          <el-col :span="12">
            <div class="memory-item">
              <div class="memory-label">系统内存</div>
              <el-progress
                :percentage="
                  Math.round(
                    cacheStatus.memory_info?.system_memory_percent || 0
                  )
                "
                :color="
                  getMemoryColor(
                    cacheStatus.memory_info?.system_memory_percent || 0
                  )
                "
                :stroke-width="12"
              />
              <div class="memory-text">
                {{
                  (cacheStatus.memory_info?.system_memory_used || 0).toFixed(1)
                }}GB /
                {{
                  (cacheStatus.memory_info?.system_memory_total || 0).toFixed(
                    1
                  )
                }}GB
              </div>
            </div>
          </el-col>
          <el-col :span="12" v-if="cacheStatus.memory_info?.gpu_memory_total">
            <div class="memory-item">
              <div class="memory-label">GPU内存</div>
              <el-progress
                :percentage="Math.round(getGpuMemoryPercent())"
                :color="getMemoryColor(getGpuMemoryPercent())"
                :stroke-width="12"
              />
              <div class="memory-text">
                {{
                  (cacheStatus.memory_info?.gpu_memory_allocated || 0).toFixed(
                    1
                  )
                }}GB /
                {{
                  (cacheStatus.memory_info?.gpu_memory_total || 0).toFixed(1)
                }}GB
              </div>
            </div>
          </el-col>
        </el-row>

        <div class="cache-summary">
          <el-descriptions :column="2" size="small" border>
            <el-descriptions-item label="模型缓存总计">
              {{ cacheStatus.total_memory_mb || 0 }}MB
            </el-descriptions-item>
            <el-descriptions-item label="最大缓存数量">
              {{ cacheStatus.max_cache_size || 0 }}
            </el-descriptions-item>
          </el-descriptions>
        </div>
      </el-card>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  Warning,
  Loading,
  CircleCheckFilled,
  Cpu,
  Monitor,
  Microphone,
  EditPen,
} from "@element-plus/icons-vue";
import { modelAPI } from "../../services/api.js";

const showDialog = ref(false);

// 模型状态数据
const modelStatus = reactive({
  is_preloading: false,
  progress: 0,
  current_model: "",
  total_models: 0,
  loaded_models: 0,
  errors: [],
});

const cacheStatus = reactive({
  whisper_models: [],
  align_models: [],
  total_memory_mb: 0,
  max_cache_size: 0,
  memory_info: {},
});

const updateTimer = ref(null);

// 计算属性
const statusType = computed(() => {
  if (modelStatus.errors.length > 0) return "danger";
  if (modelStatus.is_preloading) return "warning";
  if (modelStatus.loaded_models > 0) return "success";
  return "info";
});

const statusText = computed(() => {
  if (modelStatus.is_preloading) {
    return `模型加载中...`;
  }
  if (modelStatus.errors.length > 0) {
    return "模型错误";
  }
  if (modelStatus.loaded_models > 0) {
    return `模型已就绪`;
  }
  return "模型状态";
});

const statusIcon = computed(() => {
  if (modelStatus.errors.length > 0) return "Warning";
  if (modelStatus.is_preloading) return "Loading";
  if (modelStatus.loaded_models > 0) return "CircleCheckFilled";
  return "Cpu";
});

// 方法
async function updateModelStatus() {
  try {
    const [preloadRes, cacheRes] = await Promise.all([
      modelAPI.getPreloadStatus(),
      modelAPI.getCacheStatus(),
    ]);

    if (preloadRes.success) {
      Object.assign(modelStatus, preloadRes.data);
    }

    if (cacheRes.success) {
      Object.assign(cacheStatus, cacheRes.data);
    }
  } catch (error) {
    console.error("更新模型状态失败:", error);
  }
}

async function startPreload() {
  try {
    const result = await modelAPI.startPreload();
    if (result.success) {
      ElMessage.success("模型预加载已启动");
      await updateModelStatus();
    } else {
      ElMessage.error(result.message || "启动预加载失败");
    }
  } catch (error) {
    console.error("启动预加载失败:", error);
    ElMessage.error(
      "启动预加载失败: " + (error.response?.data?.message || error.message)
    );
  }
}

async function clearModelCache() {
  try {
    await ElMessageBox.confirm(
      "确定要清空所有模型缓存吗？这将释放内存但需要重新加载模型。",
      "确认操作",
      {
        type: "warning",
      }
    );

    const result = await modelAPI.clearCache();
    if (result.success) {
      ElMessage.success("模型缓存已清空");
      await updateModelStatus();
    } else {
      ElMessage.error(result.message || "清空缓存失败");
    }
  } catch (error) {
    if (error !== "cancel") {
      console.error("清空缓存失败:", error);
      ElMessage.error(
        "清空缓存失败: " + (error.response?.data?.message || error.message)
      );
    }
  }
}

function getMemoryColor(percent) {
  if (percent < 50) return "#67c23a";
  if (percent < 75) return "#e6a23c";
  return "#f56c6c";
}

function getGpuMemoryPercent() {
  const total = cacheStatus.memory_info?.gpu_memory_total || 0;
  const allocated = cacheStatus.memory_info?.gpu_memory_allocated || 0;
  return total > 0 ? (allocated / total) * 100 : 0;
}

function startStatusUpdates() {
  updateModelStatus();
  updateTimer.value = setInterval(updateModelStatus, 5000);
}

// 生命周期
onMounted(() => {
  startStatusUpdates();
});

onUnmounted(() => {
  if (updateTimer.value) {
    clearInterval(updateTimer.value);
  }
});
</script>

<style scoped>
.model-status-content {
  max-height: 70vh;
  overflow-y: auto;
}

.status-card,
.cache-card,
.memory-card {
  margin-bottom: 16px;
}

.status-card:last-child,
.cache-card:last-child,
.memory-card:last-child {
  margin-bottom: 0;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
}

.header-actions {
  margin-left: auto;
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
  font-size: 14px;
  color: #606266;
}

.error-section,
.success-section {
  margin-bottom: 16px;
}

.error-list {
  margin: 0;
  padding-left: 20px;
}

.cache-section {
  margin-bottom: 16px;
}

.model-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid #f0f0f0;
}

.model-item:last-child {
  border-bottom: none;
}

.model-info {
  flex: 1;
}

.model-name {
  font-weight: 500;
  color: #303133;
  margin-bottom: 4px;
}

.model-details {
  font-size: 12px;
  color: #909399;
}

.model-stats {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
}

.load-time {
  font-size: 12px;
  color: #909399;
}

.align-models {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.align-tag {
  margin: 0;
}

.memory-item {
  margin-bottom: 16px;
}

.memory-label {
  font-size: 14px;
  font-weight: 500;
  color: #606266;
  margin-bottom: 8px;
}

.memory-text {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
  text-align: center;
}

.cache-summary {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #f0f0f0;
}
</style>
