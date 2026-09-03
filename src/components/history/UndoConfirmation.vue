<script setup lang="ts">
defineProps<{ modelValue: boolean; root: string; total: number }>()
defineEmits(['update:modelValue', 'confirm'])
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    title="确认恢复原名称"
    width="520"
    align-center
    :close-on-click-modal="false"
    @close="$emit('update:modelValue', false)"
  >
    <el-alert
      title="撤回会按安全顺序恢复这一批名称"
      type="warning"
      :closable="false"
      show-icon
    />
    <dl>
      <dt>根目录</dt><dd>{{ root }}</dd>
      <dt>待恢复</dt><dd><strong>{{ total }} 项</strong></dd>
    </dl>
    <p>程序不会覆盖现有项目。处理期间请勿移动、删除或改名相关文件和文件夹。</p>
    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">返回检查</el-button>
      <el-button type="primary" @click="$emit('confirm')">确认恢复</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
dl { display: grid; grid-template-columns: 70px 1fr; gap: 14px; margin: 20px 0 14px; }
dt, p { color: var(--muted); }
dd { min-width: 0; margin: 0; word-break: break-all; }
strong { color: var(--primary); font-size: 19px; }
p { margin: 0; line-height: 1.7; }
</style>
