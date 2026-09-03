<script setup lang="ts">
import {
  CircleCheckFilled,
  Document,
  Folder,
  InfoFilled,
  RemoveFilled,
  Search,
  WarningFilled,
} from '@element-plus/icons-vue'
import { computed } from 'vue'
import { useRenameStore } from '../../stores/rename'
import { createResultRows } from './resultRows'

const emit = defineEmits(['details'])
const store = useRenameStore()
const rows = computed(() => createResultRows(store.items, store.root))

function statusIcon(status: string) {
  if (status === '可修改') return CircleCheckFilled
  if (status === '名称未变化') return RemoveFilled
  if (status === '已匹配') return Search
  return WarningFilled
}

function statusClass(status: string) {
  if (status === '可修改') return 'is-ready'
  if (status === '名称未变化' || status === '已匹配') return 'is-neutral'
  return 'is-warning'
}
</script>

<template>
  <el-table
    :data="rows"
    height="100%"
    empty-text="输入查找内容并扫描后，匹配结果会显示在这里"
  >
    <el-table-column label="类型" width="58" align="center">
      <template #default="scope">
        <el-tooltip :content="scope.row.kind" :show-after="250">
          <el-icon class="type-icon" :aria-label="scope.row.kind">
            <Folder v-if="scope.row.kind === '文件夹'" />
            <Document v-else />
          </el-icon>
        </el-tooltip>
      </template>
    </el-table-column>

    <el-table-column label="所在目录" width="76" align="center">
      <template #default="scope">
        <span
          v-if="scope.row.directory.isRoot"
          data-testid="root-directory"
          class="root-directory"
          aria-label="根目录"
        >.</span>
        <el-tooltip v-else :content="scope.row.directory.path" placement="top" :show-after="180">
          <span
            data-testid="nested-directory"
            class="directory-icon"
            :aria-label="scope.row.directory.accessibleLabel"
            :data-directory-path="scope.row.directory.path"
            tabindex="0"
          >
            <el-icon><Folder /></el-icon>
          </span>
        </el-tooltip>
      </template>
    </el-table-column>

    <el-table-column prop="oldName" label="原名称" min-width="180" show-overflow-tooltip />
    <el-table-column label="新名称" min-width="200" show-overflow-tooltip>
      <template #default="scope">
        <span class="new-name">{{ scope.row.newName }}</span>
      </template>
    </el-table-column>

    <el-table-column label="状态" width="64" align="center">
      <template #default="scope">
        <el-tooltip :content="scope.row.status" :show-after="250">
          <el-icon class="status-icon" :class="statusClass(scope.row.status)" :aria-label="scope.row.status">
            <component :is="statusIcon(scope.row.status)" />
          </el-icon>
        </el-tooltip>
      </template>
    </el-table-column>

    <el-table-column label="说明" width="64" align="center">
      <template #default="scope">
        <el-tooltip :content="scope.row.detail" :show-after="250">
          <el-button text circle aria-label="查看说明" @click="emit('details', scope.row)">
            <el-icon><InfoFilled /></el-icon>
          </el-button>
        </el-tooltip>
      </template>
    </el-table-column>
  </el-table>
</template>

<style scoped>
.type-icon,
.status-icon {
  font-size: 17px;
}

.type-icon,
.root-directory,
.directory-icon,
.is-neutral {
  color: var(--muted);
}

.directory-icon {
  display: inline-grid;
  width: 28px;
  height: 28px;
  place-items: center;
  border-radius: 8px;
  background: var(--surface-soft);
  cursor: help;
}

.directory-icon:focus-visible {
  outline: 2px solid var(--primary);
  outline-offset: 2px;
}

.new-name,
.is-ready {
  color: var(--primary);
  font-weight: 700;
}

.is-warning {
  color: var(--warning);
}
</style>
