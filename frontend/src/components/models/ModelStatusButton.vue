<template>
  <el-button
    :type="statusType"
    size="small"
    @click="showDialog = true"
    :loading="modelStatus.is_preloading"
    class="model-status-btn"
    :class="{
      'status-loading': modelStatus.is_preloading,
      'status-success':
        modelStatus.loaded_models > 0 && !modelStatus.is_preloading,
      'status-error': modelStatus.errors.length > 0,
      'status-idle':
        modelStatus.loaded_models === 0 &&
        !modelStatus.is_preloading &&
        modelStatus.errors.length === 0,
    }"
  >
    <el-icon v-if="!modelStatus.is_preloading">
      <component :is="statusIcon" />
    </el-icon>
    {{ statusText }}
  </el-button>

  <!-- 模型状态对话框 -->
  <el-dialog
    v-model="showDialog"
    title="模型预加载状态"
    width="600px"
    :close-on-click-modal="false"
    destroy-on-close
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
              'indicator-loading': modelStatus.is_preloading,
              'indicator-success':
                modelStatus.loaded_models > 0 && !modelStatus.is_preloading,
              'indicator-error': modelStatus.errors.length > 0,
              'indicator-idle':
                modelStatus.loaded_models === 0 &&
                !modelStatus.is_preloading &&
                modelStatus.errors.length === 0,
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
              <p>预加载失败次数已达到上限 ({{ modelStatus.failed_attempts }}/{{ modelStatus.max_retry_attempts }})。</p>
              <p>请检查系统状态后点击"重置重试"按钮重新尝试。</p>
              <p class="retry-tip">💡 提示：模型仍可在首次使用时自动加载</p>
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
import { ref, reactive, computed, onMounted, onUnmounted, watch, nextTick } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  Warning,
  Loading,
  CircleCheckFilled,
  Download,
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
  failed_attempts: 0,
  max_retry_attempts: 3,
});

const cacheStatus = reactive({
  whisper_models: [],
  align_models: [],
  total_memory_mb: 0,
  max_cache_size: 0,
  memory_info: {},
});

const updateTimer = ref(null);
const highFrequencyTimer = ref(null);

// 计算属性
const isPreloadBlocked = computed(() => {
  return modelStatus.failed_attempts >= modelStatus.max_retry_attempts;
});

const statusType = computed(() => {
  if (modelStatus.errors.length > 0) return "danger";
  if (modelStatus.is_preloading) return "warning";
  if (modelStatus.loaded_models > 0) return "success";
  return "primary";
});

const statusText = computed(() => {
  if (isPreloadBlocked.value) {
    return `重试已达上限 (${modelStatus.failed_attempts}/${modelStatus.max_retry_attempts})`;
  }
  if (modelStatus.is_preloading) {
    if (modelStatus.progress > 0) {
      return `加载中... ${Math.round(modelStatus.progress)}%`;
    }
    return "加载中...";
  }
  if (modelStatus.errors.length > 0) {
    return "加载错误";
  }
  if (modelStatus.loaded_models > 0) {
    return `已加载模型 (${modelStatus.loaded_models})`;
  }
  return "未加载模型";
});

function getPreloadButtonText() {
  if (isPreloadBlocked.value) {
    return "重试已达上限";
  }
  if (modelStatus.is_preloading) {
    return "预加载中...";
  }
  return "开始预加载";
}

const statusIcon = computed(() => {
  if (modelStatus.errors.length > 0) return "Warning";
  if (modelStatus.is_preloading) return "Loading";
  if (modelStatus.loaded_models > 0) return "CircleCheckFilled";
  return "Download";
});

