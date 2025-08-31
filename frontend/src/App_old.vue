<template>
  <el-container class="app-container">
    <!-- 顶部标题 -->
    <el-header class="header">
      <el-row justify="center">
        <el-col :span="24">
          <h1 class="title">
            <el-icon><VideoPlay /></el-icon>
            Video To SRT 转录工具
          </h1>
          <!-- <p class="subtitle">基于 WhisperX 的高性能视频字幕生成工具</p> -->
        </el-col>
      </el-row>
    </el-header>

    <!-- 主要内容区域 -->
    <el-main class="main-content">
      <el-row :gutter="20" justify="center">
        <el-col :xs="24" :sm="20" :md="16" :lg="14" :xl="12">
          
          <!-- 1. 文件选择区域 -->
          <el-card class="upload-card" shadow="hover">
            <template #header>
              <div class="card-header">
                <el-icon><FolderOpened /></el-icon>
                <span>1. 选择媒体文件</span>
                <div style="margin-left: auto; display: flex; gap: 8px;">
                  <el-button 
                    type="info" 
                    size="small"
                    @click="showHardwareDialog = true"
                    plain
                  >
                    <el-icon><Monitor /></el-icon>
                    硬件信息
                  </el-button>
                  <el-button 
                    :type="modelStatusType"
                    size="small"
                    @click="showModelDialog = true"
                    :plain="modelStatusType !== 'danger'"
                    :loading="modelStatus.is_preloading"
                  >
                    <el-icon>
                      <component :is="modelStatusIcon" />
                    </el-icon>
                    {{ modelStatusText }}
                  </el-button>
                  <el-button 
                    type="success" 
                    size="small"
                    @click="toggleUploadMode"
                    :disabled="creating || uploading"
                  >
                    <el-icon><Upload /></el-icon>
                    {{ showUpload ? '切换到本地模式' : '切换到上传模式' }}
                  </el-button>
                  <el-button 
                    type="primary" 
                    size="small"
                    @click="loadFiles"
                    :loading="loadingFiles"
                    v-if="!showUpload"
                  >
                    <el-icon><Refresh /></el-icon>
                    刷新
                  </el-button>
                </div>
              </div>
            </template>
            
            <div class="file-selection-area">
              <!-- 上传模式 -->
              <div v-if="showUpload" class="upload-mode">
                <el-upload
                  class="upload-area"
                  drag
                  :auto-upload="false"
                  :on-change="handleUpload"
                  :show-file-list="false"
                  :disabled="uploading"
                  accept=".mp4,.avi,.mkv,.mov,.wmv,.flv,.webm,.m4v,.mp3,.wav,.flac,.aac,.ogg,.m4a,.wma"
                >
                  <div class="upload-content">
                    <el-icon class="upload-icon"><UploadFilled /></el-icon>
                    <div class="upload-text" v-if="!uploading">
                      拖拽文件到此处，或<em>点击选择</em>
                    </div>
                    <div class="upload-text" v-else>
                      正在上传... {{ uploadProgress }}%
                    </div>
                    <div class="upload-hint">
                      支持格式：MP4, AVI, MKV, MOV, WMV, MP3, WAV, FLAC 等
                    </div>
                  </div>
                </el-upload>
                
                <!-- 上传进度条 -->
                <el-progress
                  v-if="uploading"
                  :percentage="uploadProgress"
                  :stroke-width="8"
                  status="active"
                  style="margin-top: 16px;"
                />
              </div>
              
              <!-- 浏览模式 -->
              <div v-else class="browse-mode">
                <!-- 目录提示 -->
                <el-alert
                  title="请将视频/音频文件放入 input 目录中"
                  type="info"
                  :closable="false"
                  show-icon
                >
                  <template #default>
                    <p>支持格式：MP4, AVI, MKV, MOV, WMV, MP3, WAV, FLAC 等</p>
                    <p>目录路径：<code>{{ inputDirPath }}</code></p>
                  </template>
                </el-alert>

              <!-- 文件列表 -->
              <div v-if="availableFiles.length > 0" class="file-list">
                <el-table 
                  :data="availableFiles" 
                  style="width: 100%"
                  @row-click="selectFile"
                  :highlight-current-row="true"
                  :current-row-key="selectedFile?.name"
                  row-key="name"
                >
                  <el-table-column type="selection" width="40" />
                  <el-table-column prop="name" label="文件名" min-width="200">
                    <template #default="scope">
                      <div class="file-name">
                        <el-icon><VideoPlay v-if="isVideoFile(scope.row.name)" /><Headphone v-else /></el-icon>
                        {{ scope.row.name }}
                      </div>
                    </template>
                  </el-table-column>
                  <el-table-column prop="size" label="大小" width="100">
                    <template #default="scope">
                      {{ formatFileSize(scope.row.size) }}
                    </template>
                  </el-table-column>
                  <el-table-column prop="modified" label="修改时间" width="160" />
                  <el-table-column label="操作" width="120">
                    <template #default="scope">
                      <el-button
                        type="primary"
                        size="small"
                        @click.stop="selectFile(scope.row)"
                        :disabled="creating"
                      >
                        选择
                      </el-button>
                    </template>
                  </el-table-column>
                </el-table>
              </div>

              <!-- 无文件提示 -->
              <el-empty v-else-if="!loadingFiles" description="input 目录中没有找到支持的媒体文件">
                <el-button type="primary" @click="loadFiles">刷新文件列表</el-button>
              </el-empty>

              <!-- 加载中 -->
              <div v-if="loadingFiles" class="loading-files">
                <el-icon class="is-loading"><Loading /></el-icon>
                <span>正在加载文件列表...</span>
              </div>
              </div>

              <!-- 选中的文件 -->
              <div v-if="selectedFile && !showUpload" class="selected-file">
                <el-tag type="success" size="large" closable @close="clearSelection">
                  <el-icon><Document /></el-icon>
                  已选择：{{ selectedFile.name }} 
                  <span v-if="selectedFile.size">({{ formatFileSize(selectedFile.size) }})</span>
                  <span v-if="selectedFile.originalName && selectedFile.originalName !== selectedFile.name">
                    <br><small>原文件名: {{ selectedFile.originalName }}</small>
                  </span>
                </el-tag>
                
                <el-button 
                  v-if="!jobId"
                  type="primary" 
                  size="large"
                  :loading="creating"
                  @click="createJob"
                  style="margin-top: 12px;"
                >
                  <el-icon v-if="!creating"><FolderAdd /></el-icon>
                  {{ creating ? "创建中..." : "创建转录任务" }}
                </el-button>
              </div>
            </div>
          </el-card>

          <!-- 2. 参数设置区域 -->
          <el-card v-if="jobId" class="settings-card" shadow="hover">
            <template #header>
              <div class="card-header">
                <el-icon><Setting /></el-icon>
                <span>2. 设置参数并开始转录</span>
              </div>
            </template>
            
            <el-form 
              :model="settings" 
              label-width="100px" 
              label-position="left"
              @submit.prevent="startJob"
            >
              <el-row :gutter="20">
                <el-col :span="12">
                  <el-form-item label="模型选择">
                    <el-select v-model="settings.model" placeholder="选择模型">
                      <el-option label="tiny (最快)" value="tiny" />
                      <el-option label="base (较快)" value="base" />
                      <el-option label="small (平衡)" value="small" />
                      <el-option label="medium (推荐)" value="medium" />
                      <el-option label="large-v2 (高精度)" value="large-v2" />
                      <el-option label="large-v3 (最高精度)" value="large-v3" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="计算类型">
                    <el-select v-model="settings.compute_type">
                      <el-option label="float16 (推荐)" value="float16" />
                      <el-option label="float32 (高精度)" value="float32" />
                      <el-option label="int8 (省内存)" value="int8" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="运行设备">
                    <el-select v-model="settings.device">
                      <el-option label="CUDA GPU" value="cuda" />
                      <el-option label="CPU" value="cpu" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="批大小">
                    <el-input-number 
                      v-model="settings.batch_size" 
                      :min="1" 
                      :max="32"
                      controls-position="right"
                    />
                  </el-form-item>
                </el-col>
                <el-col :span="24">
                  <el-form-item>
                    <el-checkbox v-model="settings.word_timestamps">
                      启用词级时间戳（更精确但较慢）
                    </el-checkbox>
                  </el-form-item>
                </el-col>
              </el-row>

              <!-- 操作按钮 -->
              <div class="action-buttons">
                <el-button 
                  type="primary" 
                  size="large"
                  :loading="starting"
                  :disabled="processing || starting"
                  @click="startJob"
                >
                  <el-icon v-if="!starting"><VideoPlay /></el-icon>
                  {{ starting ? "启动中..." : "开始转录" }}
                </el-button>
                
                <el-button 
                  type="danger"
                  size="large"
                  :loading="canceling"
                  :disabled="!processing || canceling"
                  @click="cancelJob"
                >
                  <el-icon v-if="!canceling"><VideoPause /></el-icon>
                  {{ canceling ? "取消中..." : "取消任务" }}
                </el-button>
                
                <el-button 
                  type="warning"
                  size="large"
                  :disabled="processing || !canRestart"
                  @click="restartJob"
                >
                  <el-icon><RefreshRight /></el-icon>
                  重新转录
                </el-button>
                
                <el-button 
                  type="success"
                  size="large"
                  @click="resetSelection"
                >
                  <el-icon><FolderOpened /></el-icon>
                  重新选择文件
                </el-button>
              </div>
            </el-form>
          </el-card>

          <!-- 3. 进度显示区域 -->
          <el-card v-if="jobId" class="progress-card" shadow="hover">
            <template #header>
              <div class="card-header">
                <el-icon><Timer /></el-icon>
                <span>3. 转录进度</span>
              </div>
            </template>
            
            <div class="progress-content">
              <!-- 进度条 -->
              <el-progress
                :percentage="progress"
                :stroke-width="12"
                :status="getProgressStatus()"
              />
              
              <!-- 状态信息 -->
              <div class="status-info">
                <el-tag :type="getStatusType()" size="large">
                  <el-icon><Clock /></el-icon>
                  {{ phaseLabel }} ({{ progress }}%)
                </el-tag>
                <p class="status-text">{{ statusText }}</p>
                <p v-if="language" class="language-info">
                  <el-icon><Flag /></el-icon>
                  检测语言: <strong>{{ language }}</strong>
                </p>
              </div>

              <!-- 错误信息 -->
              <el-alert
                v-if="status === 'failed'"
                :title="'任务失败：' + lastError"
                type="error"
                show-icon
                :closable="false"
              />

              <!-- 下载按钮 -->
              <div v-if="status === 'finished' && downloadUrl" class="download-section">
                <el-button 
                  type="success" 
                  size="large"
                  @click="downloadFile"
                >
                  <el-icon><Download /></el-icon>
                  下载 SRT 字幕文件
                </el-button>
                
                <el-button 
                  type="warning" 
                  size="large"
                  @click="copyResultToSource"
                  style="margin-left: 12px;"
                >
                  <el-icon><FolderAdd /></el-icon>
                  复制到源文件目录
                </el-button>
              </div>
            </div>
          </el-card>

        </el-col>
      </el-row>
    </el-main>
    
    <!-- 硬件信息对话框 -->
    <HardwareDialog v-model="showHardwareDialog" />
    
    <!-- 模型状态对话框 -->
    <el-dialog
      v-model="showModelDialog"
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
                  {{ modelStatus.is_preloading ? '预加载中...' : '开始预加载' }}
                </el-button>
                <el-button
                  type="warning"
                  size="small"
                  @click="clearModelCache"
                >
                  清空缓存
                </el-button>
              </div>
            </div>
          </template>
          
          <!-- 预加载进度 -->
          <div v-if="modelStatus.is_preloading" class="progress-section">
            <div class="progress-info">
              <span>正在加载: {{ modelStatus.current_model || '准备中...' }}</span>
              <span>{{ modelStatus.loaded_models }}/{{ modelStatus.total_models }}</span>
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
                <li v-for="error in modelStatus.errors" :key="error">{{ error }}</li>
              </ul>
            </el-alert>
          </div>
          
          <!-- 成功状态 -->
          <div v-if="!modelStatus.is_preloading && modelStatus.loaded_models > 0 && modelStatus.errors.length === 0" class="success-section">
            <el-alert
              title="模型预加载完成"
              type="success"
              :closable="false"
              show-icon
            >
              已成功加载 {{ modelStatus.loaded_models }}/{{ modelStatus.total_models }} 个模型
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
              <div v-if="cacheStatus.whisper_models && cacheStatus.whisper_models.length > 0">
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
                    <el-tag type="info" size="small">{{ model.memory_mb }}MB</el-tag>
                    <div class="load-time">加载: {{ model.load_time?.toFixed(2) }}s</div>
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
              <div v-if="cacheStatus.align_models && cacheStatus.align_models.length > 0">
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
              <el-empty v-else description="暂无缓存的对齐模型" :image-size="60" />
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
                  :percentage="Math.round(cacheStatus.memory_info?.system_memory_percent || 0)"
                  :color="getMemoryColor(cacheStatus.memory_info?.system_memory_percent || 0)"
                  :stroke-width="12"
                />
                <div class="memory-text">
                  {{ (cacheStatus.memory_info?.system_memory_used || 0).toFixed(1) }}GB / 
                  {{ (cacheStatus.memory_info?.system_memory_total || 0).toFixed(1) }}GB
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
                  {{ (cacheStatus.memory_info?.gpu_memory_allocated || 0).toFixed(1) }}GB / 
                  {{ (cacheStatus.memory_info?.gpu_memory_total || 0).toFixed(1) }}GB
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
  </el-container>
