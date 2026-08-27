# Batch Rename Modernization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让扫描结果准确反映名称匹配，重构为现代化单列表界面，并补齐正则示例、应用图标、中文开发日志和面向使用者的项目说明。

**Architecture:** 保持 `batch_rename/core.py` 为无界面扫描与执行核心，在数据模型中明确区分“名称匹配”和“可执行改名”。`batch_rename/app.py` 使用单个 Treeview 消费稳定排序后的候选项，并通过独立示例数据和样式配置构建新版界面；图标以 PNG/ICO 资源随 PyInstaller 打包。

**Tech Stack:** Python 3.13、Tkinter/ttk、pytest、Pillow、PyInstaller、ImageGen

---

### Task 1: 修正匹配结果与执行动作的语义

**Files:**
- Modify: `batch_rename/models.py`
- Modify: `batch_rename/core.py`
- Modify: `tests/test_scan.py`
- Modify: `tests/test_rules.py`

**Step 1: 写入失败回归测试**

新增测试，创建 `众川合同.docx`，使用“众川 → 众川”扫描，并断言候选数量为 1、状态为 `UNCHANGED`、可执行数量为 0。

**Step 2: 验证测试按预期失败**

Run: `python -m pytest tests/test_scan.py::test_same_replacement_still_lists_matching_name -v`

Expected: FAIL，当前实现返回空候选列表。

**Step 3: 分离匹配判断和名称转换**

在 `RenameRule` 中增加 `matches(name, is_file)`，扫描时先判断完整可搜索部分是否匹配，再计算新名称。匹配但名称未变化时创建 `CandidateStatus.UNCHANGED` 候选，说明“名称符合搜索条件，但替换后没有变化”。

**Step 4: 覆盖受保护扩展名场景**

新增测试，查找 `jpg` 且保持扩展名保护时，`照片.jpg` 进入列表并标记未变化，同时说明扩展名受保护。

**Step 5: 运行核心测试并提交**

Run: `python -m pytest tests/test_rules.py tests/test_scan.py tests/test_execute.py -v`

Commit title: `修复：扫描结果按名称匹配而非名称变化统计`

Commit body: 说明复现条件、根因、匹配与执行状态的分离以及测试结果。

### Task 2: 统一列表排序与统计

**Files:**
- Modify: `batch_rename/app.py`
- Modify: `tests/test_app.py`

**Step 1: 写入失败测试**

用混合顺序构造文件夹和文件候选，断言 `sorted_preview_items()` 返回文件夹优先、文件其次、同类按原名称自然排序的单一序列；断言统计包含 `matched_total`、`ready_total`、`unchanged_total` 和 `blocked_total`。

**Step 2: 验证测试失败**

Run: `python -m pytest tests/test_app.py -v`

Expected: FAIL，现有代码只有两个分类列表和旧统计字段。

**Step 3: 实现单一数据接口**

以稳定键 `(类型顺序, natural_name_key, 所在目录)` 排序全部候选；统一预览条数只截取显示，不改变完整统计。

**Step 4: 调整无动作提示**

匹配数量大于 0 而可执行数量为 0 时，状态文本明确显示“已匹配 N 项，但本次没有可执行动作”，列表仍保留所有匹配项。

**Step 5: 运行界面辅助测试并提交**

Run: `python -m pytest tests/test_app.py -v`

Commit title: `功能：统一文件夹与文件的匹配结果列表`

### Task 3: 增加可直接套用的正则示例

**Files:**
- Create: `batch_rename/examples.py`
- Create: `tests/test_examples.py`
- Modify: `batch_rename/app.py`

**Step 1: 写入示例有效性测试**

对日期压缩、图片序号、删除标签和片段交换四个示例逐一创建 `RenameRule`，并断言示例输入得到示例输出。

**Step 2: 验证模块不存在导致失败**

Run: `python -m pytest tests/test_examples.py -v`

Expected: FAIL，`batch_rename.examples` 尚不存在。

**Step 3: 实现不可变示例数据**

每个示例包含名称、用途、查找表达式、替换内容、输入和输出，不在界面代码中重复硬编码。

**Step 4: 增加示例选择窗口**

规则卡片提供“正则示例”按钮；示例窗口展示完整表达式、结果和解释，并可将选中示例填入主界面且自动开启正则模式。

**Step 5: 运行测试并提交**

Run: `python -m pytest tests/test_examples.py tests/test_app.py -v`

