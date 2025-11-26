<template>
  <div class="editor-view">
    <!-- 顶部导航栏 -->
    <header class="editor-header">
      <div class="header-left">
        <router-link to="/tasks" class="back-btn" title="返回任务列表">
          <svg viewBox="0 0 24 24" fill="currentColor">
            <path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/>
          </svg>
        </router-link>
        <div class="project-info">
          <h1 class="project-name">{{ projectName }}</h1>
          <span v-if="isDirty" class="unsaved-badge">未保存</span>
        </div>
      </div>

      <div class="header-center">
        <PlaybackControls :compact="true" />
      </div>

      <div class="header-right">
        <!-- 撤销/重做 -->
        <div class="btn-group">
          <button class="header-btn" :class="{ disabled: !canUndo }" @click="undo" title="撤销 (Ctrl+Z)">
            <svg viewBox="0 0 24 24" fill="currentColor">
              <path d="M12.5 8c-2.65 0-5.05.99-6.9 2.6L2 7v9h9l-3.62-3.62c1.39-1.16 3.16-1.88 5.12-1.88 3.54 0 6.55 2.31 7.6 5.5l2.37-.78C21.08 11.03 17.15 8 12.5 8z"/>
            </svg>
          </button>
          <button class="header-btn" :class="{ disabled: !canRedo }" @click="redo" title="重做 (Ctrl+Y)">
            <svg viewBox="0 0 24 24" fill="currentColor">
              <path d="M18.4 10.6C16.55 8.99 14.15 8 11.5 8c-4.65 0-8.58 3.03-9.96 7.22L3.9 16c1.05-3.19 4.05-5.5 7.6-5.5 1.95 0 3.73.72 5.12 1.88L13 16h9V7l-3.6 3.6z"/>
            </svg>
          </button>
        </div>

        <!-- 保存按钮 -->
        <button class="header-btn header-btn--primary" @click="saveProject" :class="{ loading: saving }" title="保存 (Ctrl+S)">
          <svg v-if="!saving" viewBox="0 0 24 24" fill="currentColor">
            <path d="M17 3H5c-1.11 0-2 .9-2 2v14c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V7l-4-4zm-5 16c-1.66 0-3-1.34-3-3s1.34-3 3-3 3 1.34 3 3-1.34 3-3 3zm3-10H5V5h10v4z"/>
          </svg>
          <span v-if="saving" class="spinner"></span>
          <span>保存</span>
        </button>

        <!-- 导出下拉菜单 -->
        <div class="dropdown" ref="exportDropdownRef">
          <button class="header-btn" @click="toggleExportMenu">
            <svg viewBox="0 0 24 24" fill="currentColor">
              <path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/>
            </svg>
            <span>导出</span>
            <svg class="arrow" viewBox="0 0 24 24" fill="currentColor">
              <path d="M7 10l5 5 5-5z"/>
            </svg>
          </button>
          <div v-show="showExportMenu" class="dropdown-menu">
            <button @click="handleExport('srt')">SRT 格式</button>
            <button @click="handleExport('vtt')">WebVTT 格式</button>
            <button @click="handleExport('txt')">纯文本</button>
            <button @click="handleExport('json')">JSON 格式</button>
          </div>
        </div>
      </div>
    </header>

    <!-- 主编辑区域 -->
    <main class="editor-main">
      <!-- 左侧面板：视频 + 波形 -->
      <div class="panel panel-left" :style="{ width: leftPanelWidth + 'px' }">
        <div class="video-section">
          <VideoStage :job-id="jobId" :show-subtitle="true" @loaded="handleVideoLoaded" @error="handleVideoError" />
        </div>
        <div class="timeline-section">
          <WaveformTimeline :job-id="jobId" @ready="handleWaveformReady" @region-update="handleRegionUpdate" @region-click="handleRegionClick" />
        </div>
      </div>

      <!-- 调整分隔条 -->
      <div class="resizer" @mousedown="startResize"></div>

      <!-- 右侧面板：字幕列表 + 其他 -->
      <div class="panel panel-right">
        <!-- 标签页导航 -->
        <div class="tab-nav">
          <button class="tab-btn" :class="{ active: activeTab === 'subtitles' }" @click="activeTab = 'subtitles'">字幕列表</button>
          <button class="tab-btn" :class="{ active: activeTab === 'validation' }" @click="activeTab = 'validation'">
            问题检查
            <span v-if="errorCount > 0" class="badge">{{ errorCount }}</span>
          </button>
          <button class="tab-btn" :class="{ active: activeTab === 'assistant' }" @click="activeTab = 'assistant'">AI 助手</button>
        </div>

        <!-- 标签页内容 -->
        <div class="tab-content">
          <div v-show="activeTab === 'subtitles'" class="tab-pane">
            <SubtitleList :auto-scroll="true" :editable="true" @subtitle-click="handleSubtitleClick" @subtitle-edit="handleSubtitleEdit" />
          </div>

          <div v-show="activeTab === 'validation'" class="tab-pane">
            <div class="placeholder-panel">
              <svg viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
              </svg>
              <h3>问题检查</h3>
              <p v-if="errorCount === 0">没有发现问题</p>
              <p v-else>发现 {{ errorCount }} 个问题</p>
              <div class="error-list" v-if="errorCount > 0">
                <div v-for="error in validationErrors" :key="`${error.type}-${error.index}`" class="error-item" :class="error.severity" @click="jumpToError(error)">
                  <span class="error-index">#{{ error.index + 1 }}</span>
                  <span class="error-message">{{ error.message }}</span>
                </div>
              </div>
            </div>
          </div>

          <div v-show="activeTab === 'assistant'" class="tab-pane">
            <div class="placeholder-panel">
              <svg viewBox="0 0 24 24" fill="currentColor">
                <path d="M21 10.5h-6.5V4h-5v6.5H3v5h6.5V22h5v-6.5H21v-5z"/>
              </svg>
              <h3>AI 助手</h3>
              <p>智能字幕优化功能</p>
              <p class="coming-soon">即将推出</p>
            </div>
          </div>
        </div>
      </div>
    </main>

    <!-- 底部状态栏 -->
    <footer class="editor-footer">
      <div class="footer-left">
        <span>{{ totalSubtitles }} 条字幕</span>
        <span v-if="currentSubtitle" class="divider">|</span>
        <span v-if="currentSubtitle">当前: #{{ currentSubtitleIndex + 1 }}</span>
      </div>
      <div class="footer-center">
        <span v-if="lastSaved">最后保存: {{ formatLastSaved(lastSaved) }}</span>
      </div>
      <div class="footer-right">
        <span v-if="errorCount > 0" class="error-indicator" @click="activeTab = 'validation'">{{ errorCount }} 个问题</span>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, provide } from 'vue'
