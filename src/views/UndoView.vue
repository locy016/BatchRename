<script setup lang="ts">
import { onMounted } from 'vue'
import OperationList from '../components/history/OperationList.vue'
import UndoCheckPanel from '../components/undo/UndoCheckPanel.vue'
import { useHistoryStore } from '../stores/history'
import { useUndoStore } from '../stores/undo'

const history = useHistoryStore()
const undo = useUndoStore()

async function executeAndRefresh() {
  await undo.execute()
  await history.load()
}

onMounted(() => history.load())
</script>

<template>
  <section class="undo">
    <header>
      <h1>撤回管理</h1>
      <p>先完成整批安全检查；任何一项有风险时都不会修改磁盘。</p>
    </header>
    <div class="undo-grid">
      <OperationList :items="history.items" :loading="history.loading" @select="undo.inspect" />
      <UndoCheckPanel
        :check="undo.check"
        :busy="undo.busy"
        @execute="executeAndRefresh"
      />
    </div>
  </section>
</template>

<style scoped>
.undo {
  height: 100%;
  display: grid;
  grid-template-rows: auto 1fr;
  gap: 16px;
}

h1,
p {
  margin: 0;
}

header p {
  margin-top: 7px;
  color: var(--muted);
}

.undo-grid {
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(280px, 35%) minmax(0, 65%);
  gap: 14px;
}

@media (max-width: 850px) {
  .undo-grid {
    grid-template-columns: 1fr;
    overflow: auto;
  }
}
</style>
