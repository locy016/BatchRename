# Menu Navigation, Two-Stage Preview, and Dialog Management Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a release-oriented 960×680 workbench with a complete left-side rename workflow, non-duplicated top menus, mutually exclusive floating tools, genuine scan/preview stages, focused same-monitor dialogs, and a complete About window.

**Architecture:** Split filesystem discovery from rename preview in `core.py` while preserving the existing `scan(ScanOptions)` compatibility wrapper and the current execution engine. Refactor `BatchRenameApp` into explicit search-snapshot and preview states, place workflow controls in a fixed left rail, and keep results/progress in a flexible right workspace. Use in-window floating panels for templates/settings and a reusable manager for actual `Toplevel` dialogs.

**Tech Stack:** Python 3.11+, Tkinter/ttk, pathlib, ctypes Win32 monitor APIs with cross-platform fallback, pytest, PyInstaller.

---

### Task 1: Add an independent match snapshot model and filesystem search

**Files:**
- Modify: `batch_rename/models.py`
- Modify: `batch_rename/core.py`
- Modify: `tests/test_scan.py`

**Step 1: Write failing discovery tests**

Add imports for `MatchOptions` and `search_matches`, then add tests equivalent to:

```python
def test_search_matches_does_not_require_replacement(tmp_path):
    source = touch(tmp_path / "项目合同.docx")

    result = search_matches(MatchOptions(tmp_path, "项目"))

    assert [item.source for item in result.items] == [source]
    assert result.search == "项目"
    assert result.use_regex is False


def test_search_matches_validates_regex_without_replacement(tmp_path):
    with pytest.raises(RuleError, match="正则表达式"):
        search_matches(MatchOptions(tmp_path, "(" , use_regex=True))
```

Retain depth, object-type, symlink, root exclusion, unreadable-directory and natural-order assertions at discovery level.

**Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_scan.py -q`

Expected: FAIL because `MatchOptions`, `MatchedItem`, `MatchResult`, and `search_matches` do not exist.

**Step 3: Implement minimal discovery types**

Add immutable options and matched-item models plus a result container:

```python
@dataclass(frozen=True, slots=True)
class MatchOptions:
    root: Path
    search: str
    use_regex: bool = False
    max_depth: int | None = None
    include_files: bool = True
    include_dirs: bool = True


@dataclass(frozen=True, slots=True)
class MatchedItem:
    source: Path
    kind: ItemKind


@dataclass(slots=True)
class MatchResult:
    root: Path
    search: str
    use_regex: bool
    items: list[MatchedItem] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
```

Implement `search_matches(options)` by moving root/depth/type validation and directory traversal out of `scan`. Validate search with `RenameRule(search, "", use_regex=...)`, call `matches` on complete names, and append `MatchedItem` without calculating a target.

**Step 4: Run focused and full core tests**

Run: `python -m pytest tests/test_scan.py tests/test_rules.py -q`

Expected: PASS.

**Step 5: Commit**

```text
核心：建立独立的名称匹配快照
```

The Chinese body must explain why replacement is excluded and how scope/search errors are retained.

### Task 2: Build rename previews from a snapshot without rereading the directory

**Files:**
- Modify: `batch_rename/models.py`
- Modify: `batch_rename/core.py`
- Modify: `tests/test_scan.py`

**Step 1: Write failing preview tests**

Add tests for a new `build_preview` function:

```python
def test_build_preview_uses_snapshot_without_scandir(tmp_path, monkeypatch):
    source = touch(tmp_path / "旧版.txt")
    snapshot = search_matches(MatchOptions(tmp_path, "旧版"))
    monkeypatch.setattr(os, "scandir", lambda *_: pytest.fail("不得重新扫描"))

    result = build_preview(snapshot, "新版")

    assert result.candidates[0].source == source
    assert result.candidates[0].new_name == "新版.txt"


def test_legacy_scan_composes_search_and_preview(tmp_path):
    source = touch(tmp_path / "旧版.txt")
    result = scan(ScanOptions(tmp_path, "旧版", "新版"))
    assert result.candidates[0].source == source