</template>

<script setup>
import { ref, reactive, onMounted, computed, onUnmounted } from "vue";
import axios from "axios";
import { ElMessage, ElMessageBox } from 'element-plus';
import HardwareDialog from './components/hardware/HardwareDialog.vue';

// 文件选择相关
const availableFiles = ref([]);
const selectedFile = ref(null);
const loadingFiles = ref(false);
const creating = ref(false);
const inputDirPath = ref('input/');
const uploading = ref(false);
const uploadProgress = ref(0);
const showUpload = ref(false); // 默认使用本地input模式

// 硬件信息对话框
const showHardwareDialog = ref(false);

// 模型状态相关
const showModelDialog = ref(false);
const modelStatus = reactive({
  is_preloading: false,
  progress: 0,
  current_model: '',
  total_models: 0,
  loaded_models: 0,
  errors: []
});
const cacheStatus = reactive({
  whisper_models: [],
  align_models: [],
  total_memory_mb: 0,
  max_cache_size: 0,
  memory_info: {}
});
const modelStatusUpdateTimer = ref(null);

// 任务相关 
const jobId = ref("");
const status = ref("");
const progress = ref(0);
const statusText = ref("请先选择文件");
const downloadUrl = ref("");
const processing = ref(false);
const starting = ref(false);
const canceling = ref(false);
const lastError = ref("");
const phase = ref("");
const language = ref("");
const canRestart = ref(false);
const pollTimer = ref(null);

