<script setup lang="ts">
import { computed } from 'vue'
import type { ExecutionProgress } from '../../api/desktop'

const props = defineProps<{
  modelValue: boolean
  progress: ExecutionProgress
}>()

const percentage = computed(() => {
  if (props.progress.total <= 0) return 0
  return Math.min(100, Math.round((props.progress.current / props.progress.total) * 100))
})
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    title="正在处理文件名"
    width="520"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    :show-close="false"
    :destroy-on-close="false"
    align-center
  >
    <div class="execution-progress" aria-live="polite">
      <el-progress :percentage="percentage" :stroke-width="10" />
      <div class="progress-count">
        <strong>{{ progress.current }} / {{ progress.total }}</strong>
        <span>正在安全更新所选项目</span>
      </div>
      <div v-if="progress.relativePath" class="current-item">
        <span>当前项目</span>
        <strong>{{ progress.relativePath }}</strong>
      </div>
      <p>处理完成前窗口会保持锁定，以免目录或规则变化影响本次结果。</p>
    </div>
  </el-dialog>
</template>

<style scoped>
.execution-progress {
  display: grid;
  gap: 18px;
}

.progress-count,
.current-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.progress-count strong {
  color: var(--primary);
  font-size: 22px;
}

.progress-count span,
.current-item span,
p {
  color: var(--muted);
}

.current-item {
  padding: 14px;
  border-radius: 10px;
  background: var(--surface-soft);
}

.current-item strong {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

p {
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
}
</style>