```

Keep explicit tests for unchanged names, protected extensions, existing targets, duplicate targets and invalid names.

**Step 2: Run and verify RED**

Run: `python -m pytest tests/test_scan.py -q`

Expected: FAIL because `build_preview` does not exist.

**Step 3: Extract preview calculation**

Implement:

```python
def build_preview(
    snapshot: MatchResult,
    replacement: str,
    *,
    rename_extension: bool = False,
) -> ScanResult:
    rule = RenameRule(
        snapshot.search,
        replacement,
        use_regex=snapshot.use_regex,
        rename_extension=rename_extension,
    )
    ...
```

Calculate targets and statuses only from `snapshot.items`. Preserve existing conflict, duplicate, unchanged and extension-protection explanations. Refactor `scan(options)` into a compatibility composition of `search_matches` and `build_preview` so public behavior and all execution tests remain unchanged.

**Step 4: Run all core tests**

Run: `python -m pytest tests/test_scan.py tests/test_execute.py tests/test_rules.py -q`

Expected: PASS.

**Step 5: Commit**

```text
核心：从匹配快照生成安全重命名预览
```

### Task 3: Introduce explicit application search and preview states

**Files:**
- Modify: `batch_rename/app.py`
- Modify: `tests/test_app.py`

**Step 1: Write failing state-transition tests**

Add helpers that create `MatchResult` and `ScanResult`, then assert:

```python
def test_replacement_change_keeps_match_snapshot_but_invalidates_preview(tk_window):
    app = BatchRenameApp(tk_window)
    app._last_matches = match_result()
    app._last_scan = scan_result()

    app.replacement_var.set("新名称")

    assert app._last_matches is not None
    assert app._last_scan is None


def test_search_change_invalidates_both_stages(tk_window):
    ...
    app.search_var.set("另一规则")
    assert app._last_matches is None
    assert app._last_scan is None
```

Test state transitions `idle → searching → matched → previewing → previewed → executing`, including enablement rules for preview and confirmation commands.

**Step 2: Run and verify RED**

Run: `python -m pytest tests/test_app.py -q`

Expected: FAIL because the app stores only `_last_scan` and one scan action.

**Step 3: Implement separate workers and messages**

Add `_last_matches`, `_start_search`, `_search_worker`, `_handle_search_done`, `_start_preview`, `_preview_worker`, and `_handle_preview_done`. Keep disk discovery and large preview generation off the UI thread. Queue message kinds must be explicit (`match_done`, `preview_done`, `execute_done`).

Split traced variables into:

- discovery inputs: directory, depth mode/value, search, regex mode, include files/directories;
- preview inputs: replacement and extension protection;
- rendering input: preview limit.

Add one `_sync_command_states()` method as the only source of truth for left-menu and native-menu enabled states.

**Step 4: Render a matched-only table**

When `_last_matches` exists and `_last_scan` is absent, insert values:

```python
(
    item.kind.value,
    str(item.source.parent),
    item.source.name,
    "",
    "等待结果预览",
    "填写替换内容后生成结果预览",
)
```

Hide the new-name overlay for blank cells. Previewed rows continue to use the current status tags and accent new-name overlay.

**Step 5: Run tests and commit**

Run: `python -m pytest tests/test_app.py tests/test_scan.py -q`

Expected: PASS.

Commit:

```text
交互：拆分扫描匹配与结果预览状态
```

### Task 4: Replace the main layout with a left workflow rail and non-duplicated top menu

**Files:**
- Modify: `batch_rename/app.py`
- Modify: `tests/test_app.py`

**Step 1: Write failing structure tests**

Assert the native menu labels are exactly `文件`, `功能`, `帮助`; global menu contents do not include left workflow labels except no duplicates; development entries include `（开发中）` and are disabled.

Assert the left rail contains, in order, directory selection, mode, search, scan, replacement, preview and execution controls. Assert the header no longer has a help button and the right workspace contains no action button row.

**Step 2: Run and verify RED**

Run: `python -m pytest tests/test_app.py -q`

Expected: FAIL because the current interface has no native menu or left workflow rail.

**Step 3: Build the native menu**

Create one `tk.Menu` on the root:

- `文件`: `退出`;
- `功能`: `结果详情`, separator, `撤回管理（开发中）`, `操作日志（开发中）`;
- `帮助`: `使用说明`, `关于`.

Keep result details disabled until an execution result exists. Keep undo/log entries permanently disabled in this version. Bind F1 to help without duplicating help in the left rail.

**Step 4: Build the left workflow rail**

Replace the current settings/actions layout with a fixed-width `Workflow.TFrame`. Use clear numbered steps and these instance attributes:

```python
self.directory_entry
self.directory_select_button
self.plain_mode_radio
self.regex_mode_radio
self.search_entry
self.search_button
self.replacement_entry
self.preview_button
self.execute_button
```

Place scan/preview/execute commands only here. Enter in the search field calls `_start_search`; Enter in the replacement field calls `_start_preview`.

Move stats, preview limit display, result table, progress and status to the flexible right workspace. Keep 960×680 and verify requested dimensions do not exceed it.

**Step 5: Run tests and commit**

Run: `python -m pytest tests/test_app.py -q`

Expected: PASS.

Commit:

```text
界面：构建左侧流程工作台与全局菜单
```

### Task 5: Add mutually exclusive in-window template and settings panels

**Files:**
- Modify: `batch_rename/app.py`
- Modify: `tests/test_app.py`

**Step 1: Write failing floating-panel tests**

Test a controller contract:

```python
app._toggle_tool_panel("settings")
assert app.active_tool_panel == "settings"
assert app.settings_panel.winfo_manager() == "place"