const settings = reactive({
  model: "medium",
  compute_type: "float16",
  device: "cuda",
  batch_size: 16,
  word_timestamps: false,
});

const phaseMap = {
  extract: "提取音频",
  split: "分段处理",
  transcribe: "语音转录",
  srt: "生成字幕",
  pending: "等待处理",
  "": "等待处理",
};

const phaseLabel = computed(() => phaseMap[phase.value] || phase.value || "等待处理");

// 模型状态计算属性
const modelStatusType = computed(() => {
  if (modelStatus.errors.length > 0) return 'danger';
  if (modelStatus.is_preloading) return 'warning';
  if (modelStatus.loaded_models > 0) return 'success';
  return 'info';
});

const modelStatusText = computed(() => {
  if (modelStatus.is_preloading) {
    return `加载中 ${modelStatus.loaded_models}/${modelStatus.total_models}`;
  }
  if (modelStatus.errors.length > 0) {
    return '模型错误';
  }
  if (modelStatus.loaded_models > 0) {
    return `已就绪 ${modelStatus.loaded_models}个`;
  }
  return '模型状态';
});

const modelStatusIcon = computed(() => {
  if (modelStatus.errors.length > 0) return 'Warning';
  if (modelStatus.is_preloading) return 'Loading';
  if (modelStatus.loaded_models > 0) return 'CircleCheckFilled';
  return 'Cpu';
});

