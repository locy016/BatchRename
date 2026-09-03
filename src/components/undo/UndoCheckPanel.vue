<script setup lang="ts">
import { computed } from 'vue'
import type { UndoCheck } from '../../api/desktop'

const props = defineProps<{ check: UndoCheck | null; busy: boolean }>()
defineEmits(['execute'])

const alertType = computed(() => props.check?.state === '可撤回' ? 'success' : 'error')
</script>

<template>
  <section class="check" v-loading="busy">
    <el-empty v-if="!check" description="从左侧选择一条操作并进行安全检查" />

    <el-result
      v-else-if="check.state === '已撤回'"
      class="terminal-result"
      icon="success"
      title="撤回已经完成"
      :sub-title="check.summary"
    >
      <template #extra>
        <el-tag type="success" effect="light" round>原名称已恢复，无需再次操作</el-tag>
      </template>
    </el-result>

    <el-result
      v-else-if="check.state === '不可用'"
      class="terminal-result"
      icon="warning"
      title="无法进行撤回"
      :sub-title="check.summary"
    />

    <template v-else>
      <el-alert
        :type="alertType"
        :title="check.summary"
        :closable="false"
        show-icon
      />
      <div class="actions">
        <span>
          {{ check.state === '可撤回' ? `已检查 ${check.items.length} 项，全部安全` : `待处理 ${check.items.length} 项` }}
        </span>
        <el-button
          type="primary"
          :disabled="check.state !== '可撤回' || busy"
          @click="$emit('execute')"
        >
          确认整批撤回
        </el-button>
      </div>
      <el-table :data="check.items" height="390">
        <el-table-column label="安全" width="64">
          <template #default="scope">{{ scope.row.safe ? '✓' : '!' }}</template>
        </el-table-column>
        <el-table-column prop="currentSource" label="当前路径" show-overflow-tooltip />
        <el-table-column prop="restoreTarget" label="恢复为" show-overflow-tooltip />
        <el-table-column prop="detail" label="说明" show-overflow-tooltip />
      </el-table>
    </template>
  </section>
</template>

<style scoped>
.check {
  min-height: 0;
  padding: 18px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface);
}

.actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 0;
  color: var(--muted);
}

.terminal-result {
  min-height: 460px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}
</style>
