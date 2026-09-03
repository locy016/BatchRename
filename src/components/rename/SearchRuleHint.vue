<script setup lang="ts">
import { InfoFilled } from '@element-plus/icons-vue'
import { computed } from 'vue'
import { useRenameStore } from '../../stores/rename'

const store = useRenameStore()
const mode = computed(() => store.useRegex ? '正则表达式' : '普通文本')
const query = computed(() => store.search || '尚未输入查找内容')
const scope = computed(() => {
  const values = []
  if (store.includeDirs) values.push('文件夹名称')
  if (store.includeFiles) values.push('文件名称')
  return values.length ? values.join('、') : '未选择扫描对象'
})
const depth = computed(() => store.maxDepth ? `${store.maxDepth} 层` : '全部子目录')
const extension = computed(() => store.renameExtension ? '允许修改扩展名' : '保护扩展名')
const example = computed(() => store.useRegex
  ? '示例：^(.+)_副本$ 可以匹配“报告_副本”'
  : '示例：输入“旧版”可以匹配“项目旧版.docx”')
const accessibleDescription = computed(() => [
  `当前模式：${mode.value}`,
  `查找内容：${query.value}`,
  example.value,
  `扫描对象：${scope.value}`,
  `扫描层级：${depth.value}`,
  `扩展名：${extension.value}`,
].join('；'))
</script>

<template>
  <el-popover placement="right" :width="340" trigger="hover" popper-class="search-rule-popover">
    <template #reference>
      <button
        type="button"
        class="hint-trigger"
        :aria-label="accessibleDescription"
        title="查看当前查找说明"
      >
        <el-icon><InfoFilled /></el-icon>
      </button>
    </template>
    <div class="hint-content">
      <header><strong>{{ mode }}</strong><span>{{ query }}</span></header>
      <p>{{ example }}</p>
      <dl>
        <div><dt>扫描对象</dt><dd>{{ scope }}</dd></div>
        <div><dt>扫描层级</dt><dd>{{ depth }}</dd></div>
        <div><dt>扩展名</dt><dd>{{ extension }}</dd></div>
      </dl>
    </div>
  </el-popover>
</template>

<style scoped>
.hint-trigger {
  display: inline-grid;
  width: 26px;
  height: 26px;
  padding: 0;
  place-items: center;
  border: 0;
  border-radius: 7px;
  color: var(--muted);
  background: transparent;
  cursor: help;
}

.hint-trigger:hover,
.hint-trigger:focus-visible {
  color: var(--primary);
  background: var(--primary-soft);
  outline: none;
}

.hint-content {
  display: grid;
  gap: 12px;
}

.hint-content header {
  display: grid;
  gap: 4px;
}

.hint-content header span,
.hint-content p,
dt {
  color: var(--muted);
}

.hint-content p,
.hint-content dl {
  margin: 0;
}

.hint-content p {
  padding: 10px;
  border-radius: 8px;
  background: var(--surface-soft);
  line-height: 1.6;
}

.hint-content dl {
  display: grid;
  gap: 8px;
}

.hint-content dl div {
  display: grid;
  grid-template-columns: 72px 1fr;
  gap: 10px;
}

.hint-content dd {
  margin: 0;
  color: var(--text);
}
</style>
