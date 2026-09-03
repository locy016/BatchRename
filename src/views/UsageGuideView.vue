<script setup lang="ts">
import UsageGuide from '../components/help/UsageGuide.vue'
</script>

<template>
  <section class="help-page">
    <header class="help-hero">
      <span class="eyebrow">GUIDE</span>
      <h1>使用说明</h1>
      <p>从浏览目录到安全执行，按四个步骤完成一次可检查、可记录、可撤回的文件名管理任务。</p>
      <div class="hero-points">
        <span>先扫描</span>
        <span>再预览</span>
        <span>最后执行</span>
      </div>
    </header>
    <UsageGuide />
  </section>
</template>

<style scoped>
.help-page{height:100%;max-width:1180px;margin:auto;overflow:auto;padding:8px 8px 36px}.help-hero{padding:28px 30px;border:1px solid var(--border);border-radius:var(--radius-large);background:linear-gradient(135deg,var(--surface),var(--primary-soft));box-shadow:var(--shadow)}.eyebrow{color:var(--primary);font-size:11px;font-weight:800;letter-spacing:.16em}h1{margin:8px 0 6px;font-size:30px;letter-spacing:-.03em}.help-hero p{max-width:720px;margin:0;color:var(--text-secondary);line-height:1.75}.hero-points{display:flex;gap:8px;margin-top:18px}.hero-points span{padding:6px 10px;border:1px solid color-mix(in srgb,var(--primary) 28%,var(--border));border-radius:999px;color:var(--primary);background:var(--surface);font-size:12px;font-weight:700}
</style>
