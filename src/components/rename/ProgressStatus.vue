<script setup lang="ts">
import { useRenameStore } from '../../stores/rename'

const store = useRenameStore()
</script>

<template>
  <el-alert
    v-if="store.errorMessage"
    type="error"
    :title="store.errorMessage"
    :closable="false"
    show-icon
  />
  <div v-else-if="store.busy === 'scanning' || store.busy === 'previewing'" class="progress">
    <el-progress
      :percentage="store.busy === 'scanning' ? 50 : 100"
      :indeterminate="store.busy === 'scanning'"
    />
    <span>
      {{ store.busy === 'scanning'
        ? `正在扫描：${store.progress.scannedDirectoryCount} 个文件夹，${store.progress.scannedFileCount} 个文件…`
        : '正在生成预览…' }}
    </span>
  </div>
</template>

<style scoped>
.progress {
  display: grid;
  grid-template-columns: 180px 1fr;
  align-items: center;
  gap: 12px;
  color: var(--muted);
  font-size: 13px;
}
</style>
