# 可拖拽工具面板实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 取消左下角“工具”标题，并让正则模板与设置面板从实际入口附近打开，具备主题化边框、阴影和主窗口内拖拽能力。

**Architecture:** 保留现有窗口内非模态面板和业务控件，用纯几何函数计算入口锚定位置与拖拽边界。每个内容面板增加独立阴影层，标题区域绑定统一拖拽事件；当前触发按钮由入口命令传入，响应式重排和主题切换复用同一定位及外观更新路径。

**Tech Stack:** Python 3.11+、Tkinter/ttk、pytest、PyInstaller。

---

### Task 1: 固定入口锚定和边界计算

**Files:**
- Modify: `batch_rename/app.py:209-260`
- Test: `tests/test_app.py`

**Step 1: Write the failing test**

增加纯函数测试，覆盖以下输入：

```python
def test_floating_panel_position_aligns_with_trigger_and_stays_in_workspace():
    assert floating_panel_position(
        workspace_size=(1100, 700),
        panel_size=(620, 460),
        trigger_bounds=(12, 640, 280, 36),
        margin=12,
    ) == (304, 228)


def test_floating_panel_position_clamps_dragged_coordinates():
    assert clamp_floating_panel_position(
        requested=(-40, 900),
        workspace_size=(1100, 700),
        panel_size=(620, 460),
        margin=12,
    ) == (12, 228)
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_app.py -k "floating_panel_position" -q`

Expected: FAIL because the geometry helpers do not exist.

**Step 3: Write minimal implementation**

在 `batch_rename/app.py` 增加 `clamp_floating_panel_position(...)` 与 `floating_panel_position(...)`。锚点默认位于按钮右侧，面板底边与按钮底边对齐；横纵坐标均限制在工作区边距以内。

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_app.py -k "floating_panel_position" -q`

Expected: PASS.

**Step 5: Commit**

```powershell
git add -- batch_rename/app.py tests/test_app.py
git commit -m "布局：让工具面板贴近触发入口"
```

### Task 2: 精简左下角入口并建立浮动层级

**Files:**
- Modify: `batch_rename/app.py:1297-1315`
- Modify: `batch_rename/app.py:2115-2243`
- Modify: `batch_rename/app.py:2278-2557`
- Test: `tests/test_app.py:1357-1435`

**Step 1: Write the failing test**

修改左侧布局测试，断言不再存在可见的“工具”标签，两个按钮仍为完整宽度并保持间距。增加面板测试，断言正则与设置各有阴影层，面板使用独立边框样式，打开后面板与阴影同时显示且阴影偏移固定。

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_app.py -k "workflow_actions_and_tools or floating_panel_shadow" -q`

Expected: FAIL because the label remains visible and shadow layers are absent.

**Step 3: Write minimal implementation**

- 删除 `tools_footer_label` 的创建和网格占位，把两个入口上移到原底部区域。
- 新增 `FloatingPanel.TFrame` 边框样式和主题语义色 `panel_shadow`。
- 为两个内容面板建立不接收交互的 `tk.Frame` 阴影层；定位时先放置阴影，再放置内容面板并提升内容层。
- 关闭面板时同时隐藏两个阴影层。

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_app.py -k "workflow_actions_and_tools or floating_panel_shadow" -q`

Expected: PASS.

**Step 5: Commit**

```powershell
git add -- batch_rename/app.py tests/test_app.py
git commit -m "界面：精简左下入口并增加浮层边框阴影"
```

### Task 3: 从实际按钮打开并支持标题拖拽

**Files:**
- Modify: `batch_rename/app.py:1807-1833`
- Modify: `batch_rename/app.py:2219-2266`
- Modify: `batch_rename/app.py:2532-2625`
- Modify: `batch_rename/app.py:4024-4025`
- Test: `tests/test_app.py:610-750`

**Step 1: Write the failing test**

增加真实 Tk 控件测试：

```python
def test_tool_panel_opens_next_to_the_button_that_triggered_it(tk_window):
    app = BatchRenameApp(tk_window)
    app.regex_templates_button.invoke()
    tk_window.update_idletasks()
    assert app._active_tool_trigger is app.regex_templates_button
    assert int(app.templates_panel.place_info()["x"]) > app.regex_templates_button.winfo_x()


