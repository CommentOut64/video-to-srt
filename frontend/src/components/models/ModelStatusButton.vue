<template>
  <el-button
    :type="statusType"
    size="small"
    @click="openDialog"
    :loading="isLoadingStatus"
    class="model-status-btn"
    :class="{
      'status-loading': isLoadingStatus,
      'status-success':
        modelStatus.loaded_models > 0 && !modelStatus.is_preloading,
      'status-error': modelStatus.errors.length > 0,
    }"
  >
    <el-icon v-if="!isLoadingStatus">
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
    :modal="true"
    :append-to-body="true"
    :lock-scroll="false"
    center
    :modal-class="'model-status-modal'"
    @close="closeDialog"
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
import {
  ref,
  reactive,
  computed,
  onMounted,
  onUnmounted,
  watch,
  nextTick,
} from "vue";
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

// 简化的模型状态数据
const modelStatus = reactive({
  is_preloading: false,
  progress: 0,
  current_model: "",
  total_models: 0,
  loaded_models: 0,
  errors: [],
  failed_attempts: 0,
  max_retry_attempts: 3,
  cache_version: 0  // 缓存版本号，用于检测状态变更
});

const cacheStatus = reactive({
  whisper_models: [],
  align_models: [],
  total_memory_mb: 0,
  max_cache_size: 0,
  memory_info: {},
  cache_version: 0  // 缓存版本号
});

// 单一自适应定时器
let pollTimer = null;
let lastCacheVersion = 0;  // 用于检测缓存状态变更

// 计算属性
const isPreloadBlocked = computed(() => {
  return modelStatus.failed_attempts >= modelStatus.max_retry_attempts;
});

// 统一的加载中状态判断
const isLoadingStatus = computed(() => {
  return (
    modelStatus.is_preloading ||
    (modelStatus.loaded_models === 0 &&
      !modelStatus.is_preloading &&
      modelStatus.errors.length === 0)
  );
});

const statusType = computed(() => {
  if (modelStatus.errors.length > 0) return "danger";
  if (isLoadingStatus.value) return "warning";
  if (modelStatus.loaded_models > 0) return "success";
  return "warning";
});

const statusText = computed(() => {
  if (isPreloadBlocked.value) {
    return `重试已达上限 (${modelStatus.failed_attempts}/${modelStatus.max_retry_attempts})`;
  }
  if (isLoadingStatus.value) {
    if (modelStatus.is_preloading && modelStatus.progress > 0) {
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
  return "加载中...";
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
  if (isLoadingStatus.value) return "Loading";
  if (modelStatus.loaded_models > 0) return "CircleCheckFilled";
  return "Loading";
});

// 智能轮询机制 - 只在状态变化时轮询
function startSmartPolling() {
  console.log("启动智能轮询（仅在状态变化时）");

  const poll = async () => {
    try {
      const wasPreloading = modelStatus.is_preloading;
      await updateModelStatus();
      const isNowPreloading = modelStatus.is_preloading;

      // 只在正在预加载时继续轮询
      if (isNowPreloading) {
        pollTimer = setTimeout(poll, 1500); // 预加载中：高频轮询
      } else {
        // 预加载完成，停止轮询
        if (wasPreloading) {
          console.log("预加载已完成，停止轮询");
        }
        stopSmartPolling();
      }

    } catch (error) {
      console.error("❌ 轮询更新失败:", error);
      // 失败后稍后重试一次
      pollTimer = setTimeout(poll, 5000);
    }
  };

  // 立即执行一次
  poll();
}

function stopSmartPolling() {
  if (pollTimer) {
    console.log("⏹️ 停止智能轮询");
    clearTimeout(pollTimer);
    pollTimer = null;
  }
}
  
// 对话框处理函数，防止布局偏移
function openDialog() {
  // 记录当前滚动条宽度
  const scrollbarWidth = window.innerWidth - document.documentElement.clientWidth;
  
  // 记录当前body的样式，以便恢复
  const currentBodyStyle = {
    paddingRight: document.body.style.paddingRight,
    overflow: document.body.style.overflow,
    width: document.body.style.width
  };
  
  // 设置body的样式来补偿可能消失的滚动条，但实际不需要因为我们设置了overflow-y: scroll
  document.body.style.paddingRight = '0px';
  document.body.style.overflow = 'hidden auto'; // 只隐藏水平滚动，保持垂直滚动
  document.body.style.width = '100vw';
  
  // 强制移除Element Plus可能添加的类
  document.body.classList.remove('el-popup-parent--hidden');
  
  showDialog.value = true;
  
  // 监听Element Plus添加类的行为并立即移除
  const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      if (mutation.type === 'attributes' && mutation.attributeName === 'class') {
        if (document.body.classList.contains('el-popup-parent--hidden')) {
          document.body.classList.remove('el-popup-parent--hidden');
        }
      }
      if (mutation.type === 'attributes' && mutation.attributeName === 'style') {
        // 防止Element Plus修改padding-right
        if (document.body.style.paddingRight && document.body.style.paddingRight !== '0px') {
          document.body.style.paddingRight = '0px';
        }
      }
    });
  });
  
  observer.observe(document.body, { 
    attributes: true, 
    attributeFilter: ['class', 'style'] 
  });
  
  // 存储observer以便后续清理
  document.body._modalObserver = observer;
}

