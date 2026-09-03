<script setup lang="ts">
import type { OperationSummary } from '../../api/desktop'

defineProps<{ items: OperationSummary[]; loading: boolean }>()
defineEmits(['select'])
</script>

<template>
  <div v-loading="loading" class="list">
    <button v-for="item in items" :key="item.identifier" @click="$emit('select', item.identifier)">
      <span>
        <b>{{ item.search || '未记录规则' }} → {{ item.replacement || '删除' }}</b>
        <small>{{ item.root }}</small>
        <small class="counts">
          成功 {{ item.successCount }}　跳过 {{ item.skippedCount }}　失败 {{ item.failedCount }}
        </small>
      </span>
      <span class="status">
        <el-tag size="small">{{ item.status }}</el-tag>
        <small v-if="item.pendingUndoCount">待撤回 {{ item.pendingUndoCount }}</small>
        <small v-else-if="item.undoneCount">已撤回 {{ item.undoneCount }}</small>
        <small>共 {{ item.itemCount }} 项</small>
      </span>
    </button>
    <el-empty v-if="!loading && !items.length" description="暂无操作日志" />
  </div>
</template>

<style scoped>
.list { display: grid; align-content: start; gap: 8px; overflow: auto; }
.list button { display: flex; justify-content: space-between; gap: 16px; padding: 14px; border: 1px solid var(--border); border-radius: var(--radius); background: var(--surface); color: var(--text); text-align: left; cursor: pointer; }
.list button:hover { border-color: var(--primary); }
span { display: grid; gap: 6px; min-width: 0; }
small { overflow: hidden; color: var(--muted); text-overflow: ellipsis; white-space: nowrap; }
.counts { color: var(--text-secondary); }
.status { justify-items: end; flex: 0 0 auto; }
</style>
