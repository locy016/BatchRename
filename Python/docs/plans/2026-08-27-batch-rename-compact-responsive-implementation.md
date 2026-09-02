# Batch Rename Compact Responsive Interface Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deliver a 960×680 responsive desktop interface with denser result viewing, polished ttk controls, complete cell hover content, and a categorized one-click regular-expression template library.

**Architecture:** Keep the Tkinter/ttk application and filesystem core separated. Add small UI helpers for adaptive scrollbars and tree-cell hover behavior, keep layout decisions inside `BatchRenameApp`, and extend immutable regex example data with category and option metadata. All new behavior is driven by tests before production changes.

**Tech Stack:** Python 3.13, Tkinter/ttk, pytest, Pillow asset checks, PyInstaller single-file build.

---

### Task 1: Lock the compact responsive layout contract

**Files:**
- Modify: `tests/test_app.py`
- Modify: `batch_rename/app.py`

**Step 1: Write the failing tests**

Add tests that create `BatchRenameApp`, call `root.update_idletasks()`, and assert:

```python
assert root.geometry().startswith("960x680")
assert root.minsize() == (960, 680)
assert app.search_entry.grid_info()["row"] == app.replacement_entry.grid_info()["row"]
assert int(app.result_tree.cget("height")) >= 10
assert root.winfo_reqheight() <= 680
assert root.winfo_reqwidth() <= 960
```

Also assert that the root result row and result card carry positive grid weights so extra maximized space flows into the table.

**Step 2: Run the focused tests and verify RED**

Run: `python -m pytest tests/test_app.py -q`

Expected: FAIL because the current window is 1240×820, the two entries occupy different rows, and the table height is 5.

**Step 3: Implement the minimal responsive layout**

Change the main geometry and minimum size to 960×680. Reduce header/card/action/progress padding, place search and replacement labels and entries on the same row, expose both entries as instance attributes, and set the result table height to at least 10. Remove fixed label widths that reserve unnecessary horizontal space and retain grid weights for maximized expansion.

**Step 4: Run tests and verify GREEN**

Run: `python -m pytest tests/test_app.py -q`

Expected: PASS.

**Step 5: Commit**

```text
界面：实现 960×680 紧凑自适应布局
```

### Task 2: Add conditional scrollbars and complete cell hover content

**Files:**
- Modify: `tests/test_app.py`
- Modify: `batch_rename/app.py`

**Step 1: Write failing behavior tests**

Add a Tk test for an `AutoHideScrollbar`: invoke its `set("0.0", "1.0")` callback and assert it removes itself from the grid, then invoke `set("0.0", "0.5")` and assert it restores its saved grid placement.

Add a test for a tree-cell helper by inserting a row with a long directory path and asserting the helper returns the correct heading and full value for a selected row/column. Verify blank space and the tree heading produce no value.

**Step 2: Run the focused tests and verify RED**

Run: `python -m pytest tests/test_app.py -q`

Expected: FAIL because the adaptive scrollbar and cell-content helper do not exist.

**Step 3: Implement minimal helpers**

Create `AutoHideScrollbar(ttk.Scrollbar)` that remembers its grid options and toggles visibility only from the scrollbar fractions. Create a `TreeCellToolTip` using the existing tooltip window behavior, `identify_row`, and `identify_column`; show a titled card only when the text pixel width exceeds the visible column width. Hide it on motion to another cell, leave, button press, mouse wheel, or scrollbar activity.

Use the adaptive class for the result table horizontal scrollbar. Keep the vertical scrollbar visible because the result count is unbounded.

**Step 4: Run tests and verify GREEN**

Run: `python -m pytest tests/test_app.py -q`

Expected: PASS.

**Step 5: Commit**

```text
交互：按需显示横向滚动并悬浮查看完整内容
```

### Task 3: Apply a cohesive ttk component theme

**Files:**
- Modify: `tests/test_app.py`
- Modify: `batch_rename/app.py`

**Step 1: Write failing style tests**

Assert key widgets use dedicated styles:

```python
assert app.directory_entry.cget("style") == "Modern.TEntry"
assert app.depth_spin.cget("style") == "Modern.TSpinbox"
assert app.result_scrollbar.cget("style") == "Modern.Vertical.TScrollbar"
assert app.progress.cget("style") == "Modern.Horizontal.TProgressbar"
```

Use `ttk.Style.lookup` to verify the styles define non-empty field backgrounds, trough colors, and active-state colors. Assert checkbuttons and radiobuttons expose the existing card-specific styled variants.

**Step 2: Run the focused tests and verify RED**

Run: `python -m pytest tests/test_app.py -q`

Expected: FAIL because entries, spinboxes and scrollbars still use generic styles.

**Step 3: Implement the ttk theme**