import { useRouter, onBeforeRouteLeave } from 'vue-router'
import { useProjectStore } from '@/stores/projectStore'
import { useUnifiedTaskStore } from '@/stores/unifiedTaskStore'
import PlaybackControls from '@/components/editor/PlaybackControls/index.vue'
import VideoStage from '@/components/editor/VideoStage/index.vue'
import SubtitleList from '@/components/editor/SubtitleList/index.vue'
import WaveformTimeline from '@/components/editor/WaveformTimeline/index.vue'

const props = defineProps({ jobId: { type: String, required: true } })
const router = useRouter()
const projectStore = useProjectStore()
const taskStore = useUnifiedTaskStore()
const exportDropdownRef = ref(null)
const activeTab = ref('subtitles')
const saving = ref(false)
const lastSaved = ref(null)
const showExportMenu = ref(false)
const leftPanelWidth = ref(600)
const isResizing = ref(false)

provide('editorContext', { jobId: props.jobId, saving })

const projectName = computed(() => projectStore.meta.filename || '未命名项目')
const isDirty = computed(() => projectStore.isDirty)
const totalSubtitles = computed(() => projectStore.totalSubtitles)
const currentSubtitle = computed(() => projectStore.currentSubtitle)
const currentSubtitleIndex = computed(() => currentSubtitle.value ? projectStore.subtitles.findIndex(s => s.id === currentSubtitle.value.id) : -1)
const canUndo = computed(() => projectStore.canUndo)
const canRedo = computed(() => projectStore.canRedo)
const validationErrors = computed(() => projectStore.validationErrors)
const errorCount = computed(() => validationErrors.value.filter(e => e.severity === 'error').length)

async function loadProject() {
  try {
    const restored = await projectStore.restoreProject(props.jobId)
    if (!restored) loadTestData()
  } catch (error) {
    console.error('加载项目失败:', error)
  }
}

function loadTestData() {
  const testSRT = `1
00:00:01,000 --> 00:00:04,000
欢迎使用字幕编辑器

2
00:00:05,000 --> 00:00:08,500
这是一个功能强大的在线工具

3
00:00:09,000 --> 00:00:12,000
支持波形可视化和精确时间调整

4
00:00:13,000 --> 00:00:16,500
让字幕编辑变得简单高效`

  projectStore.importSRT(testSRT, {
    jobId: props.jobId,
    filename: '示例视频.mp4',
    duration: 60,
    videoPath: `/api/media/${props.jobId}/video`,
    audioPath: `/api/media/${props.jobId}/audio`
  })
}

