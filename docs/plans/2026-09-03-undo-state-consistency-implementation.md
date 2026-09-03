# Undo State Consistency Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让撤回完成后的界面提示、操作门禁与日志状态保持一致。

**Architecture:** 由 Rust 撤回服务产生单一、明确的检查状态，Vue 只负责按状态呈现。撤回页面在操作结束后统一刷新检查结果和日志摘要，避免多个界面区域读取不同时间点的数据。

**Tech Stack:** Rust、Serde、Tauri、Vue 3、Pinia、Element Plus、Vitest

---

### Task 1: 建立撤回检查状态契约

**Files:**
- Modify: `src-tauri/src/domain/models.rs`
- Modify: `src-tauri/src/services/undo.rs`
- Test: `src-tauri/tests/undo.rs`
- Modify: `src/api/desktop.ts`

1. 先添加序列化检查，证明已撤回记录当前没有明确状态且提示错误。
2. 运行撤回测试，确认测试按预期失败。
3. 增加撤回检查状态枚举，并让预检分别返回可撤回、存在风险、已撤回和不可用。
4. 使用状态作为执行门禁，删除含义重复的 `safe` 字段。
5. 运行撤回测试，确认全部通过。

### Task 2: 按状态呈现撤回结果

**Files:**
- Modify: `src/components/undo/UndoCheckPanel.vue`
- Create: `src/components/undo/UndoCheckPanel.spec.ts`

1. 先添加已撤回状态组件测试，要求显示成功反馈并隐藏空表格和执行按钮。
2. 运行测试，确认当前组件失败。
3. 根据状态计算提示类型和可执行性，单独呈现已完成与不可用状态。
4. 运行组件测试，确认通过。

### Task 3: 同步刷新页面状态

**Files:**
- Modify: `src/views/UndoView.vue`
- Modify: `src/views/UndoView.spec.ts`
- Modify: `src/stores/undo.ts`

1. 先添加撤回结束后刷新日志列表的页面测试。
2. 运行测试，确认当前页面没有刷新日志。
3. 让撤回操作使用 `try/finally` 恢复忙碌状态，并在成功后刷新检查和日志。
4. 运行页面测试及前端全部测试。

### Task 4: 完整验证与提交

1. 运行 Rust 格式、静态检查和全部测试。
2. 运行前端全部测试、类型检查、生产构建和端到端测试。
3. 构建 Windows 程序并核验 GUI 子系统。
4. 使用中文提交标题和详细正文记录根因、状态契约与验证范围，不执行推送。
