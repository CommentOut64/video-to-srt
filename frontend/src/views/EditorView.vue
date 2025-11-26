<template>
  <div class="editor-view">
    <h1>字幕编辑器</h1>
    <p class="placeholder-text">此页面将在阶段 5 实现</p>
    <p class="job-id">Job ID: {{ jobId }}</p>
    <el-button @click="goToTest">返回测试页面</el-button>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'

const props = defineProps({
  jobId: {
    type: String,
    required: true
  }
})

const router = useRouter()

function goToTest() {
  router.push('/test')
}
</script>

<style lang="scss" scoped>
.editor-view {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  gap: 24px;

  h1 {
    color: var(--text-bright);
  }

  .placeholder-text {
    color: var(--text-muted);
  }

  .job-id {
    font-family: monospace;
    color: var(--accent-blue);
  }
}
</style>
