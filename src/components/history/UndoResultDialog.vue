<script setup lang="ts">
import { computed } from 'vue'
import type { UndoSummary } from '../../api/desktop'

const props = defineProps<{ modelValue: boolean; summary: UndoSummary | null }>()
defineEmits(['update:modelValue'])
const complete = computed(() => (props.summary?.failed ?? 0) === 0)
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    :title="complete ? '撤回完成' : '撤回未全部完成'"
    width="500"
    align-center
    @close="$emit('update:modelValue', false)"
  >
    <el-result
      :icon="complete ? 'success' : 'warning'"
      :title="complete ? '原名称已经恢复' : '部分项目需要处理后重试'"
      sub-title="结果已经写入操作日志，可在当前详情中核对每个项目。"
    >
      <template #extra>
        <span>成功 {{ summary?.succeeded ?? 0 }} 项　失败 {{ summary?.failed ?? 0 }} 项</span>
      </template>
    </el-result>
  </el-dialog>
</template>
