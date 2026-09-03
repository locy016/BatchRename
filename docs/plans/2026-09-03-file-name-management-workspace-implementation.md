# File Name Management Workspace Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将工作台升级为选择目录即可浏览、规则说明清晰、列表自适应且执行过程可感知的“文件名管理”产品。

**Architecture:** Rust 增加独立的根目录第一层读取契约；Pinia 使用明确的结果模式组织目录内容、匹配结果和安全预览；Vue 组件分别负责流程、上下文说明、表格和执行反馈。保留现有数据目录与日志格式。

**Tech Stack:** Rust、Tauri 2、Vue 3、Pinia、Element Plus、Vitest、Playwright

---

### Task 1: 根目录内容读取

**Files:**
- Modify: `src-tauri/src/domain/models.rs`
- Modify: `src-tauri/src/services/scanner.rs`
- Modify: `src-tauri/src/commands/scan.rs`
- Modify: `src-tauri/src/lib.rs`
- Test: `src-tauri/tests/scanner.rs`
- Modify: `src/api/desktop.ts`

1. 添加失败测试，要求只读取根目录第一层、文件夹优先自然排序并返回总数。
2. 运行测试确认失败。
3. 实现 `list_root_items` 服务和 Tauri 命令，限制返回前 100 项。
4. 运行扫描测试确认通过并提交。

### Task 2: 三态列表状态机

**Files:**
- Modify: `src/stores/rename.ts`
- Modify: `src/stores/rename.spec.ts`
- Modify: `src/components/rename/MatchStatistics.vue`

1. 添加选择目录后进入目录内容模式的失败测试。
2. 添加扫描后切换匹配结果、预览后切换安全预览的失败测试。
3. 实现 `resultMode`、根目录项目和模式化统计；查找变化保留根目录列表。
4. 运行状态仓库测试确认通过并提交。

### Task 3: 流程栏、正则入口与查找说明

**Files:**
- Create: `src/components/rename/SearchRuleHint.vue`
- Create: `src/components/rename/SearchRuleHint.spec.ts`
- Modify: `src/components/layout/WorkflowRail.vue`
- Modify: `src/components/layout/WorkflowRail.spec.ts`
- Modify: `src/components/rename/RegexTemplateDrawer.vue`
- Modify: `src/components/rename/RegexTemplateDrawer.spec.ts`

1. 添加失败测试，要求流程栏不再包含正则勾选，替换与预览同一行且按钮文字为“预览”。
2. 添加普通文本与正则模式说明的失败测试。
3. 添加正则抽屉包含模式开关的失败测试。
4. 实现组件与布局，运行相关测试确认通过并提交。

### Task 4: 自适应结果表格与底部工具栏

**Files:**
- Modify: `src/components/rename/resultRows.ts`
- Modify: `src/components/rename/ResultTable.vue`
- Modify: `src/components/rename/ResultTable.spec.ts`
- Modify: `src/views/RenameView.vue`
- Modify: `src/components/layout/WorkflowRail.vue`

1. 添加序号、根目录文字和列宽结构失败测试。
2. 调整表格列宽、禁止表头换行，并让表格占满可用高度。
3. 将工作台比例调整为 30%/70%，固定左下角工具栏。
4. 运行组件与页面测试确认通过并提交。

### Task 5: 阻塞式执行进度

**Files:**
- Modify: `src/api/desktop.ts`
- Modify: `src/stores/rename.ts`
- Modify: `src/stores/rename.spec.ts`
- Create: `src/components/rename/ExecutionProgressDialog.vue`
- Create: `src/components/rename/ExecutionProgressDialog.spec.ts`
- Modify: `src/views/RenameView.vue`
- Modify: `src/components/rename/ExecutionDetails.vue`

1. 添加执行回调更新真实进度并在异常后解除忙碌状态的失败测试。
2. 添加进度弹窗不可关闭的失败测试。
3. 实现进度状态和阻塞式弹窗，完成后切换成功结果。
4. 运行测试确认通过并提交。

### Task 6: 正式品牌与产品介绍

**Files:**
- Modify: `src/app/AppShell.vue`
- Modify: `src/app/AppShell.spec.ts`
- Modify: `src/components/help/AboutPanel.vue`
- Modify: `src/views/UsageGuideView.vue`
- Modify: `src/components/help/UsageGuide.vue`
- Modify: `src-tauri/tauri.conf.json`
- Modify: `src-tauri/src/lib.rs`
- Modify: `index.html`
- Modify: `README.md`
- Modify: `tests/release/test_release_config.py`

1. 添加品牌失败测试，要求显示“文件名管理”。
2. 更新窗口标题、顶部导航、关于和 README，保留 BatchRename 数据目录说明。
3. 运行产品与发布配置测试确认通过并提交。

### Task 7: 完整验证与发行构建

1. 运行 Rust 格式、Clippy 和全部测试。
2. 运行前端全部测试、类型检查、生产构建和端到端测试。
3. 构建 Windows 单文件程序与 NSIS 安装包，核验 GUI 子系统和 SHA-256。
4. 确认工作区洁净，记录中文详细提交，不执行推送。
