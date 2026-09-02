# BatchRename 2.0 Tauri + Vue Rewrite Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在仓库根目录建立 Rust + Tauri 2 + Vue 3 桌面版本，完整复现 Python 版已经公开的扫描、预览、安全执行、操作日志和整批撤回，并改善界面响应、模块边界与 Windows 发布体验。

**Architecture:** Vue/TypeScript 负责路由、状态和展示，所有目录读取与磁盘修改都通过具有业务含义的 Tauri Command 进入无 Tauri 依赖的 Rust 领域与服务层。Python 子项目在整个迁移期作为可运行产品和行为 Oracle；规则与日志使用共享夹具验证跨实现一致性，直到 2.0 发布候选通过才切换默认发行版。

**Tech Stack:** Rust stable-msvc、Tauri 2、Vue 3、TypeScript、Vite、Vue Router、Pinia、Element Plus、Vitest、Vue Test Utils、Playwright、Serde、regex、fancy-regex、thiserror。

**Execution constraints:** 直接在 `main` 上按任务提交，不创建分支或 worktree；所有提交标题和正文使用中文；不主动推送；每个磁盘行为先写失败测试；不要删除或弱化 `Python` 子项目。

---

### Task 1: 准备工具链与记录迁移基线

**Files:**
- Create: `docs/benchmarks/2026-09-02-python-baseline.md`
- Create: `Python/tools/benchmark_workflow.py`
- Create: `Python/tests/test_benchmark_workflow.py`
- Modify: `.gitignore`

**Step 1: 验证环境门禁**

Run:

```powershell
node --version
npm --version
rustc --version
cargo --version
```

Expected: 当前首次执行显示 Node.js 16.20.2，且 Rust 命令不存在，证明环境尚不满足设计门禁。

**Step 2: 升级开发环境**

在取得系统级安装授权后安装满足当前 Vue/Vite 要求的 Node.js LTS、Rust stable-msvc、Visual Studio C++ Build Tools 的“使用 C++ 的桌面开发”组件，并确认 WebView2 Runtime。不要在未授权时静默修改系统环境。

Run:

```powershell
node --version
rustup default stable-msvc
rustc --version
cargo --version
```

Expected: Node.js 满足当前 Vue/Vite 最低版本，Rust 与 Cargo 使用稳定 MSVC 工具链。

**Step 3: 为 Python 基线脚本写失败测试**

测试要求脚本能够创建指定数量和深度的临时目录、运行匹配与预览，并输出包含 `scenario`、`entries`、`scanMs`、`previewMs` 和 `matched` 的 JSON；测试必须使用小型临时目录且不执行改名。

Run:

```powershell
cd Python
python -m pytest tests/test_benchmark_workflow.py -q
```

Expected: FAIL，提示基线脚本或公开测量函数不存在。

**Step 4: 实现最小基线工具并记录结果**

实现 `benchmark_scenario(root, options) -> dict[str, object]`，使用 `time.perf_counter_ns()` 分别测量 `search_matches` 与 `build_preview`。命令行提供 1,000、10,000 和可选 100,000 项场景，默认只运行 1,000 项，临时目录由调用方决定是否保留。

运行基线并把机器、Python、项目提交、数据规模和结果写入基线文档。禁止把绝对用户路径写入仓库。

**Step 5: 更新忽略规则并验证**

在 `.gitignore` 加入：

```gitignore
node_modules/
target/
coverage/
playwright-report/
test-results/
.vite/
```

Run:

```powershell
cd Python
python -m pytest tests/test_benchmark_workflow.py -q
python -m pytest -q
```

Expected: 基线测试通过，Python 完整测试至少 190 项全部通过。

**Step 6: Commit**

```powershell
git add .gitignore Python/tools/benchmark_workflow.py Python/tests/test_benchmark_workflow.py docs/benchmarks/2026-09-02-python-baseline.md
git commit -m "基准：建立 Python 工作流性能参照"
```

---

### Task 2: 建立 Tauri、Vue 与测试骨架

**Files:**
- Create: `package.json`
- Create: `package-lock.json`
- Create: `index.html`
- Create: `vite.config.ts`
- Create: `vitest.config.ts`
- Create: `tsconfig.json`
- Create: `tsconfig.node.json`
- Create: `src/main.ts`
- Create: `src/App.vue`
- Create: `src/app/AppShell.vue`
- Create: `src/app/AppShell.spec.ts`
- Create: `src/router/index.ts`
- Create: `src/styles/index.scss`
- Create: `src/env.d.ts`
- Create: `src-tauri/Cargo.toml`
- Create: `src-tauri/build.rs`
- Create: `src-tauri/tauri.conf.json`
- Create: `src-tauri/capabilities/default.json`
- Create: `src-tauri/src/main.rs`
- Create: `src-tauri/src/lib.rs`