function closeDialog() {
  // 清理observer
  if (document.body._modalObserver) {
    document.body._modalObserver.disconnect();
    delete document.body._modalObserver;
  }
  
  // 恢复body样式
  document.body.style.paddingRight = '';
  document.body.style.overflow = '';
  document.body.style.width = '';
  
  // 确保移除Element Plus的类
  document.body.classList.remove('el-popup-parent--hidden');
  
  showDialog.value = false;
}

// 监听对话框关闭
watch(showDialog, (newVal) => {
  if (!newVal) {
    // 延迟恢复，确保对话框完全关闭
    nextTick(() => {
      closeDialog();
    });
  }
});

// 简化的状态更新方法 - 单一数据源
async function updateModelStatus() {
  try {
    console.log("更新模型状态");

    const [preloadRes, cacheRes] = await Promise.all([
      modelAPI.getPreloadStatus(),
      modelAPI.getCacheStatus(),
    ]);

    let statusChanged = false;
    
    if (preloadRes.success) {
      const newStatus = preloadRes.data;
      
      // 检测关键状态变化
      const wasPreloading = modelStatus.is_preloading;
      const isNowPreloading = newStatus.is_preloading;
      const progressChanged = Math.abs(newStatus.progress - modelStatus.progress) > 1;
      
      // 更新状态
      Object.assign(modelStatus, newStatus);
      
      // 状态变化日志
      if (wasPreloading !== isNowPreloading) {
        console.log(isNowPreloading ? " 预加载开始" : "预加载完成");
        statusChanged = true;
      } else if (isNowPreloading && progressChanged) {
        console.log(`📊 预加载进度: ${Math.round(newStatus.progress)}%`);
      }
    } else {
      console.warn("⚠️ 获取预加载状态失败:", preloadRes.message);
    }

    if (cacheRes.success) {
      // 检测缓存版本变化
      if (cacheRes.data.cache_version !== lastCacheVersion) {
        console.log("缓存状态已更新");
        lastCacheVersion = cacheRes.data.cache_version;
        statusChanged = true;
      }
      Object.assign(cacheStatus, cacheRes.data);
    } else {
      console.warn("⚠️ 获取缓存状态失败:", cacheRes.message);
    }
    
  } catch (error) {
    console.error("❌ 更新模型状态失败:", error);
  }
}

