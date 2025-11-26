<template>
  <div class="task-list-view">
    <h1>任务列表</h1>
    <p class="placeholder-text">此页面将在阶段 5 实现</p>
    <el-button @click="goToTest">返回测试页面</el-button>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'

const router = useRouter()

function goToTest() {
  router.push('/test')
}
</script>

<style lang="scss" scoped>
.task-list-view {
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
}
</style>
