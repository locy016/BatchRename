<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'

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
    </header>
    <main class="app-main">
      <RouterView />
    </main>
  </div>
</template>
