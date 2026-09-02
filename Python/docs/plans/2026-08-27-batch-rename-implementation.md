# Batch Rename Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 构建一个带完整中文说明、预览确认、冲突保护和进度反馈的 Windows 批量重命名单文件工具。

**Architecture:** 将不依赖界面的扫描与执行核心和 Tkinter 界面分离。核心返回结构化候选与结果，GUI 通过后台线程和消息队列消费进度，从而保持响应并便于完整测试。

**Tech Stack:** Python 3、Tkinter/ttk、pytest、PyInstaller、PowerShell

---

### Task 1: 定义规则与名称转换

**Files:**
- Create: `batch_rename/__init__.py`
- Create: `batch_rename/models.py`
- Create: `batch_rename/core.py`
- Test: `tests/test_rules.py`

1. 先写普通文本、正则捕获组、扩展名保护和非法名称测试。
2. 运行 `python -m pytest tests/test_rules.py -v`，确认因接口不存在而失败。
3. 实现最小数据模型、规则编译和名称转换。
4. 再次运行测试并确认通过。

### Task 2: 实现层级扫描和冲突预检

**Files:**
- Modify: `batch_rename/core.py`
- Test: `tests/test_scan.py`

1. 先写默认全层级、限制层级、对象类型筛选、中文名称和冲突测试。
2. 运行目标测试，确认预期失败。
3. 使用 `os.scandir` 实现不跟随符号链接的扫描与候选生成。
4. 标记已有目标、批内重复目标和不可访问项目。
5. 运行规则与扫描测试并确认通过。

### Task 3: 实现安全执行与进度

**Files:**
- Modify: `batch_rename/core.py`
- Test: `tests/test_execute.py`

1. 先写实际改名、跳过冲突、深层优先、扫描后状态变化和进度回调测试。
2. 运行目标测试，确认预期失败。
3. 实现逐项二次校验、深层优先执行和结果汇总。
4. 运行所有核心测试并确认通过。

### Task 4: 构建 Tkinter 图形界面

**Files:**
- Create: `batch_rename/app.py`
- Create: `main.py`
- Test: `tests/test_app.py`

1. 先写入口与界面模块可导入测试。
2. 运行测试，确认因模块不存在而失败。
3. 实现扫描范围、规则输入、分类预览、统计、确认、进度、结果详情和帮助窗口。
4. 为关键控件添加可见说明、示例、悬停提示和状态栏反馈。
5. 使用线程和队列执行扫描与改名，所有 Tk 控件仅在主线程更新。
6. 运行完整测试并启动 GUI 冒烟检查。

### Task 5: 文档和单文件构建

**Files:**
- Create: `README.md`
- Create: `requirements-dev.txt`
- Create: `BatchRename.spec`
- Create: `build.ps1`

1. 记录使用步骤、规则示例、安全行为、开发测试和构建方法。
2. 创建固定入口和无控制台单文件 PyInstaller 配置。
3. 运行 `python -m pytest -v`。
4. 运行 `powershell -ExecutionPolicy Bypass -File .\build.ps1`。
5. 确认 `dist/BatchRename.exe` 存在并可启动。
