<script setup lang="ts">
import type { OperationStatus } from '../../types/contracts'

defineProps<{ query: string; status: string }>()
defineEmits(['update:query', 'update:status', 'search'])

const statuses: OperationStatus[] = [
  '准备中', '执行中', '已完成', '部分失败', '已中断',
  '撤回检查失败', '撤回中', '已撤回', '部分撤回', '记录损坏',
]
</script>

<template>
  <div class="filters">
    <el-input
      :model-value="query"
      clearable
      placeholder="搜索目录、查找或替换内容"
      @update:model-value="$emit('update:query', $event)"
      @keyup.enter="$emit('search')"
    />
    <el-select :model-value="status" @update:model-value="$emit('update:status', $event)">
      <el-option label="全部状态" value="" />
      <el-option v-for="value in statuses" :key="value" :label="value" :value="value" />
    </el-select>
    <el-button type="primary" @click="$emit('search')">查询</el-button>
  </div>
</template>

<style scoped>
.filters { display: grid; grid-template-columns: minmax(220px, 1fr) 150px auto; gap: 10px; }
</style>
