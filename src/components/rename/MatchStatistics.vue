<script setup lang="ts">
import { useRenameStore } from '../../stores/rename'

const store = useRenameStore()
</script>

<template>
  <footer class="stats">
    <template v-if="store.resultMode === 'directory'">
      <span>根目录内容：<b>{{ store.rootTotal }}</b> 项</span>
      <span>当前显示：{{ store.previewLimit === null ? store.rootItems.length : Math.min(store.rootItems.length, store.previewLimit) }} 项</span>
      <span>输入查找内容并扫描后，列表将切换为符合项</span>
    </template>
    <template v-else>
      <span>匹配：<b>{{ store.summary.matched }}</b> 项</span>
      <span>可修改：<b class="ok">{{ store.summary.ready }}</b></span>
      <span>无变化：{{ store.summary.unchanged }}</span>
      <span>冲突：{{ store.summary.conflicts }}</span>
      <span>阻止：{{ store.summary.invalid }}</span>
    </template>
  </footer>
</template>

<style scoped>
.stats {
  display: flex;
  gap: 22px;
  min-height: 46px;
  align-items: center;
  padding: 0 16px;
  color: var(--muted);
  border-top: 1px solid var(--border);
  white-space: nowrap;
  overflow: hidden;
}

b {
  color: var(--text);
}

.ok {
  color: var(--success);
}
</style>
