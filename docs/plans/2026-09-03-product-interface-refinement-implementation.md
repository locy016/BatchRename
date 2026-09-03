# BatchRename Product Interface Refinement Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将重命名工作区、结果表达、深浅色主题和帮助导航精修为一致、紧凑且可验证的产品级桌面界面。

**Architecture:** 保持 Rust 扫描/预览领域层与 Vue 工作流状态层的边界；排序在 Rust 扫描结果中统一完成，键盘与布局行为由 Vue 组件负责，视觉状态由全局语义令牌和 Element Plus 变量映射负责。帮助内容拆成独立路由页面，顶部仅承担导航。

**Tech Stack:** Rust 2024、Tauri 2、Vue 3、Vue Router、Pinia、Element Plus、SCSS、Vitest、Playwright。

---

### Task 1: 窗口尺寸和四步流程骨架

**Files:**
- Modify: `src-tauri/tauri.conf.json`
- Modify: `src/components/layout/WorkflowRail.vue`
- Modify: `src/components/layout/WorkflowRail.spec.ts`
- Create: `src-tauri/tests/window_config.rs`

**Step 1: Write the failing tests**

- 在 `window_config.rs` 读取 Tauri 配置，断言默认尺寸为 1360×840、最小尺寸为 1180×760。
- 在 `WorkflowRail.spec.ts` 断言页面不再出现旧提示和独立“扫描范围”步骤，只显示四个任务步骤。

**Step 2: Run tests to verify they fail**

Run:
`cargo test --test window_config`
`node node_modules/vitest/vitest.mjs run src/components/layout/WorkflowRail.spec.ts`

Expected: 旧窗口尺寸和六步流程导致断言失败。

**Step 3: Implement the layout skeleton**

- 更新窗口默认与最小尺寸。
- 将流程栏改为目录、查找、替换/预览、确认执行四段。
- 移除职业化副标题、扫描范围和扩展名复选项。

**Step 4: Run focused tests**

Expected: 两组测试通过。

**Step 5: Commit**

Commit title: `界面：重整窗口与重命名流程`

### Task 2: 设置归位和替换回车预览

**Files:**
- Modify: `src/components/rename/SettingsDrawer.vue`
- Modify: `src/components/layout/WorkflowRail.vue`
- Modify: `src/components/layout/WorkflowRail.spec.ts`
- Create: `src/components/rename/SettingsDrawer.spec.ts`

**Step 1: Write the failing tests**

- 断言设置抽屉包含处理对象、扫描层级和扩展名保护。
- 断言替换输入框按回车只在 `canPreview` 为真时调用 `preview()`。

**Step 2: Run tests to verify they fail**

Expected: 扫描层级仍不在设置抽屉，替换输入框没有回车处理。

**Step 3: Implement**

- 将层级数值组件放入设置抽屉并复用 `setMaxDepth()`。
- 重组设置分组与说明。
- 为替换输入框增加与按钮相同门禁的回车预览。

**Step 4: Run focused and store tests**

Expected: 组件测试和重命名状态测试通过。

**Step 5: Commit**

Commit title: `交互：归并扫描设置并支持回车预览`

### Task 3: 统一文件夹、目录与名称排序

**Files:**
- Modify: `src-tauri/src/services/scanner.rs`
- Modify: `src-tauri/tests/scanner.rs`

**Step 1: Write the failing test**

构造根目录和多层子目录中的文件夹、文件及带数字名称，断言顺序为：类型、目录深度、目录自然顺序、名称自然顺序。

**Step 2: Run test to verify it fails**

Run: `cargo test --test scanner sorts_by_kind_directory_then_natural_name`

Expected: 当前“类型后直接按名称”的实现返回错误顺序。

**Step 3: Implement one ordering function**

- 计算项目父目录相对根目录的组件数量。
- 比较类型、深度、逐级自然目录名称、项目自然名称。
- 保持扫描与预览使用同一快照顺序。

**Step 4: Run scanner and all Rust tests**

Expected: 新测试与现有扫描、预览、执行测试全部通过。

**Step 5: Commit**

Commit title: `结果：统一类型与目录排序规则`

### Task 4: 所在目录渐进展示

**Files:**
- Modify: `src/components/rename/ResultTable.vue`
- Create: `src/components/rename/ResultTable.spec.ts`

**Step 1: Write the failing tests**

