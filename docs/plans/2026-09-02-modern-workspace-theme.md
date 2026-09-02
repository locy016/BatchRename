# Modern Workspace and Theme Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the decorative header and cramped traditional layout with a modern productivity workspace that shows directory inventory above results, match statistics below the table, comfortable workflow/tool spacing, and persisted system/light/dark appearance modes.

**Architecture:** Extend the existing match snapshot with inventory totals collected during the same traversal, then bind those totals to a dedicated directory-context bar without adding another filesystem pass. Isolate appearance preference loading, system resolution and palettes behind pure functions; keep one Tk widget tree and reconfigure ttk styles, Tk widgets, overlays and open panels in place when the theme changes.

**Tech Stack:** Python 3.11+, Tkinter/ttk, pathlib, Windows registry through `winreg`, JSON preferences, pytest, Pillow screenshot tooling, PyInstaller.

**Repository constraint:** Work directly on local `main` as explicitly requested. Do not create a branch or worktree and do not push.

---

### Task 1: Count directory inventory during the existing scan

**Files:**
- Modify: `batch_rename/models.py`
- Modify: `batch_rename/core.py`
- Test: `tests/test_scan.py`

**Step 1: Write failing snapshot-count tests**

Add tests that create direct and nested directories/files and assert a `MatchResult` exposes complete traversal counts:

```python
result = search_matches(MatchOptions(tmp_path, "项目", max_depth=2))
assert result.scanned_directory_count == 2
assert result.scanned_file_count == 3
```

Add one case with `include_files=False` and prove file totals still count every traversed file while only directory matches enter `items`. Add a depth-one case proving nested children outside the configured scan depth are not counted.

**Step 2: Run and verify RED**

Run: `python -m pytest tests/test_scan.py -q -k "inventory or scanned_count"`

Expected: FAIL because the snapshot has no count fields.

**Step 3: Implement counts in the existing traversal**

Add default-zero integer fields to `MatchResult`. In `search_matches`, increment the directory or file total immediately after type detection and before include filters or name matching. Do not count symlinks, unknown entry types, the root itself, or entries deeper than `max_depth`.

**Step 4: Verify and commit**

Run: `python -m pytest tests/test_scan.py -q`

Commit: `核心：在扫描快照中记录目录文件总量`

### Task 2: Build directory-context and match-stat presentation models

**Files:**
- Modify: `batch_rename/app.py`
- Test: `tests/test_app.py`

**Step 1: Write failing pure formatting tests**

Introduce wished-for helpers such as:

```python
assert directory_scope_text("all", 1) == "全部层级"
assert directory_scope_text("limited", 3) == "最多 3 层"
assert directory_inventory_text(None) == "尚未扫描"
assert directory_inventory_text(snapshot) == "文件夹 2  ·  文件 3"
```

Cover unreadable-location suffixes and long root-path preservation for tooltip use.

**Step 2: Run and verify RED**

Run focused helper tests and confirm imports fail for the new functions.

**Step 3: Implement presentation helpers and variables**

Keep exact inventory numbers in separate `StringVar`s for folder, file and warning values instead of parsing one sentence. Add methods that update the directory context for idle, scanning and completed states. Root or depth changes reset counts; search text, regex mode and object filters invalidate matches but may show “需要重新扫描”; replacement-only changes preserve completed inventory.

**Step 4: Verify and commit**

Run focused app tests.

Commit: `界面：建立目录概况与匹配统计展示模型`

### Task 3: Replace the decorative header with the directory overview

**Files:**
- Modify: `batch_rename/app.py`
- Test: `tests/test_app.py`

**Step 1: Write failing layout tests**

Assert the large `Header.TFrame` brand block no longer exists in the main grid. Assert a `directory_overview` occupies result-workspace row 0 and exposes current-root, scope, folder-count, file-count and unreadable-count widgets. Verify the root path tooltip retains the full directory string.

Assert `stats_label` or its four replacement statistic widgets are placed below `result_tree`, not above `result_card`.

**Step 2: Run and verify RED**

