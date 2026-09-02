# Compact Result Table Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace repeated absolute paths and wide text-only metadata columns with relative directories, responsive name columns, semantic icons, hover explanations and click-through result details.

**Architecture:** Keep complete paths and user-facing text in the existing result models and Treeview values. Add pure formatting and width functions, then layer reusable Canvas icons over the visible type, status and detail cells in the same way the existing new-name overlay preserves per-column styling. Store display details by Treeview row id so icon clicks can open the existing managed, monitor-aware dialog without touching scan or execution data.

**Tech Stack:** Python 3.11+, Tkinter/ttk Canvas and Treeview, pathlib, pytest, PyInstaller.

**Repository constraint:** Work directly on local `main` as explicitly requested. Do not create a branch or worktree and do not push.

---

### Task 1: Display directories relative to the selected root

**Files:**
- Modify: `batch_rename/app.py`
- Modify: `tests/test_app.py`

**Step 1: Write failing pure-function tests**

Import a new `result_parent_text(root, source)` helper and cover:

```python
assert result_parent_text(Path("C:/资料"), Path("C:/资料/合同.docx")) == "（根目录）"
assert result_parent_text(Path("C:/资料"), Path("C:/资料/合同/2026/清单.xlsx")) == r"合同\2026"
```

Also cover a source outside the root and expect the complete parent path as a safe fallback.

**Step 2: Run and verify RED**

Run: `python -m pytest tests/test_app.py -q -k "result_parent_text"`

Expected: import failure because the helper does not exist.

**Step 3: Implement the formatter and pass the root through rendering**

Use `source.parent.relative_to(root)` and return `（根目录）` for `Path(".")`. Catch `ValueError` and return `str(source.parent)`.

Change:

```python
_fill_matches(tree, items, root=match_result.root)
_fill_tree(tree, items, root=scan_result.root)
```

Both scan rows and preview rows must call the same helper. Direct test helpers must pass an explicit root.

**Step 4: Verify and commit**

Run: `python -m pytest tests/test_app.py -q`

Commit: `界面：结果目录改用根目录相对路径`

### Task 2: Calculate responsive result-column widths

**Files:**
- Modify: `batch_rename/app.py`
- Modify: `tests/test_app.py`

**Step 1: Write failing width-policy tests**

Add tests for `calculate_result_column_widths(total_width, mode)`. Assert:

- `kind`, `status` and `detail` remain fixed narrow columns;
- `parent`, `old` and `new` consume the remaining width;
- `new > old > parent` when extra width is available;
- totals do not exceed the supplied usable width at 720, 980 and 1440 pixels;
- every column remains positive in compact mode.

**Step 2: Run and verify RED**

Run the focused tests and confirm the function is missing.

**Step 3: Implement the pure calculator**

Use fixed widths around 44/48/44 pixels for type/status/detail. Give elastic space to parent/old/new at 26/34/40 percent after mode-specific minimums. If space is below the preferred minimum total, scale only the elastic minima while preserving positive safety bounds.

**Step 4: Apply widths on Treeview resize**

Bind the result Treeview `<Configure>` event to a lightweight method that recalculates only when the available width changes materially. Set all six widths in place, reschedule the new-name overlay and later icon overlay, and remove the old fixed text-column policies.

**Step 5: Verify and commit**

Run the app tests and commit: `界面：名称与相对目录列按可用宽度伸缩`

### Task 3: Draw semantic icons over visible metadata cells

**Files:**
- Modify: `batch_rename/app.py`
- Modify: `tests/test_app.py`

**Step 1: Write failing icon-specification tests**

Define an immutable `ResultIconSpec` and pure `result_icon_spec(column, value)` function. Cover:

- folder and file use distinct neutral shapes;
- ready, unchanged and blocked statuses use distinct shapes and semantic colors;
- detail always uses the information icon and retains its complete tooltip text;
- unknown status uses the blocked fallback.

**Step 2: Run and verify RED**

Confirm the spec function does not exist.

**Step 3: Implement `TreeCellIconOverlay`**

Create pooled Canvas widgets only for visible cells in `kind`, `status` and `detail`. Each canvas must:

- draw the icon from `ResultIconSpec` without image assets;
- use the normal or selected row background;
- keep the row id and column name;
- update its `ToolTip.text` with the complete underlying value;
- forward wheel scrolling;
- select/focus its Treeview row on click;
- call an optional action callback for status and detail.

Schedule refresh on configure, expose, selection, vertical/horizontal scroll and data refresh. Hide unused canvases after every refresh.

**Step 4: Integrate with result rendering**

Instantiate one icon overlay beside `new_name_overlay`. Keep the complete type, status and detail strings in Treeview values, then place icons over those cells. Empty tables must hide both overlay types.

**Step 5: Verify and commit**

Run focused overlay tests and the full app suite. Commit: `界面：用语义图标压缩类型状态与说明列`

### Task 4: Open complete result details from status and info icons

**Files:**
- Modify: `batch_rename/app.py`
- Modify: `tests/test_app.py`

**Step 1: Write failing interaction tests**

Assert every rendered row stores display details containing type, relative directory, original name, new name, status and explanation. Simulate status/detail icon activation and verify:

- the row becomes selected;
- a single managed `result-item-details` window opens;
- all full text is present;
- activating another row refreshes rather than duplicates the window;
- type icons select the row but do not open the window.

**Step 2: Implement row metadata and dialog content**

Rebuild `self._result_row_details` each time the table is filled. Add `_show_result_item_details(item_id, focus_column)` using `ManagedDialogs`; close and rebuild the existing detail instance when the selected row changes so content cannot become stale.

Use read-only labels with selectable name/path fields where useful. Explain the clicked status or detail first, followed by the complete row context. The dialog must not mutate rules or files.

**Step 3: Verify mouse behavior**

Ensure icon clicks do not accidentally trigger the result workspace overlay-close binding before the details window opens. Confirm keyboard and ordinary row selection still work.

**Step 4: Verify and commit**

Run app tests and commit: `交互：状态与说明图标打开完整结果详情`

### Task 5: Update product guidance, screenshot and release artifact

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `batch_rename/app.py`
- Replace: `docs/images/batch-rename-main.png`
- Replace: `docs/images/batch-rename-compact.png`
- Modify: `tests/test_documentation.py` only if new assertions are needed

**Step 1: Update help and README**

Explain relative directory display, fixed semantic icon columns, hover text, click-through details and responsive original/new-name widths. Keep technical overlay and width formulas in CHANGELOG.

**Step 2: Capture real safe previews**

Refresh standard and compact screenshots from the real Tk application using preview-only injected candidates. Include at least one nested relative directory and visible ready/unchanged/blocked icons. Do not execute renames.

**Step 3: Review and verify**

Use `superpowers:requesting-code-review`. Fix Critical and Important findings with regression tests.

Run:

```powershell
python -m compileall -q batch_rename tests main.py
python -m pytest -q
git diff --check
git status --short
```

**Step 4: Build and smoke-test**

Run `build.ps1`, start only the new `dist\BatchRename.exe`, detect a visible `批量重命名工具` window, and stop only PIDs created by this smoke test. Copy the verified artifact to the same main checkout `dist` path, record bytes and SHA-256 in CHANGELOG, and do not push.

**Step 5: Commit**

Commit product documentation and release evidence in detailed Chinese commits. Confirm the final repository remains on `main` with no additional branches or worktrees.