// 获取进度条状态
function getProgressStatus() {
  if (status.value === 'finished') return 'success';
  if (status.value === 'failed') return 'exception';
  return 'active';
}

// 获取状态标签类型
function getStatusType() {
  switch (status.value) {
    case 'finished': return 'success';
    case 'failed': return 'danger';
    case 'canceled': return 'warning';
    case 'processing': return 'primary';
    default: return 'info';
  }
}

// 检查是否为视频文件
function isVideoFile(filename) {
  const videoExtensions = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'];
  const ext = filename.toLowerCase().substring(filename.lastIndexOf('.'));
  return videoExtensions.includes(ext);
}

// 文件上传处理
async function handleUpload(uploadFile) {
  if (!uploadFile) {
    ElMessage.warning('请选择文件');
    return;
  }
  
  // 检查文件类型
  const videoExtensions = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'];
  const audioExtensions = ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.wma'];
  const ext = uploadFile.name.toLowerCase().substring(uploadFile.name.lastIndexOf('.'));
  
  if (![...videoExtensions, ...audioExtensions].includes(ext)) {
    ElMessage.error('不支持的文件格式，请上传视频或音频文件');
    return;
  }
  
  uploading.value = true;
  uploadProgress.value = 0;
  
  try {
    const formData = new FormData();
    formData.append('file', uploadFile.raw);
    
    const { data } = await axios.post('/api/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      },
      onUploadProgress: (progressEvent) => {
        uploadProgress.value = Math.round(
          (progressEvent.loaded / progressEvent.total) * 100
        );
      }
    });
    
    jobId.value = data.job_id;
    selectedFile.value = {
      name: data.filename,
      originalName: data.original_name,
      size: uploadFile.size
    };
    status.value = "ready";
    statusText.value = "文件已上传，可开始转录";
    canRestart.value = false;
    showUpload.value = false;
    
    ElMessage.success('文件上传成功！转录任务已创建。');
    
    // 刷新文件列表
    loadFiles();
  } catch (error) {
    console.error('文件上传失败:', error);
    ElMessage.error('文件上传失败：' + (error.response?.data?.detail || error.message));
  } finally {
    uploading.value = false;
    uploadProgress.value = 0;
  }
}