app._toggle_tool_panel("templates")
assert app.active_tool_panel == "templates"
assert app.settings_panel.winfo_manager() == ""
assert app.templates_panel.winfo_manager() == "place"

app.root.event_generate("<Escape>")
assert app.active_tool_panel is None
```

Also test repeated clicking closes the active panel and clicking the right workspace closes it.

**Step 2: Run and verify RED**

Run: `python -m pytest tests/test_app.py -q`

Expected: FAIL because templates use a `Toplevel` and settings are permanently visible.

**Step 3: Implement the controller and panels**

Add two bottom-left menu controls with text plus symbols (`正则模板`, `设置`). Create white card frames as children of the main shell and show them using `place`, anchored immediately to the right of the rail and clamped inside the client area.

Move existing template selection widgets into `templates_panel` without changing the template data. Applying a template fills mode/search/replacement/extension settings, invalidates matching state and closes the panel.

Move depth, object types, extension protection and preview limit into `settings_panel`. Update tooltips to explain which stage each option invalidates.

**Step 4: Run tests and commit**

Run: `python -m pytest tests/test_app.py tests/test_examples.py -q`

Expected: PASS.

Commit:

```text
交互：增加互斥收缩的模板与设置浮动面板
```

### Task 6: Centralize same-monitor dialog placement, focus and single instances

**Files:**
- Modify: `batch_rename/app.py`
- Modify: `tests/test_app.py`

**Step 1: Write pure geometry and manager tests**

Add a pure helper test:

```python
def test_centered_dialog_geometry_is_clamped_to_parent_monitor():
    geometry = centered_dialog_geometry(
        parent=(2100, 100, 960, 680),
        dialog=(760, 640),
        work_area=(1920, 0, 3840, 1040),
    )
    assert geometry == "760x640+2200+120"