**Step 1: 写前端壳层失败测试**

测试挂载 `AppShell`，断言存在产品标题、主导航以及 `/rename`、`/history`、`/undo`、`/help` 四个可达入口。Element Plus 与 Tauri API 通过测试安装器和适配器替身注入。

Run:

```powershell
npm run test -- src/app/AppShell.spec.ts
```

Expected: FAIL，项目或组件不存在。

**Step 2: 创建最小前端工程**

使用 Vue 3、TypeScript、Vite、Router、Pinia 和 Element Plus 按需导入。`package.json` 至少定义：

```json
{
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc -b && vite build",
    "test": "vitest run",
    "test:watch": "vitest",
    "tauri": "tauri"
  }
}
```

根应用只渲染 AppShell 与 RouterView，不加入磁盘功能。

**Step 3: 创建最小 Tauri 工程**

包版本设为 `2.0.0-alpha.1`，应用标识使用稳定反向域名；主窗口标题为“批量重命名”，最小尺寸使用设计确认值。Capabilities 初始只开放 core 窗口和 dialog 所需权限，不开放通用文件系统写权限。

Run:

```powershell
cargo check --manifest-path src-tauri/Cargo.toml
npm run build
```

Expected: Rust 检查和 Vue 生产构建通过。

**Step 4: 生成应用图标**

以 `Python/assets/app-icon.png` 为唯一源图，通过 Tauri 图标工具生成 `src-tauri/icons`，不要人工维护多份位图源文件。

Run:

```powershell
npm run tauri icon Python/assets/app-icon.png
```

Expected: Tauri 所需 Windows 图标存在。

**Step 5: 验证测试壳层**

Run:

```powershell
npm run test -- src/app/AppShell.spec.ts
cargo test --manifest-path src-tauri/Cargo.toml
```

Expected: 前端壳层测试和 Rust 空工程测试通过。

**Step 6: Commit**

```powershell
git add package.json package-lock.json index.html vite.config.ts vitest.config.ts tsconfig*.json src src-tauri
git commit -m "基础：建立 Tauri 与 Vue 2.0 工程骨架"
```

---

### Task 3: 冻结跨实现行为夹具和数据契约

**Files:**
- Create: `tests/fixtures/rules-v1.json`
- Create: `tests/fixtures/logs/operation-completed-v1.json`
- Create: `tests/fixtures/logs/operation-partial-v1.json`
- Create: `tests/fixtures/logs/operation-interrupted-v1.json`
- Create: `tests/fixtures/logs/operation-partially-undone-v1.json`
- Create: `Python/tools/export_compatibility_fixtures.py`
- Create: `Python/tests/test_compatibility_fixtures.py`
- Create: `src/types/contracts.ts`
- Create: `src-tauri/src/domain/mod.rs`
- Create: `src-tauri/src/domain/models.rs`
- Create: `src-tauri/tests/contracts.rs`

**Step 1: 写 Python 夹具失败测试**

断言规则夹具覆盖普通文本、15 条内置模板、扩展名保护、名称未变化和无效替换引用；日志夹具必须由当前 `OperationLog` 成功读取，并覆盖正常、部分失败、中断和部分撤回。

Run:

```powershell
cd Python
python -m pytest tests/test_compatibility_fixtures.py -q
```

Expected: FAIL，夹具尚不存在。

**Step 2: 生成并审查夹具**

导出工具从 Python 模型构建脱敏数据，只写相对演示路径，不读取真实 `%LOCALAPPDATA%`。规则夹具字段固定为：

```text
id, search, replacement, input, isFile, renameExtension, expectedName, expectedError
```

**Step 3: 写 Rust 契约失败测试**

定义 `ItemKind`、`CandidateStatus`、`MatchOptions`、`MatchedItem`、`RenameCandidate`、`OperationLogV1` 和逐项记录。测试读取四份 JSON 并断言字段、中文枚举和 `schema_version = 1` 正确。

Run:

```powershell
cargo test --manifest-path src-tauri/Cargo.toml --test contracts
```

Expected: FAIL，Rust 模型尚未实现。

**Step 4: 实现 Rust 模型和 TypeScript DTO**

持久化模型保持旧 JSON 字段，IPC DTO 使用 `camelCase`。两者通过显式转换实现，不能直接把持久化枚举暴露为前端状态机。

**Step 5: 验证双端契约**

Run:

```powershell
cd Python
python -m pytest tests/test_compatibility_fixtures.py -q
cd ..
cargo test --manifest-path src-tauri/Cargo.toml --test contracts
npm run build
```

Expected: Python、Rust 和 TypeScript 类型检查全部通过。

**Step 6: Commit**