Configure `Modern.TEntry`, `Modern.TSpinbox`, horizontal and vertical scrollbar styles, polished check/radio layouts, progress styling, main/secondary/quiet buttons, focus colors and disabled colors. Apply the dedicated styles to every main-window instance and to popup scrollbars where practical. Restyle the tooltip to the project palette and clamp its position to the current screen.

**Step 4: Run tests and verify GREEN**

Run: `python -m pytest tests/test_app.py -q`

Expected: PASS.

**Step 5: Commit**

```text
视觉：统一桌面控件与悬浮提示样式
```

### Task 4: Expand and categorize the regex template library

**Files:**
- Modify: `tests/test_examples.py`
- Modify: `tests/test_app.py`
- Modify: `batch_rename/examples.py`
- Modify: `batch_rename/app.py`

**Step 1: Write failing template tests**

Require at least 12 examples and at least four categories. For every example, build a real `RenameRule` with its `rename_extension` flag and assert its documented before/after result. Require category, title, purpose, search and option metadata.

Add an application test proving `_apply_regex_example` sets search, replacement, regex mode and extension handling from the selected template.

**Step 2: Run focused tests and verify RED**

Run: `python -m pytest tests/test_examples.py tests/test_app.py::test_applying_regex_example_fills_rule_and_enables_regex_mode -q`

Expected: FAIL because there are only four uncategorized examples and extension metadata is absent.

**Step 3: Implement template metadata and validated examples**

Extend `RegexExample` with `category` and `rename_extension=False`. Add classic examples covering date separators, numeric sequences, prefix/suffix removal, bracket cleanup, leading/trailing whitespace, repeated whitespace, repeated separators, fragment swapping, date/number repositioning and JPEG/JPG extension normalization. Avoid examples that Python replacement syntax cannot perform, such as arbitrary numeric zero-padding or case conversion.

Update `_apply_regex_example` to synchronize the extension option. Every template remains non-destructive until the user scans and confirms.

**Step 4: Run tests and verify GREEN**

Run: `python -m pytest tests/test_examples.py tests/test_app.py -q`

Expected: PASS.

**Step 5: Commit**

```text
功能：扩充分类正则模板与一键应用选项
```

### Task 5: Redesign the regex template chooser for beginners

**Files:**
- Modify: `tests/test_app.py`
- Modify: `batch_rename/app.py`

**Step 1: Write a failing UI structure test**

Open the chooser through a testable builder and assert it exposes a category selector, template selector, read-only search/replacement fields, before/after preview, and an apply button. Assert choosing a category filters template titles without mutating the global immutable tuple.

**Step 2: Run the focused test and verify RED**

Run: `python -m pytest tests/test_app.py -q`

Expected: FAIL because the current chooser is a single flat list.

**Step 3: Implement the categorized chooser**

Use a compact two-pane popup: category chips or list on the left, templates below or beside it, and a detail card on the right. Show plain-language purpose before expressions, explain empty replacement and extension behavior, and provide “一键应用此规则”. Ensure double-clicking a template performs the same action and closes the popup.

**Step 4: Run tests and verify GREEN**

Run: `python -m pytest tests/test_app.py -q`

Expected: PASS.

**Step 5: Commit**

```text
界面：为初学者重构正则模板选择器
```

### Task 6: Update product guidance and complete release verification

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `batch_rename/app.py`

**Step 1: Update user-facing guidance**

Describe the 960×680 responsive behavior, single-line rule editing, automatic horizontal scrollbar, cell hover content, and categorized regex templates in natural product language. Update built-in help and tooltips to match exact labels and behavior. Record design decisions, test evidence and visual findings in the Chinese development log.

**Step 2: Run stale-text and syntax checks**

Run: `rg -n "1240x820|两个标签页|横向滚动可查看|四组" batch_rename README.md CHANGELOG.md -S`

Expected: no obsolete user-facing descriptions outside historical context.

Run: `python -m compileall -q batch_rename tests main.py`

Expected: exit code 0.

**Step 3: Run full automated verification**

Run: `python -m pytest -q`

Expected: all tests pass.

**Step 4: Perform visual verification**

Launch the source application at 960×680 and inspect the complete window. Then maximize it and verify the result table receives the extra height. Populate long sample names and paths to verify hover content and horizontal scrollbar behavior. Open the regex chooser and apply examples from several categories.

**Step 5: Build and smoke-test the single file**

Run: `powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1`

Expected: tests pass inside the build and `dist\BatchRename.exe` is created. Start only this executable, verify a visible “批量重命名工具” child window, stop only the test-launched processes, and record file size plus SHA-256.

**Step 6: Commit**

```text
文档：介绍紧凑界面与常用正则模板
发布：记录自适应界面完整验证结果
```

Do not push any commit; leave the local `main` branch ahead of `origin/main` for the user to review and push manually.
