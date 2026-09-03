<template>
  <div class="about-content">
    <section class="content-section">
      <div class="section-heading"><span>NOW</span><div><h2>当前能力</h2><p>围绕一次可靠的名称整理任务提供完整闭环。</p></div></div>
      <div class="capability-grid">
        <article><h3>灵活匹配</h3><p>普通文本、经典正则模板、多层目录和独立文件类型范围。</p></article>
        <article><h3>安全预览</h3><p>名称变化、冲突、非法名称和无变化项目逐项可见。</p></article>
        <article><h3>本机执行</h3><p>处理过程不上传目录内容，执行前再次检查磁盘状态。</p></article>
        <article><h3>操作日志与撤回</h3><p>记录每个结果，并在恢复前完成整批安全检查。</p></article>
      </div>
    </section>

    <section class="content-section roadmap">
      <div class="section-heading"><span>NEXT</span><div><h2>后续方向</h2><p>快速开发期将继续围绕可靠性和大目录体验收敛。</p></div></div>
      <ul><li>提升超大目录扫描和结果分页体验。</li><li>补强日志筛选、撤回说明和异常恢复引导。</li><li>完善正式发行前的签名、升级与兼容验证。</li></ul>
    </section>

    <div class="details-grid">
      <section class="content-section">
        <h2>版本信息</h2>
        <dl><div><dt>产品</dt><dd>BatchRename 批量重命名</dd></div><div><dt>版本</dt><dd>2.0.0 Alpha</dd></div><div><dt>平台</dt><dd>Windows 10 / 11</dd></div></dl>
      </section>
      <section class="content-section">
        <h2>数据位置</h2>
        <p>设置与操作日志保存在本机用户数据目录：</p>
        <code>%LOCALAPPDATA%\BatchRename</code>
        <p>目录名称和文件名称不会上传到远程服务。</p>
      </section>
      <section class="content-section contact-card">
        <h2>联系作者</h2>
        <p>欢迎反馈可复现的问题、使用场景和产品建议。</p>
        <a href="mailto:lo.c@live.cn">lo.c@live.cn</a>
      </section>
    </div>

    <section class="disclaimer">
      <strong>免责声明</strong>
      <p>软件处于快速开发期，并按现状提供。请在处理重要资料前保留独立备份；因权限、硬件故障、其他程序并发修改或特殊文件系统行为造成的结果，由使用者自行评估和承担。</p>
    </section>
  </div>
</template>

<style scoped>
.about-content{display:grid;gap:16px;margin-top:16px}.content-section,.disclaimer{padding:22px;border:1px solid var(--border);border-radius:var(--radius-large);background:var(--surface)}.section-heading{display:flex;gap:12px;align-items:flex-start}.section-heading>span{display:grid;min-width:42px;height:34px;padding:0 8px;place-items:center;border-radius:10px;color:var(--primary);background:var(--primary-soft);font-size:10px;font-weight:800;letter-spacing:.08em}.section-heading h2,.section-heading p,h3{margin:0}.section-heading h2,.content-section>h2{font-size:17px}.section-heading p{margin-top:4px;color:var(--muted);font-size:13px}.capability-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:18px}.capability-grid article{padding:16px;border:1px solid var(--border);border-radius:var(--radius);background:var(--surface-soft)}.capability-grid h3{font-size:14px}.capability-grid p,.content-section>p,.disclaimer p{margin:7px 0 0;color:var(--text-secondary);font-size:13px;line-height:1.75}.roadmap ul{display:grid;gap:9px;margin:18px 0 0;padding-left:20px;color:var(--text-secondary);font-size:13px;line-height:1.65}.details-grid{display:grid;grid-template-columns:1fr 1.15fr .85fr;gap:16px}.content-section>h2{margin:0}dl{display:grid;gap:10px;margin:16px 0 0}dl div{display:flex;justify-content:space-between;gap:18px;padding-bottom:9px;border-bottom:1px solid var(--border)}dt{color:var(--muted)}dd{margin:0;color:var(--text);font-weight:650}code{display:block;margin:13px 0;padding:10px 12px;border-radius:8px;background:var(--surface-soft);color:var(--primary);overflow:hidden;text-overflow:ellipsis}.contact-card{background:var(--primary-soft)}.contact-card a{display:inline-block;margin-top:15px;color:var(--primary);font-size:16px;font-weight:750;text-decoration:none}.disclaimer{background:var(--warning-soft)}.disclaimer strong{color:var(--warning)}@media(max-width:900px){.capability-grid{grid-template-columns:1fr 1fr}.details-grid{grid-template-columns:1fr}}
</style>