```powershell
git add tests/fixtures Python/tools/export_compatibility_fixtures.py Python/tests/test_compatibility_fixtures.py src/types src-tauri/src/domain src-tauri/tests/contracts.rs
git commit -m "契约：冻结 Python 与 Rust 行为兼容夹具"
```

---

### Task 4: 移植名称规则、正则适配与 Windows 校验

**Files:**
- Create: `src-tauri/src/domain/rules.rs`
- Create: `src-tauri/src/domain/validation.rs`
- Create: `src-tauri/src/domain/errors.rs`
- Create: `src-tauri/tests/rules.rs`
- Modify: `src-tauri/src/domain/mod.rs`
- Modify: `src-tauri/Cargo.toml`

**Step 1: 写规则失败测试**

读取 `rules-v1.json`，逐项验证名称或错误。额外覆盖空查找、中文、Windows 设备名、非法字符、尾随点或空格、仅扩展名匹配、命名捕获和 Python 替换引用。

Run:

```powershell
cargo test --manifest-path src-tauri/Cargo.toml --test rules
```

Expected: FAIL，规则模块不存在。

**Step 2: 实现普通文本和扩展名保护**

公开接口：

```rust
pub struct RenameRule { /* compiled state */ }
impl RenameRule {
    pub fn compile(search: &str, replacement: &str, use_regex: bool, rename_extension: bool) -> Result<Self, DomainError>;
    pub fn matches(&self, name: &str) -> Result<bool, DomainError>;
    pub fn rename(&self, name: &str, is_file: bool) -> Result<String, DomainError>;
}
```

先让普通文本、扩展名保护和名称校验测试通过。

**Step 3: 实现 Python 风格替换解析器**

解析字面量、`\\`、`\1`、`\g<1>` 和 `\g<name>`，无效引用返回稳定错误码 `invalidReplacementReference`。不得仅通过字符串替换把 `\1` 改成 `$1`。

**Step 4: 实现双正则引擎选择**

默认使用 `regex`；只有检测到兼容清单内的高级结构才使用 `fancy-regex`。设置表达式长度和回溯限制，运行错误转为 `regexRuntimeError`。

**Step 5: 验证全部规则**

Run:

```powershell
cargo test --manifest-path src-tauri/Cargo.toml --test rules
cd Python
python -m pytest tests/test_rules.py tests/test_examples.py tests/test_compatibility_fixtures.py -q
```

Expected: Rust 夹具和 Python 原行为全部通过。

**Step 6: Commit**

```powershell
git add src-tauri/src/domain src-tauri/tests/rules.rs src-tauri/Cargo.toml src-tauri/Cargo.lock
git commit -m "规则：移植名称校验与 Python 正则兼容层"
```

---

### Task 5: 实现可取消扫描服务与分页结果

**Files:**
- Create: `src-tauri/src/services/mod.rs`
- Create: `src-tauri/src/services/scanner.rs`
- Create: `src-tauri/src/state/mod.rs`
- Create: `src-tauri/src/state/job_manager.rs`
- Create: `src-tauri/src/commands/mod.rs`
- Create: `src-tauri/src/commands/scan.rs`
- Create: `src-tauri/tests/scanner.rs`
- Modify: `src-tauri/src/lib.rs`

**Step 1: 写扫描失败测试**

覆盖全部层级、深度 1、只处理文件夹、只处理文件、符号链接不跟随、不可读目录警告、目录与文件总量、文件夹优先和自然名称排序。

Run:

```powershell
cargo test --manifest-path src-tauri/Cargo.toml --test scanner
```

Expected: FAIL，扫描服务不存在。

**Step 2: 实现同步领域扫描器**

实现：

```rust
pub fn search_matches(
    options: &MatchOptions,
    cancel: &CancellationToken,
    progress: impl FnMut(ScanProgress),
) -> Result<MatchSnapshot, DomainError>;
```

保持不跟随符号链接、扫描总量独立于处理对象过滤、根目录不进入候选集。

**Step 3: 实现任务管理器**

任务管理器保存任务标识、取消令牌和最终快照句柄。重复扫描取消旧任务；修改磁盘任务存在时拒绝新扫描。任务完成后只保留当前有效快照。

**Step 4: 建立 Tauri 扫描命令与 Channel**

`start_scan` 返回任务标识；Channel 事件包含 `jobId`、阶段、扫描数量、匹配数量和可选警告。最多每 50 毫秒或每 200 项发送一次普通进度，完成和错误不节流。

**Step 5: 验证扫描与取消**

增加取消测试，断言取消后返回 `cancelled` 且没有残留活动任务。

Run:

```powershell
cargo test --manifest-path src-tauri/Cargo.toml --test scanner
cargo test --manifest-path src-tauri/Cargo.toml
```

Expected: 扫描、取消和任务互斥测试全部通过。

**Step 6: Commit**