Run: `python -m pytest tests/test_app.py -q -k "directory_overview or stats_below or decorative_header"`

Expected: layout assertions fail against the current brand header and top statistics frame.

**Step 3: Implement the new result hierarchy**

Make the body the expandable first row of `main_content`. Build a compact directory overview as the result workspace’s top section. Keep “匹配结果” and preview limit in the table heading. Move four match statistics to a footer inside or immediately below the result card and keep progress below it.

Use a clipped single-line root label with a full-path `ToolTip`. Keep counts visible at 1120 pixels by assigning expansion only to the path region.

**Step 4: Connect scan lifecycle**

Set “正在统计” in `_start_search`, exact totals in `_handle_search_done`, and preserve them through `_handle_preview_done`. Reset or mark stale according to Task 2 dependency rules. Existing match/preview statistics continue to use `stats_var` or exact per-stat variables.

**Step 5: Verify and commit**

Run all app tests.

Commit: `布局：用目录概况替换装饰标题并下移结果统计`

### Task 4: Add persisted appearance preferences and system resolution

**Files:**
- Create: `batch_rename/preferences.py`
- Modify: `batch_rename/app.py`
- Create: `tests/test_preferences.py`
- Modify: `tests/test_app.py`

**Step 1: Write failing preference tests**

Cover:

```python
assert normalize_appearance("dark") == "dark"
assert normalize_appearance("unknown") == "system"
assert load_preferences(missing_path).appearance == "system"
```

Write/read a temporary JSON file, verify malformed JSON and invalid values safely fall back, and inject a system-light provider to test resolving `system` into `light` or `dark` without touching the real registry.

**Step 2: Run and verify RED**

Run: `python -m pytest tests/test_preferences.py -q`

Expected: import failure because the preferences module does not exist.

**Step 3: Implement the preference boundary**

Create an immutable preference model, a default path under `%LOCALAPPDATA%\BatchRename\settings.json`, tolerant loading, atomic-enough single-file saving through a temporary sibling and replace, and Windows system-light resolution using `winreg`. File or registry errors fall back without raising into app startup.

Inject preference path and system-theme provider into `BatchRenameApp` for tests. Store the requested appearance separately from the resolved palette.

**Step 4: Verify and commit**

Run preference and affected app tests.

Commit: `设置：保存并解析系统浅色深色外观`

### Task 5: Define modern light and dark palettes and runtime theme switching

**Files:**
- Modify: `batch_rename/app.py`
- Test: `tests/test_app.py`

**Step 1: Write failing palette and state-preservation tests**

Define a pure `theme_palette("light" | "dark")` contract. Assert required semantic tokens exist for canvas, surface, elevated surface, sidebar, text, muted text, border, accent, accent hover, selection, input, disabled, success, warning and danger.

Create an app, retain references to search/replacement variables, match snapshot and preview, switch appearance, then assert all references and values are unchanged while representative ttk styles, root background, Treeview and overlay backgrounds use the new palette.

**Step 2: Run and verify RED**

Run focused theme tests and confirm missing API/style changes.

**Step 3: Implement palette-driven styling**

Replace static `COLORS` reads with `self.colors` resolved from the active palette. Reconfigure all existing ttk styles from palette tokens. Track raw Tk widgets—template list, overlay labels/canvases, tooltip windows and text widgets—that require direct color updates.

Add `set_appearance(mode, persist=True)` that updates radio state, saves the requested mode, resolves system mode, closes stale tooltips and repaints in place. Bind root focus to re-resolve only when requested mode is `system` and the resolved mode changed.

**Step 4: Add the View menu**

Insert `视图` between `功能` and `帮助`, add an `外观` submenu with radio commands for 跟随系统/浅色/深色, and expose current checked state through `appearance_var`. Do not duplicate theme options in the bottom settings panel.

**Step 5: Verify and commit**

Run all app tests.

Commit: `主题：实现现代浅色深色与系统外观切换`

### Task 6: Modernize the workflow rail and bottom tool actions

**Files:**
- Modify: `batch_rename/app.py`
- Test: `tests/test_app.py`

