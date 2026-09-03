<script setup lang="ts">
import { computed } from 'vue'
import { useRenameStore } from '../../stores/rename'

defineProps<{ modelValue: boolean }>()
defineEmits(['update:modelValue'])

const store = useRenameStore()
const depth = computed({
  get: () => store.maxDepth ?? 0,
  set: (value: number | undefined) => store.setMaxDepth(value ?? 0),
})
const previewLimit = computed({
  get: () => store.previewLimit,
  set: (value: number | undefined) => store.setPreviewLimit(value),
})
</script>

<template>
  <el-drawer
    :model-value="modelValue"
    title="扫描与命名设置"
    :size="420"
    class="settings-drawer"
    @close="$emit('update:modelValue', false)"
  >
    <div class="drawer-intro">
      <strong>控制扫描边界</strong>
      <p>这里的选项只决定扫描范围和文件名保护方式，不会直接修改任何内容。</p>
    </div>

    <section class="setting-card">
      <div class="section-title">
        <div>
          <h3>扫描对象</h3>
          <p>选择要在结果中包含的名称类型。</p>
        </div>
      </div>
      <div class="choice-grid">
        <el-checkbox v-model="store.includeDirs" border @change="store.invalidateScan">
          文件夹名称
        </el-checkbox>
        <el-checkbox v-model="store.includeFiles" border @change="store.invalidateScan">
          文件名称
        </el-checkbox>
      </div>
    </section>

    <section class="setting-card">
      <div class="section-title">
        <div>
          <h3>结果显示</h3>
          <p>只控制表格显示条数；完整统计和最终执行范围不会改变。</p>
        </div>
        <el-input-number v-model="previewLimit" :min="1" :max="100" controls-position="right" />
      </div>
    </section>

    <section class="setting-card">
      <div class="section-title">
        <div>
          <h3>扫描层级</h3>
          <p>0 表示扫描全部子目录；1 只查看根目录中的项目。</p>
        </div>
        <el-input-number v-model="depth" :min="0" :max="99" controls-position="right" />
      </div>
    </section>

    <section class="setting-card">
      <div class="section-title">
        <div>
          <h3>扩展名保护</h3>
          <p>建议保持开启，避免无意改变文件类型。</p>
        </div>
        <el-switch
          :model-value="!store.renameExtension"
          inline-prompt
          active-text="保护"
          inactive-text="允许"
          @update:model-value="store.renameExtension = !$event; store.invalidatePreview()"
        />
      </div>
    </section>

    <div class="setting-note">
      根目录本身不会被重命名。设置变化后，已有扫描结果会自动失效，避免使用过期结果执行。
    </div>
  </el-drawer>
</template>

<style scoped>
.drawer-intro,
.setting-card,
.setting-note {
  border: 1px solid var(--border);
  border-radius: var(--radius);
}

.drawer-intro {
  padding: 16px;
  background: var(--primary-soft);
}

.drawer-intro p,
.section-title p {
  margin: 5px 0 0;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.65;
}

.setting-card {
  margin-top: 14px;
  padding: 16px;
  background: var(--surface);
}

.section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
}

h3 {
  margin: 0;
  font-size: 14px;
}

.choice-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-top: 14px;
}

.choice-grid .el-checkbox {
  width: 100%;
  margin: 0;
}

.setting-note {
  margin-top: 14px;
  padding: 14px 16px;
  color: var(--muted);
  background: var(--surface-soft);
  font-size: 12px;
  line-height: 1.7;
}
</style>