```powershell
git add src-tauri/src/services src-tauri/src/state src-tauri/src/commands src-tauri/tests/scanner.rs
git commit -m "扫描：建立可取消任务与分层目录匹配"
```

---

### Task 6: 实现预览、冲突检查和结果分页

**Files:**
- Create: `src-tauri/src/services/preview.rs`
- Create: `src-tauri/src/commands/preview.rs`
- Create: `src-tauri/tests/preview.rs`
- Modify: `src-tauri/src/services/mod.rs`
- Modify: `src-tauri/src/commands/mod.rs`
- Modify: `src-tauri/src/lib.rs`

**Step 1: 写预览失败测试**

移植 Python 预览测试：名称未变化、受保护扩展名、目标已存在、批内重复目标、非法名称、替换变化不重新读取目录、统计不受分页上限影响。

**Step 2: 实现纯预览服务**

`build_preview(snapshot, replacement, rename_extension)` 只使用扫描快照和当前目录状态检查，不重新递归扫描。完整候选保存在后端，返回概要和第一页。

**Step 3: 实现分页接口**

提供 `get_preview_page(job_id, offset, limit)`，限制单页最大数量并返回 `total`。页面排序必须稳定；任务标识失效返回 `staleSnapshot`。

**Step 4: 运行测试**

Run:

```powershell
cargo test --manifest-path src-tauri/Cargo.toml --test preview
cargo test --manifest-path src-tauri/Cargo.toml
```

Expected: 所有预览与分页测试通过。

**Step 5: Commit**

```powershell
git add src-tauri/src/services/preview.rs src-tauri/src/commands/preview.rs src-tauri/tests/preview.rs src-tauri/src/lib.rs
git commit -m "预览：复现安全状态与后端分页结果"
```

---

### Task 7: 实现兼容旧格式的原子操作日志

**Files:**
- Create: `src-tauri/src/services/journal.rs`
- Create: `src-tauri/src/commands/history.rs`
- Create: `src-tauri/tests/journal.rs`
- Create: `tests/compat/test_rust_log_roundtrip.py`
- Modify: `src-tauri/src/services/mod.rs`
- Modify: `src-tauri/src/commands/mod.rs`

**Step 1: 写日志失败测试**

覆盖单操作单文件、同目录临时文件替换、新旧 JSON 往返、按时间倒序概要、关键词和状态筛选、损坏文件隔离、准备中或执行中恢复为中断。

**Step 2: 实现 `OperationStore`**

默认目录必须解析到现有 `%LOCALAPPDATA%\BatchRename\operations`。保存流程为序列化、同目录临时写入、刷新、替换正式文件、清理临时文件。标识符通过白名单验证。

**Step 3: 实现概要索引与延迟详情**

`query_operations` 只返回分页概要；`get_operation` 才读取逐项详情。第一版可以在内存缓存文件元数据，但必须依据修改时间失效，不引入数据库迁移。

**Step 4: 验证 Python 与 Rust 往返**

兼容测试调用一个小型 Rust 测试工具写入临时档案，再由 Python `OperationLog.from_dict` 读取；Python 夹具也必须由 Rust 读取并保持字段。根目录兼容测试需要把仓库内 `Python` 目录显式加入测试导入路径，不能依赖开发机器的全局 `PYTHONPATH`。

Run:

```powershell
cargo test --manifest-path src-tauri/Cargo.toml --test journal
python -m pytest tests/compat/test_rust_log_roundtrip.py -q
```

Expected: 双向往返全部通过，真实用户日志目录未被读取或修改。

**Step 5: Commit**

```powershell
git add src-tauri/src/services/journal.rs src-tauri/src/commands/history.rs src-tauri/tests/journal.rs tests/compat/test_rust_log_roundtrip.py
git commit -m "日志：兼容 Python 档案并支持分页查询"
```

---

### Task 8: 实现安全执行与逐项写档

**Files:**
- Create: `src-tauri/src/services/executor.rs`
- Create: `src-tauri/src/commands/execute.rs`
- Create: `src-tauri/tests/executor.rs`
- Modify: `src-tauri/src/state/job_manager.rs`
- Modify: `src-tauri/src/lib.rs`

**Step 1: 写执行失败测试**

覆盖准备日志失败时零改名、文件改名、子项目先于父目录、来源消失、目标突然出现、仅大小写变化、逐项进度、逐项日志保存失败后停止以及最终状态归纳。

**Step 2: 实现预检和排序**

执行只接受当前有效预览标识和 READY 项，开始前重查路径。排序使用深度降序并保持相同深度稳定顺序。

**Step 3: 实现大小写改名和任务互斥**

仅大小写变化先改到同目录唯一临时名，再改到目标；第二步失败时尽力恢复来源。执行期间任务管理器拒绝扫描和撤回。

**Step 4: 实现操作日志和进度 Channel**

