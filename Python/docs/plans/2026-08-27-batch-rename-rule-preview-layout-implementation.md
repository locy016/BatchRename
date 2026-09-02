# Batch Rename Rule Preview Layout Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refine the 960×680 interface with a 35/65 settings split, 100-row default preview, shared quick-preview actions, one-line statistics, reordered result columns, and an independently colored new-name cell.

**Architecture:** Keep all scan behavior in the existing `_start_scan` path and only add UI bindings that call it. Preserve Treeview as the data and scrolling surface, then add a lightweight visible-cell overlay for the new-name column because ttk row tags cannot color one cell independently. Continue using the current custom ttk theme and immutable scan/result models.

**Tech Stack:** Python 3.13, Tkinter/ttk, pytest, PyInstaller.

---

### Task 1: Lock the 35/65 layout, 100-row default and single-line statistics

**Files:**
- Modify: `tests/test_app.py`
- Modify: `batch_rename/app.py`

**Step 1: Write failing tests**

Create `BatchRenameApp` with the shared Tk fixture and assert:

```python
assert app.settings_frame.grid_columnconfigure(0)["weight"] == 35
assert app.settings_frame.grid_columnconfigure(1)["weight"] == 65
assert not app.settings_frame.grid_columnconfigure(0)["uniform"]
assert app.preview_limit_var.get() == 100
assert app.stats_var.get() == (
    "匹配：0 项 | 可修改：0 项 | 名称未变化：0 项 | 阻止执行：0 项"
)
assert not app.stats_label.cget("wraplength")
```

**Step 2: Run the focused test and verify RED**

Run: `python -m pytest tests/test_app.py -q`

Expected: FAIL because the current layout is 50/50, preview defaults to 10, and statistics start as “尚未扫描”.

**Step 3: Implement the minimal layout contract**

Expose `settings_frame`, set column weights to 35 and 65 in one proportional `uniform` group, initialize the preview limit to 100, initialize the complete zero statistics string, expose `stats_label`, and remove its wrapping constraint. Verify the rendered card widths rather than only inspecting grid configuration. Adjust action-grid weights and compact spacing only as needed to keep all controls on one row at 960 pixels.

**Step 4: Run tests and verify GREEN**

Run: `python -m pytest tests/test_app.py -q`

Expected: PASS and the existing 960×680 request-size test remains green.

**Step 5: Commit**

```text
界面：调整设置比例与单行匹配统计
```

### Task 2: Add a shared quick scan entry point and rename the main action

**Files:**
- Modify: `tests/test_app.py`
- Modify: `batch_rename/app.py`

**Step 1: Write failing interaction tests**

Patch the application instance `_start_scan` method with a counting callable before building or rebinding the shortcut, then assert invoking the compact button calls it once. Generate `<Return>` on the search entry and assert the same method is called. Assert:

```python
assert app.search_scan_button.cget("text") == "扫描"
assert app.scan_button.cget("text") == "结果预览"
```

Extend the busy-state test to require the compact scan button to become disabled and enabled with the other rule inputs.

**Step 2: Run focused tests and verify RED**

Run: `python -m pytest tests/test_app.py -q`

Expected: FAIL because no compact scan button or Enter binding exists and the main button still says “扫描匹配”.

**Step 3: Implement the shared action**

Place a compact `Secondary.TButton` immediately after the search entry, store it as `search_scan_button`, and set its command to `_start_scan`. Bind search-entry Return through a small `_preview_from_search` method that returns `"break"` after calling `_start_scan`, preventing the key from triggering unrelated controls. Rename the main button to “结果预览”. Add the compact button to `_input_widgets` so busy-state locking remains centralized.

**Step 4: Run tests and verify GREEN**

Run: `python -m pytest tests/test_app.py -q`

Expected: PASS.

**Step 5: Commit**

```text
交互：增加查找框快捷扫描与结果预览入口
```

### Task 3: Reorder result columns and preserve candidate mapping

**Files:**
- Modify: `tests/test_app.py`
- Modify: `batch_rename/app.py`

**Step 1: Write failing table tests**

Assert the Treeview columns are:

```python
("kind", "parent", "old", "new", "status", "detail")
```

Insert one `RenameCandidate` through `_fill_tree` and assert the row values are ordered as type, parent path, old name, new name, status and detail. Check that directory and status columns use compact non-stretch widths while parent/name/detail columns stretch.

**Step 2: Run focused tests and verify RED**

Run: `python -m pytest tests/test_app.py -q`

Expected: FAIL because parent currently follows the two name columns.

**Step 3: Implement new column order**