```

Add Tk tests proving that opening the same key twice returns the same `Toplevel`, `transient()` points to the root, closing unregisters it, and modal dialogs own the grab.

**Step 2: Run and verify RED**

Run: `python -m pytest tests/test_app.py -q`

Expected: FAIL because dialogs are independently created and not managed.

**Step 3: Implement monitor bounds and dialog manager**

Implement a Windows monitor-work-area helper with `MonitorFromWindow` and `GetMonitorInfoW`; use `winfo_vroot*` fallback outside Windows or if ctypes calls fail. Keep geometry arithmetic in a pure function for deterministic tests.

Add `ManagedDialogs` with `open`, `focus_existing`, and `close` behavior. Every managed window must be `transient(root)`, centered after `update_idletasks`, clamped, lifted, and focused after idle. Only selection dialogs use `grab_set`; informational dialogs remain non-modal. Restore focus to the root on close.

Convert help and result details to the manager. System message boxes retain `parent=self.root`.

**Step 4: Run tests and commit**

Run: `python -m pytest tests/test_app.py -q`

Expected: PASS.

Commit:

```text
窗口：统一多屏定位、焦点与单实例管理
```

### Task 7: Add release-oriented About information and version metadata

**Files:**
- Modify: `batch_rename/__init__.py`
- Modify: `batch_rename/app.py`
- Modify: `tests/test_app.py`
- Modify: `tests/test_build_config.py`

**Step 1: Write failing version and About tests**

Assert `__version__ == "1.1.0-beta.1"`. Open About and assert its visible text variables/content include:

- current implemented capabilities;
- `撤回管理` and `操作日志` marked in development;
- rapid-development statement;
- backup and user-confirmation disclaimer;
- `lo.c@live.cn`;
- exact version.

Assert the email is selectable/read-only text and no `mailto` command is bound.

**Step 2: Run and verify RED**

Run: `python -m pytest tests/test_app.py tests/test_build_config.py -q`

Expected: FAIL because the package remains 1.0.0 and no About window exists.

**Step 3: Implement About cards**

Set `__version__ = "1.1.0-beta.1"` and import it into the app. Build About with brand icon/title, version badge, current features, development roadmap, safety disclaimer and contact section. Use the managed dialog service and current visual styles.

Add package version metadata to the PyInstaller build only if supported without a new runtime dependency; do not invent a Windows product-version format that rejects the prerelease string. The visible About value remains the canonical version.

**Step 4: Run tests and commit**

Run: `python -m pytest tests/test_app.py tests/test_build_config.py -q`

Expected: PASS.

Commit:

```text
产品：增加关于信息与预发行版本标识
```

### Task 8: Update product guidance, perform visual QA, and build the beta single file

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `batch_rename/app.py`
- Replace: `docs/images/batch-rename-main.png`

**Step 1: Update current product documentation**

Rewrite README interface/use sections for the left workflow and genuine scan/preview stages. Explain the top menu, floating tools, development placeholders, About contents and beta status in product language. Keep implementation decisions and debugging history in `CHANGELOG.md`.

Update built-in help to match exact labels and state invalidation rules. Do not describe undo/log as implemented.

**Step 2: Run stale-text, syntax and full tests**

Run:

```powershell
rg -n '扫描范围占|查找与替换输入框保持在同一行|点击框后的“扫描”' README.md batch_rename -S
python -m compileall -q batch_rename tests main.py
python -m pytest -q
git diff --check
```

Expected: no obsolete current-product text; all commands exit 0.

**Step 3: Perform Windows visual verification**

At 960×680 verify:

- every workflow step fits in the left rail;
- no old action buttons remain in the right workspace;
- native top menus do not duplicate the left workflow;
- settings/templates alternate and collapse;
- matched-only rows and preview rows are visually distinct;
- About/help/details stay on the main window monitor and receive focus;
- maximize gives added space to results.

Capture a real two-stage scan/preview screenshot and replace `docs/images/batch-rename-main.png`.

**Step 4: Build and smoke-test**

Run: `powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1`

Expected: tests pass inside the build and `dist\BatchRename.exe` is created.

Start only the new artifact, verify a visible `批量重命名工具` window, stop only newly launched PIDs, and record size/SHA-256. Copy the verified artifact to `D:\ProjectFolder\BatchRename\dist\BatchRename.exe` after validating the exact destination.

**Step 5: Commit release documentation**

```text
文档：介绍两阶段重命名工作台与菜单导航
发布：记录 1.1.0-beta.1 完整验证结果
```

Do not push unless the user explicitly asks during this task. Preserve the feature worktree until integration is chosen.