// 切换上传模式
function toggleUploadMode() {
  showUpload.value = !showUpload.value;
  if (showUpload.value) {
    // 清除已选择的文件
    selectedFile.value = null;
  }
}

// 加载可用文件列表
async function loadFiles() {
  loadingFiles.value = true;
  try {
    const { data } = await axios.get('/api/files');
    availableFiles.value = data.files || [];
    if (availableFiles.value.length === 0) {
      ElMessage.info('input 目录中没有找到支持的媒体文件');
    }
  } catch (error) {
    console.error('获取文件列表失败:', error);
    ElMessage.error('获取文件列表失败：' + (error.response?.data?.detail || error.message));
  } finally {
    loadingFiles.value = false;
  }
}

// 模型状态相关方法
async function updateModelStatus() {
  try {
    // 并行获取预加载状态和缓存状态
    const [preloadRes, cacheRes] = await Promise.all([
      axios.get('/api/models/preload/status'),
      axios.get('/api/models/cache/status')
    ]);
    
    if (preloadRes.data.success) {
      Object.assign(modelStatus, preloadRes.data.data);
    }
    
    if (cacheRes.data.success) {
      Object.assign(cacheStatus, cacheRes.data.data);
    }
  } catch (error) {
    console.error('更新模型状态失败:', error);
    // 静默失败，不显示错误消息以免干扰用户
  }
}