初始档案成功后才允许第一项磁盘修改。每项结果立即保存；保存失败停止后续处理并返回中断。Channel 事件包含当前序号、总数、相对路径和结果。

**Step 5: 验证**

Run:

```powershell
cargo test --manifest-path src-tauri/Cargo.toml --test executor
cargo test --manifest-path src-tauri/Cargo.toml
```

Expected: 所有执行和故障注入测试通过。

**Step 6: Commit**

```powershell
git add src-tauri/src/services/executor.rs src-tauri/src/commands/execute.rs src-tauri/src/state/job_manager.rs src-tauri/tests/executor.rs src-tauri/src/lib.rs
git commit -m "执行：实现预检改名与逐项原子记录"
```

---

### Task 9: 实现整批撤回和失败重试

**Files:**
- Create: `src-tauri/src/services/undo.rs`
- Create: `src-tauri/src/commands/undo.rs`
- Create: `src-tauri/tests/undo.rs`
- Modify: `src-tauri/src/lib.rs`

**Step 1: 写撤回失败测试**

逐项移植 Python 撤回测试，并增加从 Python 日志夹具撤回的集成测试。覆盖嵌套目录、来源缺失、恢复目标占用、类型变化、大小写、运行时失败停止、再次重试和完全撤回后禁止重复执行。

**Step 2: 实现纯预检**

根据后续文件夹恢复推导当前路径，生成逐项 `UndoCheckItem`。任一项不安全时整批 `safe = false`，且不得修改日志或磁盘。

**Step 3: 实现撤回执行**

只接受日志标识、日志更新时间和预检令牌；确认前日志发生变化则要求重新检查。按原执行记录逆序处理，每项保存撤回状态，运行中失败立即停止。

**Step 4: 验证**

Run:

```powershell
cargo test --manifest-path src-tauri/Cargo.toml --test undo
cargo test --manifest-path src-tauri/Cargo.toml
```

Expected: 所有撤回语义与 Python 版一致。

**Step 5: Commit**

```powershell
git add src-tauri/src/services/undo.rs src-tauri/src/commands/undo.rs src-tauri/tests/undo.rs src-tauri/src/lib.rs
git commit -m "撤回：实现整批预检、逆序恢复与重试"
```

---

### Task 10: 建立前端状态机、Tauri 适配器和设计系统

**Files:**
- Create: `src/api/desktop.ts`
- Create: `src/api/desktop.spec.ts`
- Create: `src/stores/rename.ts`
- Create: `src/stores/rename.spec.ts`
- Create: `src/stores/history.ts`
- Create: `src/stores/undo.ts`
- Create: `src/styles/tokens.scss`
- Create: `src/styles/element.scss`
- Create: `src/views/RenameView.vue`
- Create: `src/views/HistoryView.vue`
- Create: `src/views/UndoView.vue`
- Create: `src/views/HelpView.vue`
- Modify: `src/router/index.ts`

**Step 1: 写状态机失败测试**

断言目录、层级、对象、查找或正则变化使扫描快照和预览失效；只修改替换内容保留匹配快照但使预览失效；迟到任务消息不能覆盖当前任务；执行和撤回状态互斥。

**Step 2: 实现唯一 Tauri 适配器**

Vue 组件只依赖 `DesktopApi` 接口。实际适配器集中封装 `invoke`、Channel 和 Dialog；测试适配器返回确定数据。禁止在组件中直接导入 `@tauri-apps/api/core`。

**Step 3: 实现 Pinia Store**

Store 用判别联合表达工作流状态，磁盘命令只能由 action 发起。任务完成、取消、失败和迟到消息均有测试。

**Step 4: 建立主题 Token**

定义浅色、深色和语义色，不直接在业务组件散布颜色。Element Plus 变量集中覆盖，保持键盘焦点、禁用态和危险动作对比度。

**Step 5: 验证**

Run:

```powershell
npm run test -- src/api src/stores
npm run build
```

Expected: 状态和类型测试通过。

**Step 6: Commit**

```powershell
git add src/api src/stores src/styles src/views src/router
git commit -m "前端：建立类型化桌面接口与工作流状态机"
```

---

### Task 11: 实现响应式主工作台与安全结果表

**Files:**
- Create: `src/components/layout/AppNavigation.vue`
- Create: `src/components/layout/WorkflowRail.vue`
- Create: `src/components/layout/CompactWorkflowDrawer.vue`
- Create: `src/components/rename/DirectoryOverview.vue`
- Create: `src/components/rename/RuleEditor.vue`
- Create: `src/components/rename/MatchStatistics.vue`
- Create: `src/components/rename/ResultTable.vue`
- Create: `src/components/rename/ResultDetails.vue`
- Create: `src/components/rename/ProgressStatus.vue`
- Create: `src/views/RenameView.spec.ts`
- Modify: `src/views/RenameView.vue`

