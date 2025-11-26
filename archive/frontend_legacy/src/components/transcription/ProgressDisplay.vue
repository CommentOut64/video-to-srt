<!--
  转录进度显示组件
-->
<template>
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
        :status="getProgressStatus(status)"
      />
      
      <!-- 状态信息 -->
      <div class="status-info">
        <el-tag :type="getStatusType(status)" size="large">
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
          @click="$emit('download')"
        >
          <el-icon><Download /></el-icon>
          下载 SRT 字幕文件
        </el-button>
        
        <el-button 
          type="warning" 
          size="large"
          @click="$emit('copy-to-source')"
          style="margin-left: 12px;"
        >
          <el-icon><FolderAdd /></el-icon>
          复制到源文件目录
        </el-button>
      </div>
    </div>
  </el-card>
</template>

<script setup>
import { defineProps, defineEmits, computed } from 'vue'
import { phaseMap, getProgressStatus, getStatusType } from '../../utils/helpers.js'

// 定义props
const props = defineProps({
  jobId: String,
  progress: Number,
  status: String,
  statusText: String,
  downloadUrl: String,
  lastError: String,
  phase: String,
  language: String
})

// 定义emits
const emits = defineEmits(['download', 'copy-to-source'])

// 计算属性
const phaseLabel = computed(() => phaseMap[props.phase] || props.phase || "等待处理")
</script>

<style scoped>
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

:deep(.el-progress-bar__outer) {
  border-radius: 8px;
}

:deep(.el-progress-bar__inner) {
  border-radius: 8px;
  background: linear-gradient(90deg, #67c23a, #85ce61);
}
</style>