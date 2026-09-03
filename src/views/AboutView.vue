<script setup lang="ts">
import AboutPanel from '../components/help/AboutPanel.vue'
</script>

<template>
  <section class="help-page">
    <header class="help-hero">
      <div>
        <span class="eyebrow">BATCHRENAME</span>
        <h1>关于</h1>
        <p>专注于 Windows 多层目录的安全名称整理：先看清变化，再决定是否执行。</p>
      </div>
      <div class="version-badge"><small>当前版本</small><strong>2.0.0 Alpha</strong></div>
    </header>
    <AboutPanel />
  </section>
</template>

<style scoped>
.help-page{height:100%;max-width:1180px;margin:auto;overflow:auto;padding:8px 8px 36px}.help-hero{display:flex;align-items:flex-end;justify-content:space-between;gap:24px;padding:28px 30px;border:1px solid var(--border);border-radius:var(--radius-large);background:linear-gradient(135deg,var(--surface),var(--primary-soft));box-shadow:var(--shadow)}.eyebrow{color:var(--primary);font-size:11px;font-weight:800;letter-spacing:.16em}h1{margin:8px 0 6px;font-size:30px;letter-spacing:-.03em}.help-hero p{max-width:720px;margin:0;color:var(--text-secondary);line-height:1.75}.version-badge{display:grid;gap:4px;min-width:160px;padding:14px 16px;border:1px solid color-mix(in srgb,var(--primary) 28%,var(--border));border-radius:var(--radius);background:var(--surface)}.version-badge small{color:var(--muted)}.version-badge strong{color:var(--primary)}
</style>