**Step 1: 写布局与流程失败测试**

覆盖左侧六步流程、窄屏抽屉、当前目录概况、匹配统计位于结果表下方、列顺序、相对目录、图标提示、新名称强调和按钮启用条件。

**Step 2: 实现标准与舒展布局**

CSS Grid 管理工作流与结果区；工作流宽度使用设计 Token，剩余空间全部交给结果列表。使用 ResizeObserver 和 CSS media/container queries，不在窗口变化时销毁表单组件。

**Step 3: 实现紧凑布局**

窄屏只保留图标导航，流程放入可关闭抽屉；抽屉与正则模板、设置互斥。焦点返回触发按钮，Esc 只关闭顶层浮层。

**Step 4: 实现结果表**

默认 100 条使用 Element Plus Table，状态和类型使用 SVG 图标及 Tooltip，不创建原生覆盖控件。长路径与名称使用溢出提示；完整详情使用单实例 Dialog。

**Step 5: 验证**

Run:

```powershell
npm run test -- src/views/RenameView.spec.ts
npm run build
```

Expected: 组件测试和生产构建通过。

**Step 6: Commit**

```powershell
git add src/components src/views/RenameView.vue src/views/RenameView.spec.ts
git commit -m "界面：建立响应式重命名工作台与结果表"
```

---

### Task 12: 接通选择目录、扫描、预览与正则模板

**Files:**
- Create: `src/components/rename/RegexTemplateDrawer.vue`
- Create: `src/components/rename/SettingsDrawer.vue`
- Create: `src/data/regexTemplates.ts`
- Create: `src/data/regexTemplates.spec.ts`
- Create: `src/views/RenameWorkflow.spec.ts`
- Modify: `src/views/RenameView.vue`
- Modify: `src/stores/rename.ts`

**Step 1: 写工作流失败测试**

使用 DesktopApi 替身完成选择目录、扫描进度、匹配列表、填写替换、结果预览、名称未变化和阻止执行的完整只读流程。断言扫描不要求替换内容，预览不再次扫描。

**Step 2: 接通目录与任务 Channel**

选目录后更新概况但不自动扫描。扫描期间显示确定或不确定进度，取消按钮调用当前任务标识；完成后获取第一页结果。

**Step 3: 移植 15 条模板**

数据字段保持分类、标题、用途、查找、替换、前后示例和扩展名开关。测试读取共享规则夹具，确保模板与兼容契约同步。

**Step 4: 接通设置抽屉**

层级和处理对象变化使扫描失效，扩展名保护只使预览失效。选项文案解释第 1 层含义和根目录不改名。

**Step 5: 验证**

Run:

```powershell
npm run test -- src/data/regexTemplates.spec.ts src/views/RenameWorkflow.spec.ts
npm run build
```

Expected: 只读工作流可完整演示。

**Step 6: Commit**

```powershell
git add src/components/rename src/data src/views/RenameWorkflow.spec.ts src/views/RenameView.vue src/stores/rename.ts
git commit -m "流程：接通目录扫描、预览与正则模板"
```

---

### Task 13: 接通确认执行与操作结果

**Files:**
- Create: `src/components/rename/ExecuteConfirmation.vue`
- Create: `src/components/rename/ExecutionDetails.vue`
- Create: `src/views/ExecuteWorkflow.spec.ts`
- Modify: `src/stores/rename.ts`
- Modify: `src/views/RenameView.vue`

**Step 1: 写执行界面失败测试**

断言只有 READY 项存在且预览仍有效时可确认；对话框展示根目录、文件夹、文件、跳过和阻止统计；确认后禁用输入并显示逐项进度；完成、部分失败和中断分别呈现。

**Step 2: 实现二次确认和任务互斥**

确认动作携带预览标识，不从前端重新拼装候选列表。执行中禁止关闭关键确认状态，但允许最小化窗口；不提供会破坏原子写档的强制取消。

**Step 3: 实现结果详情**

详情通过操作标识从后端读取真实日志，不以临时前端数组作为事实依据。完整路径仅在使用者主动展开时显示。

**Step 4: 验证**

Run:

```powershell
npm run test -- src/views/ExecuteWorkflow.spec.ts
npm run build
```

Expected: 执行状态和错误路径全部通过。

**Step 5: Commit**

```powershell
git add src/components/rename src/views/ExecuteWorkflow.spec.ts src/views/RenameView.vue src/stores/rename.ts
git commit -m "执行界面：完成确认、进度与真实结果详情"
```

---

### Task 14: 实现操作日志与撤回管理页面

