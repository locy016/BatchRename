<div align="center">
  <img src="Python/assets/app-icon.png" width="112" alt="批量重命名应用图标">
  <h1>批量重命名</h1>
  <p>面向 Windows 多层目录的安全名称整理工具</p>
</div>

## 当前可用版本

当前稳定开发版本位于 [`Python`](Python/) 子项目，已经提供名称扫描、结果预览、普通文本与正则替换、安全执行、操作日志和整批撤回。它仍可独立运行、测试并通过 PyInstaller 生成 Windows 单文件程序。

- [查看当前产品介绍](Python/README.md)
- [查看 Python 版开发日志](Python/CHANGELOG.md)
- [查看 Python 版源码](Python/batch_rename/)

![当前 Python 版主工作台](Python/docs/images/batch-rename-main.png)

## 下一代桌面版本

项目准备采用 Rust、Tauri 2、Vue 3、TypeScript、Vue Router、Pinia 和 Element Plus 重建桌面版本。新架构的目标不是机械翻译界面代码，而是保持现有安全行为和历史日志兼容，同时拆分扫描、预览、执行、日志、撤回与界面状态，减少长期迭代形成的耦合和交互延迟。

下一代版本会与 Python 版并行验证。只有扫描、正则、冲突判断、执行顺序、异常日志和撤回行为通过兼容测试后，才会替换当前发行版。

- [查看 BatchRename 2.0 架构设计](docs/plans/2026-09-02-tauri-vue-rewrite-design.md)
- [查看分阶段实施计划](docs/plans/2026-09-02-tauri-vue-rewrite-implementation.md)

## Python 版运行与构建

```powershell
cd Python
python main.py
python -m pytest -q
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

也可以从仓库根目录直接构建：

```powershell
powershell -ExecutionPolicy Bypass -File .\Python\build.ps1
```

构建产物位于 `Python\dist\BatchRename.exe`。

## 仓库结构

```text
BatchRename/
├─ Python/      当前可运行、可测试、可构建的 Python 版本
├─ docs/        下一代架构设计与实施计划（计划阶段创建）
└─ README.md    整体项目入口
```

联系作者：`lo.c@live.cn`