**Step 1: Write failing rendered-layout tests**

At 1120×720 and 150%/200% Tk scaling, assert:

- standard rail uses the new target width without overflowing the body;
- directory, scan, preview and execute buttons have a consistent requested height;
- vertical gaps between primary workflow actions meet a small minimum;
- regex templates and settings buttons each span the full rail width and are vertically stacked;
- tool buttons remain inside the rail at minimum height.

**Step 2: Run and verify RED**

Run focused workflow layout tests and observe current side-by-side tool buttons and short action padding fail.

**Step 3: Implement the rail grouping and styles**

Use neutral flat/outline styling for directory and scan, indigo accent for preview, and a distinct final-action style for execute. Introduce consistent button padding and focus/hover/disabled states for both themes.

Regroup existing controls without creating duplicates. Add a “工具” footer label and stack the two full-width tool buttons with comfortable spacing. Increase standard/spacious/drawer widths only as far as verified by minimum-window tests.

**Step 4: Verify and commit**

Run app layout tests at every scaling and the full app suite.

Commit: `界面：重排左侧流程并扩大工具操作空间`

### Task 7: Expand and restructure the regex and settings work panels

**Files:**
- Modify: `batch_rename/app.py`
- Test: `tests/test_app.py`

**Step 1: Write failing panel geometry tests**

Open each panel at 1120×720, 1440×900 and a tall compact layout. Assert a title, helper text and close button exist; standard panel width is at least 600 when space allows; height is at least 420 or clamped to available body space; all boundaries remain inside `body_frame`.

For regex templates, assert the list column receives at least 35% and the details column at least 50% of rendered width. For settings, assert each semantic group is present and no control overlaps.

**Step 2: Run and verify RED**

Run focused panel tests and confirm the current request-height/min-500-width implementation fails.

**Step 3: Implement work-panel shells**

Create a reusable header row with title, helper and close action. Position panels near the left rail with 12–16 pixel body margins, vertically centered or top-aligned instead of bottom-attached. Use target widths by layout mode (about 620 standard, 720 spacious) and a stable content height; clamp safely and give internal lists scrolling when needed.

Rebuild regex content as a 40/60 layout and settings as three labeled sections. Preserve existing variables, template filtering, one-click apply, busy locking, Escape behavior and mutual exclusivity.

**Step 4: Verify and commit**

Run all app tests.

Commit: `布局：扩展正则模板与设置工作面板`

### Task 8: Update guidance, screenshots and release artifact

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `batch_rename/app.py`
- Modify: `tools/capture_product_previews.py`
- Replace: `docs/images/batch-rename-main.png`
- Replace: `docs/images/batch-rename-compact.png`
- Modify: `tests/test_documentation.py`

**Step 1: Update product guidance**

Describe directory inventory versus match statistics, the relocated statistics footer, modern workflow/tool layout, larger work panels and View → Appearance modes. Update built-in help and About current capabilities. Keep implementation history and validation detail in CHANGELOG rather than README.

**Step 2: Capture safe real previews**

Update the existing preview tool to inject inventory totals and render both light standard layout and dark or system compact layout. Capture real Tk windows without scanning the demonstration path or invoking execute. Verify images visually for spacing, theme contrast, directory overview and statistics placement.

**Step 3: Request independent review**

Use `superpowers:requesting-code-review`. Fix every Critical and Important finding with a failing regression test before implementation.

**Step 4: Run final verification**

Run:

```powershell
python -m compileall -q batch_rename tests tools main.py
python -m pytest -q
git diff --check
git status --short
```

**Step 5: Build and smoke-test**

Run `build.ps1`. Start only the new `dist\BatchRename.exe`, record the exact PIDs created after a before-snapshot, detect a visible `批量重命名工具` window, and terminate only those new PIDs. Record artifact bytes and SHA-256 in CHANGELOG.

**Step 6: Commit**

Commit product documentation, screenshots and release evidence with detailed Chinese messages. Confirm the repository remains on `main`, one worktree, no extra branches, clean status, and no push.
