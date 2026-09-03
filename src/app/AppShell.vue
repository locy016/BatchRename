<script setup lang="ts">
import { ArrowDown } from '@element-plus/icons-vue'
import { computed, onMounted } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { usePreferencesStore, type Appearance } from '../stores/preferences'

const preferences = usePreferencesStore()
const route = useRoute()
const router = useRouter()
const helpActive = computed(() => route.path.startsWith('/help'))

const navigation = [
  { to: '/rename', label: '文件名管理' },
  { to: '/history', label: '操作日志' },
]

onMounted(() => preferences.load())

function openHelp(path: string) {
  void router.push(path)
}
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <nav aria-label="主要功能">
        <RouterLink v-for="item in navigation" :key="item.to" :to="item.to">
          {{ item.label }}
        </RouterLink>
        <el-dropdown trigger="click" popper-class="help-navigation" @command="openHelp">
          <button
            data-testid="help-menu"
            type="button"
            class="menu-trigger"
            :class="{ active: helpActive }"
            aria-haspopup="menu"
          >
            帮助
            <el-icon><ArrowDown /></el-icon>
          </button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="/help/guide">使用说明</el-dropdown-item>
              <el-dropdown-item command="/help/about">关于</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </nav>
      <el-select
        class="theme-select"
        :model-value="preferences.appearance"
        aria-label="界面风格"
        @update:model-value="preferences.setAppearance($event as Appearance)"
      >
        <el-option label="跟随系统" value="system" />
        <el-option label="浅色" value="light" />
        <el-option label="深色" value="dark" />
      </el-select>
    </header>
    <main class="app-main">
      <RouterView />
    </main>
  </div>
</template>