// 方法
async function updateModelStatus() {
  try {
    console.log("🔄 开始更新模型状态...");
    
    const [preloadRes, cacheRes] = await Promise.all([
      modelAPI.getPreloadStatus(),
      modelAPI.getCacheStatus(),
    ]);

    if (preloadRes.success) {
      const newStatus = preloadRes.data;
      console.log("📡 服务器状态:", {
        is_preloading: newStatus.is_preloading,
        progress: newStatus.progress,
        loaded_models: newStatus.loaded_models,
        current_model: newStatus.current_model
      });
      
      // 检测状态变化
      const wasPreloading = modelStatus.is_preloading;
      const isNowPreloading = newStatus.is_preloading;
      
      // 直接更新本地状态
      Object.assign(modelStatus, newStatus);
      
      // 状态变化日志
      if (wasPreloading !== isNowPreloading) {
        if (isNowPreloading) {
          console.log("🚀 预加载已开始");
          stopRegularUpdates();
          startHighFrequencyUpdates();
        } else {
          console.log("✅ 预加载已完成");
          stopHighFrequencyUpdates();
          startRegularUpdates();
        }
      }
      
      console.log("✅ 本地状态已更新");
    } else {
      console.warn("⚠️ 获取预加载状态失败:", preloadRes.message);
    }

    if (cacheRes.success) {
      Object.assign(cacheStatus, cacheRes.data);
      console.log("💾 缓存状态已更新");
    } else {
      console.warn("⚠️ 获取缓存状态失败:", cacheRes.message);
    }
  } catch (error) {
    console.error("❌ 更新模型状态失败:", error);
  }
}