Update columns, headings, width definitions and `_fill_tree` values together. Give parent the largest base width, preserve natural candidate sorting, and keep the existing cell-content tooltip compatible because it derives headings and values from the current Treeview column tuple.

**Step 4: Run tests and verify GREEN**

Run: `python -m pytest tests/test_app.py -q`

Expected: PASS.

**Step 5: Commit**

```text
界面：按目录与名称确认顺序重排结果表
```

### Task 4: Color only visible new-name cells

**Files:**
- Modify: `tests/test_app.py`
- Modify: `batch_rename/app.py`

**Step 1: Write failing overlay tests**

Create a visible test window, insert candidates, update idle tasks, and call the wished-for overlay refresh. Assert the overlay creates a label for a visible item whose text equals the Treeview `new` value and whose foreground is the application accent color. Assert the overlay targets the `new` column after the column reorder and clears labels when the tree is emptied.

**Step 2: Run focused tests and verify RED**

Run: `python -m pytest tests/test_app.py -q`

Expected: FAIL because the new-name overlay does not exist.

**Step 3: Implement the visible-cell overlay**

Create `TreeColumnTextOverlay` with `tree`, `column`, foreground and background inputs. On refresh, use `tree.bbox(item, column)` to find visible cells, reuse a label pool, place labels inside the cell, and hide unused labels. Bind label clicks to select the corresponding row and attach full-text tooltips. Schedule refresh after table fill, configure/expose, mouse-wheel scrolling and scrollbar commands. Store it as `new_name_overlay`.

Do not alter candidate data, tags, sorting or execution selection. Only visible rows receive overlay labels.

**Step 4: Run tests and verify GREEN**

Run: `python -m pytest tests/test_app.py -q`

Expected: PASS.

**Step 5: Commit**

```text
视觉：突出显示结果表中的新名称
```

### Task 5: Refine label and numeric control styles

**Files:**
- Modify: `tests/test_app.py`
- Modify: `batch_rename/app.py`

**Step 1: Write failing style tests**

Assert the preview spinbox is exposed, uses `Modern.TSpinbox`, has centered text, and its style defines focus/active colors. Assert field labels use a dedicated style and the statistics label uses a dedicated one-line style.

**Step 2: Run focused tests and verify RED**

Run: `python -m pytest tests/test_app.py -q`

Expected: FAIL because the preview spinbox is local, values are not centered, and field/stat label styles are not separated.

**Step 3: Implement style refinements**

Add `Field.TLabel` and `MatchStats.TLabel`; apply them consistently to main setting labels and statistics. Expose `preview_spin`, set spinbox justification to center, and refine arrow hover, focus border and disabled colors without increasing the 680-pixel request height.

**Step 4: Run tests and verify GREEN**

Run: `python -m pytest tests/test_app.py -q`

Expected: PASS.

**Step 5: Commit**

```text
视觉：优化文字层级与数值选择组件
```

### Task 6: Update guidance and complete release verification

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `batch_rename/app.py`

**Step 1: Update product guidance**

Describe the 35/65 layout, 100-row preview, Enter/scan/result-preview shared action, complete one-line statistics, new column order and highlighted new name in product language. Update built-in help and tooltips to use the exact current labels. Record the implementation rationale and verification evidence in the Chinese development log.

**Step 2: Run stale-text and syntax checks**

Run: `rg -n '扫描匹配|预览上限.*10|类型、原名称、新名称、所在目录' batch_rename README.md CHANGELOG.md -S`

Expected: no obsolete current user-facing text outside historical development entries.

Run: `python -m compileall -q batch_rename tests main.py`

Expected: exit code 0.

**Step 3: Run full tests**

Run: `python -m pytest -q`

Expected: all tests pass.

**Step 4: Perform Windows visual verification**

Launch the source application. At 960×680 verify the 35/65 cards, search button, same-line statistics, preview value 100, requested column order and teal new-name labels. Press Enter in the search field with identical search/replacement values and confirm nonzero matches with zero executable actions. Maximize and confirm the result area expands.

**Step 5: Build and smoke-test the single file**

Run: `powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1`

Expected: tests pass inside the build and `dist\BatchRename.exe` is produced. Copy the verified latest artifact to `D:\ProjectFolder\BatchRename\dist\BatchRename.exe`, start only that executable, verify a visible “批量重命名工具” window, stop only test-launched processes, and record size plus SHA-256.

**Step 6: Commit**

```text
文档：介绍规则快捷预览与结果确认布局
发布：记录规则预览版本完整验证结果
```

Push the verified feature branch to `origin` after the user explicitly authorizes publication. Preserve the feature worktree so follow-up fixes can continue without altering the main checkout.
