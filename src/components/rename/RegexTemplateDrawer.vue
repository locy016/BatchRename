<script setup lang="ts">
import { regexTemplates } from '../../data/regexTemplates'
import { useRenameStore } from '../../stores/rename'

defineProps<{ modelValue: boolean }>()
const emit = defineEmits(['update:modelValue'])
const store = useRenameStore()

function setRegexMode(value: boolean) {
  if (store.useRegex === value) return
  store.useRegex = value
  store.invalidateScan()
}

function apply(template: typeof regexTemplates[number]) {
  store.useRegex = true
  store.setSearch(template.search)
  store.setReplacement(template.replacement)
  store.renameExtension = template.renameExtension
  emit('update:modelValue', false)
}
</script>

<template>
  <el-drawer
    :model-value="modelValue"
    title="正则模板"
    :size="460"
    class="regex-drawer"
    @close="$emit('update:modelValue', false)"
  >
    <section class="mode-card">
      <div><strong>使用正则表达式</strong><p>开启后，查找内容将按正则语法解释。</p></div>
      <el-switch
        :model-value="store.useRegex"
        inline-prompt
        active-text="开启"
        inactive-text="关闭"
        @update:model-value="setRegexMode"
      />
    </section>
    <div class="intro">
      <strong>从用途开始选择</strong>
      <p>无需记忆表达式。对照处理前后的示例，选择符合目的的模板即可填入。</p>
    </div>
    <div class="templates">
      <article v-for="template in regexTemplates" :key="template.title">
        <div class="template-head"><small>{{ template.category }}</small><h3>{{ template.title }}</h3></div>
        <p>{{ template.purpose }}</p>
        <code><span>{{ template.before }}</span><b>→</b><span>{{ template.after }}</span></code>
        <el-button type="primary" plain @click="apply(template)">应用模板</el-button>
      </article>
    </div>
  </el-drawer>
</template>

<style scoped>
.mode-card,
.intro,
article {
  padding: 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
}

.mode-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  background: var(--surface);
}

.mode-card p,
.intro p {
  margin: 5px 0 0;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.7;
}

.intro {
  margin-top: 12px;
  background: var(--primary-soft);
}

.templates {
  display: grid;
  gap: 12px;
  margin-top: 14px;
}

article {
  display: grid;
  gap: 10px;
  background: var(--surface);
}

h3,
article > p {
  margin: 0;
}

.template-head {
  display: flex;
  align-items: center;
  gap: 10px;
}

.template-head h3 {
  font-size: 14px;
}

.template-head small {
  padding: 3px 7px;
  border-radius: 999px;
  color: var(--primary);
  background: var(--primary-soft);
}

article > p {
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.6;
}

code {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  gap: 8px;
  padding: 10px;
  border-radius: 8px;
  color: var(--text-secondary);
  background: var(--surface-soft);
  overflow: hidden;
}

code span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

code b {
  color: var(--primary);
}

article .el-button {
  justify-self: end;
}
</style>