async function saveProject() {
  if (saving.value) return
  saving.value = true
  try {
    await projectStore.saveProject()
    lastSaved.value = Date.now()
  } catch (error) {
    console.error('保存失败:', error)
  } finally {
    saving.value = false
  }
}

function undo() { if (canUndo.value) projectStore.undo() }
function redo() { if (canRedo.value) projectStore.redo() }
function toggleExportMenu() { showExportMenu.value = !showExportMenu.value }

function handleExport(format) {
  showExportMenu.value = false
  let content = ''
  let filename = projectName.value.replace(/\.[^/.]+$/, '')

  switch (format) {
    case 'srt': content = projectStore.generateSRT(); filename += '.srt'; break
    case 'vtt': content = generateVTT(); filename += '.vtt'; break
    case 'txt': content = projectStore.subtitles.map(s => s.text).join('\n'); filename += '.txt'; break
    case 'json': content = JSON.stringify(projectStore.subtitles, null, 2); filename += '.json'; break
  }

  downloadFile(content, filename)
}

function generateVTT() {
  let vtt = 'WEBVTT\n\n'
  projectStore.subtitles.forEach((sub, i) => {
    const start = formatVTTTime(sub.start)
    const end = formatVTTTime(sub.end)
    vtt += `${i + 1}\n${start} --> ${end}\n${sub.text}\n\n`
  })
  return vtt
}

