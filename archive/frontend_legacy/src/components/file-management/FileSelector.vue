<!--
  文件选择组件 - 支持本地input模式和上传模式
-->
<template>
  <el-card class="upload-card" shadow="hover">
    <template #header>
      <div class="card-header">
        <el-icon><FolderOpened /></el-icon>
        <span>1. 选择媒体文件</span>
        <div style="margin-left: auto; display: flex; gap: 8px;">
          <el-button 
            type="success" 
            size="small"
            @click="$emit('toggle-mode')"
            :disabled="creating || uploading"
          >
            <el-icon><Upload /></el-icon>
            {{ showUpload ? '切换到本地模式' : '切换到上传模式' }}
          </el-button>
          <el-button 
            type="primary" 
            size="small"
            @click="$emit('refresh-files')"
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
            @row-click="$emit('select-file', $event)"
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
                  @click.stop="$emit('select-file', scope.row)"
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
          <el-button type="primary" @click="$emit('refresh-files')">刷新文件列表</el-button>
        </el-empty>

        <!-- 加载中 -->
        <div v-if="loadingFiles" class="loading-files">
          <el-icon class="is-loading"><Loading /></el-icon>
          <span>正在加载文件列表...</span>
        </div>
      </div>

      <!-- 选中的文件 -->
      <div v-if="selectedFile && !showUpload" class="selected-file">
        <el-tag type="success" size="large" closable @close="$emit('clear-selection')">
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
          @click="$emit('create-job')"
          style="margin-top: 12px;"
        >
          <el-icon v-if="!creating"><FolderAdd /></el-icon>
          {{ creating ? "创建中..." : "创建转录任务" }}
        </el-button>
      </div>
    </div>
  </el-card>
</template>

<script setup>
import { defineEmits, defineProps } from 'vue'
import { formatFileSize } from '../../utils/helpers.js'
import { FileService } from '../../services/fileService.js'

// 定义props
const props = defineProps({
  showUpload: Boolean,
  availableFiles: Array,
  selectedFile: Object,
  loadingFiles: Boolean,
  creating: Boolean,
  uploading: Boolean,
  uploadProgress: Number,
  inputDirPath: String,
  jobId: String
})

// 定义emits
const emits = defineEmits([
  'toggle-mode',
  'refresh-files', 
  'select-file',
  'clear-selection',
  'create-job',
  'upload-file'
])

// 检查是否为视频文件
function isVideoFile(filename) {
  return FileService.isVideoFile(filename)
}

// 处理文件上传
function handleUpload(uploadFile) {
  emits('upload-file', uploadFile)
}
</script>

<style scoped>
.upload-card {
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
</style>