async function startPreload() {
  try {
    const { data } = await axios.post('/api/models/preload/start');
    if (data.success) {
      ElMessage.success('模型预加载已启动');
      // 立即更新状态
      await updateModelStatus();
    } else {
      ElMessage.error(data.message || '启动预加载失败');
    }
  } catch (error) {
    console.error('启动预加载失败:', error);
    ElMessage.error('启动预加载失败: ' + (error.response?.data?.message || error.message));
  }
}

async function clearModelCache() {
  try {
    await ElMessageBox.confirm('确定要清空所有模型缓存吗？这将释放内存但需要重新加载模型。', '确认操作', {
      type: 'warning'
    });
    
    const { data } = await axios.post('/api/models/cache/clear');
    if (data.success) {
      ElMessage.success('模型缓存已清空');
      await updateModelStatus();
    } else {
      ElMessage.error(data.message || '清空缓存失败');
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('清空缓存失败:', error);
      ElMessage.error('清空缓存失败: ' + (error.response?.data?.message || error.message));
    }
  }
}

function startModelStatusUpdates() {
  // 立即更新一次
  updateModelStatus();
  
  // 设置定时更新
  modelStatusUpdateTimer.value = setInterval(() => {
    updateModelStatus();
  }, 5000); // 每5秒更新一次
}

function getMemoryColor(percent) {
  if (percent < 50) return '#67c23a';
  if (percent < 75) return '#e6a23c';
  return '#f56c6c';
}

function getGpuMemoryPercent() {
  const total = cacheStatus.memory_info?.gpu_memory_total || 0;
  const allocated = cacheStatus.memory_info?.gpu_memory_allocated || 0;
  return total > 0 ? (allocated / total) * 100 : 0;
}

// 选择文件
function selectFile(file) {
  selectedFile.value = file;
  ElMessage.success(`已选择文件：${file.name}`);
}

// 清除选择
function clearSelection() {
  selectedFile.value = null;
}

// 创建转录任务
async function createJob() {
  if (!selectedFile.value) {
    ElMessage.warning('请先选择文件');
    return;
  }
  
  creating.value = true;
  try {
    const fd = new FormData();
    fd.append('filename', selectedFile.value.name);
    
    const { data } = await axios.post('/api/create-job', fd);
    jobId.value = data.job_id;
    status.value = "ready";
    statusText.value = "文件已准备就绪，可开始转录";
    canRestart.value = false;
    
    ElMessage.success('转录任务创建成功！');
  } catch (error) {
    console.error('创建任务失败:', error);
    ElMessage.error('创建任务失败：' + (error.response?.data?.detail || error.message));
  } finally {
    creating.value = false;
  }
}

// 重置选择
function resetSelection() {
  ElMessageBox.confirm('确定要重新选择文件吗？这将清除当前的转录进度。', '确认操作', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  }).then(() => {
    // 重置所有状态
    selectedFile.value = null;
    jobId.value = "";
    status.value = "";
    progress.value = 0;
    statusText.value = "请先选择文件";
    downloadUrl.value = "";
    processing.value = false;
    canRestart.value = false;
    lastError.value = "";
    phase.value = "";
    language.value = "";
    
    // 清除轮询定时器
    if (pollTimer.value) {
      clearTimeout(pollTimer.value);
      pollTimer.value = null;
    }
    
    // 刷新文件列表
    loadFiles();
    ElMessage.success('已重置，可以重新选择文件');
  }).catch(() => {
    // 用户取消操作
  });
}

