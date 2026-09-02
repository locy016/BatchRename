<div align="center">
  <img src="Python/assets/app-icon.png" width="112" alt="批量重命名应用图标">
  <h1>BatchRename 批量重命名</h1>
  <p>面向 Windows 多层目录的安全名称整理工具</p>
</div>

## BatchRename 2.0

2.0 采用 Rust、Tauri 2 和 Vue 3 构建，在保持 Python 版安全语义与日志格式兼容的基础上，让大目录扫描、结果浏览和操作管理保持流畅。当前版本为 `2.0.0-alpha.1` 测试候选。

它适合整理照片、项目资料、日期文件、编号文档和带有重复标签的目录：先按名称查询，查看完整匹配数和前 100 条安全预览，确认后才执行。替换后名称不变的项目仍会列出并解释原因，不会把“找到但无需修改”误显示为零。

主要能力：

- 当前目录及指定 1–N 层或全部层级扫描，文件夹与文件统一分类、自然名称排序。
- 普通文本和 Python 风格正则替换，默认保护扩展名，内置 15 个带前后示例的一键模板。
- 目标占用、批内重复、Windows 非法名称和名称未变化的预览门禁。
- 子项目优先、执行时二次检查、仅大小写安全改名和逐项原子操作日志。
- 关键词与状态历史查询、详情延迟加载、整批撤回预检、逆序恢复和失败重试。
- 跟随系统、浅色、深色三态外观，以及标准屏幕、宽屏和窄屏响应式布局。

## 下载与构建产物

Windows 构建同时产生两种候选：

- NSIS 安装包：适合日常安装使用，位于 `src-tauri\target\release\bundle\nsis`。
- 原始 EXE：无需安装的便携测试候选，位于 `src-tauri\target\release\batch-rename.exe`。

从源码验证并构建：

```powershell
powershell -NoProfile -File .\scripts\build-release.ps1
powershell -NoProfile -File .\scripts\smoke-test-release.ps1
```

需要 Node.js 24 LTS、Rust stable-msvc、Visual Studio C++ Build Tools 和 WebView2 Runtime。

## Python 版

成熟的 Python 版本完整保留在 [`Python`](Python/) 子项目中，可独立运行、测试或用 PyInstaller 构建单文件程序。迁移期需要继续使用原界面或验证旧工作流时，请查看 [Python 版产品说明](Python/README.md)。

## 安全与数据

根目录自身不会改名。操作日志保存在 `%LOCALAPPDATA%\BatchRename\operations`，外观设置保存在 `%LOCALAPPDATA%\BatchRename\settings.json`。软件在执行和撤回前会再次检查磁盘状态，但重要资料仍应先行备份。

- [2.0 架构设计](docs/plans/2026-09-02-tauri-vue-rewrite-design.md)
- [实施与验证计划](docs/plans/2026-09-02-tauri-vue-rewrite-implementation.md)
- [性能对比](docs/benchmarks/2026-09-02-tauri-comparison.md)

联系作者：`lo.c@live.cn`