- 根目录项目显示 `.`。
- 子目录项目不显示路径文字，只显示带无障碍标签的文件夹图标。
- 工具提示内容保存完整相对路径。

**Step 2: Run test to verify it fails**

Expected: 当前表格直接显示相对路径文字。

**Step 3: Implement a pure row mapping helper and cell template**

- 稳定计算相对父目录。
- 根目录渲染 `.`，子目录渲染文件夹图标。
- 图标工具提示显示完整相对路径。

**Step 4: Run component tests**

Expected: 路径、类型和状态图标测试通过。

**Step 5: Commit**

Commit title: `结果：收拢目录路径并按需展示详情`

### Task 5: 重建深浅色主题和抽屉视觉

**Files:**
- Modify: `src/styles/tokens.scss`
- Modify: `src/styles/index.scss`
- Modify: `src/styles/element.scss`
- Modify: `src/components/rename/SettingsDrawer.vue`
- Modify: `src/components/rename/RegexTemplateDrawer.vue`
- Modify: `tests/e2e/responsive-theme.spec.ts`
- Create: `src/styles/theme.spec.ts`

**Step 1: Write the failing tests**

- 断言应用头部和导航不再使用固定浅色值。
- 断言深色主题定义 Element Plus 的背景、文字、边框、填充、遮罩和浮层变量。
- 端到端打开设置抽屉后切换深色，检查抽屉与页面主题属性一致且无浅色背景变量。

**Step 2: Run tests to verify they fail**

Expected: 固定 `#fff`、不完整 Element 变量和旧抽屉结构导致失败。

**Step 3: Implement semantic theme system**

- 扩充表面、浮层、交互和遮罩令牌。
- 将应用壳、业务卡片和 Element Plus 全部映射到令牌。
- 为抽屉加入稳定的页头、分组卡片、说明和间距。

**Step 4: Run unit and e2e theme tests**

Expected: 浅色、深色、系统三种模式及打开状态浮层通过。

**Step 5: Commit**

Commit title: `外观：统一深浅色主题与浮层组件`

### Task 6: 帮助子菜单和独立产品页面

**Files:**
- Modify: `src/app/AppShell.vue`
- Modify: `src/app/AppShell.spec.ts`
- Modify: `src/router/index.ts`
- Replace: `src/views/HelpView.vue`
- Create: `src/views/UsageGuideView.vue`
- Create: `src/views/AboutView.vue`
- Modify: `src/components/help/UsageGuide.vue`
- Modify: `src/components/help/AboutPanel.vue`
- Modify: `src/views/HelpView.spec.ts`
- Modify: `tests/e2e/execute-history-undo.spec.ts`

**Step 1: Write the failing tests**

- 顶部主导航只保留三个工作区链接，帮助为菜单按钮。
- 帮助菜单包含“使用说明”“关于”并链接不同路由。
- 两个页面分别验证操作指南内容和产品/版本/数据/联系信息。

**Step 2: Run tests to verify they fail**

Expected: 当前帮助是单链接和混合粗糙页面。

**Step 3: Implement navigation and pages**

- 使用可访问的 Element Plus 下拉菜单作为帮助入口。
- 新增 `/help/guide`、`/help/about`，旧 `/help` 重定向到使用说明。
- 重组内容为产品头图、步骤卡片、安全说明、能力清单和产品信息。

**Step 4: Run component and e2e tests**

Expected: 菜单键鼠可达，两个页面独立显示且信息完整。

**Step 5: Commit**

Commit title: `帮助：拆分导航与产品说明页面`

### Task 7: 综合收敛、发行验证与本地提交

**Files:**
- Modify only when a failing verification proves a defect.

**Step 1: Run formatting and strict checks**

Run Rust format check, Clippy `-D warnings`, TypeScript type check and frontend production build.

**Step 2: Run all automated tests**

Run all Rust tests, all Vitest tests and all Playwright tests.

**Step 3: Build Windows release artifacts**

Run Tauri release build and generate the portable executable plus NSIS installer.

**Step 4: Inspect release properties**

Verify PE subsystem remains Windows GUI, collect file sizes and SHA-256 values, and confirm the Git worktree is clean after commit.

**Step 5: Commit verification record when code or documentation changed**

Commit title: `发布：完成产品界面精修验证`

Do not push. The user performs every remote push manually.
