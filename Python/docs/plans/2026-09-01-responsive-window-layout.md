# Responsive Window Layout Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Adapt the application window and internal workbench to standard, ultrawide, and portrait displays while preserving a 960×680 minimum and introducing a ChatGPT App-inspired compact navigation drawer.

**Architecture:** Add pure geometry and breakpoint functions, then keep monitor detection as a thin Windows/fallback adapter. Refactor the existing left workflow rail so the same controls can switch between normal grid placement and a compact in-window drawer without recreating widgets or losing application state. Recalculate table columns and floating panel anchors only when the responsive mode or client dimensions materially change.

**Tech Stack:** Python 3.11+, Tkinter/ttk, ctypes Win32 monitor APIs, pytest, PyInstaller.

---

### Task 1: Add pure screen classification and window geometry

**Files:**
- Modify: `batch_rename/app.py`
- Modify: `tests/test_app.py`

**Step 1: Write failing geometry tests**

Add tests for a `calculate_window_layout(work_area)` pure function and returned immutable layout data. Cover:

```python
assert calculate_window_layout((0, 0, 1920, 1080)).geometry == "960x680+480+200"
assert calculate_window_layout((0, 0, 2560, 1440)).geometry == "1280x720+640+360"
assert calculate_window_layout((0, 0, 3840, 2160)).size == (1920, 1080)
assert calculate_window_layout((0, 0, 3440, 1440)).screen_kind == "ultrawide"
assert calculate_window_layout((0, 0, 1080, 1920)).screen_kind == "portrait"
```

Also cover 5120×1440, negative monitor coordinates and a work area smaller than 960×680.

**Step 2: Run and verify RED**

Run: `python -m pytest tests/test_app.py -q`

Expected: import or attribute failures because the layout engine does not exist.

**Step 3: Implement minimal pure functions**

Add a frozen `WindowLayout` dataclass with `screen_kind`, `width`, `height`, `x`, `y`, `layout_mode`, `size`, and `geometry`. Implement the confirmed ratio thresholds and standard/ultrawide/portrait formulas, then center and clamp the result.

Add `layout_mode_for_width(width)` returning `compact`, `standard`, or `spacious` at 1120 and 1440 breakpoints.

**Step 4: Run focused tests and commit**

Run: `python -m pytest tests/test_app.py -q`

Commit:

```text
窗口：建立屏幕分类与初始尺寸计算引擎
```

### Task 2: Detect the pointer monitor and apply initial geometry

**Files:**
- Modify: `batch_rename/app.py`
- Modify: `tests/test_app.py`

**Step 1: Write adapter and initialization tests**

Inject a work-area provider into `BatchRenameApp`, then assert the root receives the expected initial geometry for standard, ultrawide and portrait work areas while `minsize()` remains `(960, 680)`.

**Step 2: Run and verify RED**

Run the new focused tests and confirm the constructor still hardcodes `960x680`.

**Step 3: Implement monitor-under-pointer detection**

On Windows use `GetCursorPos`, `MonitorFromPoint` and `GetMonitorInfoW`. Return `(left, top, right, bottom)`; fall back to Tk virtual desktop on API or platform failure.

Accept an optional provider in the application constructor for deterministic tests. Apply `calculate_window_layout` before building widgets and store `initial_window_layout`.

**Step 4: Verify and commit**

Commit:

```text
窗口：按当前显示器工作区自适应初始尺寸
```

### Task 3: Add debounced responsive modes and result-column policies

**Files:**
- Modify: `batch_rename/app.py`
- Modify: `tests/test_app.py`

**Step 1: Write failing mode-transition tests**

Test `compact`, `standard`, and `spacious` mode application. Assert rail widths of approximately 64/270/300, preserve the same entry widget instances and variables across transitions, and verify result columns receive mode-specific widths without hiding type, old name, new name or status.

**Step 2: Implement responsive controller**

Bind `<Configure>` on the root and debounce with `after(120, ...)`. Store the pending callback id and current mode. Reapply only when mode or client dimensions change meaningfully.

Move table-width dictionaries into named policies and update existing columns in place. Reposition an open floating panel after each applied layout.

**Step 3: Run tests and commit**

Commit:

```text
界面：增加三档响应式布局与结果列宽策略
```

### Task 4: Build compact navigation and workflow drawer

**Files:**
- Modify: `batch_rename/app.py`
- Modify: `tests/test_app.py`

**Step 1: Write failing compact-navigation tests**

Assert compact mode shows a 64-pixel navigation strip and hides the full rail from grid placement. Opening the workflow drawer must place the existing `workflow_rail` over the body without recreating `search_entry`; repeated click, Escape, result click, template opening or settings opening must close it.

Assert standard/spacious transitions restore the full rail and close the drawer.

**Step 2: Implement compact strip and drawer controller**

Create the compact strip once with workflow, regex-template and settings actions. Switch the existing full rail between grid placement and `place` overlay. Generalize overlay close behavior so only one of workflow drawer, regex templates or settings can be active.

Keep busy-state controls locked; closing the drawer remains allowed.

**Step 3: Verify float-panel bounds**

At 960×680 and 200% Tk scaling, open each overlay and assert its bottom/right edge stays inside the body. Resize through all three modes while preserving search, replacement, match snapshot and preview state.

**Step 4: Run tests and commit**

Commit:

```text
交互：构建紧凑导航与互斥工作流抽屉
```

### Task 5: Update product guidance and responsive screenshots

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `batch_rename/app.py`
- Replace: `docs/images/batch-rename-main.png`
- Create: `docs/images/batch-rename-compact.png`
- Modify: `tests/test_documentation.py`

**Step 1: Update help and README**

Explain automatic standard/ultrawide/portrait sizing, the three internal modes, compact navigation drawer and state-preserving resize behavior. Keep formulas and implementation diagnosis in CHANGELOG, not README.

**Step 2: Capture real standard and compact views**

Capture a current standard preview and a compact/portrait-style view with the workflow drawer open. Do not execute renames.

**Step 3: Verify documentation assets**

Require the new compact screenshot in documentation tests and run stale-text checks.

**Step 4: Commit**

```text
文档：介绍多分辨率适配与紧凑工作流
```

### Task 6: Review, verify and build the single-file release

**Files:**
- Verify all source, test, documentation and build artifacts

**Step 1: Request code review**

Review the complete branch against the design document, focusing on monitor geometry, resize state preservation, compact overlay mutual exclusion and high-DPI bounds. Fix every Critical or Important issue with regression coverage.

**Step 2: Run final checks**

```powershell
python -m compileall -q batch_rename tests main.py
python -m pytest -q
git diff --check
git status --short
```

Expected: all commands succeed and the committed worktree is clean.

**Step 3: Build and smoke-test**

Run `build.ps1`, start only the new `dist\BatchRename.exe`, verify a visible `批量重命名工具` window and stop only the newly launched PIDs. Record final size and SHA-256 in CHANGELOG, then copy the verified artifact to the main checkout `dist` directory after validating both paths.

**Step 4: Commit release verification**

```text
发布：记录响应式工作台完整验证结果
```

Do not push unless the user explicitly requests it for this task.