async function startPreload() {
  try {
    console.log("🚀 用户点击启动预加载");
    
    // 检查当前状态
    if (modelStatus.is_preloading) {
      ElMessage.warning("预加载正在进行中，请稍候");
      return;
    }
    
    if (isPreloadBlocked.value) {
      ElMessage.error("预加载重试次数已达上限，请先重置");
      return;
    }

    console.log("📡 发送预加载启动请求...");
    const result = await modelAPI.startPreload();
    console.log("📊 API响应:", result);
    
    if (result.success) {
      ElMessage.success("模型预加载已启动");
      
      // 立即更新状态以获取最新的预加载状态
      console.log("🔄 立即更新状态检查预加载启动情况");
      await updateModelStatus();
      
      // 如果检测到正在预加载，启动高频更新
      if (modelStatus.is_preloading) {
        console.log("✅ 检测到预加载已启动，开始高频监控");
        startHighFrequencyUpdates();
      } else {
        console.log("⚠️ 未检测到预加载状态，延迟重试检查");
        setTimeout(async () => {
          await updateModelStatus();
          if (modelStatus.is_preloading) {
            startHighFrequencyUpdates();
          }
        }, 2000);
      }
      
    } else {
      console.warn("⚠️ 预加载启动失败:", result.message);
      ElMessage.error(result.message || "启动预加载失败");
    }
  } catch (error) {
    console.error("❌ 启动预加载异常:", error);
    ElMessage.error("启动预加载失败: " + (error.response?.data?.message || error.message));
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

    console.log("开始清空模型缓存");

    const result = await modelAPI.clearCache();
    if (result.success) {
      ElMessage.success("模型缓存已清空");

      // 立即更新本地状态
      modelStatus.loaded_models = 0;
      modelStatus.is_preloading = false;
      modelStatus.progress = 0;
      modelStatus.current_model = "";
      modelStatus.errors = [];

      cacheStatus.whisper_models = [];
      cacheStatus.align_models = [];
      cacheStatus.total_memory_mb = 0;

      console.log("本地状态已重置，开始更新服务器状态");

      // 立即从服务器更新状态
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

async function resetPreloadAttempts() {
  try {
    await ElMessageBox.confirm(
      "确定要重置预加载重试计数吗？这将允许重新尝试预加载模型。",
      "确认重置",
      {
        type: "warning",
      }
    );

    console.log("开始重置预加载重试计数");

    const response = await fetch('/api/models/preload/reset', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    const result = await response.json();
    
    if (result.success) {
      ElMessage.success("预加载重试计数已重置");
      
      // 立即更新本地状态
      modelStatus.failed_attempts = 0;
      modelStatus.errors = [];

      console.log("本地状态已重置，开始更新服务器状态");

      // 立即从服务器更新状态
      await updateModelStatus();
    } else {
      ElMessage.error(result.message || "重置失败");
    }
  } catch (error) {
    if (error !== "cancel") {
      console.error("重置预加载重试计数失败:", error);
      ElMessage.error(
        "重置失败: " + (error.response?.data?.message || error.message)
      );
    }
  }
}

// 高频率状态更新 - 用于预加载期间
function startHighFrequencyUpdates() {
  console.log("� 启动高频率状态更新");
  stopHighFrequencyUpdates(); // 先停止之前的更新
  
  let updateCount = 0;
  const maxUpdates = 90; // 最多更新90次（1.5分钟）
  
  highFrequencyTimer.value = setInterval(async () => {
    updateCount++;
    console.log(`⚡ 高频更新 #${updateCount}`);
    
    await updateModelStatus();
    
    // 检查是否完成
    if (!modelStatus.is_preloading && modelStatus.loaded_models > 0) {
      console.log("🎉 预加载完成，停止高频更新");
      stopHighFrequencyUpdates();
      ElMessage.success(`模型预加载完成！已加载 ${modelStatus.loaded_models} 个模型`);
      return;
    }
    
    // 达到最大次数停止
    if (updateCount >= maxUpdates) {
      console.log("⏰ 高频更新达到最大次数，切换到常规更新");
      stopHighFrequencyUpdates();
      startRegularUpdates();
    }
  }, 1000); // 每秒更新
}

function stopHighFrequencyUpdates() {
  if (highFrequencyTimer.value) {
    console.log("⏹️ 停止高频率状态更新");
    clearInterval(highFrequencyTimer.value);
    highFrequencyTimer.value = null;
  }
}

function startRegularUpdates() {
  console.log("🔄 启动常规状态更新");
  stopRegularUpdates(); // 先停止之前的更新
  
  const updateInterval = () => {
    if (modelStatus.is_preloading) return 3000; // 预加载时3秒
    if (modelStatus.loaded_models > 0) return 15000; // 已加载时15秒
    return 8000; // 其他情况8秒
  };

  const scheduleNext = () => {
    updateTimer.value = setTimeout(async () => {
      await updateModelStatus();
      scheduleNext(); // 递归调度
    }, updateInterval());
  };

  scheduleNext();
}

function stopRegularUpdates() {
  if (updateTimer.value) {
    clearTimeout(updateTimer.value);
    updateTimer.value = null;
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

function getStatusIndicatorText() {
  if (isPreloadBlocked.value) {
    return `重试已达上限 (${modelStatus.failed_attempts}/${modelStatus.max_retry_attempts})`;
  }
  if (modelStatus.is_preloading) {
    return "加载中";
  }
  if (modelStatus.errors.length > 0) {
    return "错误";
  }
  if (modelStatus.loaded_models > 0) {
    return "已就绪";
  }
  return "待机";
}

// 手动强制更新状态
async function forceUpdate() {
  console.log("手动触发状态更新");
  await updateModelStatus();
  ElMessage.info("状态已刷新");
}

// 调试函数：模拟预加载状态变化
function simulatePreloading() {
  console.log("模拟预加载开始");
  modelStatus.is_preloading = true;
  modelStatus.progress = 0;
  modelStatus.current_model = "模拟加载中...";

  // 模拟进度更新
  let progress = 0;
  const interval = setInterval(() => {
    progress += 10;
    modelStatus.progress = progress;

    if (progress >= 100) {
      clearInterval(interval);
      modelStatus.is_preloading = false;
      modelStatus.loaded_models = 3;
      modelStatus.current_model = "";
      console.log("模拟预加载完成");
    }
  }, 1000);
}

function startStatusUpdates() {
  console.log("🔄 启动初始状态更新");
  // 立即更新一次状态
  updateModelStatus().then(() => {
    console.log("✅ 初始状态更新完成，开始常规更新");
    startRegularUpdates();
  });
}

// 生命周期
onMounted(() => {
  console.log("🎬 ModelStatusButton 组件已挂载");
  
  // 添加响应式监听
  watch(() => modelStatus.is_preloading, (newVal, oldVal) => {
    if (newVal !== oldVal) {
      console.log(`🔄 预加载状态变化: ${oldVal} -> ${newVal}`);
      console.log(`🎨 按钮状态: ${statusType.value}, 文本: ${statusText.value}`);
    }
  });
  
  watch(() => modelStatus.progress, (newVal, oldVal) => {
    if (modelStatus.is_preloading && Math.abs(newVal - oldVal) > 5) {
      console.log(`📊 预加载进度: ${oldVal}% -> ${newVal}%`);
    }
  });
  
  watch(() => modelStatus.loaded_models, (newVal, oldVal) => {
    if (newVal !== oldVal) {
      console.log(`📦 已加载模型数量变化: ${oldVal} -> ${newVal}`);
    }
  });
  
  // 启动状态更新
  console.log("⚡ 启动初始状态检查");
  startStatusUpdates();
});

onUnmounted(() => {
  console.log("🔚 ModelStatusButton 组件卸载，清理定时器");
  stopRegularUpdates();
  stopHighFrequencyUpdates();
});
</script>

<style scoped>
.model-status-content {
  max-height: 60vh;
  overflow: hidden;
}

.status-section {
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
  background: #fafafa;
}

.status-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
  margin-bottom: 16px;
  justify-content: space-between;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
  margin-left: auto;
  margin-right: 16px;
}

.indicator-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  animation: blink 2s infinite;
}

.status-indicator.indicator-loading {
  background-color: rgba(243, 156, 18, 0.1);
  color: #f39c12;
}

.status-indicator.indicator-loading .indicator-dot {
  background-color: #f39c12;
  animation: pulse-dot 1.5s ease-in-out infinite;
}

.status-indicator.indicator-success {
  background-color: rgba(39, 174, 96, 0.1);
  color: #27ae60;
}

.status-indicator.indicator-success .indicator-dot {
  background-color: #27ae60;
  animation: none;
}

.status-indicator.indicator-error {
  background-color: rgba(231, 76, 60, 0.1);
  color: #e74c3c;
}

.status-indicator.indicator-error .indicator-dot {
  background-color: #e74c3c;
  animation: blink 1s infinite;
}

.status-indicator.indicator-idle {
  background-color: rgba(52, 152, 219, 0.1);
  color: #3498db;
}

.status-indicator.indicator-idle .indicator-dot {
  background-color: #3498db;
  animation: none;
}

@keyframes pulse-dot {
  0%,
  100% {
    transform: scale(1);
    opacity: 1;
  }
  50% {
    transform: scale(1.2);
    opacity: 0.7;
  }
}

@keyframes blink {
  0%,
  50% {
    opacity: 1;
  }
  51%,
  100% {
    opacity: 0.3;
  }
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
  /* 防止内容变化引起的布局跳动 */
  overflow: hidden;
}

.cache-row {
  display: flex;
  gap: 16px;
  /* 确保两列布局稳定 */
  align-items: flex-start;
}

.cache-card {
  flex: 1;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  padding: 12px;
  background: #fafafa;
  min-height: 120px;
  /* 防止内容变化导致的布局偏移 */
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.cache-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
  margin-bottom: 12px;
  font-size: 14px;
}

.model-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
  /* 防止内容变化时的抖动 */
  min-height: 40px;
  transition: none; /* 移除可能导致平移的过渡效果 */
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
  font-size: 13px;
}

.model-details {
  font-size: 11px;
  color: #909399;
}

.model-stats {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
}

.align-models {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.align-tag {
  margin: 0;
  font-size: 11px;
}

.retry-blocked-section {
  margin-top: 16px;
}

.retry-blocked-section .retry-tip {
  margin-top: 8px;
  font-size: 12px;
  color: #909399;
  margin-bottom: 0;
}

.error-section,
.retry-blocked-section {
  margin-top: 16px;
}

.error-list {
  margin: 8px 0 0 0;
  padding-left: 16px;
}

.error-list li {
  margin-bottom: 4px;
  font-size: 12px;
}

.empty-state {
  text-align: center;
  color: #909399;
  font-size: 12px;
  padding: 20px 0;
}

.model-status-btn {
  white-space: nowrap;
  min-width: 140px;
  font-weight: 500;
  transition: all 0.3s ease;
  border-radius: 6px;
}

.model-status-btn.status-loading {
  background-color: #f39c12;
  border-color: #f39c12;
  color: white;
  animation: pulse 1.5s ease-in-out infinite;
}

.model-status-btn.status-success {
  background-color: #27ae60;
  border-color: #27ae60;
  color: white;
  box-shadow: 0 2px 8px rgba(39, 174, 96, 0.3);
}

.model-status-btn.status-error {
  background-color: #e74c3c;
  border-color: #e74c3c;
  color: white;
  box-shadow: 0 2px 8px rgba(231, 76, 60, 0.3);
}

.model-status-btn.status-idle {
  background-color: #3498db;
  border-color: #3498db;
  color: white;
}

.model-status-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  /* 移除可能导致相邻元素偏移的过渡 */
}

@keyframes pulse {
  0% {
    box-shadow: 0 0 0 0 rgba(243, 156, 18, 0.4);
  }
  70% {
    box-shadow: 0 0 0 8px rgba(243, 156, 18, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(243, 156, 18, 0);
  }
}
</style>