Commit title: `功能：提供可直接应用的正则重命名示例`

### Task 4: 重构现代化原生界面

**Files:**
- Modify: `batch_rename/app.py`
- Modify: `tests/test_app.py`

**Step 1: 写入布局结构测试**

实例化隐藏窗口，断言只有一个结果 Treeview、主要卡片和操作按钮存在，忙碌状态会锁定全部规则输入。

**Step 2: 验证旧布局不满足测试**

Run: `python -m pytest tests/test_app.py -v`

Expected: FAIL，旧界面仍包含 Notebook 和两个 Treeview。

**Step 3: 实现视觉系统和卡片布局**

建立集中配色、字体、间距和 ttk 样式；使用顶部品牌区、两列设置卡片、操作统计条、单一结果卡片和底部进度区。保留窗口缩放、横纵滚动、悬停说明、确认对话框和后台线程。

**Step 4: 更新列表渲染与反馈**

结果表加入类型列和状态色；扫描后展示匹配总数而不是“名称变化”；无动作、冲突和错误使用清晰但不过度机械的中文提示。

**Step 5: 运行界面测试并提交**

Run: `python -m pytest tests/test_app.py -v`

Commit title: `界面：重构现代化布局与统一结果视图`

### Task 5: 生成并接入应用图标

**Files:**
- Create: `assets/app-icon.png`
- Create: `assets/app-icon.ico`
- Modify: `batch_rename/app.py`
- Modify: `BatchRename.spec`
- Modify: `tests/test_build_config.py`

**Step 1: 写入资源配置失败测试**

断言 PNG 和 ICO 存在、PNG 为正方形透明图、ICO 包含适合 Windows 的多尺寸资源，并断言 PyInstaller 配置引用 ICO。

**Step 2: 验证测试失败**

Run: `python -m pytest tests/test_build_config.py -v`

Expected: FAIL，当前没有图标资源。

**Step 3: 使用 ImageGen 生成图标主视觉**

生成透明背景、无文字的文件夹与循环重命名箭头图标，使用深蓝与青绿色，确保 16 像素下仍能辨识。

**Step 4: 生成多尺寸 ICO 并接入**

使用 Pillow 从 PNG 生成 16、24、32、48、64、128、256 像素 ICO；窗口运行时使用资源路径加载图标，PyInstaller 通过 `icon="assets/app-icon.ico"` 嵌入 EXE。

**Step 5: 运行配置测试并提交**

Run: `python -m pytest tests/test_build_config.py tests/test_app.py -v`

Commit title: `视觉：生成并接入批量重命名应用图标`

### Task 6: 重写项目介绍并建立中文开发日志

**Files:**
- Modify: `README.md`
- Create: `CHANGELOG.md`

**Step 1: 重写 README**

按“项目定位、适用场景、功能、开始使用、规则示例、安全机制、开发运行、构建发布”组织内容；只描述当前项目，不列开发改动流水账。

**Step 2: 编写 CHANGELOG**

记录初始版本与本轮改版的背景、扫描根因、设计决策、实现范围、测试和构建验证；用自然中文保留开发过程。

**Step 3: 检查语言与链接**

Run: `rg -n "feat:|fix:|TODO|做了哪些改动" README.md CHANGELOG.md`

Expected: 无机械式提交前缀、占位符或改动清单措辞。

**Step 4: 提交文档**

Commit title: `文档：完善项目介绍与中文开发日志`

### Task 7: 完整验证与本地收尾

**Files:**
- Modify when necessary: `build.ps1`
- Verify: `dist/BatchRename.exe`

**Step 1: 运行完整测试和编译检查**

Run: `python -m pytest -v`

Run: `python -m compileall -q batch_rename main.py tests`

Expected: 全部通过且无编译错误。

**Step 2: 构建单文件应用**

Run: `powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1`

Expected: 生成带图标的 `dist/BatchRename.exe`。

**Step 3: 启动冒烟验证**

启动 EXE，确认窗口标题、图标和单列表界面出现；随后只终止本次验证启动的进程。

**Step 4: 检查 Git 状态与提交历史**

Run: `git status --short --branch`

Run: `git log --pretty=fuller -10`

Expected: 工作树干净；本轮提交标题和正文为中文；本地分支领先远程；不执行 `git push`。

**Step 5: 记录验证结论并提交**

如验证需要更新日志，提交标题使用：`发布：记录新版应用的完整验证结果`。
