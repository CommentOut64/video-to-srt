<template>
  <div id="app">
    <div class="container">
      <!-- 顶部标题栏 -->
      <div class="header">
        <div class="header-content">
          <h1 class="title">
            <img src="/logo.png" alt="Logo" class="logo" />
            视频转字幕工具
          </h1>
          <div class="header-actions">
            <!-- 模型状态按钮 -->
            <ModelStatusButton />
            
            <!-- 硬件信息按钮 -->
            <el-button type="info" size="small" @click="showHardwareDialog = true" plain>
              <el-icon><Monitor /></el-icon>
              硬件信息
            </el-button>
          </div>
        </div>
      </div>

      <!-- 主要内容区域 -->
      <div class="main-content">
        <!-- 文件选择器 -->
        <FileSelector v-model:file="selectedFile" @file-change="handleFileChange" />
        
        <!-- 转录设置 -->
        <TranscriptionSettings 
          v-model:settings="settings" 
          :file="selectedFile"
          @settings-change="handleSettingsChange"
        />
        
        <!-- 进度显示 -->
        <ProgressDisplay 
          :job="currentJob"
          :results="results"
          :show="showProgress"
          @cancel="handleCancel"
          @download="handleDownload"
        />
        
        <!-- 硬件信息对话框 -->
        <HardwareDialog v-model="showHardwareDialog" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Monitor } from '@element-plus/icons-vue'
import { FileService } from './services/FileService'
import { TranscriptionService } from './services/TranscriptionService'

// 导入组件
import FileSelector from './components/ui/FileSelector.vue'
import TranscriptionSettings from './components/ui/TranscriptionSettings.vue'
import ProgressDisplay from './components/ui/ProgressDisplay.vue'
import HardwareDialog from './components/ui/HardwareDialog.vue'
import ModelStatusButton from './components/models/ModelStatusButton.vue'

// 响应式数据
const selectedFile = ref(null)
const showHardwareDialog = ref(false)
const showProgress = ref(false)
const currentJob = ref(null)
const results = reactive({})

// 转录设置
const settings = reactive({
  model: 'small',
  language: 'auto',
  useVAD: true,
  batchSize: 16,
  computeType: 'float16',
  outputFormat: 'srt',
  maxLineWidth: 42,
  maxLineCount: 2,
  highlightWords: false
})

// 计算属性
const canStartTranscription = computed(() => {
  return selectedFile.value && !showProgress.value
})

// 方法
function handleFileChange(file) {
  selectedFile.value = file
  results.value = {}
}

function handleSettingsChange(newSettings) {
  Object.assign(settings, newSettings)
}

async function handleStartTranscription() {
  if (!selectedFile.value) {
    ElMessage.warning('请先选择一个文件')
    return
  }

  try {
    showProgress.value = true
    
    // 开始转录
    const job = await TranscriptionService.startTranscription(
      selectedFile.value,
      settings
    )
    
    currentJob.value = job
    
    // 轮询作业状态
    await TranscriptionService.pollJobStatus(job.job_id, (jobData) => {
      currentJob.value = jobData
      
      if (jobData.status === 'completed') {
        ElMessage.success('转录完成!')
        results.value = jobData.result || {}
      } else if (jobData.status === 'failed') {
        ElMessage.error('转录失败: ' + (jobData.error || '未知错误'))
      }
    })
    
  } catch (error) {
    console.error('转录错误:', error)
    ElMessage.error('转录失败: ' + (error.response?.data?.message || error.message))
  } finally {
    showProgress.value = false
  }
}

function handleCancel() {
  if (currentJob.value?.job_id) {
    TranscriptionService.cancelJob(currentJob.value.job_id)
  }
  showProgress.value = false
  currentJob.value = null
}

function handleDownload(type) {
  if (currentJob.value?.job_id) {
    TranscriptionService.downloadResult(currentJob.value.job_id, type)
  }
}
</script>

<style scoped>
#app {
  font-family: 'Avenir', Helvetica, Arial, sans-serif;
  color: #2c3e50;
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

.header {
  background: rgba(255, 255, 255, 0.95);
  border-radius: 15px;
  margin-bottom: 20px;
  box-shadow: 0 8px 32px rgba(31, 38, 135, 0.37);
  backdrop-filter: blur(4px);
  border: 1px solid rgba(255, 255, 255, 0.18);
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 30px;
}

.title {
  font-size: 2rem;
  font-weight: 700;
  color: #2c3e50;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 15px;
}

.logo {
  width: 40px;
  height: 40px;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.main-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

@media (max-width: 768px) {
  .container {
    padding: 10px;
  }
  
  .header-content {
    flex-direction: column;
    gap: 15px;
    padding: 15px 20px;
  }
  
  .title {
    font-size: 1.5rem;
  }
}
</style>