function formatVTTTime(seconds) {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = (seconds % 60).toFixed(3)
  return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.padStart(6, '0')}`
}

function downloadFile(content, filename) {
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function handleVideoLoaded(duration) { console.log('视频加载完成:', duration) }
function handleVideoError(error) { console.error('视频加载错误:', error) }
function handleWaveformReady() { console.log('波形加载完成') }
function handleRegionUpdate(region) { console.log('区域更新:', region) }
function handleRegionClick(region) { console.log('区域点击:', region) }
function handleSubtitleClick(subtitle) { console.log('字幕点击:', subtitle) }
function handleSubtitleEdit(id, field, value) { console.log('字幕编辑:', id, field, value) }

function jumpToError(error) {
  const subtitle = projectStore.subtitles[error.index]
  if (subtitle) {
    projectStore.view.selectedSubtitleId = subtitle.id
    projectStore.seekTo(subtitle.start)
    activeTab.value = 'subtitles'
  }
}

function startResize(e) {
  isResizing.value = true
  document.addEventListener('mousemove', onResize)
  document.addEventListener('mouseup', stopResize)
}

function onResize(e) {
  if (!isResizing.value) return
  const newWidth = e.clientX
  leftPanelWidth.value = Math.max(400, Math.min(window.innerWidth - 400, newWidth))
}

function stopResize() {
  isResizing.value = false
  document.removeEventListener('mousemove', onResize)
  document.removeEventListener('mouseup', stopResize)
}

function handleClickOutside(e) {
  if (exportDropdownRef.value && !exportDropdownRef.value.contains(e.target)) {
    showExportMenu.value = false
  }
}

function handleKeydown(e) {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return
  if (e.ctrlKey || e.metaKey) {
    switch (e.key) {
      case 's': e.preventDefault(); saveProject(); break
      case 'z': e.preventDefault(); e.shiftKey ? redo() : undo(); break
      case 'y': e.preventDefault(); redo(); break
    }
  }
}

function formatLastSaved(timestamp) {
  const date = new Date(timestamp)
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

onBeforeRouteLeave((to, from) => {
  if (isDirty.value) {
    const answer = window.confirm('有未保存的修改，确定要离开吗?')
    if (!answer) return false
  }
})

onMounted(() => {
  loadProject()
  document.addEventListener('keydown', handleKeydown)
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown)
  document.removeEventListener('click', handleClickOutside)
})
</script>

<style lang="scss" scoped>
@use '@/styles/variables' as *;
@use '@/styles/mixins' as *;

.editor-view {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--bg-base);
  color: var(--text-normal);
}

.editor-header {
  @include flex-between;
  height: 56px;
  padding: 0 16px;
  background: var(--bg-primary);
  border-bottom: 1px solid var(--border-default);
  flex-shrink: 0;

  .header-left, .header-center, .header-right { display: flex; align-items: center; gap: 12px; }
  .header-center { flex: 1; justify-content: center; max-width: 600px; margin: 0 24px; }

  .back-btn {
    @include flex-center;
    width: 36px;
    height: 36px;
    border-radius: var(--radius-md);
    color: var(--text-secondary);
    transition: all var(--transition-fast);
    svg { width: 20px; height: 20px; }
    &:hover { background: var(--bg-tertiary); color: var(--text-primary); }
  }

  .project-name { font-size: 16px; font-weight: 600; color: var(--text-primary); margin: 0; }
  .unsaved-badge { padding: 2px 8px; background: rgba(210, 153, 34, 0.15); color: var(--warning); font-size: 11px; border-radius: var(--radius-full); }

  .btn-group { display: flex; background: var(--bg-secondary); border-radius: var(--radius-md); overflow: hidden; }

  .header-btn {
    height: 36px;
    padding: 0 12px;
    @include flex-center;
    gap: 6px;
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
    color: var(--text-normal);
    font-size: 13px;
    transition: all var(--transition-fast);
    svg { width: 18px; height: 18px; }
    .arrow { width: 14px; height: 14px; margin-left: -2px; }
    &:hover { background: var(--bg-tertiary); }
    &.disabled { opacity: 0.4; pointer-events: none; }
    &--primary { background: var(--primary); color: white; &:hover { background: var(--primary-hover); } }
    &.loading { pointer-events: none; }
    .spinner { width: 14px; height: 14px; border: 2px solid rgba(255, 255, 255, 0.3); border-top-color: white; border-radius: 50%; animation: spin 0.8s linear infinite; }
  }

  .dropdown { position: relative; }
  .dropdown-menu {
    position: absolute; top: 100%; right: 0; margin-top: 4px;
    background: var(--bg-elevated); border: 1px solid var(--border-default); border-radius: var(--radius-md);
    box-shadow: var(--shadow-lg); padding: 4px; z-index: 100; min-width: 140px;
    button { display: block; width: 100%; padding: 8px 12px; text-align: left; font-size: 13px; color: var(--text-normal); border-radius: var(--radius-sm); transition: background var(--transition-fast); &:hover { background: var(--bg-tertiary); } }
  }
}

@keyframes spin { to { transform: rotate(360deg); } }

.editor-main { flex: 1; display: flex; overflow: hidden; }
.panel { display: flex; flex-direction: column; overflow: hidden; }
.panel-left { min-width: 400px; .video-section { flex: 1; min-height: 200px; padding: 12px; } .timeline-section { height: 240px; padding: 0 12px 12px; } }
.resizer { width: 4px; background: var(--border-default); cursor: col-resize; transition: background var(--transition-fast); &:hover { background: var(--primary); } }
.panel-right { flex: 1; min-width: 350px; display: flex; flex-direction: column; background: var(--bg-primary); }

.tab-nav {
  display: flex; padding: 0 12px; background: var(--bg-secondary); border-bottom: 1px solid var(--border-default);
  .tab-btn {
    position: relative; padding: 12px 16px; font-size: 13px; color: var(--text-secondary); transition: color var(--transition-fast);
    &::after { content: ''; position: absolute; bottom: 0; left: 0; right: 0; height: 2px; background: transparent; transition: background var(--transition-fast); }
    &:hover { color: var(--text-normal); }
    &.active { color: var(--primary); &::after { background: var(--primary); } }
    .badge { @include flex-center; min-width: 18px; height: 18px; margin-left: 6px; padding: 0 5px; background: var(--danger); color: white; font-size: 11px; border-radius: var(--radius-full); }
  }
}

.tab-content { flex: 1; overflow: hidden; }
.tab-pane { height: 100%; overflow: auto; }

.placeholder-panel {
  @include flex-center;
  @include flex-column;
  padding: 48px 24px; text-align: center; color: var(--text-muted);
  svg { width: 48px; height: 48px; margin-bottom: 16px; opacity: 0.5; }
  h3 { font-size: 16px; font-weight: 600; color: var(--text-normal); margin-bottom: 8px; }
  p { font-size: 13px; margin-bottom: 4px; }
  .coming-soon { color: var(--primary); font-style: italic; }
  .error-list { width: 100%; max-width: 400px; margin-top: 16px; text-align: left; }
  .error-item {
    display: flex; align-items: center; gap: 8px; padding: 8px 12px; margin-bottom: 4px;
    background: var(--bg-secondary); border-radius: var(--radius-sm); cursor: pointer; transition: background var(--transition-fast);
    &:hover { background: var(--bg-tertiary); }
    &.error { border-left: 3px solid var(--danger); }
    &.warning { border-left: 3px solid var(--warning); }
    .error-index { font-family: var(--font-mono); font-size: 12px; color: var(--text-muted); }
    .error-message { font-size: 13px; color: var(--text-normal); }
  }
}

.editor-footer {
  @include flex-between;
  height: 28px; padding: 0 16px;
  background: var(--bg-secondary); border-top: 1px solid var(--border-default);
  font-size: 12px; color: var(--text-muted); flex-shrink: 0;
  .footer-left, .footer-center, .footer-right { display: flex; align-items: center; gap: 8px; }
  .divider { color: var(--border-default); }
  .error-indicator { color: var(--danger); cursor: pointer; &:hover { text-decoration: underline; } }
}
</style>
