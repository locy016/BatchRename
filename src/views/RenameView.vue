<script setup lang="ts">
import { ref } from 'vue'
import { useRenameStore } from '../stores/rename'
import WorkflowRail from '../components/layout/WorkflowRail.vue'
import DirectoryOverview from '../components/rename/DirectoryOverview.vue'
import ResultTable from '../components/rename/ResultTable.vue'
import MatchStatistics from '../components/rename/MatchStatistics.vue'
import ProgressStatus from '../components/rename/ProgressStatus.vue'
import ResultDetails from '../components/rename/ResultDetails.vue'
import RegexTemplateDrawer from '../components/rename/RegexTemplateDrawer.vue'
import SettingsDrawer from '../components/rename/SettingsDrawer.vue'
import ExecuteConfirmation from '../components/rename/ExecuteConfirmation.vue'
import ExecutionDetails from '../components/rename/ExecutionDetails.vue'
import ExecutionProgressDialog from '../components/rename/ExecutionProgressDialog.vue'

const store = useRenameStore()
const detail = ref<any>(null)
const detailsOpen = ref(false)
const templates = ref(false)
const settings = ref(false)
const confirming = ref(false)
const completed = ref(false)

function show(item: any) {
  detail.value = item
  detailsOpen.value = true
}

function openTemplates() {
  settings.value = false
  templates.value = true
}

function openSettings() {
  templates.value = false
  settings.value = true
}

async function execute() {
  confirming.value = false
  const succeeded = await store.execute()
  if (succeeded) completed.value = true
}
</script>

<template>
  <div class="rename-workspace">
    <WorkflowRail
      @execute="confirming = true"
      @templates="openTemplates"
      @settings="openSettings"
    />
    <main class="results">
      <DirectoryOverview
        :root="store.root"
        :directories="store.overview.directories"
        :files="store.overview.files"
        :loading="store.overviewBusy"
      />
      <ProgressStatus />
      <section class="table-card">
        <ResultTable @details="show" />
        <MatchStatistics />
      </section>
    </main>
    <ResultDetails v-model="detailsOpen" :item="detail" />
    <RegexTemplateDrawer v-model="templates" />
    <SettingsDrawer v-model="settings" />
    <ExecuteConfirmation v-model="confirming" @confirm="execute" />
    <ExecutionProgressDialog
      :model-value="store.busy === 'executing'"
      :progress="store.executionProgress"
    />
    <ExecutionDetails v-model="completed" :operation-id="store.lastOperationId" />
  </div>
</template>

<style scoped>
.rename-workspace {
  display: grid;
  grid-template-columns: minmax(292px, 30%) minmax(0, 70%);
  height: calc(100vh - 56px);
  min-height: 0;
  margin: -20px;
  overflow: hidden;
}

.results {
  display: grid;
  grid-template-rows: auto auto minmax(0, 1fr);
  gap: 12px;
  min-width: 0;
  min-height: 0;
  padding: 18px;
  overflow: hidden;
}

.table-card {
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto;
  min-height: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface);
  overflow: hidden;
}

@media (max-width: 820px) {
  .rename-workspace {
    grid-template-columns: 1fr;
  }

  .rename-workspace > :first-child {
    display: none;
  }
}
</style>