def test_dragging_tool_panel_header_moves_and_clamps_panel(tk_window):
    app = BatchRenameApp(tk_window)
    app._toggle_tool_panel("settings", trigger=app.settings_tool_button)
    app._start_tool_panel_drag(SimpleNamespace(x_root=400, y_root=500))
    app._drag_tool_panel(SimpleNamespace(x_root=-1000, y_root=-1000))
    assert app._tool_panel_position == (12, 12)
```

同时断言拖拽绑定只存在于标题区域，不绑定模板列表、输入框或设置选项。

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_app.py -k "tool_panel_opens_next or dragging_tool_panel" -q`

Expected: FAIL because trigger tracking and drag handlers do not exist.

**Step 3: Write minimal implementation**

- 入口命令通过闭包把实际按钮传给 `_toggle_tool_panel(name, trigger=...)`；保留直接调用时的默认入口，兼容截图工具和既有测试。
- `_build_tool_panel_header` 返回标题容器，并只在标题容器、标题文字和辅助说明上绑定按下、移动、释放事件。
- 实现 `_start_tool_panel_drag`、`_drag_tool_panel` 和 `_finish_tool_panel_drag`，使用根坐标计算位移，再调用纯边界函数。
- `_position_active_tool_panel` 优先使用拖拽坐标；没有拖拽坐标时读取实际触发按钮相对 `body_frame` 的矩形并计算锚点。
- 响应式重排时约束已有拖拽坐标；关闭时清理触发控件、拖拽起点和自定义坐标。

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_app.py -k "tool_panel_opens_next or dragging_tool_panel or bottom_tool_panels" -q`

Expected: PASS.

**Step 5: Commit**

```powershell
git add -- batch_rename/app.py tests/test_app.py
git commit -m "交互：支持工具面板锚定与窗口内拖拽"
```

### Task 4: 同步主题、文档和真实界面验证

**Files:**
- Modify: `batch_rename/app.py`
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `tools/capture_product_previews.py`
- Modify: `docs/images/batch-rename-main.png`
- Modify: `docs/images/batch-rename-regex-templates.png`
- Test: `tests/test_app.py`
- Test: `tests/test_documentation.py`

**Step 1: Write the failing test**

增加浅色、深色主题测试，断言面板边框与阴影在运行时使用当前色板；调整文档测试，要求 README 描述“入口附近打开”和“标题拖拽”。

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_app.py tests/test_documentation.py -k "tool_panel or readme" -q`

Expected: FAIL because new主题角色和产品说明尚未同步。

**Step 3: Write minimal implementation**

- 为浅色和深色主题补充边框、阴影颜色，并在 `_apply_runtime_theme` 中更新已创建阴影层。
- 更新 README 的工作台、紧凑布局和正则模板说明，不记录机械式改动清单。
- 在 CHANGELOG 以中文记录需求背景、交互取舍、测试过程和验证结果。
- 更新截图工具的面板打开方式，生成主界面与正则面板真实截图并检查锚定、边框、阴影和内容完整性。

**Step 4: Run focused tests**

Run: `python -m pytest tests/test_app.py tests/test_documentation.py -q`

Expected: PASS.

**Step 5: Run full verification**

Run: `python -m compileall -q batch_rename tests tools main.py`

Run: `python -m pytest -q`

Run: `git diff --check`

Expected: bytecode compilation exits 0, all tests pass, and Git reports no whitespace errors.

**Step 6: Run application smoke test**

启动 `python main.py`，只跟踪本次启动的新进程；确认主窗口可见，分别打开两个面板并核对贴近入口、拖拽、边框、阴影和关闭行为，验证后只结束本次新增进程。

**Step 7: Commit**

```powershell
git add -- batch_rename/app.py tests/test_app.py tests/test_documentation.py README.md CHANGELOG.md tools/capture_product_previews.py docs/images/batch-rename-main.png docs/images/batch-rename-regex-templates.png
git commit -m "发布：完善可拖拽工具面板与产品说明"
```

**Step 8: Leave push to the user**

核对本地提交与工作区状态，只报告人工推送所需提交信息，不执行 `git push`。
