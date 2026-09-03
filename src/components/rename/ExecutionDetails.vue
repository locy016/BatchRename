<script setup lang="ts">
defineProps<{ modelValue: boolean; operationId: string }>()
defineEmits(['update:modelValue'])
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    title="处理完成"
    width="500"
    align-center
    @close="$emit('update:modelValue', false)"
  >
    <el-result
      icon="success"
      title="文件名处理已经完成"
      sub-title="每个项目的处理结果均已写入操作日志，需要时可在对应日志详情中恢复。"
    >
      <template #extra><code>{{ operationId }}</code></template>
    </el-result>
  </el-dialog>
</template>
