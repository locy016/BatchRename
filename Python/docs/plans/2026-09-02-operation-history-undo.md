# 操作日志与撤回管理实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为每次批量重命名建立可持久化、可查询的操作档案，并提供经过整批安全预检、支持中断续查的撤回管理中心。

**Architecture:** 新增独立 `history.py` 负责档案模型、JSON 序列化、原子保存、历史加载和筛选；`core.py` 增加只依赖路径与档案记录的撤回预检和执行器。主界面在确认执行前创建日志，通过进度回调逐项持久化，并用一个双页面管理中心承载撤回与日志查询。现有扫描、预览和执行模型保持兼容。

**Tech Stack:** Python 3.11+、dataclasses、JSON、pathlib、Tkinter/ttk、pytest、PyInstaller。

---

### Task 1: 建立操作档案模型与原子存储

**Files:**
- Create: `batch_rename/history.py`
- Create: `tests/test_history.py`
- Modify: `batch_rename/__init__.py`

**Step 1: Write the failing tests**

覆盖：

```python
def test_operation_log_round_trips_all_rule_and_item_fields(tmp_path): ...
def test_operation_store_saves_one_atomic_json_file_per_operation(tmp_path): ...
def test_operation_store_loads_newest_first_and_isolates_corrupt_files(tmp_path): ...
def test_operation_store_marks_running_logs_as_interrupted_on_load(tmp_path): ...
def test_filter_operations_matches_root_rule_identifier_and_status(): ...
```

档案使用字符串枚举描述执行状态和撤回状态；逐项记录保留原路径、目标路径、类型、执行结果、执行说明、撤回结果及撤回说明。

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_history.py -q`

Expected: FAIL because `batch_rename.history` does not exist.

**Step 3: Write minimal implementation**

实现：

- `OperationStatus`、`UndoStatus`；
- `OperationItem`、`OperationLog`，含统计属性和 `to_dict` / `from_dict`；
- `OperationStore(directory)` 的 `create`、`save`、`load`、`load_all`；
- `.tmp` 同目录写入后 `Path.replace` 的原子保存；
- 损坏档案转换为只读错误记录，不影响其他文件；
- `filter_operations` 的大小写无关关键词和状态筛选；
- `default_operation_directory()` 返回 `%LOCALAPPDATA%\BatchRename\operations`。

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_history.py -q`

Expected: PASS.

**Step 5: Commit**

```powershell
git add -- batch_rename/history.py batch_rename/__init__.py tests/test_history.py
git commit -m "日志：建立原子操作档案存储"
```

### Task 2: 把执行过程接入可恢复日志

**Files:**
- Modify: `batch_rename/history.py`
- Modify: `batch_rename/app.py:3781-3855`
- Modify: `tests/test_history.py`
- Modify: `tests/test_app.py`

**Step 1: Write the failing tests**

增加应用测试：确认执行前成功创建 `准备中` 档案；逐项进度把记录写入档案；完成后状态为已完成或部分失败；首次保存失败时不调用执行器；执行中保存失败时停止后续处理并保留错误说明。

为避免让 UI 负责业务拼装，在 `history.py` 提供：

```python
def create_operation_log(scan, matches, options) -> OperationLog: ...
def append_execution_record(log, record) -> None: ...
def finalize_operation(log) -> None: ...
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_history.py tests/test_app.py -k "operation_log or execution_journal" -q`

Expected: FAIL because execution does not create or update a persistent journal.

**Step 3: Write minimal implementation**

- `BatchRenameApp` 接受可注入的 `operation_store`，默认使用本地操作目录。
- `_confirm_execute` 在启动线程前创建并保存日志；失败时显示错误且不改变磁盘。
- 后台执行进度同步追加记录并保存；保存异常通过专用异常中止执行循环。
- 完成消息同时携带 `ExecutionResult` 和最新档案，刷新“结果详情”与历史缓存。
- 日志保存不改变现有 `ExecutionResult` 公共接口。

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_history.py tests/test_app.py -k "operation_log or execution_journal" -q`

Expected: PASS.

**Step 5: Commit**

```powershell
git add -- batch_rename/history.py batch_rename/app.py tests/test_history.py tests/test_app.py
git commit -m "执行：为批量改名写入可恢复日志"
```

### Task 3: 实现整批撤回预检与逆序恢复

**Files:**
- Modify: `batch_rename/models.py`
- Modify: `batch_rename/core.py`
- Modify: `batch_rename/history.py`
- Create: `tests/test_undo.py`

**Step 1: Write the failing tests**

覆盖：

```python
def test_undo_restores_nested_directory_and_file_in_reverse_execution_order(tmp_path): ...
def test_undo_preflight_blocks_entire_batch_when_current_item_is_missing(tmp_path): ...
def test_undo_preflight_blocks_entire_batch_when_original_name_is_occupied(tmp_path): ...
def test_undo_handles_case_only_rename(tmp_path): ...
def test_undo_stops_after_runtime_failure_and_can_retry_remaining_items(tmp_path): ...
def test_fully_undone_operation_cannot_run_again(tmp_path): ...
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_undo.py -q`

Expected: FAIL because undo APIs do not exist.

**Step 3: Write minimal implementation**

新增：

- `UndoCheckItem`、`UndoCheckResult`、`UndoResult`；
- `preflight_undo(operation)`：推导嵌套目录改名后的当前路径，检查缺失、占用、类型与重复撤回，任何风险使 `safe=False`；
- `undo_operation(operation, progress=None, save=None)`：仅在预检通过时运行，按成功记录逆序恢复，逐项更新撤回状态；
- 运行期失败立即停止，已恢复项不重复处理，后续可重新预检剩余项；
- 复用 `_rename_case_only`，不覆盖、不删除任何路径。

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_undo.py tests/test_execute.py -q`

