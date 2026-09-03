<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useHistoryStore } from '../stores/history'
import OperationFilters from '../components/history/OperationFilters.vue'
import OperationList from '../components/history/OperationList.vue'
import OperationDetails from '../components/history/OperationDetails.vue'
import UndoConfirmation from '../components/history/UndoConfirmation.vue'
import UndoProgressDialog from '../components/history/UndoProgressDialog.vue'
import UndoResultDialog from '../components/history/UndoResultDialog.vue'

const store = useHistoryStore()
const query = ref('')
const status = ref('')
const undoConfirming = ref(false)
const undoCompleted = ref(false)
const load = () => store.load(query.value, status.value || null)

async function executeUndo() {
  undoConfirming.value = false
  if (await store.executeUndo()) undoCompleted.value = true
}

onMounted(load)
</script>

<template>
  <section class="history">
    <header>
      <div>
        <h1>操作日志</h1>
        <p>查看每次文件名处理记录，并在同一页面完成安全检查与整批撤回。</p>
      </div>
      <OperationFilters
        v-model:query="query"
        v-model:status="status"
        @search="load"
      />
    </header>
    <el-alert
      v-if="store.errorMessage"
      type="error"
      :title="store.errorMessage"
      :closable="false"
      show-icon
    />
    <div class="history-grid">
      <OperationList
        :items="store.items"
        :loading="store.loading"
        @select="store.select"
      />
      <OperationDetails
        :operation="store.selected"
        :undo-check="store.undoCheck"
        :busy="store.selectionBusy || store.undoBusy"
        :undo-error="store.undoError"
        @undo="undoConfirming = true"
      />
    </div>
    <UndoConfirmation
      v-model="undoConfirming"
      :root="store.selected?.root ?? ''"
      :total="store.undoCheck?.items.length ?? 0"
      @confirm="executeUndo"
    />
    <UndoProgressDialog :model-value="store.undoBusy" :progress="store.undoProgress" />
    <UndoResultDialog v-model="undoCompleted" :summary="store.undoSummary" />
  </section>
</template>

<style scoped>
.history {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.history header {
  display: grid;
  grid-template-columns: 1fr minmax(400px, 55%);
  align-items: end;
  gap: 20px;
}

h1,
p {
  margin: 0;
}

header p {
  margin-top: 7px;
  color: var(--muted);
}

.history-grid {
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(280px, 34%) minmax(0, 66%);
  flex: 1 1 auto;
  gap: 14px;
}

@media (max-width: 850px) {
  .history header,
  .history-grid {
    grid-template-columns: 1fr;
  }

  .history-grid {
    overflow: auto;
  }
}
</style>
