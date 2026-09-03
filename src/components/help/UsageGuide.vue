<template>
  <div class="guide-content">
    <section class="content-section">
      <div class="section-heading">
        <span>01</span>
        <div><h2>快速开始</h2><p>日常文本替换只需要四步，高级选项按需打开。</p></div>
      </div>
      <div class="step-grid">
        <article><b>1</b><h3>选择目录</h3><p>目录选定后会立即统计范围，并列出根目录中的文件夹和文件。</p></article>
        <article><b>2</b><h3>查找并扫描</h3><p>输入名称片段后点击扫描，或直接按回车。</p></article>
        <article><b>3</b><h3>替换并预览</h3><p>输入新内容后按回车，逐项核对新名称和状态。</p></article>
        <article><b>4</b><h3>确认执行</h3><p>只有安全预览中的可修改项目会进入确认环节。</p></article>
      </div>
    </section>

    <div class="two-column">
      <section class="content-section">
        <div class="section-heading"><span>02</span><div><h2>查找方式</h2><p>从简单文本开始，需要时再使用正则。</p></div></div>
        <div class="info-list">
          <article><h3>普通文本</h3><p>适合替换固定词语、编号前缀或重复标记；查找框后的提示图标会说明当前规则与范围。</p></article>
          <article><h3>正则模板</h3><p>从左下角打开模板窗口，可开启正则模式并按处理前后示例一键应用，无需记忆表达式。</p></article>
          <article><h3>扫描设置</h3><p>在设置中选择文件夹、文件、扫描层级和扩展名保护。</p></article>
        </div>
      </section>

      <section class="content-section">
        <div class="section-heading"><span>03</span><div><h2>结果状态</h2><p>执行前先理解每种状态代表的含义。</p></div></div>
        <dl class="status-list">
          <div><dt class="ready">可修改</dt><dd>目标名称有效且没有冲突。</dd></div>
          <div><dt>已匹配</dt><dd>符合查找规则，等待生成预览。</dd></div>
          <div><dt>名称未变化</dt><dd>替换后与原名称相同，不执行动作。</dd></div>
          <div><dt class="warning">冲突或阻止</dt><dd>目标已存在、批内重复或名称不合法。</dd></div>
        </dl>
      </section>
    </div>

    <section class="content-section keyboard-section">
      <div class="section-heading"><span>04</span><div><h2>键盘操作</h2><p>减少鼠标往返，但不跳过安全确认。</p></div></div>
      <div class="shortcut-grid">
        <div><kbd>Enter</kbd><span>在查找框中开始扫描</span></div>
        <div><kbd>Enter</kbd><span>在替换框中生成预览</span></div>
        <div><kbd>Esc</kbd><span>关闭当前抽屉或弹窗</span></div>
      </div>
    </section>

    <section class="safety-panel">
      <div><strong>安全边界</strong><p>预览不会修改磁盘。确认执行时仍会重新检查来源和目标；目录被其他程序改动时，对应项目会安全跳过并写入操作日志。</p></div>
      <div><strong>需要恢复？</strong><p>进入撤回管理，整批撤回前会先检查每个目标，再决定是否恢复。重要资料仍建议保留独立备份。</p></div>
    </section>
  </div>
</template>

<style scoped>
.guide-content{display:grid;gap:16px;margin-top:16px}.content-section,.safety-panel{padding:22px;border:1px solid var(--border);border-radius:var(--radius-large);background:var(--surface)}.section-heading{display:flex;gap:12px;align-items:flex-start}.section-heading>span{display:grid;width:34px;height:34px;place-items:center;border-radius:10px;color:var(--primary);background:var(--primary-soft);font-size:12px;font-weight:800}.section-heading h2,.section-heading p,h3{margin:0}.section-heading h2{font-size:17px}.section-heading p{margin-top:4px;color:var(--muted);font-size:13px}.step-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:18px}.step-grid article,.info-list article{padding:15px;border:1px solid var(--border);border-radius:var(--radius);background:var(--surface-soft)}.step-grid b{color:var(--primary);font-size:12px}.step-grid h3,.info-list h3{margin-top:8px;font-size:14px}.step-grid p,.info-list p{margin:6px 0 0;color:var(--text-secondary);font-size:12px;line-height:1.7}.two-column{display:grid;grid-template-columns:1fr 1fr;gap:16px}.info-list{display:grid;gap:9px;margin-top:17px}.status-list{display:grid;gap:1px;margin:17px 0 0}.status-list div{display:grid;grid-template-columns:105px 1fr;gap:10px;padding:11px 0;border-bottom:1px solid var(--border)}.status-list div:last-child{border-bottom:0}.status-list dt{color:var(--muted);font-weight:700}.status-list dt.ready{color:var(--success)}.status-list dt.warning{color:var(--warning)}.status-list dd{margin:0;color:var(--text-secondary);font-size:13px}.shortcut-grid{display:flex;gap:12px;margin-top:18px}.shortcut-grid div{display:flex;align-items:center;gap:10px;padding:10px 12px;border:1px solid var(--border);border-radius:10px;background:var(--surface-soft);color:var(--text-secondary);font-size:13px}kbd{min-width:48px;padding:4px 7px;border:1px solid var(--border-strong);border-radius:6px;background:var(--surface);color:var(--text);font-family:inherit;text-align:center;box-shadow:0 2px 0 var(--border)}.safety-panel{display:grid;grid-template-columns:1fr 1fr;gap:24px;background:var(--primary-soft)}.safety-panel p{margin:7px 0 0;color:var(--text-secondary);font-size:13px;line-height:1.75}@media(max-width:900px){.step-grid{grid-template-columns:1fr 1fr}.two-column,.safety-panel{grid-template-columns:1fr}.shortcut-grid{display:grid}}
</style>
