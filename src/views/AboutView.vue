<script setup lang="ts">
import AboutPanel from '../components/help/AboutPanel.vue'
</script>

<template>
  <section class="help-page">
    <header class="help-hero">
      <div>
        <span class="eyebrow">文件名管理 · FILE NAME MANAGEMENT</span>
        <h1>关于文件名管理</h1>
        <p>为 Windows 多层目录提供清晰、高效且可撤回的文件名称管理体验：先看清变化，再决定是否执行。</p>
        <div class="product-tags" aria-label="产品标签">
          <span>文件名称管理</span><span>批量重命名</span><span>高效文件名管理</span><span>文件名管理工具</span>
        </div>
      </div>
      <div class="version-badge"><small>当前版本</small><strong>2.0.0 Alpha</strong></div>
    </header>
    <AboutPanel />
  </section>
</template>

<style scoped>
.help-page{height:100%;max-width:1180px;margin:auto;overflow:auto;padding:8px 8px 36px}.help-hero{display:flex;align-items:flex-end;justify-content:space-between;gap:24px;padding:28px 30px;border:1px solid var(--border);border-radius:var(--radius-large);background:linear-gradient(135deg,var(--surface),var(--primary-soft));box-shadow:var(--shadow)}.eyebrow{color:var(--primary);font-size:11px;font-weight:800;letter-spacing:.16em}h1{margin:8px 0 6px;font-size:30px;letter-spacing:-.03em}.help-hero p{max-width:720px;margin:0;color:var(--text-secondary);line-height:1.75}.version-badge{display:grid;gap:4px;min-width:160px;padding:14px 16px;border:1px solid color-mix(in srgb,var(--primary) 28%,var(--border));border-radius:var(--radius);background:var(--surface)}.version-badge small{color:var(--muted)}.version-badge strong{color:var(--primary)}
.product-tags{display:flex;flex-wrap:wrap;gap:7px;margin-top:14px}.product-tags span{padding:5px 9px;border:1px solid color-mix(in srgb,var(--primary) 22%,var(--border));border-radius:999px;color:var(--primary);background:var(--surface);font-size:12px;font-weight:650}
</style>