// 格式化文件大小
function formatFileSize(bytes) {
  if (bytes === 0) return "0 Bytes";
  const k = 1024;
  const sizes = ["Bytes", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
}

async function startJob() {
  if (!jobId.value) {
    ElMessage.warning('请先选择文件并创建任务');
    return;
  }
  
  starting.value = true;
  processing.value = true;
  lastError.value = "";
  
  try {
    const fd = new FormData();
    fd.append("job_id", jobId.value);
    fd.append("settings", JSON.stringify(settings));
    await axios.post("/api/start", fd);
    
    ElMessage.success('转录任务已启动！');
    poll(); // 开始轮询状态
  } catch (e) {
    const errorMessage = "启动失败: " + (e?.message || e);
    statusText.value = errorMessage;
    processing.value = false;
    ElMessage.error(errorMessage);
  } finally {
    starting.value = false;
  }
}

async function cancelJob() {
  if (!jobId.value) return;
  
  try {
    await ElMessageBox.confirm('确定要取消当前转录任务吗？', '确认操作', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    });
    
    canceling.value = true;
    await axios.post(`/api/cancel/${jobId.value}`);
    ElMessage.success('任务已取消');
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('取消任务失败');
    }
  } finally {
    canceling.value = false;
  }
}

async function restartJob() {
  if (!jobId.value) return;
  
  try {
    await ElMessageBox.confirm('确定要重新转录当前文件吗？', '确认操作', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    });
    
    // 重置转录相关状态
    status.value = "";
    progress.value = 0;
    phase.value = "";
    statusText.value = "重新开始转录";
    downloadUrl.value = "";
    lastError.value = "";
    language.value = "";
    canRestart.value = false;
    
    // 清除之前的轮询
    if (pollTimer.value) {
      clearTimeout(pollTimer.value);
      pollTimer.value = null;
    }
    
    await startJob();
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('重新转录失败');
    }
  }
}

async function poll() {
  clearTimeout(pollTimer.value);
  if (!jobId.value) return;
  
  try {
    const { data } = await axios.get(`/api/status/${jobId.value}`);
    if (data.error) {
      statusText.value = data.error;
      processing.value = false;
      return;
    }
    
    status.value = data.status;
    progress.value = data.progress || 0;
    statusText.value = data.message || data.status;
    phase.value = data.phase || "";
    language.value = data.language || "";
    lastError.value = data.error || "";
    
    if (status.value === "finished") {
      processing.value = false;
      downloadUrl.value = `/api/download/${jobId.value}`;
      canRestart.value = true;
      ElMessage.success('转录完成！可以下载字幕文件了。');
    } else if (status.value === "failed" || status.value === "canceled") {
      processing.value = false;
      canRestart.value = true;
      if (status.value === "failed") {
        ElMessage.error('转录失败：' + (lastError.value || '未知错误'));
      }
    } else {
      // 继续轮询
      pollTimer.value = setTimeout(poll, 1500);
    }
  } catch (e) {
    // 网络错误：稍后重试
    pollTimer.value = setTimeout(poll, 2500);
  }
}

// 下载文件
function downloadFile() {
  if (downloadUrl.value) {
    window.open(downloadUrl.value, '_blank');
    ElMessage.success('开始下载字幕文件');
  }
}

// 复制结果到源目录
async function copyResultToSource() {
  if (!jobId.value) {
    ElMessage.warning('没有可复制的结果');
    return;
  }
  
  try {
    const { data } = await axios.post(`/api/copy-result/${jobId.value}`);
    ElMessage.success('字幕文件已复制到源文件目录！');
  } catch (error) {
    console.error('复制结果失败:', error);
    ElMessage.error('复制结果失败：' + (error.response?.data?.detail || error.message));
  }
}

// 组件卸载时清理定时器
onUnmounted(() => {
  if (pollTimer.value) {
    clearTimeout(pollTimer.value);
  }
});

onMounted(() => {
  // 页面加载时自动获取文件列表
  loadFiles();
  // 启动模型状态更新
  startModelStatusUpdates();
});

onUnmounted(() => {
  // 清理定时器
  if (modelStatusUpdateTimer.value) {
    clearInterval(modelStatusUpdateTimer.value);
  }
  if (pollTimer.value) {
    clearInterval(pollTimer.value);
  }
});
</script>

<style scoped>
.app-container {
  min-height: 100vh;
  /* background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); */
}