async function startPreload() {
  try {
    console.log(" 用户点击启动预加载");

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

      // 立即更新状态
      console.log("立即更新状态检查预加载启动情况");
      await updateModelStatus();

      // 如果检测到正在预加载，启动智能轮询
      if (modelStatus.is_preloading) {
        console.log("检测到预加载已启动，开始智能轮询");
        startSmartPolling();
      } else {
        console.log("⚠️ 未检测到预加载状态，延迟重试检查");
        setTimeout(async () => {
          await updateModelStatus();
          if (modelStatus.is_preloading) {
            startSmartPolling();
          }
        }, 2000);
      }
    } else {
      console.warn("⚠️ 预加载启动失败:", result.message);
      ElMessage.error(result.message || "启动预加载失败");
    }
  } catch (error) {
    console.error("❌ 启动预加载异常:", error);
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

    const response = await fetch("/api/models/preload/reset", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
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

// 手动强制更新状态
async function forceUpdate() {
  console.log("手动触发状态更新");
  await updateModelStatus();
  ElMessage.info("状态已刷新");
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
  if (isLoadingStatus.value) {
    return "加载中";
  }
  if (modelStatus.errors.length > 0) {
    return "错误";
  }
  if (modelStatus.loaded_models > 0) {
    return "已就绪";
  }
  return "加载中";
}

// 组件生命周期管理
onMounted(async () => {
  console.log("🎬 ModelStatusButton 组件已挂载 - 智能轮询版本");

  // 监听预加载状态变化
  watch(
    () => modelStatus.is_preloading,
    (newVal, oldVal) => {
      if (newVal !== oldVal) {
        console.log(`预加载状态变化: ${oldVal} -> ${newVal}`);
        if (!newVal && oldVal) {
          // 从预加载中变为非预加载，说明完成了
          ElMessage.success(`模型预加载完成！已加载 ${modelStatus.loaded_models} 个模型`);
        }
      }
    }
  );

  watch(
    () => modelStatus.loaded_models,
    (newVal, oldVal) => {
      if (newVal !== oldVal && newVal > oldVal) {
        console.log(`📊 已加载模型数量更新: ${oldVal} -> ${newVal}`);
      }
    }
  );

  // 初始状态检查：只检查一次，如果正在预加载才启动轮询
  console.log(" 执行初始状态检查");
  await updateModelStatus();

  if (modelStatus.is_preloading) {
    console.log("检测到正在预加载，启动智能轮询");
    startSmartPolling();
  } else {
    console.log("模型状态稳定，无需启动轮询");
  }
});

onUnmounted(() => {
  console.log("🔚 ModelStatusButton 组件卸载 - 清理资源");

  // 清理轮询定时器
  stopSmartPolling();

  // 清理对话框observer
  if (document.body._modalObserver) {
    document.body._modalObserver.disconnect();
    delete document.body._modalObserver;
  }

  // 确保清理body样式
  document.body.style.paddingRight = '';
  document.body.style.overflow = '';
  document.body.style.width = '';
  document.body.classList.remove('el-popup-parent--hidden');
});
</script>

<style scoped>
.model-status-content {
  max-height: 60vh;
  overflow: hidden;
  /* 防止对话框内容变化引起布局偏移 */
  contain: layout;
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
  /* 防止按钮状态变化引起布局偏移 */
  will-change: auto;
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

.model-status-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
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

<!-- 全局样式防止对话框布局偏移 -->
<style>
/* 防止滚动条变化引起的水平移动 */
html {
  overflow-y: scroll !important;
  scrollbar-gutter: stable;
}

body {
  /* 确保body始终保持相同的宽度 */
  overflow-x: hidden;
  width: 100vw;
  position: relative;
  /* 防止Element Plus添加padding-right */
  box-sizing: border-box;
}

/* 强制防止Element Plus修改body样式 */
body.el-popup-parent--hidden {
  padding-right: 0 !important;
  overflow: visible !important;
  width: 100vw !important;
}

.el-overlay {
  /* 确保遮罩层不影响主界面布局 */
  position: fixed !important;
  z-index: 2000;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  /* 防止创建新的堆叠上下文影响布局 */
  contain: strict;
}

.el-dialog {
  /* 确保对话框使用固定定位 */
  position: fixed !important;
  transform: translateX(-50%) translateY(-50%);
  left: 50vw;
  top: 50vh;
  margin: 0 !important;
  max-width: calc(100vw - 32px);
  /* 防止对话框影响主界面 */
  contain: layout style;
}

.model-status-modal {
  /* 自定义遮罩层样式 */
  background-color: rgba(0, 0, 0, 0.5);
}

/* 防止Element Plus自动添加的滚动锁定样式 */
.el-popup-parent--hidden {
  padding-right: 0 !important;
  overflow: auto !important;
}

/* 确保所有可能的容器都不会因为对话框而移动 */
#app, .app-container, .main-content {
  transition: none !important;
  transform: none !important;
  margin: 0 !important;
  padding-right: 0 !important;
}
</style>