Expected: PASS and existing execution tests remain green.

**Step 5: Commit**

```powershell
git add -- batch_rename/models.py batch_rename/core.py batch_rename/history.py tests/test_undo.py tests/test_execute.py
git commit -m "撤回：实现整批预检与逆序恢复"
```

### Task 4: 建立双页面操作管理中心

**Files:**
- Modify: `batch_rename/app.py:2010-2020`
- Modify: `batch_rename/app.py:3830-3955`
- Modify: `tests/test_app.py:900-1020`

**Step 1: Write the failing tests**

覆盖：菜单项去掉“开发中”并启用；两个入口打开同一个受管理窗口并切换到正确页面；日志列表按时间倒序；关键词和状态筛选；选择记录显示规则统计和逐项明细；撤回按钮必须经过最新预检；撤回完成刷新状态；浅色与深色切换同步到已打开管理中心。

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_app.py -k "history_center or undo_manager or operation_log_menu" -q`

Expected: FAIL because menu items are disabled placeholders.

**Step 3: Write minimal implementation**

- 菜单标签改为“撤回管理”“操作日志”并绑定命令。
- 新建 `_show_history_center(page)`，使用 `ManagedDialogs` 创建一个可调整大小、同屏聚焦的非模态窗口。
- Notebook 两页共享历史缓存与选中档案；使用 Treeview 展示操作和项目明细。
- 日志页提供关键词、状态选择和刷新。
- 撤回页提供安全说明、检查结果、“安全检查”和警示样式“确认撤回”；检查快照与档案更新时间一致时才启用执行。
- 撤回在线程中运行，显示逐项进度并通过消息队列刷新窗口，不阻塞主界面。

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_app.py -k "history_center or undo_manager or operation_log_menu" -q`

Expected: PASS.

**Step 5: Commit**

```powershell
git add -- batch_rename/app.py tests/test_app.py
git commit -m "界面：启用撤回管理与操作日志中心"
```

### Task 5: 完成浮动面板主题收尾并重建产品说明

**Files:**
- Modify: `batch_rename/__init__.py`
- Modify: `batch_rename/app.py`
- Replace: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `tools/capture_product_previews.py`
- Modify: `docs/images/batch-rename-main.png`
- Modify: `docs/images/batch-rename-regex-templates.png`
- Create: `docs/images/batch-rename-operation-history.png`
- Modify: `docs/images/batch-rename-workflow.svg`
- Modify: `tests/test_app.py`
- Modify: `tests/test_documentation.py`

**Step 1: Write the failing tests**

- 浮动面板阴影与边框随主题切换；
- README 版本为 `1.1.0-beta.2`，包含日志、撤回、整批预检和本地档案位置；
- README 不包含“撤回管理（开发中）”“操作日志（开发中）”或“尚未提供自动撤回”；
- 三张真实界面截图和流程图均被引用；
- 帮助与关于页面只描述真实能力。

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_app.py tests/test_documentation.py -k "theme or readme or about or help" -q`

Expected: FAIL on stale product text and missing history preview.

**Step 3: Write minimal implementation**

- 版本更新为 `1.1.0-beta.2`。
- 完成浮动面板边框、阴影的浅色/深色运行时更新。
- 完整替换 README，按当前产品能力重建章节，不沿用旧残留段落。
- 更新帮助、关于和流程图，将“执行 → 写入日志 → 安全检查 → 撤回”关系说清楚。
- 截图工具使用临时日志目录注入演示档案，不扫描或修改真实目录；生成主工作台、正则浮层和操作管理中心截图。
- CHANGELOG 用中文记录数据边界、异常策略、实现取舍、测试和构建结果。

**Step 4: Run focused tests**

Run: `python -m pytest tests/test_app.py tests/test_documentation.py -q`

Expected: PASS.

**Step 5: Commit**

```powershell
git add -- batch_rename/__init__.py batch_rename/app.py README.md CHANGELOG.md tools/capture_product_previews.py docs/images tests/test_app.py tests/test_documentation.py
git commit -m "文档：重建日志撤回版产品说明与界面预览"
```

### Task 6: 完整验证、构建与本地交付

**Files:**
- Modify: `CHANGELOG.md`
- Generated: `dist/BatchRename.exe`

**Step 1: Run full verification**

Run: `python -m compileall -q batch_rename tests tools main.py`

Run: `python -m pytest -q`

Run: `git diff --check`

Expected: compilation exits 0, all tests pass, no whitespace errors.

**Step 2: Run source UI smoke test**

只跟踪本次 `python main.py` 新增进程，确认主窗口、浮动面板、操作日志页与撤回页可以打开并获得焦点；验证后只结束本次新增进程。

**Step 3: Build single-file application**

Run: `powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1`

若现有 `dist\BatchRename.exe` 正在运行导致覆盖失败，不结束使用者进程；改用隔离构建目录验证最新单文件，并明确报告正式路径仍被占用。

**Step 4: Run packaged smoke test**

记录构建产物大小和 SHA-256，只启动本次新产物，确认可见窗口与管理中心后停止本次新增进程。

**Step 5: Record evidence and commit**

把测试数量、截图尺寸、构建大小、哈希、冒烟 PID 范围及任何占用情况写入 CHANGELOG。

```powershell
git add -- CHANGELOG.md
git commit -m "发布：记录日志撤回版本完整验证结果"
```

**Step 6: Leave push to the user**

确认工作区和本地提交，只提供人工推送所需信息，不执行任何推送动作。