.header {
  background: rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.2);
  text-align: center;
  padding: 30px 0;
}

.title {
  color: #409eff;
  font-size: 2.5rem;
  font-weight: 700;
  margin: 0;
  /* text-shadow: 0 2px 4px rgba(91, 90, 90, 0.3); */
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
}

.title .el-icon {
  font-size: 2.5rem;
}

.subtitle {
  color: rgba(255, 255, 255, 0.9);
  font-size: 1.1rem;
  margin: 10px 0 0;
  font-weight: 300;
}

.main-content {
  padding: 40px 20px;
}

.upload-card,
.settings-card,
.progress-card {
  margin-bottom: 20px;
  border-radius: 16px;
  overflow: hidden;
  border: none;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 1.1rem;
  font-weight: 600;
  color: #2c3e50;
}

.file-selection-area {
  text-align: left;
}

.file-list {
  margin: 20px 0;
}

.file-name {
  display: flex;
  align-items: center;
  gap: 8px;
}

.selected-file {
  text-align: center;
  margin: 20px 10px;
}

.loading-files {
  text-align: center;
  padding: 40px 0;
  color: #606266;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.upload-mode {
  margin-bottom: 20px;
}

.upload-content {
  text-align: center;
  padding: 60px 20px;
}

.browse-mode {
  /* 保持现有布局 */
}

.upload-area {
  text-align: center;
}

.upload-icon {
  font-size: 4rem;
  color: #409eff;
  margin-bottom: 16px;
}

.upload-text {
  font-size: 1.2rem;
  color: #606266;
  margin-bottom: 8px;
}

.upload-hint {
  color: #909399;
  font-size: 0.9rem;
}

.file-info {
  margin: 20px 0;
}

.upload-actions {
  margin-top: 20px;
  display: flex;
  gap: 12px;
  justify-content: center;
  flex-wrap: wrap;
}

.upload-progress {
  margin-top: 20px;
}

.progress-text {
  margin-top: 8px;
  color: #606266;
  font-size: 0.9rem;
}

.action-buttons {
  text-align: center;
  margin-top: 20px;
  display: flex;
  gap: 12px;
  justify-content: center;
  flex-wrap: wrap;
}

.progress-content {
  text-align: center;
}

.status-info {
  margin: 20px 0;
}

.status-text {
  margin: 12px 0;
  font-size: 1rem;
  color: #606266;
}

.language-info {
  color: #67c23a;
  font-size: 0.95rem;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.download-section {
  margin-top: 20px;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .title {
    font-size: 2rem;
  }
  
  .title .el-icon {
    font-size: 2rem;
  }
  
  .subtitle {
    font-size: 1rem;
  }
  
  .main-content {
    padding: 20px 10px;
  }
  
  .action-buttons,
  .upload-actions {
    flex-direction: column;
    align-items: center;
  }
  
  .action-buttons .el-button,
  .upload-actions .el-button {
    width: 200px;
  }
}

/* 自定义 Element Plus 样式 */
:deep(.el-upload-dragger) {
  border: 2px dashed #d9d9d9;
  border-radius: 12px;
  background-color: #fafafa;
  transition: all 0.3s ease;
}

:deep(.el-upload-dragger:hover) {
  border-color: #409eff;
  background-color: #f0f9ff;
}

:deep(.el-card__header) {
  background: linear-gradient(90deg, #f8f9fa, #e9ecef);
  border-bottom: 2px solid #dee2e6;
}

:deep(.el-progress-bar__outer) {
  border-radius: 8px;
}

:deep(.el-progress-bar__inner) {
  border-radius: 8px;
  background: linear-gradient(90deg, #67c23a, #85ce61);
}

:deep(.el-button) {
  border-radius: 8px;
  font-weight: 500;
  transition: all 0.3s ease;
}

:deep(.el-tag) {
  border-radius: 6px;
  font-weight: 500;
}

:deep(.el-select),
:deep(.el-input-number) {
  width: 100%;
}

/* 模型状态对话框样式 */
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
