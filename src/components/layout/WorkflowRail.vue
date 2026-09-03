<script setup lang="ts">
import SearchRuleHint from '../rename/SearchRuleHint.vue'
import { useRenameStore } from '../../stores/rename'

defineEmits(['execute', 'templates', 'settings'])
const store = useRenameStore()
</script>

<template>
  <aside class="workflow">
    <ol>
      <li>
        <label>1　选择目录</label>
        <div class="action-row">
          <el-input :model-value="store.root" readonly placeholder="请选择需要整理的根目录" />
          <el-button @click="store.chooseRoot">选择</el-button>
        </div>
      </li>
      <li>
        <label>2　查找内容</label>
        <div class="action-row">
          <el-input
            :model-value="store.search"
            :placeholder="store.useRegex ? '输入正则表达式' : '例如：旧版'"
            @update:model-value="store.setSearch"
            @keyup.enter="store.canScan && store.scan()"
          >
            <template #suffix><SearchRuleHint /></template>
          </el-input>
          <el-button type="primary" :disabled="!store.canScan" @click="store.scan">扫描</el-button>
        </div>
      </li>
      <li>
        <label>3　替换与预览</label>
        <div data-testid="preview-row" class="action-row">
          <el-input
            :model-value="store.replacement"
            placeholder="可留空以删除匹配片段"
            @update:model-value="store.setReplacement"
            @keyup.enter="store.canPreview && store.preview()"
          />
          <el-button :disabled="!store.canPreview" @click="store.preview">预览</el-button>
        </div>
      </li>
      <li>
        <label>4　确认执行</label>
        <el-button
          class="wide"
          type="primary"
          :disabled="!store.canExecute"
          @click="$emit('execute')"
        >
          确认并执行 {{ store.summary.ready }} 项
        </el-button>
      </li>
    </ol>
    <div class="rail-tools">
      <el-button text @click="$emit('templates')">⌘ 正则模板</el-button>
      <el-button text @click="$emit('settings')">⚙ 设置</el-button>
    </div>
  </aside>
</template>

<style scoped>
.workflow {
  height: 100%;
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto;
  padding: 18px;
  border-right: 1px solid var(--border);
  background: var(--surface);
  overflow: hidden;
}

ol {
  display: grid;
  align-content: start;
  gap: 10px;
  margin: 0;
  padding: 0 4px 12px 0;
  list-style: none;
  overflow: auto;
}

li {
  display: grid;
  gap: 10px;
  padding: 14px;
  border-radius: var(--radius);
  background: var(--surface-soft);
}

label {
  font-size: 13px;
  font-weight: 700;
}

.action-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 64px;
  align-items: center;
  gap: 8px;
}

.action-row .el-button {
  width: 64px;
  margin: 0;
}

.wide {
  width: 100%;
}

.rail-tools {
  display: flex;
  justify-content: space-between;
  padding-top: 12px;
  border-top: 1px solid var(--border);
  background: var(--surface);
}
</style>