**Files:**
- Create: `src/components/history/OperationFilters.vue`
- Create: `src/components/history/OperationList.vue`
- Create: `src/components/history/OperationDetails.vue`
- Create: `src/components/undo/UndoCheckPanel.vue`
- Create: `src/components/undo/UndoConfirmation.vue`
- Create: `src/views/HistoryView.spec.ts`
- Create: `src/views/UndoView.spec.ts`
- Modify: `src/views/HistoryView.vue`
- Modify: `src/views/UndoView.vue`
- Modify: `src/stores/history.ts`
- Modify: `src/stores/undo.ts`

**Step 1: 写日志页面失败测试**

覆盖分页、状态筛选、关键词、损坏记录、延迟详情、逐项执行和撤回状态，以及从主界面新执行后刷新历史。

**Step 2: 实现日志页面**

列表与详情分离请求；快速输入筛选使用短防抖并取消旧请求。长项目列表使用后端分页，只有确有大量数据时启用 Table V2。

**Step 3: 写撤回页面失败测试**

断言没有安全检查时确认按钮禁用，检查中显示状态，任一阻止项使整批不可执行，日志更新时间变化使旧检查失效，撤回后刷新日志与待恢复数量。

**Step 4: 实现撤回页面**

确认对话框展示根目录、待恢复数量和风险提示。撤回进度由 Channel 驱动；部分失败保留可重试项，完全撤回后禁用重复操作。

**Step 5: 验证**

Run:

```powershell
npm run test -- src/views/HistoryView.spec.ts src/views/UndoView.spec.ts
npm run build
```

Expected: 日志和撤回组件测试通过。

**Step 6: Commit**

```powershell
git add src/components/history src/components/undo src/views/HistoryView* src/views/UndoView* src/stores/history.ts src/stores/undo.ts
git commit -m "管理：实现操作日志查询与整批撤回界面"
```

---

### Task 15: 完成主题、偏好、帮助与无障碍交互

**Files:**
- Create: `src/stores/preferences.ts`
- Create: `src/stores/preferences.spec.ts`
- Create: `src/components/help/AboutPanel.vue`
- Create: `src/components/help/UsageGuide.vue`
- Create: `src/views/HelpView.spec.ts`
- Create: `src-tauri/src/services/preferences.rs`
- Create: `src-tauri/src/commands/preferences.rs`
- Create: `src-tauri/tests/preferences.rs`
- Modify: `src/views/HelpView.vue`
- Modify: `src-tauri/src/lib.rs`

**Step 1: 写偏好失败测试**

覆盖缺失或损坏配置回退跟随系统、浅色、深色、切换不清空工作流、重启恢复和旧 Python 设置文件读取。

**Step 2: 实现偏好服务与主题**

继续使用 `%LOCALAPPDATA%\BatchRename\settings.json`，兼容现有 `appearance` 字段。前端为 `<html>` 设置主题属性，Element Plus 和自定义 Token 同步响应。

**Step 3: 实现帮助和关于**

内容必须描述真实完成能力、2.0 版本、日志位置、安全边界、免责声明和联系方式。不得把尚未完成的自动更新或跨平台描述成现有功能。

**Step 4: 验证键盘和焦点**

组件测试覆盖 Tab 顺序、Enter 执行明确默认动作、Esc 关闭顶层浮层、关闭后焦点返回触发器、图标按钮具有中文 accessible name。

Run:

```powershell
npm run test -- src/stores/preferences.spec.ts src/views/HelpView.spec.ts
cargo test --manifest-path src-tauri/Cargo.toml --test preferences
npm run build
```

Expected: 偏好、帮助、主题和类型检查通过。

**Step 5: Commit**

```powershell
git add src/stores/preferences* src/components/help src/views/HelpView* src-tauri/src/services/preferences.rs src-tauri/src/commands/preferences.rs src-tauri/tests/preferences.rs src-tauri/src/lib.rs
git commit -m "体验：完成三态外观、帮助与键盘交互"
```

---

### Task 16: 建立端到端安全闭环和性能门禁

**Files:**
- Create: `playwright.config.ts`
- Create: `tests/e2e/rename-preview.spec.ts`
- Create: `tests/e2e/execute-history-undo.spec.ts`
- Create: `tests/e2e/responsive-theme.spec.ts`
- Create: `tests/performance/generate-tree.ps1`
- Create: `tests/performance/run-benchmarks.ps1`
- Create: `docs/benchmarks/2026-09-02-tauri-comparison.md`
- Modify: `package.json`

**Step 1: 写只读 E2E 测试**

使用可替换 DesktopApi 在浏览器中验证选择目录、扫描、预览、正则模板、统计、窄屏和主题，不需要真实 Tauri 运行时。

**Step 2: 写 Windows 临时目录闭环测试**

测试脚本只能在新建的明确临时目录内生成数据，先验证绝对路径属于临时根，再执行改名与撤回。覆盖文件、文件夹、嵌套目录和大小写变化。

**Step 3: 建立性能比较**

