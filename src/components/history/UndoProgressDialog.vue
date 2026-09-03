<script setup lang="ts">
import { computed } from 'vue'
import type { UndoProgress } from '../../api/desktop'

const props = defineProps<{ modelValue: boolean; progress: UndoProgress }>()
const percentage = computed(() => props.progress.total > 0
  ? Math.min(100, Math.round(props.progress.current / props.progress.total * 100))
  : 0)
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    title="正在恢复原名称"
    width="520"
    align-center
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    :show-close="false"
    :destroy-on-close="false"
  >
    <div class="undo-progress" aria-live="polite">
      <el-progress :percentage="percentage" :stroke-width="10" />
      <div class="progress-count">
        <strong>{{ progress.current }} / {{ progress.total }}</strong>
        <span>{{ progress.outcome || '准备恢复' }}</span>
      </div>
      <div v-if="progress.path" class="current-item">
        <span>当前项目</span>
        <strong>{{ progress.path }}</strong>
      </div>
      <p>{{ progress.detail || '正在核对磁盘状态并恢复原名称。' }}</p>
    </div>
  </el-dialog>
</template>

<style scoped>
.undo-progress { display: grid; gap: 18px; }
.progress-count, .current-item { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.progress-count strong { color: var(--primary); font-size: 22px; }
.progress-count span, .current-item span, p { color: var(--muted); }
.current-item { padding: 14px; border-radius: 10px; background: var(--surface-soft); }
.current-item strong { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
p { margin: 0; font-size: 13px; line-height: 1.7; }
</style>
