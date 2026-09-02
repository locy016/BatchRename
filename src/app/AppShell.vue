<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterLink, RouterView } from 'vue-router'
import { usePreferencesStore, type Appearance } from '../stores/preferences'
const preferences = usePreferencesStore()
onMounted(() => preferences.load())

const navigation = [
  { to: '/rename', label: '重命名' },
  { to: '/history', label: '操作日志' },
  { to: '/undo', label: '撤回管理' },
  { to: '/help', label: '帮助' },
]
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <div data-testid="product-title" class="product-title">批量重命名</div>
      <nav aria-label="主要功能">
        <RouterLink v-for="item in navigation" :key="item.to" :to="item.to">
          {{ item.label }}
        </RouterLink>
      </nav>
      <el-select class="theme-select" :model-value="preferences.appearance" aria-label="界面风格" @update:model-value="preferences.setAppearance($event as Appearance)"><el-option label="跟随系统" value="system"/><el-option label="浅色" value="light"/><el-option label="深色" value="dark"/></el-select>
    </header>
    <main class="app-main">
      <RouterView />
    </main>
  </div>
</template>
