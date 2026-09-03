<script setup lang="ts">
import { computed } from 'vue'
import type { UndoCheck } from '../../api/desktop'
import type { OperationLogV1 } from '../../types/contracts'

const props = defineProps<{
  operation: OperationLogV1 | null
  undoCheck: UndoCheck | null
  busy: boolean
  undoError: string
}>()
defineEmits(['undo'])

const undoAlertType = computed(() => {
  if (props.undoCheck?.state === '可撤回' || props.undoCheck?.state === '已撤回') return 'success'
  if (props.undoCheck?.state === '存在风险') return 'warning'
  return 'error'
})
</script>

<template>
  <aside class="detail" v-loading="busy">
    <el-empty v-if="!operation" description="选择一条日志查看详情和撤回状态" />
    <template v-else>
      <div class="detail-heading">
        <div>
          <el-tag effect="light">{{ operation.status }}</el-tag>
          <h2>{{ operation.search || '未记录查找规则' }} → {{ operation.replacement || '删除匹配内容' }}</h2>
          <p :title="operation.root">{{ operation.root }}</p>
        </div>
        <time>{{ operation.updated_at }}</time>
      </div>

      <dl>
        <div><dt>查找方式</dt><dd>{{ operation.use_regex ? '正则表达式' : '普通文本' }}</dd></div>
        <div><dt>处理范围</dt><dd>{{ operation.include_dirs ? '文件夹' : '' }}{{ operation.include_dirs && operation.include_files ? '、' : '' }}{{ operation.include_files ? '文件' : '' }}</dd></div>
        <div><dt>扫描层级</dt><dd>{{ operation.max_depth === null ? '全部层级' : `${operation.max_depth} 层` }}</dd></div>
      </dl>

      <div class="items-table">
        <el-table :data="operation.items" height="100%" empty-text="此记录没有项目明细">
          <el-table-column prop="kind" label="类型" width="68" />
          <el-table-column prop="source" label="原路径" min-width="190" show-overflow-tooltip />
          <el-table-column prop="target" label="处理后" min-width="190" show-overflow-tooltip />
          <el-table-column prop="outcome" label="执行" width="68" />
          <el-table-column prop="undo_status" label="撤回" width="86" />
        </el-table>
      </div>

      <section class="undo-card">
        <div class="undo-heading">
          <div><h3>撤回操作</h3><p>恢复本批次中已成功处理的文件夹和文件名称。</p></div>
          <el-button
            v-if="undoCheck?.state === '可撤回'"
            data-testid="execute-undo"
            type="primary"
            :loading="busy"
            @click="$emit('undo')"
          >确认整批撤回</el-button>
        </div>

        <el-alert
          v-if="undoError"
          type="error"
          :title="undoError"
          :closable="false"
          show-icon
        />
        <el-alert
          v-else-if="undoCheck"
          :type="undoAlertType"
          :title="undoCheck.summary"
          :closable="false"
          show-icon
        />
        <p v-else class="checking">正在读取撤回安全状态…</p>

        <el-table
          v-if="undoCheck?.items.length"
          :data="undoCheck.items"
          max-height="170"
          class="undo-items"
        >
          <el-table-column label="安全" width="58" align="center">
            <template #default="scope">{{ scope.row.safe ? '✓' : '!' }}</template>
          </el-table-column>
          <el-table-column prop="currentSource" label="当前路径" show-overflow-tooltip />
          <el-table-column prop="restoreTarget" label="恢复为" show-overflow-tooltip />
          <el-table-column prop="detail" label="说明" show-overflow-tooltip />
        </el-table>
      </section>
    </template>
  </aside>
</template>

<style scoped>
.detail {
  min-width: 0;
  min-height: 0;
  display: grid;
  grid-template-rows: auto auto minmax(170px, 1fr) auto;
  gap: 14px;
  padding: 18px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface);
  overflow: auto;
}

.detail-heading,
.undo-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
}

.detail-heading > div {
  min-width: 0;
}

.detail-heading h2 {
  margin: 10px 0 5px;
  font-size: 18px;
}

.detail-heading p,
.undo-heading p,
.checking {
  margin: 0;
  color: var(--muted);
}

.detail-heading p {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

time {
  flex: none;
  color: var(--muted);
  font-size: 12px;
}

dl {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin: 0;
}

dl div {
  padding: 10px 12px;
  border-radius: 9px;
  background: var(--surface-soft);
}

dt {
  color: var(--muted);
  font-size: 12px;
}

dd {
  margin: 5px 0 0;
  color: var(--text);
  font-weight: 650;
}

.items-table {
  min-height: 170px;
  overflow: hidden;
}

.undo-card {
  display: grid;
  gap: 12px;
  padding: 15px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface-soft);
}

.undo-heading {
  align-items: center;
}

.undo-heading h3 {
  margin: 0 0 5px;
  font-size: 15px;
}

.undo-heading p,
.checking {
  font-size: 12px;
}

.undo-items {
  border-radius: 9px;
}

@media (max-width: 980px) {
  dl {
    grid-template-columns: 1fr;
  }

  time {
    display: none;
  }
}
</style>