在与 Python 基线相同的 1,000、10,000 和可选 100,000 项场景记录扫描、预览、首批结果、取消响应和历史首页时间。报告同时记录版本、提交和硬件，不只写“更快”。

**Step 4: 运行完整验证**

Run:

```powershell
npm run test
npm run build
cargo test --manifest-path src-tauri/Cargo.toml
npx playwright test
powershell -NoProfile -File .\tests\performance\run-benchmarks.ps1
cd Python
python -m pytest -q
```

Expected: 前端、Rust、E2E 与 Python 回归全部通过；比较文档具有完整数据。

**Step 5: Commit**

```powershell
git add playwright.config.ts tests/e2e tests/performance docs/benchmarks/2026-09-02-tauri-comparison.md package.json package-lock.json
git commit -m "验证：建立跨实现闭环与性能门禁"
```

---

### Task 17: 构建 Windows 安装包和便携候选产物

**Files:**
- Create: `scripts/build-release.ps1`
- Create: `scripts/smoke-test-release.ps1`
- Create: `tests/release/test_release_config.py`
- Modify: `src-tauri/tauri.conf.json`
- Modify: `README.md`

**Step 1: 写发布配置失败测试**

断言版本、产品名、图标、NSIS 目标、中文安装信息、最小窗口、Capabilities、前端构建命令和产物验证脚本存在。测试不能要求网络或签名密钥。

**Step 2: 实现发布脚本**

脚本依次运行前端测试、类型检查、Rust 测试、兼容测试和 Tauri 构建，任一步失败立即停止。不要删除仓库外目录，不自动关闭既有 BatchRename 进程。

**Step 3: 实现安全冒烟脚本**

启动前记录精确产物路径的现有 PID，只跟踪本次新增 PID；等待标题窗口或超时，验证后只结束新增进程。输出路径、大小、SHA-256、启动 PID、窗口 PID 和剩余新增进程。

**Step 4: 构建并验证 NSIS 与便携 EXE**

Run:

```powershell
powershell -NoProfile -File .\scripts\build-release.ps1
powershell -NoProfile -File .\scripts\smoke-test-release.ps1
```

Expected: NSIS 安装包和原始 Tauri EXE生成；冒烟成功且无新增进程残留。若 MSI 需要额外系统组件，本阶段不以 MSI 阻塞 NSIS 发布。

**Step 5: 更新 README**

README 明确区分 Python 当前版、2.0 Alpha、NSIS 安装包和便携候选的适用条件。只有本任务验证通过才把 2.0 标为可测试版本。

**Step 6: Commit**

```powershell
git add scripts tests/release src-tauri/tauri.conf.json README.md
git commit -m "发布：生成 BatchRename 2.0 Windows 候选版本"
```

---

### Task 18: 终审、兼容核对与阶段交付

**Files:**
- Create: `docs/release/2.0.0-alpha.1-checklist.md`
- Create: `CHANGELOG.md`
- Modify: `README.md`
- Modify: `Python/README.md`

**Step 1: 按设计完成逐项核对**

核对公开功能矩阵、15 条模板、Python 替换引用、扫描总量、冲突状态、安全执行、旧日志、撤回、三态主题、响应式布局、窗口焦点和发行产物。每项记录自动化证据或人工检查结果。

**Step 2: 运行最终测试**

Run:

```powershell
npm run test
npm run build
cargo fmt --manifest-path src-tauri/Cargo.toml -- --check
cargo clippy --manifest-path src-tauri/Cargo.toml --all-targets -- -D warnings
cargo test --manifest-path src-tauri/Cargo.toml
npx playwright test
python -m pytest tests/compat tests/release -q
cd Python
python -m compileall -q batch_rename tests tools main.py
python -m pytest -q
cd ..
git diff --check
```

Expected: 全部命令退出码为 0，无跳过的安全兼容项。

**Step 3: 真实产物复核**

在 Windows 中文路径、深层目录和包含冲突的测试数据上完成扫描、预览、执行、日志读取、撤回闭环。记录安装包和便携 EXE 的大小、哈希与窗口启动结果。

**Step 4: 更新产品说明与中文日志**

根 README 只描述已经通过验证的 2.0 Alpha 能力；Python README 保持其自身使用说明。根 CHANGELOG 记录架构、兼容差异、性能数据、测试数量和产物信息，不写成文件变更清单。

**Step 5: Commit**

```powershell
git add docs/release CHANGELOG.md README.md Python/README.md
git commit -m "发布：完成 2.0 Alpha 兼容与性能终审"
```

**Step 6: 保持本地交付**

Run:

```powershell
git status --short
git log --oneline --decorate -20
git rev-list --left-right --count origin/main...HEAD
```

Expected: 工作区干净，所有提交位于 `main`，只报告领先远端数量；不得执行 `git push`。
