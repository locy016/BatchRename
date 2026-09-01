# README Product Guide Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Publish a current, product-oriented Chinese README with real interface previews, a branded six-step workflow diagram, complete guidance, and verified local assets.

**Architecture:** Keep all README visuals inside `docs/images` so GitHub renders the page without external services. Generate screenshots from the real Tk interface in safe preview-only states, create a maintainable SVG workflow diagram, and add lightweight documentation tests that parse local image references and SVG XML.

**Tech Stack:** Markdown, SVG/XML, Tkinter, Pillow ImageGrab, pytest, Git/GitHub.

---

### Task 1: Lock documentation asset integrity

**Files:**
- Create: `tests/test_documentation.py`
- Modify: `README.md`

**Step 1: Write failing documentation tests**

Add tests that extract local Markdown image targets from README, assert every path exists, require references to `batch-rename-main.png`, `batch-rename-regex-templates.png`, and `batch-rename-workflow.svg`, and parse the SVG with `xml.etree.ElementTree`.

**Step 2: Run the focused test and verify RED**

Run: `python -m pytest tests/test_documentation.py -q`

Expected: failure because the workflow and template assets are not yet referenced or present.

**Step 3: Add temporary README references only after assets are created in Tasks 2–3**

Keep the test failing until all three visuals exist; do not weaken it to accept missing files.

### Task 2: Create the branded workflow diagram

**Files:**
- Create: `docs/images/batch-rename-workflow.svg`

**Step 1: Draw a repository-native SVG**

Create a 1440×360 responsive SVG with six connected cards:

1. 选择目录
2. 查找规则
3. 扫描匹配
4. 填写替换
5. 结果预览
6. 确认执行

Use the application navy/accent palette, concise Chinese subtitles, arrow connectors, rounded cards, and a bottom safety statement that scanning and preview do not modify the disk.

**Step 2: Parse and inspect**

Run an XML parse and open the SVG locally to confirm all text and connectors fit without clipping.

### Task 3: Capture current real interface previews

**Files:**
- Replace: `docs/images/batch-rename-main.png`
- Create: `docs/images/batch-rename-regex-templates.png`

**Step 1: Capture main preview safely**

Start the real 960×680 Tk app in a DPI-aware process, build a match snapshot and preview from the project worktree, render statistics/results, capture the physical window bounds, and destroy the window without invoking execution.

**Step 2: Capture template panel safely**

Start a fresh app, open the in-window regex template panel, select a representative category/template, capture the full window with the apply button visible, and destroy it without applying or scanning.

**Step 3: Inspect both PNGs**

Verify title bar, menu, left workflow, bottom tools, full statistics and template apply action are readable at original resolution.

### Task 4: Rewrite README as the current product guide

**Files:**
- Modify: `README.md`

**Step 1: Reorganize content**

Use this order: brand/version, product positioning, main preview, six-step workflow, two-stage explanation, regex template preview, use cases, core capabilities, detailed operation, regex examples, safety, roadmap, source/build, structure.

**Step 2: Keep labels and capability status exact**

Use `扫描`, `结果预览`, `确认执行`, `正则模板`, `设置`, `功能 → 结果详情`. Describe undo/log as development placeholders only.

**Step 3: Run documentation tests**

Run: `python -m pytest tests/test_documentation.py -q`

Expected: PASS with all three local visual references present and SVG parseable.

### Task 5: Record documentation and visual verification

**Files:**
- Modify: `CHANGELOG.md`

**Step 1: Add a Chinese development-log section**

Record information architecture, SVG rationale, screenshot states, safety constraints, stale-text checks and test results. Keep these implementation details out of README.

**Step 2: Commit product documentation**

Commit with a Chinese subject and detailed Chinese body describing the user-facing guide, real visual assets and validation.

### Task 6: Verify, synchronize and push

**Files:**
- Verify all changed files

**Step 1: Refresh remote state**

Run `git fetch origin` and confirm the push will be fast-forward for the selected remote branch; never force-push.

**Step 2: Run final checks**

Run:

```powershell
python -m compileall -q batch_rename tests main.py
python -m pytest -q
git diff --check
git status --short
```

Expected: all tests pass, no formatting errors, clean working tree after the final commit.

**Step 3: Push**

Push `feature/menu-navigation-dialogs` to `origin` with upstream tracking. Report the exact remote branch and commit; do not rewrite history or delete local branches/worktrees.
